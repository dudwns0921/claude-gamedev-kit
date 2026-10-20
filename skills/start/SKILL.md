---
name: start
description: >-
  Takes a game from "the kit is installed, nothing is decided" to the first cycle: writes the GDD with the user by interview (one loop → one question per turn),
  agrees on the look with concept images, proposes the first cycle's goal, and hands over to the CEO (the ceo skill — or the cycle skill, for one who builds by hand). Where the game stands is read from its files,
  so any session can pick it up. Use when the user says "새 게임 시작하자" ("let's start a new game"), "게임 하나 만들자" ("let's make a game"), "GDD 같이 쓰자" ("let's write the GDD together"),
  "기획부터 하자" ("start with the design"), "컨셉 잡자" ("let's settle the concept"), "컨셉 그림 그려줘" ("draw a concept picture"),
  "첫 사이클까지 가자" ("take it to the first cycle"), "뭐부터 하지" ("where do I start"), or "어디까지 했지" ("how far did we get") · "이어서 하자" ("let's continue") before any cycle document exists; right after `/gamedev-kit:init` finishes.
  Not when a cycle document already exists (→ ceo, or cycle by hand), and not when `kit.config.json` is missing (→ init first, which comes back here with what the user said). Not for a 3D model, a sprite or a sound (→ asset).
---

# start

Three stages, in order: **GDD → concept → first goal.** Each ends in files of the game (`docs/GDD.md`, `docs/concept/`, `docs/DESIGN.md`), so nothing lives only in this conversation.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/start.py" status          # where the game stands and which stage is next
python3 "${CLAUDE_SKILL_DIR}/scripts/start.py" skip <gdd|concept>     # the user does not want this stage now
python3 "${CLAUDE_SKILL_DIR}/scripts/start.py" unskip <gdd|concept>
```

1. **Run `status`.** It says to run `/gamedev-kit:init` if the kit is not installed, and the CEO if a cycle document exists — go there and stop here.
2. **Read only the stage file it names** (`stages/gdd.md` · `stages/concept.md` · `stages/goal.md`) and do that stage. Do not read the other two — each is read when its stage begins.
3. **The user may skip a stage** ("컨셉은 나중에" — "the concept later", "GDD 는 이미 머리에 있어" — "the GDD is already in my head"). Run `skip`, say in one line what the later stages will lack because of it, and go on.
   `status` keeps listing skipped stages — mention them when the goal stage comes, once.
4. **At the end of each stage, say in one line that this is a good place to `/clear`**: the state is in the files, so `/clear` then `/gamedev-kit:start` continues — in the same window.
   An interview grows the conversation fast, and everything re-read each turn costs — do not carry a finished stage into the next one unless the user wants to go on.

What this skill does not do: it does not create a cycle document (the cycle skill's `new` does), does not write code, and does not make planning documents of its own —
the GDD is the record of what was decided.
