#!/usr/bin/env python3
"""Check that no individual records leaked into the public repository — games' names and dates.

  python3 tools/private_check.py                    every file git knows
  python3 tools/private_check.py --message <file>   a commit message (called by the commit-msg hook)

The blocked words (games' names and the like) live outside the repository: private-words.txt in the rules folder
(~/.config/gamedev-kit/rules, override with GAMEDEV_KIT_RULES — the old voice folder is read too), one per line. Without that file only dates are checked.
Dates (YYYY-MM-DD) are written nowhere outside tests/.

The commit-msg hook in .githooks/ runs it; turn the hooks on once per clone: git config core.hooksPath .githooks
"""
import os
import re
import subprocess
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOMES = [os.path.expanduser(os.environ.get("GAMEDEV_KIT_RULES") or "~/.config/gamedev-kit/rules"),
         os.path.expanduser(os.environ.get("GAMEDEV_KIT_VOICE") or "~/.config/gamedev-kit/voice")]
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def words():
    out = []
    for home in HOMES:
        path = os.path.join(home, "private-words.txt")
        if os.path.exists(path):
            out += [w.strip().lower() for w in open(path, encoding="utf-8") if w.strip() and not w.startswith("#")]
    return sorted(set(out))


def problems(name, text, block, dates):
    for n, line in enumerate(text.split("\n"), 1):
        low = line.lower()
        if any(w in low for w in block):
            yield f"{name}:{n}: blocked word"
        if dates and DATE_RE.search(line):
            yield f"{name}:{n}: date"


def main():
    args, block, found = sys.argv[1:], words(), []
    if args[:1] == ["--message"] and len(args) == 2:
        lines = [l for l in open(args[1], encoding="utf-8").read().split("\n") if not l.startswith("#")]
        found = list(problems("commit message", "\n".join(lines), block, True))
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
        sys.exit("\n".join(found) + "\nIndividual records do not belong in this repository — move them to records.md in your private folder (~/.config/gamedev-kit/)")
    print("Nothing leaked" + ("" if block else " (no private-words.txt — only dates were checked)"))


if __name__ == "__main__":
    main()
