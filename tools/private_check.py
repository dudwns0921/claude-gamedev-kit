#!/usr/bin/env python3
"""공개 저장소에 낱낱의 기록이 새지 않았는지 본다 — 게임의 이름과 날짜.

  python3 tools/private_check.py                    git 이 아는 파일을 전부
  python3 tools/private_check.py --message <파일>   커밋 메시지 (commit-msg 훅이 부른다)

막을 낱말(게임의 이름 따위)은 저장소 밖에 있다: 보이스 폴더(~/.config/gamedev-kit/voice, GAMEDEV_KIT_VOICE 로 바꾼다)의
private-words.txt, 한 줄에 하나. 그 파일이 없으면 날짜만 본다. 날짜(YYYY-MM-DD)는 tests/ 밖 어디에도 적지 않는다.

훅은 저장소마다 한 번 건다:
  printf '#!/bin/sh\\nexec python3 tools/private_check.py --message "$1"\\n' > .git/hooks/commit-msg && chmod +x .git/hooks/commit-msg
"""
import os
import re
import subprocess
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser(os.environ.get("GAMEDEV_KIT_VOICE") or "~/.config/gamedev-kit/voice")
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def words():
    path = os.path.join(HOME, "private-words.txt")
    if not os.path.exists(path):
        return []
    return [w.strip().lower() for w in open(path, encoding="utf-8") if w.strip() and not w.startswith("#")]


def problems(name, text, block, dates):
    for n, line in enumerate(text.split("\n"), 1):
        low = line.lower()
        if any(w in low for w in block):
            yield f"{name}:{n}: 막을 낱말이 있다"
        if dates and DATE_RE.search(line):
            yield f"{name}:{n}: 날짜가 있다"


def main():
    args, block, found = sys.argv[1:], words(), []
    if args[:1] == ["--message"] and len(args) == 2:
        lines = [l for l in open(args[1], encoding="utf-8").read().split("\n") if not l.startswith("#")]
        found = list(problems("커밋 메시지", "\n".join(lines), block, True))
    elif not args:
        for name in subprocess.run(["git", "-C", KIT, "ls-files"], capture_output=True, text=True).stdout.split():
            try:
                text = open(os.path.join(KIT, name), encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            found += problems(name, text, block, not name.startswith("tests/"))
    else:
        sys.exit(__doc__)
    if found:
        sys.exit("\n".join(found) + "\n낱낱의 기록은 이 저장소에 두지 않는다 — 보이스 폴더의 records.md 로 옮긴다")
    print("새는 것이 없다" + ("" if block else " (private-words.txt 가 없어 날짜만 봤다)"))


if __name__ == "__main__":
    main()
