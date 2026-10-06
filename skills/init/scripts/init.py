#!/usr/bin/env python3
"""게임 저장소에 gamedev-kit 이 쓰는 파일을 깐다. 게임 저장소 루트에서 돌린다.

  python3 init.py              깔 수 있는 엔진을 적는다
  python3 init.py <엔진>       설정 · GDD 틀 · 런타임 틀을 깐다

이미 있는 파일은 건드리지 않는다 — 몇 번을 돌려도 같다.
"""
import json
import os
import shutil
import sys

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
ENGINES = os.path.join(KIT, "engines")
LOCK_LINE = "~$*.xlsx"


def engines():
    return sorted(d for d in os.listdir(ENGINES) if os.path.exists(os.path.join(ENGINES, d, "kit.config.json")))


def place(src, dst, root, done):
    rel = os.path.relpath(dst, root)
    if os.path.exists(dst):
        done.append(f"  그대로  {rel}")
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(src, dst)
    done.append(f"  새로    {rel}")
    return True


def main():
    args = sys.argv[1:]
    root = os.getcwd()
    if "--root" in args:  # 테스트용
        i = args.index("--root")
        root = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    if not args:
        sys.exit("엔진을 고른다: " + " · ".join(engines()))
    engine = args[0]
    if engine not in engines():
        sys.exit(f"모르는 엔진 {engine} — " + " · ".join(engines()))
    src = os.path.join(ENGINES, engine)
    done = []

    config = os.path.join(root, "kit.config.json")
    if os.path.exists(config):
        has = json.load(open(config, encoding="utf-8")).get("engine", "")
        if has != engine:
            sys.exit(f"kit.config.json 은 이미 {has or '다른'} 엔진으로 깔려 있다 — 바꾸려면 그 파일을 먼저 지운다")
    place(os.path.join(src, "kit.config.json"), config, root, done)

    files = os.path.join(src, "files")
    for dirpath, _dirs, names in os.walk(files):
        for name in sorted(names):
            path = os.path.join(dirpath, name)
            place(path, os.path.join(root, os.path.relpath(path, files)), root, done)

    place(os.path.join(KIT, "templates", "GDD.md"), os.path.join(root, "docs", "GDD.md"), root, done)
    made_claude = place(os.path.join(KIT, "templates", "CLAUDE.md"), os.path.join(root, "CLAUDE.md"), root, done)
    extra = os.path.join(src, "CLAUDE.md")  # 그 엔진에서만 맞는 규칙 (실행 · 검증 · 함정)
    if made_claude and os.path.exists(extra):
        with open(os.path.join(root, "CLAUDE.md"), "a", encoding="utf-8") as f:
            f.write(open(extra, encoding="utf-8").read())

    ignore = os.path.join(root, ".gitignore")
    text = open(ignore, encoding="utf-8").read() if os.path.exists(ignore) else ""
    if LOCK_LINE not in text:
        with open(ignore, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n")
                    + "\n# 엑셀이 파일을 열어 둔 동안 만드는 잠금 파일\n" + LOCK_LINE + "\n")
        done.append("  더함    .gitignore (엑셀 잠금 파일)")

    print(f"gamedev-kit — {engine}\n" + "\n".join(done))
    if not made_claude and "gdd-sync" not in open(os.path.join(root, "CLAUDE.md"), encoding="utf-8").read():
        print(f"\nCLAUDE.md 에 동기화 규칙이 없다 — 이 틀의 절을 옮겨 적는다: {os.path.join(KIT, 'templates', 'CLAUDE.md')}")
        if os.path.exists(extra):
            print(f"엔진 규칙도: {extra}")
    notes = os.path.join(src, "NOTES.md")
    if os.path.exists(notes):
        print("\n" + open(notes, encoding="utf-8").read().strip())


if __name__ == "__main__":
    main()
