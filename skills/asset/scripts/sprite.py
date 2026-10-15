#!/usr/bin/env python3
"""Sprites — from a one-line description to a 2D picture and an animated sheet ready for the game (Ludo): picture → approval → motion.

  python3 sprite.py new <name> [--type <kind>] [--ref <picture> [--as-is]] "<what it is — in English>"
  python3 sprite.py image <name>... [--ref <picture>]  make one still picture
  python3 sprite.py approve <name>...                  after a human has looked at the picture. It goes to the game folder
  python3 sprite.py keep <name>...                     the art style changed after it was drawn and the user keeps it — no longer shown as old style
  python3 sprite.py reject <name> "<the user's words>"  turn it down — records why and lifts the approval
  python3 sprite.py animate <name> <motion> [--seconds <seconds>] [--frames <count>] "<what motion — in English>"
                                                       animate the approved picture into a sheet. Costs credits
  python3 sprite.py status                             how far each sprite has come · each sheet's grid
  python3 sprite.py credits                            credits left

One sprite is one folder: <work>/<name>/ holds the record (sprite.json) · the still (still.png) · a sheet and a preview per motion (<motion>.png · .gif).
The approved picture goes to <sprite.dir>/<name>.png, a sheet to <sprite.dir>/<name>_<motion>.png. Making the same motion again overwrites the sheet.
A sheet's grid (columns · rows · frame count · pixels per cell) is written in the record and shown by status — use it to slice in the engine.

--type is Ludo's image_type (sprite · icon · ui_asset · tile · texture · item-icon · portrait …). Omitted, the configured one.
--ref is that sprite's reference picture (path relative to the root) — the picture itself is shown to draw from, not put into words.
--as-is uses that picture as the still without redrawing (must be png).

Every description is followed by the same text as in asset.py (Art style · World · Learned) — `asset.py look` · `asset.py learn`.
Config is "sprite" inside "asset" in kit.config.json at the project root.

Keys stay outside the repository — environment variable LUDO_API_KEY, or else the line of the same name
in asset.env_file (default ~/.config/gamedev-kit/asset.env).
"""
import datetime
import hashlib
import json
import mimetypes
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asset  # same skill — finding the root · keys · the record folder · what is attached to every asset

SECTION = "sprite"
DEFAULTS = {
    "dir": "",                                   # folder finished pictures and sheets go to (relative to the root)
    "style_ref": "",                             # art style reference picture (path relative to the root). If set, every picture is matched to its style
    "view": "",                                  # the viewpoint in words — follows every description (one English line)
    "image": {"image_type": "sprite"},           # passed as is to Ludo's image request (art_style · perspective · aspect_ratio may be added)
    "animate": {"model": "hydra", "duration": 3},  # passed as is to Ludo's animate request (frames · frame_size · loop may be added)
}
LUDO = os.environ.get("LUDO_API_BASE", "https://api.ludo.ai/api")  # the tests change this
KEY = "LUDO_API_KEY"
POLL = float(os.environ.get("ASSET_POLL_SEC", "2"))
WAIT = 30 * 60
PNG = b"\x89PNG\r\n\x1a\n"
KINDS = ((b"RIFF", "webp"), (b"\xff\xd8", "jpg"), (b"GIF8", "gif"))
CONVERT = (("sips", "-s", "format", "png", "{src}", "--out", "{out}"), ("ffmpeg", "-y", "-loglevel", "error", "-i", "{src}", "{out}"),
           ("magick", "{src}", "{out}"), ("dwebp", "{src}", "-o", "{out}"))  # tries whichever exist, in order
DONE = ("succeeded", "failed", "canceled")
FRAMES = (4, 9, 16, 25, 36, 49, 64)

# What a picture must keep to be used as a sprite. Always attached, whatever the art style
FOR_2D = "A single subject, whole inside the frame with a margin around it. No text, no labels, no cast shadow, no ground."
SUBJECT_REF = ("The image shows the subject: redraw this exact subject — the same silhouette, proportions, colours and "
               "distinctive details — as described here.")

CFG = dict(DEFAULTS)


class Failed(RuntimeError):
    """Ludo ended the job as failed · canceled."""


def setup(root=None):
    global CFG
    asset.ROOT = os.path.abspath(root) if root else asset.find_root(os.getcwd())
    have = json.load(open(os.path.join(asset.ROOT, asset.CONFIG_NAME), encoding="utf-8")).get(asset.SECTION, {})
    asset.CFG = dict(asset.DEFAULTS, **have)
    mine = have.get(SECTION, {})
    CFG = dict(DEFAULTS, **mine)
    for key in ("image", "animate"):  # set only some and the rest keep their defaults
        CFG[key] = dict(DEFAULTS[key], **mine.get(key, {}))
    if not CFG["dir"]:
        sys.exit(f"{asset.SECTION}.{SECTION}.dir in {asset.CONFIG_NAME} is empty — set the folder sprites go to (the asset skill's Config section)")


def http(url, body=None, method=None, auth=True, content_type="application/json"):
    headers = {"Authorization": f"ApiKey {asset.key(KEY)}"} if auth else {}  # no key is sent to the addresses we are given (files)
    if body is not None:
        headers["Content-Type"] = content_type
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(text)
            text = err["error"]["message"] if isinstance(err.get("error"), dict) else err.get("message", text)
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        hint = " — not enough credits (sprite.py credits)" if e.code == 402 else ""
        raise RuntimeError(f"{url.split('?')[0]} → {e.code}: {str(text)[:500]}{hint}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"{url.split('?')[0]} → {e.reason}")


def call(path, body=None):
    return json.loads(http(LUDO + path, None if body is None else json.dumps(body).encode()))


def upload(path):
    """Upload a picture from the game to Ludo and get its address."""
    data, mime = open(path, "rb").read(), mimetypes.guess_type(path)[0] or "image/png"
    slot = call("/assets/uploads", {"mime_type": mime, "size": len(data)})
    http(slot["upload_url"], data, method="PUT", auth=False, content_type=mime)
    return slot["file_url"]


def run(rec, slot, label, path, body):
    """Start one job and wait it out → (result, credits spent). Written as soon as it starts — so an interruption does not buy the same job twice."""
    job = slot.get("job") or {}
    if not (job.get("id") and job.get("status") not in DONE):
        made = call(path, body())
        if not (isinstance(made, dict) and made.get("id") and made.get("status")):
            return made, None  # the result came straight back, not a job
        job = slot["job"] = {"id": made["id"], "status": made["status"]}
        save(rec)
        print(f"{label}: Ludo job {job['id']}", flush=True)
    until = time.time() + WAIT
    while True:
        got = call(f"/assets/jobs/{job['id']}?wait=30")
        job["status"] = got["status"]
        if got["status"] in DONE:
            job["credits"] = got.get("credits_charged")
            save(rec)
            if got["status"] != "succeeded":
                raise Failed(f"{label}: Ludo {got['status']} — {(got.get('error') or {}).get('message', '')} (credits are refunded)")
            return got.get("result"), got.get("credits_charged")
        print(f"{label}: {got['status']}", flush=True)
        if time.time() > until:
            sys.exit(f"{label}: not finished yet — run the same command again to keep waiting")
        time.sleep(POLL)


# ── Records ───────────────────────────────────────────────────────────

def load(name):
    path = os.path.join(asset.folder(name), "sprite.json")
    if not os.path.exists(path):
        sys.exit(f"{name}: no record — sprite.py new {name} \"<what it is>\"")
    return json.load(open(path, encoding="utf-8"))


def save(rec):
    path = os.path.join(asset.folder(rec["name"]), "sprite.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")


def still_path(name):
    return os.path.join(asset.folder(name), "still.png")


def rel(path):
    return os.path.relpath(path, asset.ROOT)


def approved(rec):
    """Is the approved picture still the same one."""
    path = still_path(rec["name"])
    return bool(rec.get("approved")) and os.path.exists(path) and asset.sha(path) == rec["approved"]


def png_size(path):
    head = open(path, "rb").read(24)
    return struct.unpack(">II", head[16:24]) if head[:8] == PNG else (0, 0)


def save_png(out, data):
    """Place the downloaded picture as a PNG. If it is .png in name only and another format inside (WebP and the like), convert it with a tool on this machine — the engine trusts the name and fails to read it."""
    if data[:8] == PNG:
        return open(out, "wb").write(data)
    kind = next((ext for magic, ext in KINDS if data.startswith(magic)), "bin")
    raw = f"{os.path.splitext(out)[0]}.{kind}"
    open(raw, "wb").write(data)
    if os.path.exists(out):
        os.remove(out)
    for tool, *args in CONVERT:
        if not shutil.which(tool):
            continue
        subprocess.run([shutil.which(tool)] + [a.format(src=raw, out=out) for a in args], capture_output=True)
        if os.path.exists(out) and open(out, "rb").read(8) == PNG:
            return os.remove(raw)
    sys.exit(f"{rel(raw)}: the downloaded picture is not a PNG ({kind}) and there is no tool to convert it — install one of {' · '.join(c[0] for c in CONVERT)}. "
             f"What came was left as is (rerunning buys a new one — you can also convert it to PNG by hand and put it at {rel(out)})")


def stage(rec):
    if approved(rec):
        return "approved — ready to animate"
    if os.path.exists(still_path(rec["name"])):
        return "picture — look, then approve"
    return "new — image"


# ── Picture ───────────────────────────────────────────────────────────

def image(name, ref=None):
    rec, words = load(name), asset.look()
    if ref:
        rec["ref"] = ref
    subject = os.path.join(asset.ROOT, rec["ref"]) if rec.get("ref") else ""
    if subject and not os.path.exists(subject):
        sys.exit(f"{name}: reference not found — {rec['ref']} (path relative to the game root)")
    style_ref = os.path.join(asset.ROOT, CFG["style_ref"]) if CFG["style_ref"] else ""
    if style_ref and not os.path.exists(style_ref):
        sys.exit(f"{asset.SECTION}.{SECTION}.style_ref: {CFG['style_ref']} not found")
    out, credits = still_path(name), None
    os.makedirs(asset.folder(name), exist_ok=True)
    if subject and rec.get("as_is"):
        prompt = f"(reference used as is: {rec['ref']})"
        shutil.copyfile(subject, out)
    else:
        view = CFG["view"].strip().rstrip(".")
        said = " ".join(x for x in (rec["subject"] + ".", view + "." if view else "", words, FOR_2D) if x)
        kind = {"image_type": rec.get("type") or CFG["image"]["image_type"]}
        if subject:
            prompt = f"{SUBJECT_REF} {said}"
            path, body = "/assets/image/edit", lambda: dict(kind, image=upload(subject), prompt=prompt,
                                                           **({"reference_image": upload(style_ref)} if style_ref else {}))
        elif style_ref:
            prompt = said
            path, body = "/assets/image/style", lambda: dict(kind, style_image=upload(style_ref), prompt=prompt)
        else:
            prompt = said
            path, body = "/assets/image", lambda: dict(CFG["image"], **kind, prompt=prompt)
        result, credits = run(rec, rec, name, path, body)
        save_png(out, http(result[0]["url"], auth=False))
    rec.setdefault("prompts", {})["still"] = prompt
    rec["approved"] = None  # a changed picture needs approval again
    rec["image"] = dict(CFG["image"], style_ref=CFG["style_ref"], credits=credits,
                        style=hashlib.sha1(asset.style().encode()).hexdigest()[:8])  # which art style it was drawn in
    save(rec)
    print(f"{name}: {rel(out)} — {' × '.join(str(x) for x in png_size(out))} px" + (f" · credits {credits}" if credits is not None else ""), flush=True)


def approve(name):
    rec = load(name)
    if not os.path.exists(still_path(name)):
        sys.exit(f"{name}: no picture — sprite.py image {name}")
    out = os.path.join(asset.ROOT, CFG["dir"], f"{name}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copyfile(still_path(name), out)
    rec["approved"], rec["out"] = asset.sha(still_path(name)), rel(out)
    save(rec)
    print(f"{name}: approved — {rec['out']}")
    asset.after(CFG)


def keep(name):
    """The picture stays although the art style changed after it was drawn — marked as drawn in the current one, so the board stops calling it old style."""
    rec = load(name)
    if not os.path.exists(still_path(name)):
        sys.exit(f"{name}: no picture — sprite.py image {name}")
    rec["image"] = dict(rec.get("image") or {}, style=hashlib.sha1(asset.style().encode()).hexdigest()[:8], kept=str(datetime.date.today()))
    save(rec)
    print(f"{name}: kept under the current art style")


def drop(name):
    """An attempt the user no longer wants (a draft beside the one that was used) — marked dropped, so the board stops asking about it.
    Nothing is deleted; `image` on it again lifts the mark."""
    rec = load(name)
    rec["dropped"] = str(datetime.date.today())
    save(rec)
    print(f"{name}: dropped — off the review; the files stay")


def reject(name, said):
    """The user turned it down — their words are the material for "Learned". Lifts the approval."""
    rec = load(name)
    rec.setdefault("said", []).append({"date": str(datetime.date.today()), "said": " ".join(said.split())})
    rec["approved"] = None
    save(rec)
    print(f"{name}: rejection recorded (#{len(rec['said'])}). If it holds for other assets too, add a line with `asset.py learn`")


# ── Motion ───────────────────────────────────────────────────────────

def animate(name, motion, prompt, seconds, frames):
    rec = load(name)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", motion):
        sys.exit(f"motion names are lowercase letters · digits · underscores: {motion!r}")
    if not approved(rec):
        sys.exit(f"{name}: no approved picture — after a human has looked at it, sprite.py approve {name}")
    m = rec.setdefault("motions", {}).setdefault(motion, {})
    m["prompt"] = prompt
    ask = dict(CFG["animate"], **({"duration": seconds} if seconds else {}), **({"frames": frames} if frames else {}))
    result, credits = run(rec, m, f"{name} {motion}", "/assets/sprite/animate",
                          lambda: dict(ask, motion_prompt=prompt, initial_image=upload(still_path(name)), gif=True))
    sheet = os.path.join(asset.folder(name), f"{motion}.png")
    save_png(sheet, http(result["spritesheet_url"], auth=False))
    gif = ""
    if result.get("gif_url"):
        gif = os.path.join(asset.folder(name), f"{motion}.gif")
        open(gif, "wb").write(http(result["gif_url"], auth=False))
    out = os.path.join(asset.ROOT, CFG["dir"], f"{name}_{motion}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copyfile(sheet, out)
    (w, h), cols, rows = png_size(sheet), result.get("num_cols") or 0, result.get("num_rows") or 0
    m.update(out=rel(out), frames=result.get("num_frames"), cols=cols, rows=rows, cell=[w // cols, h // rows] if cols and rows else None,
             seconds=result.get("duration"), asked=ask, credits=credits, made=m.get("made", 0) + 1)
    save(rec)
    print(f"{name} {motion}: {m['out']} — {grid(m)}" + (f" · credits {credits}" if credits is not None else "")
          + (f"\npreview (for the user to watch): {rel(gif)}" if gif else ""))
    asset.after(CFG)


def grid(m):
    cell = " × ".join(str(x) for x in m["cell"]) + " px" if m.get("cell") else "?"
    return f"{m.get('frames', '?')} frames · {m.get('cols', '?')} cols × {m.get('rows', '?')} rows · cell {cell}"


def status():
    work = os.path.join(asset.ROOT, asset.CFG["work"])
    names = sorted(n for n in os.listdir(work) if os.path.exists(os.path.join(work, n, "sprite.json"))) \
        if os.path.isdir(work) else []
    if not names:
        print("no sprites — sprite.py new <name> \"<what it is>\"")
    for n in names:
        rec = load(n)
        print(f"{n:<24} {stage(rec):<28} {rec['subject'][:50]}")
        for motion, m in (rec.get("motions") or {}).items():
            if m.get("out"):
                print(f"  {motion:<22} {m['out']} — {grid(m)}")
            else:
                print(f"  {motion:<22} in progress — continue with the same animate command")


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--type", "--ref", "--seconds", "--frames"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    as_is = "--as-is" in args
    args = [a for a in args if a != "--as-is"]
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd not in ("new", "image", "approve", "keep", "drop", "reject", "animate", "status", "credits") or (cmd not in ("status", "credits") and not rest):
        sys.exit(__doc__)
    setup(opts.get("--root"))
    ref = opts.get("--ref")
    if ref and not os.path.exists(os.path.join(asset.ROOT, ref)):
        sys.exit(f"{ref}: reference not found (path relative to the game root)")
    if as_is and (cmd != "new" or not ref or not ref.lower().endswith(".png")):
        sys.exit("--as-is goes with new and a png --ref")
    try:
        seconds = float(opts["--seconds"]) if "--seconds" in opts else None
        frames = int(opts["--frames"]) if "--frames" in opts else None
        if (seconds is not None and seconds <= 0) or (frames is not None and frames not in FRAMES):
            raise ValueError
    except ValueError:
        sys.exit("--seconds is seconds above 0, --frames is one of " + " · ".join(str(x) for x in FRAMES))
    try:
        if cmd == "new":
            if len(rest) != 2:
                sys.exit(__doc__)
            name, subject = rest[0], rest[1].strip().rstrip(".")
            if os.path.exists(os.path.join(asset.folder(name), "sprite.json")):
                sys.exit(f"{name}: already exists — use another name or edit {rel(asset.folder(name))}/sprite.json")
            rec = {"name": name, "kind": "sprite", "subject": subject, "type": opts.get("--type"), "created": str(datetime.date.today())}
            if ref:
                rec.update(ref=ref, as_is=as_is)
            save(rec)
            print(f"{name}: {rel(asset.folder(name))}/sprite.json" + (f" · reference {ref}" + (" (used as is)" if as_is else "") if ref else ""))
        elif cmd == "image":
            for name in rest:
                image(name, ref)
        elif cmd == "approve":
            for name in rest:
                approve(name)
        elif cmd == "keep":
            for name in rest:
                keep(name)
        elif cmd == "drop":
            for name in rest:
                drop(name)
        elif cmd == "reject":
            if len(rest) != 2:
                sys.exit(__doc__)
            reject(*rest)
        elif cmd == "animate":
            if len(rest) != 3:
                sys.exit(__doc__)
            animate(rest[0], rest[1], " ".join(rest[2].split()), seconds, frames)
        elif cmd == "credits":
            got = call("/assets/account")
            credits = got.get("credits") or {}
            print(f"credits left: {credits.get('available', credits)}")
        else:
            status()
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
