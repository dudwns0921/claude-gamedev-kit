#!/usr/bin/env python3
"""Collect the lessons piled up in game repositories (docs/kit-feedback.md) — the road by which what games taught comes back to the kit.

  python3 tools/kit_feedback.py list <game repo>...                       lines not yet reflected, numbered
  python3 tools/kit_feedback.py done <game repo> <number,number> <version>   mark reflected lines [x] (records which version they went into)

A person and Claude do the reflecting — read the line and move it to the right place among engines/<engine>/CLAUDE.md (what becomes the game's rules) · NOTES.md (what to do after installing) · the skill documents · the scripts.
A line that fits that game only is not moved; mark it done saying so (in the version slot, "안 올림: <reason>").
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
            print(f"{repo} — " + (f"{len(todo)} lines" if p else f"{FILE} not found"))
            for i, text in enumerate(todo, 1):
                print(f"  {i}. {text}")
    elif len(args) == 4 and args[0] == "done":
        p = path(args[1]) or sys.exit(f"{args[1]}: {FILE} not found")
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
            sys.exit(f"no such number — {n} lines remain")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
        print(f"{len(want)} lines: [x]")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
