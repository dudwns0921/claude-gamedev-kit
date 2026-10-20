#!/usr/bin/env python3
"""The CEO — runs a game's cycles in the background, one headless Claude Code run (a worker) per step, while the user decides and plays.
It coordinates and decides nothing: every question stays a decision for the user, on the dashboard.

  python3 ceo.py status                 each open cycle: its stage and what moves it next — decisions · the build turn · play · a worker on it · ready
  python3 ceo.py ready                  the cycles a worker can take now (no open decision, no worker, no window of the user's on it, not at Play)
  python3 ceo.py run <NN> next          a worker goes on with cycle NN until it stops: decisions asked · the build turn another's · Play.
                                        It blocks until the worker ends — start it in the background
  python3 ceo.py run new "<goal>"       a worker starts a cycle for the goal (weighed against the others, then spec · design · plan) and stops at its decisions
  python3 ceo.py run <NN> playtest "<the user's problem list>"   a worker turns the list into a playtest document and stops at what is the user's
  python3 ceo.py run <NN> implement [<document>]                 a worker builds a playtest document's tasks and commits the round
  python3 ceo.py workers [<NN>]         the workers of this game — running, or how each ended (its STOP line and its last words), cost
  python3 ceo.py --notice               at session start (a hook): in a game the CEO runs, a window opened or cleared is told it is the CEO's — so "go on" picks it up
  python3 ceo.py setup --mode <permission mode> [--tools "<tool,…>"] [--budget <usd>] [--parallel <n>] [--model <model>]
                                        how workers run — "ceo" in kit.config.json. The user says it once: a worker runs with no one to ask
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time

CONFIG_NAME = "kit.config.json"
SECTION = "ceo"
DIR = os.path.join("docs", "cycle")
DEFAULTS = {"mode": "", "tools": ["Bash", "Read", "Edit", "Write", "Glob", "Grep", "Skill", "Agent"], "budget": 15, "parallel": 2, "model": ""}
MODES = ("acceptEdits", "auto", "bypassPermissions")
STAGE_RE = re.compile(r"(?:Stage|단계): *(\S+)")
CLOSED = ("Closed", "끝")
PLAY = re.compile(r"Play|플레이|배포|회고")
BUILDING = ("Plan", "계획", "Build", "구현")  # a cycle whose next step is a build
OPEN_DECISION = re.compile(r"^- \[ \] D\d+\.", re.M)
STOP_RE = re.compile(r"^STOP: *(\w+)\s*(?:—|-)?\s*(.*)$", re.M)
WORKER_RULES = """You run as a worker of the game's CEO session: headless — no one reads this conversation while it runs, and no one can answer you.
- Never ask in the chat. Every question for the user is a decision (the cycle skill's `cycle.py ask …`), which reaches them on the dashboard; once asked, stop.
- Stop at the stops, do not wait them out: decisions asked and waiting · the build turn another session's · Play reached (the user plays) · work the user must see.
- Work on your one cycle. Never start another, never take a cycle another session holds.
- Commit as the skills say — each build, each round of fixes.
- Wait for everything in the foreground — agents (never `run_in_background`), checks, engine runs. This run ends the moment your turn ends,
  and whatever still runs in the background is lost with it, half done. Never end a turn to wait for a notification.
- Advice to /clear or to change sessions is not for you.
- End your last message with exactly one line: `STOP: <decisions|turn|play|blocked|done> — <one plain sentence for the user>`."""
ROOT = ""


def find_root(start):
    """Walk up from the current folder to the one holding kit.config.json."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return out_of_build_folder(d)
        up = os.path.dirname(d)
        if up == d:
            sys.exit(f"{CONFIG_NAME} not found — run this inside a game repository, after /gamedev-kit:init")
        d = up


BUILD_FOLDER = re.compile(r"^(.*)[/\\]\.git[/\\]gamedev-kit[/\\]worktrees[/\\][^/\\]+(?:[/\\](.*))?$")


def out_of_build_folder(d):
    """A cycle's build folder (a git worktree beside git's own files) holds a copy of the game: its documents and its state are the game's own folder's."""
    m = BUILD_FOLDER.match(d)
    return (os.path.join(m.group(1), m.group(2)) if m.group(2) else m.group(1)) if m else d


def whole():
    return json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8"))


def cfg():
    return dict(DEFAULTS, **(whole().get(SECTION) or {}))


def kept():
    """Beside git's own files, as the cycle script keeps who holds what — never committed. A folder outside git keeps it in docs/cycle/."""
    p = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT, capture_output=True, text=True)
    return os.path.join(ROOT, p.stdout.strip(), "gamedev-kit") if p.returncode == 0 and p.stdout.strip() else os.path.join(ROOT, DIR, ".gamedev-kit")


def load(path, empty):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return empty


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except (OSError, ValueError, TypeError):
        return True


def docs():
    d = os.path.join(ROOT, DIR)
    return sorted(os.path.join(d, n) for n in os.listdir(d) if re.match(r"\d+-.*\.md$", n)) if os.path.isdir(d) else []


def num(path):
    return int(os.path.basename(path).split("-")[0])


def doc_of(n):
    hit = [p for p in docs() if num(p) == int(n)]
    return hit[0] if hit else sys.exit(f"C{n}: no such cycle")


def stage_of(text):
    m = STAGE_RE.search(text)
    return m.group(1) if m else "?"


def store():
    """Who holds which cycle and whose build has the turn — the cycle script's record, read only."""
    path = os.path.join(kept(), "sessions.json") if kept().endswith(os.sep + "gamedev-kit") else os.path.join(ROOT, DIR, ".sessions.json")  # where the cycle script keeps it
    s = load(path, {}).get(os.path.realpath(ROOT)) or {}
    held = {int(h.get("cycle", 0)): int(p) for p, h in (s.get("held") or {}).items() if str(p).isdigit() and alive(p)}
    b = s.get("build")
    return held, b if b and alive(b.get("pid")) else None


def workers():
    return load(os.path.join(kept(), "workers.json"), [])


def save_workers(rows):
    path = os.path.join(kept(), "workers.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as f:
        json.dump(rows[-200:], f, ensure_ascii=False, indent=1)
    os.replace(path + ".part", path)


def running():
    """Cycle number → the worker on it now."""
    return {w["cycle"]: w for w in workers() if not w.get("ended") and alive(w.get("pid"))}


def settle():
    """A worker gone without ending (stopped, the machine slept) is written as gone — not left as running in the record."""
    rows, changed = workers(), False
    for w in rows:
        if not w.get("ended") and not alive(w.get("pid")):
            w.update(ended=f"{datetime.datetime.now():%Y-%m-%d %H:%M}", ended_at=time.time(), stop="gone", said="ended without a word — stopped from outside")
            changed = True
    if changed:
        save_workers(rows)


def folder_left(n):
    """What cycle n's build folder holds that is not in the game yet — commits not merged, changes not committed. "" when it has no folder or nothing."""
    wt = os.path.join(kept(), "worktrees", f"c{n:02d}")
    if not os.path.isdir(wt):
        return ""
    git = lambda *a: subprocess.run(["git", *a], cwd=wt, capture_output=True, text=True).stdout
    ahead = int(git("rev-list", "--count", f"HEAD", f"^{subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()}").strip() or 0)
    loose = len([l for l in git("status", "--porcelain").split("\n") if l.strip()])
    return " · ".join(x for x in (f"{ahead} commit(s) not merged" if ahead else "", f"{loose} change(s) not committed" if loose else "") if x)


def last_of(n):
    return next((w for w in reversed(workers()) if w["cycle"] == n and w.get("ended")), None)


def state(path):
    """(stage, what moves it next, ready for a worker)."""
    text, n = open(path, encoding="utf-8").read(), num(path)
    stage, held, build, busy = stage_of(text), *store(), running()
    asked = len(OPEN_DECISION.findall(text))
    if n in busy:
        return stage, f"a worker is on it — {busy[n]['what']}, since {busy[n]['started']}", False
    if n in held and held[n] not in {w.get("pid") for w in busy.values()}:
        return stage, "a window of yours works on it — left alone", False
    if asked:
        return stage, f"{asked} decision(s) wait for you — the dashboard's Review", False
    left = folder_left(n)
    if left:  # a build its worker did not finish or merge — at Play it is a playtest round's
        return stage, f"its build folder holds work not in the game ({left}) — `run {n} {'implement' if PLAY.match(stage) else 'next'}` finishes and merges it", True
    if PLAY.match(stage):
        return stage, "yours to play — problems go to `run playtest`", False
    last = last_of(n)
    if last and last.get("stop") == "blocked" and os.path.getmtime(path) <= last.get("ended_at", 0):
        return stage, f"blocked — {last.get('said', '')} (`workers {n}`)", False
    folders = isinstance((whole().get("cycle") or {}).get("worktree"), dict)  # each build in a folder of its own: only the merge takes the turn
    if build and not folders and stage in BUILDING and held.get(n) != build.get("pid"):  # its next step builds, and another has the turn
        return stage, f"waits for the build turn — {build.get('what', '')} has it", False
    return stage, "ready — a worker can go on with it", True


def cmd_status():
    shown = 0
    for p in docs():
        text = open(p, encoding="utf-8").read()
        if stage_of(text) in CLOSED:
            continue
        stage, what, _ready = state(p)
        print(f"C{num(p):02d} {os.path.basename(p)[3:-3]} — {stage} · {what}")
        shown += 1
    if not shown:
        print("no cycle is open — propose goals (the skill's \"New goals\")")
    played = [p for p in docs() if PLAY.match(stage_of(open(p, encoding="utf-8").read())) and num(p) not in running()]
    if len(played) > 1:
        print(f"{len(played)} cycles stand at Play — ask the user once which of them they have played and are done with; "
              "those close (`cycle.py close --doc <document>`), and what they bring about a closed one is a new cycle's")
    held, build = store()
    if isinstance((whole().get("cycle") or {}).get("worktree"), dict):
        print("builds: each cycle in a folder of its own — several build at once; only a merge into the game takes the turn, for a moment. "
              "Start every cycle that can move, up to the workers allowed — never queue builds one after another")
    else:
        print("builds: one at a time in the game's folder — the others wait for the turn; spec · design · plan · playtest analysis go on meanwhile")
    if build:
        print(f"build turn: {build.get('what', '')} since {build.get('at', '')}")
    n = len(running())
    print(f"workers running: {n} of {cfg()['parallel']}" + ("" if cfg()["mode"] else " · not set up — ask the user how workers may run (`setup`)"))


def cmd_ready():
    room = cfg()["parallel"] - len(running())
    hits = [p for p in docs() if stage_of(open(p, encoding="utf-8").read()) not in CLOSED and state(p)[2]]
    for p in hits:
        how = re.search(r"`(run \d+ \w+)`", state(p)[1])
        print(f"C{num(p):02d} {os.path.basename(p)[3:-3]} — `{how.group(1) if how else f'run {num(p)} next'}`")
    print(f"room for {max(room, 0)} more worker(s)" if hits else "nothing a worker can take now")


def prompt(kind, n, said):
    take = f"Work on cycle {n} of this game. With the cycle skill (/gamedev-kit:cycle), first `cycle.py take {n}`, then "
    return {"next": take + "`next` — and go on stage by stage until it stops.",
            "new": f"A new cycle for this goal, in the user's words: {said}\nStart it with the cycle skill (/gamedev-kit:cycle) and go on until it stops.",
            "playtest": take + f"hand this problem list, verbatim, to the playtest skill (/gamedev-kit:playtest) for analysis:\n{said}",
            "implement": take + "build the playtest document " + (said or "(the newest)") + " with the playtest skill (/gamedev-kit:playtest implement), and commit the round."}[kind]


def cmd_run(target, kind, said=""):
    c = cfg()
    if c["mode"] not in MODES:
        sys.exit("not set up — a worker runs with no one to ask, so the user says once how far it may go: "
                 f"`setup --mode <{'|'.join(MODES)}>` (the skill's \"Setting up\")")
    claude = os.environ.get("KIT_CLAUDE") or shutil.which("claude")
    if not claude:
        sys.exit("claude (Claude Code) is not on this machine's PATH")
    n = 0 if kind == "new" else int(str(target).lstrip("Cc"))
    if n:
        path = doc_of(n)
        if kind != "implement" and stage_of(open(path, encoding="utf-8").read()) in CLOSED:  # a playtest already analysed is built to the end
            sys.exit(f"C{n:02d} is closed — the user played it and was done with it. What they bring about it now is a new cycle's: "
                     f"`run new \"<their words>\"` (or later: `cycle.py later \"…\"`)")
        stage, what, ready = state(path)
        if kind == "next" and not ready:
            sys.exit(f"C{n:02d} — {what}")
        if n in running():
            sys.exit(f"C{n:02d}: {what}")
    if len(running()) >= c["parallel"]:
        sys.exit(f"{c['parallel']} worker(s) already running — the next one starts when one ends (`setup --parallel <n>` to change)")
    before = set(docs())
    logs = os.path.join(kept(), "workers")
    os.makedirs(logs, exist_ok=True)
    started = datetime.datetime.now()
    log = os.path.join(logs, f"C{n:02d}-{kind}-{started:%Y%m%d-%H%M%S}.json")
    args = [claude, "-p", prompt(kind, n, said), "--permission-mode", c["mode"], "--output-format", "json", "--append-system-prompt", WORKER_RULES,
            "--max-budget-usd", str(c["budget"])] + (["--allowedTools", ",".join(c["tools"])] if c["tools"] else []) + (["--model", c["model"]] if c["model"] else [])
    with open(log, "w", encoding="utf-8") as out, open(log[:-5] + ".err", "w", encoding="utf-8") as err:
        proc = subprocess.Popen(args, cwd=ROOT, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                env=dict(os.environ, KIT_WORKER="1"))  # its hooks leave the dashboard's answers to the CEO window
        rows = workers()
        rows.append({"cycle": n, "kind": kind, "what": {"next": "going on", "new": f"new: {said[:60]}", "playtest": "playtest analysis",
                                                       "implement": "playtest build"}[kind], "pid": proc.pid, "started": f"{started:%Y-%m-%d %H:%M}", "log": log})
        save_workers(rows)
        print(f"worker started for {'a new cycle' if kind == 'new' else f'C{n:02d}'} ({kind}) — it runs until it stops", flush=True)
        code = proc.wait()
    got = load(log, {})
    result = got.get("result") or ""
    stop = STOP_RE.search(result)
    rows = workers()
    for w in rows:
        if w.get("pid") == proc.pid and w.get("log") == log:
            if not n:  # a new cycle: the document the worker made
                made = sorted(set(docs()) - before)
                w["cycle"] = num(made[0]) if made else 0
            w.update(ended=f"{datetime.datetime.now():%Y-%m-%d %H:%M}", ended_at=time.time(), code=code, cost=got.get("total_cost_usd"),
                     stop=stop.group(1).lower() if stop else "", said=(stop.group(2).strip() if stop else ""), last=result.strip()[-1500:])
            n = w["cycle"]
    save_workers(rows)
    minutes = round((datetime.datetime.now() - started).total_seconds() / 60)
    cost = f" · ${got['total_cost_usd']:.2f}" if isinstance(got.get("total_cost_usd"), (int, float)) else ""
    if stop:
        print(f"C{n:02d} worker ended — STOP {stop.group(1)}: {stop.group(2).strip()} · {minutes} min{cost}")
    else:
        print(f"C{n:02d} worker ended without a STOP line (exit {code}{', ' + str(got.get('subtype')) if got.get('subtype') else ''}) · {minutes} min{cost}"
              f" — its last words: `workers {n}`; its output: {os.path.relpath(log, ROOT)}")


def cmd_workers(only=None):
    rows = [w for w in workers() if only is None or w["cycle"] == int(only)]
    for w in rows[-12:]:
        if not w.get("ended"):
            print(f"C{w['cycle']:02d} {w['kind']} — {'running' if alive(w.get('pid')) else 'gone without ending (the machine slept, or it was stopped)'} since {w['started']}")
            continue
        cost = f" · ${w['cost']:.2f}" if isinstance(w.get("cost"), (int, float)) else ""
        print(f"C{w['cycle']:02d} {w['kind']} {w['started']} → {w['ended']} — STOP {w.get('stop') or '?'}: {w.get('said', '')}{cost}")
    if only is not None and rows and rows[-1].get("last"):
        print("\nlast words:\n" + rows[-1]["last"])
    if not rows:
        print("no worker yet")


def cmd_setup(opts):
    data = whole()
    c = dict(data.get(SECTION) or {})
    if "--mode" in opts:
        if opts["--mode"] not in MODES:
            sys.exit(f"--mode is one of {' · '.join(MODES)}")
        c["mode"] = opts["--mode"]
    if "--tools" in opts:
        c["tools"] = [t.strip() for t in opts["--tools"].split(",") if t.strip()]
    for k, cast in (("--budget", float), ("--parallel", int)):
        if k in opts:
            c[k[2:]] = cast(opts[k])
    if "--model" in opts:
        c["model"] = opts["--model"]
    data[SECTION] = c
    with open(os.path.join(ROOT, CONFIG_NAME), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    c = dict(DEFAULTS, **c)
    print(f"workers run with {c['mode'] or '(no mode yet)'} · tools {', '.join(c['tools']) or 'any'} · up to ${c['budget']:g} each · {c['parallel']} at a time"
          + (f" · model {c['model']}" if c["model"] else ""))


NOTICE = ("This game is run by the CEO (`ceo` in kit.config.json). Unless the user asks to work on one cycle by hand in this window, this window is the CEO's: "
          "load the ceo skill (/gamedev-kit:ceo) before anything else and go on from its `status` — \"go on\", \"계속\", \"이어서\" mean that. "
          "Nothing needs carrying over: the cycles, the workers and the answers are all in files.")


def notice():
    """At session start (a hook): one paragraph, only in a game the CEO runs, never in a worker — it is quiet everywhere else and never fails."""
    if os.environ.get("KIT_WORKER"):
        return
    d = os.getcwd()
    while not os.path.exists(os.path.join(d, CONFIG_NAME)):
        if os.path.dirname(d) == d:
            return
        d = os.path.dirname(d)
    try:
        mode = (json.load(open(os.path.join(d, CONFIG_NAME), encoding="utf-8")).get(SECTION) or {}).get("mode")
    except (OSError, ValueError, AttributeError):
        return
    if mode:
        print(NOTICE)


def main():
    args = sys.argv[1:]
    if args == ["--notice"]:
        return notice()
    opts = {}
    for flag in ("--root", "--mode", "--tools", "--budget", "--parallel", "--model"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    cmd, rest = (args[0] if args else ""), args[1:]
    settle()
    if cmd == "status" and not rest:
        return cmd_status()
    if cmd == "ready" and not rest:
        return cmd_ready()
    if cmd == "workers" and len(rest) <= 1:
        return cmd_workers(rest[0].lstrip("Cc") if rest else None)
    if cmd == "setup":
        return cmd_setup(opts)
    if cmd == "run" and len(rest) >= 2:
        if rest[0] == "new" and len(rest) == 2:
            return cmd_run(0, "new", rest[1])
        if re.fullmatch(r"[Cc]?\d+", rest[0]) and rest[1] in ("next", "playtest", "implement"):
            if rest[1] == "next" and len(rest) == 2 or rest[1] == "playtest" and len(rest) == 3 or rest[1] == "implement" and len(rest) <= 3:
                return cmd_run(rest[0], rest[1], rest[2] if len(rest) == 3 else "")
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
