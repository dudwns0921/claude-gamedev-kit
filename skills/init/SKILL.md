---
name: init
description: >-
  Sets a game repo up for gamedev-kit, from an empty folder if need be: asks where the game will be played (a phone · a computer · a browser — one or several) and so which engine (the editor and the engine project are made with the engine's own tools),
  then installs the files the kit uses — engine config (kit.config.json), GDD template, CLAUDE.md rules,
  the balance value file, the engine's other template files, the engine's .gitignore lines. Ends by offering the dashboard of all games (one question, only where Node.js is) and goes on into the GDD with what the user said about the game.
  Also aligns the kit rules in CLAUDE.md after the kit bumps its version (rules). Use when starting a new game — "이런 게임 만들고 싶어" ("I want to make a game like …"), "게임 만들자" ("let's make a game") in a folder without kit.config.json — on "gamedev-kit 깔아줘" ("install gamedev-kit"),
  "엔진 프로젝트 만들어줘" ("create the engine project"), "키트 규칙 맞춰줘" ("align the kit rules"), "init rules", "GDD 동기화 세팅" ("set up GDD sync"),
  "밸런스 표 세팅" ("set up the balance table"), or when gdd-sync, balance-table or start says it cannot find kit.config.json.
---

# init

Run at the game repo root. Existing files are not touched, so re-running is safe.

**Re-running in an already-installed project** overwrites nothing and does three things: creates document templates the kit has gained since (e.g. `docs/DESIGN.md`) if missing,
reports config sections missing from `kit.config.json` (copying them in is your job — it does not edit the file), and skips the engine template files (the value file and what else the engine brings).
Why it skips the engine template files: in a project that moved the value file or deliberately deleted a template, creating the same file again makes a duplicate. To really reinstall, `--files`.
It does not touch CLAUDE.md, and if the kit rules are an old version it says so — aligning them is "Aligning the kit rules" below.

## Procedure

1. **Which engine.**

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" --detect
   ```

   If the folder is already an engine project (or the kit is already installed), it names the engine — use it and do not ask.
   Otherwise it lists each engine with where its games can be played, what it suits and when to pick it. Ask **about the player, not the tool**, in one decision:
   where will people play it — a phone (Android · iPhone), a computer (Steam), a browser (shared by a link) — **more than one may be picked**, and
   **ask whether a store or a computer may come later even if it starts in a browser** (it moves the choice: a browser-only engine cannot follow there without a wrapper).
   Then recommend the engine whose `pick it when` fits the places and the game the user described (2D or 3D, how large), say why in one line, and name the alternative.
   Say the costs of the places picked once: an iPhone build needs a Mac with Xcode, and each store has its own developer account and fee — uploading is not the kit's (the user asks Claude Code when the game is ready).
   If the user already said where it is played or which engine ("a Godot one", "for Android"), do not ask — say in one line which engine that means and go on.
   If the repo belongs to any other engine, do not install and say so.
   **Keep what the user said about the game** — it is the first answer of the GDD interview that follows (step 9), not to be asked again.

2. **The engine project — only if step 1 found none.** Finding the editor and creating the project are not the kit's: do them with the engine's own tools
   (its command line, or its MCP server if one is connected). Installing the editor, its build modules for the places picked and signing in to its hub are the user's —
   a download of several GB, so say what to install and wait; do not run an install unasked. Where the editor lives on this machine goes under `## This game's rules` in CLAUDE.md (step 4).

3. **Install.**

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" <engine>
   ```

   Installed: `kit.config.json` · `docs/GDD.md` · `docs/DESIGN.md` · `CLAUDE.md` · the engine's template files (the value file and what else the engine brings) · `.gitignore` lines (the Excel lock file and what the engine generates — lines already present are not repeated; `--gitignore` adds only those).

   Then let the engine read what was installed once (compile · import — the engine rules' "Running" says how), so the files it creates beside them (`.meta`, import caches) appear; fix any error before going on.

4. **If CLAUDE.md was newly created**, fill in `<game name>` (and the title of `docs/GDD.md` — a CLAUDE.md or GDD made by an older kit has `<게임 이름>` there), and under the existing `## This game's rules` heading at its end write where the editor lives on this machine
   and where the game is played — do not add a second heading. If CLAUDE.md already existed, do not touch it —
   if it reports no kit rules block, ask the user whether to do "Aligning the kit rules" below.

5. **If the project structure differs from the template, align it.** To keep the value file elsewhere, move the file and edit `balance-table.code` in
   `kit.config.json`. Replace the three example value lines in the value file with the game's values.

6. **Create the table and check.** Create `data/balance.xlsx` with the balance-table skill's `export`, and check with the gdd-sync skill that
   a report comes out. It works if the GDD template's example row (BAL.PLAYER.HP) pairs with the value file's example value and shows as `synced`.

7. **Assets are the user's.** The kit makes none: the cycle runs on placeholders, and the user's files — made however they like (their `ways.md`) — go in the slots.

8. **The dashboard — one question, at most.** The dashboard shows every game on this machine on one page (optional; it needs git and Node.js).
    Run `python3 "${CLAUDE_SKILL_DIR}/../board/scripts/board.py" serve --status` and `command -v node git`, then:
    - **Running already** (another game started it): ask "Show this game on the dashboard too?" — yes → run `serve` (it joins the game and sends its board in seconds).
    - **Not running, Node.js and git present**: ask "Start a dashboard that shows all your games on one page? (local, about a minute the first time)" — yes → run `serve`
      and relay its last lines (where it is, how to reach it from another device).
    - **Node.js or git missing**: do not ask. Say in one line that a dashboard of all games exists for later (`/gamedev-kit:board`, needs Node.js).
    A no is final for this init; nothing else in the kit depends on it.

9. **Go on to the game.** The kit is installed and the game is still empty. If the user came in with a game in mind ("I want to make a game where …"),
    go straight on to the start skill — what they said is its first answer: say it back as the loop it describes and ask only what it leaves open.
    If they only asked to install, say in one line that saying what game they want (or `/gamedev-kit:start`) takes it from here — GDD → concept → the first cycle's goal.

## Aligning the kit rules (`/gamedev-kit:init rules`)

In the game's CLAUDE.md, the kit's part is the single span between `<!-- gamedev-kit start … -->` and `<!-- gamedev-kit end -->` (a block written by an older kit has `gamedev-kit 시작` / `gamedev-kit 끝` there — it is found the same way, and gets the new markers when it is replaced) — it holds the common rules (GDD sync · balance table · cycle …) and
that engine's rules (Running · Verification · Pitfalls), and ends with two import lines — `@~/.config/gamedev-kit/rules/rules.md` and `…/rules-<engine>.md` — that bring in the user's own rules
from earlier games (the feedback skill's ledger; the files live outside the game, and init makes them when they are missing).
The first time a session opens the game, Claude Code asks the user to allow an import from outside the project — say in one line that it is their own rules file.
When the kit bumps its version, replace only that span wholesale. **Outside the block is the game's and is not touched.**
At session start a hook looks at the block: **an old version it replaces by itself** (only the block, and only if nobody edited inside it) and says so in one line; a missing or hand-edited block it only reports. So after the kit is updated there is normally nothing to run.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" <engine> --rules
```

- **If the block is an old version**, only the block changes. Done. See what changed with `git diff CLAUDE.md` and relay it in one or two lines.
- **If there is no block** (a project installed before this scheme), it is appended at the end. Existing text stays, so sections copied from an old version remain outside the block and **the same thing is said twice**.
  The script lists the overlapping headings. Compare those sections with the block one by one: delete outside what says the same as the block, and keep outside only what this game
  rewrote or added (gather it under "This game's rules"). **Before deleting, show the user what is deleted and what is kept, and get an answer** — the user wrote that text.
  Overlap between the engine rules' pitfalls and the game's "Pitfalls" is handled the same way.
- **If the inside of the block was edited by hand**, the script stops. Move the edited text outside the block and run again — text outside takes precedence over the block. `--force` only when the user says it may be discarded.
- If the user does not want the block, put `"init": { "rules": false }` in `kit.config.json` — the hook neither replaces nor reports.

## Adding an engine (plugin-side work)

In `engines/<name>/` put `kit.config.json` (code extension · value-line regex · asset formats and folders), `CLAUDE.md` (the engine rules appended to the game's
CLAUDE.md), `files/` (files copied as-is into the game repo), `project.json` (how to recognise a project and when to pick the engine — read by `init.py`, not copied into the game;
its keys are listed at the top of `init.py`) and `gitignore` (lines appended to the game's `.gitignore`). `init.py` has no branch per engine — everything it needs is in those files.
Add a value file in that engine's syntax to `CODE` in `tests/test_tools.py` to check that the tools read and edit it.
