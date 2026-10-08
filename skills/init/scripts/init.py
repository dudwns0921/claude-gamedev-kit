#!/usr/bin/env python3
"""게임 저장소에 gamedev-kit 이 쓰는 파일을 깐다. 게임 저장소 루트에서 돌린다.

  python3 init.py              깔 수 있는 엔진을 적는다
  python3 init.py <엔진>       설정 · GDD 틀 · 런타임 틀을 깐다
  python3 init.py <엔진> --files   이미 깐 프로젝트에서 엔진 틀(값 파일 · 런타임)도 없는 것을 다시 깐다
  python3 init.py <엔진> --rules   CLAUDE.md 의 키트 규칙 블록을 지금 판으로 맞춘다 (없으면 끝에 붙인다). 블록 밖은 건드리지 않는다
  python3 init.py --rules-check    블록이 없거나 옛 판이면 한 줄 적는다 (세션이 시작될 때 훅이 부른다. 같으면 조용하다)

이미 있는 파일은 건드리지 않는다 — 몇 번을 돌려도 같다.
이미 깐 프로젝트(kit.config.json 이 있다)에서 다시 돌리면 엔진 틀은 건너뛴다: 값 파일을 옮겼거나 틀을 일부러 지운 프로젝트에
같은 파일을 또 만들지 않게 (Godot 은 `class_name` 이 둘이면 뜨지 않는다). 대신 그 뒤로 키트에 생긴 설정 절을 알려 준다.

CLAUDE.md 에서 키트의 것은 `<!-- gamedev-kit 시작 … -->` 과 `<!-- gamedev-kit 끝 -->` 사이뿐이다 (공통 규칙 + 엔진 규칙).
키트가 판을 올리면 --rules 가 그 사이만 통째로 바꾼다 — 게임의 규칙은 블록 밖에 있고 건드리지 않는다.
블록 안을 손으로 고쳤으면 덮지 않고 멈춘다 (고친 것을 밖으로 옮기거나 --force).
"""
import hashlib
import json
import os
import re
import shutil
import sys

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
ENGINES = os.path.join(KIT, "engines")
LOCK_LINE = "~$*.xlsx"
START, END = "<!-- gamedev-kit 시작", "<!-- gamedev-kit 끝 -->"
BLOCK_RE = re.compile(re.escape(START) + r" · ([0-9a-f]+)[^\n]*-->\n(.*?)\n" + re.escape(END), re.S)
OWN = """
## This game's rules

Structure, pitfalls and verification methods specific to this game go here. Where they disagree with the block above, what is written here wins.
"""


def engines():
    return sorted(d for d in os.listdir(ENGINES) if os.path.exists(os.path.join(ENGINES, d, "kit.config.json")))


def rules(engine):
    """(머리, 규칙 본문) — 본문은 공통 틀의 절들과 그 엔진의 규칙이다."""
    head, body = open(os.path.join(KIT, "templates", "CLAUDE.md"), encoding="utf-8").read().split("\n## ", 1)
    extra = os.path.join(ENGINES, engine, "CLAUDE.md")  # 그 엔진에서만 맞는 규칙 (실행 · 검증 · 함정)
    more = open(extra, encoding="utf-8").read().strip() if os.path.exists(extra) else ""
    return head.strip() + "\n", ("## " + body.strip() + ("\n\n" + more if more else "")).strip()


def digest(body):
    return hashlib.sha1(body.strip().encode("utf-8")).hexdigest()[:8]


def block(body):
    return (f"{START} · {digest(body)} — kit rules. Do not edit between these markers (`/gamedev-kit:init rules` replaces the whole block). "
            f"This game's own rules go outside the block. -->\n{body.strip()}\n{END}\n")


def rules_state(root, engine):
    """none(블록이 없다) · same · stale(키트가 판을 올렸다) · edited(블록 안을 손으로 고쳤다). CLAUDE.md 가 없으면 None."""
    path = os.path.join(root, "CLAUDE.md")
    if not os.path.exists(path):
        return None
    m = BLOCK_RE.search(open(path, encoding="utf-8").read())
    if not m:
        return "none"
    if digest(m.group(2)) != m.group(1):
        return "edited"
    return "same" if m.group(1) == digest(rules(engine)[1]) else "stale"


def sync_rules(root, engine, force):
    path = os.path.join(root, "CLAUDE.md")
    head, body = rules(engine)
    state = rules_state(root, engine)
    if state is None:
        open(path, "w", encoding="utf-8").write(head + "\n" + block(body) + OWN)
        return print("CLAUDE.md 를 새로 만들었다 — `<게임 이름>` 을 채운다")
    text = open(path, encoding="utf-8").read()
    if state == "same":
        return print("CLAUDE.md 의 키트 규칙은 지금 판과 같다")
    if state == "edited" and not force:
        sys.exit("CLAUDE.md 의 키트 규칙 블록 안이 손으로 고쳐졌다 — 덮지 않는다. 고친 것을 블록 밖으로 옮기고 다시 돌리거나, 버려도 되면 --force")
    if state == "none":
        titles = [t for t in re.findall(r"^## (.+)$", body, re.M) if re.search(rf"^## {re.escape(t)}\s*$", text, re.M)]
        open(path, "w", encoding="utf-8").write(text.rstrip("\n") + "\n\n" + block(body))
        print("CLAUDE.md 끝에 키트 규칙 블록을 붙였다 — 있던 글은 그대로다")
        if titles:
            print("블록 밖에 같은 제목의 절이 남아 있다 (옛 판을 옮겨 적은 것): " + " · ".join(titles)
                  + "\n겹치는 말은 블록 밖에서 지우고, 이 게임에서 고쳐 쓴 말만 밖에 남긴다 — 지우기 전에 사용자에게 보인다")
        return None
    open(path, "w", encoding="utf-8").write(BLOCK_RE.sub(lambda m: block(body).rstrip("\n"), text, count=1))
    print("CLAUDE.md 의 키트 규칙 블록을 지금 판으로 바꿨다 — 블록 밖은 그대로다")


def check_rules():
    """세션이 시작될 때 훅이 부른다. 할 말이 없으면 조용하다. 무슨 일이 있어도 0 으로 끝난다."""
    d = os.getcwd()
    while not os.path.exists(os.path.join(d, "kit.config.json")):
        if os.path.dirname(d) == d:
            return
        d = os.path.dirname(d)
    cfg = json.load(open(os.path.join(d, "kit.config.json"), encoding="utf-8"))
    if cfg.get("engine") not in engines() or cfg.get("init", {}).get("rules") is False:
        return
    say = {"none": "CLAUDE.md 에 키트 규칙 블록이 없다 (키트의 새 규칙이 이 프로젝트에 들어오지 않는다)",
           "stale": "CLAUDE.md 의 키트 규칙이 옛 판이다 (키트가 규칙을 고쳤다)",
           "edited": "CLAUDE.md 의 키트 규칙 블록 안이 손으로 고쳐져 있다 (판을 맞출 수 없다)"}.get(rules_state(d, cfg["engine"]))
    if say:
        print(f"[gamedev-kit] {say}. 하던 일을 막지 않는다 — 끊을 자리에서 사용자에게 한 줄로 알린다: `/gamedev-kit:init rules` 로 맞출 수 있다. "
              "알리지 않게 하려면 kit.config.json 에 `\"init\": {\"rules\": false}`.")


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
    if "--rules-check" in args:
        try:
            check_rules()
        except Exception:
            pass
        return
    again_files, only_rules, force = "--files" in args, "--rules" in args, "--force" in args
    args = [a for a in args if a not in ("--files", "--rules", "--force")]
    if not args:
        sys.exit("엔진을 고른다: " + " · ".join(engines()))
    engine = args[0]
    if engine not in engines():
        sys.exit(f"모르는 엔진 {engine} — " + " · ".join(engines()))
    src = os.path.join(ENGINES, engine)
    done = []
    if only_rules:
        return sync_rules(root, engine, force)

    config = os.path.join(root, "kit.config.json")
    had = os.path.exists(config)
    if had:
        has = json.load(open(config, encoding="utf-8")).get("engine", "")
        if has != engine:
            sys.exit(f"kit.config.json 은 이미 {has or '다른'} 엔진으로 깔려 있다 — 바꾸려면 그 파일을 먼저 지운다")
    place(os.path.join(src, "kit.config.json"), config, root, done)

    files = os.path.join(src, "files")
    skipped = []
    for dirpath, _dirs, names in os.walk(files):
        for name in sorted(names):
            path = os.path.join(dirpath, name)
            dst = os.path.join(root, os.path.relpath(path, files))
            if had and not again_files and not os.path.exists(dst):
                skipped.append(os.path.relpath(dst, root))
            else:
                place(path, dst, root, done)
    if skipped:
        done.append(f"  건너뜀  엔진 틀 {len(skipped)}개 — 이미 깐 프로젝트다. 옮겼거나 지운 것이면 그대로 두고, 다시 깔려면 --files: " + " · ".join(skipped))

    place(os.path.join(KIT, "templates", "GDD.md"), os.path.join(root, "docs", "GDD.md"), root, done)
    place(os.path.join(KIT, "templates", "DESIGN.md"), os.path.join(root, "docs", "DESIGN.md"), root, done)
    made_claude = not os.path.exists(os.path.join(root, "CLAUDE.md"))
    if made_claude:
        head, body = rules(engine)
        open(os.path.join(root, "CLAUDE.md"), "w", encoding="utf-8").write(head + "\n" + block(body) + OWN)
    done.append(f"  {'새로  ' if made_claude else '그대로'}  CLAUDE.md")

    ignore = os.path.join(root, ".gitignore")
    text = open(ignore, encoding="utf-8").read() if os.path.exists(ignore) else ""
    if LOCK_LINE not in text:
        with open(ignore, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n")
                    + "\n# 엑셀이 파일을 열어 둔 동안 만드는 잠금 파일\n" + LOCK_LINE + "\n")
        done.append("  더함    .gitignore (엑셀 잠금 파일)")

    print(f"gamedev-kit — {engine}\n" + "\n".join(done))
    if had:  # 그 뒤로 키트에 생긴 설정 절
        want = json.load(open(os.path.join(src, "kit.config.json"), encoding="utf-8"))
        have = json.load(open(config, encoding="utf-8"))
        missing = [k for k in want if k not in have] + [f"{k}.{s}" for k, v in want.items() if isinstance(v, dict) and isinstance(have.get(k), dict)
                                                         for s in v if s not in have[k]]
        if missing:
            print(f"\nkit.config.json 에 없는 절: {' · '.join(missing)} — 쓰려면 이 틀에서 옮겨 적는다: {os.path.join(src, 'kit.config.json')}")
    state = rules_state(root, engine)
    if state != "same":
        print("\nCLAUDE.md 의 키트 규칙: " + {"none": "블록이 없다 — `--rules` 가 끝에 붙인다 (있던 글은 건드리지 않는다)",
                                           "stale": "옛 판이다 — `--rules` 가 블록만 바꾼다",
                                           "edited": "블록 안이 손으로 고쳐졌다 — 고친 것을 밖으로 옮긴 뒤 `--rules`"}[state])
    notes = os.path.join(src, "NOTES.md")
    if os.path.exists(notes):
        print("\n" + open(notes, encoding="utf-8").read().strip())


if __name__ == "__main__":
    main()
