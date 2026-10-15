#!/usr/bin/env python3
"""The user's own rules — what their games taught that would trip them again — and the road by which a rule that holds for anyone goes to the kit as an issue.

The rules live outside every game, on this machine: ~/.config/gamedev-kit/rules/ (change it with GAMEDEV_KIT_RULES). rules.md holds whatever the engine,
rules-<engine>.md holds for one engine (the `engine` of kit.config.json). One rule per line: `- R3. <the rule and its reason> (<game>)`, then
` [issue #12]` once it went to the kit, or ` [not for the kit: <why>]`. The kit rules block in every game's CLAUDE.md imports both files,
so a rule holds from the next session in every game of the user's — their size is the cost, read on every turn.

  python3 feedback.py add "<the rule and its reason>"   A rule for this engine's games (--any: whatever the engine). Prints its id. Nothing is asked — it stays on this machine
  python3 feedback.py list                 The rules this game loads, each with its state: not sent · issue #12 · not for the kit — and each file's size (--all: every file)
  python3 feedback.py drop R3              Remove it. Its number is not given out again
  python3 feedback.py preview R3,R5        The title · body of the issues that would go out, and similar issues already open on the kit. Sends nothing
  python3 feedback.py send R3,R5           Open the issues (gh) and write their numbers on the rules. Without gh, gives a pre-filled "new issue" address
  python3 feedback.py send R3 --to 14      No new issue — comment "seen here too" on issue #14
  python3 feedback.py sent R3 14           The user posted it by hand from the address
  python3 feedback.py keep R3 "<why>"      The user's alone — not offered for the kit again
  python3 feedback.py auto on|off          The user's standing answer: send every rule to the kit by itself (on), or only what they send (off). Asked once, kept on this machine
  python3 feedback.py push                 With auto on: send every rule not yet sent, not kept, with nothing that looks like a game's words — a new issue, or a comment on an
                                           open one that says much the same. What is held back stays for the user to reword. The hook runs it after a turn (--quiet)
  python3 feedback.py state                Every rule sent: where its issue stands on the kit — open · closed (completed) · closed (not planned). Read without logging in
  python3 feedback.py --notice             Called by the hook at session start: one line when unsent rules have piled up. Does not look outside

`list` · `preview` · `state` take --json (what the dashboard reads). Outside a game, --all lists every file and send · drop still work.
Before anything goes out it looks for words that seem to be a game's (the game folder's name · the GDD's title · feedback.private in kit.config.json ·
the game the rule came from · private-words.txt in the rules folder) and for dates, and stops if there are any. `--as-is` only when the user said to send it as it is.

Where issues go: the repository in the plugin manifest (override with feedback.repo in kit.config.json). The path of gh is feedback.gh.

The rules once lived in the voice folder (~/.config/gamedev-kit/voice, GAMEDEV_KIT_VOICE) — the first run copies them here and leaves that folder as it was.
Lessons a game once wrote in docs/kit-feedback.md are taken in once: a line much like a rule already here is marked as that rule, any other becomes a new rule.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

CONFIG_NAME = "kit.config.json"
OLD_FILE = os.path.join("docs", "kit-feedback.md")  # where a game kept its lessons for the kit before the rules held them
PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                      ".claude-plugin", "plugin.json")
WEB = "https://github.com"
API = os.environ.get("GAMEDEV_KIT_GITHUB_API") or "https://api.github.com"
HOME = os.path.expanduser(os.environ.get("GAMEDEV_KIT_RULES") or "~/.config/gamedev-kit/rules")
OLD_HOME = os.path.expanduser(os.environ.get("GAMEDEV_KIT_VOICE") or "~/.config/gamedev-kit/voice")
LAST = os.path.join(HOME, "rules.last")
SETTINGS = os.path.join(HOME, "settings.json")  # {"auto": true | false} — absent until the user has been asked  # the highest rule number given out so far — a dropped rule's number is not reused
RULES_HEAD = ("# The user's rules{engine}\n\n"
              "What this user learned in earlier games that holds {scope} — one rule per line, written by `feedback.py add`. "
              "Claude Code loads this file into every game made with gamedev-kit.\n\n")
RULE_RE = re.compile(r"^- R(\d+)\. (.*?)(?: \((?P<game>[^()]*)\))?(?: \[(?:issue #(?P<issue>\d+)|not for the kit: (?P<kept>[^\]]*))\])?$", re.M)
OLD_OPEN = re.compile(r"^- \[ \] (.*)$")
META_RE = re.compile(r"^\(([^)]*)\)\s*(.*)$")
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
WORD_RE = re.compile(r"[0-9A-Za-z_가-힣]{2,}")
NOTICE = 5  # this many unsent rules from this game and the session start says so
NEAR = 0.25  # this much word overlap and it is shown as similar — the reader decides whether it is the same
SAME = 0.5  # an old lesson line this close to a rule is taken as that rule

ROOT = ""
CFG = {}
GAME = ""
ENGINE = ""


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


def enter(root, must):
    global ROOT, CFG, GAME, ENGINE
    ROOT = os.path.abspath(root) if root else find_root(os.getcwd())
    if not ROOT or not os.path.exists(os.path.join(ROOT, CONFIG_NAME)):
        if must:
            sys.exit(f"{CONFIG_NAME} not found — run this inside a game repository, after /gamedev-kit:init")
        ROOT = ""
        return
    CFG = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8"))
    GAME = "-".join(os.path.basename(ROOT).split())
    ENGINE = CFG.get("engine") or ""


def read(path):
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def rules_file(engine):
    return os.path.join(HOME, f"rules-{engine}.md" if engine else "rules.md")


def rule_files():
    """Every rule file — numbers are unique across all of them, other engines' included."""
    names = os.listdir(HOME) if os.path.isdir(HOME) else []
    return [os.path.join(HOME, n) for n in sorted(names) if n == "rules.md" or re.fullmatch(r"rules-.+\.md", n)]


def settle():
    """The rules folder made, the rules of the old voice folder copied in once, this game's rule files there (an import must not point at a missing file),
    and this game's old lesson lines taken in. Returns what was done, a line each."""
    told = []
    if not rule_files() and os.path.isdir(OLD_HOME):
        for name in sorted(os.listdir(OLD_HOME)):
            if name in ("rules.md", "rules.last", "private-words.txt") or re.fullmatch(r"rules-.+\.md", name):
                text = read(os.path.join(OLD_HOME, name)).replace("written by `voice.py rule`", "written by `feedback.py add`")
                write(os.path.join(HOME, name), text)
                told.append(f"copied {name} from {OLD_HOME} — the rules live in {HOME} now (the old folder is left as it was)")
    for engine in dict.fromkeys(("", ENGINE)):
        if not os.path.exists(rules_file(engine)):
            write(rules_file(engine), RULES_HEAD.format(engine=f" — {engine}" if engine else "",
                                                        scope=f"in every {engine} game" if engine else "whatever the engine"))
    return told + take_old_lessons()


def rules(files=None):
    """[(id number, text, game, issue, kept, file)] in file order."""
    out = []
    for path in files or rule_files():
        for m in RULE_RE.finditer(read(path)):
            out.append({"id": f"R{m.group(1)}", "num": int(m.group(1)), "text": m.group(2).strip(), "game": m.group("game") or "",
                        "issue": m.group("issue") or "", "kept": m.group("kept") or "", "file": os.path.basename(path)})
    return out


def last_rule():
    return max([r["num"] for r in rules()] + [int(read(LAST).strip() or 0)])


def find(rid):
    m = re.fullmatch(r"[Rr]?(\d+)", rid.strip())
    hit = next((r for r in rules() if m and r["num"] == int(m.group(1))), None)
    return hit or sys.exit(f"{rid}: no such rule — `list --all`")


def line(r):
    tail = f" [issue #{r['issue']}]" if r["issue"] else f" [not for the kit: {r['kept']}]" if r["kept"] else ""
    return f"- {r['id']}. {r['text']}" + (f" ({r['game']})" if r["game"] else "") + tail


def rewrite(r):
    """Write one rule's line back as it now stands."""
    path = os.path.join(HOME, r["file"])
    text = read(path)
    m = next(m for m in RULE_RE.finditer(text) if int(m.group(1)) == r["num"])
    write(path, text[:m.start()] + line(r) + text[m.end():])


def add(text, any_engine, quiet=False):
    text = " ".join(text.split())
    if not text:
        sys.exit("a rule needs its text — `add \"<the rule and its reason>\"`")
    if not any_engine and not ENGINE:
        sys.exit(f"{CONFIG_NAME} names no engine — `add --any` for a rule that holds whatever the engine")
    path, num = rules_file("" if any_engine else ENGINE), last_rule() + 1
    body = read(path)
    write(path, body + ("" if body.endswith("\n") else "\n") + f"- R{num}. {text}" + (f" ({GAME})" if GAME else "") + "\n")
    write(LAST, f"{num}\n")
    if not quiet:
        print(f"R{num} — {path}")
    return f"R{num}"


def words(text):
    return set(WORD_RE.findall(text.lower()))


def overlap(a, b):
    x, y = words(a), words(b)
    return len(x & y) / max(1, min(len(x), len(y)))


def take_old_lessons():
    """This game's unsent lines in docs/kit-feedback.md become rules — once. A line much like a rule already here is marked as that rule."""
    path = os.path.join(ROOT, OLD_FILE) if ROOT else ""
    if not path or not os.path.exists(path):
        return []
    out, told = read(path).split("\n"), []
    for i, ln in enumerate(out):
        m = OLD_OPEN.match(ln)
        if not m:
            continue
        meta = META_RE.match(m.group(1))
        engine = meta.group(1).split("·")[0].strip() if meta else ENGINE
        text = (meta.group(2) if meta else m.group(1)).strip()
        mine = [r for r in rules() if r["file"] in ("rules.md", f"rules-{engine}.md")]
        best = max(mine, key=lambda r: overlap(text, r["text"]), default=None)
        if best and overlap(text, best["text"]) >= SAME:
            rid, what = best["id"], "the same as"
        else:
            rid, what = add(text, engine != ENGINE or not engine, quiet=True), "now"
        out[i] = f"- [>] {m.group(1)} — {what} rule {rid}"
        told.append(f"{OLD_FILE}: “{text[:60]}…” → {what} {rid}")
    write(path, "\n".join(out))
    return told


def config():
    return CFG


def kit():
    """(the repository issues go to `owner/name`, the kit's version)"""
    plugin = json.load(open(PLUGIN, encoding="utf-8"))
    repo = config().get("feedback", {}).get("repo") or plugin["repository"]
    return repo.replace(WEB + "/", "").strip("/"), plugin["version"]


def private(rule):
    """Words that seem to be a game's — what must not go out to a public repository."""
    found = [os.path.basename(ROOT)] if ROOT else []
    found += list(config().get("feedback", {}).get("private", [])) + [rule["game"]]
    gdd = os.path.join(ROOT, "docs", "GDD.md") if ROOT else ""
    if gdd and os.path.exists(gdd):
        head = open(gdd, encoding="utf-8").readline().lstrip("# ").split("—")[0].strip()
        if "<" not in head:
            found.append(head)
    for home in (HOME, OLD_HOME):
        found += [w.strip() for w in read(os.path.join(home, "private-words.txt")).split("\n") if w.strip() and not w.startswith("#")]
    return sorted({w.lower() for w in found if len(w.strip()) >= 3})


def leaks(rule):
    low = rule["text"].lower()
    return [f"‘{w}’" for w in private(rule) if w in low] + (["a date"] if DATE_RE.search(rule["text"]) else [])


def engine_of(rule):
    return rule["file"][len("rules-"):-3] if rule["file"].startswith("rules-") else "any"


def title(rule):
    head = rule["text"].split("→")[0].split(" — ")[0].strip()
    return f"feedback({engine_of(rule)}): " + (head if len(head) <= 80 else head[:79].rstrip() + "…")


def body(rule, version):
    return f"{rule['text']}\n\nengine: {engine_of(rule)} · kit: {version}"


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "gamedev-kit"})
    return json.load(urllib.request.urlopen(req, timeout=10))


def open_issues(repo):
    """Feedback issues open on the kit. None when they cannot be read — that does not block sending."""
    out = []
    try:
        for page in (1, 2, 3):
            got = get(f"{API}/repos/{repo}/issues?state=open&per_page=100&page={page}")
            out += [i for i in got if "pull_request" not in i and i.get("title", "").startswith("feedback(")]
            if len(got) < 100:
                break
    except Exception:
        return None
    return out


def near(rule, issues):
    """Open issues of the same engine whose words overlap, the three with the most overlap first."""
    found = []
    for i in issues:
        if not i["title"].startswith(f"feedback({engine_of(rule)})"):
            continue
        score = overlap(rule["text"], i["title"] + " " + (i.get("body") or ""))
        if score >= NEAR:
            found.append((score, i["number"], i["title"]))
    return sorted(found, reverse=True)[:3]


def pick(arg):
    want = [a for a in arg.split(",") if a.strip()]
    return [find(a) for a in want] or sys.exit("give rules as `R3,R5`")


def gh():
    name = config().get("feedback", {}).get("gh") or "gh"
    return name if os.path.exists(name) else shutil.which(name)


def state_word(r):
    return f"issue #{r['issue']}" if r["issue"] else f"not for the kit: {r['kept']}" if r["kept"] else "not sent"


def cmd_list(every, as_json):
    files = rule_files() if every or not ROOT else [p for p in dict.fromkeys((rules_file(""), rules_file(ENGINE))) if os.path.exists(p)]
    shown = rules(files)
    if as_json:
        return print(json.dumps([dict(r, state=state_word(r), engine=engine_of(r), leaks=leaks(r)) for r in shown], ensure_ascii=False, indent=1))
    for path in files:
        print(f"{os.path.basename(path)} — {os.path.getsize(path)} bytes")
        for r in rules([path]):
            bad = leaks(r) if not (r["issue"] or r["kept"]) else []
            print(f"  {r['id']}. {r['text']}" + (f" ({r['game']})" if r["game"] else "") + f" — {state_word(r)}"
                  + (f"\n     ! would not go out as written: {' · '.join(bad)}" if bad else ""))
    if not shown:
        print("no rules yet — `add \"<the rule and its reason>\"`")


def cmd_preview(arg, as_json):
    repo, version = kit()
    issues = open_issues(repo)
    out = []
    for r in pick(arg):
        out.append({"id": r["id"], "title": title(r), "body": body(r, version), "leaks": leaks(r),
                    "similar": [{"number": n, "title": t} for _s, n, t in near(r, issues or [])], "sent": r["issue"]})
    if as_json:
        return print(json.dumps({"repo": repo, "checked": issues is not None, "issues": out}, ensure_ascii=False, indent=1))
    print(f"Goes to: {WEB}/{repo}/issues" + ("" if issues is not None else " (could not read the open issues — similar ones were not checked)"))
    for p in out:
        print(f"\n[{p['id']}] {p['title']}\n{p['body']}")
        if p["sent"]:
            print(f"(already sent as issue #{p['sent']})")
        if p["leaks"]:
            print(f"! words that seem to be a game's: {' · '.join(p['leaks'])} — not sent until the rule is reworded")
        for s in p["similar"]:
            print(f"~ similar issue #{s['number']}: {s['title']}")


def cmd_send(arg, to, as_is):
    if os.environ.get("GAMEDEV_KIT_JOB"):  # Claude run by the dashboard with nobody watching: nothing leaves the machine
        sys.exit("not sent — this is a run the dashboard started (GAMEDEV_KIT_JOB); rules go out from a session the user is in")
    repo, version = kit()
    chosen = pick(arg)
    if to and len(chosen) != 1:
        sys.exit("--to takes one rule only")
    for r in chosen:  # if any one is caught, nothing is sent
        if r["issue"]:
            sys.exit(f"{r['id']} already went out as issue #{r['issue']}. Nothing was sent")
        bad = leaks(r)
        if bad and not as_is:
            sys.exit(f"{r['id']} has words that seem to be a game's ({' · '.join(bad)}) — reword it in {os.path.join(HOME, r['file'])}. Nothing was sent")
    tool = gh()
    for r in chosen:
        if to:
            said = f"Seen here too (engine: {engine_of(r)} · kit: {version})\n\n{r['text']}"
            args, by_hand = ["issue", "comment", to, "--repo", repo, "--body", said], f"comment this on {WEB}/{repo}/issues/{to}:\n{said}"
        else:
            args = ["issue", "create", "--repo", repo, "--title", title(r), "--body", body(r, version)]
            by_hand = f"{WEB}/{repo}/issues/new?title={urllib.parse.quote(title(r))}&body={urllib.parse.quote(body(r, version))}"
        p = subprocess.run([tool] + args, capture_output=True, text=True) if tool else None
        if p is None or p.returncode != 0:
            why = "gh not found" if p is None else "gh could not post: " + (p.stderr.strip().split("\n")[-1] if p.stderr.strip() else "?")
            print(f"[{r['id']}] {why} — the user posts it by hand: {by_hand}\n    once posted, record it with `sent {r['id']} <issue number>`")
            continue
        num = to or (re.findall(r"/issues/(\d+)", p.stdout) or ["?"])[-1]
        rewrite(dict(r, issue=num, kept=""))
        print(f"[{r['id']}] " + (f"commented on issue #{num}" if to else f"opened issue #{num}: {WEB}/{repo}/issues/{num}"))


def auto():
    try:
        return json.load(open(SETTINGS, encoding="utf-8")).get("auto")
    except (OSError, ValueError):
        return None


def waiting():
    """Rules that would go out: not sent, not kept."""
    return [r for r in rules() if not r["issue"] and not r["kept"]]


def cmd_push(quiet):
    """Send what can go by itself. Silent with --quiet unless something went out."""
    if os.environ.get("GAMEDEV_KIT_JOB"):
        return None if quiet else print("not sent — this is a run the dashboard started; the next session sends them")
    if auto() is not True:
        return None if quiet else print("auto is off — the user sends rules themselves (`send`), or `auto on` once they say so")
    todo = waiting()
    held = [r for r in todo if leaks(r)]
    go = [r for r in todo if not leaks(r)]
    if not go:
        return None if quiet else print(f"nothing to send" + (f" — {len(held)} held back until reworded: {', '.join(r['id'] for r in held)}" if held else ""))
    tool = gh()
    if not tool:
        return None if quiet else print(f"{len(go)} rule(s) wait for gh — install it and `gh auth login`, then `push`")
    repo, _version = kit()
    issues = open_issues(repo) or []
    for r in go:
        same = next((n for s, n, _t in near(r, issues) if s >= SAME), None)
        with contextlib.redirect_stdout(io.StringIO()) if quiet else contextlib.nullcontext():
            cmd_send(r["id"], str(same) if same else "", False)
    sent = [r for r in rules() if r["issue"] and r["id"] in {g["id"] for g in go}]
    if sent:
        print(f"[gamedev-kit] sent {len(sent)} of the user's rules to the kit: " + " · ".join(f"{r['id']} → #{r['issue']}" for r in sent))
    if held and not quiet:
        print(f"{len(held)} held back until reworded: {', '.join(r['id'] for r in held)}")


def cmd_state(as_json):
    """Where each sent rule's issue stands. `closed (completed)` is the kit saying it now carries the rule."""
    repo, out = kit()[0], []
    for r in [r for r in rules() if r["issue"]]:
        try:
            got = get(f"{API}/repos/{repo}/issues/{r['issue']}")
            why = (got.get("state_reason") or "").replace("_", " ")
            st = got["state"] + (f" ({why})" if got["state"] == "closed" and why else "")
        except Exception:
            st = "could not be read"
        out.append({"id": r["id"], "issue": r["issue"], "state": st, "carried": st == "closed (completed)", "text": r["text"]})
    if as_json:
        return print(json.dumps(out, ensure_ascii=False, indent=1))
    for s in out:
        print(f"{s['id']} · #{s['issue']} {s['state']}" + (" — the kit carries it now: ask the user whether to drop their copy (`drop`)" if s["carried"] else ""))
    if not out:
        print("no rule has been sent to the kit")


def notice():
    """Called by the hook at session start. Silent when there is nothing to say. Does not look outside."""
    enter(None, must=False)
    if not ROOT:
        return
    settle()
    limit = config().get("feedback", {}).get("notice", NOTICE)
    todo = waiting()
    if limit is False or not todo:
        return
    if auto() is None:
        print(f"[gamedev-kit] {len(todo)} of the user's rules have not gone to the kit, and they have not been asked how rules go. Do not interrupt the work in hand — "
              "at a stopping point, ask once, as the feedback skill's \"Asking once\" says.")
    elif auto() is False and len([r for r in todo if r["game"] == GAME]) >= limit:
        print(f"[gamedev-kit] {len(todo)} of the user's rules have not been offered to the kit. At a stopping point, tell the user in one line: "
              "`/gamedev-kit:feedback` (or the dashboard's Rules page) sends them. To turn this notice off, put `\"feedback\": {\"notice\": false}` in kit.config.json.")
    elif auto() and [r for r in todo if leaks(r)]:
        print(f"[gamedev-kit] {len([r for r in todo if leaks(r)])} of the user's rules are held back from the kit — they name a game or a date. "
              "At a stopping point, offer to reword them (the feedback skill).")


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
    flags = {a for a in args if a in ("--as-is", "--any", "--all", "--json")}
    args = [a for a in args if a not in flags]
    cmd, rest = (args[0] if args else ""), args[1:]
    need = {"add": 1, "list": 0, "drop": 1, "preview": 1, "send": 1, "sent": 2, "keep": 2, "state": 0, "auto": 1, "push": 0}
    quiet = "--quiet" in args
    args = [a for a in args if a != "--quiet"]
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd == "push" and quiet:  # the hook: never a failed turn, and nothing said unless something went out
        try:
            enter(opts.get("--root"), must=False)
            if ROOT:
                settle()
                cmd_push(True)
        except Exception:
            pass
        return
    if need.get(cmd) != len(rest):
        sys.exit(__doc__)
    enter(opts.get("--root"), must=cmd == "add")
    for told in settle():
        if "--json" not in flags:
            print(told)
    if cmd == "add":
        add(rest[0], "--any" in flags)
    elif cmd == "list":
        cmd_list("--all" in flags, "--json" in flags)
    elif cmd == "preview":
        cmd_preview(rest[0], "--json" in flags)
    elif cmd == "state":
        cmd_state("--json" in flags)
    elif cmd == "auto":
        if rest[0] not in ("on", "off"):
            sys.exit("auto on | off")
        write(SETTINGS, json.dumps({"auto": rest[0] == "on"}) + "\n")
        print("rules go to the kit by themselves" if rest[0] == "on" else "rules go to the kit only when the user sends them")
    elif cmd == "push":
        cmd_push(False)
    elif cmd == "send":
        cmd_send(rest[0], opts.get("--to", "").lstrip("#"), "--as-is" in flags)
    elif cmd == "sent":
        r, num = find(rest[0]), rest[1].lstrip("#")
        if not num.isdigit():
            sys.exit(f"{rest[1]}: an issue number")
        rewrite(dict(r, issue=num, kept=""))
        print(f"{r['id']} [issue #{num}]")
    elif cmd == "keep":
        r = find(rest[0])
        rewrite(dict(r, issue="", kept=" ".join(rest[1].split()).replace("]", ")")))
        print(f"{r['id']} — not for the kit")
    else:
        r = find(rest[0])
        write(LAST, f"{last_rule()}\n")
        path = os.path.join(HOME, r["file"])
        text = read(path)
        m = next(m for m in RULE_RE.finditer(text) if int(m.group(1)) == r["num"])
        write(path, text[:m.start()] + text[m.end():].lstrip("\n"))
        print(f"dropped {r['id']} — {path}")


if __name__ == "__main__":
    main()
