#!/usr/bin/env python3
"""The CEO — runs a game's cycles in the background, one headless Claude Code run (a worker) per step, while the user decides and plays.
It coordinates and decides nothing: every question stays a decision for the user, on the dashboard.

  python3 ceo.py status                 each open cycle: its stage and what moves it next — decisions · the build turn · the one thing to judge · a worker on it · ready.
                                        A built cycle nothing waits on is said, to be closed (`cycle.py settle`) — no one is asked
  python3 ceo.py ready                  the cycles a worker can take now (no open decision, no worker, no window of the user's on it, not at Play)
  python3 ceo.py run <NN> next          a worker goes on with cycle NN until it stops: decisions asked · the build turn another's · built (verified, and closed when nothing waits).
                                        It blocks until the worker ends — start it in the background
  python3 ceo.py run new "<goal>"       a worker starts a cycle for the goal (weighed against the others, then spec · design · plan) and stops at its decisions
  python3 ceo.py run <NN> playtest "<the user's problem list>"   a worker turns the list into a playtest document and stops at what is the user's
  python3 ceo.py run <NN> implement [<document>]                 a worker builds a playtest document's tasks and commits the round
  python3 ceo.py workers [<NN>]         the workers of this game — running, or how each ended (its STOP line and its last words), cost
  python3 ceo.py --notice               at session start (a hook): in a game the CEO runs, a window opened or cleared is told it is the CEO's — so "go on" picks it up
  python3 ceo.py setup --mode <permission mode> [--tools "<tool,…>"] [--budget <usd>] [--parallel <n>] [--model <model>]
                                        how workers run — "ceo" in kit.config.json. The user says it once: a worker runs with no one to ask
  python3 ceo.py accounts               the Claude accounts workers run on, in the order they are used — this machine's, not the game's (below)

Accounts — ~/.config/gamedev-kit/accounts/ (GAMEDEV_KIT_ACCOUNTS), outside every game, as the user sets it up:
  accounts.json   [{"name": "pro", "parallel": 2}, {"name": "max", "parallel": 5}] — a worker goes to the first that has room
  <name>.token    what `claude setup-token` printed, signed in as that account (chmod 600). A name with no token is this machine's own login
An account's limit is spent by every game on this machine, so its workers are counted across games. A worker that hits an account's usage limit
rests that account for an hour; the next `run` goes to the next account. No accounts.json: every worker runs on this machine's login, as before.
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
JUDGE = re.compile(r"^###\s+For you to judge[ \t]*$", re.M)  # the one thing of a cycle only a person can judge (the cycle skill writes it)
CHECKED = re.compile(r"^- Checked \((ok|problem)\): (.+?)(?: — “.*”)? \(\d{4}-\d\d-\d\d\)$", re.M)
STOP_RE = re.compile(r"^STOP: *(\w+)\s*(?:—|-)?\s*(.*)$", re.M)
WORKER_RULES = """You run as a worker of the game's CEO session: headless — no one reads this conversation while it runs, and no one can answer you.
- Never ask in the chat. Every question for the user is a decision (the cycle skill's `cycle.py ask …`), which reaches them on the dashboard; once asked, stop.
- Stop at the stops, do not wait them out: decisions asked and waiting · the build turn another session's · the build verified and committed · work the user must see.
- Verify the build yourself — the tests, and the play route's pictures held against the spec and the design (the cycle skill's "Verify the build").
  Never hand the user a list of things to check by playing: at most the one thing only a person can judge goes to them.
- Work on your one cycle. Never start another, never take a cycle another session holds.
- Commit as the skills say — each build, each round of fixes.
- Wait for everything in the foreground — agents (never `run_in_background`), checks, engine runs. This run ends the moment your turn ends,
  and whatever still runs in the background is lost with it, half done. Never end a turn to wait for a notification.
- Advice to /clear or to change sessions is not for you.
- End your last message with exactly one line: `STOP: <decisions|turn|play|blocked|done> — <one plain sentence for the user>`
  (`play` only when the one thing for the user to judge waits; a build that closed is `done`)."""
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


ACCOUNTS = os.path.expanduser(os.environ.get("GAMEDEV_KIT_ACCOUNTS") or "~/.config/gamedev-kit/accounts")
# what says which account a run is signed in as — the CEO window's own (a desktop app session passes its account on) is left out of a worker given a token
AUTH_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_ACCOUNT_UUID", "CLAUDE_CODE_USER_EMAIL",
            "CLAUDE_CODE_ORGANIZATION_UUID", "CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH", "CLAUDE_CODE_OAUTH_SCOPES", "USE_LOCAL_OAUTH", "USE_STAGING_OAUTH")
LIMIT_RE = re.compile(r"usage limit|limit reached|hit your limit|rate.?limit|out of (?:extra )?usage", re.I)
REST = 3600  # an account that hit its limit is passed over this long

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


def accounts():
    """The accounts workers run on, in the order they are used: [{name, parallel}]. Empty: this machine's login only."""
    rows = load(os.path.join(ACCOUNTS, "accounts.json"), [])
    return [{"name": r["name"], "parallel": int(r.get("parallel", 1))} for r in (rows if isinstance(rows, list) else [])
            if isinstance(r, dict) and re.fullmatch(r"[A-Za-z0-9_-]+", str(r.get("name", "")))]


def token_of(name):
    try:
        return open(os.path.join(ACCOUNTS, f"{name}.token"), encoding="utf-8").read().strip()
    except OSError:
        return ""


def keep(name, data):
    os.makedirs(ACCOUNTS, exist_ok=True)
    path = os.path.join(ACCOUNTS, name)
    with open(path + f".{os.getpid()}.part", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(path + f".{os.getpid()}.part", path)


def on_accounts():
    """pid → account of every worker running on this machine, whatever the game — an account's limit is spent by all of them."""
    return {p: a for p, a in load(os.path.join(ACCOUNTS, "running.json"), {}).items() if alive(p)}


def resting():
    """Account → when it may run again, for the accounts that hit their usage limit within the hour."""
    return {a: t for a, t in load(os.path.join(ACCOUNTS, "resting.json"), {}).items() if isinstance(t, (int, float)) and t > time.time()}


def use(pid, name):
    """Counts a worker against its account (pid given) or stops counting it (name None)."""
    rows = on_accounts()
    if name is None:
        rows.pop(str(pid), None)
    else:
        rows[str(pid)] = name
    keep("running.json", rows)


def account_line():
    """Each account as it stands: workers on it of its room, or resting."""
    busy, rest = list(on_accounts().values()), resting()
    return " · ".join(f"{a['name']} " + (f"rests until {time.strftime('%H:%M', time.localtime(rest[a['name']]))}" if a["name"] in rest
                                         else f"{busy.count(a['name'])}/{a['parallel']}") + ("" if token_of(a["name"]) else " (this machine's login)")
                      for a in accounts())


def pick_account():
    """The first account with room that is not resting — None when there are accounts and none has room; {} when there are none."""
    have = accounts()
    if not have:
        return {}
    busy, rest = list(on_accounts().values()), resting()
    return next((a for a in have if a["name"] not in rest and busy.count(a["name"]) < a["parallel"]), None)


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


def judge_left(text):
    """The cycle's one thing for the user to judge, when no answer is recorded for it — "" otherwise."""
    m = JUDGE.search(text)
    if not m:
        return ""
    nxt = re.search(r"^#{1,3} ", text[m.end():], re.M)
    lines = [x.strip() for x in text[m.end():m.end() + nxt.start() if nxt else len(text)].split("\n") if x.strip() and not x.strip().startswith(("<!--", "|", "- Checked (", "- Not played:"))]
    bullets = [re.sub(r"^(?:[-*]|\d+[.)])\s+", "", x) for x in lines if re.match(r"^(?:[-*]|\d+[.)])\s+", x)] or lines
    done = {" ".join(c.split()) for _r, c in CHECKED.findall(text)}
    return bullets[0] if bullets and " ".join(bullets[0].split()) not in done else ""


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
        if judge_left(text):
            return stage, "built — one thing for you to judge, on the dashboard's Review (a problem goes to `run playtest`)", False
        return stage, f"built, nothing waits on you — close it: `cycle.py settle --doc {os.path.relpath(path, ROOT)}`", False
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
    idle = [p for p in docs() if PLAY.match(stage_of(open(p, encoding="utf-8").read())) and num(p) not in running()
            and not OPEN_DECISION.search(open(p, encoding="utf-8").read()) and not judge_left(open(p, encoding="utf-8").read())]
    if idle:
        print(f"{len(idle)} built cycle(s) wait on nothing — close each now, without asking: "
              + " · ".join(f"`cycle.py settle --doc {os.path.relpath(p, ROOT)}`" for p in idle)
              + " (it says what still waits, if anything does); what the user brings about a closed one is a new cycle's")
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
    if accounts():
        print(f"accounts: {account_line()}")


def cmd_accounts():
    if not accounts():
        print(f"no accounts — every worker runs on this machine's login. To spread them over accounts: {os.path.join(ACCOUNTS, 'accounts.json')} "
              "(this script's head says how)")
        return
    print(account_line())
    missing = [a["name"] for a in accounts() if not token_of(a["name"])]
    if len(missing) > 1:
        print(f"more than one account without a token ({' · '.join(missing)}) — they are all this machine's one login")


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
    n = 0 if kind == "new" else int(str(target).lstrip("Cc"))
    if n:
        path = doc_of(n)
        if kind != "implement" and stage_of(open(path, encoding="utf-8").read()) in CLOSED:  # a playtest already analysed is built to the end
            sys.exit(f"C{n:02d} is closed — the user played it and was done with it. What they bring about it now is a new cycle's: "
                     f"`run new \"<their words>\"` (or later: `cycle.py later \"…\"`)")
        stage, what, ready = state(path)
        built = PLAY.match(stage) and n not in running() and "nothing waits" in what  # an answer the CEO recorded may still ask for work on it
        if kind == "next" and not ready and not built:
            sys.exit(f"C{n:02d} — {what}")
        if n in running():
            sys.exit(f"C{n:02d}: {what}")
    claude = os.environ.get("KIT_CLAUDE") or shutil.which("claude")  # looked for once the cycle is known to be runnable — a refusal needs no claude
    if not claude:
        sys.exit("claude (Claude Code) is not on this machine's PATH")
    if len(running()) >= c["parallel"]:
        sys.exit(f"{c['parallel']} worker(s) already running — the next one starts when one ends (`setup --parallel <n>` to change)")
    account = pick_account()
    if account is None:
        sys.exit(f"no account has room — {account_line()}; the next one starts when a worker ends or an account rests no more")
    env = dict(os.environ, KIT_WORKER="1")  # its hooks leave the dashboard's answers to the CEO window
    token = token_of(account["name"]) if account else ""
    if token:  # signed in as that account, whatever the CEO window is signed in as
        env = {k: v for k, v in env.items() if k not in AUTH_ENV}
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    before = set(docs())
    logs = os.path.join(kept(), "workers")
    os.makedirs(logs, exist_ok=True)
    started = datetime.datetime.now()
    log = os.path.join(logs, f"C{n:02d}-{kind}-{started:%Y%m%d-%H%M%S}.json")
    args = [claude, "-p", prompt(kind, n, said), "--permission-mode", c["mode"], "--output-format", "json", "--append-system-prompt", WORKER_RULES,
            "--max-budget-usd", str(c["budget"])] + (["--allowedTools", ",".join(c["tools"])] if c["tools"] else []) + (["--model", c["model"]] if c["model"] else [])
    with open(log, "w", encoding="utf-8") as out, open(log[:-5] + ".err", "w", encoding="utf-8") as err:
        proc = subprocess.Popen(args, cwd=ROOT, stdout=out, stderr=err, stdin=subprocess.DEVNULL, env=env)
        name = account.get("name", "")
        if name:
            use(proc.pid, name)
        rows = workers()
        rows.append({"cycle": n, "kind": kind, "what": {"next": "going on", "new": f"new: {said[:60]}", "playtest": "playtest analysis",
                                                       "implement": "playtest build"}[kind], "pid": proc.pid, "started": f"{started:%Y-%m-%d %H:%M}", "log": log,
                     "account": name})
        save_workers(rows)
        print(f"worker started for {'a new cycle' if kind == 'new' else f'C{n:02d}'} ({kind})" + (f" on the {name} account" if name else "")
              + " — it runs until it stops", flush=True)
        code = proc.wait()
        if name:
            use(proc.pid, None)
    got = load(log, {})
    result = got.get("result") or ""
    stop = STOP_RE.search(result)
    limit = not stop and (code or got.get("is_error") or not got) and LIMIT_RE.search(result + "\n" + open(log[:-5] + ".err", encoding="utf-8", errors="replace").read()[-4000:])
    if limit and name:
        keep("resting.json", dict(resting(), **{name: time.time() + REST}))
    rows = workers()
    for w in rows:
        if w.get("pid") == proc.pid and w.get("log") == log:
            if not n:  # a new cycle: the document the worker made
                made = sorted(set(docs()) - before)
                w["cycle"] = num(made[0]) if made else 0
            w.update(ended=f"{datetime.datetime.now():%Y-%m-%d %H:%M}", ended_at=time.time(), code=code, cost=got.get("total_cost_usd"),
                     stop=stop.group(1).lower() if stop else "limit" if limit else "", last=result.strip()[-1500:],
                     said=stop.group(2).strip() if stop else f"the {name or 'signed-in'} account hit its usage limit" if limit else "")
            n = w["cycle"]
    save_workers(rows)
    minutes = round((datetime.datetime.now() - started).total_seconds() / 60)
    cost = f" · ${got['total_cost_usd']:.2f}" if isinstance(got.get("total_cost_usd"), (int, float)) else ""
    if stop:
        print(f"C{n:02d} worker ended — STOP {stop.group(1)}: {stop.group(2).strip()} · {minutes} min{cost}")
    elif limit:
        print(f"C{n:02d} worker ended — the {name or 'signed-in'} account hit its usage limit · {minutes} min"
              + (f". It rests an hour; `run` again goes to the next account ({account_line()})" if name and len(accounts()) > 1
                 else " — it runs again once the limit resets (more accounts: `accounts`)"))
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
        on = f" · {w['account']}" if w.get("account") else ""
        print(f"C{w['cycle']:02d} {w['kind']} {w['started']} → {w['ended']} — STOP {w.get('stop') or '?'}: {w.get('said', '')}{cost}{on}")
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
    kept_mode = "--mode" not in opts and c.get("mode")
    c = dict(DEFAULTS, **c)
    print(("mode unchanged — " if kept_mode else "") + f"workers run with {c['mode'] or '(no mode yet)'} · tools {', '.join(c['tools']) or 'any'} · up to ${c['budget']:g} each · {c['parallel']} at a time"
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
    if cmd == "accounts" and not rest:
        return cmd_accounts()
    if cmd == "run" and len(rest) >= 2:
        if rest[0] == "new" and len(rest) == 2:
            return cmd_run(0, "new", rest[1])
        if re.fullmatch(r"[Cc]?\d+", rest[0]) and rest[1] in ("next", "playtest", "implement"):
            if rest[1] == "next" and len(rest) == 2 or rest[1] == "playtest" and len(rest) == 3 or rest[1] == "implement" and len(rest) <= 3:
                return cmd_run(rest[0], rest[1], rest[2] if len(rest) == 3 else "")
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
