# CLAUDE.md — <게임 이름>

Design document: [docs/GDD.md](docs/GDD.md)

## Language

Talk to the user in the language they write in, and write everything under `docs/` in that language too. The fixed headings and labels of the kit's document formats (cycle, playtest, GDD tables) stay exactly as the templates give them — scripts parse them.

## The GDD and the code must always agree

Items with an ID in the GDD Appendix A sync table (numbers · enums · rules · input · HUD) state the same fact in two places, the GDD and the code.
Change only one side and the other side lies. So:

- If you created or changed such a value **in the code** → at the end of the task run `/gamedev-kit:gdd-sync to-gdd` to bring the GDD (table and body) in line.
- If you changed such a value **in the GDD** → run `/gamedev-kit:gdd-sync to-code` to bring the code in line.
- If you do not know which side is right, look at the report only with `/gamedev-kit:gdd-sync` and ask the user.
- When defining a new value in code, add a `GDD: <ID>` marker to the defining line. If the item is not in the table, add a row to the table first.

This rule applies even when the user does not say "GDD". Even a task that changes one balance constant ends with the sync.

## Balance values are edited in the table

Balance numbers are edited in `data/balance.xlsx` (Excel). The game in development overrides the value file with the table's values,
and re-reads the table when it is saved — the game is not closed. The tool is the balance-table skill of the gamedev-kit plugin.

- Once values are settled, use the balance-table skill to `bake` → `/gamedev-kit:gdd-sync to-gdd`.
  **A release build does not read the table; it uses only the baked values.** `check` must pass before deploying.
- If you added a new value or hand-edited a number in the value file, `export`. export rewrites the table with the code's values —
  if there are values being edited in the table, bake first.
- Code that uses a value reads it from the value file every time it is used. Do not copy it into a variable at startup.

The files and line shapes the tools look at are in `kit.config.json`.

## Playtest feedback goes through a document

When the user plays and writes down several problems, hand them to `/gamedev-kit:playtest`. The analyst agent creates a work document in `docs/playtest/`,
and a developer agent takes each task one by one. This session only directs — it does not analyze or fix directly.

## A bundled goal goes through a cycle

A goal that involves several tasks, like "let's add ○○ this time", is handed to `/gamedev-kit:cycle`. The cycle document (`docs/cycle/`) accumulates
"목표" → "기획" → "디자인" → "작업" → "플레이" → "배포" → "회고". Rules · numbers · spatial dimensions are done by the systems designer agent,
what is seen and heard by the designer agent, and implementation by a developer agent per task.
The rules for screens and UI are in [docs/DESIGN.md](docs/DESIGN.md).

**The user decides.** Claude does not decide scope · taste · numbers · whether to ship on the user's behalf. Offer options and one recommendation and ask,
and write the answer in the cycle document's "결정" in the user's own words (verbatim).

## 3D assets and sound come from one paragraph

3D models are made with `/gamedev-kit:asset` — image → the user looks and approves → mesh → size and origin fitted, into the asset folder.
The art style is the single `<!-- asset-style -->` paragraph in `docs/DESIGN.md`, attached identically to every asset. Do not write a separate prompt per asset.
The user approves images. The record stays in `assets/_gen/<name>/asset.json`.

Sound effects · looping sounds · music are made with the same skill (ElevenLabs). The sound style is the `<!-- sound-style -->` paragraph.
Claude cannot hear sound — after making it, give the path and the user listens. The record is `assets/_gen/<name>/sound.json`.

## Keep sessions short

The longer the conversation, the more is re-read every turn, costing tokens and time. At the cycle's break points (where a decision was asked · when it is time to play · where the cycle ended)
move to a new session — `/gamedev-kit:cycle next` continues from the document. For work outside a cycle, leave a note with `/gamedev-kit:handoff` and in the new session
`/gamedev-kit:handoff resume`. The main session does not read cycle · playtest documents whole — that skill's script extracts the lines needed.

## Split what was learned in two

Of the pitfalls you tripped over and the verification methods you found, those specific to this game go in this file's "Pitfalls". Those that other games on the same engine would also hit
get one line in `docs/kit-feedback.md` (the cycle skill's `lesson`) — they go up to the kit and the next game starts with them.

## What goes outside

- Deployment is `/gamedev-kit:deploy` (butler → itch.io). Before uploading, show the target · version · size and get consent.
  After uploading, an itch.io devlog draft for that build is left in `docs/devlog/` — there is no API for posting, so the user pastes it.
- The butler login and the asset API keys live outside the repository. Do not write them in any file.
