---
name: init
description: >-
  Sets a game repo up for gamedev-kit, from an empty folder if need be: asks which engine (Godot · Unity), finds the editor on this machine and the build modules it needs,
  creates the engine project when there is none, then installs the files the kit uses — engine config (kit.config.json), GDD template, CLAUDE.md rules,
  the balance value file, the engine's other template files, the engine's .gitignore lines. Ends by pointing to `/gamedev-kit:start`.
  Also aligns the kit rules in CLAUDE.md after the kit bumps its version (rules). Use when starting a new game, on "gamedev-kit 깔아줘" ("install gamedev-kit"),
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
   Otherwise ask the user **one question**: which of the engines it lists. If the repo belongs to any other engine, do not install and say so.

2. **The editor on this machine.**

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" <engine> --editor
   ```

   It prints the editor executable it found (the newest when several versions are installed) and whether the modules a build needs are there.
   When something is missing it prints exactly what to install and exits 1: **relay that to the user and wait.** Installing an editor or a module is a download of several GB
   and signing in to the engine's hub (license) is the user's — do not run an install command unasked, even though one is printed. After they say it is done, run `--editor` again.
   A missing build module does not block the next steps (it blocks building) — if the user wants to add it later, go on and say it is still to do.

3. **Create the engine project — only if step 1 found none.**

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" <engine> --create
   ```

   It works in a folder that already has `.git`, `docs/` and the like, and does nothing if the project is already there. It can take minutes; the editor must not have this folder open.

4. **Install.**

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" <engine>
   ```

   Installed: `kit.config.json` · `docs/GDD.md` · `docs/DESIGN.md` · `CLAUDE.md` · the engine's template files (the value file and what else the engine brings) · `.gitignore` lines (the Excel lock file and what the engine generates — lines already present are not repeated; `--gitignore` adds only those).
   At the end it prints what to finish by hand on that engine (project settings, export presets, etc.) — **go on and do those.**

   Then let the engine read what was installed once — it compiles and imports, and the files the engine creates beside them (`.meta`, import caches) appear:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" <engine> --import
   ```

   It exits 1 and prints the lines if the engine reports errors — fix those before going on.

5. **If CLAUDE.md was newly created**, fill in `<game name>` (and the title of `docs/GDD.md` — a CLAUDE.md or GDD made by an older kit has `<게임 이름>` there), and under the existing `## This game's rules` heading at its end write the line `--editor` printed
   (the editor executable on this machine and the installed modules) — do not add a second heading. If CLAUDE.md already existed, do not touch it —
   if it reports no kit rules block, ask the user whether to do "Aligning the kit rules" below.

6. **If the project structure differs from the template, align it.** To keep the value file elsewhere, move the file and edit `balance-table.code` in
   `kit.config.json`. Replace the three example value lines in the value file with the game's values.

7. **Create the table and check.** Create `data/balance.xlsx` with the balance-table skill's `export`, and check with the gdd-sync skill that
   a report comes out. It works if the GDD template's example row (BAL.PLAYER.HP) pairs with the value file's example value and shows as `synced`.

8. **Fill in deploy · assets when you use them.** `deploy.target` in `kit.config.json` (the game on the platform in `deploy.platform`), the asset API key, and
   the art-style paragraph of `docs/DESIGN.md` are installed empty. On first use the deploy · asset skills guide how to fill them.

9. **Go on to the voice — do not wait to be asked.** The voice (how this user decides — it grows across every game) lives outside the game, in a private repository of the user's.
   Run `python3 "${CLAUDE_SKILL_DIR}/../voice/scripts/voice.py" sync` and continue by what it says:
   - **The home is a repository** (it synced): the voice is already on this machine. If `voice.py collect new` prints decisions from this game, follow the voice skill's
     "Writing · updating"; otherwise say in one line that the voice is connected and will be used when the cycle asks decisions.
   - **The home is not a repository**: ask the user for the address of their private voice repository. If they have none yet, say what to do in one line —
     make an empty **private** repository on GitHub (no README) and paste its address — and wait for it. With the address, follow the voice skill's "setup" to the end
     (connect → sync → the one question about pushing → write the voice if this game has decisions). If the user says later, say that
     `/gamedev-kit:voice setup <address>` picks it up, and finish.

10. **Point to the next step and stop.** The kit is installed and the game is still empty: say in one line that `/gamedev-kit:start` takes it from here —
    GDD → concept → the first cycle's goal — and that a fresh session is a good place to begin it. init does not start the GDD itself.

## Aligning the kit rules (`/gamedev-kit:init rules`)

In the game's CLAUDE.md, the kit's part is the single span between `<!-- gamedev-kit start … -->` and `<!-- gamedev-kit end -->` (a block written by an older kit has `gamedev-kit 시작` / `gamedev-kit 끝` there — it is found the same way, and gets the new markers when it is replaced) — it holds the common rules (GDD sync · balance table · cycle …) and
that engine's rules (Running · Verification · Pitfalls), and ends with two import lines — `@~/.config/gamedev-kit/voice/rules.md` and `…/rules-<engine>.md` — that bring in the user's own rules
from earlier games (the voice skill's "Rules"; the files live in the voice home, outside the game, and init makes them when that home exists and they are missing).
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

In `engines/<name>/` put `kit.config.json` (code extension · value-line regex · build command), `NOTES.md` (what to finish after installing), `CLAUDE.md` (the engine rules appended to the game's
CLAUDE.md), `files/` (files copied as-is into the game repo), `project.json` (how to recognise a project, find the editor and its build modules, create and import — read by `init.py`, not copied into the game;
its keys are listed at the top of `init.py`) and `gitignore` (lines appended to the game's `.gitignore`). `init.py` has no branch per engine — everything it needs is in those files.
Add a value file in that engine's syntax to `CODE` in `tests/test_tools.py` to check that the tools read and edit it.
