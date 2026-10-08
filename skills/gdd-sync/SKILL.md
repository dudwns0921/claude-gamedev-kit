---
name: gdd-sync
description: >-
  Syncs the game design document (docs/GDD.md) and the game code in both directions. Matches the IDs in the GDD's 부록 A 동기화 표
  against `GDD: <ID>` markers in code to find 불일치, 미구현 and 고아 items, aligns values in the given direction (GDD→code or code→GDD),
  then updates the table's 코드 위치 and 상태 columns. kit.config.json sets the code extensions and symbol shapes.
  Always use this skill when: the user says "GDD 동기화", "문서랑 코드 맞춰", "gdd-sync", "GDD 반영",
  "설계대로 됐는지 확인", or asks to reflect a number in the GDD; a number, list or rule in the GDD was edited; an item in the GDD table
  (balance constant, enum, input mapping, HUD layout) was created or changed in code; a new system's implementation gave a GDD
  미구현 item matching code. Even if the user does not say "GDD", when the work changes the value of such an item,
  use this skill to update the table at the wrap-up step.
---

# gdd-sync

The GDD (`docs/GDD.md`) and the code record the same facts in two places. Change only one and the other starts lying,
and that lie comes back weeks later as "the doc says 90 seconds, why is it 60?". This skill compares the two and aligns them to one side.

Sync covers **only items with an ID in the GDD's 부록 A 동기화 표**. Tone, dialogue and art direction have no counterpart in code, so they are not handled.

## Arguments

| Call | Meaning |
|---|---|
| `/gamedev-kit:gdd-sync` | Comparison report only. Changes nothing |
| `/gamedev-kit:gdd-sync to-code` | GDD is the truth. Fix the code of 불일치 items to the GDD value |
| `/gamedev-kit:gdd-sync to-gdd` | Code is the truth. Fix the GDD of 불일치 items to the code value |
| `/gamedev-kit:gdd-sync <ID>` or `/gamedev-kit:gdd-sync to-code BAL.CYCLE.*` | Specific items only |

With no direction, produce the report and then **ask the user, for each 불일치, which side is right.** Whether the design intent changed or the value was
changed for convenience during implementation cannot be known from the code alone. If called in auto mode with no direction, write a recommended direction for each 불일치 alongside the report and stop.

## Procedure

### 1. Compare

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sync_report.py"
```

The script pairs each ID in the table with the `GDD: <ID>` marker in code and determines the status.

- **동기** — a numeric item (BAL, numbers in HUD) equals the GDD value. A range like `20~25` is 동기 if the value falls inside.
- **불일치** — the numbers differ. Needs human judgment.
- **동기?** — a marker exists on an item that cannot be compared automatically, such as an enum, rule or input. **Read the code yourself** and check it matches the table.
  E.g. an enum must match down to the order, and a rule is 동기 only if the condition check written in the table actually exists.
- **미구현** — no marker.
- **고아 표식** — code has `GDD: X` but the table has no X. A typo, or a sign that a row must be added to the table.
- **Location mismatch** — the marker is no longer at the code location written in the table. The file was moved or deleted.

`--json` output is easier to handle. `--only <ID>` shows a single item.

### 2. Judge

Open the code for each **동기?** item, one by one. If it matches, treat it as 동기; if not, as 불일치. Skimming here leaves in place
the enum order errors and missing rules the script cannot catch — this is where a human (or Claude) actually adds value in this skill.

**미구현** items are **not created**, even in to-code mode. Where the matching code should go is a design decision, and this skill is
a tool for aligning counterparts that already exist. However, if a natural place already exists (e.g. the balance value file exists and one BAL item
is missing), adding one line is fine. The boundary is "does it need a new file or a new system".

### 3. Apply

**to-code:** change the value on the marked line to the GDD value. For a range value (`20~25`), touch the code only if its value is outside the range; leave it if inside.
After changing, check whether anything using that value has derived calculations — if the table's 비고 says something like "A must equal B+C", align that too.
If the project uses a balance table (xlsx), after fixing the value file also align the table with `balance_table.py export` (balance-table skill).

**to-gdd:** change the table's 값 column to the code value, and **also fix the same number in the body text**. Go to the section number in the 출처 column (e.g. 4.4) and find where the value
appears in prose. Fixing only the table and leaving the body makes the table and body diverge again. Append `코드 기준 갱신 YYYY-MM-DD` to 비고
so that "why this value?" can be answered later.

When a value changes, other items derived from it and computed results in the body (sentences like "모두 잃기까지 약 18분") change with it.

### 4. Update the table

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sync_report.py" --write
```

Rewrites the 코드 위치 and 상태 columns to the current state. **Never touches the 값 column** — values were judged and fixed in step 3.
`동기?` is written to the table as `동기`, so for items judged 불일치 in step 2, fix the value before --write or write `불일치` in the table by hand.

### 5. Report

```
## GDD 동기화 결과
- 동기 N · 불일치 N(→ 처리 N) · 미구현 N · 고아 N
- 바꾼 것: <ID>: 50 → 45 (코드 기준, docs/GDD.md 4.4 본문도 수정)
- 판단 필요: <ID>: GDD 90 / 코드 60 — 난이도 테스트 중 바꾼 값으로 보임. 어느 쪽이 맞는지?
- 미구현 중 곧 필요한 것: <ID> (…)
```

## Marker rules in code

Put the marker on **the line that defines the value**, not a line that uses it. The script reads `= number` on the same line, so keep one per line.
Use the engine's comment syntax — the script only looks for the text `GDD: <ID>`.

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
When an item goes away, do not delete the row; write its 상태 as `폐기`.
