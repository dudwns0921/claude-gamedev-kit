#!/usr/bin/env python3
"""사이클 문서(docs/cycle/NN-이름.md)의 장부 — 문서를 통째로 읽거나 손으로 고치지 않고 필요한 줄만 꺼내고 바꾼다.

  python3 cycle.py new <짧은-이름> "<목표 — 사용자의 말 그대로>"   새 문서. 번호는 있는 문서 다음
  python3 cycle.py status                       문서마다 단계 · 작업 수 · 답 없는 결정 수
  python3 cycle.py next                         지금 단계, 답 없는 결정, 다음에 돌릴 차수의 작업
  python3 cycle.py task T3                      작업 하나와 그 작업에 걸린 결정만 (구현 에이전트가 읽는 것)
  python3 cycle.py mark T1,T3 done              [x]. `blocked` 는 [!], `open` 은 [ ]
  python3 cycle.py mark T2 blocked "<이유>"     작업 아래 `- **막힘**:` 한 줄. done 뒤의 글은 `- **한 것**:`
  python3 cycle.py ask <기획|디자인|계획> "<질문 — ① … ② … · 권함: ①>"   결정을 하나 더하고 번호(D4)를 적는다
  python3 cycle.py decide D2 "<사용자의 답 그대로>"
  python3 cycle.py stage <단계>                 머리의 `단계:` 를 고친다

문서는 가장 새 것(번호가 가장 큰 것)이다. 다른 문서면 `--doc <경로>`.
"""
import datetime
import os
import re
import subprocess
import sys

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "cycle")
TEMPLATE = """# 사이클 {num} — {name}

시작: {date} · 커밋 {commit} · 단계: 목표

## 목표
{goal}

## 결정

## 기획

## 디자인

## 작업

## 순서

## 플레이

## 배포

## 회고
"""
BOX = {"done": "x", "blocked": "!", "open": " "}
NOTE = {"done": "한 것", "blocked": "막힘"}
TASK_RE = re.compile(r"^### \[(.)\] (T\d+)\.(.*)$", re.M)
DECISION_RE = re.compile(r"^- \[(.)\] (D\d+)\.(.*)$", re.M)

ROOT = ""


def find_root(start):
    """kit.config.json 이 있는 폴더를 지금 폴더에서 위로 올라가며 찾는다. 도구는 플러그인 안에 있고 게임은 밖에 있다."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            sys.exit(f"{CONFIG_NAME} 을 찾지 못했다 — 게임 저장소 안에서 돌리고 있는가, /gamedev-kit:init 을 했는가")
        d = up


def docs():
    d = os.path.join(ROOT, DIR)
    return sorted(os.path.join(d, n) for n in os.listdir(d) if re.match(r"\d+-.*\.md$", n)) if os.path.isdir(d) else []


def pick(path):
    if path:
        path = path if os.path.isabs(path) else os.path.join(ROOT, path)
        if not os.path.exists(path):
            sys.exit(f"{path}: 문서가 없다")
        return path
    if not docs():
        sys.exit(f"{DIR}/ 에 사이클 문서가 없다 — cycle.py new <짧은-이름> \"<목표>\"")
    return docs()[-1]


def read(path):
    return open(path, encoding="utf-8").read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def section(text, title):
    """`## <title>` 절의 (시작, 끝). 없으면 None."""
    m = re.search(rf"^## {re.escape(title)}[ \t]*$", text, re.M)
    if not m:
        return None
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return m.end(), m.end() + nxt.start() if nxt else len(text)


def stage_of(text):
    m = re.search(r"단계: *(.+)", text)
    return m.group(1).strip() if m else "?"


def tasks(text):
    """작업 번호 → (상태 글자, 제목, 블록 시작, 블록 끝)."""
    found, hits = {}, list(TASK_RE.finditer(text))
    for m in hits:
        nxt = re.search(r"^##+ ", text[m.end():], re.M)
        found[m.group(2)] = (m.group(1), m.group(3).strip(), m.start(), m.end() + nxt.start() if nxt else len(text))
    return found


def decisions(text):
    return {m.group(2): (m.group(1), m.group(0)) for m in DECISION_RE.finditer(text)}


def waiting(block, ds):
    """작업 블록의 `대기: D2` 중 아직 답이 없는 것."""
    line = re.search(r"\*\*대기\*\*:(.*)", block)
    return [d for d in re.findall(r"D\d+", line.group(1)) if ds.get(d, (" ",))[0] != "x"] if line else []


def waves(text):
    span = section(text, "순서")
    out = []
    for line in (text[span[0]:span[1]].split("\n") if span else []):
        m = re.match(r"- *(\d+) *차:(.*)", line.strip())
        if m:
            out.append((int(m.group(1)), re.findall(r"T\d+", m.group(2).split("—")[0])))
    return out


def summary(path):
    text = read(path)
    marks = [t[0] for t in tasks(text).values()]
    open_d = sum(1 for d in decisions(text).values() if d[0] != "x")
    return (f"{os.path.relpath(path, ROOT)} — 단계: {stage_of(text)} · 작업 [x] {marks.count('x')} · [ ] {marks.count(' ')} · "
            f"[!] {marks.count('!')} · 답 없는 결정 {open_d}")


def cmd_next(path):
    text = read(path)
    ts, ds = tasks(text), decisions(text)
    print(summary(path))
    for num, (mark, line) in ds.items():
        if mark != "x":
            print(f"답 없는 결정: {line[6:]}")
    for num, (mark, title, a, b) in ts.items():
        if mark == "!":
            print(f"막힌 작업: {num}. {title}")
    for n, names in waves(text):
        left = [t for t in names if t in ts and ts[t][0] == " "]
        if not left:
            continue
        print(f"다음 차수: {n}차")
        for t in left:
            hold = waiting(text[ts[t][2]:ts[t][3]], ds)
            print(f"  {t}. {ts[t][1]}" + (f" — 대기 {' · '.join(hold)} (지금은 돌리지 않는다)" if hold else ""))
        break
    else:
        if ts and all(t[0] != " " for t in ts.values()):
            print("남은 작업이 없다")


def cmd_task(path, num):
    text = read(path)
    ts, ds = tasks(text), decisions(text)
    if num not in ts:
        sys.exit(f"{num}: 그런 작업이 없다 — " + " · ".join(ts))
    block = text[ts[num][2]:ts[num][3]].rstrip()
    print(f"{os.path.relpath(path, ROOT)} · 단계: {stage_of(text)}\n\n{block}")
    refs = [d for d in dict.fromkeys(re.findall(r"D\d+", block)) if d in ds]
    if refs:
        print("\n걸린 결정:")
        for d in refs:
            print(ds[d][1])


def cmd_mark(path, names, state, note):
    text = read(path)
    for num in names.split(","):
        ts = tasks(text)
        if num not in ts:
            sys.exit(f"{num}: 그런 작업이 없다 — " + " · ".join(ts))
        _mark, _title, a, b = ts[num]
        block = TASK_RE.sub(lambda m: f"### [{BOX[state]}] {m.group(2)}.{m.group(3)}", text[a:b], count=1)
        if note and state in NOTE:
            block = block.rstrip("\n") + f"\n- **{NOTE[state]}**: {note}\n\n"
        text = text[:a] + block + text[b:]
        print(f"{num}: [{BOX[state]}]")
    write(path, text)


def cmd_ask(path, who, question):
    text = read(path)
    span = section(text, "결정") or sys.exit("문서에 `## 결정` 절이 없다")
    num = "D%d" % (max([int(d[1:]) for d in decisions(text)] or [0]) + 1)
    body = text[span[0]:span[1]].rstrip("\n")
    write(path, text[:span[0]] + body + f"\n- [ ] {num}. {question.strip()} ({who})\n\n" + text[span[1]:])
    print(num)


def cmd_decide(path, num, answer):
    text = read(path)
    ds = decisions(text)
    if num not in ds:
        sys.exit(f"{num}: 그런 결정이 없다 — " + " · ".join(ds))
    old = ds[num][1]
    write(path, text.replace(old, f"- [x]{old[5:]} → {answer.strip()} ({datetime.date.today()})", 1))
    print(f"{num}: 답을 적었다")


def cmd_new(name, goal):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        sys.exit(f"이름은 소문자 · 숫자 · 붙임표다: {name!r}")
    num = max([int(os.path.basename(p).split("-")[0]) for p in docs()] or [0]) + 1
    path = os.path.join(ROOT, DIR, f"{num:02d}-{name}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    write(path, TEMPLATE.format(num=f"{num:02d}", name=name, date=datetime.date.today(),
                                commit=git("rev-parse", "--short", "HEAD") or "없음", goal=goal.strip()))
    print(os.path.relpath(path, ROOT))
    if git("status", "--porcelain"):
        print("커밋 안 된 변경이 있다")


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--doc"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    cmd, rest = (args[0] if args else ""), args[1:]
    need = {"new": 2, "status": 0, "next": 0, "task": 1, "mark": (2, 3), "ask": 2, "decide": 2, "stage": 1}
    if cmd not in need or len(rest) not in (need[cmd] if isinstance(need[cmd], tuple) else (need[cmd],)):
        sys.exit(__doc__)
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    if cmd == "new":
        return cmd_new(*rest)
    if cmd == "status":
        return print("\n".join(summary(p) for p in docs()) or f"{DIR}/ 에 사이클 문서가 없다")
    path = pick(opts.get("--doc"))
    if cmd == "next":
        cmd_next(path)
    elif cmd == "task":
        cmd_task(path, rest[0])
    elif cmd == "mark":
        if rest[1] not in BOX:
            sys.exit("상태는 done · blocked · open 이다")
        cmd_mark(path, rest[0], rest[1], rest[2] if len(rest) > 2 else "")
    elif cmd == "ask":
        cmd_ask(path, *rest)
    elif cmd == "decide":
        cmd_decide(path, *rest)
    else:
        text = read(path)
        if not re.search(r"단계: *.+", text):
            sys.exit("문서 머리에 `단계:` 가 없다")
        write(path, re.sub(r"(단계: *).+", lambda m: m.group(1) + rest[0], text, count=1))
        print(f"단계: {rest[0]}")


if __name__ == "__main__":
    main()
