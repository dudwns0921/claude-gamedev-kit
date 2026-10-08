---
name: board
description: >-
  Draws the game's status board (항해도) — HTML pages made by a script. First screen: the stages of play in the order the player meets them,
  one card each, with how complete it is across 기능 · 아트 · 사운드 · 검증 (됨 · 임시 · 안 만듦 · 문제). A card opens that stage's page: GDD rows,
  art, sounds, checks, open questions, the cycle tasks that touched it. Everything is read from the GDD table, asset records, cycle and playtest
  documents. Once drawn, it redraws itself at the end of every turn.
  Use when the user says "현황판", "보드 보여줘", "지금 어디까지 됐어", "진행 상황 한눈에", "얼마나 만들었어", asks to see progress or the decisions so far
  as a page, or says the board looks stale or wrong.
---

# board

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/board.py"
```

It writes `docs/board/index.html` (and the stage pages beside it) and prints the path and one line of counts. **Relay that line and the path — do not read the HTML, and do not
read the GDD or cycle documents to describe the board.** The page is for the user's eyes; opening it costs nothing, reading it into the session does.

1. Run the script. Give the user the path (they open it in a browser and leave it open — the page reloads itself every 30 seconds).
2. The first run is the opt-in. From then on the plugin's hook redraws it when a turn ends and the GDD or a cycle document has changed. Nothing to do per turn.
3. To stop: delete `docs/board/`. The hook only redraws a board that exists.

## What it shows, and from where

Two kinds of page, written next to each other in `docs/board/`:

- `index.html` — **the chart (항해도).** One screen: the stages of play in the order the player meets them, one card each, with a completion ring
  and four meters. Nothing else. A card links to its stage page.
- `stage-N.html` — one stage: its GDD rows, art thumbnails (click to enlarge), sounds (playable), checks, open questions, and the cycle tasks that touched it.

The board shows the flow, not the history: answered decisions and the per-cycle record stay in the cycle documents.

Every state is read, never judged:

| Meter | 됨 / 임시 / 안 만듦 / 문제 come from | Kept right by |
|---|---|---|
| 기능 | `docs/GDD.md` appendix A — 동기 / — / 미구현 / 불일치 | `/gamedev-kit:gdd-sync` |
| 아트 · 사운드 | asset records in `assets/_gen` (a record whose file is in the game = 됨) and the `### 필요한 에셋` table of each cycle document (있는가: `없음` = 안 만듦, `임시 …` = 임시) | `/gamedev-kit:asset`, the designer agent |
| 검증 | each cycle that touched the stage (회고 · 배포 = 됨, 플레이 = 임시 "해 볼 차례", earlier = 안 만듦); playtest tasks (`[ ]` = 문제); the user's notes | `cycle.py`, `/gamedev-kit:playtest` |
| 못 정한 것 | unstruck bullets of the GDD section whose heading contains `미정`, and unanswered cycle decisions | the GDD, `cycle.py` |

**If the user says something on the board is wrong after playing** ("엔딩 소리가 이상해", "이건 아직 임시야"), do not edit the HTML. If it is a list of
problems, that is `/gamedev-kit:playtest`. If it is one remark, append one line to `docs/board-notes.md` and rerun the script:

```
- 이타카 · 엔딩 | 사운드 | 문제 | 엔딩 음악이 너무 일찍 끊긴다
```

Stage name (a part of it is enough) | 기능 · 아트 · 사운드 · 검증 | 문제 · 임시 · 됨 · 없음 | the user's words. Delete the line when it is fixed.

## The flow — set once per game

Without config there is one stage per GDD section, which is not the order of play. On the first run, read the GDD's structure section once and
write `board.flow` in `kit.config.json` — the stages a player goes through, in order — then show the user the list and ask if the stages are right.

```json
"board": {
  "loop_label": "구간 × 6",
  "flow": [
    { "name": "세이렌 구간", "about": "one line the card shows", "loop": true,
      "sections": ["4.1", "4.2"],            "ids": ["HUD.ROPE", "RULE.FAIL.*"],
      "assets": ["siren*", "wax_*"],         "words": ["밀랍", "선원"],
      "image": "docs/capture/siren.png" }
  ]
}
```

- `sections` — GDD sections whose table rows belong here. `ids` — row IDs (globs) that belong here whatever their section; wins over `sections`.
- `assets` — asset names (globs). An asset no stage names goes to the stage whose tasks mention it, else to "미분류".
- `words` — words that pull playtest tasks and open questions without a table ID to this stage.
- `image` — the card's picture (a capture). Without it the first art thumbnail is used. `loop` — consecutive stages that repeat get one bracket.
- Rows, assets and questions no stage claims are shown under "미분류" — nothing is dropped. When a new asset or GDD section lands there, add it to a stage.

- `"ignore"` (beside `flow`) — asset names (globs) not to count: planned in a cycle document, then dropped.
- "미분류" is not part of the completion %. It is a to-do for the flow: place what is there, or ignore it.

Other keys: `"out"`, `"gdd"`, `"cycles"`, `"playtests"`, `"gen"`, `"notes"`, `"reload_sec"`.

Add `docs/board/` to `.gitignore` — the pages are redrawn from the documents and carry a timestamp, so committing them only makes noise.

## Not covered

- Videos, and time and tokens per agent. The records exist (`video/`, session logs) but are not on the board yet.
- Whether a stage *needs* art or sound it does not have: an empty meter says "nothing was read", not "nothing is needed".
- It is a local file. Nothing is published or uploaded.
