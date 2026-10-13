---
name: cycle
description: >-
  Drives one game-dev cycle — Goal → Spec → Design → Plan → Build → Play — through a single document (docs/cycle/).
  Systems designer, designer and developer agents work stage by stage; every decision goes back to the user — or, in auto mode,
  is made by the user's voice up to the point of playing. Use when the user states a bundle of goals ("이번 사이클", "다음 버전 만들자",
  "이번엔 ○○ 를 넣자" — "this cycle", "let's make the next version", "this time let's add ○○"); says "사이클 이어서", "다음 단계", "어디까지 했지"
  ("continue the cycle", "next stage", "where were we"); answers a decision ("D2 는 ①로", "D2 is ①"); or wants it run without them
  ("자동으로 돌려줘", "알아서 만들어 놔", "나 없는 동안 진행해줘" — "run it automatically", "build it on your own", "go on while I'm away", "auto").
  Not for one-line fixes.
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
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" ask <Spec|Design|Plan> "<question — ① … ② … · recommended: ①>"
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" decide D2 "<the user's answer verbatim>"
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" decide D2 "②" --proxy V3   # auto mode: decided in the user's place — written [~]
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" confirm D2,D5              # the user accepts proxy decisions (`all`). To overturn: decide
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" stage <stage>
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" later "<the user's words>"                      # something put off — shown when the next cycle starts
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" lesson "<what tripped us → how to avoid it>"   # to send up to the kit (when it happens)
python3 "${CLAUDE_SKILL_DIR}/../voice/scripts/voice.py" rule add "<the rule and its reason>"   # one of the user's own rules — holds in their next game too (--any: whatever the engine)
```

These act on the newest document (for another, `--doc <path>`). Use Edit only for writing a long section (Play) — and even then read only that section's line range, not the whole document.

**Break sessions.** All state is in the document, so a new session continues with one `next`. There are three places to break —
where you asked decisions and stopped, where the build is done and it is the user's turn to play, where the user states a new goal. On reaching one, recommend in one line:
"Opening a new session here and continuing with `/gamedev-kit:cycle next` is lighter." If the user says just go on, go on.
Do not chain two or more cycles in one session. If you were also doing work outside the cycle (assets · settings · another repo), leave a note with the handoff skill and move on.

**Not done in this session**: reading code · reading images · reading logs. Agents do all of it and only summaries come back. When relaying an agent's report to the user, do not expand it at length again.

**The user decides.** No agent decides for them. Agents return "Decisions needed" as options plus one recommendation,
this skill collects and asks them, and writes the answers in the document's "Decisions" section in the user's own words (verbatim). Do not do work that hangs on an unanswered decision.
The one exception is **auto mode** (below): the user has asked, for this run, that their voice decide in their place — and even then every such decision is marked and waits for them.

| Call | Meaning |
|---|---|
| `/gamedev-kit:cycle <goal>` | New cycle. Runs through spec · design · plan, then asks the decisions |
| `/gamedev-kit:cycle next` | Next stage of the newest cycle |
| `/gamedev-kit:cycle auto <goal>` · `auto next` | Auto mode — run to the point of playing without asking; the user's voice decides |
| `/gamedev-kit:cycle status` | Per cycle: current stage · remaining tasks · unanswered decisions |

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
The script creates `docs/cycle/NN-<short-name>.md` from the template below and records the current commit. If it reports uncommitted changes, say so.
**`new` also closes the previous cycle** — there is no closing stage. A document that stood at Play becomes `Closed`, and the script prints what that cycle left: open and blocked tasks,
unanswered decisions, and what the user put off (`later`). Relay those lines as facts, once; do not pick from them. If it says the previous cycle is still before Play, say so and go on.
Then the voice skill's "Review" — the one place the voice is shown unasked: the lines it picked up that the user has not seen, if any. Show them in the same message and go on to Spec without waiting.

### 2. Spec · 3. Design · 4. Plan

Who owns what: the **systems designer** owns how the game works (rules · balance numbers · structure and dimensions of spaces), the **designer** owns how it looks and sounds
(UI appearance · effects · sound · assets), the **developer** owns how to build it. A later agent does not edit earlier sections; it takes them as given.

**Which model thinks is set per game**: `"models"` in `kit.config.json`. `standard` (or no key) → call the systems designer and the designer without a model — the agent's own, Opus. `max` → pass `model: fable` on those calls. Read the key once at the start; it changes nothing else.

Call them one at a time in the order systems designer → designer → developer (`plan`). Call the next only after the previous returns. Pass only the cycle document path and the mode. Do not attach your own thoughts.

- If the systems designer returns "nothing touches the rules", go straight to Design.
- Of the systems designer's "Decisions needed", those that split a rule (is this rule A or B) are **asked first, before going to Design** — what the next two write changes wholesale with the answer.
  Do not ask about "start" values of numbers. They are tuned in the table after the build.
- **The agents ask each other; the user is asked only what is theirs.** If the designer or developer returns "Questions for spec", call the systems designer again with them attached;
  if the developer returns "Questions for design", call the designer again with them attached. If the section they own changed, call the asker again. Do not answer in their place,
  and do not pass these to the user — an owner that cannot settle one from what is already decided hands it back under "Decisions needed", and only then is it asked.

If the "Design" section's "Assets needed" lists a 3D model, sprite or sound that does not exist, tell the user — what to do about it is asked as a decision: make it with the asset skill (needs its services set up), bring their own file, or leave the placeholder.
**Either way the build runs on placeholders.** Assets are not made during Build — they are made after it, all at once ("Assets" below).

Number the "Decisions needed" from all three consecutively (D1 …), write them into the document's "Decisions" with `ask`, and ask the user all at once —
options · what each costs · the recommendation. Then show the task count and waves. **Stop here.**

**A decision chosen by eye is asked with a picture, one per question.** A screen, a pose, a grip, a colour: text plus a wide comparison image handed over separately cannot be chosen from (least of all on a phone).
Write the questions to a json file and make the sheets — each comes out as one picture with the numbered question and its options on top and, below, one tightly cropped picture per option, labelled (now · the change · a reference):

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sheet.py" <questions.json> [--name <name>]   # → docs/cycle/sheets/<name>-<n>.png (.html when this machine has no browser)
```

The file's shape is in the script's head (`sheet.py` with no arguments). The pictures are the captures the agents already took, and the crop boxes come from the agent that raised the decision —
ask it for the paths and boxes, **do not Read the captures here**. Use the decision's id (`D3`) as the question's `id`, give the user every sheet at once, and let them answer by number ("D3 은 ⓑ, D4 는 지금" — "D3 is ⓑ, D4 as it is").
The decision is still written with `ask` and answered with `decide` — the sheet is only how it is shown.

**The voice works behind this, unseen.** If the user has a voice (`python3 "${CLAUDE_SKILL_DIR}/../voice/scripts/voice.py" path` prints its path — it lives outside the game),
between `ask` and asking the user, follow the voice skill's "Predict": `voice.py sync`, read that document and record one prediction per decision
(`voice.py predict D2 ② V3`, or `predict D2 -` when no principle applies). After the answers are recorded, follow its "Score" and "Learn".
**Say nothing about any of it** — no predictions, no hits or misses, no "updated the voice". The user just answers questions.

When answers come, record them with `decide D1 "<the user's words verbatim>"`. If an answer changes the spec · design · plan (scope cut · a different option chosen),
call that agent again to fix its section, and realign the sections of the stages after it. The same goes when the user asks to change the plan directly.
If an answer puts work off ("○○ first, then △△"), the put-off part is in no task list and `next` will say nothing is left — write it down while recording the answer:
a task if it belongs to this cycle (call `plan`), `later` if it does not.

### 5. Build

`next` lists the next wave's tasks (pending ones are shown as `waiting on D2` — do not run them). Per wave, one developer agent per task. Call the same wave all at once in one message.
**Call `build` with `model: sonnet`** — the task says where and how, so the build does not need the model that planned it (`plan` runs on the agent's own model; do not pass one).
Pass three lines — `build T<n>`, the document path, and the task-extraction command (`python3 <absolute path to this skill's cycle.py> task T<n> --doc <document>`). **Do not copy out the task content.**
Things that apply identically to every task, like the engine executable's path, are written once in the project's CLAUDE.md — do not repeat them to each agent.
Record returned results with `mark` (agents do not edit the document): done → `mark T1,T3 done`, blocked · failed → `mark T2 blocked "<reason>"`.
Do not fix a blocked task here yourself — ask the user whether to call `plan` again with "Why blocked" attached.
**While `plan` is running, do not run `mark` · `ask` · `decide`** — it is rewriting the same document (and may set a blocked task back to open). Record them all after it returns.
Before the first wave on a machine that has not run this project (a fresh clone), check that the engine executable written in CLAUDE.md exists — without it a whole wave comes back unverified.
A blocked task or a returned "Deviations from the document" may be something learned — see "What was learned" below.

When all waves are done, once: if values · rules changed, `/gamedev-kit:gdd-sync to-gdd`; if the balance value file changed, the balance-table skill's `export`;
the project's full verification (CLAUDE.md "Verification"). Then tell the user what to play and look at, collected from the tasks' "For a human to check", the spec's "To see by playing" and the design's "For a human to see".
The spec's numbers went in as "start" values — also say which values in the table (`data/balance.xlsx`) to try moving.

**Assets — after the build, all at once.** The cycle owns each asset's slot — name, path, size — not how it gets made. Only now, with every wave done and the verification passed, fill the slots the user said to fill. The behaviour is fixed, so nothing made now is made for a rule that changes under it;
and the user looks once, not every few tasks.

1. List them from the "Assets needed" table — every row still `none` or `placeholder …` that was decided "make" or "bring my own". For the ones the user brings, follow the asset skill's "Bring your own" and skip to step 3.
   For the ones to make: Say how many and what it will cost (images are cheap; meshes, sprite animations and sounds cost credits).
2. Follow the asset skill's procedure for all of them together: every image first, then **show the user all of them in one sitting** — the board's asset sheet (`docs/board/assets.html`)
   has them side by side — and take approvals and redraws together; then meshes and sounds.
3. Each finished asset goes to the path its placeholder holds, so it drops in without a code change. Where it does not (a different size, a rig, a pivot) — that is a build task: write it into the document and run it.
4. Write each path in the table's "Have" cell, run the verification again, and only then tell the user what to play.

If the user would rather play on placeholders first and make assets after that round, do it in that order — say the choice in one line when the build ends. In auto mode this step does not run.

### 6. Play

**The last stage, and it stays open.** The user plays and feeds back, round after round — that is the normal shape, not an overrun. Do not ask whether the cycle is done
and do not write a wrap-up: the cycle is closed by the next one (`new`).

If a problem list comes, hand it to `/gamedev-kit:playtest` and write that document's path in the "Play" section.
If given screenshots, you may call the designer with `review` (without a model — Opus — in either mode; checking against DESIGN.md is lighter than writing the design). Any number of rounds is fine.
If the user says they settled values in the table: balance-table skill's `bake` → `/gamedev-kit:gdd-sync to-gdd`.
When the user puts something off ("나중에", "다음에 하자" — "later", "let's do that next time"), record it with `later "<their words>"` — `new` shows it when the next cycle starts.
**Shipping is not a stage.** A build goes out when the user asks for one (`/gamedev-kit:deploy`), usually after several cycles — do not ask about it or offer it here.

## What was learned — when it happens

There is no end-of-cycle step to save this for. Look at two moments: when a Build wave returns a blocked task or "Deviations from the document", and when a playtest round's build returns
(the playtest skill does this itself for its own tasks — do not repeat it). What counts: what tripped us up · engine settings done by hand · a newly found way to check. **Sort each one of three ways, as it is written:**

1. **Only this game** (relies on this game's structure · rules · names) → ask whether to write it in the project's CLAUDE.md "Pitfalls".
2. **Would trip this user again in another game** (their engine, their genre, their tools, their way of working) → one of their own rules: `voice.py rule add "<the rule and its reason>"`
   (`--any` when it holds whatever the engine). It holds from the next session, in every game of theirs; nothing is asked, and nothing leaves the machine but their private repository.
3. **Of those, would trip anyone** (another user's game on the same engine would hit it, or a kit tool fell short) → **also** one line in `docs/kit-feedback.md` with `lesson`, so it can be sent to the kit.
   Write it so it makes sense without the game's names · files · numbers: "what tripped us → how to avoid (check) it".

A lesson for the kit is therefore always a personal rule first — the rule works now, the kit catches up later. If the project's CLAUDE.md needs it too, write it there as well.
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

## Spec
## Design
## Tasks
## Order
## Play
```

Update the header's `Stage:` with `stage` every time the stage changes (Goal · Spec · Design · Plan · Build · Play). `next` and `status` read that line. Keep the stage name short — circumstances go in that section.

Documents written before the kit wrote English use the Korean words (`# 사이클`, `단계:`, `## 목표` · `## 결정` · `## 기획` · `## 디자인` · `## 작업` · `## 순서` · `## 플레이`, `· 권함:`, `- 1차:`, `**대기**`). The script reads both, and what it adds to such a document is English — leave the old lines as they are.

## Auto mode

`/gamedev-kit:cycle auto <goal>` starts a cycle and `/gamedev-kit:cycle auto next` continues the newest one **without asking** — the user's voice decides, and it stops where the user has to play.
It holds for that run only. **When called with `auto`, read `${CLAUDE_SKILL_DIR}/auto.md` first and follow it** — it changes how decisions, missing assets and blocked tasks are handled.
Without `auto`, do not read it.

## next

Run `cycle.py next` and continue from there — do not read the document. If it lists "proxy decision (unconfirmed)", those come first: show each with what was chosen and on what basis, and take the user's accept or overturn before anything else.
Accepted → `confirm D2,D5` (or `confirm all`); overturned → `decide D2 "<their words>"`. An overturned decision is an answer that changes the plan: call the agent whose section it touches,
then rework the tasks that hung on it. Then the voice skill's "Score" and "Learn", silently. If a document without a `## Spec` section (made before this stage existed) stands before Design or Plan,
call spec first — the systems designer creates the section. A document whose build has already started continues as-is. If it stands at a stopping point (decisions), ask again — do not move on without an answer.
A document standing at 배포 or 회고 (shipping and retrospective — made when those were stages) is in Play — treat it so, and write nothing in those sections.

## status

Relay the output of `cycle.py status` as-is.

## Keep the documents

Do not delete finished cycle documents either. The next cycle's systems designer · designer · developer read the previous cycles' decisions and do not ask the same questions again.
