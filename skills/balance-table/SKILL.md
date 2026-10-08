---
name: balance-table
description: >-
  Edits balance numbers in an Excel table (data/balance.xlsx) and keeps it aligned with the balance value file in code. Code → table (export),
  table → code (bake), are they equal (check), serve the table to a running game (serve). Engine-agnostic
  (kit.config.json sets the shape of a value line). Use when the user says "밸런스 표", "엑셀",
  "표 구워줘", "bake", "표랑 코드 맞춰", "값이 게임에 안 먹어"; a value was added to the balance value file or
  a number was edited by hand (export); the user says a value was settled in the table (bake → gdd-sync to-gdd);
  before making a deploy build (check); a runtime that cannot read disk needs the table (serve).
---

# balance-table

Balance values live in two places. The **table** (`data/balance.xlsx`) is where people edit; the **value file** (code) is what the game uses.
During development the game reads the table and overrides the value file's values — values are tried without quitting the game.
Once a value is settled, bake the table into code. Deploy builds do not read the table and use only baked values.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" export   # code → table (rebuilds the table)
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" bake     # table → code
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" check    # if different, prints the differing lines and exits 1
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" serve    # serves the table at http://127.0.0.1:8765/balance
```

## When to do what

| What happened | What to do |
|---|---|
| A new value was added to the value file, or a number was edited by hand | `export`. Otherwise dev builds use the table's old value |
| The user settled a value in the table | `bake` → `/gamedev-kit:gdd-sync to-gdd` |
| Making a deploy build | `check` must pass. Put it in the build script |
| The GDD was edited and `/gdd-sync to-code` changed the value file | `export` |

**export rewrites the table with the code values.** Any values being edited in the table are lost — before export, run `check` to see whether any values differ,
and if so ask the user whether to bake first.

## Value file rules

- One value per line, one number. A `GDD: <ID>` marker at the end of the line. The description comment directly above the line becomes the table's 설명 column.
- Names are uppercase with underscores (`NOISE_RUN_PER_SEC`). They must equal the 이름 in column A of the table.
- Write floats with a decimal point (`4.0`). A value written without one is treated as an integer, and bake stops if the table has a decimal for it.
- Lines not determined by a single number (expressions, arrays, strings) do not go in the table. Compute derived values in code.
- The `balance-table.line` regex in `kit.config.json` sets what a line looks like.

## Table rules

- Only column A 이름 and column B 값 are read. The other columns (코드값, 분류, GDD ID, 설명) are for people.
- Names that exist only in the table are ignored. Non-numeric cells are skipped too.
- For values used only at start (starting crew count etc.), saving does not change a run in progress — they apply from the next run.

## Reloading while running (differs per engine)

`/gamedev-kit:init` installs the runtime template files into the game repository (the plugin's `engines/<engine>/files/`).

- **Godot** — the game reads the table file directly (`game/config/balance_table.gd`, `game/debug/balance_watch.gd`).
  On save it reloads within 0.5 s and shows the changed values on screen. Headless runs do not read the table and use baked values.
- **Runtimes that cannot read disk** — `serve` serves the table as JSON: `{"stamp": "<save time>", "values": {"name": number}}`. 503 while a save is in progress.
  The game fetches it periodically and overrides.

Code that uses a value reads it from the value file every time. Storing it in a variable at startup holds on to the old value.

## Deploy build check

The plugin is installed in a folder managed by Claude, so the game's build script cannot call this script by path.
If the build script must run `check`, copy `scripts/balance_table.py` into the game repository's `tools/` and call that
(it runs as a single file with no external packages). Re-copy the copy when the plugin is updated.
