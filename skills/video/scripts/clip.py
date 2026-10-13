#!/usr/bin/env python3
"""Clip — from one line of description to footage that looks filmed: description (· reference images) → approval → generation (Higgsfield) → a human watches → game folder or docs folder.

  python3 clip.py check                                    can it run: keys · model · where clips go · the footage style paragraph
  python3 clip.py new <name> --for game|page [--seconds <n>] [--size landscape|portrait|square] [--image <picture>]... "<what the shot is — in English>"
  python3 clip.py approve <name>...                        after a human has seen the description and the reference images. Only approved clips are made
  python3 clip.py make <name>... [--again]                 generate with Higgsfield and download. Costs credits. A clip already in the making is waited on, not re-sent
  python3 clip.py place <name>...                          after a human has watched the clip. Puts it where it is used
  python3 clip.py status                                   how far each clip has come

One clip is one folder: <work>/<name>/ holds the record (clip.json) · the downloaded footage (clip.mp4).
There are two uses — page is outside the game, so the mp4 goes as it is to <page.dir>; game is converted to the format the engine reads (<game.convert>) and goes to <game.dir>.

The config picks the model — video.clip.model is the Higgsfield endpoint ID, the input names that differ per model go in video.clip.fields,
and values sent every time go in video.clip.params. The footage style is what sits between `<!-- footage-style -->` and
`<!-- /footage-style -->` in video.style_file (default docs/DESIGN.md) — when present it is appended to every description as it is.

Keys stay outside the repository — the environment variables HF_API_KEY_ID · HF_API_KEY_SECRET, or else the lines of the same
names in video.env_file (default ~/.config/gamedev-kit/asset.env).
"""
import datetime
import hashlib
import json
import mimetypes
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

CONFIG_NAME = "kit.config.json"
SECTION = "video"
DEFAULTS = {
    "work": "video",
    "style_file": "docs/DESIGN.md",
    "ffmpeg": "ffmpeg",
    "size": "landscape",
    "page": {"dir": "docs/video"},
    "game": {"dir": "", "ext": "", "convert": []},
    "env_file": "~/.config/gamedev-kit/asset.env",
    "clip": {
        "model": "higgsfield/cinema-studio/4.0",   # endpoint ID — in the docs of the model picked in the console
        "seconds": 5,
        "params": {},                              # values sent every time (resolution · generate_audio …)
        # this tool's word → the model's input name. Empty means not sent. Pictures go to images (several) or image (one), whichever the model takes
        "fields": {"prompt": "prompt", "seconds": "duration", "aspect": "aspect_ratio", "images": "image_urls", "image": ""},
    },
}
API = os.environ.get("HIGGSFIELD_API_BASE", "https://api.higgsfield.ai")  # the tests change this
POLL = float(os.environ.get("VIDEO_POLL_SEC", "2"))
WAIT = 30 * 60
ASPECT = {"landscape": "16:9", "portrait": "9:16", "square": "1:1"}
OPEN, CLOSE = "<!-- footage-style -->", "<!-- /footage-style -->"
DONE = ("completed", "failed", "nsfw", "canceled")

ROOT = ""
CFG = {}


def find_root(start):
    """Walk up from the current folder to the one holding kit.config.json. The tools live in the plugin; the game lives elsewhere."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            sys.exit(f"{CONFIG_NAME} not found — run this inside a game repository, after /gamedev-kit:init")
        d = up


def setup(root=None):
    global ROOT, CFG
    ROOT = os.path.abspath(root) if root else find_root(os.getcwd())
    have = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get(SECTION, {})
    CFG = dict(DEFAULTS, **have)
    for key in ("page", "game"):  # a partial section still gets the defaults for the rest
        CFG[key] = dict(DEFAULTS[key], **have.get(key, {}))
    clip = have.get("clip", {})
    CFG["clip"] = dict(DEFAULTS["clip"], **clip)
    CFG["clip"]["fields"] = dict(DEFAULTS["clip"]["fields"], **clip.get("fields", {}))


def key(name, need=True):
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.expanduser(CFG["env_file"])
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == name and v:
                return v.strip("\"'")
    if need:
        sys.exit(f"{name} is missing — add a line `{name}=...` to {path} (the video skill's 'first time only')")
    return ""


def http(url, body=None, headers=None, method=None, auth=True):
    """The key goes to Higgsfield only, not to where files are uploaded or downloaded (storage · CDN)."""
    headers = dict(headers or {})
    if auth:
        headers["Authorization"] = f"Key {key('HF_API_KEY_ID')}:{key('HF_API_KEY_SECRET')}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(text)
            text = err.get("detail") or err.get("message") or err.get("error") or text
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(f"{url.split('?')[0]} → {e.code}: {str(text)[:500]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"{url.split('?')[0]} → {e.reason}")


# ── record ────────────────────────────────────────────────────────────

def folder(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
        sys.exit(f"a name is lowercase letters · digits · underscores: {name!r}")
    return os.path.join(ROOT, CFG["work"], name)


def load(name):
    path = os.path.join(folder(name), "clip.json")
    if not os.path.exists(path):
        sys.exit(f"{name}: no record — clip.py new {name} --for game|page \"<what the shot is>\"")
    return json.load(open(path, encoding="utf-8"))


def save(rec):
    os.makedirs(folder(rec["name"]), exist_ok=True)
    with open(os.path.join(folder(rec["name"]), "clip.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")


def style():
    path = os.path.join(ROOT, CFG["style_file"])
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    return " ".join(text.split(OPEN, 1)[1].split(CLOSE, 1)[0].split()) if OPEN in text and CLOSE in text else ""


def prompt(rec):
    return " ".join(f"{rec['what'].rstrip('.')}. {style()}".split())


def mark(rec):
    """A value that changes when what is to be made changes — the approval is tied to it."""
    shas = [hashlib.sha1(open(os.path.join(ROOT, p), "rb").read()).hexdigest() for p in rec["images"]]
    seed = json.dumps([prompt(rec), rec["seconds"], rec["size"], shas, CFG["clip"]["model"], CFG["clip"]["params"]], ensure_ascii=False)
    return hashlib.sha1(seed.encode()).hexdigest()[:12]


def stage(rec):
    if rec.get("out") and rec.get("made", {}).get("mark") == mark(rec):
        return f"placed — {rec['out']}"
    if rec.get("made", {}).get("mark") == mark(rec):
        return "a human's turn to watch — then place"
    if rec.get("request", {}).get("mark") == mark(rec):
        return "in the making — make picks up the wait"
    if rec.get("approved") == mark(rec):
        return "ready to make — make (costs credits)"
    return "waiting for approval — description" + (" · reference images" if rec["images"] else "") + " to be seen by a human"


# ── making ────────────────────────────────────────────────────────────

def upload(path):
    ctype = mimetypes.guess_type(path)[0] or "image/png"
    made = json.loads(http(f"{API}/files/generate-upload-url", json.dumps({"content_type": ctype}).encode(),
                           {"Content-Type": "application/json"}))
    http(made["upload_url"], open(path, "rb").read(), made.get("upload_headers") or {"Content-Type": ctype}, method="PUT", auth=False)
    return made["public_url"]


def body(rec):
    clip, out = CFG["clip"], dict(CFG["clip"]["params"])
    names = clip["fields"]
    values = {"prompt": prompt(rec), "seconds": rec["seconds"], "aspect": ASPECT[rec["size"]]}
    for word, value in values.items():
        if names.get(word):
            out[names[word]] = value
    if rec["images"]:
        if not names.get("images") and not names.get("image"):
            sys.exit(f"{rec['name']}: there are reference images but images · image in {SECTION}.clip.fields are empty — fill in the input name this model takes pictures through")
        urls = [upload(os.path.join(ROOT, p)) for p in rec["images"]]
        if names.get("images"):
            out[names["images"]] = urls
        else:
            out[names["image"]] = urls[0]
    return out


def make(name, again):
    rec = load(name)
    now = mark(rec)
    if rec.get("approved") != now:
        sys.exit(f"{name}: not approved (again if the description · images · model changed after approval) — once a human has seen it, clip.py approve {name}")
    if rec.get("made", {}).get("mark") == now and not again:
        sys.exit(f"{name}: already made — for one more take of the same description, --again (costs credits again)")
    req = rec.get("request", {})
    if req.get("mark") != now or (again and rec.get("made", {}).get("id") == req.get("id")):
        req = {"mark": now, "key": str(uuid.uuid4()), "model": CFG["clip"]["model"], "prompt": prompt(rec)}
        payload = body(rec)
        rec["request"] = req
        save(rec)  # written before sending — if it is cut off, re-sending with the same key does not make it twice
        sent = json.loads(http(f"{API}/{req['model']}", json.dumps(payload).encode(),
                               {"Content-Type": "application/json", "Idempotency-Key": req["key"]}))
        req.update(id=sent["request_id"], status_url=sent["status_url"])
        save(rec)
        print(f"{name}: sent — {req['model']} · {rec['seconds']}s")
    elif not req.get("status_url"):
        sys.exit(f"{name}: cut off while sending — delete request from the record and make again")
    delay, until = POLL, time.time() + WAIT
    while True:
        state = json.loads(http(req["status_url"]))
        if state["status"] in DONE:
            break
        if time.time() > until:
            sys.exit(f"{name}: waited {WAIT // 60} minutes — make again picks up the wait")
        time.sleep(delay)
        delay = min(delay * 1.5, max(POLL, 10.0)) if POLL >= 1 else POLL
    if state["status"] != "completed":
        del rec["request"]
        save(rec)
        why = {"nsfw": "blocked by the content check — change the description or the images", "canceled": "canceled"}.get(state["status"], str(state.get("error") or "failed"))
        sys.exit(f"{name}: {why}")
    url = (state.get("video") or {}).get("url")
    if not url:
        sys.exit(f"{name}: finished but there is no video — does this model produce video ({req['model']})")
    mp4 = os.path.join(folder(name), "clip.mp4")
    with open(mp4, "wb") as f:
        f.write(http(url, auth=False))
    rec["made"] = {"mark": now, "id": req["id"], "date": str(datetime.date.today()), "model": req["model"], "prompt": req["prompt"]}
    rec.pop("out", None)
    save(rec)
    print(f"{name}: {os.path.relpath(mp4, ROOT)} — {os.path.getsize(mp4) / 1e6:.1f} MB\nThe user judges the motion — hand them the path. When they say it is good, place")


def place(name):
    rec = load(name)
    mp4 = os.path.join(folder(name), "clip.mp4")
    if rec.get("made", {}).get("mark") != mark(rec) or not os.path.exists(mp4):
        sys.exit(f"{name}: no footage made from the current description — clip.py make {name}")
    where = CFG[rec["for"]]
    ext = "mp4" if rec["for"] == "page" else where["ext"]
    if not where["dir"] or not ext or (rec["for"] == "game" and not where["convert"]):
        sys.exit(f"{SECTION}.{rec['for']} in {CONFIG_NAME} is not filled in — dir" + (" · ext · convert" if rec["for"] == "game" else ""))
    out = os.path.join(ROOT, where["dir"], f"{name}.{ext}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if rec["for"] == "page":
        shutil.copyfile(mp4, out)
    elif subprocess.run(shlex.split(CFG["ffmpeg"]) + ["-y", "-i", mp4, *where["convert"], out], cwd=ROOT).returncode != 0 \
            or not os.path.exists(out):
        sys.exit(f"{name}: could not convert to {ext} — check {SECTION}.game.convert")
    rec["out"] = os.path.relpath(out, ROOT)
    save(rec)
    print(f"{name}: {rec['out']} — {os.path.getsize(out) / 1e6:.1f} MB")


def check():
    bad = [f"{n} is missing — `{n}=...` in {os.path.expanduser(CFG['env_file'])}" for n in ("HF_API_KEY_ID", "HF_API_KEY_SECRET") if not key(n, need=False)]
    if not CFG["clip"]["model"]:
        bad.append(f"{SECTION}.clip.model is empty — the endpoint ID of the model picked in the Higgsfield console")
    if not CFG["game"]["dir"] or not CFG["game"]["convert"]:
        bad.append(f"{SECTION}.game is not filled in — clips played inside the game cannot be placed (page works)")
    print(f"Model: {CFG['clip']['model']} · default {CFG['clip']['seconds']}s · always sent {json.dumps(CFG['clip']['params'], ensure_ascii=False)}")
    print("Footage style: " + (style() or f"none — one English paragraph between `{OPEN}` … `{CLOSE}` in {CFG['style_file']} (it runs without one. Each clip will look different)"))
    print("\n".join(bad) if bad else "Ready to run")
    sys.exit(1 if bad else 0)


def status():
    base = os.path.join(ROOT, CFG["work"])
    names = sorted(n for n in os.listdir(base) if os.path.exists(os.path.join(base, n, "clip.json"))) if os.path.isdir(base) else []
    for n in names:
        rec = load(n)
        print(f"{n} ({rec['for']} · {rec['seconds']}s) — {stage(rec)}")
    if not names:
        print("No clips")


def main():
    args = sys.argv[1:]
    opts, images = {}, []
    for flag in ("--root", "--for", "--seconds", "--size"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    while "--image" in args:
        i = args.index("--image")
        images.append(args[i + 1])
        del args[i:i + 2]
    again = "--again" in args
    args = [a for a in args if a != "--again"]
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd not in ("check", "new", "approve", "make", "place", "status") or (cmd in ("approve", "make", "place") and not rest):
        sys.exit(__doc__)
    setup(opts.get("--root"))
    if cmd == "check":
        check()
    elif cmd == "status":
        status()
    elif cmd == "new":
        if len(rest) != 2 or opts.get("--for") not in ("game", "page") or opts.get("--size", CFG["size"]) not in ASPECT:
            sys.exit(__doc__)
        for p in images:
            if not os.path.exists(os.path.join(ROOT, p)):
                sys.exit(f"{p}: picture not found (path relative to the game root)")
        old = load(rest[0]) if os.path.exists(os.path.join(folder(rest[0]), "clip.json")) else {}
        rec = dict(old, name=rest[0], what=" ".join(rest[1].split()), images=images, size=opts.get("--size", CFG["size"]),
                   seconds=int(opts.get("--seconds", CFG["clip"]["seconds"])))
        rec["for"] = opts["--for"]
        save(rec)
        print(f"{rec['name']}: {stage(rec)}\nPrompt to send: {prompt(rec)}")
    else:
        for name in rest:
            try:
                if cmd == "approve":
                    rec = load(name)
                    rec["approved"] = mark(rec)
                    save(rec)
                    print(f"{name}: approved — {rec['seconds']}s · {CFG['clip']['model']}")
                elif cmd == "make":
                    make(name, again)
                else:
                    place(name)
            except RuntimeError as e:
                sys.exit(f"{name}: {e}")


if __name__ == "__main__":
    main()
