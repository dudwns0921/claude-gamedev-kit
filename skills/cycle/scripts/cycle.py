#!/usr/bin/env python3
"""Ledger for the cycle document (docs/cycle/NN-name.md) — pulls out and changes only the lines needed, without reading the whole document or editing it by hand.

  python3 cycle.py new <short-name> "<goal — in the user's own words>"   New document. Numbered after the last one. A previous cycle standing at Play becomes `Closed`, and what is left · deferred there is reported
  python3 cycle.py status                       Per document: stage · task counts · open decisions
  python3 cycle.py next                         Current stage, open decisions, the tasks of the next wave to run
  python3 cycle.py task T3                      One task and only the decisions it depends on (what the developer agent reads)
  python3 cycle.py mark T1,T3 done              [x]. `blocked` is [!], `open` is [ ]
  python3 cycle.py mark T2 blocked "<reason>"   One `- **Blocked**:` line under the task. Text after done goes in `- **Done**:`
  python3 cycle.py ask <stage> "<question — ① … ② … · recommended: ①>"   Adds a decision and prints its number (D4). Any stage: Spec · Design · Plan · Build · Play, or Playtest · Asset
        [--image "<label>=<path>" …]            Pictures to look at while deciding (a capture of now, the candidates, a reference) — shown with it on the board and the dashboard
  python3 cycle.py attach D3 --image "<label>=<path>" …   Pictures for a decision already asked (they replace any attached before)
  python3 cycle.py reask D3 "<question — ① … ② … · recommended: ①>" [--image …]   Ask it again as a new decision (the answer was a question back, the options changed): D3 closes as "asked again as D7", D7 is asked
  python3 cycle.py decide D2 "<the user's answer, as said>"
  python3 cycle.py confirm D2,D5                A document from the time of auto mode: the user accepted what was decided in their place ([~]) — it becomes [x]. `confirm all` for all of them. To overturn: `decide D2 "<the user's answer>"`
  python3 cycle.py drop D4,D12 "<why, as said>"   The user says the decision is not needed any more — [-]. Nothing waits on it; it is no longer asked
  python3 cycle.py stage <stage>                Changes `Stage:` in the head (Goal · Spec · Design · Plan · Build · Play)
  python3 cycle.py later "<in the user's own words>"   One `- Next:` line in the "Play" section for something deferred. `new` shows it when the next cycle is made
  python3 cycle.py carry "<what the next session must know>"   One `- [ ]` line in the "Carried over" section, for work in hand that the document does not hold. `next` shows it
  python3 cycle.py carry done                   The lines were picked up — they become [x], so the session after does not pick them up again

The document is the newest one (highest number). For another, `--doc <path>`.
Documents are written in English. Ones written before that use Korean words — both are read, and a stage or section given in Korean is taken too.
"""
import contextlib
import datetime
import io
import json
import os
import re
import subprocess
import sys

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "cycle")
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


def pictures(images):
    """`<label>=<path>` (or a bare path, labelled by its name) → [{label, path}], every file checked before anything is written."""
    pics = []
    for given in images:
        label, sep, rel = given.partition("=")
        rel = rel if sep else label
        label = label.strip() if sep else os.path.splitext(os.path.basename(rel))[0]
        if not os.path.isfile(os.path.join(ROOT, rel)):
            sys.exit(f"{rel}: no such file (paths are relative to the game root) — nothing was written")
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


def cmd_ask(path, who, question, images=()):
    question = clean(question)
    text = read(path)
    span = section(text, "Decisions") or sys.exit("the document has no `## Decisions` section")
    pics = pictures(images)
    num = "D%d" % (max([int(d[1:]) for d in decisions(text)] or [0]) + 1)
    body = text[span[0]:span[1]].rstrip("\n")
    write(path, text[:span[0]] + body + f"\n- [ ] {num}. {question.strip()} ({EN.get(who, who)})\n\n" + text[span[1]:])
    if pics:
        keep_pictures(path, num, question.strip(), pics)
    print(num)


def cmd_reask(path, num, question, images=()):
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
    who = re.search(r"\((Spec|Design|Plan|Build|Play|Playtest|Asset|기획|디자인|계획|구현|플레이)\)", old)
    pics = pictures(images)
    new = "D%d" % (max(int(d[1:]) for d in ds) + 1)
    ask = PROXY_RE.match(old).group(1) if mark == "~" else old.split(" → ")[0]
    text = text.replace(old, f"- [-]{ask[5:]} → asked again as {new} ({datetime.date.today()})", 1)
    write(path, text)
    with contextlib.redirect_stdout(io.StringIO()):
        cmd_ask(path, EN.get(who.group(1), who.group(1)) if who else "Spec", question)
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
    ds = decisions(read(path))
    if num not in ds:
        sys.exit(f"{num}: no such decision — " + " · ".join(ds))
    if not images:
        sys.exit('give the pictures: attach D3 --image "<label>=<path>" …')
    pics = pictures(images)
    keep_pictures(path, num, ds[num][1][6:].split(" — ")[0].strip(), pics)
    print(f"{num}: {len(pics)} picture(s) — shown with it on the board and the dashboard")


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
    for said in LATER_RE.findall(text):
        print(f"deferred: {said}")
    for line in carried(text):
        print(f"carried over, not picked up: {line}")


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
    if before:
        close(before[-1])
    if dirty:
        print("there are uncommitted changes")


def main():
    args = sys.argv[1:]
    opts, images = {}, []
    for flag in ("--root", "--doc"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    while "--image" in args:
        i = args.index("--image")
        if i + 1 >= len(args):
            sys.exit(__doc__)
        images.append(args[i + 1])
        del args[i:i + 2]
    cmd, rest = (args[0] if args else ""), args[1:]
    if images and cmd not in ("ask", "attach", "reask"):
        sys.exit("--image goes with ask, attach or reask")
    need = {"new": 2, "status": 0, "next": 0, "task": 1, "mark": (2, 3), "ask": 2, "attach": 1, "reask": 2, "decide": 2, "confirm": 1, "drop": 2, "stage": 1, "later": 1, "carry": 1}
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
        cmd_ask(path, *rest, images)
    elif cmd == "attach":
        cmd_attach(path, rest[0], images)
    elif cmd == "reask":
        cmd_reask(path, rest[0], rest[1], images)
    elif cmd == "decide":
        cmd_decide(path, *rest)
    elif cmd == "confirm":
        cmd_confirm(path, rest[0])
    elif cmd == "drop":
        cmd_drop(path, *rest)
    elif cmd == "later":
        cmd_later(path, rest[0])
    elif cmd == "carry":
        cmd_carry(path, rest[0])
    else:
        text = read(path)
        if not STAGE_RE.search(text):
            sys.exit("the document head has no `Stage:`")
        stage = EN.get(rest[0], rest[0])
        write(path, STAGE_RE.sub(lambda m: m.group(1) + stage, text, count=1))
        print(f"stage: {stage}")


if __name__ == "__main__":
    main()
