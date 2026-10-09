---
name: init
description: >-
  Installs the files gamedev-kit (gdd-sync · balance-table) uses into a game repo — engine config (kit.config.json), GDD template,
  CLAUDE.md rules, the balance value file and the runtime template that re-reads the table while running. The engine currently included is Godot.
  Also aligns the kit rules in CLAUDE.md after the kit bumps its version (rules). Use when starting a new game, on "gamedev-kit 깔아줘",
  "키트 규칙 맞춰줘", "init rules", "GDD 동기화 세팅", "밸런스 표 세팅", or when gdd-sync or balance-table says it cannot find kit.config.json.
---

# init

Run at the game repo root. Existing files are not touched, so re-running is safe.

**Re-running in an already-installed project** overwrites nothing and does three things: creates document templates the kit has gained since (e.g. `docs/DESIGN.md`) if missing,
reports config sections missing from `kit.config.json` (copying them in is your job — it does not edit the file), and skips the engine template files (value file · runtime).
Why it skips the engine template files: in a project that moved the value file or deliberately deleted a template, creating the same file again makes a duplicate. To really reinstall, `--files`.
It does not touch CLAUDE.md, and if the kit rules are an old version it says so — aligning them is "Aligning the kit rules" below.

## Procedure

1. **Decide the engine.** The only engine currently included is `godot` (run without arguments to list included engines). If the repo belongs to another engine (no `project.godot`, and
   another engine's project file exists), do not install and say so — this kit has never been verified on that engine.

2. **Install.**

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" godot
   ```

   Installed: `kit.config.json` · `docs/GDD.md` · `docs/DESIGN.md` · `CLAUDE.md` · the engine's value file and runtime template · one `.gitignore` line.
   At the end it prints what to finish by hand on that engine (autoload registration, export presets, etc.) — **go on and do those.**

3. **If CLAUDE.md was newly created**, fill in `<게임 이름>` (and the title of `docs/GDD.md`). If it already existed, do not touch it —
   if it reports no kit rules block, ask the user whether to do "Aligning the kit rules" below.

4. **If the project structure differs from the template, align it.** To keep the value file elsewhere, move the file and edit `balance-table.code` in
   `kit.config.json`. Replace the three example value lines in the value file with the game's values.

5. **Create the table and check.** Create `data/balance.xlsx` with the balance-table skill's `export`, and check with the gdd-sync skill that
   a report comes out. It works if the GDD template's example row (BAL.PLAYER.HP) pairs with the value file's example value and shows as `동기`.

6. **Fill in deploy · assets when you use them.** `deploy.itch` in `kit.config.json` (itch.io `user/game`), the asset API key, and
   the art-style paragraph of `docs/DESIGN.md` are installed empty. On first use the deploy · asset skills guide how to fill them.

7. **Go on to the voice — do not wait to be asked.** The voice (how this user decides — it grows across every game) lives outside the game, in a private repository of the user's.
   Run `python3 "${CLAUDE_SKILL_DIR}/../voice/scripts/voice.py" sync` and continue by what it says:
   - **The home is a repository** (it synced): the voice is already on this machine. If `voice.py collect new` prints decisions from this game, follow the voice skill's
     "Writing · updating"; otherwise say in one line that the voice is connected and will be used when the cycle asks decisions.
   - **The home is not a repository**: ask the user for the address of their private voice repository. If they have none yet, say what to do in one line —
     make an empty **private** repository on GitHub (no README) and paste its address — and wait for it. With the address, follow the voice skill's "setup" to the end
     (connect → sync → the one question about pushing → write the voice if this game has decisions). If the user says later, say that
     `/gamedev-kit:voice setup <address>` picks it up, and finish.

## Aligning the kit rules (`/gamedev-kit:init rules`)

In the game's CLAUDE.md, the kit's part is the single span between `<!-- gamedev-kit 시작 … -->` and `<!-- gamedev-kit 끝 -->` — it holds the common rules (GDD sync · balance table · cycle …) and
that engine's rules (Running · Verification · Pitfalls). When the kit bumps its version, replace only that span wholesale. **Outside the block is the game's and is not touched.**
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
CLAUDE.md), `files/` (files copied as-is into the game repo).
Add a value file in that engine's syntax to `CODE` in `tests/test_tools.py` to check that the tools read and edit it.
