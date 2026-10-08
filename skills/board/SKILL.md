---
name: board
description: >-
  Draws the game's status board — one HTML page made by a script from the GDD sync table and the cycle documents. Top half: how much of what
  was designed is built, per GDD section (동기 · 불일치 · 미구현 · 폐기), each row tagged with the cycle tasks that touched it. Bottom half: how the work
  went, per cycle — stage, the user's decisions in their own words, tasks by wave. Once drawn, it redraws itself at the end of every turn.
  Use when the user says "현황판", "보드 보여줘", "지금 어디까지 됐어", "진행 상황 한눈에", "얼마나 만들었어", asks to see progress or the decisions so far
  as a page, or says the board looks stale or wrong.
---

# board

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/board.py"
```

It writes `docs/board/index.html` and prints the path and one line of counts. **Relay that line and the path — do not read the HTML, and do not
read the GDD or cycle documents to describe the board.** The page is for the user's eyes; opening it costs nothing, reading it into the session does.

1. Run the script. Give the user the path (they open it in a browser and leave it open — the page reloads itself every 30 seconds).
2. The first run is the opt-in. From then on the plugin's hook redraws it when a turn ends and the GDD or a cycle document has changed. Nothing to do per turn.
3. To stop: delete `docs/board/`. The hook only redraws a board that exists.

## What it shows, and from where

| On the page | Source | Kept right by |
|---|---|---|
| Section cards, state bars, rows | `docs/GDD.md` appendix A — the 출처 column groups rows under that GDD section | `/gamedev-kit:gdd-sync` |
| `07·T3` tags on a row | the `- **GDD**:` line of each cycle task | the developer agent's plan |
| Stage strip, decision cards, task columns | `docs/cycle/NN-*.md` — `단계:`, `## 결정`, `### [x] T1.`, `## 순서` | `cycle.py` |

**The board does not judge.** States are the ones written in the GDD table; it does not scan code. If the user says a number looks wrong,
the table is stale — run `/gamedev-kit:gdd-sync`, not this. If a decision or task is missing, it is missing from the cycle document.

## Config

None needed. To move things, in `kit.config.json`:

```json
"board": { "out": "docs/board/index.html", "gdd": "docs/GDD.md", "cycles": "docs/cycle", "reload_sec": 30 }
```

Add `docs/board/` to `.gitignore` — the page is redrawn from the documents and carries a timestamp, so committing it only makes noise.

## Not covered

- Asset and video thumbnails, and time and tokens per agent. The records exist (`assets/_gen`, `video/`, session logs) but are not on the board yet.
- It is a local file. Nothing is published or uploaded.
