#!/usr/bin/env python3
"""플레이테스트 분석 문서(docs/playtest/*.md)의 장부 — 문서를 통째로 읽거나 손으로 고치지 않고 필요한 줄만 꺼내고 바꾼다.

  python3 playtest.py status                    문서마다 작업 수와 답 없는 질문이 있는지
  python3 playtest.py next                      다음에 돌릴 차수의 작업
  python3 playtest.py task T3                   요약과 작업 하나만 (구현 에이전트가 읽는 것)
  python3 playtest.py mark T1,T3 done           [x]. `blocked` 는 [!], `open` 은 [ ]
  python3 playtest.py mark T2 blocked "<이유>"  작업 아래 `- **막힘**:` 한 줄. done 뒤의 글은 `- **한 것**:`

문서는 가장 새 것(이름순으로 마지막)이다. 다른 문서면 `--doc <경로>`.
"""
import os
import re
import sys

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "playtest")
BOX = {"done": "x", "blocked": "!", "open": " "}
NOTE = {"done": "한 것", "blocked": "막힘"}
TASK_RE = re.compile(r"^### \[(.)\] (T\d+)\.(.*)$", re.M)

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
    return sorted(os.path.join(d, n) for n in os.listdir(d) if n.endswith(".md")) if os.path.isdir(d) else []


def pick(path):
    if path:
        path = path if os.path.isabs(path) else os.path.join(ROOT, path)
        if not os.path.exists(path):
            sys.exit(f"{path}: 문서가 없다")
        return path
    if not docs():
        sys.exit(f"{DIR}/ 에 분석 문서가 없다")
    return docs()[-1]


def section(text, title):
    m = re.search(rf"^## {re.escape(title)}[ \t]*$", text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end():m.end() + nxt.start() if nxt else len(text)].strip()


def tasks(text):
    """작업 번호 → (상태 글자, 제목, 블록 시작, 블록 끝)."""
    found = {}
    for m in TASK_RE.finditer(text):
        nxt = re.search(r"^##+ ", text[m.end():], re.M)
        found[m.group(2)] = (m.group(1), m.group(3).strip(), m.start(), m.end() + nxt.start() if nxt else len(text))
    return found


def summary(path):
    text = open(path, encoding="utf-8").read()
    marks = [t[0] for t in tasks(text).values()]
    ask = section(text, "사용자에게 물을 것")
    return (f"{os.path.relpath(path, ROOT)} — 작업 [x] {marks.count('x')} · [ ] {marks.count(' ')} · [!] {marks.count('!')}"
            + ("" if not ask or ask.startswith("없음") else " · 사용자에게 물을 것이 있다"))


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--doc"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    cmd, rest = (args[0] if args else ""), args[1:]
    need = {"status": (0,), "next": (0,), "task": (1,), "mark": (2, 3)}
    if cmd not in need or len(rest) not in need[cmd]:
        sys.exit(__doc__)
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    if cmd == "status":
        return print("\n".join(summary(p) for p in docs()) or f"{DIR}/ 에 분석 문서가 없다")
    path = pick(opts.get("--doc"))
    text = open(path, encoding="utf-8").read()
    ts = tasks(text)
    if cmd == "next":
        print(summary(path))
        ask = section(text, "사용자에게 물을 것")
        if ask and not ask.startswith("없음"):
            print("사용자에게 물을 것:\n" + ask)
        for line in section(text, "순서").split("\n"):
            m = re.match(r"- *(\d+) *차:(.*)", line.strip())
            left = [t for t in re.findall(r"T\d+", m.group(2).split("—")[0]) if t in ts and ts[t][0] == " "] if m else []
            if left:
                print(f"다음 차수: {m.group(1)}차")
                for t in left:
                    kind = re.search(r"\*\*분류\*\*: *(\S+)", text[ts[t][2]:ts[t][3]])
                    print(f"  {t}. {ts[t][1]}" + (f" ({kind.group(1)})" if kind else ""))
                break
    elif cmd == "task":
        if rest[0] not in ts:
            sys.exit(f"{rest[0]}: 그런 작업이 없다 — " + " · ".join(ts))
        print(f"{os.path.relpath(path, ROOT)}\n\n## 요약\n{section(text, '요약')}\n\n{text[ts[rest[0]][2]:ts[rest[0]][3]].rstrip()}")
    else:
        if rest[1] not in BOX:
            sys.exit("상태는 done · blocked · open 이다")
        for num in rest[0].split(","):
            ts = tasks(text)
            if num not in ts:
                sys.exit(f"{num}: 그런 작업이 없다 — " + " · ".join(ts))
            a, b = ts[num][2], ts[num][3]
            block = TASK_RE.sub(lambda m: f"### [{BOX[rest[1]]}] {m.group(2)}.{m.group(3)}", text[a:b], count=1)
            if len(rest) > 2 and rest[1] in NOTE:
                block = block.rstrip("\n") + f"\n- **{NOTE[rest[1]]}**: {rest[2]}\n\n"
            text = text[:a] + block + text[b:]
            print(f"{num}: [{BOX[rest[1]]}]")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
