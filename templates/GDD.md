# <game name> — Game design document

## 1. Overview

## 2. Game structure

## 3. Tone

## 4. Rules and systems

A number written in the body must have the same value as the same item in Appendix A.

## 5. Art direction

## 6. Sound

## 7. Scope

## 8. Open questions

Only what is not decided yet, one `- ` line each. An answered one is struck (`~~…~~ → <answer>`) and its answer written in the body above.

---

## Appendix A. Sync table

This table holds only the items where **the GDD and the code must have the same value**. What has no counterpart in code — tone, dialogue, art direction — is not here.
The `gdd-sync` skill looks at this table only. Change a number in the body and this table changes with it; change this table and the body changes with it.

**Rules**

- An ID has the form `category.target.attribute` and never changes once given. When an item goes away, do not delete the row — write `retired` as its state.
- A code location has the form `file:symbol`. Leave it as `—` while there is no implementation. The skill fills it in.
- In code, the line that defines the value carries a `GDD: <ID>` comment. The skill finds the counterpart by this comment.
- State: `synced` (both sides equal) · `missing` (no code) · `mismatch` (they differ, a person decides) · `retired`.
- A value may be a range (`20~25`). A code value inside it is synced.

### A.1 Balance numbers

| ID | Value | Source | Code location | State | Note |
|---|---|---|---|---|---|
| BAL.PLAYER.HP | 100 | 4 | — | missing | example — starting health |
| BAL.PLAYER.WALK_SPEED | 4~16 | 4 | — | missing | example — walking speed. Written as a range, any value inside it is synced |
| BAL.COIN.VALUE | 5 | 4 | — | missing | example — the value of one coin |

### A.2 Enums (what a list holds, and in what order)

| ID | Value | Source | Code location | State | Note |
|---|---|---|---|---|---|

### A.3 Rules (condition → result)

| ID | Rule | Source | Code location | State | Note |
|---|---|---|---|---|---|

### A.4 Input

| ID | Value | Source | Code location | State | Note |
|---|---|---|---|---|---|

### A.5 HUD layout

| ID | Value | Source | Code location | State | Note |
|---|---|---|---|---|---|
