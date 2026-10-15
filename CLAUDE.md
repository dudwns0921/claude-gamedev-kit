# CLAUDE.md — claude-gamedev-kit

This is a Claude Code plugin repository. There is no game code here — the plugin is installed into game repositories and used there.

## Rules

- **Whatever differs per engine lives only in `engines/<engine>/`.** Do not put branches on an engine's name into skills or scripts.
  Scripts read only values from `kit.config.json` (extensions · regexes · paths). Adding an engine must be a matter of adding one folder.
  The engines included now are Godot, Unity and web (plain HTML and JavaScript — no editor) — **only an engine verified by making a whole game with it goes in** (the Roblox settings were removed in 0.9.0; they are in the git history).
  Unity and web are being filled in while games are made with them — how far it has been run is recorded in `records.md`.
  `tests/test_structure.py` blocks an engine's name appearing as a string in a script.
- **A skill is complete within its own folder.** Do not import another skill's scripts. Settings go in `kit.config.json` under a section named after the skill.
- **Scripts use only the standard library** (Python 3.9 — a package missing on the installing side breaks only there. `tests/test_structure.py` blocks it). Only the script Blender runs (`blender_finish.py`) uses `bpy`. The game root is found by walking up from the current folder — never from the script's location.
- **Do not overwrite files in the game repository.** init creates only files that do not exist. There is one exception — the `<!-- gamedev-kit start -->` block (`<!-- gamedev-kit 시작 -->` in a game set up by an older kit) inside the game's CLAUDE.md belongs to the kit,
  so `init --rules` replaces it whole (it does not touch anything outside the block, and stops if the inside was edited by hand). A change to the rules installed into games goes out through this block.
- **Files that skill documents and hooks point to must exist.** When moving or renaming a script, also fix the documents that call it (`${CLAUDE_SKILL_DIR}/…`) and
  `hooks/hooks.json` (`${CLAUDE_PLUGIN_ROOT}/…`) — hooks fail silently. `tests/test_structure.py` blocks it.
- **The plugin's description is written in one place, `plugin.json`.** Writing it again in the plugin entry of `marketplace.json` leaves one side stale.
- Skill names are embedded in the games' CLAUDE.md and GDD (`/gamedev-kit:gdd-sync`). Do not change them.
- **For anything that goes out (an issue posted to this repository), the script checks and the skill asks.** An agent neither obtains approval nor skips it.
  Logins and tokens are done by the user and kept outside the repository.
- **Do not write instructions that make something read a cycle or playtest document whole.** The lines needed are pulled out by that skill's script (`cycle.py` · `playtest.py`).
- **Do not write a game's name.** This repository is installed into any game. When bringing over something learned in a game, drop that game's name · files · numbers and
  keep only the rule and its reason ("where it was learned" stays in the user's own rules — do not write a game's name in commit messages either). Use `<game>` in examples.
- **The cycle owns an asset's slot, not how it is made.** Name, path and size belong to the workflow; a file in the slot counts whoever made it.
  The asset and video skills are optional ways to fill slots — nothing in the cycle, the board or the other skills may require their services.
  Without them (no key, or the user would rather not), the cycle still runs: the slot waits on a placeholder and the user makes the file and puts it there.
- **The kit covers making a game and showing where it stands — nothing after.** What repeats while a game is made (cycles, GDD ↔ code, decisions, assets in slots) is the kit's;
  what happens now and then at the end (a store build, signing, uploading) is left to Claude Code itself, asked in plain words. Do not add a skill for it.
- **Commit messages are written in English**, as `<version> — <summary>`.
- After a change, bump `version` in `.claude-plugin/plugin.json` — without it the installed side does not receive the new version.

## Verification

```bash
python3 tests/test_tools.py        # creates a temporary project per engine config and runs gdd-sync · balance-table end to end. init recognises engine projects and lists the engines to choose from, feedback against a fake gh · a fake GitHub server, asset and start's concept images against a fake API server, video against a fake Higgsfield server · a fake ffmpeg (asset's finishing runs for real if Blender is present)
python3 tests/test_structure.py    # runs nothing, only reads files — do the files that skill documents and hooks point to exist, are there no branches on an engine's name in scripts, is only the standard library used
claude plugin validate .           # manifest
```

These tests do not run the files an engine folder installs into a game (`engines/<engine>/files/`). If you change them, run them in that engine yourself — what was run and what was not is recorded in `records.md` (see "Where records go" below).

Tokens and time are measured from the game repository's session logs — compare before and after a change:

```bash
python3 tools/session_usage.py <game repo>    # the main session's average context, and one agent run's cache writes and duration
```

## Where tokens go

Measured on real games' session logs: the largest share is what the main session re-reads every turn (more so the longer a session runs), then the developer agent called per task,
then the analysis · design agents. The always-loaded descriptions are small next to these. (The measured figures are not written here — see "Where records go" below.)
So the order when improving: ① what the main session reads and writes (ledgers by script, sessions cut at each cycle) ② agents not reading documents whole
③ the length of the sections agents write. Shortening skill bodies comes after that.

## Where records go

What comes out of making a game falls into these kinds. This repository is public — only what holds for any game comes here.

| What | Where |
|---|---|
| Individual records — what was made in which game and how many, measured figures, dates, cycle · playtest documents, **what was actually used and what was not** | That game's repository; what spans games goes in the user's private folder (`records.md` under `~/.config/gamedev-kit/`) |
| What holds only in that game — its own traps and ways to verify | That game's CLAUDE.md |
| What holds in this user's next game too — traps, ways to verify, ways of working tied to their engine · genre · tools | The user's own rules (`rules.md` · `rules-<engine>.md` in `~/.config/gamedev-kit/rules/` — on their machine; every game imports them, so they hold from the next session) |
| What holds for any game — traps, ways to verify, shortcomings of the tools | Here (rules · scripts), by way of the user's own rules sent as issues |

So the README and documents here state **only what the kit does** — the one exception is the README's lists of the engines and asset services games have been made with (names only). Whether something was used or not (verification status), the history of what was removed, and figures and dates such as how many · how many turns · how many days go in `records.md` (not in commit messages either).

Rules written down are not enough — `tools/private_check.py` enforces it: it searches the files git knows and commit messages for games' names (`private-words.txt` in the rules folder — the names themselves
must not be here, so the list lives outside the repository) and for dates. The tests run it, and it is also installed as a commit-msg hook (how to install it is at the top of that file). When starting a new game, add its name as a line in `private-words.txt`.

## What games teach comes back here

Traps that were hit and ways to verify are carried over to `engines/<engine>/CLAUDE.md` (what becomes the games' rules), and what the engine needs done with a file the kit
puts in a slot to `engines/<engine>/kit.config.json` (the `after` lines the asset and video tools print), so the next game does not go through the same thing again.

A lesson is sorted where the game trips (when a task is blocked · after a playtest fix), into two tiers: only that game → its CLAUDE.md; would trip the same user in another game →
one of their own rules (`feedback.py add` — on their machine, loaded into every game of theirs by the import lines at the end of the kit rules block, so it holds at once).
Whether a rule holds for every game is not asked of the user line by line — that judgement is the sweep's. The user answers once how their rules go out (`feedback.py auto`):
from then on a hook sends each new rule to this repository as an issue (titles start with `feedback(<engine>):`), or the user sends them from the skill or the dashboard's Rules page.
The script holds back anything that names a game or a date, and leaves out the game a rule came from.
A rule much like an open issue does not open a new one but comments on it — an issue with comments is one seen twice.
**The kit takes a rule when a second game has seen it.** Until then the lesson works where it was learned, among its sender's own rules; a shortcoming of the kit itself is fixed on the first report.
The personal rule carries its issue number; once that issue closes as completed the kit carries the rule, and the feedback skill asks the user whether to drop their copy (`feedback.py state`).

Turning the issues into rules is a sweep, not a chore per issue — seeing them together is what lets the same lesson from several games become one rule.
`.github/workflows/harvest.yml` runs it when ten eligible issues have collected, or on the button (Actions → harvest → Run workflow, `force` for fewer):
`tools/harvest.py pick` chooses the issues (from the owner · members · collaborators; an outsider's only once the owner labels it `harvest:ok`), a model reads them
with `.github/harvest.md` as its instructions and edits the files, `tools/harvest.py apply` · `check` refuse any change outside `engines/` · `skills/` · `agents/` · `templates/` · `tests/`
and bump the version, and the run ends with **one pull request** — never a push to main, and no second sweep while that one is open.
Issue text is untrusted: the job the model runs in can only read the repository; the job that pushes runs no model and none of the changed code.
The owner's part: label outsiders' issues worth reading `harvest:ok`, review the pull request as one from outside (the table of issue → lane → where, the size of each engine rule file before and after), and merge or close it.
Merging closes the issues that became rules or were already covered; feature requests and lessons too tied to one game stay open, labelled `harvest:request` · `harvest:skip` (remove the label to have the next sweep read it again).

Games receive the reflected rules through a hook at session start — an untouched block is replaced with the current version by itself (if the block is missing or was edited by hand, the hook only says so: `/gamedev-kit:init rules`).

Choose the right place for each line (the sweep is told the same in `.github/harvest.md`) — recurring traps and ways to verify go in the engine's CLAUDE.md, what a tool can prevent goes in a script (better than writing it down),
and what concerns one skill goes in that skill's document. Something seen in only one game is noted as such — it is made firm when it shows up again in a second game.
