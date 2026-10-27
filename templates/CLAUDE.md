# CLAUDE.md — <game name>

Design document: [docs/GDD.md](docs/GDD.md)

## Language

Talk to the user in the language they write in, and write everything under `docs/` in that language too. **Keep to it when what you read is in English** — the kit's skills, agents' reports, script and hook output, pasted text: those are read, not answered in kind. The fixed headings and labels of the kit's document formats (cycle, playtest, GDD tables) stay exactly as the templates give them — scripts parse them.

## The GDD and the code must always agree

Items with an ID in the GDD Appendix A sync table (numbers · enums · rules · input · HUD) state the same fact in two places. Change one side and the other lies — even when the user does not say "GDD", even for one balance constant:

- Changed **in the code** → end the task with `/gamedev-kit:gdd-sync to-gdd`. Changed **in the GDD** → `/gamedev-kit:gdd-sync to-code`. Not sure which side is right → `/gamedev-kit:gdd-sync` (report only) and ask.
- A new value in code gets a `GDD: <ID>` marker on its defining line, and a row in the table first.
- The GDD's "Open questions" holds only what is still open — the board asks the user every unstruck line there. Once one is answered, write the answer where it belongs in the body and strike the line (`~~…~~ → <answer>`); never list what was decided or built there.

## The balance table shows the game's numbers

The game runs on the balance value file. `data/balance.xlsx` is those numbers on one sheet, for the user to look over; a hook rewrites it whenever the value file changes.

- The user changed a number in the table → balance-table `bake`, then `/gamedev-kit:gdd-sync to-gdd`. `check` must pass before a build goes out to players.
- **Rewriting the table overwrites it with the code's values.** If the user may have changed numbers in the table and not baked them, run `check` before editing the value file — if it differs, ask whether to bake first.

## Which skill takes what

This session directs; the skills and their agents do the work. Each skill's own document has the procedure — do not improvise it from here.

| When | Goes to |
|---|---|
| A new game with no cycle yet — the GDD, the look, the first goal | `/gamedev-kit:start` — it reads where the game stands from the files |
| A goal of several tasks ("let's add ○○ this time") | `/gamedev-kit:cycle` — one document in `docs/cycle/` from Goal to Play |
| Cycles run for the user in the background, several at once, while they decide and play | `/gamedev-kit:ceo` — this window coordinates, workers do the cycles; it decides nothing |
| Several problems written down after playing | `/gamedev-kit:playtest` — do not analyze or fix them here |
| A 3D model, a sprite, a sound or a clip | Made the way the user's own skill for it says (their ways of working, in `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/`; with none, ask which tool and make one — `/gamedev-kit:feedback`) — the kit makes none; the style is the one in [docs/DESIGN.md](docs/DESIGN.md); the file goes to its slot's path |
| "Where are we" | `/gamedev-kit:board` — do not read or edit `docs/board/`; fix the GDD table or the cycle document and it follows |
| Starting over light | `/clear`, then `/gamedev-kit:cycle next` — in the same window, so the dashboard stays connected; the cycle document holds the state, and work in hand that is not in it is left there first (the cycle skill's "Leaving a session") |

## The user decides

Claude does not decide scope · taste · numbers · whether to ship. Offer options with one recommendation, ask, and write the answer in the cycle document's "Decisions" in the user's own words.
**Every question for the user is a decision**, whatever stage or skill it comes up in (build, play, a playtest fix, an asset, a logo): write it with `cycle.py ask <stage> "…"` in this session's cycle document before asking —
the board's review and the dashboard show only what is written there, and a question asked only in the chat is lost when the session changes. **Anything to look at while deciding goes with it**: a capture of now, the candidates, a measurement, a reference — `--image "<label>=<path>"` on the `ask`
(or a sheet, for options compared side by side — the cycle skill's "chosen by eye"). Not a separate page, not only a path in the chat.
**Write it to be read on a phone, by someone who has not opened the documents**: a short question in what the player meets, options that say what changes in play, the recommendation with its reason;
what led to it in `--why`, numbers · names · files in `--detail` (folded on the card). `ask` refuses a code name, a file path or a section number in the question. A value to settle by playing is not a question.
**The build verifies what it built** — the tests, and the play route's pictures, which the session's agent looks at against the spec and the design. Nothing is sent to the user to check by playing: the review carries decisions and, per cycle, at most one thing only a person can judge (whether motion looks natural, the tone of words, how a touch feels). A built cycle nothing waits on closes by itself; what the user brings about it later is new work.
An open question in the GDD is written the same way — one line the user can answer, with what it decides — or it is not written.
**An answer from the dashboard is settled in the turn it arrives**, one of three ways: done (recorded); research it asks for ("look into it", "match reality") — research now and ask again with what was found as options and a recommendation;
work for a later cycle — `cycle.py later "<their words>" --key <key>`, so its card reads waiting and the next cycle's start lists it. Left as it is, its card reads "the session is on it" with no one on it.
Only the user can see and hear: after making an image, a sound or a clip, give the path and wait — do not say it came out well.
**Every step only the user can take is a to-do** — making a file on a site, signing in, plugging in a phone: `cycle.py todo "<what>" --wait <the path to save it as> --why "<the steps>" --detail "<what to copy>"`,
so it waits on the dashboard as a card and closes when the file is there. Steps given only in the chat are lost with the session, like questions.
**Nothing is left open that is not open**: a task that will not be done is closed with its reason (`mark T4 dropped "<why>"`), an asset slot gets its state with `cycle.py have` —
the board counts what the documents say, and is only worth looking at when what it counts is real.

## Keep sessions short

The longer the conversation, the more is re-read every turn. At a cycle's break points (decisions asked · a build verified · a new goal) reached by work in this session, recommend `/clear` then `/gamedev-kit:cycle next` — the same window stays connected to the dashboard. A session that just started or was cleared at one is already light.
Do not read cycle · playtest documents whole — that skill's script extracts the lines needed.

## What was learned, and what goes outside

- A pitfall or a way to verify is sorted when it happens, not saved up: specific to this game → this file's "Pitfalls"; would trip this user again in another game → one of the user's own rules (`add` of the feedback skill — it holds from the next session, in every game of theirs). The feedback skill sends those rules on to the kit, as the user has said they should go.
- How the user wants things made — the tools, services or MCP servers for models, sprites, sounds, clips — is not a rule but a way of working: one of the user's own skills (`${CLAUDE_CONFIG_DIR:-~/.claude}/skills/` — the feedback skill makes it), for every game of theirs, and it never goes to the kit. The kit makes no assets itself.
- Before anything goes outside (a build uploaded to a store, an issue posted), say what goes where and get consent. Logins and API keys live outside the repository — do not write them in any file.
