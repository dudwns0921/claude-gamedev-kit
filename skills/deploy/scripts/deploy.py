#!/usr/bin/env python3
"""Deploy — builds the game and uploads it to itch.io with butler.

  python3 deploy.py check                  OK to upload?: butler · target · uncommitted changes · pre-checks
  python3 deploy.py build [channel]        run the build command from the config and check the output folder
  python3 deploy.py push [channel] [--dry-run]  butler push. With --dry-run, only shows what would go up
  python3 deploy.py status                 the channels and builds itch.io holds
  python3 deploy.py version                the version attached on upload

With no channel, every channel in the config. check and push stop on uncommitted changes (--dirty skips this).

What is built how and uploaded where is in "deploy" in the project root's kit.config.json:

  "deploy": {
    "itch": "user/game",
    "version": { "file": "project.godot", "regex": "config/version=\\"([^\\"]+)\\"" },
    "pre": ["pre-check command", ...],
    "channels": { "html5": { "build": "build command", "dir": "build/web", "must": "index.html" } }
  }

The user logs in once: butler login (or the environment variable BUTLER_API_KEY).
"""
import json
import os
import re
import shutil
import subprocess
import sys

CONFIG_NAME = "kit.config.json"
SECTION = "deploy"
DEFAULTS = {
    "itch": "",                          # user/game
    "butler": "butler",
    "version": {"file": "", "regex": ""},  # the file holding the version and the regex that picks it (group 1). Empty means the commit hash
    "pre": [],                           # commands that must pass before uploading (run from the root)
    "channels": {},                      # channel name → { build, dir, must }
}

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
    CFG = dict(DEFAULTS)
    CFG.update(json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get(SECTION, {}))


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def version():
    v = CFG["version"] or {}
    if v.get("file") and v.get("regex"):
        path = os.path.join(ROOT, v["file"])
        m = re.search(v["regex"], open(path, encoding="utf-8").read()) if os.path.exists(path) else None
        if not m:
            sys.exit(f"{SECTION}.version: no version found in {v['file']} — group 1 of the regex must be the version")
        return m.group(1)
    return git("rev-parse", "--short", "HEAD") or sys.exit(
        f"Cannot settle a version — fill in {SECTION}.version or make a commit")


def channels(name):
    all_ = CFG["channels"]
    if not all_:
        sys.exit(f"{SECTION}.channels in {CONFIG_NAME} is empty — give each channel a build · dir (the config section of the deploy skill)")
    if name is None:
        return list(all_.items())
    if name not in all_:
        sys.exit(f"unknown channel {name} — " + " · ".join(all_))
    return [(name, all_[name])]


def problems(dirty):
    """The reasons not to upload. Empty means OK to upload."""
    bad = []
    if not shutil.which(CFG["butler"]):
        bad.append(f"butler not found ({CFG['butler']}) — get it from https://itch.io/docs/butler/ and `butler login`")
    if not re.fullmatch(r"[^/\s:]+/[^/\s:]+", CFG["itch"]):
        bad.append(f"{SECTION}.itch is not in the form `user/game`: {CFG['itch']!r}")
    if not CFG["channels"]:
        bad.append(f"{SECTION}.channels is empty")
    changed = git("status", "--porcelain")
    if changed and not dirty:
        bad.append("uncommitted changes — the uploaded build could not be traced to a commit\n" + changed)
    for cmd in CFG["pre"]:
        p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
        print(f"  {'pass' if p.returncode == 0 else 'fail'}  {cmd}")
        if p.returncode != 0:
            bad.append(f"pre-check failed: {cmd}\n{(p.stdout + p.stderr).strip()[-2000:]}")
    return bad


def check(dirty):
    bad = problems(dirty)
    if bad:
        sys.exit("Cannot upload:\n- " + "\n- ".join(bad))
    print(f"OK to upload — {CFG['itch']} · version {version()} · channels " + " · ".join(CFG["channels"]))


def built(name, ch):
    """Check the build output folder is fit to upload. (folder, file count, bytes)"""
    if not ch.get("dir"):
        sys.exit(f"{SECTION}.channels.{name}.dir is empty")
    d = os.path.join(ROOT, ch["dir"])
    files = [os.path.join(p, n) for p, _dirs, names in os.walk(d) for n in names]
    if not files:
        sys.exit(f"{name}: no build in {ch['dir']} — deploy.py build {name}")
    if ch.get("must") and not os.path.exists(os.path.join(d, ch["must"])):
        sys.exit(f"{name}: {ch['dir']}/{ch['must']} is missing — the build is incomplete")
    return d, len(files), sum(os.path.getsize(f) for f in files)


def build(name):
    for name, ch in channels(name):
        if ch.get("build"):
            os.makedirs(os.path.join(ROOT, ch.get("dir") or "."), exist_ok=True)
            print(f"{name}: {ch['build']}", flush=True)
            if subprocess.run(ch["build"], shell=True, cwd=ROOT).returncode != 0:
                sys.exit(f"{name}: build failed")
        _d, n, size = built(name, ch)
        print(f"{name}: {ch['dir']} — {n} file(s) · {size / 1e6:.1f} MB")


def push(name, dry, dirty):
    if not dry:
        check(dirty)
    ver = version()
    for name, ch in channels(name):
        d, n, size = built(name, ch)
        target = f"{CFG['itch']}:{name}"
        cmd = [CFG["butler"], "push", d, target, "--userversion", ver] + (["--dry-run"] if dry else [])
        print(f"{name}: {ch['dir']} ({n} file(s) · {size / 1e6:.1f} MB) → {target} · version {ver}"
              + (" · not uploaded" if dry else ""), flush=True)
        if subprocess.run(cmd, cwd=ROOT).returncode != 0:
            sys.exit(f"{name}: butler push failed")


def main():
    args = sys.argv[1:]
    root = None
    if "--root" in args:  # for tests
        i = args.index("--root")
        root = args[i + 1]
        del args[i:i + 2]
    flags = {a for a in args if a.startswith("--")}
    args = [a for a in args if not a.startswith("--")]
    cmd = args[0] if args else ""
    if cmd not in ("check", "build", "push", "status", "version") or flags - {"--dry-run", "--dirty"}:
        sys.exit(__doc__)
    setup(root)
    name = args[1] if len(args) > 1 else None
    if cmd == "check":
        check("--dirty" in flags)
    elif cmd == "build":
        build(name)
    elif cmd == "push":
        push(name, "--dry-run" in flags, "--dirty" in flags)
    elif cmd == "status":
        sys.exit(subprocess.run([CFG["butler"], "status", CFG["itch"]], cwd=ROOT).returncode)
    else:
        print(version())


if __name__ == "__main__":
    main()
