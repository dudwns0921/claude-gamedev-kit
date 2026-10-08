#!/usr/bin/env python3
"""게임 저장소들에 쌓인 "키트로 올릴 것"(docs/kit-feedback.md)을 모은다 — 게임에서 배운 것이 키트로 돌아오는 길.

  python3 tools/kit_feedback.py list <게임 저장소>...             아직 반영하지 않은 줄을 번호와 함께
  python3 tools/kit_feedback.py done <게임 저장소> <번호,번호> <버전>   반영한 줄을 [x] 로 (어느 버전에 들어갔는지 적는다)

반영은 사람과 Claude 가 한다 — 줄을 읽고 engines/<엔진>/CLAUDE.md(게임의 규칙이 될 것) · NOTES.md(깐 뒤 할 일) · 스킬 문서 · 스크립트 중 맞는 곳에 옮긴다.
그 게임에만 맞는 줄이면 옮기지 않고 그렇게 적어 done 한다 (버전 자리에 "안 올림: <이유>").
"""
import os
import re
import sys

FILE = os.path.join("docs", "kit-feedback.md")
LINE = re.compile(r"^- \[ \] (.*)$")


def path(repo):
    p = os.path.join(os.path.abspath(os.path.expanduser(repo)), FILE)
    return p if os.path.exists(p) else None


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "list":
        for repo in args[1:]:
            p = path(repo)
            lines = open(p, encoding="utf-8").read().split("\n") if p else []
            todo = [m.group(1) for m in map(LINE.match, lines) if m]
            print(f"{repo} — " + (f"{len(todo)}줄" if p else f"{FILE} 가 없다"))
            for i, text in enumerate(todo, 1):
                print(f"  {i}. {text}")
    elif len(args) == 4 and args[0] == "done":
        p = path(args[1]) or sys.exit(f"{args[1]}: {FILE} 가 없다")
        want = {int(n) for n in args[2].split(",")}
        out, n = [], 0
        for line in open(p, encoding="utf-8").read().split("\n"):
            m = LINE.match(line)
            if m:
                n += 1
                if n in want:
                    line = f"- [x] {m.group(1)} — 키트 {args[3]}"
            out.append(line)
        if not want <= set(range(1, n + 1)):
            sys.exit(f"번호가 없다 — 남은 줄은 {n}개다")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
        print(f"{len(want)}줄: [x]")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
