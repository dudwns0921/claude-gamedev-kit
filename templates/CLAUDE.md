# CLAUDE.md — <게임 이름>

Design document: [docs/GDD.md](docs/GDD.md)

## Language

Talk to the user in the language they write in, and write everything under `docs/` in that language too. The fixed headings and labels of the kit's document formats (cycle, playtest, GDD tables) stay exactly as the templates give them — scripts parse them.

## The GDD and the code must always agree

Items with an ID in the GDD Appendix A sync table (numbers · enums · rules · input · HUD) state the same fact in two places. Change one side and the other lies — even when the user does not say "GDD", even for one balance constant:

- Changed **in the code** → end the task with `/gamedev-kit:gdd-sync to-gdd`. Changed **in the GDD** → `/gamedev-kit:gdd-sync to-code`. Not sure which side is right → `/gamedev-kit:gdd-sync` (report only) and ask.
- A new value in code gets a `GDD: <ID>` marker on its defining line, and a row in the table first.

## Balance values are edited in the table

Balance numbers are edited in `data/balance.xlsx`. The game in development reads the table over the value file and re-reads it on save; **a release build uses only the baked values.**

- Code reads a value from the value file every time it is used — never copied into a variable at startup.
- Values settled in the table → balance-table `bake`, then `/gamedev-kit:gdd-sync to-gdd`. `check` must pass before deploying.
- Added a value or hand-edited a number in the value file → `export`. **export overwrites the table with the code's values** — if values are being edited in the table, bake first.

## Which skill takes what

This session directs; the skills and their agents do the work. Each skill's own document has the procedure — do not improvise it from here.

| When | Goes to |
|---|---|
| A goal of several tasks ("let's add ○○ this time") | `/gamedev-kit:cycle` — one document in `docs/cycle/` from 목표 to 회고 |
| Several problems written down after playing | `/gamedev-kit:playtest` — do not analyze or fix them here |
| A 3D model or a sound | `/gamedev-kit:asset` — the style is the one paragraph in [docs/DESIGN.md](docs/DESIGN.md); do not write a style per asset |
| A trailer shot or a cutscene clip | `/gamedev-kit:video` |
| "Where are we" | `/gamedev-kit:board` — do not read or edit `docs/board/`; fix the GDD table or the cycle document and it follows |
| Building and uploading | `/gamedev-kit:deploy` |
| Moving to a new session | `/gamedev-kit:cycle next` inside a cycle, `/gamedev-kit:handoff` outside one |

## The user decides

Claude does not decide scope · taste · numbers · whether to ship. Offer options with one recommendation, ask, and write the answer in the cycle document's "결정" in the user's own words.
Only the user can see and hear: after making an image, a sound or a clip, give the path and wait — do not say it came out well.

The one exception is auto mode, and only when the user asks for it (`/gamedev-kit:cycle auto …`): the user's voice decides in their place up to the point of playing, every such decision is marked `[~]` and waits for them, and it never ships, spends money or starts a second cycle.
The voice (how this user decides) is kept outside this repository and works unseen — do not show or mention it unless a cycle ends or the user asks.

## Keep sessions short

The longer the conversation, the more is re-read every turn. Move to a new session at a cycle's break points (decisions asked · time to play · cycle ended).
Do not read cycle · playtest documents whole — that skill's script extracts the lines needed.

## What was learned, and what goes outside

- A pitfall or a way to verify that is specific to this game goes in this file's "Pitfalls"; one that another game on the same engine would hit gets a line in `docs/kit-feedback.md` (the cycle skill's `lesson`).
- Before anything is uploaded, show the target · version · size and get consent. Logins and API keys live outside the repository — do not write them in any file.
