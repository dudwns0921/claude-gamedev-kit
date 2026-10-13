#!/usr/bin/env python3
"""Send the lessons piled up in a game (docs/kit-feedback.md) to the kit repository as issues — the road by which what was learned goes back to the kit.

  python3 feedback.py list                 unsent lines, numbered — the text as it will go out (date · cycle number stripped)
  python3 feedback.py preview 1,3          title · body of the issues to go out, and similar issues already open on the kit. Sends nothing (`all` for every line)
  python3 feedback.py send 1,3             open new issues (gh). Without gh, gives a pre-filled "new issue" address
  python3 feedback.py send 2 --to 14       no new issue — comment "seen here too" on issue #14
  python3 feedback.py sent 2 14            write the issue number on a line the user posted by hand from the address
  python3 feedback.py skip 4 "<reason>"    a line decided not to send (it was this game's only)
  python3 feedback.py --notice             called by the hook at session start: one line if unsent lines have piled up

Numbers count the unsent lines ([ ]) only — sending or skipping shifts them, so `list` again. A sent line becomes [>], a skipped one [-].
Before anything goes out it looks for words that seem to be this game's (the repository folder's name · the GDD's title ·
feedback.private in kit.config.json · private-words.txt in the voice folder) and for dates, and stops if there are any.
`--as-is` is added only when the user said to send it as it is.

Where it goes: the repository in the plugin manifest (override with feedback.repo in kit.config.json). The path of gh is feedback.gh.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

CONFIG_NAME = "kit.config.json"
FEEDBACK = os.path.join("docs", "kit-feedback.md")
PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                      ".claude-plugin", "plugin.json")
WEB = "https://github.com"
API = os.environ.get("GAMEDEV_KIT_GITHUB_API") or "https://api.github.com"
VOICE = os.path.expanduser(os.environ.get("GAMEDEV_KIT_VOICE") or "~/.config/gamedev-kit/voice")
OPEN_RE = re.compile(r"^- \[ \] (.*)$")
META_RE = re.compile(r"^\(([^)]*)\)\s*(.*)$")
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
WORD_RE = re.compile(r"[0-9A-Za-z_가-힣]{2,}")
NOTICE = 5  # this many unsent lines and the session start says so
NEAR = 0.25  # this much word overlap and it is shown as a similar issue — the reader decides whether it is the same

ROOT = ""


def find_root(start):
    """Walk up from the current folder to the one holding kit.config.json. The tools live in the plugin; the game lives elsewhere."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def config():
    return json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8"))


def kit():
    """(the repository issues go to `owner/name`, the kit's version)"""
    plugin = json.load(open(PLUGIN, encoding="utf-8"))
    repo = config().get("feedback", {}).get("repo") or plugin["repository"]
    return repo.replace(WEB + "/", "").strip("/"), plugin["version"]


def lines():
    path = os.path.join(ROOT, FEEDBACK)
    return open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else []


def todo():
    """Unsent lines: [(line number in the file, engine, text to go out)]. Of the leading (engine · cycle · date) only the engine is kept."""
    out = []
    for i, line in enumerate(lines()):
        m = OPEN_RE.match(line)
        if not m:
            continue
        meta = META_RE.match(m.group(1))
        engine = meta.group(1).split("·")[0].strip() if meta else config().get("engine", "?")
        out.append((i, engine, (meta.group(2) if meta else m.group(1)).strip()))
    return out


def pick(arg):
    """`1,3` · `all` → [(number, (line number in the file, engine, text))]"""
    items = todo()
    if arg == "all":
        return list(enumerate(items, 1))
    try:
        want = sorted({int(n) for n in arg.split(",")})
    except ValueError:
        sys.exit(f"{arg}: give numbers as `1,3` or `all`")
    if not want or not set(want) <= set(range(1, len(items) + 1)):
        sys.exit(f"no such number — there are {len(items)} unsent lines")
    return [(n, items[n - 1]) for n in want]


def mark(done):
    """Rewrite lines as {line number in the file: (box, tail)} says."""
    out = lines()
    for i, (box, tail) in done.items():
        out[i] = f"- [{box}] {OPEN_RE.match(out[i]).group(1)} — {tail}"
    with open(os.path.join(ROOT, FEEDBACK), "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def private():
    """Words that seem to be this game's — what must not go out to a public repository."""
    words = [os.path.basename(ROOT)] + list(config().get("feedback", {}).get("private", []))
    gdd = os.path.join(ROOT, "docs", "GDD.md")
    if os.path.exists(gdd):
        head = open(gdd, encoding="utf-8").readline().lstrip("# ").split("—")[0].strip()
        if "<" not in head:
            words.append(head)
    mine = os.path.join(VOICE, "private-words.txt")
    if os.path.exists(mine):
        words += [w.strip() for w in open(mine, encoding="utf-8") if w.strip() and not w.startswith("#")]
    return sorted({w.lower() for w in words if len(w.strip()) >= 3})


def leaks(text, block):
    low = text.lower()
    return [f"‘{w}’" for w in block if w in low] + (["a date"] if DATE_RE.search(text) else [])


def title(engine, text):
    head = text.split("→")[0].strip()
    return f"feedback({engine}): " + (head if len(head) <= 80 else head[:79].rstrip() + "…")


def body(engine, text, version):
    return f"{text}\n\n엔진: {engine} · 키트: {version}"


def open_issues(repo):
    """Feedback issues open on the kit. None when they cannot be read — that does not block sending."""
    out = []
    try:
        for page in (1, 2, 3):
            req = urllib.request.Request(f"{API}/repos/{repo}/issues?state=open&per_page=100&page={page}",
                                         headers={"Accept": "application/vnd.github+json", "User-Agent": "gamedev-kit"})
            got = json.load(urllib.request.urlopen(req, timeout=10))
            out += [i for i in got if "pull_request" not in i and i.get("title", "").startswith("feedback(")]
            if len(got) < 100:
                break
    except Exception:
        return None
    return out


def near(engine, text, issues):
    """Open issues of the same engine whose words overlap, the three with the most overlap first."""
    mine, found = set(WORD_RE.findall(text.lower())), []
    for i in issues:
        if not i["title"].startswith(f"feedback({engine})"):
            continue
        theirs = set(WORD_RE.findall((i["title"] + " " + (i.get("body") or "")).lower()))
        score = len(mine & theirs) / max(1, min(len(mine), len(theirs)))
        if score >= NEAR:
            found.append((score, i["number"], i["title"]))
    return sorted(found, reverse=True)[:3]


def gh():
    name = config().get("feedback", {}).get("gh") or "gh"
    return name if os.path.exists(name) else shutil.which(name)


def cmd_list():
    items, block = todo(), private()
    print(f"{FEEDBACK} — {len(items)} unsent lines" if lines() else f"{FEEDBACK} not found")
    for n, (_i, engine, text) in enumerate(items, 1):
        bad = leaks(text, block)
        print(f"  {n}. ({engine}) {text}" + (f"\n     ! words that seem to be this game's: {' · '.join(bad)}" if bad else ""))


def cmd_preview(arg):
    repo, version = kit()
    issues, block = open_issues(repo), private()
    print(f"Goes to: {WEB}/{repo}/issues" + ("" if issues is not None else " (could not read the open issues — similar ones were not checked)"))
    for n, (_i, engine, text) in pick(arg):
        print(f"\n[{n}] {title(engine, text)}\n{body(engine, text, version)}")
        bad = leaks(text, block)
        if bad:
            print(f"! words that seem to be this game's: {' · '.join(bad)} — not sent until the line is rewritten")
        for _s, num, name in near(engine, text, issues or []):
            print(f"~ similar issue #{num}: {name}")


def cmd_send(arg, to, as_is):
    repo, version = kit()
    chosen, block = pick(arg), private()
    if to and len(chosen) != 1:
        sys.exit("--to takes one line only")
    for n, (_i, _engine, text) in chosen:  # if any one is caught, nothing is sent
        bad = leaks(text, block)
        if bad and not as_is:
            sys.exit(f"line {n} has words that seem to be this game's ({' · '.join(bad)}) — rewrite that line in {FEEDBACK}. Nothing was sent")
    tool, done = gh(), {}
    for n, (i, engine, text) in chosen:
        if to:
            said = f"여기서도 봤다 (엔진: {engine} · 키트: {version})\n\n{text}"
            args, by_hand = ["issue", "comment", to, "--repo", repo, "--body", said], f"comment this on {WEB}/{repo}/issues/{to}:\n{said}"
        else:
            args = ["issue", "create", "--repo", repo, "--title", title(engine, text), "--body", body(engine, text, version)]
            by_hand = (f"{WEB}/{repo}/issues/new?title={urllib.parse.quote(title(engine, text))}"
                       f"&body={urllib.parse.quote(body(engine, text, version))}")
        p = subprocess.run([tool] + args, capture_output=True, text=True) if tool else None
        if p is None or p.returncode != 0:
            why = "gh not found" if p is None else "gh could not post: " + (p.stderr.strip().split("\n")[-1] if p.stderr.strip() else "?")
            print(f"[{n}] {why} — the user posts it by hand: {by_hand}\n    once posted, record it with `sent <number> <issue number>` (`list` again for the number)")
            continue
        num = to or (re.findall(r"/issues/(\d+)", p.stdout) or ["?"])[-1]
        done[i] = (">", f"이슈 #{num}")
        print(f"[{n}] " + (f"commented on issue #{num}" if to else f"opened issue #{num}: {WEB}/{repo}/issues/{num}"))
    mark(done)


def cmd_close(arg, box, tail):
    chosen = pick(arg)
    if len(chosen) != 1:
        sys.exit("one line at a time")
    mark({chosen[0][1][0]: (box, tail)})
    print(f"written to {FEEDBACK}")


def notice():
    """Called by the hook at session start. Silent when there is nothing to say. Does not look outside."""
    global ROOT
    ROOT = find_root(os.getcwd())
    if not ROOT:
        return
    limit = config().get("feedback", {}).get("notice", NOTICE)
    count = sum(1 for line in lines() if OPEN_RE.match(line))
    if limit is False or count < limit:
        return
    print(f"[gamedev-kit] {count} lessons for the kit have piled up ({FEEDBACK}). Do not interrupt the work in hand — at a stopping point, tell the user in one line: "
          "`/gamedev-kit:feedback` sends them. To turn this notice off, put `\"feedback\": {\"notice\": false}` in kit.config.json.")


def main():
    args = sys.argv[1:]
    if "--notice" in args:
        try:
            notice()
        except Exception:  # a hook never blocks the session, whatever happens
            pass
        return
    opts = {}
    for flag in ("--root", "--to"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    as_is = "--as-is" in args
    args = [a for a in args if a != "--as-is"]
    cmd, rest = (args[0] if args else ""), args[1:]
    need = {"list": 0, "preview": 1, "send": 1, "sent": 2, "skip": 2}
    if need.get(cmd) != len(rest):
        sys.exit(__doc__)
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    if not ROOT or not os.path.exists(os.path.join(ROOT, CONFIG_NAME)):
        sys.exit(f"{CONFIG_NAME} not found — run this inside a game repository, after /gamedev-kit:init")
    if cmd == "list":
        cmd_list()
    elif cmd == "preview":
        cmd_preview(rest[0])
    elif cmd == "send":
        cmd_send(rest[0], opts.get("--to", "").lstrip("#"), as_is)
    elif cmd == "sent":
        cmd_close(rest[0], ">", f"이슈 #{rest[1].lstrip('#')}")
    else:
        cmd_close(rest[0], "-", f"안 보냄: {' '.join(rest[1].split())}")


if __name__ == "__main__":
    main()
