#!/usr/bin/env python3
"""Sound — makes sound effects and music from a one-line description (ElevenLabs).

  python3 sound.py sfx <name> [--seconds <seconds>] [--loop] [--influence <0~1>] "<what sound — in English>"
  python3 sound.py music <name> --seconds <seconds> "<what music — in English>"
  python3 sound.py again <name>...        make it again exactly as recorded (same description, different result)
  python3 sound.py status                 the sounds made

Sound effects are 0.5~30 s (omitted, the length is decided for you), music 3~600 s. --loop is a sound whose end runs into its start (wind · engine · background).
The file goes to <sound.dir>/<name>.<mp3|wav>, the record to <work>/<name>/sound.json. Making the same name again overwrites the file.

The sound style lives in one place — between `<!-- sound-style -->` and `<!-- /sound-style -->` in asset.style_file (default docs/DESIGN.md).
That paragraph is not attached to music — a paragraph between `<!-- music-style -->` and `<!-- /music-style -->`, if present, is.
If present, it follows every description as is. Config is "sound" inside "asset" in kit.config.json at the project root.

Keys stay outside the repository — environment variable ELEVENLABS_API_KEY, or else the line of the same name
in asset.env_file (default ~/.config/gamedev-kit/asset.env).
"""
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request
import wave

CONFIG_NAME = "kit.config.json"
SECTION = "asset"
DEFAULTS = {
    "work": "assets/_gen",
    "style_file": "docs/DESIGN.md",
    "env_file": "~/.config/gamedev-kit/asset.env",
    "sound": {
        "dir": "",                      # folder finished sounds go to (relative to the root)
        "format": "mp3_44100_128",      # ElevenLabs' output_format. pcm_* is wrapped as wav
        "influence": 0.3,               # how literally the description is followed (0~1)
        "music_model": "music_v1",
    },
}
API = os.environ.get("ELEVENLABS_API_BASE", "https://api.elevenlabs.io/v1")  # the tests change this
KEY = "ELEVENLABS_API_KEY"
OPEN, CLOSE = "<!-- sound-style -->", "<!-- /sound-style -->"
MUSIC = ("<!-- music-style -->", "<!-- /music-style -->")
LIMITS = {"sfx": (0.5, 30), "music": (3, 600)}
LONGEST = 450  # length limit of a sound effect description — measured after the sound style paragraph is attached

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
    CFG = {k: have.get(k, v) for k, v in DEFAULTS.items()}
    CFG["sound"] = dict(DEFAULTS["sound"], **have.get("sound", {}))
    if not CFG["sound"]["dir"]:
        sys.exit(f"{SECTION}.sound.dir in {CONFIG_NAME} is empty — set the folder sounds go to (the asset skill's Config section)")


def key():
    if os.environ.get(KEY):
        return os.environ[KEY]
    path = os.path.expanduser(CFG["env_file"])
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == KEY and v:
                return v.strip("\"'")
    sys.exit(f"{KEY} is missing — add a `{KEY}=...` line to {path} (the asset skill's 'First time only')")


def post(path, body):
    req = urllib.request.Request(f"{API}/{path}?output_format={CFG['sound']['format']}", data=json.dumps(body).encode(),
                                 headers={"xi-api-key": key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(text)["detail"]
            text = detail.get("message", text) if isinstance(detail, dict) else json.dumps(detail, ensure_ascii=False)
        except (ValueError, KeyError, TypeError):
            pass
        raise RuntimeError(f"ElevenLabs {path} → {e.code}: {str(text)[:500]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"ElevenLabs {path} → {e.reason}")


def folder(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
        sys.exit(f"names are lowercase letters · digits · underscores: {name!r}")
    return os.path.join(ROOT, CFG["work"], name)


def style(kind="sfx"):
    """The style paragraph attached to that kind of sound. Music reads only its own paragraph (music-style) — the sound effect style ("no music" and the like) ruins a music description."""
    path = os.path.join(ROOT, CFG["style_file"])
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    start, end = MUSIC if kind == "music" else (OPEN, CLOSE)
    if start not in text or end not in text:
        return ""
    return " ".join(text.split(start, 1)[1].split(end, 1)[0].split())


def write(name, data):
    """Place the downloaded sound in the game folder. pcm gets a wav header (16-bit · mono)."""
    fmt = CFG["sound"]["format"]
    out = os.path.join(ROOT, CFG["sound"]["dir"], f"{name}.{'wav' if fmt.startswith('pcm_') else fmt.split('_')[0]}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if fmt.startswith("pcm_"):
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(fmt.split("_")[1]))
            w.writeframes(data)
    else:
        open(out, "wb").write(data)
    return out


def make(rec):
    name, kind = rec["name"], rec["kind"]
    lo, hi = LIMITS[kind]
    if rec.get("seconds") is not None and not lo <= rec["seconds"] <= hi:
        sys.exit(f"{name}: {'a sound effect' if kind == 'sfx' else 'music'} is {lo}~{hi} s")
    prompt = rec["subject"] + (f". {style(kind)}" if style(kind) else "")
    if kind == "sfx" and len(prompt) > LONGEST:
        sys.exit(f"{name}: the description is {len(prompt)} characters — with the sound style paragraph it must fit in {LONGEST} (the paragraph is {len(style())})")
    if kind == "sfx":
        body = {"text": prompt, "prompt_influence": rec["influence"], "loop": rec["loop"]}
        if rec.get("seconds") is not None:
            body["duration_seconds"] = rec["seconds"]
        data = post("sound-generation", body)
    else:
        data = post("music", {"prompt": prompt, "music_length_ms": int(rec["seconds"] * 1000),
                              "model_id": CFG["sound"]["music_model"], "force_instrumental": True})
    if not data:
        raise RuntimeError(f"{name}: an empty sound came back")
    out = write(name, data)
    rec.update(prompt=prompt, out=os.path.relpath(out, ROOT), format=CFG["sound"]["format"],
               made=str(datetime.date.today()), takes=rec.get("takes", 0) + 1)
    path = os.path.join(folder(name), "sound.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{name}: {rec['out']} — {len(data) / 1e3:.0f} KB" + (" · looping sound" if rec.get("loop") else "")
          + (f" · take {rec['takes']}" if rec["takes"] > 1 else ""))


def records():
    work = os.path.join(ROOT, CFG["work"])
    names = sorted(os.listdir(work)) if os.path.isdir(work) else []
    return [json.load(open(os.path.join(work, n, "sound.json"), encoding="utf-8"))
            for n in names if os.path.exists(os.path.join(work, n, "sound.json"))]


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--seconds", "--influence"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    loop = "--loop" in args
    args = [a for a in args if a != "--loop"]
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd not in ("sfx", "music", "again", "status") or (cmd in ("sfx", "music") and len(rest) != 2) \
            or (cmd == "again" and not rest) or (cmd == "music" and "--seconds" not in opts):
        sys.exit(__doc__)
    setup(opts.get("--root"))
    try:
        seconds = float(opts["--seconds"]) if "--seconds" in opts else None
        influence = float(opts["--influence"]) if "--influence" in opts else CFG["sound"]["influence"]
        if not 0 <= influence <= 1:
            raise ValueError
    except ValueError:
        sys.exit("--seconds is seconds, --influence is 0~1")
    try:
        if cmd in ("sfx", "music"):
            name, subject = rest[0], rest[1].strip().rstrip(".")
            folder(name)
            old = next((r for r in records() if r["name"] == name), {})
            rec = {"name": name, "kind": cmd, "subject": subject, "seconds": seconds, "takes": old.get("takes", 0)}
            if cmd == "sfx":
                rec.update(loop=loop, influence=influence)
            make(rec)
        elif cmd == "again":
            have = {r["name"]: r for r in records()}
            for name in rest:
                if name not in have:
                    sys.exit(f"{name}: no record — sound.py sfx {name} \"<what sound>\"")
                make(have[name])
        else:
            if not records():
                print("no sounds — sound.py sfx <name> \"<what sound>\"")
            for r in records():
                length = "auto" if r.get("seconds") is None else f"{r['seconds']} s"
                print(f"{r['name']:<24} {'music' if r['kind'] == 'music' else 'loop' if r.get('loop') else 'sfx':<6} "
                      f"{length:<8} {r['out']} · {r['subject'][:50]}")
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
