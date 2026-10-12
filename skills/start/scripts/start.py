#!/usr/bin/env python3
"""시작 — 키트를 깐 빈 게임이 첫 사이클의 목표에 닿기까지 어디에 서 있는가. 상태는 게임의 파일에서 읽는다 — 세션이 바뀌어도 같은 답이 나온다.

  python3 start.py status          GDD → 컨셉 → 목표 가운데 어디까지 왔고 다음 단계가 무엇인지
  python3 start.py skip <단계>     그 단계를 건너뛴다 (gdd · concept). status 가 건너뛴 것을 계속 적는다 — 잊지 않게
  python3 start.py unskip <단계>   건너뛴 것을 되돌린다

단계가 끝났는지는 이렇게 본다:
  gdd      GDD(gdd-sync.gdd, 기본 docs/GDD.md)의 본문 절 가운데 개요 · 게임 구조 · 규칙과 시스템 · 제작 범위 에 글이 있다.
           톤 · 사운드 · 미정 사항은 비어 있어도 된다 (적기만 한다). 틀에 처음부터 있던 줄은 글로 치지 않는다.
           그 제목이 GDD 에 아예 없으면(틀을 고쳐 쓴 GDD) 비었다고 하지 않는다 — 알리기만 한다.
  concept  GDD 의 아트 방향 절에 글이 있고, docs/concept/ 에 그림이 하나라도 있다 (사용자가 넣은 레퍼런스도 그림이다).
  goal     사이클 문서(docs/cycle/NN-*.md)가 생기면 시작은 끝났다.
건너뛴 단계는 docs/start/state.json 에 적힌다.
"""
import json
import os
import re
import sys

CONFIG_NAME = "kit.config.json"
KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
STAGES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stages")
STATE = os.path.join("docs", "start", "state.json")
CONCEPT = os.path.join("docs", "concept")
CYCLE = os.path.join("docs", "cycle")
MUST = ["개요", "게임 구조", "규칙", "제작 범위"]  # 이 절들에 글이 있어야 gdd 단계가 끝난다
MAY = ["톤", "사운드"]                             # 비어 있으면 적기만 한다
ART = "아트 방향"                                  # concept 단계의 것
SKIPPABLE = {"gdd": "GDD", "concept": "컨셉"}
PICTURES = (".png", ".jpg", ".jpeg", ".webp")

ROOT = ""


def find_root(start):
    """kit.config.json 이 있는 폴더를 지금 폴더에서 위로 올라가며 찾는다. 도구는 플러그인 안에 있고 게임은 밖에 있다."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            sys.exit(f"{CONFIG_NAME} 을 찾지 못했다 — 키트가 아직 깔리지 않았다. 먼저 `/gamedev-kit:init`")
        d = up


def gdd_path():
    cfg = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8"))
    return (cfg.get("gdd-sync") or {}).get("gdd") or "docs/GDD.md"


def sections(text):
    """본문의 `## ` 절마다 (제목, 본문 줄들). 부록부터는 표다 — 보지 않는다."""
    out = []
    for line in text.split("\n"):
        if line.startswith("## "):
            title = re.sub(r"^\d+\.\s*", "", line[3:].strip())
            if title.startswith("부록"):
                break
            out.append((title, []))
        elif out:
            out[-1][1].append(line.strip())
    return out


def template_lines():
    """틀에 처음부터 있는 줄 — 절에 이것만 있으면 아직 아무것도 쓰지 않은 것이다."""
    path = os.path.join(KIT, "templates", "GDD.md")
    return {line.strip() for line in open(path, encoding="utf-8")} if os.path.exists(path) else set()


def filled(title_key, parts, given):
    """그 낱말이 든 제목의 절에 글이 있는가. 그런 제목이 없으면 None."""
    for title, lines in parts:
        if title_key in title:
            return any(l and l != "---" and not l.startswith("<!--") and l not in given for l in lines)
    return None


def skipped():
    path = os.path.join(ROOT, STATE)
    return json.load(open(path, encoding="utf-8")).get("skip", []) if os.path.exists(path) else []


def cmd_skip(stage, on):
    if stage not in SKIPPABLE:
        sys.exit(f"건너뛸 수 있는 단계는 {' · '.join(SKIPPABLE)} 다" + (" — 목표는 건너뛸 것이 없다. 바로 `/gamedev-kit:cycle`" if stage == "goal" else ""))
    have = [s for s in skipped() if s != stage] + ([stage] if on else [])
    path = os.path.join(ROOT, STATE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"skip": [s for s in SKIPPABLE if s in have]}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{SKIPPABLE[stage]} 단계를 " + ("건너뛴다 — `status` 가 계속 적는다. 되돌리려면 `unskip`" if on else "다시 한다"))


def cmd_status():
    rel = gdd_path()
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        sys.exit(f"{rel} 이 없다 — `/gamedev-kit:init` 을 다시 돌리면 틀이 생긴다 (있는 파일은 건드리지 않는다)")
    cycle_dir = os.path.join(ROOT, CYCLE)
    cycles = sorted(n for n in os.listdir(cycle_dir) if re.match(r"\d+-.*\.md$", n)) if os.path.isdir(cycle_dir) else []
    parts, given, skip = sections(open(path, encoding="utf-8").read()), template_lines(), skipped()
    state = {k: filled(k, parts, given) for k in MUST + MAY + [ART]}
    empty = [k for k in MUST if state[k] is False]
    gone = [k for k in MUST + [ART] if state[k] is None]
    pictures = sorted(os.path.relpath(os.path.join(d, n), ROOT) for d, _s, names in os.walk(os.path.join(ROOT, CONCEPT))
                      for n in names if n.lower().endswith(PICTURES))
    lack = ([f"{rel} 의 {ART} 절이 비어 있다"] if state[ART] is False else []) + ([] if pictures else [f"{CONCEPT}/ 에 그림이 없다"])
    done = {"gdd": not empty or "gdd" in skip, "concept": not lack or "concept" in skip}
    mark = lambda stage: "건너뜀" if stage in skip else ("됨" if done[stage] else "할 것")

    if cycles:
        print(f"시작은 끝났다 — 사이클 문서가 있다 ({CYCLE}/{cycles[-1]}). 이어 가는 것은 `/gamedev-kit:cycle`")
    words = [("비어 있는 절", empty), ("글이 있는 절", [k for k in MUST if state[k]]), ("비어 있어도 되는 절", [k for k in MAY if state[k] is False]),
             ("틀의 제목이 없어 보지 못한 절", gone)]
    lines = [f"  [{mark('gdd')}] GDD ({rel}) — " + " · ".join(f"{label}: {' · '.join(names)}" for label, names in words if names),
             f"  [{mark('concept')}] 컨셉 — " + (" · ".join(lack) if lack else f"아트 방향이 적혀 있고 그림이 {len(pictures)}장 있다"),
             f"  [{'됨' if cycles else '할 것'}] 첫 목표 — " + (f"사이클 문서 {len(cycles)}개" if cycles else "사이클 문서가 아직 없다")]
    print("\n".join(lines))
    if skip:
        print("건너뛴 단계: " + " · ".join(SKIPPABLE[s] for s in skip) + " — 나중에 하려면 `unskip <단계>`")
    if cycles:
        return
    stage = next((s for s in ("gdd", "concept") if not done[s]), "goal")
    print(f"다음: {dict(SKIPPABLE, goal='첫 목표')[stage]} 단계 — 이 파일만 읽고 그 단계를 한다: {os.path.join(STAGES, stage + '.md')}")


def main():
    global ROOT
    args = sys.argv[1:]
    if "--root" in args:  # 테스트용
        i = args.index("--root")
        ROOT = os.path.abspath(args[i + 1])
        del args[i:i + 2]
        if not os.path.exists(os.path.join(ROOT, CONFIG_NAME)):
            sys.exit(f"{CONFIG_NAME} 을 찾지 못했다 — 키트가 아직 깔리지 않았다. 먼저 `/gamedev-kit:init`")
    else:
        ROOT = find_root(os.getcwd())
    if args == ["status"] or not args:
        cmd_status()
    elif len(args) == 2 and args[0] in ("skip", "unskip"):
        cmd_skip(args[1], args[0] == "skip")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
