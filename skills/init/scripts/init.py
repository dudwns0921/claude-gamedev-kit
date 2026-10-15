#!/usr/bin/env python3
"""Install the files gamedev-kit uses into a game repository. Run it at the game repository's root.

  python3 init.py              list the engines that can be installed
  python3 init.py --detect     which engine's project this folder already is (or the engines to choose from: where each one's games are played, what it suits)
  python3 init.py <engine> --editor     the editor executable on this machine and the modules a build needs — if missing, says what to install and exits 1
  python3 init.py <engine> --create     create the engine project in this folder if there is none (.git · docs/ may already be there)
  python3 init.py <engine>       install the config · GDD template · engine templates. Also adds the engine's .gitignore lines
  python3 init.py <engine> --import     have the engine read the installed files once (compile · import). Exits 1 if there are error lines
  python3 init.py <engine> --gitignore  add only the engine's .gitignore lines (lines already there are not written again)
  python3 init.py <engine> --files   in an already installed project, also reinstall the engine templates (the value file and what else the engine brings) that are missing
  python3 init.py <engine> --rules   bring the kit rules block in CLAUDE.md to the current version (appended at the end if absent). Nothing outside the block is touched
  python3 init.py --rules-check    called by the hook when a session starts: if the block is an older version, replaces it with the current one and prints one line. If the block is absent or was edited by hand, only reports it. Silent if they match

Files that already exist are not touched — the result is the same however many times it runs.
Run again in an already installed project (kit.config.json exists), it skips the engine templates: a project that moved the value file
or deleted a template on purpose does not get the same file again (Godot will not start with two of the same `class_name`). Instead it reports the config sections the kit has gained since.

In CLAUDE.md, the kit's part is only what lies between `<!-- gamedev-kit start … -->` and `<!-- gamedev-kit end -->` (common rules + engine rules).
A block written by an older kit carries the Korean markers (`gamedev-kit 시작` / `gamedev-kit 끝`): it is found too, and is rewritten with the new markers when it is brought up to date.
When the kit bumps its version, --rules replaces just that span — the game's rules are outside the block and are not touched.
If the inside of the block was edited by hand, it stops instead of overwriting (move the edits outside, or --force).
The block ends with two import lines (`@<rules home>/rules.md` · `@<rules home>/rules-<engine>.md`) — the user's own rules from earlier games, which Claude Code
reads in with the game's CLAUDE.md. They live in the rules home (~/.config/gamedev-kit/rules/, or GAMEDEV_KIT_RULES), outside the game; the two files are made when missing
(and, the first time, the rules kept in the old voice home are copied over — the feedback skill owns these files).

How to recognise an engine project · find the editor · create one is in engines/<engine>/project.json (not copied into the game):
  marker    if this file exists, it is that engine's project
  editor    env (environment variable pointing at the executable) · path (names to look for on PATH) · <sys.platform>.glob (where it installs — if several, the newest by the version regex) ·
            <sys.platform>.modules (from the executable's folder to the modules folder) · missing (what to tell the user when it is not there)
  modules   for each module a build needs: name · dir · must (what has to be inside) · install (what to say when missing. {version} is filled in)
  create · import   files (files written if absent) · run (commands — {editor} · {root} · {log}) · error (regex for error lines to look for in the output)
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
ENGINES = os.environ.get("GAMEDEV_KIT_ENGINES") or os.path.join(KIT, "engines")  # the tests change this
LOCK_LINE = "~$*.xlsx"
START, END = "<!-- gamedev-kit start", "<!-- gamedev-kit end -->"
OLD_START, OLD_END = "<!-- gamedev-kit 시작", "<!-- gamedev-kit 끝 -->"  # written by older kits — read, never written
# The fingerprint in the start marker is taken over the text between the marker lines only, so it does not depend on which markers a block carries.
BLOCK_RE = re.compile("(?P<start>" + re.escape(START) + "|" + re.escape(OLD_START) + r") · ([0-9a-f]+)[^\n]*-->\n(.*?)\n"
                      "(?P<end>" + re.escape(END) + "|" + re.escape(OLD_END) + ")", re.S)
HOME = os.path.expanduser(os.environ.get("GAMEDEV_KIT_RULES") or "~/.config/gamedev-kit/rules")
OLD_HOME = os.path.expanduser(os.environ.get("GAMEDEV_KIT_VOICE") or "~/.config/gamedev-kit/voice")  # where the rules lived before
# The last part of the block. Import lines are plain text on lines of their own — Claude Code does not expand one inside a code span or a fenced block.
MINE = """## The user's own rules

These are the user's own rules from earlier games, kept outside this repository — they hold in this game too.

@{home}/rules.md
@{home}/rules-{engine}.md"""
# The head of a rule file made here — the same words feedback.py writes (the feedback skill owns these files; the tests hold the two together).
RULES_HEAD = ("# The user's rules{engine}\n\n"
              "What this user learned in earlier games that holds {scope} — one rule per line, written by `feedback.py add`. "
              "Claude Code loads this file into every game made with gamedev-kit.\n\n")
OWN = """
## This game's rules

Structure, pitfalls and verification methods specific to this game go here. Where they disagree with the block above, what is written here wins.
"""


def engines():
    return sorted(d for d in os.listdir(ENGINES) if os.path.exists(os.path.join(ENGINES, d, "kit.config.json")))


def project(engine):
    """How to recognise that engine's project · find the editor · create one. Unlike the game's config (kit.config.json), it is not copied into the game."""
    path = os.path.join(ENGINES, engine, "project.json")
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}


def detect(root):
    """The engines this folder is already a project of — usually one or none."""
    return [e for e in engines() if project(e).get("marker") and os.path.exists(os.path.join(root, project(e)["marker"]))]


def find_editor(engine):
    """(executable, version, every installed version). Environment variable → PATH → install location, in that order. (None, "", []) if not found."""
    ed = project(engine).get("editor", {})

    def version(path):
        m = re.search(ed["version"], path.replace(os.sep, "/")) if ed.get("version") else None
        return m.group(1) if m else ""

    named = os.environ.get(ed.get("env") or "", "")
    if named:
        if not os.path.exists(named):
            sys.exit(f"the file the environment variable {ed['env']} points to does not exist: {named}")
        return named, version(named), []
    for name in ed.get("path", []):
        if shutil.which(name):
            return shutil.which(name), "", []
    found = [p for pattern in ed.get(sys.platform, {}).get("glob", []) for p in glob.glob(os.path.expanduser(pattern))]
    if not found:
        return None, "", []
    found.sort(key=lambda p: [int(n) for n in re.findall(r"\d+", version(p))])  # versions compare number by number (10 is newer than 9)
    return found[-1], version(found[-1]), [version(p) for p in found if version(p)]


def need_editor(engine):
    exe, version, _all = find_editor(engine)
    if not exe:
        ed = project(engine).get("editor", {})
        sys.exit(f"{ed.get('name', engine)} editor not found — the user installs it:\n" + "\n".join(f"  {line}" for line in ed.get("missing", [])))
    return exe, version


def cmd_editor(engine):
    spec = project(engine)
    ed = spec.get("editor", {})
    if not ed:
        return print(f"{engine}: no editor to find — nothing to install")
    exe, version = need_editor(engine)
    versions = find_editor(engine)[2]
    print(f"{ed.get('name', engine)} {version} — {exe}".replace("  ", " ")
          + (f"\n  installed versions {' · '.join(versions)} — picked the newest (for another, set the environment variable {ed['env']})" if len(versions) > 1 else ""))
    base, have, lack = ed.get(sys.platform, {}).get("modules"), [], []
    for mod in spec.get("modules", []):
        if base is None:
            print(f"  unknown  {mod['name']} — where it installs on this machine is not known. Check in the editor")
            continue
        folder = os.path.normpath(os.path.join(os.path.dirname(exe), base, mod["dir"]))
        gone = [m for m in mod.get("must", []) if not os.path.exists(os.path.join(folder, m))]
        if os.path.isdir(folder) and not gone:
            have.append(mod["name"])
            print(f"  found    {mod['name']}" + (f" ({' · '.join(mod['must'])})" if mod.get("must") else ""))
        else:
            lack.append(mod["name"])
            print(f"  missing  {mod['name']} — " + (f"{' · '.join(gone)} not found in it" if os.path.isdir(folder) else f"{folder} does not exist"))
            print("\n".join(f"           {line.replace('{version}', version)}" for line in mod.get("install", [])))
    print("\nWrite under `## This game's rules` in CLAUDE.md (that heading already exists — do not create a new one): "
          f"editor executable `{exe}`" + (f" · installed modules {' · '.join(have)}" if have else ""))
    if lack:
        sys.exit(f"\nmodules the build needs are missing: {' · '.join(lack)} — installing them is the user's call (the download is large). Run this again after installing")


def run_step(engine, step, root):
    """Run create · import from project.json: write the missing files, run the editor commands, look for error lines in the output."""
    spec = project(engine).get(step)
    if not spec:
        return print(f"{engine}: nothing to do for {step}")
    for rel, text in spec.get("files", {}).items():
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w", encoding="utf-8").write(text)
            print(f"  new      {rel}")
    if not spec.get("run"):
        return None
    exe = need_editor(engine)[0]
    for argv in spec["run"]:
        log = os.path.join(tempfile.mkdtemp(prefix="kit-init-"), "editor.log")
        cmd = [a.replace("{editor}", exe).replace("{root}", root).replace("{log}", log) for a in argv]
        print("  run      " + " ".join(cmd) + "  (may take a few minutes)", flush=True)
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        out = p.stdout + p.stderr + (open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else "")
        shutil.rmtree(os.path.dirname(log), True)
        bad = [line for line in out.split("\n") if spec.get("error") and re.search(spec["error"], line)]
        if p.returncode or bad:
            tail = bad[:20] or out.strip().split("\n")[-20:]
            sys.exit(f"{step} failed (exit code {p.returncode}" + (f" · error lines {len(bad)}" if bad else "") + ") — if the editor has this project open, close it:\n"
                     + "\n".join(tail))


def cmd_create(engine, root):
    marker = project(engine).get("marker")
    if not marker:
        sys.exit(f"{engine}: engines/{engine}/project.json does not say how to create one")
    here = detect(root)
    if engine in here:
        return print(f"already a {engine} project ({marker}) — not creating one")
    if here:
        sys.exit(f"this folder is already a {' · '.join(here)} project — not creating a {engine} project on top of it")
    run_step(engine, "create", root)
    if not os.path.exists(os.path.join(root, marker)):
        sys.exit(f"it was reported created but {marker} is missing — check the editor's log")
    print(f"created the {engine} project ({marker}). Next, install the kit files: `init.py {engine}` → `init.py {engine} --import`")


def add_ignore(engine, root, done):
    """Append only those of the engine's .gitignore lines that are not there yet."""
    src = os.path.join(ENGINES, engine, "gitignore")
    if not os.path.exists(src):
        return
    path = os.path.join(root, ".gitignore")
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    have = {line.strip() for line in text.split("\n")}
    new = [line.strip() for line in open(src, encoding="utf-8") if line.strip() and line.strip() not in have]
    if new:
        with open(path, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n") + f"\n# what {engine} generates · what is kept out of the repository\n" + "\n".join(new) + "\n")
    done.append(f"  {'added' if new else 'kept '}    .gitignore ({engine} — "
                + (f"{len(new)} line{'' if len(new) == 1 else 's'}: {' · '.join(new)}" if new else "every line is already there") + ")")


def rules_home():
    """The rules home as the block writes it: with `~` when it is under the home directory, so the block comes out the same on every machine."""
    home = os.path.expanduser("~")
    path = "~" + HOME[len(home):] if HOME.startswith(home + os.sep) else HOME
    return path.replace(os.sep, "/")


def rules(engine):
    """(head, rules body) — the body is the sections of the common template, that engine's rules, and the lines that import the user's own rules."""
    head, body = open(os.path.join(KIT, "templates", "CLAUDE.md"), encoding="utf-8").read().split("\n## ", 1)
    extra = os.path.join(ENGINES, engine, "CLAUDE.md")  # rules that hold only for that engine (running · verifying · pitfalls)
    more = open(extra, encoding="utf-8").read().strip() if os.path.exists(extra) else ""
    mine = MINE.format(home=rules_home(), engine=engine)
    return head.strip() + "\n", ("## " + body.strip() + ("\n\n" + more if more else "") + "\n\n" + mine).strip()


def own_rules(engine, done=None):
    """Make the two rule files the block imports when they are not there — an import must not point at a missing file.
    The first time, the rules the old voice home kept are copied over (that folder is left as it was)."""
    names = os.listdir(HOME) if os.path.isdir(HOME) else []
    if not any(n == "rules.md" or re.fullmatch(r"rules-.+\.md", n) for n in names) and os.path.isdir(OLD_HOME):
        for n in sorted(os.listdir(OLD_HOME)):
            if n in ("rules.md", "rules.last", "private-words.txt") or re.fullmatch(r"rules-.+\.md", n):
                os.makedirs(HOME, exist_ok=True)
                text = open(os.path.join(OLD_HOME, n), encoding="utf-8").read().replace("written by `voice.py rule`", "written by `feedback.py add`")
                open(os.path.join(HOME, n), "w", encoding="utf-8").write(text)
                if done is not None:
                    done.append(f"  copied   {os.path.join(HOME, n)} (from {OLD_HOME})")
    for name, scope in (("", "whatever the engine"), (engine, f"in every {engine} game")):
        path = os.path.join(HOME, f"rules-{name}.md" if name else "rules.md")
        if not os.path.exists(path):
            os.makedirs(HOME, exist_ok=True)
            open(path, "w", encoding="utf-8").write(RULES_HEAD.format(engine=f" — {name}" if name else "", scope=scope))
            if done is not None:
                done.append(f"  new      {path}")


def digest(body):
    return hashlib.sha1(body.strip().encode("utf-8")).hexdigest()[:8]


def block(body):
    return (f"{START} · {digest(body)} — kit rules. Do not edit between these markers (`/gamedev-kit:init rules` replaces the whole block). "
            f"This game's own rules go outside the block. -->\n{body.strip()}\n{END}\n")


def rules_state(root, engine):
    """none (no block) · same · stale (the kit bumped its version, or the block carries the old markers) · edited (the inside of the block was edited by hand).
    None if there is no CLAUDE.md."""
    path = os.path.join(root, "CLAUDE.md")
    if not os.path.exists(path):
        return None
    m = BLOCK_RE.search(open(path, encoding="utf-8").read())
    if not m:
        return "none"
    if digest(m.group(3)) != m.group(2):
        return "edited"
    current = m.group(2) == digest(rules(engine)[1]) and (m.group("start"), m.group("end")) == (START, END)
    return "same" if current else "stale"


def sync_rules(root, engine, force):
    own_rules(engine)
    path = os.path.join(root, "CLAUDE.md")
    head, body = rules(engine)
    state = rules_state(root, engine)
    if state is None:
        open(path, "w", encoding="utf-8").write(head + "\n" + block(body) + OWN)
        return print("created CLAUDE.md — fill in `<game name>`")
    text = open(path, encoding="utf-8").read()
    if state == "same":
        return print("the kit rules in CLAUDE.md match the current version")
    if state == "edited" and not force:
        sys.exit("the kit rules block in CLAUDE.md was edited by hand — not overwriting. Move the edits outside the block and run again, or --force if they can be dropped")
    if state == "none":
        titles = [t for t in re.findall(r"^## (.+)$", body, re.M) if re.search(rf"^## {re.escape(t)}\s*$", text, re.M)]
        open(path, "w", encoding="utf-8").write(text.rstrip("\n") + "\n\n" + block(body))
        print("appended the kit rules block at the end of CLAUDE.md — the existing text is untouched")
        if titles:
            print("sections with the same titles remain outside the block (copied from an older version): " + " · ".join(titles)
                  + "\nDelete the overlapping text outside the block and keep outside only what this game rewrote — show the user before deleting")
        return None
    open(path, "w", encoding="utf-8").write(BLOCK_RE.sub(lambda m: block(body).rstrip("\n"), text, count=1))
    print("replaced the kit rules block in CLAUDE.md with the current version — outside the block is untouched")


def check_rules():
    """Called by the hook when a session starts. Silent when there is nothing to say. Exits 0 whatever happens."""
    d = os.getcwd()
    while not os.path.exists(os.path.join(d, "kit.config.json")):
        if os.path.dirname(d) == d:
            return
        d = os.path.dirname(d)
    cfg = json.load(open(os.path.join(d, "kit.config.json"), encoding="utf-8"))
    if cfg.get("engine") not in engines() or cfg.get("init", {}).get("rules") is False:
        return
    own_rules(cfg["engine"])
    state = rules_state(d, cfg["engine"])
    if state == "stale":  # the block is the kit's — an untouched block is aligned without asking
        path = os.path.join(d, "CLAUDE.md")
        text = open(path, encoding="utf-8").read()
        open(path, "w", encoding="utf-8").write(BLOCK_RE.sub(lambda m: block(rules(cfg["engine"])[1]).rstrip("\n"), text, count=1))
        return print("[gamedev-kit] The kit changed its rules, so the kit rules block in CLAUDE.md was replaced with the current version (outside the block is untouched). "
                     "What changed is in `git diff CLAUDE.md` — tell the user in one line at the next stopping point. "
                     "To stop it aligning itself, put `\"init\": {\"rules\": false}` in kit.config.json.")
    say = {"none": "CLAUDE.md has no kit rules block (the kit's new rules do not reach this project)",
           "edited": "The kit rules block in CLAUDE.md has been edited by hand (it cannot be brought to the current version)"}.get(state)
    if say:
        print(f"[gamedev-kit] {say}. Do not stop the work in hand — tell the user in one line at the next stopping point: `/gamedev-kit:init rules` can align it. "
              "To stop this notice, put `\"init\": {\"rules\": false}` in kit.config.json.")


def place(src, dst, root, done):
    rel = os.path.relpath(dst, root)
    if os.path.exists(dst):
        done.append(f"  kept     {rel}")
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(src, dst)
    done.append(f"  new      {rel}")
    return True


def main():
    args = sys.argv[1:]
    root = os.getcwd()
    if "--root" in args:  # for the tests
        i = args.index("--root")
        root = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    if "--rules-check" in args:
        try:
            check_rules()
        except Exception:
            pass
        return
    if "--detect" in args:
        here, config = detect(root), os.path.join(root, "kit.config.json")
        has = json.load(open(config, encoding="utf-8")).get("engine", "") if os.path.exists(config) else ""
        def choice(e):  # where a game made with it is played, and what it suits — the engine's own words (engines/<engine>/project.json)
            c = project(e).get("choose", {})
            return f"  {e} — plays {c['plays_on']} · {c['suits']}" if c.get("plays_on") else f"  {e}"
        print("\n".join(f"{e} — {project(e)['marker']} exists" for e in here)
              or "not an engine project — engines to choose from, by where the game is played:\n" + "\n".join(choice(e) for e in engines()))
        return print(f"the kit is already installed as {has} (kit.config.json)" if has else "the kit is not installed yet (no kit.config.json)")
    again_files, only_rules, force = "--files" in args, "--rules" in args, "--force" in args
    steps = [a for a in args if a in ("--editor", "--create", "--import", "--gitignore")]
    args = [a for a in args if a not in ("--files", "--rules", "--force", *steps)]
    if not args:
        sys.exit("pick an engine: " + " · ".join(engines()))
    engine = args[0]
    if engine not in engines():
        sys.exit(f"unknown engine {engine} — " + " · ".join(engines()))
    src = os.path.join(ENGINES, engine)
    done = []
    if only_rules:
        return sync_rules(root, engine, force)
    if steps:  # the engine project's side — each is called on its own
        if steps[0] == "--editor":
            return cmd_editor(engine)
        if steps[0] == "--create":
            return cmd_create(engine, root)
        if steps[0] == "--import":
            return run_step(engine, "import", root)
        add_ignore(engine, root, done)
        return print("\n".join(done) or f"{engine}: no .gitignore lines to add")

    config = os.path.join(root, "kit.config.json")
    had = os.path.exists(config)
    if had:
        has = json.load(open(config, encoding="utf-8")).get("engine", "")
        if has != engine:
            sys.exit(f"kit.config.json is already installed for {('the ' + has) if has else 'another'} engine — to change it, delete that file first")
    place(os.path.join(src, "kit.config.json"), config, root, done)

    files = os.path.join(src, "files")
    skipped = []
    for dirpath, _dirs, names in os.walk(files):
        for name in sorted(names):
            path = os.path.join(dirpath, name)
            dst = os.path.join(root, os.path.relpath(path, files))
            if had and not again_files and not os.path.exists(dst):
                skipped.append(os.path.relpath(dst, root))
            else:
                place(path, dst, root, done)
    if skipped:
        done.append(f"  skipped  engine templates: {len(skipped)} — the project is already installed. Leave them if they were moved or deleted; to reinstall, --files: "
                    + " · ".join(skipped))

    place(os.path.join(KIT, "templates", "GDD.md"), os.path.join(root, "docs", "GDD.md"), root, done)
    place(os.path.join(KIT, "templates", "DESIGN.md"), os.path.join(root, "docs", "DESIGN.md"), root, done)
    made_claude = not os.path.exists(os.path.join(root, "CLAUDE.md"))
    if made_claude:
        head, body = rules(engine)
        open(os.path.join(root, "CLAUDE.md"), "w", encoding="utf-8").write(head + "\n" + block(body) + OWN)
    done.append(f"  {'new ' if made_claude else 'kept'}     CLAUDE.md")
    own_rules(engine, done)

    ignore = os.path.join(root, ".gitignore")
    text = open(ignore, encoding="utf-8").read() if os.path.exists(ignore) else ""
    if LOCK_LINE not in text:
        with open(ignore, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n")
                    + "\n# the lock file Excel makes while it has the table open\n" + LOCK_LINE + "\n")
        done.append("  added    .gitignore (Excel lock file)")
    add_ignore(engine, root, done)

    print(f"gamedev-kit — {engine}\n" + "\n".join(done))
    if had:  # config sections the kit has gained since
        want = json.load(open(os.path.join(src, "kit.config.json"), encoding="utf-8"))
        have = json.load(open(config, encoding="utf-8"))
        missing = [k for k in want if k not in have] + [f"{k}.{s}" for k, v in want.items() if isinstance(v, dict) and isinstance(have.get(k), dict)
                                                         for s in v if s not in have[k]]
        if missing:
            print(f"\nsections missing from kit.config.json: {' · '.join(missing)} — to use them, copy them over from this template: {os.path.join(src, 'kit.config.json')}")
    state = rules_state(root, engine)
    if state != "same":
        print("\nkit rules in CLAUDE.md: " + {"none": "no block — `--rules` appends it at the end (the existing text is not touched)",
                                             "stale": "an older version — `--rules` replaces only the block",
                                             "edited": "the block was edited by hand — move the edits outside it, then `--rules`"}[state])
    marker = project(engine).get("marker")
    if marker and not os.path.exists(os.path.join(root, marker)):
        print(f"\nthis folder is not a {engine} project yet (no {marker}) — `init.py {engine} --create` makes one")
    notes = os.path.join(src, "NOTES.md")
    if os.path.exists(notes):
        print("\n" + open(notes, encoding="utf-8").read().strip())


if __name__ == "__main__":
    main()
