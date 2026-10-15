#!/usr/bin/env python3
"""Deploy — builds the game and gets the build to the platform it is for.

  python3 deploy.py check                  OK to upload?: the platform's tool and login · target · uncommitted changes · pre-checks
  python3 deploy.py build [channel]        run the build command from the config and check the output folder
  python3 deploy.py push [channel] [--dry-run]  upload. With --dry-run, only shows what would go where
  python3 deploy.py status                 what the platform holds now
  python3 deploy.py version                the version attached on upload
  python3 deploy.py notes                  what the user does once on this platform (log in, create the page)

With no channel, every channel in the config. check and push stop on uncommitted changes (--dirty skips this).

What is built how and goes where is in "deploy" in the project root's kit.config.json:

  "deploy": {
    "platform": "<a folder of platforms/>",
    "target": "<the game on that platform — its form is the platform's to say>",
    "version": { "file": "<file holding the version>", "regex": "<group 1 is the version>" },
    "pre": ["pre-check command", ...],
    "channels": { "<channel>": { "build": "build command", "dir": "build/out", "must": "a file that must be there" } }
  }

Everything that differs per platform is in platforms/<platform>/platform.json (not copied into the game) — this script knows no platform's name:

  label       the platform's name as shown
  target      form (what a target looks like) · regex (named groups become placeholders) · empty (what to say when it is not filled in)
  tool        name · env (environment variable pointing at the executable) · path (names to look for on PATH) · missing (what to tell the user) ·
              login: env (set = logged in) · files (exists = logged in) · missing
  where       how target and channel read together
  upload      the upload command. Without one the script uploads nothing: push prints `manual`, what the user does with the build
  preview     arguments added to the upload command for --dry-run. Without them --dry-run runs nothing
  status      the command that shows what the platform holds
  after       what to look at once it is up
  legacy_key  a key of "deploy" that older configs used for this platform's target (read when "platform" is absent)

Placeholders: {tool} {dir} {file} {target} {channel} {version}, and the named groups of target.regex.
platforms/<platform>/NOTES.md is what the user does once; it is printed by `notes` and when check fails on the platform's side.
"""
import json
import os
import re
import shutil
import subprocess
import sys

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
PLATFORMS = os.environ.get("GAMEDEV_KIT_PLATFORMS") or os.path.join(KIT, "platforms")  # the tests change this
CONFIG_NAME = "kit.config.json"
SECTION = "deploy"
SPEC = "platform.json"
DEFAULTS = {
    "platform": "",                      # a folder of platforms/
    "target": "",                        # the game on that platform
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


def platforms():
    return sorted(d for d in (os.listdir(PLATFORMS) if os.path.isdir(PLATFORMS) else []) if os.path.exists(os.path.join(PLATFORMS, d, SPEC)))


def spec(name):
    return json.load(open(os.path.join(PLATFORMS, name, SPEC), encoding="utf-8"))


def setup(root=None):
    global ROOT, CFG
    ROOT = os.path.abspath(root) if root else find_root(os.getcwd())
    section = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get(SECTION, {})
    CFG = dict(DEFAULTS)
    CFG.update(section)
    if "platform" not in section:  # a config written before platforms: the platform's own key held the target
        for name in platforms():
            key = spec(name).get("legacy_key")
            if key and key in section:
                CFG["platform"], CFG["target"] = name, section.get("target") or section[key]
                break


def platform():
    """The platform file of the configured platform. Stops when none is named or the name is no folder of platforms/."""
    name = CFG["platform"]
    if not name:
        sys.exit(f"{SECTION}.platform in {CONFIG_NAME} is empty — where the build goes: " + " · ".join(platforms()))
    if name not in platforms():
        sys.exit(f"unknown platform {name} — " + " · ".join(platforms()))
    return dict(spec(name), label=spec(name).get("label") or name)


def notes():
    path = os.path.join(PLATFORMS, CFG["platform"], "NOTES.md")
    return open(path, encoding="utf-8").read().strip() if os.path.exists(path) else ""


def fill(text, values):
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def tool(p):
    """The executable the platform's commands call, or "" when it is not on this machine (or the platform needs none)."""
    t = p.get("tool") or {}
    named = os.environ.get(t.get("env") or "", "")
    if named:
        return shutil.which(named) or ""
    return next((found for found in map(shutil.which, t.get("path", [])) if found), "")


def logged_in(p):
    login = (p.get("tool") or {}).get("login")
    return (not login or any(os.environ.get(v) for v in login.get("env", []))
            or any(os.path.exists(os.path.expanduser(f)) for f in login.get("files", [])))


def target(p):
    """The match of the target against the platform's form, or None."""
    return re.fullmatch(p.get("target", {}).get("regex") or r".+", CFG["target"] or "")


def values(p, name, ch, folder):
    """What the placeholders stand for. `folder` is the build folder as the text should show it."""
    return dict(target(p).groupdict(), tool=tool(p), dir=folder, file=os.path.join(folder, ch["must"]) if ch.get("must") else folder,
                target=CFG["target"], channel=name, version=version())


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


def problems(p, dirty):
    """The reasons not to upload: (on the platform's side, on the game's side). Both empty means OK to upload."""
    theirs, ours = [], []
    t = p.get("tool")
    if t and p.get("upload"):
        if not tool(p):
            theirs.append(f"{t.get('name', 'the upload tool')} not found — {t.get('missing', '')}")
        elif not logged_in(p):
            theirs.append(f"{t.get('name', 'the upload tool')} is not logged in — {t['login'].get('missing', '')}")
    form = p.get("target", {})
    if not CFG["target"]:
        theirs.append(f"{SECTION}.target is empty — {form.get('empty', '')}")
    elif not target(p):
        theirs.append(f"{SECTION}.target is not in the form `{form.get('form', '')}`: {CFG['target']!r}")
    if not CFG["channels"]:
        ours.append(f"{SECTION}.channels is empty")
    changed = git("status", "--porcelain")
    if changed and not dirty:
        ours.append("uncommitted changes — the uploaded build could not be traced to a commit\n" + changed)
    for cmd in CFG["pre"]:
        r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
        print(f"  {'pass' if r.returncode == 0 else 'fail'}  {cmd}")
        if r.returncode != 0:
            ours.append(f"pre-check failed: {cmd}\n{(r.stdout + r.stderr).strip()[-2000:]}")
    return theirs, ours


def check(dirty):
    p = platform()
    theirs, ours = problems(p, dirty)
    if theirs or ours:
        once = f"\n\n{p['label']} — what the user does once:\n{notes()}" if theirs and notes() else ""
        sys.exit("Cannot upload:\n- " + "\n- ".join(theirs + ours) + once)
    print(f"OK to upload — {p['label']} · {CFG['target']} · version {version()} · channels " + " · ".join(CFG["channels"])
          + ("" if p.get("upload") else " · uploaded by the user"))
    return p


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
    """Upload — or, for a platform with no upload command, say what the user does with the build. Nothing is uploaded with --dry-run."""
    p = check(dirty) if not dry else platform()
    if dry and not target(p):
        sys.exit(f"{SECTION}.target is not filled in — deploy.py check")
    upload, after = p.get("upload"), []
    for name, ch in channels(name):
        d, n, size = built(name, ch)
        shown = values(p, name, ch, ch["dir"])
        where = fill(p.get("where") or "{target}", shown)
        print(f"{name}: {ch['dir']} ({n} file(s) · {size / 1e6:.1f} MB) → {p['label']} {where} · version {shown['version']}"
              + (" · not uploaded" if dry or not upload else ""), flush=True)
        if not upload:
            after.append(fill(p.get("manual") or "The user uploads {file} by hand.", shown))
            continue
        if dry and ("preview" not in p or not tool(p)):  # without the tool the preview is the line above; check says what is missing
            continue
        cmd = [fill(a, values(p, name, ch, d)) for a in upload + (p["preview"] if dry else [])]
        if subprocess.run(cmd, cwd=ROOT).returncode != 0:
            sys.exit(f"{name}: upload failed ({' '.join(cmd[:2])})")
        if not dry and p.get("after"):
            after.append(fill(p["after"], shown))
    for line in dict.fromkeys(after):
        print(line)


def status():
    p = platform()
    if not p.get("status"):
        print(f"{p['label']} has no status command — what it holds is seen on the platform itself")
        return 0
    if not target(p) or not tool(p):
        sys.exit("Cannot ask — deploy.py check")
    shown = dict(target(p).groupdict(), tool=tool(p), target=CFG["target"])
    return subprocess.run([fill(a, shown) for a in p["status"]], cwd=ROOT).returncode


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
    if cmd not in ("check", "build", "push", "status", "version", "notes") or flags - {"--dry-run", "--dirty"}:
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
        sys.exit(status())
    elif cmd == "notes":
        p = platform()
        print(f"{p['label']} — target `{p.get('target', {}).get('form', '')}` · "
              + ("uploaded by this script" if p.get("upload") else "uploaded by the user") + "\n\n" + notes())
    else:
        print(version())


if __name__ == "__main__":
    main()
