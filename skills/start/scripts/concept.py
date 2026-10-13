#!/usr/bin/env python3
"""Concept pictures — pictures drawn to agree with the user on how the game will look. Not assets that go into the game (the asset skill does those).

  python3 concept.py new <name> [--size 1024x1536] [--ref <picture>] "<what to draw — in English>"
  python3 concept.py list          the pictures there are and the text that drew them

A picture goes to docs/concept/<name>.png, the text that drew it to <name>.json beside it. **An existing name is never overwritten** — a redraw gets a new name too (so it can be compared with the one before).
--size is the screen's orientation: portrait 1024x1536 (default) · landscape 1536x1024 · square 1024x1024.
--ref is a picture the user liked (a path, or the name of an existing concept) — it is shown to the model as it draws, so what was liked stays and only what was asked changes.

The model and quality come from asset.image in kit.config.json. The key is kept outside the repository — the environment variable OPENAI_API_KEY, or else
the line of that name in asset.env_file (default ~/.config/gamedev-kit/asset.env). Every picture costs money — the skill tells the user how many it will draw first.
"""
import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
import uuid

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "concept")
IMAGE = {"model": "gpt-image-2.5-flare", "quality": "medium"}  # what asset.image says wins
ENV_FILE = "~/.config/gamedev-kit/asset.env"
SIZE = "1024x1536"
OPENAI = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")  # the tests change this
KEEP = ("The attached image is the picture to keep: the same composition, palette, shapes and mood. "
        "Change only what is asked below and leave everything else as it is.")

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


def key(name):
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.expanduser(CFG.get("env_file") or ENV_FILE)
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == name and v:
                return v.strip("\"'")
    sys.exit(f"{name} is not set — put one line `{name}=...` in {path} (the user does this. Keys are not kept in the repository)")


def http(url, token, body, content_type="application/json"):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": content_type}
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
        sys.exit(f"{url} → {e.code}: {str(text)[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"{url} → {e.reason}")


def multipart(fields, path):
    mark = uuid.uuid4().hex
    parts = [f'--{mark}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{mark}\r\nContent-Disposition: form-data; name="image[]"; filename="{os.path.basename(path)}"\r\n'
                 f"Content-Type: {mimetypes.guess_type(path)[0] or 'image/png'}\r\n\r\n".encode() + open(path, "rb").read() + b"\r\n")
    return b"".join(parts) + f"--{mark}--\r\n".encode(), f"multipart/form-data; boundary={mark}"


def picture(name):
    return os.path.join(ROOT, DIR, f"{name}.png")


def find_ref(ref):
    """A path (from the current folder · the game root) or the name of an existing concept."""
    for path in (ref, os.path.join(ROOT, ref), picture(ref)):
        if os.path.isfile(path):
            return os.path.abspath(path)
    sys.exit(f"reference not found: {ref} — give a path (from the game root) or the name of an existing concept (`list`)")


def cmd_new(name, size, ref, prompt):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        sys.exit(f"a name is lowercase letters · digits · underscores · hyphens: {name!r}")
    if not re.fullmatch(r"\d+x\d+", size):
        sys.exit(f"--size looks like 1024x1536: {size!r}")
    out = picture(name)
    if os.path.exists(out):
        sys.exit(f"{os.path.relpath(out, ROOT)} already exists — not overwriting. A redraw gets a new name too (like {name}_2)")
    prompt = " ".join(prompt.split())
    image = dict(IMAGE, **{k: v for k, v in (CFG.get("image") or {}).items() if k in IMAGE})
    fields = dict(image, size=size, output_format="png")
    if ref:
        src = find_ref(ref)
        body, ctype = multipart(dict(fields, prompt=f"{KEEP} {prompt}"), src)
        raw = http(f"{OPENAI}/images/edits", key("OPENAI_API_KEY"), body, ctype)
    else:
        raw = http(f"{OPENAI}/images/generations", key("OPENAI_API_KEY"), json.dumps(dict(fields, prompt=prompt)).encode())
    data = base64.b64decode(json.loads(raw)["data"][0]["b64_json"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "wb").write(data)
    with open(out[:-4] + ".json", "w", encoding="utf-8") as f:
        json.dump(dict(image, name=name, size=size, ref=os.path.relpath(src, ROOT) if ref else None, prompt=prompt), f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{os.path.relpath(out, ROOT)} — the user opens it (it is not read in this session)")


def cmd_list():
    d = os.path.join(ROOT, DIR)
    names = sorted(n for n in os.listdir(d) if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))) if os.path.isdir(d) else []
    if not names:
        return print(f"no pictures in {DIR}/")
    for n in names:
        note = os.path.join(d, os.path.splitext(n)[0] + ".json")
        if not os.path.exists(note):
            print(f"{DIR}/{n} — a picture the user put in")
            continue
        rec = json.load(open(note, encoding="utf-8"))
        print(f"{DIR}/{n} — {rec.get('size', '')}" + (f" · redrawn from {rec['ref']}" if rec.get("ref") else "") + f" · {rec.get('prompt', '')}")


def main():
    global ROOT, CFG
    args = sys.argv[1:]
    root = None
    if "--root" in args:  # for the tests
        i = args.index("--root")
        root = args[i + 1]
        del args[i:i + 2]
    opts = {"--size": SIZE, "--ref": ""}
    for flag in opts:
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    ROOT = os.path.abspath(root) if root else find_root(os.getcwd())
    CFG = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get("asset") or {}
    if args == ["list"]:
        cmd_list()
    elif len(args) == 3 and args[0] == "new":
        cmd_new(args[1], opts["--size"], opts["--ref"], args[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
