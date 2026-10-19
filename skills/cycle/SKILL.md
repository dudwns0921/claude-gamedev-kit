---
name: cycle
description: >-
  Drives one game-dev cycle — Goal → Spec → Design → Plan → Build → Play — through a single document (docs/cycle/).
  Systems designer, designer and developer agents work stage by stage; every decision goes back to the user. Use when the user states a bundle of goals ("이번 사이클", "다음 버전 만들자",
  "이번엔 ○○ 를 넣자" — "this cycle", "let's make the next version", "this time let's add ○○"); says "사이클 이어서", "다음 단계", "어디까지 했지"
  ("continue the cycle", "next stage", "where were we"); answers a decision ("D2 는 ①로", "D2 is ①").
  Also how work crosses sessions — the document holds the state, so there is no separate handoff note: use when the user says "세션 바꾸자",
  "새 세션에서 이어가자", "인계 메모 남겨줘", "여기까지 정리해줘" ("let's switch sessions", "let's continue in a new session", "leave a handoff note",
  "wrap up where we are"), or in a new session "이어서 하자", "아까 하던 거" ("let's continue", "what we were doing"). Not for one-line fixes.
---

# cycle

One cycle runs **until one goal is built and in the user's hands to play** — and stays open there while they play and feed back. At each stage the agent in charge works, and results accumulate in one cycle document —
later stages read the earlier stages' sections. **This session only directs.** Doing spec or design here, or reading and editing code, defeats the split.

## Ledger by script, sessions short

Most tokens and time go to **what this session re-reads every turn**. So keep two rules.

**Do not read the cycle document whole or edit it by hand.** The document is tens of thousands of tokens. The script pulls out and changes the lines needed:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" new <short-name> "<goal — in the user's own words>"
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" status          # one line per document
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" next            # stage · unanswered decisions · next wave's tasks
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" task T3         # one task and only the decisions it hangs on
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" mark T1,T3 done # blocked "<reason>" · open
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" ask <stage> "<question — ① … ② … · recommended: ①>"   # any stage — Build · Play too
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" decide D2 "<the user's answer verbatim>"
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" confirm D2,D5              # a document from the time of auto mode: the user accepts what was decided in their place (`all`). To overturn: decide
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" drop D4,D12 "<why>"         # the user says a decision is not needed any more — [-], nothing waits on it
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" stage <stage>
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" line "<the goal in one line>"                    # what the board's "Now" shows
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" shot "<stage of play>" <picture>                 # that stage's screen as it stands now — the board's card shows it
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" later "<the user's words>" [--epic <epic>]       # something put off — into the backlog (docs/backlog.md), kept until taken or dropped
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" backlog                                         # what waits, by epic · `backlog take B2,B5` · `backlog drop B3 "<why>"` · `backlog epic B3 "<epic>"`
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" epic T3,T4 "<epic>"                              # the stage of play a task is for (or Foundation) — the developer writes it at Plan
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" epics                                           # per epic: its tasks across every cycle and playtest, and its backlog
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" carry "<what the next session must know>"       # work in hand that the document does not hold — `next` shows it
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" carry done                                      # picked up — not shown again
python3 "${CLAUDE_SKILL_DIR}/../feedback/scripts/feedback.py" add "<what tripped us → how to avoid it>"   # one of the user's own rules — holds in their next game too (--any: whatever the engine)
```

These act on the newest document (for another, `--doc <path>`, or name a task across the game as `C16-T3`). Use Edit only for writing a long section (Play) — and even then read only that section's line range, not the whole document.

**Clear the context at the breaks — in the same session.** All state is in the document, so a cleared session continues with one `next`. There are three places to break —
where you asked decisions and stopped, where the build is done and it is the user's turn to play, where the user states a new goal. On reaching one **through work done in this session**, recommend in one line:
"`/clear` here, then `/gamedev-kit:cycle next`, is lighter." The user stays in the same window (on the desktop, the terminal or their phone) and the dashboard stays connected to it —
answers sent from there still wake it, and a cleared session picks up whatever waits as it starts. If the user says just go on, go on.
When decisions are asked, the user may answer on the dashboard instead of the chat: this session stays open and waits, and "Send to the session" wakes it.
A session that started (or was cleared) with `next` often starts at one of these (decisions asked again · Play) — it is already light, so do not recommend clearing again; recommend it only once this session has run a stage, a wave or a playtest round.
Do not chain two or more cycles in one session. If work is in hand that the document does not hold (assets · settings · another repo · a fix under way), leave it first — "Leaving a session" below.

**Not done in this session**: reading code · reading images · reading logs. Agents do all of it and only summaries come back. When relaying an agent's report to the user, do not expand it at length again.

**The user decides.** No agent decides for them. Agents return "Decisions needed" as options plus one recommendation,
this skill collects and asks them, and writes the answers in the document's "Decisions" section in the user's own words (verbatim). Do not do work that hangs on an unanswered decision.

| Call | Meaning |
|---|---|
| `/gamedev-kit:cycle <goal>` | New cycle. Runs through spec · design · plan, then asks the decisions |
| `/gamedev-kit:cycle next` | Next stage of the newest cycle |
| `/gamedev-kit:cycle status` | Per cycle: current stage · remaining tasks · unanswered decisions |

## How the work is laid out

The game is the project. Its **epics** are the stages of play (`board.flow` — the board skill writes them once) and one more, **Foundation**, for what no stage owns (save, input, shared UI).
A **cycle** is a sprint: a goal, the tasks that build it, a Play that closes it. Every task belongs to one epic — its `- **Epic**:` line, which the developer writes at Plan
and the analyst writes for a playtest's tasks; one that comes back without it is given one with `epic` before the build. A task is `T3` inside its cycle and `C16-T3` across the game.
The **backlog** (`docs/backlog.md`) holds what is put off, each line with its epic, until a cycle takes it or the user drops it. The board counts each epic's tasks and backlog.

## Stages

| | Stage | Who | Document section | Stops at |
|---|---|---|---|---|
| 1 | Goal | user | Goal | |
| 2 | Spec | `gamedev-kit:systems-designer` `spec` | Spec | |
| 3 | Design | `gamedev-kit:designer` `design` | Design | |
| 4 | Plan | `gamedev-kit:developer` `plan` | Tasks · Order | **ask the decisions** |
| 5 | Build | `gamedev-kit:developer` `build T<n>`, one per task | task checkboxes | |
| 6 | Play | user (problems go to `/gamedev-kit:playtest`) | Play | **stays here** — the next cycle closes it |

### 1. Goal

Create the document with `new` — pass the goal in the user's words as-is, unpolished. Even if the goal looks several cycles big, do not shrink it — whether to shrink is asked as an option at the Plan stage.
Then give it one line with `line` — what the cycle does, in what the player meets, in the user's language (at most 120 characters): it heads the board's "Now",
above the user's own words. When the goal changes under way, write the line again.
The script creates `docs/cycle/NN-<short-name>.md` from the template below and records the current commit. If it reports uncommitted changes, say so.
**`new` also closes the previous cycle** — there is no closing stage. A document that stood at Play becomes `Closed`, and the script prints what that cycle left: open and blocked tasks,
unanswered decisions, and what the user put off (`later`). Relay those lines as facts, once; do not pick from them. If it says the previous cycle is still before Play, say so and go on.

**What earlier work left is settled before the goal moves on — the board is how the user sees nothing was forgotten, and it counts only what is still real.**
`new` also prints every playtest task still open, every asset slot still empty, and every slot whose file is in the game while its "Have" cell says none. Take them in this order:
- **Bookkeeping, done here at once:** a slot whose file is there → `have <slot> "<path>"`; a playtest task its own line says was merged, folded, or done by a later one
  → the playtest skill's `mark T4 dropped "<what the line says>"`.
- **The rest is the user's, as decisions** (`ask Spec …`, one per group, not one per line): the playtest tasks still worth doing — ① into this goal ② a later cycle ③ dropped
  (`mark … dropped`); the empty slots — ① made in this cycle ② kept on the placeholder (`have <slot> "placeholder (kept — Dn)"`) ③ not needed (`have <slot> "dropped — <why>"`).
  What waits in the backlog (`backlog:` lines) is in the same decision as the playtest tasks: ① into this goal → `backlog take B2` ② still later → nothing to do, it stays
  ③ not needed → `backlog drop B3 "<why>"`. (`deferred:` lines are from a document written before the backlog — one still for later goes in with `later`.)
  To-dos not done and checks never answered come with the rest.
  Put the lines in `--detail`. A condition a task waits on ("only if fps drops") is checked, not asked, when it can be.

### 2. Spec · 3. Design · 4. Plan

Who owns what: the **systems designer** owns how the game works (rules · balance numbers · structure and dimensions of spaces), the **designer** owns how it looks and sounds
(UI appearance · effects · sound · assets), the **developer** owns how to build it. A later agent does not edit earlier sections; it takes them as given.

**Which model thinks is set per game**: `"models"` in `kit.config.json`. `standard` (or no key) → call the systems designer and the designer without a model — the agent's own, Opus. `max` → pass `model: fable` on those calls. Read the key once at the start; it changes nothing else.

**How deep this cycle goes — decided here, from the goal, before any agent is called.** Each of the three is an expensive call that reads the project; a goal that does not
touch an owner's part does not pay for it. Read the goal (and the decisions already in the document) — do not scan the project for this:

| The goal | Runs | Skip with |
|---|---|---|
| A new system, rule, screen or mode · numbers whose shape changes · anything unsure | systems designer → designer → developer | — |
| Only how something looks or sounds changes (a screen's layout, effects, sounds, assets, polish) | designer → developer | `skip Spec "<why>"` |
| Nothing seen or heard changes (save, loading, performance, a value's range, inner logic) | systems designer → developer | `skip Design "<why>"` |
| A few tasks in one place that leave every rule and look as they are (a bug cluster, wiring what is already designed) | developer | both |

Say it to the user in one line as you go on — "Spec and Design skipped: only the wiring of the agreed save screen" — not as a question: they can say "the full way" and it is undone
(the sections are empty but for that line). When unsure, run it. A skip is cheap to be wrong about: if the developer returns "Questions for spec" or "Questions for design"
on a skipped section, call that owner then, with the questions. A fix of a line or two is not a cycle at all.

Call them one at a time in the order systems designer → designer → developer (`plan`). Call the next only after the previous returns. Pass only the cycle document path and the mode. Do not attach your own thoughts.

- If the systems designer returns "nothing touches the rules", go straight to Design.
- Of the systems designer's "Decisions needed", those that split a rule (is this rule A or B) are **asked first, before going to Design** — what the next two write changes wholesale with the answer.
  Do not ask about "start" values of numbers. They are tuned in the table after the build.
- **The agents ask each other; the user is asked only what is theirs.** If the designer or developer returns "Questions for spec", call the systems designer again with them attached;
  if the developer returns "Questions for design", call the designer again with them attached. If the section they own changed, call the asker again. Do not answer in their place,
  and do not pass these to the user — an owner that cannot settle one from what is already decided hands it back under "Decisions needed", and only then is it asked.

If the "Design" section's "Assets needed" lists a 3D model, sprite or sound that does not exist, tell the user — what to do about it is asked as a decision: have it made (the way the user's own skill for it says, if they have one), bring their own file, or leave the placeholder.
**Either way the build runs on placeholders.** Assets are not made during Build — they are made after it, all at once ("Assets" below).

Number the "Decisions needed" from all three consecutively (D1 …), write them into the document's "Decisions" with `ask`, and ask the user all at once —
options · what each costs · the recommendation. Then show the task count and waves. **Stop here.**

**Every question for the user is a decision — in every stage, not only these three.** One that comes up in Build or Play (a fix that could go two ways, which logo, whether to redo a picture),
from a playtest or an asset, is written with `ask Build|Play|Playtest|Asset "…"` in the newest cycle document before it is asked. A question asked only in the chat is not on the board's review,
cannot be answered from the dashboard, and is lost when the session changes.

**A decision is read on a phone, by someone who has not opened the documents.** The question is short (under 90 characters) and in what the player meets —
"how did the pickup feel?", not the constant behind it; each option says what changes in play, not in code; the recommendation carries its one-line reason.
What led to it goes in `--why` (a line or two), and the numbers, names and files behind it in `--detail` — the card keeps it folded. `ask` refuses a question
with fewer than two options, one too long, or one with a code name, a file path or a document section number in it — rewrite it, do not work around it.
Something to settle by playing (a value inside an agreed range) is not a question: say what to try in the table instead.
Carry the agents' `why:` and `detail:` lines over to `--why` and `--detail`.

**Whatever the user should look at to decide goes with the decision.** `ask … --image "<label>=<path>"` (repeat it; paths from the game root) keeps the pictures beside the question,
and the board's review and the dashboard show them on its card — a capture of how it is now, a measurement, a reference, the candidates. Ask the agent that raised it for the paths.
Pictures made after the question was asked go on with `attach D3 --image "<label>=<path>" …`.
**A clip, when stills cannot show it.** A choice about motion, timing or feel (how a jump lands, how fast a door opens, whether a hit reads) is judged from a few seconds of play:
the agent that raised it records one with what the engine offers (a movie-writing run, a browser's screen recording), cut to the seconds that matter, as mp4 or webm under 25 MB,
and it goes with `--image` like a picture — played on the card. Whether a decision needs one is the asking agent's call; most do not.
**A sound, when it is chosen by ear.** A voice line, a hit, a jingle, a loop — the candidates go on the card as files, one per option (`--image "① low=sfx/hit_a.mp3"`),
as mp3 · m4a · wav under 25 MB (not ogg: a phone's Safari plays none), each played on its own bar. Only the user can hear them — do not describe how they sound in place of the file.

**A decision chosen by eye is asked with a picture, one per question.** Candidates the user picks from (logo drafts, two looks of one screen) are the options of one decision, each with its picture —
not a page of their own. A screen, a pose, a grip, a colour: text plus a wide comparison image handed over separately cannot be chosen from (least of all on a phone),
so when the options are compared side by side, make a sheet.
Write the questions to a json file and make the sheets — each comes out as one picture with the numbered question and its options on top and, below, one tightly cropped picture per option, labelled (now · the change · a reference):

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sheet.py" <questions.json> [--name <name>]   # → docs/cycle/sheets/<name>-<n>.png (.html when this machine has no browser)
```

The file's shape is in the script's head (`sheet.py` with no arguments). The pictures are the captures the agents already took, and the crop boxes come from the agent that raised the decision —
ask it for the paths and boxes, **do not Read the captures here**. Use the decision's id (`D3`) as the question's `id`, give the user every sheet at once, and let them answer by number ("D3 은 ⓑ, D4 는 지금" — "D3 is ⓑ, D4 as it is").
The decision is still written with `ask` and answered with `decide` — the sheet is only how it is shown. The script keeps the questions beside the pictures
(`<name>.json`), and the board's review page shows the same pictures with a button per option.

**If the board is shared** (`board.share` in `kit.config.json`), republish it once the decisions are written — the board skill's "The link" — and give the link with the questions:
the user can answer on the phone, or in the chat as before.

When answers come, record them with `decide D1 "<the user's words verbatim>"`.
**An answer that is a question back, or that changes what is being asked** ("can it be both?", "is that possible without a server?"): answer what they asked in a line or two,
then ask it again with `reask D1 "<question — ① … ② … · recommended: ①>"` — D1 closes as "asked again as D7" and D7 is a new decision, a new card on the dashboard.
Never re-ask only in the chat, and never edit the decision line by hand. If an answer changes the spec · design · plan (scope cut · a different option chosen),
call that agent again to fix its section, and realign the sections of the stages after it. The same goes when the user asks to change the plan directly.
If an answer puts work off ("○○ first, then △△"), the put-off part is in no task list and `next` will say nothing is left — write it down while recording the answer:
a task if it belongs to this cycle (call `plan`), `later` if it does not.

### 5. Build

`next` lists the next wave's tasks (pending ones are shown as `waiting on D2` — do not run them). Per wave, one developer agent per task. Call the same wave all at once in one message.
**Call `build` with `model: sonnet`** — the task says where and how, so the build does not need the model that planned it (`plan` runs on the agent's own model; do not pass one).
Pass three lines — `build T<n>`, the document path, and the task-extraction command (`python3 <absolute path to this skill's cycle.py> task T<n> --doc <document>`). **Do not copy out the task content.**
Things that apply identically to every task, like the engine executable's path, are written once in the project's CLAUDE.md — do not repeat them to each agent.
In the same message that calls the wave, `mark T1,T3 doing` — the board and the dashboard show which tasks are being worked on now.
Record returned results with `mark` (agents do not edit the document): done → `mark T1,T3 done`, blocked · failed → `mark T2 blocked "<reason>"`.
Do not fix a blocked task here yourself — ask the user whether to call `plan` again with "Why blocked" attached.
**While `plan` is running, do not run `mark` · `ask` · `decide`** — it is rewriting the same document (and may set a blocked task back to open). Record them all after it returns.
Before the first wave on a machine that has not run this project (a fresh clone), check that the engine executable written in CLAUDE.md exists — without it a whole wave comes back unverified.
A blocked task or a returned "Deviations from the document" may be something learned — see "What was learned" below.

When all waves are done, once: if values · rules changed, `/gamedev-kit:gdd-sync to-gdd`; if the balance value file changed, the balance-table skill's `export`;
the project's full verification (CLAUDE.md "Verification").
**Shoot the screens.** For each stage of play (the board's stages, `board.flow`) this cycle changed — and each that has no screen yet — capture it as the player sees it,
the way the engine's rules say ("Screen … by capture"), into `docs/capture/cycle<NN>/`, and record it with `shot "<stage>" <picture>`. The board's cards show the newest screen of each stage
with the cycle it came from, so the user sees the game, not a percentage. Do not Read the captures for this — they are for the board. An engine with no way to capture: leave it; the card says so.
Then tell the user what to play and look at, collected from the tasks' "For a human to check", the spec's "To see by playing" and the design's "For a human to see".
If the board is shared, republish it first — its review page carries the last two as checks with OK · Problem buttons.
The spec's numbers went in as "start" values — also say which values in the table (`data/balance.xlsx`) to try moving (the spec's "Tuning notes").

**Assets — after the build, all at once.** The cycle owns each asset's slot — name, path, size — not how it gets made. Only now, with every wave done and the verification passed, fill the slots the user said to fill. The behaviour is fixed, so nothing made now is made for a rule that changes under it;
and the user looks once, not every few tasks.

1. List them from the "Assets needed" table — every row still `none` or `placeholder …` that was decided "make" or "bring my own".
   For the ones the user brings, tell them exactly what to deliver, one line each: the path the placeholder holds, the format the game already uses, and the size
   (longest side in metres for a model, shown pixels for a sprite, seconds for a sound).
   The kit makes no assets: the ones to make are made the way the user's own skill for that kind says (their ways of working, in `~/.claude/skills/`). With none, ask which tool or service,
   and make the answer one of their skills (the feedback skill's "Ways of working"). Say how many and what it may cost before making any.
2. **Show the user all of them in one sitting** — as decisions with the pictures attached (`ask Asset … --image`), or the board's asset sheet (`docs/board/assets.html`),
   which lays every file in a slot side by side — and take approvals and redraws together.
3. Each finished asset goes to the path its placeholder holds, so it drops in without a code change. Where it does not (a different size, a rig, a pivot) — that is a build task: write it into the document and run it.
4. Write each path in the table's "Have" cell with `have <slot> "<path>"` (and `have <slot> "placeholder (kept — Dn)"` for one the user leaves as it is), run the verification again,
   and only then tell the user what to play. A cell left `none` stays "Not made" on the board — for every cycle after.

If the user would rather play on placeholders first and make assets after that round, do it in that order — say the choice in one line when the build ends.

**What only the user can do goes on the board, not only in the chat.** A step outside this conversation — making a file on a site because no tool here can,
signing in, plugging in a phone, recording a voice — is a to-do: `todo "<what, in a line>" --wait <the path to save it as> --why "<the steps>" --detail "<the prompt and settings to copy>" [--image …]`.
The dashboard shows it as a card with the text to copy; with `--wait` the card closes by itself when the file is there, and the dashboard's watcher wakes this session for it.
Then say it in the chat in a line — the card holds the rest. When the file comes (or the user says done): look at it, go on with what waited for it, then `did U1`.
Not needed any more → `drop U1 "<why>"`. A choice is not a to-do — that is `ask`.

### 6. Play

**The last stage, and it stays open.** The user plays and feeds back, round after round — that is the normal shape, not an overrun. Do not ask whether the cycle is done
and do not write a wrap-up: the cycle is closed by the next one (`new`).

If a problem list comes, hand it to `/gamedev-kit:playtest` and write that document's path in the "Play" section.
**Checks are read by someone holding the game, not the documents.** `stage Play` (and `checks`) lists every check that names something from the code or the documents
(a constant, a section, a decision number) or runs long: rewrite each, before telling the user what to play, as one plain question about what the player meets —
"Does the split land on the share you want in one try?" — and move the numbers and what to move in the table to the spec's "Tuning notes", which the card does not show.
Each check by playing the user answers (in the chat or on the dashboard) is recorded: `checked "<the check>" ok|problem "<what they saw>"` — the start of the line is enough.
A cycle the next one closes with checks never answered is written "Not played" and stays so on the board until they are (`checked … --doc <that document>`); `new` lists them.
If given screenshots, you may call the designer with `review` (without a model — Opus — in either mode; checking against DESIGN.md is lighter than writing the design). Any number of rounds is fine.
If the user says they settled values in the table: balance-table skill's `bake` → `/gamedev-kit:gdd-sync to-gdd`.
When the user puts something off ("나중에", "다음에 하자" — "later", "let's do that next time"), record it with `later "<their words>" --epic <epic>` — it waits in the backlog, and `new` lists it as each cycle starts.
**Shipping is not a stage.** A build goes out when the user asks for one, usually after several cycles — do not ask about it or offer it here.

## What was learned — when it happens

There is no end-of-cycle step to save this for. Look at two moments: when a Build wave returns a blocked task or "Deviations from the document", and when a playtest round's build returns
(the playtest skill does this itself for its own tasks — do not repeat it). What counts: what tripped us up · engine settings done by hand · a newly found way to check. **Sort each one of two ways, as it is written:**

1. **Only this game** (relies on this game's structure · rules · names) → ask whether to write it in the project's CLAUDE.md "Pitfalls".
2. **Would trip this user again in another game** (their engine, their genre, their tools, their way of working) → one of their own rules: `feedback.py add "<what tripped us → how to avoid it>"`
   (`--any` when it holds whatever the engine). It holds from the next session, in every game of theirs; nothing is asked. Write it so it makes sense without the game's names · files · numbers.
   Whether it holds for every game is not judged here — the feedback skill sends rules to the kit, and the kit's sweep sorts them.

If the project's CLAUDE.md needs it too, write it there as well.
If the sorting is hard, ask: "Would you need to know this when making another game next time?" If there is nothing, write nothing — do not force-fill.

## Cycle document

```markdown
# Cycle NN — <short name>

Started: <date> · Commit <7-char hash> · Stage: Goal

## Goal
In the user's own words (verbatim).

## Decisions
- [ ] D1. <question> — ① … ② … · recommended: ① (who recommended it: Spec | Design | Plan)
- [x] D2. <question> → <the user's answer verbatim> (<date>)

## For you            ← added by the first `todo`
- [ ] U1. <what the user does> — wait: `<path>`

## Spec
## Design
## Tasks
## Order
## Play
```

`carry` adds a `## Carried over` section at the end the first time it is used — `- [ ]` not yet picked up, `- [x]` picked up.

Update the header's `Stage:` with `stage` every time the stage changes (Goal · Spec · Design · Plan · Build · Play). `next` and `status` read that line. Keep the stage name short — circumstances go in that section.

Documents written before the kit wrote English use the Korean words (`# 사이클`, `단계:`, `## 목표` · `## 결정` · `## 기획` · `## 디자인` · `## 작업` · `## 순서` · `## 플레이`, `· 권함:`, `- 1차:`, `**대기**`). The script reads both, and what it adds to such a document is English — leave the old lines as they are.

## Leaving a session

The cycle document is the one thing a cleared (or new) session picks up from — there is no separate note. Stage, decisions and tasks are already in it. What is not — work outside the tasks,
what the user said in this conversation that is written nowhere, a job still running — goes in with `carry`, one line each, **only what the next session cannot find in a file**:

- unfinished work: what, how far, where to pick up (`file:line` · the command to type)
- what the user decided in this conversation, in their own words (verbatim) — so it is not asked again
- what tripped this conversation up · what must not be touched · a question still unanswered

Write from what you know now — do not re-read files to write the lines; that makes the session you are leaving heavier. A handful of lines, not the history of the conversation,
not copies of logs or code. **Point only to files inside the repository** — what lives in the session's own folder (subagent transcripts) is deleted with the session.
The script stamps each line with the date and the commit, and says so if there are uncommitted changes — relay that. Then one line: "`/clear`, then `/gamedev-kit:cycle next`." Do not continue working before the context is cleared.

Before the first cycle there is no document to carry in, and none is needed: `/gamedev-kit:start` reads where the game stands from its files.

## next

Run `cycle.py next` and continue from there — do not read the document. If the board is shared, read the answers tapped on it first (the board skill's "Reading the answers").
**If it lists "carried over" lines, those come first**: they are what the last session had in hand.
A "for the user" line whose file is there now is next: look at it and go on with what waited for it, then `did U1`.
If their commit differs from the current one, say so — the lines are a snapshot of when they were left. Run `carry done` at once (what is still unfinished when this session ends is carried again),
ask the questions among them, and start from them — **do not scan the project to find out what the lines do not say**; open only the files that work needs.
A "handoff note not resumed" line is a note from before `carry` existed: read that one file and treat it the same way. If it lists "proxy decision (unconfirmed)", those come first: show each with what was chosen and on what basis, and take the user's accept or overturn before anything else.
Accepted → `confirm D2,D5` (or `confirm all`); overturned → `decide D2 "<their words>"`; not needed any more → `drop D2 "<their words>"` (also what "Not needed" on the dashboard asks for). An overturned decision is an answer that changes the plan: call the agent whose section it touches,
then rework the tasks that hung on it. If a document without a `## Spec` section (made before this stage existed) stands before Design or Plan,
call spec first — the systems designer creates the section. A document whose build has already started continues as-is. If it stands at a stopping point (decisions), ask again — do not move on without an answer.
A document standing at 배포 or 회고 (shipping and retrospective — made when those were stages) is in Play — treat it so, and write nothing in those sections.

## status

Relay the output of `cycle.py status` as-is.

## Keep the documents

Do not delete finished cycle documents either. The next cycle's systems designer · designer · developer read the previous cycles' decisions and do not ask the same questions again.
