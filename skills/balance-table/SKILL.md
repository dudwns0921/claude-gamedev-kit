---
name: balance-table
description: >-
  Keeps the balance table (data/balance.xlsx) — an Excel sheet where the game's balance numbers are seen at a glance — in step with the balance value file
  in code, which is what the game runs on. Code → table (export; a hook does it whenever the value file changes), table → code (bake),
  are they equal (check). Engine-agnostic (kit.config.json sets the shape of a value line). Use when the user says "밸런스 표" ("balance table"), "엑셀" ("Excel"),
  "표 구워줘" ("bake the table"), "bake", "표랑 코드 맞춰" ("align the table and the code"), "표 보여줘" ("show me the table"); the user says they changed a number in the table
  (bake → gdd-sync to-gdd); the table does not exist yet or looks out of date (export); before making a deploy build (check).
---

# balance-table

The game runs on the **value file** (code). The **table** (`data/balance.xlsx`) is that file's numbers on one sheet — every value side by side,
with its group, GDD ID and note — for the user to look over, sort and filter. A number the user changes in the table reaches the game when it is baked into the value file.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" export   # code → table (rebuilds the table)
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" bake     # table → code
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" check    # if different, prints the differing lines and exits 1. Also names values that are only in code (→ export)
```

**The table keeps itself current.** Once it exists, the plugin's hooks run `export --if-stale` after each edit or command, when an agent finishes and when a turn ends:
the table is rewritten when the value file is newer than it. Nothing to do per turn. The status board's first screen has a "Balance table →" tile that opens the file.

A table the script writes carries the value file's modification time, so file times say where the two stand: the same time — in step; the table newer —
the user saved it in the spreadsheet and has not baked, or the table was never stamped (the hook leaves it alone, and the board's tile stops saying "in step"; `check` tells which); the value file newer — the hook rewrites the table.

## When to do what

| What happened | What to do |
|---|---|
| There is no table yet | `export` — the first run is the opt-in; the hook only rewrites a table that exists |
| The user changed a number in the table | `bake` → `/gamedev-kit:gdd-sync to-gdd` |
| The value file is about to be edited (a task, `/gdd-sync to-code`) and the table may hold unbaked changes | `check` first. If it differs, ask the user whether to bake |
| Making a deploy build | `check` must pass. Put it in the build script |

**export rewrites the table with the code values**, and an edit to the value file makes the hook do exactly that. Numbers the user changed in the table and has not baked
are lost then — that is why `check` comes before editing the value file.

## Value file rules

- One value per line, one number. A `GDD: <ID>` marker at the end of the line. The description comment directly above the line becomes the table's Note column.
- Names are uppercase with underscores (`NOISE_RUN_PER_SEC`). They must equal the Name in column A of the table.
- Write floats with a decimal point (`4.0`). A value written without one is treated as an integer, and bake stops if the table has a decimal for it.
- Lines not determined by a single number (expressions, arrays, strings) do not go in the table. Compute derived values in code.
- The `balance-table.line` regex in `kit.config.json` sets what a line looks like.

## Table rules

- Only column A Name and column B Value are read. The other columns (Code value, Group, GDD ID, Note) are for people.
  Reading goes by column, not by the header text — a table made with the older Korean header row (이름 · 값 · …) works as it is; the next `export` or `bake` rewrites the header in English.
- Names that exist only in the table are ignored.
- The game does not read the table. A number changed there takes effect after `bake`, on the next run of the game.

## Deploy build check

The plugin is installed in a folder managed by Claude, so the game's build script cannot call this script by path.
If the build script must run `check`, copy `scripts/balance_table.py` into the game repository's `tools/` and call that
(it runs as a single file with no external packages). Re-copy the copy when the plugin is updated.
