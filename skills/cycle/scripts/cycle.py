#!/usr/bin/env python3
"""Ledger for the cycle document (docs/cycle/NN-name.md) — pulls out and changes only the lines needed, without reading the whole document or editing it by hand.

  python3 cycle.py new <short-name> "<goal — in the user's own words>"   New document. Numbered after the last one. A previous cycle standing at Play becomes `Closed`, and what is left · deferred there is reported —
                                                with every playtest task still open and every asset slot still empty, so nothing made earlier is forgotten
  python3 cycle.py status                       Per document: stage · task counts · open decisions
  python3 cycle.py next                         Current stage, open decisions, the tasks of the next wave to run
  python3 cycle.py task T3                      One task and only the decisions it depends on (what the developer agent reads)
  python3 cycle.py mark T1 done "<what changed>"   [x], with one `- **Done**:` line — what changed, for the user: one plain sentence (the dashboard shows it),
                                                no code names, under 120 characters. `blocked` is [!], `open` is [ ], `doing` is [>] — the task an agent is on now (the board shows it)
  python3 cycle.py mark T2 blocked "<reason>"   One `- **Blocked**:` line under the task. Text after done goes in `- **Done**:`
  python3 cycle.py mark T4 dropped "<why>"      [-] — not to be done (merged into another, overtaken, the user said no). The reason is required
  python3 cycle.py ask <stage> "<question — ① … ② … · recommended: ①>"   Adds a decision and prints its number (D4). Any stage: Spec · Design · Plan · Build · Play, or Playtest · Asset
        [--image "<label>=<path>" …]            Pictures to look at while deciding (a capture of now, the candidates, a reference) — shown with it on the board and the dashboard.
                                                A short clip of play (.mp4 · .webm) or a sound to hear (.mp3 · .m4a · .wav — a voice line, an effect, a loop; up to 25 MB)
                                                goes the same way, played on the card
        [--why "<what led to it, in a line or two>"] [--detail "<the numbers, names and files behind it>"]
                                                The card reads the question, the why, the options, the recommendation — and keeps the detail folded.
                                                Written for the user to read on a phone, in what the player meets: the question short, two options or more,
                                                and no code names, file paths or document section numbers in it — those go in --detail. ask refuses otherwise
  python3 cycle.py attach D3 --image "<label>=<path>" …   Pictures for a decision already asked (they replace any attached before)
  python3 cycle.py reask D3 "<question — ① … ② … · recommended: ①>" [--image …]   Ask it again as a new decision (the answer was a question back, the options changed): D3 closes as "asked again as D7", D7 is asked
  python3 cycle.py todo "<what the user does, in a line>" [--wait <path>] [--why "<the steps>"] [--detail "<the prompt · settings to copy>"] [--image …]
                                                Something only the user can do outside this chat (make a file on a site, sign in, plug in a phone) — prints its number (U1).
                                                It waits on the board and the dashboard as a card; with --wait it closes by itself once that file is there
                                                (and the dashboard's watcher wakes the session for it). Not a choice — that is `ask`
  python3 cycle.py did U1 ["<what came of it>"]  The user did it — [x]. `drop U1 "<why>"` when it is not needed any more
  python3 cycle.py have <slot> "<what is in it>"   Writes the "Have" cell of an asset slot (the newest document that lists it): the path made · `placeholder (kept — D7)`
                                                for one the user leaves on its placeholder · `dropped — <why>` for one not needed. The board counts it as written
  python3 cycle.py decide D2 "<the user's answer, as said>"
  python3 cycle.py confirm D2,D5                A document from the time of auto mode: the user accepted what was decided in their place ([~]) — it becomes [x]. `confirm all` for all of them. To overturn: `decide D2 "<the user's answer>"`
  python3 cycle.py drop D4,D12 "<why, as said>"   The user says the decision (or the to-do, U3) is not needed any more — [-]. Nothing waits on it; it is no longer asked
  python3 cycle.py line "<the goal in one line>"   The goal as the board shows it — one line in what the player meets, under the user's own words in "Goal"
  python3 cycle.py shot "<stage of play>" <picture>   The screen of that stage of play as it stands now (a capture, from the game root) — one line under "Screens"
                                                in the "Play" section, replacing that stage's line. The board shows the newest one on the stage's card, and the cycle's first one on the cycle
  python3 cycle.py stage <stage>                Changes `Stage:` in the head (Goal · Spec · Design · Plan · Build · Play)
  python3 cycle.py skip Spec|Design "<why, in a line>"   The goal does not touch that section's owner (no rule or number changes · nothing seen or heard changes):
                                                its agent is not called, and the section says so. `next` and `status` show it
  python3 cycle.py epic T3,T4 "<epic>"          The epic a task belongs to — one stage of play (board.flow in kit.config.json, a part of its name is enough),
                                                or Foundation for what no stage owns (save, input, shared UI). One `- **Epic**:` line under the task
  python3 cycle.py epics                        Per epic: the tasks of every cycle and playtest in it (done · in hand · open · blocked) and what waits in the backlog;
                                                then the tasks with no epic yet
  python3 cycle.py later "<in the user's own words>" [--epic <epic>] [--key <review key>]   Puts it in the backlog (docs/backlog.md) — it stays there until a cycle takes it
                                                or the user drops it. With --key (an answer from the dashboard that is work for later), the line names the card — the board shows it waiting, not in hand
  python3 cycle.py backlog                      What waits in the backlog, by epic
  python3 cycle.py backlog take B2,B5           Taken into the newest cycle — [>] with its number. Its work is planned there as tasks
  python3 cycle.py backlog drop B3 "<why>"      Not to be done after all — [-] with the reason
  python3 cycle.py backlog epic B3 "<epic>"     The epic it belongs to

Tasks are named T3 inside their cycle, and C16-T3 across the game — every command that takes a task takes either (C16-T3 picks cycle 16's document).
  python3 cycle.py carry "<what the next session must know>"   One `- [ ]` line in the "Carried over" section, for work in hand that the document does not hold. `next` shows it
  python3 cycle.py checked "<the check, as the board lists it>" ok|problem ["<what was seen>"]   One `- Checked:` line in the "Play" section — the card leaves,
                                                and the cycle counts as played. A cycle closed with checks never answered stays "not played" on the board
  python3 cycle.py close                        The user has played it and is done with it — a cycle at Play becomes `Closed`. It closes by itself too,
                                                once every check by playing is answered ok and no decision of it is open. A playtest document already analysed
                                                is still built to the end on a closed cycle; anything the user brings about it afterwards is a new cycle's (`new`) or the backlog's (`later`)
  python3 cycle.py checks                       The checks by playing that do not read at a glance (a name from the code or the documents, too long) — `stage Play` says the same
  python3 cycle.py carry done                   The lines were picked up — they become [x], so the session after does not pick them up again

Several sessions at once — each works on one cycle; it is told apart by its Claude Code process, so it holds across /clear and lets go when the window closes:
  python3 cycle.py take 13 [--force]            This session works on cycle 13 from now on (`new` takes the one it makes). Refused while another open session
                                                holds it — --force only when the user says that session is done with it. `leave` lets it go
  python3 cycle.py open                         The other cycles still before Play: stage, whether a session works on it, its epics · files · GDD ids · asset slots —
                                                what the systems designer's `fit` weighs a new goal against
  python3 cycle.py commit build | playtest <document> | fix "<what>"   Commits what this build changed, the moment it is done (and after each round of fixes):
                                                the files changed since the build turn was taken, and this cycle's document — not what another session has in hand
  python3 cycle.py worktree open | merge | drop "<why>"   Where the game sets `cycle.worktree`: the cycle's build runs in its own folder (a git worktree,
                                                the engine's cache cloned in) — several cycles build at once. merge commits it, merges it into the game and removes the folder
  python3 cycle.py turn [take "<what>" | done | free]   The build turn — one session builds at a time. `mark … doing` takes it for the cycle, `stage Play` gives it back;
                                                `turn` alone exits 1 while another session has it (`until cycle.py turn; do sleep 60; done` waits for it).
                                                `free` — only when the user says the other session's build is not running

The document is the one this session holds; with none, the newest (highest number) — unless another session holds a cycle, then it says which there are
and stops for `take`. For another, `--doc <path>`.
Documents are written in English. Ones written before that use Korean words — both are read, and a stage or section given in Korean is taken too.
"""
import collections
import contextlib
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "cycle")
CLIP_MAX = 25 * 2**20  # the dashboard takes a file up to 30 MB
SOUNDS = (".mp3", ".m4a", ".wav")  # a sound to hear while deciding — a voice line, an effect, a loop
SHEETS = os.path.join(DIR, "sheets")  # where the sheet script keeps its questions — the board reads a decision's pictures from there
NOTES = os.path.join("docs", "handoff")  # notes of the skill that carried work across sessions before `carry` did
TEMPLATE = """# Cycle {num} — {name}

Started: {date} · Commit {commit} · Stage: Goal

## Goal
{goal}

## Decisions

## Spec

## Design

## Tasks

## Order

## Play
"""
BOX = {"done": "x", "blocked": "!", "open": " ", "dropped": "-", "doing": ">"}
OPEN = " >"  # a task not finished: not started, or one an agent is on
NOTE = {"done": "Done", "blocked": "Blocked", "dropped": "Dropped"}
# The words of the document: written in English, read in English and in the Korean of older documents.
KO = {"Goal": "목표", "Decisions": "결정", "Spec": "기획", "Design": "디자인", "Plan": "계획", "Build": "구현", "Tasks": "작업",
      "Order": "순서", "Play": "플레이", "Closed": "끝"}
EN = {ko: en for en, ko in KO.items()}  # a stage or section given in Korean on the command line is written in English
STAGE_RE = re.compile(r"((?:Stage|단계): *)(.+)")
OPEN_STAGE = re.compile(r"Play|플레이|배포|회고")  # 배포 · 회고 are from documents written when those were stages
CLOSED = ("Closed", "끝")
WAITING_RE = re.compile(r"\*\*(?:Waiting|대기)\*\*:(.*)")
WAVE_RE = re.compile(r"- *(?:Wave *(\d+)|(\d+) *차):(.*)")
CARRY = "Carried over"
CARRY_RE = re.compile(r"^- \[ \] (.+)$", re.M)
RESUMED_RE = re.compile(r"^(?:Resumed|이어받음):", re.M)
LATER_RE = re.compile(r"^- (?:Next|다음에): *(.+)$", re.M)
CHECKED_RE = re.compile(r"^- Checked \((ok|problem)\): (.+?)(?: — “.*”)? \(\d{4}-\d\d-\d\d\)$", re.M)
LINE_RE = re.compile(r"^In one line: *(.*)$", re.M)
SCREENS = "### Screens"
SHOT_RE = re.compile(r"^- (.+?) — `([^`]+)`$", re.M)
SHOT_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
CHECK_HEADS = re.compile(r"^###\s+(?:To see by playing|For a human to see)[ \t]*$", re.M)
PROXY_RE = re.compile(r"^(.*) → (.*?) · (?:proxy|대리) (.*?) \(\d{4}-\d\d-\d\d\)$")
TASK_RE = re.compile(r"^### \[(.)\] (T\d+)\.(.*)$", re.M)
DECISION_RE = re.compile(r"^- \[(.)\] (D\d+)\.(.*)$", re.M)
TODO = "For you"  # what only the user can do outside the chat — the board's review carries each as a card
TODO_RE = re.compile(r"^- \[(.)\] (U\d+)\.(.*)$", re.M)
WAIT_RE = re.compile(r" — wait: `([^`]+)`")
PLAYTESTS = os.path.join("docs", "playtest")
PLAYTEST_TASK = re.compile(r"^### \[([ !])\] (T\d+)\.(.*)$", re.M)
NEEDS_RE = re.compile(r"^### (?:Assets needed|필요한 에셋)[ \t]*$", re.M)
HAVE_EMPTY = re.compile(r"^(?:none|없음|—|-)?\s*$|^(?:none|없음)\b", re.I)
EPIC_RE = re.compile(r"^- \*\*Epic\*\*: *(.*)$", re.M)
WHAT_RE = re.compile(r"^- \*\*What\*\*: *\S", re.M)      # what the task is, for the user
CHANGE_RE = re.compile(r"^- \*\*Change\*\*: *\S", re.M)  # how the game will be different
KEY_RE = re.compile(r"^C(\d+)-(T\d+)$")  # a task across the game: cycle 16's T3 is C16-T3
FOUNDATION = "Foundation"  # the epic for what no stage of play owns — the board's `foundation` names it otherwise
BACKLOG = os.path.join("docs", "backlog.md")
BACKLOG_HEAD = ("# Backlog\n\nWhat is put off for a later cycle — one line each, kept until a cycle takes it (`[>]`) or the user drops it (`[-]`).\n"
                "Written by `cycle.py later` · `backlog` — do not edit by hand.\n\n")
BACKLOG_RE = re.compile(r"^- \[(.)\] (B\d+)\. (.*)$", re.M)
BL_EPIC = re.compile(r" — epic: ([^()]+?)(?= \(|$)")
SESSIONS = "sessions.json"  # which session holds which cycle, and the build turn — the board's watchers read it too, to send each answer to its cycle's session

ROOT = ""


def find_root(start):
    """Walk up from the current folder to the one holding kit.config.json. The tools live in the plugin; the game lives elsewhere."""
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


def docs():
    d = os.path.join(ROOT, DIR)
    return sorted(os.path.join(d, n) for n in os.listdir(d) if re.match(r"\d+-.*\.md$", n)) if os.path.isdir(d) else []


def session():
    """The Claude Code session this runs in: the nearest Claude Code process above this script — the same across /clear,
    gone when its window closes. None where there is no `ps`: sessions are then not told apart, and everything acts on the newest document."""
    if os.environ.get("KIT_SESSION"):
        return int(os.environ["KIT_SESSION"])
    try:
        pid = os.getppid()
        for _ in range(8):  # the nearest Claude Code process above — a shell may stand between (the Bash tool), or none (a hook, a monitor)
            out = subprocess.run(["ps", "-o", "ppid=,command=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
            if not out:
                break
            up, _sep, cmd = out.partition(" ")
            words, mark = cmd.split(), os.environ.get("KIT_SESSION_MARK")  # mark: what the tests' stand-in for a session carries
            if words and (os.path.basename(words[0]) == "claude" or os.path.basename(words[0]) in ("node", "bun") and len(words) > 1 and "claude" in words[1]
                          or os.path.basename(os.path.dirname(words[0])) == "ccd-cli"  # the desktop app's sessions: <…>/ccd-cli/<version>
                          or mark and mark in cmd):
                return pid
            pid = int(up)
            if pid <= 1:
                break
        out = subprocess.run(["ps", "-o", "ppid=", "-p", str(os.getppid())], capture_output=True, text=True, timeout=5).stdout.strip()
        return int(out) if out and int(out) > 1 else None  # no Claude Code above: the process above the shell that started this
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except (OSError, ValueError):
        return True  # there, but not ours to signal


def store():
    """Which session holds which cycle, and whose build is running — beside git's own files, so it is never committed.
    A game folder that is not a git repository keeps it in docs/cycle/."""
    p = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT, capture_output=True, text=True)
    if p.returncode == 0 and p.stdout.strip():
        return os.path.join(ROOT, p.stdout.strip(), "gamedev-kit", SESSIONS)
    return os.path.join(ROOT, DIR, "." + SESSIONS)


@contextlib.contextmanager
def sessions():
    """This game's entry in the store, cleared of sessions that have ended — {"held": {pid: {cycle, doc, at}}, "build": {pid, what, at} | None}.
    Changed in place inside the block and written back after it; one script at a time (a lock file)."""
    path = store()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock = path + ".lock"
    for _ in range(100):
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - os.path.getmtime(lock) > 10:  # left by a script that was killed
                    os.remove(lock)
            time.sleep(0.05)
    try:
        try:
            every = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            every = {}
        mine = every.get(os.path.realpath(ROOT)) or {}
        build = mine.get("build")
        state = {"held": {p: h for p, h in (mine.get("held") or {}).items() if alive(p)},
                 "build": build if build and alive(build.get("pid", 0)) else None}
        yield state
        if state["held"] or state["build"]:
            every[os.path.realpath(ROOT)] = state
        else:
            every.pop(os.path.realpath(ROOT), None)
        with open(path + ".part", "w", encoding="utf-8") as f:
            json.dump(every, f, ensure_ascii=False, indent=1)
        os.replace(path + ".part", path)
    finally:
        with contextlib.suppress(OSError):
            os.remove(lock)


def stamp():
    return f"{datetime.datetime.now():%Y-%m-%d %H:%M}"


def open_docs():
    return [p for p in docs() if stage_of(read(p)) not in CLOSED]


def building_docs():
    """The open cycles still before Play — what a new goal can collide with. One at Play is built: its fixes go through playtests."""
    return [p for p in open_docs() if not OPEN_STAGE.match(stage_of(read(p)))]


def holders():
    """Cycle document (from the game root) → the session holding it, for the sessions still open other than this one."""
    me = str(session())
    with sessions() as s:
        return {h["doc"]: dict(h, pid=p) for p, h in s["held"].items() if p != me}


def held_doc():
    """The document this session holds, if it holds one."""
    me = session()
    if me is None:
        return None
    with sessions() as s:
        h = s["held"].get(str(me))
    return os.path.join(ROOT, h["doc"]) if h and os.path.exists(os.path.join(ROOT, h["doc"])) else None


def unheld(others):
    """Several sessions work on the game and this one holds no cycle — which document a line goes to is not guessed."""
    lines = []
    for p in sorted(set(open_docs()) | {os.path.join(ROOT, d) for d in others}):
        rel, h = os.path.relpath(p, ROOT), others.get(os.path.relpath(p, ROOT))
        lines.append(f"  C{cycle_no(p)} {os.path.basename(p)[3:-3]} (stage {stage_of(read(p))}) — "
                     + (f"held by another session open since {h['at']}" if h else "free"))
    return ("another session is working on this game, and this one holds no cycle — say which this session works on:\n" + "\n".join(lines)
            + "\n`take <number>` to work on a free one (`new` starts another) · `--doc <path>` for one line in another cycle")


def pick(path):
    if path:
        path = path if os.path.isabs(path) else os.path.join(ROOT, path)
        if not os.path.exists(path):
            sys.exit(f"{path}: no such document")
        return path
    if not docs():
        sys.exit(f"no cycle document in {DIR}/ — cycle.py new <short-name> \"<goal>\"")
    mine = held_doc()
    if mine:
        return mine
    others = holders()
    if others:
        sys.exit(unheld(others))
    return docs()[-1]


def take(path, force=False):
    """This session works on that cycle from now on — every command without --doc acts on it, and the dashboard's answers to it come here."""
    me, rel = session(), os.path.relpath(path, ROOT)
    if me is None:
        return
    with sessions() as s:
        other = next((p for p, h in s["held"].items() if h["doc"] == rel and p != str(me)), None)
        if other and not force:
            sys.exit(f"C{cycle_no(path)} is held by another session open since {s['held'][other]['at']} — work on it there, or close that session. "
                     f"If the user says that session is done with it: take {cycle_no(path)} --force")
        if other:
            del s["held"][other]
        s["held"][str(me)] = {"cycle": str(cycle_no(path)), "doc": rel, "at": stamp()}
    print(f"this session works on C{cycle_no(path)} — {rel}")


def turn(what, path=None):
    """The build turn: one session's build at a time — two builds in one folder see each other's half-made code, and an engine runs one batch job per project.
    Taken by this session for `what`; refused while another open session has it."""
    me = session()
    if me is None:
        return True
    with sessions() as s:
        b = s["build"]
        if b and b["pid"] != me:
            print(f"the build turn is another session's ({b['what']}, since {b['at']}) — wait for it: run in the background\n"
                  f"  until python3 \"{os.path.abspath(__file__)}\" turn; do sleep 60; done\n"
                  "and call the wave when it ends. Meanwhile spec · design · plan · decisions · play go on")
            return False
        if not b:  # what is already changed now is not this build's — `commit` leaves it out
            s["build"] = {"pid": me, "what": what, "at": stamp(), "before": tree_state()}
    return True


def cmd_turn(rest):
    me = session()
    if rest and rest[0] == "take":
        mine = held_doc()
        if wt_cfg() and mine and os.path.isdir(wt_dir(cycle_no(mine))):
            return print(f"C{cycle_no(mine):02d} builds in its own folder — no turn to take; `worktree merge` takes it for the merge only")
        if not turn(" ".join(rest[1:]) or "a build"):
            sys.exit(1)
        return print("the build turn is this session's")
    if rest and rest[0] in ("done", "free"):
        with sessions() as s:
            b = s["build"]
            if b and (b["pid"] == me or rest[0] == "free"):
                s["build"] = None
                return print(f"the build turn is free ({b['what']} is done with it)")
        return print("the build turn was not this session's" if b else "the build turn is free")
    with sessions() as s:
        b = s["build"]
    if b and b["pid"] != me:
        print(f"the build turn is another session's: {b['what']}, since {b['at']}")
        sys.exit(1)
    print("the build turn is this session's" if b else "the build turn is free")


def git_top():
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def tree_state():
    """Every path git sees changed — tracked or new, not ignored — from the repository's top → a hash of what is in it now ("" when deleted)."""
    top = git_top()
    if not top:
        return {}
    raw = subprocess.run(["git", "status", "--porcelain", "-z", "-uall"], cwd=top, capture_output=True).stdout.decode("utf-8", "replace").split("\0")
    out, i = {}, 0
    while i < len(raw):
        entry = raw[i]
        i += 1
        if len(entry) < 4:
            continue
        if entry[0] in "RC":
            i += 1  # a rename names the old path next
        full = os.path.join(top, entry[3:])
        out[entry[3:]] = hashlib.sha1(open(full, "rb").read()).hexdigest() if os.path.isfile(full) else ""
    return out


def cmd_commit(path, kind, said=""):
    """Commits what this build changed, as soon as it is done — and again after each round of fixes from play:
    the files changed since the build turn was taken (with several sessions in one folder, what the others have in hand stays out),
    and this cycle's document. kind: build · playtest <document> · fix "<what, in a line>"."""
    top = git_top()
    if not top:
        return print("not a git repository — nothing committed")
    me = session()
    with sessions() as s:
        b = s["build"]
    mine = b if b and b["pid"] == me else None
    if holders() and not mine:
        sys.exit("other sessions work in this folder and this one does not hold the build turn — what changed is not told apart. "
                 "Take it before changing code (`turn take \"<what>\"`), then commit")
    if mine and "before" not in mine:
        sys.exit("the build turn was taken by an older kit, which kept no record of what was changed before it — this build's files are not told apart. "
                 "Commit them by naming them (git add <files>; git commit), then `turn done` — the next turn keeps the record")
    before = (mine or {}).get("before")
    others = {os.path.realpath(os.path.join(ROOT, d)) for d in holders()}  # another session's cycle document is its own to commit
    now = tree_state()
    files = [f for f, h in now.items() if (before is None or before.get(f) != h) and os.path.realpath(os.path.join(top, f)) not in others]
    doc = os.path.relpath(os.path.realpath(path), os.path.realpath(top))
    if doc in now and doc not in files:
        files.append(doc)
    if not files:
        return print("nothing changed since the build turn was taken — nothing committed")
    text = read(path)
    line = (LINE_RE.search(text).group(1).strip() if LINE_RE.search(text) else "") or os.path.basename(path)[3:-3]
    msg = {"build": f"Cycle {cycle_no(path):02d} build — {line}", "playtest": f"Cycle {cycle_no(path):02d} playtest {re.sub(r'[.]md$', '', os.path.basename(said))} — fixes from play",
           "fix": f"Cycle {cycle_no(path):02d} fix — {' '.join(said.split())}"}[kind]
    subprocess.run(["git", "add", "-A", "--", *files], cwd=top, check=True, capture_output=True)
    done = subprocess.run(["git", "commit", "-q", "-m", msg, "--", *files], cwd=top, capture_output=True, text=True)
    if done.returncode:
        sys.exit("git commit failed:\n" + (done.stderr or done.stdout).strip())
    if mine:
        with sessions() as s:  # committed — a second commit in the same turn (assets after the build) takes only what changes after this
            if s["build"] and s["build"]["pid"] == me:
                s["build"]["before"] = tree_state()
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=top, capture_output=True, text=True).stdout.strip()
    print(f"committed {head}: {msg} — {len(files)} file(s)")


def wt_cfg():
    """`cycle.worktree` in kit.config.json — a build runs in a folder of its own, so several build at once: {"clone": [the ignored folders a build needs, cloned in], "prune": [paths inside them removed again]}."""
    w = own_cfg().get("worktree")
    return w if isinstance(w, dict) else None


def wt_dir(n):
    """Cycle n's build folder — beside git's own files, out of every scan of the game."""
    p = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT, capture_output=True, text=True)
    return os.path.join(ROOT, p.stdout.strip(), "gamedev-kit", "worktrees", f"c{n:02d}")


def clone(src, dst):
    """A copy that shares the disk where the file system can (APFS · btrfs · XFS) — a game's import cache runs to gigabytes."""
    for args in (["cp", "-c", "-R"], ["cp", "-R", "--reflink=auto"]):
        if subprocess.run([*args, src, dst], capture_output=True).returncode == 0:
            return
    shutil.copytree(src, dst, symlinks=True)


def cmd_worktree(path, action, said=""):
    """open: the cycle's own build folder (a git worktree on branch kit/cNN from the last commit, with the folders the engine needs cloned in) —
    every build and check of the cycle runs there, beside other cycles' builds. merge: commit it there, merge it into the game, remove the folder.
    drop: remove the folder and its branch unmerged — only when the user says the build is not wanted."""
    cfg = wt_cfg() or sys.exit("this game builds in its own folder — no `\"cycle\": {\"worktree\": …}` in kit.config.json")
    top, n = git_top(), cycle_no(path)
    wt, branch = wt_dir(n), f"kit/c{n:02d}"
    game = os.path.join(wt, os.path.relpath(os.path.realpath(ROOT), os.path.realpath(top)))  # the game's root inside the folder
    git = lambda *a, at=top: subprocess.run(["git", *a], cwd=at, capture_output=True, text=True)
    if action == "open":
        with sessions() as s:  # building in the folder needs no turn: one held for the build is given back, so other cycles can merge meanwhile
            if s["build"] and s["build"]["pid"] == session() and "merge" not in s["build"].get("what", ""):
                s["build"] = None
                print("the build turn is given back — this build runs in its own folder; `worktree merge` takes the turn for the merge only")
        if os.path.isdir(wt):
            return print(f"build folder: {game}")
        made = git("worktree", "add", "-q", "-b", branch, wt, "HEAD")
        if made.returncode:
            made = git("worktree", "add", "-q", wt, branch)  # its branch is left from before
        if made.returncode:
            sys.exit("git worktree add failed:\n" + made.stderr.strip())
        for d in cfg.get("clone") or []:
            if os.path.exists(os.path.join(ROOT, d)) and not os.path.exists(os.path.join(game, d)):
                clone(os.path.join(ROOT, d), os.path.join(game, d))
        for d in cfg.get("prune") or []:  # a compile cache cloned from another path is wrong here — better absent than stale
            target = os.path.join(game, d)
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            elif os.path.exists(target):
                os.remove(target)
        print(f"build folder: {game} — every build and check of C{n:02d} runs there; the game's folder stays as it is until `worktree merge`")
        dirty = [l for l in git("status", "--porcelain").stdout.split("\n") if l.strip()]
        if dirty:
            print(f"the game's folder has {len(dirty)} uncommitted change(s) — the build folder starts from the last commit, without them")
        return
    if not os.path.isdir(wt):
        sys.exit(f"C{n:02d} has no build folder (`worktree open`)")
    if action == "drop":
        if not said.strip():
            sys.exit('say why: worktree drop "<the user\'s words>"')
        git("worktree", "remove", "--force", wt)
        git("branch", "-D", branch)
        return print(f"C{n:02d}'s build folder dropped, unmerged — {said}")
    text = read(path)
    line = (LINE_RE.search(text).group(1).strip() if LINE_RE.search(text) else "") or os.path.basename(path)[3:-3]
    git("add", "-A", at=wt)
    if git("diff", "--cached", "--quiet", at=wt).returncode:
        done = git("commit", "-q", "-m", f"Cycle {n:02d} build — {line}", at=wt)
        if done.returncode:
            sys.exit("git commit in the build folder failed:\n" + (done.stderr or done.stdout).strip())
    if int(git("rev-list", "--count", f"HEAD..{branch}").stdout.strip() or 0) == 0:
        git("worktree", "remove", "--force", wt)
        git("branch", "-D", branch)
        return print(f"C{n:02d}'s build folder held nothing new — removed")
    if not turn(f"C{n:02d} merge", path):  # the game's folder: one merge, play route and commit at a time
        sys.exit(1)
    merged = git("merge", "--no-ff", "-m", f"Merge cycle {n:02d} build — {line}", branch)
    if merged.returncode:
        clash = sorted(set(git("diff", "--name-only", "--diff-filter=U").stdout.split()))
        git("merge", "--abort")  # a merge refused before it began (local changes in the way) has nothing to abort — harmless
        with sessions() as s:
            if s["build"] and s["build"]["pid"] == session():
                s["build"] = None
        sys.exit(f"C{n:02d} not merged — the build folder is kept, the game's folder is as it was.\n"
                 + (f"both changed: {' · '.join(clash)}" if clash else (merged.stderr or merged.stdout).strip()[-800:])
                 + "\nPut it to the user as a decision (which side, or rebuild that part in the build folder) — never resolve it by choosing a side here")
    head = git("rev-parse", "--short", "HEAD").stdout.strip()
    git("worktree", "remove", "--force", wt)
    git("branch", "-D", branch)
    print(f"merged {head}: cycle {n:02d}'s build is in the game — the build folder is removed. The build turn is this session's until `stage Play`")


def cmd_open(path):
    """The other cycles still before Play — what the systems designer weighs a new goal against (`fit`): where each stands, who works on it,
    and what it touches (epics · files · GDD ids · asset slots). One at Play is left out: it is built, and what it fixes now goes through playtests."""
    others, me, b = holders(), session(), None
    with sessions() as s:
        b = s["build"]
    shown = 0
    for p in building_docs():
        if os.path.abspath(p) == os.path.abspath(path):
            continue
        text, rel = read(p), os.path.relpath(p, ROOT)
        h, ts = others.get(rel), tasks(text)
        line = LINE_RE.search(text)
        goal = section(text, "Goal")
        files, ids, epics = set(), set(), collections.Counter()
        for _n, (mark, _t, a, z) in ts.items():
            if mark == "-":
                continue
            block = text[a:z]
            epics[epic_of(block) or "no epic"] += 1
            for m in re.finditer(r"^- \*\*(?:Where|GDD)\*\*:(.*)$", block, re.M):
                files.update(re.findall(r"[\w./-]+\.[a-z][a-z0-9]{0,5}\b", m.group(1)))
                ids.update(re.findall(r"\b[A-Z]{2,}(?:\.[A-Z0-9_]+)+\b", m.group(1)))
        spec = section(text, "Spec")
        if spec:
            ids.update(re.findall(r"\b[A-Z]{2,}(?:\.[A-Z0-9_]+)+\b", text[spec[0]:spec[1]]))
        print(f"C{cycle_no(p)} {os.path.basename(p)[3:-3]} — stage {stage_of(text)} · "
              + (f"another session works on it (since {h['at']})" if h else "no session works on it")
              + (" · building now" if b and h and b["pid"] == int(h["pid"]) else ""))
        print(f"  goal: {(line.group(1).strip() if line and line.group(1).strip() else ' '.join(text[goal[0]:goal[1]].split()) if goal else '')[:300]}")
        if epics:
            print("  epics: " + " · ".join(f"{e} ({n})" for e, n in epics.most_common()))
        if files:
            print("  files: " + " · ".join(sorted(files)[:40]))
        if ids:
            print("  GDD: " + " · ".join(sorted(ids)[:40]))
        if slots(text):
            print("  asset slots: " + " · ".join(slots(text)))
        shown += 1
    if not shown:
        print("no other cycle is before Play")


def read(path):
    return open(path, encoding="utf-8").read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def section(text, title):
    """(start, end) of the `## <title>` section, under its English or its older Korean name. None if absent."""
    m = re.search(rf"^## (?:{re.escape(title)}|{re.escape(KO.get(title, title))})[ \t]*$", text, re.M)
    if not m:
        return None
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return m.end(), m.end() + nxt.start() if nxt else len(text)


def stage_of(text):
    m = STAGE_RE.search(text)
    return m.group(2).strip() if m else "?"


def tasks(text):
    """Task number → (state mark, title, block start, block end)."""
    found, hits = {}, list(TASK_RE.finditer(text))
    for m in hits:
        nxt = re.search(r"^##+ ", text[m.end():], re.M)
        found[m.group(2)] = (m.group(1), m.group(3).strip(), m.start(), m.end() + nxt.start() if nxt else len(text))
    return found


def decisions(text):
    return {m.group(2): (m.group(1), m.group(0)) for m in DECISION_RE.finditer(text)}


def todos(text):
    """U number → (state mark, the whole line, the file it waits for)."""
    out = {}
    for m in TODO_RE.finditer(text):
        wait = WAIT_RE.search(m.group(3))
        out[m.group(2)] = (m.group(1), m.group(0), wait.group(1) if wait else "")
    return out


def slots(text):
    """The rows of the "Assets needed" table: name → (Have cell, the row as written)."""
    out, head = {}, NEEDS_RE.search(text)
    if not head:
        return out
    end = re.search(r"^##+ ", text[head.end():], re.M)
    for row in text[head.end():head.end() + end.start() if end else len(text)].split("\n"):
        cells = [c.strip() for c in row.strip().strip("|").split("|")] if row.startswith("|") else []
        name = cells[0].split(" — ")[0].strip("` ") if cells else ""
        if len(cells) >= 4 and re.fullmatch(r"[a-z][a-z0-9_]*", name) and cells[1].strip("—–- "):
            out[name] = (cells[3], row)
    return out


def leftovers():
    """What earlier work left that no cycle holds any more: playtest tasks still open, asset slots still empty (as the newest document listing them says)."""
    d = os.path.join(ROOT, PLAYTESTS)
    tests = [(n, m.group(1), m.group(2), m.group(3).strip()) for n in (sorted(os.listdir(d)) if os.path.isdir(d) else []) if n.endswith(".md")
             for m in PLAYTEST_TASK.finditer(read(os.path.join(d, n)))]
    have = {}
    for p in docs():
        have.update(slots(read(p)))
    empty = [n for n, (cell, _row) in have.items() if HAVE_EMPTY.search(cell)]
    made = asset_files()
    return tests, [n for n in empty if n not in made], [n for n in empty if n in made]


def own_cfg():
    """This skill's section of kit.config.json — "check": "wave" where the engine runs one at a time in a project folder (the engine's config sets it)."""
    try:
        return json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get("cycle", {}) or {}
    except (OSError, ValueError):
        return {}


def board_cfg():
    try:
        return json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get("board", {}) or {}
    except (OSError, ValueError):
        return {}


def epic_names():
    """The epics a task can belong to: the stages of play (board.flow), then Foundation."""
    cfg = board_cfg()
    return [f["name"] for f in cfg.get("flow") or [] if f.get("name")] + [cfg.get("foundation") or FOUNDATION]


def resolve_epic(said):
    """An epic by its name, or a part of it that names only one."""
    said, names = " ".join(said.split()), epic_names()
    hit = [n for n in names if n.casefold() == said.casefold()] or [n for n in names if said and said.casefold() in n.casefold()]
    if len(hit) != 1:
        sys.exit(f"{said!r}: " + ("names more than one epic" if hit else "no such epic") + " — " + " · ".join(names)
                 + ("" if board_cfg().get("flow") else "  (no stages of play yet: the board skill writes board.flow)"))
    return hit[0]


def epic_of(block):
    m = EPIC_RE.search(block)
    return m.group(1).strip() if m else ""


def doc_of(num):
    """The document of a cycle by its number."""
    hit = [p for p in docs() if int(os.path.basename(p).split("-")[0]) == int(num)]
    return hit[0] if hit else sys.exit(f"C{num}: no such cycle — " + " · ".join("C%d" % int(os.path.basename(p).split("-")[0]) for p in docs()))


def keyed(path, names):
    """Task names given as T3 (in the document picked) or C16-T3 (in cycle 16's) → (the document, [T3, …]). One document per call."""
    found, out = set(), []
    for n in names.split(","):
        m = KEY_RE.match(n.strip())
        found.add(doc_of(m.group(1)) if m else path)
        out.append(m.group(2) if m else n.strip())
    if len(found) > 1:
        sys.exit("tasks of one cycle per call")
    return found.pop(), ",".join(out)


def cycle_no(path):
    return int(os.path.basename(path).split("-")[0])


def asset_files():
    """Names of the files in the game's asset folder (the board's `assets`, without its work folder `gen`) — a slot whose file is there is made."""
    cfg = board_cfg()
    adir, gen = os.path.join(ROOT, cfg.get("assets", "assets")), os.path.abspath(os.path.join(ROOT, cfg.get("gen", "assets/_gen")))
    return {n.split(".")[0] for base, _dirs, names in os.walk(adir) if not os.path.abspath(base).startswith(gen) for n in names}


def waiting(block, ds):
    """The decisions in a task block's `Waiting: D2` that have no answer yet."""
    line = WAITING_RE.search(block)
    return [d for d in re.findall(r"D\d+", line.group(1)) if ds.get(d, (" ",))[0] not in "x~-"] if line else []


def carried(text):
    """The lines a session left for the next one that no session has picked up yet."""
    span = section(text, CARRY)
    return CARRY_RE.findall(text[span[0]:span[1]]) if span else []


def old_notes():
    """Notes in docs/handoff/ that no session resumed — so a game that left one before `carry` existed does not lose it."""
    d = os.path.join(ROOT, NOTES)
    names = sorted(n for n in os.listdir(d) if n.endswith(".md")) if os.path.isdir(d) else []
    return [os.path.join(NOTES, n) for n in names if not RESUMED_RE.search(read(os.path.join(d, n)))]


def waves(text):
    span = section(text, "Order")
    out = []
    for line in (text[span[0]:span[1]].split("\n") if span else []):
        m = WAVE_RE.match(line.strip())
        if m:
            out.append((int(m.group(1) or m.group(2)), re.findall(r"T\d+", m.group(3).split("—")[0])))
    return out


def summary(path):
    text = read(path)
    marks = [t[0] for t in tasks(text).values()]
    dmarks = [d[0] for d in decisions(text).values()]
    open_d, proxy = sum(1 for m in dmarks if m not in "x~-"), dmarks.count("~")
    left = len(carried(text))
    yours = sum(1 for t in todos(text).values() if t[0] == " ")
    skips = skipped(text)
    return (f"{os.path.relpath(path, ROOT)} — stage: {stage_of(text)} · tasks [x] {marks.count('x')} · [ ] {marks.count(' ')} · "
            + (f"[>] {marks.count('>')} · " if '>' in marks else "")
            + f"[!] {marks.count('!')} · open decisions {open_d}" + (f" · proxy decisions {proxy} (unconfirmed)" if proxy else "")
            + (f" · carried over {left}" if left else "") + (f" · for the user {yours}" if yours else "")
            + "".join(f" · {k} skipped" for k in skips))


def cmd_next(path, looked=False):
    text = read(path)
    ts, ds = tasks(text), decisions(text)
    print(summary(path))
    others = holders()
    if not looked and held_doc() != path and os.path.relpath(path, ROOT) not in others:
        take(path)  # (not one only looked at with --doc) the session that goes on with a free cycle works on it — a second session opened after it is then told, not let in beside it
    if others:
        print("other sessions work on: " + " · ".join(f"C{h['cycle']}" for h in others.values())
              + " — this session's commands act on its own cycle; the build turn is one session's at a time (`turn`)")
        with sessions() as s:
            b = s["build"]
        if b and b["pid"] != session():
            print(f"build turn: another session's ({b['what']}, since {b['at']}) — this cycle's waves wait for it")
    for line in carried(text):
        print(f"carried over: {line}")
    for note in old_notes():
        print(f"handoff note not resumed: {note} — read it, then append a line `Resumed: <date>` to it")
    for num, (mark, line) in ds.items():
        if mark == "~":
            print(f"proxy decision (unconfirmed): {line[6:]}")
        elif mark not in "x-":
            print(f"open decision: {line[6:]}")
    for num, (mark, line, wait) in todos(text).items():
        if mark == " ":
            there = wait and os.path.exists(os.path.join(ROOT, wait))
            print(f"for the user: {line[6:]}" + (f" — the file is there now: look at it, go on with what waited for it, then `did {num}`" if there else ""))
    for num, (mark, title, a, b) in ts.items():
        if mark == "!":
            print(f"blocked task: {num}. {title}")
        elif mark == ">":
            print(f"in progress: {num}. {title} — an agent was on it; if none is now, run it again")
    for n, names in waves(text):
        left = [t for t in names if t in ts and ts[t][0] in OPEN]
        if not left:
            continue
        print(f"next wave: {n}" + (" — checked as a wave: `build T<n> wave` for each (no engine run), then one `check` (the skill's \"Checked as a wave\")"
                                   if own_cfg().get("check") == "wave" else ""))
        for t in left:
            hold = waiting(text[ts[t][2]:ts[t][3]], ds)
            epic = epic_of(text[ts[t][2]:ts[t][3]])
            print(f"  {t}. {ts[t][1]}" + (f" [{epic}]" if epic else "") + (f" — waiting on {' · '.join(hold)} (not run for now)" if hold else ""))
        break
    else:
        if ts and all(t[0] not in OPEN for t in ts.values()):
            print("no tasks left")
    unsaid = [n for n, (mark, _t, a, b) in ts.items() if mark in OPEN and not (WHAT_RE.search(text[a:b]) and CHANGE_RE.search(text[a:b]))]
    if unsaid:
        print(f"tasks with no plain \"What\" or \"Change\" line: {' · '.join(unsaid)} — call `plan` again for them before the build (the dashboard shows those two)")
    bare = [n for n, (mark, _t, a, b) in ts.items() if mark != "-" and not epic_of(text[a:b])]
    if bare:
        print(f"tasks with no epic: {' · '.join(bare)} — `epic {','.join(bare)} \"<epic>\"` (" + " · ".join(epic_names()) + ")")
    open_b = [b for b in backlog() if b[0] == " "]
    if open_b:
        print(f"backlog: {len(open_b)} waiting (`backlog`)")


def cmd_task(path, num):
    text = read(path)
    ts, ds = tasks(text), decisions(text)
    if num not in ts:
        sys.exit(f"{num}: no such task — " + " · ".join(ts))
    block = text[ts[num][2]:ts[num][3]].rstrip()
    print(f"{os.path.relpath(path, ROOT)} · C{cycle_no(path)}-{num} · stage: {stage_of(text)}\n\n{block}")
    refs = [d for d in dict.fromkeys(re.findall(r"D\d+", block)) if d in ds]
    if refs:
        print("\ndecisions it depends on:")
        for d in refs:
            print(ds[d][1])


DONE_MAX = 120  # what changed, read on the dashboard at a glance


def plain(line, most):
    """What keeps a line the user reads from reading at a glance — empty when it reads."""
    code = sorted(set(m.group(0) for m in CODE_WORDS.finditer(line)))
    return ((["code names, files or section numbers (" + " · ".join(code) + ")"] if code else [])
            + ([f"{len(line)} characters — one plain sentence, under {most}"] if len(line) > most else []))


def cmd_mark(path, names, state, note):
    if state == "done":
        if "," in names:
            sys.exit('one task per call, each with what changed: mark T1 done "<what changed, one plain line>"')
        if not note.strip():
            sys.exit('say what changed, for the user — one plain line: mark T1 done "<what the player meets now>" (the developer returns it as "Changed")')
        bad = plain(" ".join(note.split()), DONE_MAX)
        if bad:
            sys.exit("Not marked — the dashboard shows this as what changed, read by the user:\n- " + "\n- ".join(bad))
    if state == "doing" and not (wt_cfg() and os.path.isdir(wt_dir(cycle_no(path)))) and not turn(f"C{cycle_no(path)}", path):
        sys.exit(1)  # a build in its own folder (`worktree open`) needs no turn: the game's folder is not touched until it merges
    text = read(path)
    for num in names.split(","):
        ts = tasks(text)
        if num not in ts:
            sys.exit(f"{num}: no such task — " + " · ".join(ts))
        _mark, _title, a, b = ts[num]
        block = TASK_RE.sub(lambda m: f"### [{BOX[state]}] {m.group(2)}.{m.group(3)}", text[a:b], count=1)
        if note and state in NOTE:
            block = block.rstrip("\n") + f"\n- **{NOTE[state]}**: {note}\n\n"
        text = text[:a] + block + text[b:]
        print(f"{num}: [{BOX[state]}]")
    write(path, text)


def pictures(images):
    """`<label>=<path>` (or a bare path, labelled by its name) → [{label, path}], every file checked before anything is written."""
    pics = []
    for given in images:
        label, sep, rel = given.partition("=")
        rel = rel if sep else label
        label = label.strip() if sep else os.path.splitext(os.path.basename(rel))[0]
        if not os.path.isfile(os.path.join(ROOT, rel)):
            sys.exit(f"{rel}: no such file (paths are relative to the game root) — nothing was written")
        if rel.lower().endswith((".mp4", ".webm", ".m4v", ".mov")) and os.path.getsize(os.path.join(ROOT, rel)) > CLIP_MAX:
            sys.exit(f"{rel}: a clip over {CLIP_MAX // 2**20} MB does not reach the dashboard — cut it to the seconds that matter and shrink it "
                     "(ffmpeg -i in -t 10 -vf scale=960:-2 -c:v libx264 -crf 28 -an out.mp4). Nothing was written")
        if rel.lower().endswith(".ogg"):  # Safari — every iPhone — plays no Ogg: the card would stay silent on the phone it is read on
            sys.exit(f"{rel}: a phone's Safari plays no .ogg — give it as .mp3 or .m4a (ffmpeg -i in.ogg -b:a 128k out.mp3). Nothing was written")
        if rel.lower().endswith(SOUNDS) and os.path.getsize(os.path.join(ROOT, rel)) > CLIP_MAX:
            sys.exit(f"{rel}: a sound over {CLIP_MAX // 2**20} MB does not reach the dashboard — cut it to what is compared and give it as .mp3 "
                     "(ffmpeg -i in -t 20 -b:a 128k out.mp3). Nothing was written")
        pics.append({"label": label, "path": rel.replace(os.sep, "/")})
    return pics


def keep_pictures(path, num, question, pics):
    """Kept beside the sheets, where the board looks for a decision's pictures — by cycle and decision. Later pictures replace earlier ones."""
    cyc = int(re.match(r"\d+", os.path.basename(path)).group(0))
    out = os.path.join(ROOT, SHEETS, f"asks-{cyc:02d}.json")
    kept = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else []
    kept = [q for q in kept if q.get("id") != num] + [{"id": num, "cycle": cyc, "question": question, "images": pics}]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=1)


WHO_TAIL = re.compile(r"(?:\s*\((?:Spec|Design|Plan|Build|Play|Playtest|Asset|기획|디자인|계획|구현|플레이)\))+\s*$")


def clean(question, num=""):
    """The question as the line holds it: without a decision number in front ("D45. …", which the line writes itself) or a stage behind."""
    q = re.sub(r"^\s*(?:D\d+\.\s*)+", "", question.strip())
    return WHO_TAIL.sub("", q).strip()


ASK_MAX = 90  # characters of the question itself (before the options) — read on a phone, at a glance
CODE_WORDS = re.compile(
    r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b"                       # a constant's name — PICKUP_WINDOW
    r"|\b[a-z][a-z0-9]*_[a-z0-9_]+\b"                        # a variable's name — pickup_window
    r"|[\w-]+/[\w./-]*\.[A-Za-z]{1,5}\b"                     # a path — game/config/balance.gd
    r"|\b[\w-]+\.(?:gd|cs|js|ts|py|tscn|tres|json|md|xlsx|unity|prefab)\b"  # a file
    r"|\bGDD\s*§?\s*\d+(?:\.\d+)+|§\s*\d+")                     # a section of a document — GDD 4.6


def unreadable(question):
    """What keeps the user from reading the question at a glance — empty when it reads."""
    marks = [m for m in re.finditer(r"[①②③④⑤⑥⑦⑧⑨⑩]", question) if question[:m.start()].count("(") <= question[:m.start()].count(")")]
    head = question[:marks[0].start()] if marks else question
    head = re.sub(r"\s*—\s*$", "", head.strip())
    said = re.split(r" · (?:recommended|권함):", question)[0]
    out = []
    if len(marks) < 2:
        out.append("give two options or more, each marked ① ② … — a question with nothing to pick is not a decision (say it, or put it in the GDD)")
    if len(head) > ASK_MAX:
        out.append(f"the question is {len(head)} characters — keep it under {ASK_MAX}; the background goes in --why, numbers and names in --detail")
    code = sorted(set(m.group(0) for m in CODE_WORDS.finditer(said)))
    if code:
        out.append("code names, files or section numbers in it (" + " · ".join(code) + ") — say what the player meets instead, and put these in --detail")
    return out


def cmd_ask(path, who, question, images=(), why="", detail=""):
    question = clean(question)
    bad = unreadable(question)
    if bad:
        sys.exit("Not asked — the user reads it on a phone, in what the player meets:\n- " + "\n- ".join(bad))
    text = read(path)
    span = section(text, "Decisions") or sys.exit("the document has no `## Decisions` section")
    pics = pictures(images)
    num = "D%d" % (max([int(d[1:]) for d in decisions(text)] or [0]) + 1)
    body = text[span[0]:span[1]].rstrip("\n")
    under = "".join(f"\n  - {k}: {' '.join(v.split())}" for k, v in (("why", why), ("detail", detail)) if v.strip())
    write(path, text[:span[0]] + body + f"\n- [ ] {num}. {question.strip()} ({EN.get(who, who)}){under}\n\n" + text[span[1]:])
    if pics:
        keep_pictures(path, num, question.strip(), pics)
    print(num)


def cmd_reask(path, num, question, images=(), why="", detail=""):
    """Ask a decision again as a new one — when the user's answer was a question back, or the options changed. The old one is closed
    ([-] "asked again as D7"), the new one gets the next number and the same asker; its pictures come along unless new ones are given.
    On the dashboard the old card leaves and a new card comes — nothing of the old answer holds it."""
    text = read(path)
    ds = decisions(text)
    if num not in ds:
        sys.exit(f"{num}: no such decision — " + " · ".join(ds))
    mark, old = ds[num]
    if mark == "x":
        sys.exit(f"{num}: already answered — to change the answer, `decide {num}`; for another question, `ask`")
    bad = unreadable(clean(question))
    if bad:
        sys.exit("Not asked — the user reads it on a phone, in what the player meets:\n- " + "\n- ".join(bad))
    who = re.search(r"\((Spec|Design|Plan|Build|Play|Playtest|Asset|기획|디자인|계획|구현|플레이)\)", old)
    pics = pictures(images)
    new = "D%d" % (max(int(d[1:]) for d in ds) + 1)
    ask = PROXY_RE.match(old).group(1) if mark == "~" else old.split(" → ")[0]
    text = text.replace(old, f"- [-]{ask[5:]} → asked again as {new} ({datetime.date.today()})", 1)
    write(path, text)
    with contextlib.redirect_stdout(io.StringIO()):
        cmd_ask(path, EN.get(who.group(1), who.group(1)) if who else "Spec", question, why=why, detail=detail)
    if not pics:  # the pictures the old one was asked with
        cyc = int(re.match(r"\d+", os.path.basename(path)).group(0))
        kept = os.path.join(ROOT, SHEETS, f"asks-{cyc:02d}.json")
        was = next((q for q in (json.load(open(kept, encoding="utf-8")) if os.path.exists(kept) else []) if q.get("id") == num), None)
        pics = was["images"] if was else []
    if pics:
        keep_pictures(path, new, clean(question), pics)
    print(f"{num} → {new}: asked again as a new decision")


def cmd_attach(path, num, images):
    """Pictures for a decision already asked — when they were made after it, or it was asked without them."""
    text = read(path)
    ds = dict(decisions(text), **{u: (m, line) for u, (m, line, _w) in todos(text).items()})  # a to-do's pictures go the same way
    if num not in ds:
        sys.exit(f"{num}: no such decision — " + " · ".join(ds))
    if not images:
        sys.exit('give the pictures: attach D3 --image "<label>=<path>" …')
    pics = pictures(images)
    keep_pictures(path, num, ds[num][1][6:].split(" — ")[0].strip(), pics)
    print(f"{num}: {len(pics)} picture(s) — shown with it on the board and the dashboard")


def cmd_todo(path, what, wait="", images=(), why="", detail=""):
    """Something only the user can do outside the chat. Kept in the document's "For you" section — the session after this one sees it with `next`."""
    what = " ".join(what.split())
    if not what:
        sys.exit("say what the user does, in a line")
    if wait and (os.path.isabs(wait) or wait.startswith("..")):
        sys.exit(f"{wait}: the file it waits for is given from the game root")
    text = read(path)
    pics = pictures(images)
    num = "U%d" % (max([int(u[1:]) for u in todos(text)] or [0]) + 1)
    span = section(text, TODO)
    if not span:  # older documents have no such section — it goes right after the decisions
        at = section(text, "Decisions")
        cut = at[1] if at else len(text)
        text = text[:cut].rstrip("\n") + f"\n\n## {TODO}\n\n" + text[cut:].lstrip("\n")
        span = section(text, TODO)
    body = text[span[0]:span[1]].rstrip("\n")
    under = "".join(f"\n  - {k}: {' '.join(v.split())}" for k, v in (("why", why), ("detail", detail)) if v.strip())
    line = f"- [ ] {num}. {what}" + (f" — wait: `{wait.replace(os.sep, '/')}`" if wait else "")
    write(path, text[:span[0]] + body + f"\n{line}{under}\n\n" + text[span[1]:].lstrip("\n"))
    if pics:
        keep_pictures(path, num, what, pics)
    print(num + (f" — closes by itself once {wait} is there" if wait else ""))


def cmd_did(path, names, said=""):
    text = read(path)
    us = todos(text)
    for num in names.split(","):
        if num not in us:
            sys.exit(f"{num}: no such to-do — " + (" · ".join(us) or "none in this document"))
        mark, old, _wait = us[num]
        if mark == " ":
            text = text.replace(old, old.replace("- [ ]", "- [x]", 1) + f" → done{': ' + ' '.join(said.split()) if said.strip() else ''} ({datetime.date.today()})", 1)
    write(path, text)
    print(f"done: {names.replace(',', ' · ')}")


def cmd_have(path, name, value):
    """The "Have" cell of an asset slot, in the newest document that lists it (the board reads a slot's state from the newest)."""
    value = " ".join(value.split()).replace("|", "/")
    for p in reversed(docs()):
        text = read(p)
        got = slots(text)
        if name in got:
            row = got[name][1]
            cells = row.strip().strip("|").split("|")
            cells[3] = f" {value} "
            write(p, text.replace(row, "|" + "|".join(cells) + "|", 1))
            return print(f"{name}: {value} — {os.path.relpath(p, ROOT)}")
    sys.exit(f"{name}: no asset slot of that name in any cycle document")


def cmd_decide(path, num, answer):
    """The user's answer is [x]. A decision made in their place by the auto mode of older kits ([~]) is overturned the same way."""
    text = read(path)
    ds = decisions(text)
    if num not in ds:
        sys.exit(f"{num}: no such decision — " + " · ".join(ds))
    mark, old = ds[num]
    ask = PROXY_RE.match(old).group(1) if mark == "~" else old
    write(path, text.replace(old, f"- [x]{ask[5:]} → {answer.strip()} ({datetime.date.today()})", 1))
    print(f"{num}: answer recorded")


def cmd_confirm(path, names):
    text = read(path)
    ds = decisions(text)
    picked = [n for n, d in ds.items() if d[0] == "~"] if names == "all" else names.split(",")
    for num in picked:
        if num not in ds or ds[num][0] != "~":
            sys.exit(f"{num}: not a proxy decision awaiting confirmation")
        ask, pick, basis = PROXY_RE.match(ds[num][1]).groups()
        text = text.replace(ds[num][1], f"- [x]{ask[5:]} → {pick} — accepted proxy ({basis}) ({datetime.date.today()})", 1)
    write(path, text)
    print(f"accepted: {' · '.join(picked)}" if picked else "no proxy decisions awaiting confirmation")


def cmd_drop(path, names, why):
    """A decision the user no longer needs — withdrawn, not answered. The question stays in the document, struck as [-] with their reason."""
    text = read(path)
    ds = decisions(text)
    for num in [n for n in names.split(",") if n.startswith("U")]:  # a to-do the user will not do
        us = todos(text)
        if num not in us:
            sys.exit(f"{num}: no such to-do — " + (" · ".join(us) or "none in this document"))
        if us[num][0] == " ":
            text = text.replace(us[num][1], us[num][1].replace("- [ ]", "- [-]", 1) + f" → not needed: {' '.join(why.split())} ({datetime.date.today()})", 1)
    for num in [n for n in names.split(",") if not n.startswith("U")]:
        if num not in ds:
            sys.exit(f"{num}: no such decision — " + " · ".join(ds))
        mark, old = ds[num]
        if mark == "x":
            sys.exit(f"{num}: already answered — to change the answer, `decide {num}`")
        if mark == "-":
            continue
        ask = PROXY_RE.match(old).group(1) if mark == "~" else old
        text = text.replace(old, f"- [-]{ask[5:]} → not needed: {' '.join(why.split())} ({datetime.date.today()})", 1)
    write(path, text)
    print(f"not needed: {' · '.join(names.split(','))}")


def check_lines(text):
    """What to check by playing — the bullets under the spec's "To see by playing" and the design's "For a human to see" (as the board reads them)."""
    out = []
    for m in CHECK_HEADS.finditer(text):
        nxt = re.search(r"^#{1,3} ", text[m.end():], re.M)
        lines = [x.strip() for x in text[m.end():m.end() + nxt.start() if nxt else len(text)].split("\n") if x.strip() and not x.strip().startswith(("<!--", "|", "- Checked (", "- Not played:", "- Next:"))]
        bullets = [re.sub(r"^(?:[-*]|\d+[.)])\s+", "", x) for x in lines if re.match(r"^(?:[-*]|\d+[.)])\s+", x)]
        out += bullets or lines
    return out


def unchecked(text):
    done = {" ".join(c.split()) for _r, c in CHECKED_RE.findall(text)}
    return [c for c in check_lines(text) if " ".join(c.split()) not in done]


CHECK_MAX = 90  # a check is a question read on a phone while playing — like a decision's


def check_unreadable(line):
    """What keeps a check by playing from being read at a glance — empty when it reads. The tuning hint behind it goes in "Tuning notes"."""
    out = []
    code = sorted(set(m.group(0) for m in CODE_WORDS.finditer(line)) | set(re.findall(r"\(\d+(?:\.\d+)+[^)]*\)|\bD\d+\b", line)))
    if code:
        out.append("names from the code or the documents (" + " · ".join(code) + ")")
    if len(line) > CHECK_MAX:
        out.append(f"{len(line)} characters — one short question, under {CHECK_MAX}")
    return out


def report_checks(text):
    """Said as the cycle reaches Play: the checks the user would not understand, to be rewritten before they are asked to play."""
    bad = [(c, check_unreadable(c)) for c in check_lines(text)]
    bad = [(c, why) for c, why in bad if why]
    if bad:
        print(f"{len(bad)} check(s) by playing do not read at a glance — rewrite each as one plain question about what the player meets, "
              "and move the numbers, names and what to move in the table to \"### Tuning notes\" (the card does not show it), before telling the user what to play:")
        for c, why in bad:
            print(f"  {c[:100]}{'…' if len(c) > 100 else ''}\n    ↳ {' · '.join(why)}")


def cmd_checks(path):
    text = read(path)
    lines = check_lines(text)
    report_checks(text)
    if lines and not any(check_unreadable(c) for c in lines):
        print(f"{len(lines)} check(s) by playing, all read at a glance")
    elif not lines:
        print("no checks by playing in this cycle")


def cmd_checked(path, line, result, seen=""):
    if result not in ("ok", "problem"):
        sys.exit("the result is ok or problem")
    text = read(path)
    line = " ".join(line.split())
    lines = {" ".join(c.split()): c for c in check_lines(text)}
    hit = lines.get(line) or next((c for k, c in lines.items() if k.startswith(line)), None) if len(line) >= 12 or line in lines else None
    if not hit:
        sys.exit("not a check of this cycle — give it as the board lists it (the start is enough):\n  " + "\n  ".join(lines) if lines else "this cycle has no checks by playing")
    span = section(text, "Play") or sys.exit("the document has no `## Play` section")
    body = text[span[0]:span[1]].rstrip("\n")
    write(path, text[:span[0]] + body + f"\n- Checked ({result}): {' '.join(hit.split())}" + (f" — “{' '.join(seen.split())}”" if seen.strip() else "")
          + f" ({datetime.date.today()})\n\n" + text[span[1]:])
    print(f"checked ({result}): {hit[:80]}" + (" — the problem goes to the playtest skill with the others" if result == "problem" else ""))
    text = read(path)
    if (result == "ok" and OPEN_STAGE.match(stage_of(text)) and not unchecked(text) and "- Checked (problem)" not in text
            and not any(d[0] == " " for d in decisions(text).values())):  # a decision still open is work still coming for it
        print("every check answered ok — the cycle is done:")
        close(path)


def cmd_close(path):
    """The user has played the cycle and is done with it. Only a played build closes — one before Play is not in their hands yet."""
    stage = stage_of(read(path))
    if stage in CLOSED:
        return print(f"already closed: {os.path.relpath(path, ROOT)}")
    if not OPEN_STAGE.match(stage):
        sys.exit(f"{os.path.relpath(path, ROOT)} stands at {stage} — only a cycle at Play closes (its build is not in the user's hands yet)")
    close(path)
    print("what the user brings about it from now on is a new cycle's (`new`) or the backlog's (`later`)")



SKIP_RE = re.compile(r"^_Skipped: (.+)_$", re.M)


def skipped(text):
    """The sections a cycle chose not to run, with why: {Spec: "…", Design: "…"}."""
    out = {}
    for name in ("Spec", "Design"):
        span = section(text, name)
        got = SKIP_RE.search(text[span[0]:span[1]]) if span else None
        if got:
            out[name] = got.group(1)
    return out


def cmd_skip(path, name, why):
    name = EN.get(name, name)
    if name not in ("Spec", "Design"):
        sys.exit("only Spec or Design is skipped — Plan always runs (the developer plans from whatever there is)")
    why = " ".join(why.split())
    if not why:
        sys.exit('say why, in a line: skip Spec "only how the menu looks changes"')
    text = read(path)
    span = section(text, name) or sys.exit(f"the document has no `## {name}` section")
    if text[span[0]:span[1]].strip() and not SKIP_RE.search(text[span[0]:span[1]]):
        sys.exit(f"## {name} already has content — it ran; nothing to skip")
    write(path, text[:span[0]] + f"\n_Skipped: {why}_\n\n" + text[span[1]:].lstrip("\n"))
    print(f"{name}: skipped — {why}. If the developer comes back with questions for {name.lower()}, its agent is called after all")


def cmd_line(path, said):
    said = " ".join(said.split())
    if not said:
        sys.exit('the goal in one line: line "the bow alone — walk slow, roll away, drop them one by one"')
    if len(said) > 120:
        sys.exit(f"{len(said)} characters — one line is at most 120; the rest stays in the user's own words below it")
    text = read(path)
    span = section(text, "Goal") or sys.exit("the document has no `## Goal` section")
    body = LINE_RE.sub("", text[span[0]:span[1]], count=1).strip("\n")
    write(path, text[:span[0]] + f"\nIn one line: {said}\n" + (body + "\n" if body else "") + "\n" + text[span[1]:].lstrip("\n"))
    print(f"in one line: {said}")


def cmd_shot(path, stage, picture):
    stage = " ".join(stage.split())
    pic = os.path.relpath(os.path.realpath(picture), os.path.realpath(ROOT)) if os.path.isabs(picture) else os.path.normpath(picture)
    if not stage or "`" in stage:
        sys.exit("the stage of play by its name on the board")
    if not pic.lower().endswith(SHOT_EXT):
        sys.exit(f"{pic}: a picture (" + " · ".join(SHOT_EXT) + ")")
    if pic.startswith("..") or not os.path.isfile(os.path.join(ROOT, pic)):
        sys.exit(f"{pic}: no such picture in the game")
    text = read(path)
    span = section(text, "Play") or sys.exit("the document has no `## Play` section")
    body = text[span[0]:span[1]].rstrip("\n")
    line = f"- {stage} — `{pic}`"
    lines = body.split("\n")
    if SCREENS not in lines:
        body += f"\n\n{SCREENS}\n{line}"
    else:  # the list is the lines of screens right under the heading — whatever follows them (a later line, a check) stays
        at = lines.index(SCREENS) + 1
        end = at
        while end < len(lines) and SHOT_RE.fullmatch(lines[end]):
            end += 1
        kept = [x for x in lines[at:end] if SHOT_RE.fullmatch(x).group(1).casefold() != stage.casefold()]
        body = "\n".join(lines[:at] + kept + [line] + lines[end:])
    write(path, text[:span[0]] + body + "\n\n" + text[span[1]:].lstrip("\n"))
    print(f"screen of {stage}: {pic}")


def backlog():
    """The backlog's lines: (mark, B number, the rest of the line, the whole line)."""
    p = os.path.join(ROOT, BACKLOG)
    return [(m.group(1), m.group(2), m.group(3), m.group(0)) for m in BACKLOG_RE.finditer(read(p))] if os.path.exists(p) else []


def backlog_text(rest):
    """What was put off, without the epic, the card and where it came from."""
    return re.split(r" — epic: | \(board: | \(from | → ", rest)[0].strip()


def cmd_later(path, said, key="", epic=""):
    """Something put off goes in the backlog, where it stays until a cycle takes it or the user drops it."""
    said = " ".join(said.split())
    if not said:
        sys.exit("say what is put off, in the user's words")
    if key and not re.fullmatch(r"[\w.-]+", key):
        sys.exit(f"{key}: a review key, as `board.py answers` lists them")
    epic = resolve_epic(epic) if epic else ""
    p = os.path.join(ROOT, BACKLOG)
    text = read(p) if os.path.exists(p) else BACKLOG_HEAD
    num = "B%d" % (max([int(b[1][1:]) for b in backlog()] or [0]) + 1)
    line = (f"- [ ] {num}. {said}" + (f" — epic: {epic}" if epic else "") + (f" (board: {key})" if key else "")
            + f" (from Cycle {cycle_no(path):02d} · {datetime.date.today()})")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    write(p, text.rstrip("\n") + ("\n" if BACKLOG_RE.search(text) else "\n\n") + line + "\n")
    print(f"{num}: in the backlog" + (f" — the card {key} shows it waiting for a later cycle" if key else "")
          + ("" if epic else " — no epic yet (`backlog epic " + num + " \"<epic>\"`)"))


def cmd_backlog(path, rest):
    """backlog · backlog take B2,B5 · backlog drop B3 "<why>" · backlog epic B3 "<epic>"."""
    items = backlog()
    if not rest:
        open_b = [b for b in items if b[0] == " "]
        if not open_b:
            return print("the backlog is empty")
        by = {}
        for b in open_b:
            m = BL_EPIC.search(b[2])
            by.setdefault(m.group(1).strip() if m else "", []).append(b)
        for epic in [n for n in epic_names() if n in by] + [n for n in by if n not in epic_names()]:
            print(f"{epic or 'no epic yet'} — {len(by[epic])}")
            for b in by[epic]:
                print(f"  {b[1]}. {backlog_text(b[2])[:110]}")
        return
    verb, names = rest[0], rest[1] if len(rest) > 1 else ""
    if verb not in ("take", "drop", "epic") or not names or (verb != "take" and len(rest) < 3):
        sys.exit('backlog · backlog take B2,B5 · backlog drop B3 "<why>" · backlog epic B3 "<epic>"')
    have = {b[1]: b for b in items}
    p = os.path.join(ROOT, BACKLOG)
    text = read(p)
    epic = resolve_epic(rest[2]) if verb == "epic" else ""
    for num in names.split(","):
        if num not in have:
            sys.exit(f"{num}: not in the backlog — " + (" · ".join(have) or "it is empty"))
        mark, _n, line_rest, line = have[num]
        if verb == "epic":
            new = BL_EPIC.sub("", line)
            cut = re.search(r" \((?:board|from) ", new)
            at = cut.start() if cut else len(new)
            new = new[:at] + f" — epic: {epic}" + new[at:]
        elif mark != " ":
            sys.exit(f"{num}: no longer waiting — {line}")
        elif verb == "take":
            new = line.replace("- [ ]", "- [>]", 1) + f" → Cycle {cycle_no(path):02d} ({datetime.date.today()})"
        else:
            new = line.replace("- [ ]", "- [-]", 1) + f" → dropped: {' '.join(rest[2].split())} ({datetime.date.today()})"
        text = text.replace(line, new, 1)
        if verb == "take":
            print(f"{num} → Cycle {cycle_no(path):02d}: {backlog_text(line_rest)}")
    write(p, text)
    if verb != "take":
        print(f"{verb}: {names.replace(',', ' · ')}" + (f" → {epic}" if epic else ""))


def cmd_epic(path, names, said):
    epic = resolve_epic(said)
    path, names = keyed(path, names)
    text = read(path)
    for num in names.split(","):
        ts = tasks(text)
        if num not in ts:
            sys.exit(f"{num}: no such task — " + " · ".join(ts))
        a, b = ts[num][2], ts[num][3]
        block = text[a:b]
        if EPIC_RE.search(block):
            block = EPIC_RE.sub(f"- **Epic**: {epic}", block, count=1)
        else:
            cut = block.find("\n") + 1 or len(block)
            block = block[:cut] + ("" if cut <= len(block) and block[cut - 1:cut] == "\n" else "\n") + f"- **Epic**: {epic}\n" + block[cut:]
        text = text[:a] + block + text[b:]
    write(path, text)
    print(f"C{cycle_no(path)}-{names.replace(',', f' · C{cycle_no(path)}-')} → {epic}")


def cmd_epics():
    """Each epic: its tasks across every cycle and playtest, and what waits for it in the backlog."""
    names = epic_names()
    rows, bare = {n: {"x": 0, ">": 0, " ": 0, "!": 0} for n in names}, []
    found = [(f"C{cycle_no(p)}", p) for p in docs()]
    d = os.path.join(ROOT, PLAYTESTS)
    found += [(f"playtest {n[:-3]}", os.path.join(d, n)) for n in (sorted(os.listdir(d)) if os.path.isdir(d) else []) if n.endswith(".md")]
    for label, p in found:
        text = read(p)
        for num, (mark, _t, a, b) in tasks(text).items():
            if mark == "-":
                continue
            epic = epic_of(text[a:b])
            if epic:
                rows.setdefault(epic, {"x": 0, ">": 0, " ": 0, "!": 0})[mark if mark in "x> !" else " "] += 1
            elif mark != "x" or label.startswith("C"):
                bare.append(f"{label}-{num}" if label.startswith("C") else f"{label} {num}")
    waiting = {}
    for b in backlog():
        if b[0] == " ":
            m = BL_EPIC.search(b[2])
            waiting[m.group(1).strip() if m else ""] = waiting.get(m.group(1).strip() if m else "", 0) + 1
    for n, c in rows.items():
        total = sum(c.values())
        print(f"{n} — tasks {c['x']}/{total} done" + "".join(f" · {k} {c[m]}" for k, m in (("in hand", ">"), ("open", " "), ("blocked", "!")) if c[m])
              + (f" · backlog {waiting[n]}" if waiting.get(n) else "") + ("" if n in names else "  (to sort — `epic <task> \"<epic>\"`)" if n == (board_cfg().get("common") or "Unsorted")
                 else "  (not an epic now — `epic <task> \"<epic>\"`)"))
    if waiting.get(""):
        print(f"backlog with no epic: {waiting['']} (`backlog`)")
    if bare:
        print(f"tasks with no epic: {len(bare)} — " + " · ".join(bare[:30]) + (" …" if len(bare) > 30 else ""))


def cmd_carry(path, said):
    """What is in hand but not in the document — work outside the tasks — is left as lines the next session's `next` shows."""
    text = read(path)
    span = section(text, CARRY)
    if said == "done":
        if span:
            write(path, text[:span[0]] + text[span[0]:span[1]].replace("- [ ] ", "- [x] ") + text[span[1]:])
        return print(f"picked up: {len(carried(text))}")
    if not span:
        text = text.rstrip("\n") + f"\n\n## {CARRY}\n"
        span = section(text, CARRY)
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rel = os.path.relpath(path, ROOT)
    dirty = [l for l in git("status", "--porcelain").split("\n") if l.strip() and not l[3:].strip().strip('"').endswith(rel)]  # the line it is about to add is not "uncommitted work"
    body, rest = text[span[0]:span[1]].rstrip("\n"), text[span[1]:]
    stamp = f"{datetime.date.today()} · commit {git('rev-parse', '--short', 'HEAD') or 'none'}"
    write(path, text[:span[0]] + body + f"\n- [ ] {' '.join(said.split())} ({stamp})\n" + ("\n" + rest if rest else ""))
    print("carried over")
    if dirty:
        print("there are uncommitted changes")


def close(path):
    """Closes the previous cycle — there is no closing stage. A document standing at Play becomes `Closed` when the next cycle is made."""
    text = read(path)
    rel, stage = os.path.relpath(path, ROOT), stage_of(text)
    if OPEN_STAGE.match(stage):
        write(path, STAGE_RE.sub(lambda m: m.group(1) + "Closed", text, count=1))
        print(f"closed: {rel}")
    elif stage not in CLOSED:
        print(f"the previous cycle is still at stage {stage}: {rel}")
    marks, ds = [t[0] for t in tasks(text).values()], [d[0] for d in decisions(text).values()]
    left = [f"{label} {n}" for label, n in (("[ ]", marks.count(" ")), ("[!]", marks.count("!")),
                                            ("open decisions", sum(1 for m in ds if m not in "x~-")), ("proxy decisions", ds.count("~"))) if n]
    if left:
        print("left in the previous cycle: " + " · ".join(left))
    for said in LATER_RE.findall(text):  # put off in the document itself, by kits before the backlog
        print(f"deferred: {said}")
    for line in carried(text):
        print(f"carried over, not picked up: {line}")
    for num, (mark, line, _wait) in todos(text).items():
        if mark == " ":
            print(f"for the user, not done: {line[6:]}")
    never = unchecked(text)
    if never:  # said in the document too, so the board keeps the cycle "not played" until they are answered — a cycle closed before this stays as it was
        text = read(path)
        span = section(text, "Play")
        if span and not re.search(r"^- Not played:", text, re.M):
            write(path, text[:span[0]] + text[span[0]:span[1]].rstrip("\n") + f"\n- Not played: {len(never)} check(s) never answered ({datetime.date.today()})\n\n" + text[span[1]:])
        print(f"checks by playing never answered: {len(never)} — the board counts this cycle as not played until they are (`checked \"…\" ok --doc {rel}`):")
        for c in never:
            print(f"  {c[:110]}")


def report_leftovers():
    """Printed as a cycle starts — what earlier work left, so the new goal is set with it in view, not without it."""
    tests, empty, unwritten = leftovers()
    if tests:
        print(f"playtest tasks still open: {len(tests)} — each goes into this goal, stays for later, or is dropped with its reason "
              "(playtest skill: `mark T4 dropped \"<why>\"`):")
        for n, mark, num, title in tests:
            print(f"  [{mark}] {n[:-3]} {num}. {title[:110]}")
    if empty:
        print(f"asset slots still empty: {len(empty)} — each is made in this cycle, kept on its placeholder "
              "(`have <slot> \"placeholder (kept — Dn)\"`), or dropped (`have <slot> \"dropped — <why>\"`): " + " · ".join(empty))
    if unwritten:
        print(f"asset slots with their file in the game but \"Have\" still empty: {len(unwritten)} — write each with `have <slot> \"<path>\"`: " + " · ".join(unwritten))
    waiting = [b for b in backlog() if b[0] == " "]
    if waiting:
        print(f"backlog: {len(waiting)} waiting — what goes into this goal is taken (`backlog take B2`), what is not needed dropped (`backlog drop B3 \"<why>\"`), the rest stays:")
        for _m, num, rest, _line in waiting:
            epic = BL_EPIC.search(rest)
            print(f"  {num}. {backlog_text(rest)[:110]}" + (f" [{epic.group(1).strip()}]" if epic else ""))


def cmd_new(name, goal):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        sys.exit(f"the name is lowercase letters · digits · hyphens: {name!r}")
    before = docs()
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = git("status", "--porcelain")  # before this writes anything — its own new document is not "uncommitted work"
    num = max([int(os.path.basename(p).split("-")[0]) for p in docs()] or [0]) + 1
    path = os.path.join(ROOT, DIR, f"{num:02d}-{name}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write(path, TEMPLATE.format(num=f"{num:02d}", name=name, date=datetime.date.today(),
                                commit=git("rev-parse", "--short", "HEAD") or "none", goal=goal.strip()))
    print(os.path.relpath(path, ROOT))
    others = holders()
    take(path)
    if before and os.path.relpath(before[-1], ROOT) in others:
        print(f"the previous cycle is another session's, left open: {os.path.relpath(before[-1], ROOT)}")
    elif before and os.environ.get("KIT_WORKER") and OPEN_STAGE.match(stage_of(read(before[-1]))):  # with the CEO, cycles run side by side — the user says when one is done
        print(f"the previous cycle is left open: {os.path.relpath(before[-1], ROOT)} — the user says when it is done (the CEO asks)")
    elif before:
        close(before[-1])
    report_leftovers()
    play = board_cfg().get("play")
    routed = isinstance(play, dict) and play.get("run") and play.get("route")
    queued = os.path.exists(os.path.join(ROOT, BACKLOG)) and "make the play route" in read(os.path.join(ROOT, BACKLOG)).lower()
    if not routed and not queued:
        print("no play route yet — the screens of the game are shot along it at the end of every build: "
              "`later \"Make the play route\" --epic Foundation`, then `backlog take` it into this cycle (the board skill's \"Play route\")")
    alongside = [p for p in building_docs() if p != path and os.path.relpath(p, ROOT) in others]  # one at Play is built — nothing to weigh
    if alongside:
        print("open alongside it, in other sessions: " + " · ".join(f"C{cycle_no(p)} (stage {stage_of(read(p))})" for p in alongside)
              + " — before Spec, call the systems designer with `fit`: it weighs this goal against them (`open` lists what they touch)")
    if dirty:
        print("there are uncommitted changes")


def main():
    args = sys.argv[1:]
    opts, images = {}, []
    for flag in ("--root", "--doc", "--key", "--why", "--detail", "--wait", "--epic"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    force = "--force" in args
    if force:
        args.remove("--force")
    while "--image" in args:
        i = args.index("--image")
        if i + 1 >= len(args):
            sys.exit(__doc__)
        images.append(args[i + 1])
        del args[i:i + 2]
    cmd, rest = (args[0] if args else ""), args[1:]
    if images and cmd not in ("ask", "attach", "reask", "todo"):
        sys.exit("--image goes with ask, attach, reask or todo")
    if ("--why" in opts or "--detail" in opts) and cmd not in ("ask", "reask", "todo"):
        sys.exit("--why and --detail go with ask, reask or todo")
    if "--wait" in opts and cmd != "todo":
        sys.exit("--wait goes with todo")
    if "--epic" in opts and cmd != "later":
        sys.exit("--epic goes with later")
    need = {"new": 2, "status": 0, "next": 0, "task": 1, "mark": (2, 3), "ask": 2, "attach": 1, "reask": 2, "decide": 2, "confirm": 1, "drop": 2, "stage": 1, "later": 1, "carry": 1, "todo": 1, "did": (1, 2), "have": 2, "checked": (2, 3), "checks": 0, "skip": 2, "line": 1, "shot": 2, "epic": 2, "epics": 0, "backlog": (0, 1, 2, 3),
            "take": 1, "leave": 0, "turn": (0, 1, 2), "open": 0, "commit": (1, 2), "worktree": (1, 2), "close": 0}
    if cmd not in need or len(rest) not in (need[cmd] if isinstance(need[cmd], tuple) else (need[cmd],)):
        sys.exit(__doc__)
    if force and cmd != "take":
        sys.exit("--force goes with take")
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    if cmd == "new":
        return cmd_new(*rest)
    if cmd == "status":
        others = holders()
        mine = held_doc() if others else None  # who works where is said only while several sessions do
        return print("\n".join(summary(p) + (" · this session" if p == mine else " · another session" if os.path.relpath(p, ROOT) in others else "")
                               for p in docs()) or f"no cycle document in {DIR}/")
    if cmd == "epics":
        return cmd_epics()
    if cmd == "take":
        said = rest[0]
        return take(pick(said) if not re.fullmatch(r"[Cc]?\d+", said) else doc_of(said.lstrip("Cc")), force)
    if cmd == "leave":
        with sessions() as s:
            h = s["held"].pop(str(session()), None)
        return print(f"this session no longer works on C{h['cycle']}" if h else "this session held no cycle")
    if cmd == "turn":
        return cmd_turn(rest)
    if cmd in ("task", "mark") and KEY_RE.match(rest[0].split(",")[0]) and "--doc" not in opts:
        path, rest[0] = keyed(None, rest[0])
    else:
        path = pick(opts.get("--doc"))
        if cmd in ("task", "mark") and KEY_RE.match(rest[0].split(",")[0]):
            path, rest[0] = keyed(path, rest[0])
    if cmd == "open":
        return cmd_open(path)
    if cmd == "worktree":
        if rest[0] not in ("open", "merge", "drop"):
            sys.exit("worktree open · worktree merge · worktree drop \"<why>\"")
        return cmd_worktree(path, *rest)
    if cmd == "commit":
        if rest[0] not in ("build", "playtest", "fix") or (rest[0] != "build") != (len(rest) == 2):
            sys.exit('commit build · commit playtest <document> · commit fix "<what, in a line>"')
        return cmd_commit(path, *rest)
    if cmd == "next":
        cmd_next(path, "--doc" in opts)
    elif cmd == "task":
        cmd_task(path, rest[0])
    elif cmd == "mark":
        if rest[1] not in BOX:
            sys.exit("the state is done · doing · blocked · open · dropped")
        if rest[1] == "dropped" and not (rest[2:] and rest[2].strip()):
            sys.exit("say why it is dropped: mark T4 dropped \"<why>\"")
        cmd_mark(path, rest[0], rest[1], rest[2] if len(rest) > 2 else "")
    elif cmd == "ask":
        cmd_ask(path, *rest, images, opts.get("--why", ""), opts.get("--detail", ""))
    elif cmd == "attach":
        cmd_attach(path, rest[0], images)
    elif cmd == "reask":
        cmd_reask(path, rest[0], rest[1], images, opts.get("--why", ""), opts.get("--detail", ""))
    elif cmd == "todo":
        cmd_todo(path, rest[0], opts.get("--wait", ""), images, opts.get("--why", ""), opts.get("--detail", ""))
    elif cmd == "did":
        cmd_did(path, *rest)
    elif cmd == "have":
        cmd_have(path, *rest)
    elif cmd == "checked":
        cmd_checked(path, *rest)
    elif cmd == "checks":
        cmd_checks(path)
    elif cmd == "close":
        cmd_close(path)
    elif cmd == "skip":
        cmd_skip(path, *rest)
    elif cmd == "decide":
        cmd_decide(path, *rest)
    elif cmd == "confirm":
        cmd_confirm(path, rest[0])
    elif cmd == "drop":
        cmd_drop(path, *rest)
    elif cmd == "line":
        cmd_line(path, rest[0])
    elif cmd == "shot":
        cmd_shot(path, *rest)
    elif cmd == "later":
        cmd_later(path, rest[0], opts.get("--key", ""), opts.get("--epic", ""))
    elif cmd == "backlog":
        cmd_backlog(path, rest)
    elif cmd == "epic":
        cmd_epic(path, *rest)
    elif cmd == "carry":
        cmd_carry(path, rest[0])
    else:
        text = read(path)
        if not STAGE_RE.search(text):
            sys.exit("the document head has no `Stage:`")
        stage = EN.get(rest[0], rest[0])
        write(path, STAGE_RE.sub(lambda m: m.group(1) + stage, text, count=1))
        print(f"stage: {stage}")
        if stage == "Play":
            with sessions() as s:  # the build is done, verification and screens with it — the next session's build may start
                if s["build"] and s["build"]["pid"] == session():
                    s["build"] = None
                    print("the build turn is free")
            report_checks(read(path))


if __name__ == "__main__":
    main()
