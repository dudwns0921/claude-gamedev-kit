---
name: gdd-sync
description: >-
  Syncs the game design document (docs/GDD.md) and the game code in both directions. Matches the IDs in the GDD's Appendix A sync table
  against `GDD: <ID>` markers in code to find mismatch, missing and orphan items, aligns values in the given direction (GDD→code or code→GDD),
  then updates the table's Code location and State columns. kit.config.json sets the code extensions and symbol shapes.
  Always use this skill when: the user says "GDD 동기화" ("sync the GDD"), "문서랑 코드 맞춰" ("align the doc and the code"), "gdd-sync",
  "GDD 반영" ("put it in the GDD"), "설계대로 됐는지 확인" ("check it was built as designed"), or asks to reflect a number in the GDD;
  a number, list or rule in the GDD was edited; an item in the GDD table
  (balance constant, enum, input mapping, HUD layout) was created or changed in code; a new system's implementation gave a GDD
  missing item matching code. Even if the user does not say "GDD", when the work changes the value of such an item,
  use this skill to update the table at the wrap-up step.
---

# gdd-sync

The GDD (`docs/GDD.md`) and the code record the same facts in two places. Change only one and the other starts lying,
and that lie comes back weeks later as "the doc says 90 seconds, why is it 60?". This skill compares the two and aligns them to one side.

Sync covers **only items with an ID in the GDD's `Appendix A. Sync table`**. Tone, dialogue and art direction have no counterpart in code, so they are not handled.

The words below are the ones the script writes. A GDD made before they were English has `부록 A` for the heading, 값 · 출처 · 코드 위치 · 상태 · 비고 for the columns
and 동기 · 불일치 · 미구현 · 폐기 for the states — the script reads those the same. Leave such a document's words alone; a state cell the script rewrites comes out in English, and a mixed table is fine.

## Arguments

| Call | Meaning |
|---|---|
| `/gamedev-kit:gdd-sync` | Comparison report only. Changes nothing |
| `/gamedev-kit:gdd-sync to-code` | GDD is the truth. Fix the code of mismatch items to the GDD value |
| `/gamedev-kit:gdd-sync to-gdd` | Code is the truth. Fix the GDD of mismatch items to the code value |
| `/gamedev-kit:gdd-sync <ID>` or `/gamedev-kit:gdd-sync to-code BAL.CYCLE.*` | Specific items only |

With no direction, produce the report and then **ask the user, for each mismatch, which side is right.** Whether the design intent changed or the value was
changed for convenience during implementation cannot be known from the code alone. If called in auto mode with no direction, write a recommended direction for each mismatch alongside the report and stop.

## Procedure

### 1. Compare

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sync_report.py"
```

The script pairs each ID in the table with the `GDD: <ID>` marker in code and determines the status.

- **synced** — a numeric item (BAL, numbers in HUD) equals the GDD value. A range like `20~25` is synced if the value falls inside.
- **mismatch** — the numbers differ. Needs human judgment.
- **synced?** — a marker exists on an item that cannot be compared automatically, such as an enum, rule or input. **Read the code yourself** and check it matches the table.
  E.g. an enum must match down to the order, and a rule is synced only if the condition check written in the table actually exists.
- **missing** — no marker.
- **Orphan markers** — code has `GDD: X` but the table has no X. A typo, or a sign that a row must be added to the table.
- **Location mismatch** — the marker is no longer at the code location written in the table. The file was moved or deleted.

`--json` output is easier to handle. `--only <ID>` shows a single item.

### 2. Judge

Open the code for each **synced?** item, one by one. If it matches, treat it as synced; if not, as mismatch. Skimming here leaves in place
the enum order errors and missing rules the script cannot catch — this is where a human (or Claude) actually adds value in this skill.

**missing** items are **not created**, even in to-code mode. Where the matching code should go is a design decision, and this skill is
a tool for aligning counterparts that already exist. However, if a natural place already exists (e.g. the balance value file exists and one BAL item
is missing), adding one line is fine. The boundary is "does it need a new file or a new system".

### 3. Apply

**to-code:** change the value on the marked line to the GDD value. For a range value (`20~25`), touch the code only if its value is outside the range; leave it if inside.
After changing, check whether anything using that value has derived calculations — if the table's Note says something like "A must equal B+C", align that too.
If the project uses a balance table (xlsx), after fixing the value file also align the table with `balance_table.py export` (balance-table skill).

**to-gdd:** change the table's Value column to the code value, and **also fix the same number in the body text**. Go to the section number in the Source column (e.g. 4.4) and find where the value
appears in prose. Fixing only the table and leaving the body makes the table and body diverge again. Append `updated from code YYYY-MM-DD` to Note
so that "why this value?" can be answered later.

When a value changes, other items derived from it and computed results in the body (sentences like "about 18 minutes until everything is lost") change with it.

### 4. Update the table

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sync_report.py" --write
```

Rewrites the Code location and State columns to the current state. **Never touches the Value column** — values were judged and fixed in step 3.
`synced?` is written to the table as `synced`, so for items judged mismatch in step 2, fix the value before --write or write `mismatch` in the table by hand.

### 5. Report

```
## GDD sync result
- synced N · mismatch N (→ handled N) · missing N · orphan N
- Changed: <ID>: 50 → 45 (from code; the body of docs/GDD.md 4.4 fixed too)
- Needs a decision: <ID>: GDD 90 / code 60 — looks like a value changed while testing difficulty. Which side is right?
- Missing and needed soon: <ID> (…)
```

## Marker rules in code

Put the marker on **the line that defines the value**, not a line that uses it. The script reads `= number` on the same line, so keep one per line.
Use the engine's comment syntax — the script only looks for the text `GDD: <ID>`.
Do not put a HUD row's marker on lines that define numeric constants: each such line is compared with the first number in that row's value cell,
so a row marked on several numbers reads as mismatch. And `--write` does not clear a mismatch that was typed into the table by hand — fix that cell yourself.

```gdscript
static var CREW_START := 12  # GDD: BAL.CREW.START
enum CyclopsState { ACTIVE, EAT, DIGEST }  # GDD: ENUM.CYCLOPS_STATE
func _can_stab() -> bool:  # GDD: RULE.STAB.WINDOW
```

```lua
Balance.CREW_START = 12 -- GDD: BAL.CREW.START
local CyclopsState = { "Active", "Eat", "Digest" } -- GDD: ENUM.CYCLOPS_STATE
local function canStab() -- GDD: RULE.STAB.WINDOW
```

```csharp
public static int CREW_START = 12; // GDD: BAL.CREW.START
public enum CyclopsState { Active, Eat, Digest } // GDD: ENUM.CYCLOPS_STATE
bool CanStab() // GDD: RULE.STAB.WINDOW
```

A rule (RULE.*) goes above the function or branch that decides it. An input (INPUT.*) goes on the config or code that maps the input.
`gdd-sync.code_ext` in `kit.config.json` sets which extensions are scanned.

If a new item was created in code first, add a row to the GDD table and write one line in the body too. Name the ID in `category.target.attribute` form,
alongside existing ones. Never change an ID once assigned — it is embedded in both code and document, so changing it means fixing both.
When an item goes away, do not delete the row; write its State as `retired`.
