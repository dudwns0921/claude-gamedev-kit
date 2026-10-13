#!/usr/bin/env python3
"""Ledger for the playtest analysis document (docs/playtest/*.md) — pulls out and changes only the lines needed, without reading the whole document or editing it by hand.

  python3 playtest.py status                    Per document: task counts and whether questions are still open
  python3 playtest.py next                      The tasks of the next wave to run
  python3 playtest.py task T3                   The summary and one task only (what the developer agent reads)
  python3 playtest.py mark T1,T3 done           [x]. `blocked` is [!], `open` is [ ]
  python3 playtest.py mark T2 blocked "<reason>"  One `- **막힘**:` line under the task. Text after done goes in `- **한 것**:`
  python3 playtest.py lesson "<what tripped us → how to avoid it>"   One line in docs/kit-feedback.md for a lesson that is not this game's alone (to send up to the kit)

The document is the newest one (last by name). For another, `--doc <path>`.
"""
import datetime
import json
import os
import re
import sys

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "playtest")
FEEDBACK = os.path.join("docs", "kit-feedback.md")
FEEDBACK_HEAD = """# 키트로 올릴 것

이 게임을 만들며 배운 것 가운데 **이 게임만의 것이 아닌 것** — 같은 엔진의 다음 게임도 걸려 넘어질 함정, 쓸 만한 확인 방법, 키트 도구의 모자란 점.
걸려 넘어진 그 자리에서 한 줄씩 쌓인다 (`cycle.py lesson` · `playtest.py lesson`). `/gamedev-kit:feedback` 이 키트 저장소의 이슈로 보낸다 — 보낸 줄은 `[>]`, 보내지 않기로 한 줄은 `[-]` 가 된다.

"""
BOX = {"done": "x", "blocked": "!", "open": " "}
NOTE = {"done": "한 것", "blocked": "막힘"}
TASK_RE = re.compile(r"^### \[(.)\] (T\d+)\.(.*)$", re.M)

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
    return sorted(os.path.join(d, n) for n in os.listdir(d) if n.endswith(".md")) if os.path.isdir(d) else []


def pick(path):
    if path:
        path = path if os.path.isabs(path) else os.path.join(ROOT, path)
        if not os.path.exists(path):
            sys.exit(f"{path}: no such document")
        return path
    if not docs():
        sys.exit(f"no analysis document in {DIR}/")
    return docs()[-1]


def section(text, title):
    m = re.search(rf"^## {re.escape(title)}[ \t]*$", text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end():m.end() + nxt.start() if nxt else len(text)].strip()


def tasks(text):
    """Task number → (state mark, title, block start, block end)."""
    found = {}
    for m in TASK_RE.finditer(text):
        nxt = re.search(r"^##+ ", text[m.end():], re.M)
        found[m.group(2)] = (m.group(1), m.group(3).strip(), m.start(), m.end() + nxt.start() if nxt else len(text))
    return found


def summary(path):
    text = open(path, encoding="utf-8").read()
    marks = [t[0] for t in tasks(text).values()]
    ask = section(text, "사용자에게 물을 것")
    return (f"{os.path.relpath(path, ROOT)} — tasks [x] {marks.count('x')} · [ ] {marks.count(' ')} · [!] {marks.count('!')}"
            + ("" if not ask or ask.startswith("없음") else " · has questions for the user"))


def lesson(said):
    engine = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get("engine", "?")
    out = os.path.join(ROOT, FEEDBACK)
    old = open(out, encoding="utf-8").read() if os.path.exists(out) else FEEDBACK_HEAD
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(old.rstrip("\n") + f"\n- [ ] ({engine} · 플레이테스트 · {datetime.date.today()}) {' '.join(said.split())}\n")
    print(f"added to {FEEDBACK}")


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--doc"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    cmd, rest = (args[0] if args else ""), args[1:]
    need = {"status": (0,), "next": (0,), "task": (1,), "mark": (2, 3), "lesson": (1,)}
    if cmd not in need or len(rest) not in need[cmd]:
        sys.exit(__doc__)
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    if cmd == "status":
        return print("\n".join(summary(p) for p in docs()) or f"no analysis document in {DIR}/")
    if cmd == "lesson":
        return lesson(rest[0])
    path = pick(opts.get("--doc"))
    text = open(path, encoding="utf-8").read()
    ts = tasks(text)
    if cmd == "next":
        print(summary(path))
        ask = section(text, "사용자에게 물을 것")
        if ask and not ask.startswith("없음"):
            print("questions for the user:\n" + ask)
        for line in section(text, "순서").split("\n"):
            m = re.match(r"- *(\d+) *차:(.*)", line.strip())
            left = [t for t in re.findall(r"T\d+", m.group(2).split("—")[0]) if t in ts and ts[t][0] == " "] if m else []
            if left:
                print(f"next wave: {m.group(1)}")
                for t in left:
                    kind = re.search(r"\*\*분류\*\*: *(\S+)", text[ts[t][2]:ts[t][3]])
                    print(f"  {t}. {ts[t][1]}" + (f" ({kind.group(1)})" if kind else ""))
                break
    elif cmd == "task":
        if rest[0] not in ts:
            sys.exit(f"{rest[0]}: no such task — " + " · ".join(ts))
        print(f"{os.path.relpath(path, ROOT)}\n\n## 요약\n{section(text, '요약')}\n\n{text[ts[rest[0]][2]:ts[rest[0]][3]].rstrip()}")
    else:
        if rest[1] not in BOX:
            sys.exit("the state is done · blocked · open")
        for num in rest[0].split(","):
            ts = tasks(text)
            if num not in ts:
                sys.exit(f"{num}: no such task — " + " · ".join(ts))
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
