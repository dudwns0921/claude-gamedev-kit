#!/usr/bin/env python3
"""Start — where an empty game with the kit installed stands on its way to the first cycle's goal. The state is read from the game's files — the answer is the same in any session.

  python3 start.py status          how far along GDD → concept → goal it is, and what the next stage is
  python3 start.py skip <stage>    skip that stage (gdd · concept). status keeps listing what was skipped — so it is not forgotten
  python3 start.py unskip <stage>  undo a skip

How a stage counts as done:
  gdd      in the GDD (gdd-sync.gdd, default docs/GDD.md), the body sections Overview · Game structure · Rules and systems · Scope have text.
           Tone · Sound · Open questions may stay empty (they are only listed). Lines that came with the template do not count as text.
           If such a title is not in the GDD at all (a GDD rewritten away from the template), it is not called empty — only reported.
  concept  the GDD's Art direction section has text, and docs/concept/ holds at least one picture (a reference the user put in is a picture too).
  goal     once a cycle document (docs/cycle/NN-*.md) exists, the start is over.
Skipped stages are recorded in docs/start/state.json.
A GDD written before the titles were English (개요 · 게임 구조 · …) is read the same — see the pairs below.
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
# A section is found by a word its title contains: (English, the older Korean form). Reports name it as the document has it.
MUST = [("Overview", "개요"), ("Game structure", "게임 구조"), ("Rules", "규칙"), ("Scope", "제작 범위")]  # the gdd stage is done when these have text
MAY = [("Tone", "톤"), ("Sound", "사운드")]             # only listed when empty
ART = ("Art direction", "아트 방향")                   # belongs to the concept stage
APPENDIX = ("Appendix", "부록")                        # from here on it is tables
# The one prose line of the Korean template — a section holding only this has nothing written yet
LEGACY_GIVEN = {"수치를 본문에 적을 때는 부록 A 의 같은 항목과 값이 같아야 한다."}
SKIPPABLE = {"gdd": "GDD", "concept": "concept"}
PICTURES = (".png", ".jpg", ".jpeg", ".webp")

ROOT = ""


def find_root(start):
    """Walk up from the current folder to the one holding kit.config.json. The tools live in the plugin; the game lives elsewhere."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            sys.exit(f"{CONFIG_NAME} not found — the kit is not installed yet. Run `/gamedev-kit:init` first")
        d = up


def gdd_path():
    cfg = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8"))
    return (cfg.get("gdd-sync") or {}).get("gdd") or "docs/GDD.md"


def sections(text):
    """(title, body lines) for each `## ` section of the body. From the appendix on it is tables — not looked at."""
    out = []
    for line in text.split("\n"):
        if line.startswith("## "):
            title = re.sub(r"^\d+\.\s*", "", line[3:].strip())
            if title.startswith(APPENDIX):
                break
            out.append((title, []))
        elif out:
            out[-1][1].append(line.strip())
    return out


def template_lines():
    """Lines that come with the template — a section holding only these has nothing written yet."""
    path = os.path.join(KIT, "templates", "GDD.md")
    return LEGACY_GIVEN | ({line.strip() for line in open(path, encoding="utf-8")} if os.path.exists(path) else set())


def filled(forms, parts, given):
    """(the word as the document has it, whether that section has text). The English word and None if there is no such title."""
    for title, lines in parts:
        for word in forms:
            if word in title:
                return word, any(l and l != "---" and not l.startswith("<!--") and l not in given for l in lines)
    return forms[0], None


def skipped():
    path = os.path.join(ROOT, STATE)
    return json.load(open(path, encoding="utf-8")).get("skip", []) if os.path.exists(path) else []


def cmd_skip(stage, on):
    if stage not in SKIPPABLE:
        sys.exit(f"stages that can be skipped: {' · '.join(SKIPPABLE)}" + (" — the goal has nothing to skip. Go straight to `/gamedev-kit:cycle`" if stage == "goal" else ""))
    have = [s for s in skipped() if s != stage] + ([stage] if on else [])
    path = os.path.join(ROOT, STATE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"skip": [s for s in SKIPPABLE if s in have]}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{SKIPPABLE[stage]} stage: " + ("skipped — `status` keeps listing it. To undo, `unskip`" if on else "back on"))


def cmd_status():
    rel = gdd_path()
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        sys.exit(f"{rel} not found — run `/gamedev-kit:init` again and the template appears (existing files are not touched)")
    cycle_dir = os.path.join(ROOT, CYCLE)
    cycles = sorted(n for n in os.listdir(cycle_dir) if re.match(r"\d+-.*\.md$", n)) if os.path.isdir(cycle_dir) else []
    parts, given, skip = sections(open(path, encoding="utf-8").read()), template_lines(), skipped()
    found = {k: filled(k, parts, given) for k in MUST + MAY + [ART]}
    state = {k: has for k, (_word, has) in found.items()}
    name = lambda keys: [found[k][0] for k in keys]
    empty = [k for k in MUST if state[k] is False]
    gone = [k for k in MUST + [ART] if state[k] is None]
    pictures = sorted(os.path.relpath(os.path.join(d, n), ROOT) for d, _s, names in os.walk(os.path.join(ROOT, CONCEPT))
                      for n in names if n.lower().endswith(PICTURES))
    lack = ([f"the {found[ART][0]} section of {rel} is empty"] if state[ART] is False else []) + ([] if pictures else [f"no pictures in {CONCEPT}/"])
    done = {"gdd": not empty or "gdd" in skip, "concept": not lack or "concept" in skip}
    mark = lambda stage: "skipped" if stage in skip else ("done" if done[stage] else "to do")
    plural = lambda n: "" if n == 1 else "s"

    if cycles:
        print(f"the start is over — a cycle document exists ({CYCLE}/{cycles[-1]}). Continue with `/gamedev-kit:cycle`")
    words = [("empty sections", name(empty)), ("sections with text", name(k for k in MUST if state[k])),
             ("sections that may stay empty", name(k for k in MAY if state[k] is False)),
             ("sections not checked for lack of the template's title", name(gone))]
    lines = [f"  [{mark('gdd')}] GDD ({rel}) — " + " · ".join(f"{label}: {' · '.join(names)}" for label, names in words if names),
             f"  [{mark('concept')}] concept — " + (" · ".join(lack) if lack else f"the art direction is written and there are {len(pictures)} picture{plural(len(pictures))}"),
             f"  [{'done' if cycles else 'to do'}] first goal — " + (f"{len(cycles)} cycle document{plural(len(cycles))}" if cycles else "no cycle document yet")]
    print("\n".join(lines))
    if skip:
        print("skipped stages: " + " · ".join(SKIPPABLE[s] for s in skip) + " — to do them later, `unskip <stage>`")
    if cycles:
        return
    stage = next((s for s in ("gdd", "concept") if not done[s]), "goal")
    print(f"next: {dict(SKIPPABLE, goal='first goal')[stage]} stage — read only this file and do that stage: {os.path.join(STAGES, stage + '.md')}")


def main():
    global ROOT
    args = sys.argv[1:]
    if "--root" in args:  # for the tests
        i = args.index("--root")
        ROOT = os.path.abspath(args[i + 1])
        del args[i:i + 2]
        if not os.path.exists(os.path.join(ROOT, CONFIG_NAME)):
            sys.exit(f"{CONFIG_NAME} not found — the kit is not installed yet. Run `/gamedev-kit:init` first")
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
