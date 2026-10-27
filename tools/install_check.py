#!/usr/bin/env python3
"""Install a commit of this kit the way a user does, and check the install works — called by the pre-push hook.

  python3 tools/install_check.py              HEAD
  python3 tools/install_check.py <commit>     that commit (the hook passes the one being pushed)

What it does, all in a temporary folder: exports the commit (so a file left out of git fails here, not on the user's side), adds it as a marketplace
under a throwaway Claude Code config, and per engine folder makes an empty game, installs the plugin there, runs the installed init for that engine,
then runs every hook that is not async from the installed hooks.json — a hook that exits non-zero or prints a traceback fails the check (hooks fail silently in a session).
Async hooks are left out: they push to outside services. The hooks run with HOME pointed at the temporary folder, so nothing of the user's is read or written.
Without the claude CLI it says so and passes — the tests still run.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd, cwd, env, timeout=120, stdin=""):
    p = subprocess.run(cmd, cwd=cwd, env=env, input=stdin, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    if not shutil.which("claude"):
        return print("install check: no claude CLI on PATH — skipped")
    tmp = tempfile.mkdtemp(prefix="kit-install-")
    failures = []
    try:
        src, cfg, home = (os.path.join(tmp, d) for d in ("src", "config", "home"))
        for d in (src, cfg, home):
            os.makedirs(d)
        archive = subprocess.run(["git", "archive", ref], cwd=KIT, capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", src], input=archive, check=True)
        meta = json.load(open(os.path.join(src, ".claude-plugin", "marketplace.json"), encoding="utf-8"))
        plugin = f"{meta['plugins'][0]['name']}@{meta['name']}"
        env = dict(os.environ, CLAUDE_CONFIG_DIR=cfg)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        code, out = run(["claude", "plugin", "marketplace", "add", src], tmp, env)
        if code:
            return failures.append(f"marketplace add: {out}")
        engines = sorted(d for d in os.listdir(os.path.join(src, "engines")) if os.path.isdir(os.path.join(src, "engines", d)))
        for engine in engines:
            game = os.path.join(tmp, "game-" + engine)
            os.makedirs(game)
            subprocess.run(["git", "init", "-q", game], check=True)
            code, out = run(["claude", "plugin", "install", plugin, "--scope", "project"], game, env)
            if code:
                failures.append(f"{engine}: plugin install: {out}")
                continue
            roots = glob.glob(os.path.join(cfg, "plugins", "cache", meta["name"], meta["plugins"][0]["name"], "*"))
            if len(roots) != 1:
                failures.append(f"{engine}: expected one installed copy, found {len(roots)}")
                continue
            root = roots[0]
            hook_env = dict(os.environ, HOME=home, CLAUDE_PLUGIN_ROOT=root, CLAUDE_PROJECT_DIR=game)
            for k in ("CLAUDE_CONFIG_DIR", "GAMEDEV_KIT_RULES", "GAMEDEV_KIT_VOICE", "GAMEDEV_KIT_ACCOUNTS"):
                hook_env.pop(k, None)
            code, out = run([sys.executable, os.path.join(root, "skills", "init", "scripts", "init.py"), engine], game, hook_env)
            if code or "Traceback" in out:
                failures.append(f"{engine}: init: {out[-800:]}")
                continue
            before = len(failures)
            hooks = json.load(open(os.path.join(root, "hooks", "hooks.json"), encoding="utf-8"))["hooks"]
            for event, groups in hooks.items():
                for group in groups:
                    for hook in group["hooks"]:
                        if hook.get("async") or hook.get("asyncRewake"):
                            continue
                        cmd = hook["command"].replace("${CLAUDE_PLUGIN_ROOT}", root)
                        # what Claude Code hands a hook on stdin, minus a real transcript
                        event_in = json.dumps({"session_id": "install-check", "cwd": game, "hook_event_name": event, "transcript_path": ""})
                        try:
                            code, out = run(["/bin/sh", "-c", cmd], game, hook_env, timeout=hook.get("timeout", 60) + 10, stdin=event_in)
                        except subprocess.TimeoutExpired:
                            code, out = 1, "timed out"
                        if code or "Traceback" in out:
                            failures.append(f"{engine}: {event} hook `{hook['command']}`: {out[-800:]}")
            print(f"install check: {engine} — " + ("installed, init and hooks ran" if len(failures) == before else "hooks failed"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if failures:
            print("install check failed:\n  " + "\n  ".join(failures))
            sys.exit(1)


if __name__ == "__main__":
    main()
