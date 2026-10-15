#!/usr/bin/env python3
"""Ledger for the cycle document (docs/cycle/NN-name.md) — pulls out and changes only the lines needed, without reading the whole document or editing it by hand.

  python3 cycle.py new <short-name> "<goal — in the user's own words>"   New document. Numbered after the last one. A previous cycle standing at Play becomes `Closed`, and what is left · deferred there is reported
  python3 cycle.py status                       Per document: stage · task counts · open decisions
  python3 cycle.py next                         Current stage, open decisions, the tasks of the next wave to run
  python3 cycle.py task T3                      One task and only the decisions it depends on (what the developer agent reads)
  python3 cycle.py mark T1,T3 done              [x]. `blocked` is [!], `open` is [ ]
  python3 cycle.py mark T2 blocked "<reason>"   One `- **Blocked**:` line under the task. Text after done goes in `- **Done**:`
  python3 cycle.py ask <stage> "<question — ① … ② … · recommended: ①>"   Adds a decision and prints its number (D4). Any stage: Spec · Design · Plan · Build · Play, or Playtest · Asset
  python3 cycle.py decide D2 "<the user's answer, as said>"
  python3 cycle.py decide D2 "②" --proxy V3     Auto mode — decided in the user's place. Written as [~] (basis: the voice's principle number, or `recommended` if none)
  python3 cycle.py confirm D2,D5                The user accepted the proxy decisions — they become [x]. `confirm all` for all of them. To overturn: `decide D2 "<the user's answer>"`
  python3 cycle.py drop D4,D12 "<why, as said>"   The user says the decision is not needed any more — [-]. Nothing waits on it; it is no longer asked
  python3 cycle.py stage <stage>                Changes `Stage:` in the head (Goal · Spec · Design · Plan · Build · Play)
  python3 cycle.py later "<in the user's own words>"   One `- Next:` line in the "Play" section for something deferred. `new` shows it when the next cycle is made
  python3 cycle.py carry "<what the next session must know>"   One `- [ ]` line in the "Carried over" section, for work in hand that the document does not hold. `next` shows it
  python3 cycle.py carry done                   The lines were picked up — they become [x], so the session after does not pick them up again
  python3 cycle.py lesson "<what tripped us → how to avoid it>"   One line in docs/kit-feedback.md for a lesson that is not this game's alone (to send up to the kit)

The document is the newest one (highest number). For another, `--doc <path>`.
Documents are written in English. Ones written before that use Korean words — both are read, and a stage or section given in Korean is taken too.
"""
import datetime
import json
import os
import re
import subprocess
import sys

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "cycle")
NOTES = os.path.join("docs", "handoff")  # notes of the skill that carried work across sessions before `carry` did
FEEDBACK = os.path.join("docs", "kit-feedback.md")
FEEDBACK_HEAD = """# For the kit

What making this game taught that is **not this game's alone** — a trap the next game on the same engine would also fall into, a way of checking that works, something the kit's tools lack.
One line is added at the spot where we tripped (`cycle.py lesson` · `playtest.py lesson`). `/gamedev-kit:feedback` sends them to the kit repository as issues — a line that was sent becomes `[>]`, one we chose not to send becomes `[-]`.

"""
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
BOX = {"done": "x", "blocked": "!", "open": " "}
NOTE = {"done": "Done", "blocked": "Blocked"}
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
PROXY_RE = re.compile(r"^(.*) → (.*?) · (?:proxy|대리) (.*?) \(\d{4}-\d\d-\d\d\)$")
TASK_RE = re.compile(r"^### \[(.)\] (T\d+)\.(.*)$", re.M)
DECISION_RE = re.compile(r"^- \[(.)\] (D\d+)\.(.*)$", re.M)

ROOT = ""


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


def docs():
    d = os.path.join(ROOT, DIR)
    return sorted(os.path.join(d, n) for n in os.listdir(d) if re.match(r"\d+-.*\.md$", n)) if os.path.isdir(d) else []


def pick(path):
    if path:
        path = path if os.path.isabs(path) else os.path.join(ROOT, path)
        if not os.path.exists(path):
            sys.exit(f"{path}: no such document")
        return path
    if not docs():
        sys.exit(f"no cycle document in {DIR}/ — cycle.py new <short-name> \"<goal>\"")
    return docs()[-1]


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
    return (f"{os.path.relpath(path, ROOT)} — stage: {stage_of(text)} · tasks [x] {marks.count('x')} · [ ] {marks.count(' ')} · "
            f"[!] {marks.count('!')} · open decisions {open_d}" + (f" · proxy decisions {proxy} (unconfirmed)" if proxy else "")
            + (f" · carried over {left}" if left else ""))


def cmd_next(path):
    text = read(path)
    ts, ds = tasks(text), decisions(text)
    print(summary(path))
    for line in carried(text):
        print(f"carried over: {line}")
    for note in old_notes():
        print(f"handoff note not resumed: {note} — read it, then append a line `Resumed: <date>` to it")
    for num, (mark, line) in ds.items():
        if mark == "~":
            print(f"proxy decision (unconfirmed): {line[6:]}")
        elif mark not in "x-":
            print(f"open decision: {line[6:]}")
    for num, (mark, title, a, b) in ts.items():
        if mark == "!":
            print(f"blocked task: {num}. {title}")
    for n, names in waves(text):
        left = [t for t in names if t in ts and ts[t][0] == " "]
        if not left:
            continue
        print(f"next wave: {n}")
        for t in left:
            hold = waiting(text[ts[t][2]:ts[t][3]], ds)
            print(f"  {t}. {ts[t][1]}" + (f" — waiting on {' · '.join(hold)} (not run for now)" if hold else ""))
        break
    else:
        if ts and all(t[0] != " " for t in ts.values()):
            print("no tasks left")


def cmd_task(path, num):
    text = read(path)
    ts, ds = tasks(text), decisions(text)
    if num not in ts:
        sys.exit(f"{num}: no such task — " + " · ".join(ts))
    block = text[ts[num][2]:ts[num][3]].rstrip()
    print(f"{os.path.relpath(path, ROOT)} · stage: {stage_of(text)}\n\n{block}")
    refs = [d for d in dict.fromkeys(re.findall(r"D\d+", block)) if d in ds]
    if refs:
        print("\ndecisions it depends on:")
        for d in refs:
            print(ds[d][1])


def cmd_mark(path, names, state, note):
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


def cmd_ask(path, who, question):
    text = read(path)
    span = section(text, "Decisions") or sys.exit("the document has no `## Decisions` section")
    num = "D%d" % (max([int(d[1:]) for d in decisions(text)] or [0]) + 1)
    body = text[span[0]:span[1]].rstrip("\n")
    write(path, text[:span[0]] + body + f"\n- [ ] {num}. {question.strip()} ({EN.get(who, who)})\n\n" + text[span[1]:])
    print(num)


def cmd_decide(path, num, answer, proxy):
    """The user's answer is [x]. What auto mode decided in their place is [~] — unconfirmed until the user accepts (confirm) or overturns (decide) it."""
    text = read(path)
    ds = decisions(text)
    if num not in ds:
        sys.exit(f"{num}: no such decision — " + " · ".join(ds))
    mark, old = ds[num]
    if proxy and mark == "x":
        sys.exit(f"{num}: the user already answered — not decided in their place")
    ask = PROXY_RE.match(old).group(1) if mark == "~" else old
    tail = f" · proxy {proxy}" if proxy else ""
    write(path, text.replace(old, f"- [{'~' if proxy else 'x'}]{ask[5:]} → {answer.strip()}{tail} ({datetime.date.today()})", 1))
    print(f"{num}: " + ("decided in the user's place (unconfirmed)" if proxy else "answer recorded"))


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
    for num in names.split(","):
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


def cmd_lesson(path, text):
    engine = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get("engine", "?")
    num = re.match(r"\d+", os.path.basename(path))
    out = os.path.join(ROOT, FEEDBACK)
    old = read(out) if os.path.exists(out) else FEEDBACK_HEAD
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write(out, old.rstrip("\n") + f"\n- [ ] ({engine} · cycle {num.group(0) if num else '?'} · {datetime.date.today()}) {' '.join(text.split())}\n")
    print(f"added to {FEEDBACK}")


def cmd_later(path, said):
    text = read(path)
    span = section(text, "Play") or sys.exit("the document has no `## Play` section")
    body = text[span[0]:span[1]].rstrip("\n")
    write(path, text[:span[0]] + body + f"\n- Next: {' '.join(said.split())}\n\n" + text[span[1]:])
    print("deferred")


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
    body, rest = text[span[0]:span[1]].rstrip("\n"), text[span[1]:]
    stamp = f"{datetime.date.today()} · commit {git('rev-parse', '--short', 'HEAD') or 'none'}"
    write(path, text[:span[0]] + body + f"\n- [ ] {' '.join(said.split())} ({stamp})\n" + ("\n" + rest if rest else ""))
    print("carried over")
    if git("status", "--porcelain"):
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
    for said in LATER_RE.findall(text):
        print(f"deferred: {said}")
    for line in carried(text):
        print(f"carried over, not picked up: {line}")


def cmd_new(name, goal):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        sys.exit(f"the name is lowercase letters · digits · hyphens: {name!r}")
    before = docs()
    num = max([int(os.path.basename(p).split("-")[0]) for p in docs()] or [0]) + 1
    path = os.path.join(ROOT, DIR, f"{num:02d}-{name}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    write(path, TEMPLATE.format(num=f"{num:02d}", name=name, date=datetime.date.today(),
                                commit=git("rev-parse", "--short", "HEAD") or "none", goal=goal.strip()))
    print(os.path.relpath(path, ROOT))
    if before:
        close(before[-1])
    if git("status", "--porcelain"):
        print("there are uncommitted changes")


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--doc", "--proxy"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    cmd, rest = (args[0] if args else ""), args[1:]
    need = {"new": 2, "status": 0, "next": 0, "task": 1, "mark": (2, 3), "ask": 2, "decide": 2, "confirm": 1, "drop": 2, "stage": 1, "later": 1, "carry": 1, "lesson": 1}
    if cmd not in need or len(rest) not in (need[cmd] if isinstance(need[cmd], tuple) else (need[cmd],)):
        sys.exit(__doc__)
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    if cmd == "new":
        return cmd_new(*rest)
    if cmd == "status":
        return print("\n".join(summary(p) for p in docs()) or f"no cycle document in {DIR}/")
    path = pick(opts.get("--doc"))
    if cmd == "next":
        cmd_next(path)
    elif cmd == "task":
        cmd_task(path, rest[0])
    elif cmd == "mark":
        if rest[1] not in BOX:
            sys.exit("the state is done · blocked · open")
        cmd_mark(path, rest[0], rest[1], rest[2] if len(rest) > 2 else "")
    elif cmd == "ask":
        cmd_ask(path, *rest)
    elif cmd == "decide":
        cmd_decide(path, *rest, opts.get("--proxy", ""))
    elif cmd == "confirm":
        cmd_confirm(path, rest[0])
    elif cmd == "drop":
        cmd_drop(path, *rest)
    elif cmd == "later":
        cmd_later(path, rest[0])
    elif cmd == "carry":
        cmd_carry(path, rest[0])
    elif cmd == "lesson":
        cmd_lesson(path, rest[0])
    else:
        text = read(path)
        if not STAGE_RE.search(text):
            sys.exit("the document head has no `Stage:`")
        stage = EN.get(rest[0], rest[0])
        write(path, STAGE_RE.sub(lambda m: m.group(1) + stage, text, count=1))
        print(f"stage: {stage}")


if __name__ == "__main__":
    main()
