#!/usr/bin/env python3
"""Assets — from a one-line description to a 3D model ready for the game: image (OpenAI) → approval → mesh (Meshy) → finishing (Blender).

  python3 asset.py new <name> --size <meters> [--poly <triangles>] [--ref <photo> [--as-is]] "<what it is — in English>"
  python3 asset.py image <name>... [--view back [--note "<text for that view only — in English>"]] [--ref <photo>]   make the images. With --view, redo only that view
  python3 asset.py approve <name>...               after a human has looked at the images. Only approved images become meshes
  python3 asset.py reject <name> "<the user's words>"   turn it down — records why and lifts the approval
  python3 asset.py learn "<one line — in English>"  add what turning assets down taught as one line of "Learned". Attached to every asset from then on
  python3 asset.py look                            what is attached to every asset — Art style · World · Learned
  python3 asset.py mesh <name>...                  make the mesh with Meshy, download it and finish it. Costs credits
  python3 asset.py finish <name>... [--size <meters>]  finish a downloaded mesh again (size · origin · export)
  python3 asset.py status                          how far each asset has come

One asset is one folder: <work>/<name>/ holds the record (asset.json) · an image per view · the downloaded mesh (raw.glb).
The finished model goes to <dir>/<name>.<format>. Size is the length of the longest side (meters); the origin is the center of the base.

What is attached to every prompt sits in asset.style_file (default docs/DESIGN.md), in three layers:
  `<!-- asset-style -->`    Art style — how it is drawn. Fixed (changing it sets new assets against the ones already made)
  `<!-- asset-world -->`    World — what exists in this world (era · materials · motifs that recur). Optional
  `<!-- asset-learned -->`  Learned — lines from what the user said when turning assets down. `learn` adds them. Optional
Config is "asset" in kit.config.json at the project root.

--ref is that asset's reference photo (path relative to the root) — the photo itself is shown to draw from, not put into words.
--as-is uses the photo as the first view without redrawing (must be png. The look is then the photo's).

Keys stay outside the repository — environment variables OPENAI_API_KEY · MESHY_API_KEY, or else the line of the same name
in asset.env_file (default ~/.config/gamedev-kit/asset.env).
"""
import base64
import datetime
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

CONFIG_NAME = "kit.config.json"
SECTION = "asset"
DEFAULTS = {
    "dir": "",                     # folder finished models go to (relative to the root)
    "format": "glb",               # glb | fbx
    "work": "assets/_gen",         # per asset: the record and intermediate files
    "style_file": "docs/DESIGN.md",
    "refs": [],                    # art style reference images (paths relative to the root). If set, they go in with every first image
    "views": ["front", "back"],    # views to make. The first is the base and the rest are drawn from it. Up to four
    "image": {"model": "gpt-image-2.5-flare", "size": "1024x1024", "quality": "medium"},
    "meshy": {"ai_model": "latest", "target_polycount": 5000, "topology": "triangle", "enable_pbr": False},
    "blender": "blender",
    "env_file": "~/.config/gamedev-kit/asset.env",
}
OPENAI = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")  # the tests change this
MESHY = os.environ.get("MESHY_API_BASE", "https://api.meshy.ai/openapi/v1")
POLL = float(os.environ.get("ASSET_POLL_SEC", "10"))
WAIT = 30 * 60
FINISH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_finish.py")

VIEWS = {
    "front": "front view, straight on, camera at the object's mid height",
    "back": "back view, seen from directly behind, camera at the object's mid height",
    "left": "left side view, exact profile, camera at the object's mid height",
    "right": "right side view, exact profile, camera at the object's mid height",
}
# What an image must keep to become a mesh. Always attached, whatever the art style
FOR_3D = ("A single object, centered, the whole object inside the frame with a margin around it. "
          "Transparent background. Flat, even, neutral lighting — no cast shadows, no ground, no rim light. "
          "No text, no labels, no other objects.")
SAME = "The same object as in the first image — identical shape, proportions, colors and materials — shown in"
# Drawn from the front image alone, things whose two sides differ (back of a hand and palm · a limb on one side) come out as the front mirrored — say what it is and not to flip it
TURNED = ("The object is: {subject}. Draw what is really seen from this side — do not mirror, flip or repeat the first image. "
          "Where the two sides differ, show the side this view faces.")
STYLE_ONLY = "Use the attached images only as a style reference (palette, shading, level of detail); do not copy their subjects."
SUBJECT_REF = ("The first attached image shows the subject: redraw this exact object — the same silhouette, proportions, colours and "
               "distinctive details — in the style described below.")
STYLE_REST = "The other attached images are style references only (palette, shading, level of detail); do not copy their subjects."
OPEN, CLOSE = "<!-- asset-style -->", "<!-- /asset-style -->"
WORLD = ("<!-- asset-world -->", "<!-- /asset-world -->")
LEARNED = ("<!-- asset-learned -->", "<!-- /asset-learned -->")
LEARN_MAX = 12  # past this the later lines stop taking effect — merge them

ROOT = ""
CFG = dict(DEFAULTS)


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
    for key in ("image", "meshy"):  # set only some and the rest keep their defaults
        CFG[key] = dict(DEFAULTS[key], **have.get(key, {}))
    if not CFG["dir"]:
        sys.exit(f"{SECTION}.dir in {CONFIG_NAME} is empty — set the folder models go to (the asset skill's Config section)")
    bad = [v for v in CFG["views"] if v not in VIEWS]
    if bad or not 1 <= len(CFG["views"]) <= 4:
        sys.exit(f"{SECTION}.views takes one to four of " + " · ".join(VIEWS))


def key(name):
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.expanduser(CFG["env_file"])
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == name and v:
                return v.strip("\"'")
    sys.exit(f"{name} is missing — add a `{name}=...` line to {path} (the asset skill's 'First time only')")


def http(url, token=None, body=None, content_type="application/json"):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if body is not None:
        headers["Content-Type"] = content_type
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(text)
            text = err["error"]["message"] if isinstance(err.get("error"), dict) else err.get("message", text)
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        raise RuntimeError(f"{url.split('?')[0]} → {e.code}: {str(text)[:500]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"{url.split('?')[0]} → {e.reason}")


# ── Records ───────────────────────────────────────────────────────────

def folder(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
        sys.exit(f"names are lowercase letters · digits · underscores: {name!r}")
    return os.path.join(ROOT, CFG["work"], name)


def load(name):
    path = os.path.join(folder(name), "asset.json")
    if not os.path.exists(path):
        sys.exit(f"{name}: no record — asset.py new {name} --size <meters> \"<what it is>\"")
    return json.load(open(path, encoding="utf-8"))


def save(rec):
    path = os.path.join(folder(rec["name"]), "asset.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")


def sha(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()


def image_path(name, view):
    return os.path.join(folder(name), f"{view}.png")


def out_path(name):
    return os.path.join(ROOT, CFG["dir"], f"{name}.{CFG['format']}")


def approved(rec):
    """Are the approved images still the same ones."""
    marks = rec.get("approved") or {}
    return bool(marks) and list(marks) == CFG["views"] and all(
        os.path.exists(image_path(rec["name"], v)) and sha(image_path(rec["name"], v)) == h for v, h in marks.items())


def stage(rec):
    if rec.get("out") and os.path.exists(os.path.join(ROOT, rec["out"])):
        return "done"
    task = rec.get("meshy") or {}
    if task.get("status") == "SUCCEEDED":
        return "mesh received — finish"
    if task.get("id") and task.get("status") not in ("FAILED", "CANCELED"):
        return "meshing — continue with mesh"
    if approved(rec):
        return "approved — mesh"
    if all(os.path.exists(image_path(rec["name"], v)) for v in CFG["views"]):
        return "images — look, then approve"
    return "new — image"


# ── Images ───────────────────────────────────────────────────────────

def style():
    path = os.path.join(ROOT, CFG["style_file"])
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    if OPEN not in text or CLOSE not in text:
        sys.exit(f"{CFG['style_file']} has no `{OPEN}` … `{CLOSE}` — write this game's art style between them as one English paragraph")
    block = " ".join(text.split(OPEN, 1)[1].split(CLOSE, 1)[0].split())
    if not block:
        sys.exit(f"the art style paragraph in {CFG['style_file']} is empty")
    return block


def between(marks):
    """The text between two markers in style_file. None if the markers are missing."""
    path = os.path.join(ROOT, CFG["style_file"])
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    return text.split(marks[0], 1)[1].split(marks[1], 1)[0] if marks[0] in text and marks[1] in text else None


def learned():
    return [re.sub(r"^[-*]\s*", "", line.strip()) for line in (between(LEARNED) or "").split("\n") if line.strip()]


def look():
    """What is attached to every asset: Art style (fixed) + World + Learned."""
    world = " ".join((between(WORLD) or "").split())
    rules = " ".join(line.rstrip(".") + "." for line in learned())
    return " ".join(x for x in (style(), world, rules) if x)


def multipart(fields, files):
    mark = uuid.uuid4().hex
    parts = [f'--{mark}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    for path in files:
        parts.append(f'--{mark}\r\nContent-Disposition: form-data; name="image[]"; filename="{os.path.basename(path)}"\r\n'
                     f"Content-Type: {mimetypes.guess_type(path)[0] or 'image/png'}\r\n\r\n".encode() + open(path, "rb").read() + b"\r\n")
    return b"".join(parts) + f"--{mark}--\r\n".encode(), f"multipart/form-data; boundary={mark}"


def draw(prompt, inputs):
    """One image. With inputs, it is drawn from them."""
    fields = dict(CFG["image"], prompt=prompt, background="transparent", output_format="png")
    if inputs:
        body, ctype = multipart(fields, inputs)
        raw = http(f"{OPENAI}/images/edits", key("OPENAI_API_KEY"), body, ctype)
    else:
        raw = http(f"{OPENAI}/images/generations", key("OPENAI_API_KEY"), json.dumps(fields).encode())
    return base64.b64decode(json.loads(raw)["data"][0]["b64_json"])


def image(name, only, ref=None, note=None):
    rec, words = load(name), look()
    if note is not None:
        if not only:
            sys.exit("--note goes with --view — it is text for that view only")
        rec.setdefault("notes", {})[only] = " ".join(note.split())
    if ref:
        rec["ref"] = ref
    subject = os.path.join(ROOT, rec["ref"]) if rec.get("ref") else ""
    if subject and not os.path.exists(subject):
        sys.exit(f"{name}: reference not found — {rec['ref']} (path relative to the game root)")
    refs = [os.path.join(ROOT, r) for r in CFG["refs"]]
    for r in refs:
        if not os.path.exists(r):
            sys.exit(f"{SECTION}.refs: {os.path.relpath(r, ROOT)} not found")
    first = CFG["views"][0]
    todo = [only] if only else CFG["views"]
    if only and only not in CFG["views"]:
        sys.exit(f"{only}: not one of the configured views — " + " · ".join(CFG["views"]))
    if first not in todo and not os.path.exists(image_path(name, first)):
        sys.exit(f"{name}: the base view ({first}) image must exist first")
    for view in todo:
        said = rec.get("notes", {}).get(view)
        mine = f"{said.rstrip('.')}. " if said else ""  # text for this view only (which side is nearer the viewer, and the like)
        if view == first and subject and rec.get("as_is"):
            prompt, data = f"(reference used as is: {rec['ref']})", open(subject, "rb").read()
        elif view == first:
            lead = f"{SUBJECT_REF} " + (f"{STYLE_REST} " if refs else "") if subject else (f"{STYLE_ONLY} " if refs else "")
            prompt = f"{lead}{rec['subject']}. {VIEWS[view].capitalize()}. {mine}{words} {FOR_3D}"
            data = draw(prompt, ([subject] if subject else []) + refs)
        else:
            prompt = f"{SAME} {VIEWS[view]}. {TURNED.format(subject=rec['subject'])} {mine}{words} {FOR_3D}"
            data = draw(prompt, [image_path(name, first)])
        os.makedirs(folder(name), exist_ok=True)
        open(image_path(name, view), "wb").write(data)
        rec.setdefault("prompts", {})[view] = prompt
        print(f"{name}: {os.path.relpath(image_path(name, view), ROOT)}", flush=True)
    rec["approved"] = None  # a changed image needs approval again
    rec["image"] = dict(CFG["image"], refs=CFG["refs"], style=hashlib.sha1(style().encode()).hexdigest()[:8])  # which art style it was drawn in
    save(rec)


def reject(name, said):
    """The user turned it down — their words are the material for "Learned". Lifts the approval."""
    rec = load(name)
    rec.setdefault("said", []).append({"date": str(datetime.date.today()), "said": " ".join(said.split())})
    rec["approved"] = None
    save(rec)
    print(f"{name}: rejection recorded (#{len(rec['said'])}). If it holds for other assets too, add a line with `learn`")


def learn(line):
    path = os.path.join(ROOT, CFG["style_file"])
    if between(LEARNED) is None:
        sys.exit(f"{CFG['style_file']} has no `{LEARNED[0]}` … `{LEARNED[1]}` — put those two lines below the art style paragraph")
    have = learned()
    if len(have) >= LEARN_MAX:
        sys.exit(f"Learned has {len(have)} lines — no more are added. Merge lines that overlap, or move a rule that always holds up into the art style paragraph (with the user)")
    text = open(path, encoding="utf-8").read()
    head, tail = text.split(LEARNED[0], 1)[0], text.split(LEARNED[1], 1)[1]
    lines = have + [" ".join(line.split()).rstrip(".")]
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + LEARNED[0] + "\n" + "\n".join(f"- {x}" for x in lines) + "\n" + LEARNED[1] + tail)
    print(f"Learned {len(lines)} line(s) — attached to assets drawn from now on:\n" + "\n".join(f"- {x}" for x in lines))


def approve(name):
    rec = load(name)
    missing = [v for v in CFG["views"] if not os.path.exists(image_path(name, v))]
    if missing:
        sys.exit(f"{name}: images missing ({' · '.join(missing)}) — asset.py image {name}")
    rec["approved"] = {v: sha(image_path(name, v)) for v in CFG["views"]}
    save(rec)
    print(f"{name}: approved — " + " · ".join(CFG["views"]))


# ── Mesh ──────────────────────────────────────────────────────────────

def start(rec):
    name = rec["name"]
    urls = ["data:image/png;base64," + base64.b64encode(open(image_path(name, v), "rb").read()).decode()
            for v in CFG["views"]]
    body = dict(CFG["meshy"], image_urls=urls, should_remesh=True, should_texture=True, target_formats=["glb"])
    if rec.get("poly"):
        body["target_polycount"] = rec["poly"]
    made = json.loads(http(f"{MESHY}/multi-image-to-3d", key("MESHY_API_KEY"), json.dumps(body).encode()))["result"]
    rec["meshy"] = {"id": made, "status": "PENDING", "params": {k: v for k, v in body.items() if k != "image_urls"},
                    "images": dict(rec["approved"])}
    save(rec)  # written as soon as it is made — so an interruption does not buy the same task twice
    print(f"{name}: Meshy task {made}", flush=True)


def mesh(names):
    recs = [load(n) for n in names]
    for rec in recs:
        if not approved(rec):
            sys.exit(f"{rec['name']}: no approved images — after a human has looked at them, asset.py approve {rec['name']}")
    for rec in recs:
        task = rec.get("meshy") or {}
        fresh = task.get("images") == rec["approved"]  # was this task made from the images approved now
        if not (fresh and task.get("id") and task.get("status") not in ("FAILED", "CANCELED")):
            start(rec)
    waiting, failed, until = [r for r in recs if r["meshy"]["status"] != "SUCCEEDED"], [], time.time() + WAIT
    while waiting:
        for rec in list(waiting):
            task = json.loads(http(f"{MESHY}/multi-image-to-3d/{rec['meshy']['id']}", key("MESHY_API_KEY")))
            rec["meshy"]["status"] = task["status"]
            if task["status"] == "SUCCEEDED":
                rec["meshy"]["credits"] = task.get("consumed_credits")
                open(os.path.join(folder(rec["name"]), "raw.glb"), "wb").write(http(task["model_urls"]["glb"]))
                print(f"{rec['name']}: mesh received (credits {task.get('consumed_credits', '?')})", flush=True)
            elif task["status"] in ("FAILED", "CANCELED"):
                rec["meshy"]["error"] = (task.get("task_error") or {}).get("message", "")
                failed.append(f"{rec['name']}: {task['status']} {rec['meshy']['error']}")
            else:
                print(f"{rec['name']}: {task['status']} {task.get('progress', 0)}%", flush=True)
                continue
            save(rec)
            waiting.remove(rec)
        if waiting:
            if time.time() > until:
                for rec in waiting:
                    save(rec)
                sys.exit("not finished yet: " + " · ".join(r["name"] for r in waiting) + " — run the same mesh command again to keep waiting")
            time.sleep(POLL)
    for rec in recs:
        if rec["meshy"]["status"] == "SUCCEEDED":
            finish(rec["name"], None)
    if failed:
        sys.exit("Meshy failed (credits are refunded):\n- " + "\n- ".join(failed))


def finish(name, size):
    rec = load(name)
    raw = os.path.join(folder(name), "raw.glb")
    if not os.path.exists(raw):
        sys.exit(f"{name}: no downloaded mesh — asset.py mesh {name}")
    if size:
        rec["size"] = size
    if not shutil.which(CFG["blender"]):
        sys.exit(f"Blender not found ({CFG['blender']}) — install it or set {SECTION}.blender to the executable's path")
    out = out_path(name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    p = subprocess.run([CFG["blender"], "--background", "--factory-startup", "--python", FINISH, "--",
                        raw, out, str(rec["size"]), CFG["format"]], capture_output=True, text=True)
    done = re.search(r"^FINISH (.*)$", p.stdout, re.M)
    if p.returncode != 0 or not done or not os.path.exists(out):
        sys.exit(f"{name}: finishing failed\n{(p.stdout + p.stderr).strip()[-2000:]}")
    rec["out"] = os.path.relpath(out, ROOT)
    rec["finished"] = dict(json.loads(done.group(1)), date=str(datetime.date.today()))
    save(rec)
    f = rec["finished"]
    print(f"{name}: {rec['out']} — triangles {f['tris']} · {' × '.join(str(x) for x in f['size'])} m · "
          f"{os.path.getsize(out) / 1e6:.1f} MB")


def status():
    work = os.path.join(ROOT, CFG["work"])
    names = sorted(n for n in os.listdir(work) if os.path.exists(os.path.join(work, n, "asset.json"))) \
        if os.path.isdir(work) else []
    if not names:
        print("no assets — asset.py new <name> --size <meters> \"<what it is>\"")
    for n in names:
        rec = load(n)
        print(f"{n:<24} {stage(rec):<28} {rec.get('size', '?')} m · {rec.get('subject', '')[:50]}")  # a hand-written record may have fields missing


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--size", "--poly", "--view", "--ref", "--note"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    as_is = "--as-is" in args
    args = [a for a in args if a != "--as-is"]
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd not in ("new", "image", "approve", "reject", "learn", "look", "mesh", "finish", "status") or (cmd not in ("status", "look") and not rest):
        sys.exit(__doc__)
    setup(opts.get("--root"))
    ref = opts.get("--ref")
    if ref and not os.path.exists(os.path.join(ROOT, ref)):
        sys.exit(f"{ref}: reference not found (path relative to the game root)")
    if as_is and (cmd != "new" or not ref or not ref.lower().endswith(".png")):
        sys.exit("--as-is goes with new and a png --ref")
    try:
        size = float(opts["--size"]) if "--size" in opts else None
        if size is not None and size <= 0:
            raise ValueError
        poly = int(opts["--poly"]) if "--poly" in opts else None
    except ValueError:
        sys.exit("--size is meters above 0, --poly is a triangle count")
    try:
        if cmd == "new":
            if len(rest) != 2 or size is None:
                sys.exit(__doc__)
            name, subject = rest[0], rest[1].strip().rstrip(".")
            if os.path.exists(os.path.join(folder(name), "asset.json")):
                sys.exit(f"{name}: already exists — use another name or edit {os.path.relpath(folder(name), ROOT)}/asset.json")
            rec = {"name": name, "subject": subject, "size": size, "poly": poly, "created": str(datetime.date.today())}
            if ref:
                rec.update(ref=ref, as_is=as_is)
            save(rec)
            print(f"{name}: {os.path.relpath(folder(name), ROOT)}/asset.json" + (f" · reference {ref}" + (" (used as is)" if as_is else "") if ref else ""))
        elif cmd == "image":
            for name in rest:
                image(name, opts.get("--view"), ref, opts.get("--note"))
        elif cmd == "reject":
            if len(rest) != 2:
                sys.exit(__doc__)
            reject(*rest)
        elif cmd == "learn":
            learn(" ".join(rest))
        elif cmd == "look":
            print(f"Art style: {style()}\nWorld: {' '.join((between(WORLD) or '').split()) or '(none)'}\nLearned: " + (" / ".join(learned()) or "(none)")
                  + f"\n— {len(look())} characters are attached to every asset")
        elif cmd == "approve":
            for name in rest:
                approve(name)
        elif cmd == "mesh":
            mesh(rest)
        elif cmd == "finish":
            for name in rest:
                finish(name, size)
        else:
            status()
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
