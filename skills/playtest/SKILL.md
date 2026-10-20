---
name: playtest
description: >-
  Playtest → analysis → build flow. The analyst agent (playtest-analyst) turns the problem list the user wrote after playing
  into a task document in docs/playtest/, and one developer agent (developer, Sonnet) per task handles it.
  Use when the user lists several problems or to-dos ("플레이해 봤는데", "해 보니까 이게 문제야", "플레이테스트", "이것들 고쳐줘" —
  "I played it and", "these are the problems I found", "playtest", "fix these"); asks to analyze a problem list or organize feedback; or says
  "분석 문서대로 구현해줘", "playtest 문서 진행해줘", "T3 부터 해줘" ("build what the analysis document says", "go on with the playtest document", "start from T3").
  Not for a single problem with an obvious cause — just fix that.
---

# playtest

Split analysis from the build, and give both to agents. Finding causes is done once by the expensive model and left as a document.
**Which model thinks is set per game**: `"models"` in `kit.config.json`. `standard` (or no key) → call the playtest-analyst without a model — the agent's own, Opus. `max` → pass `model: fable` on those calls. Read the key once at the start; it changes nothing else.
Fixing is done by a cheap-model agent per task — each reads only its own task entry and the files to fix.
**This session only directs.** Reading code and analyzing here, or fixing directly, defeats the split.

| Call | Meaning |
|---|---|
| `/gamedev-kit:playtest <problem list>` | Analyze, then build every task with no blocking question |
| `/gamedev-kit:playtest plan <problem list>` | Analysis only. Create the document and stop |
| `/gamedev-kit:playtest implement [document] [T3 …]` | Build only. Without a document, the newest in `docs/playtest/`; without tasks, all remaining |
| `/gamedev-kit:playtest status` | Remaining tasks of the documents |

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/playtest.py" status          # one line per document
python3 "${CLAUDE_SKILL_DIR}/scripts/playtest.py" next            # questions to ask · next wave's tasks
python3 "${CLAUDE_SKILL_DIR}/scripts/playtest.py" task T3         # the summary and one task only
python3 "${CLAUDE_SKILL_DIR}/scripts/playtest.py" mark T1 done "<what changed, one plain line>"   # blocked "<reason>" · open · dropped "<why>"
python3 "${CLAUDE_SKILL_DIR}/scripts/playtest.py" open            # every task still open, in every document
# Every command acts on the newest document. When two or more carry the newest day, it stops and lists them — run it again with --doc <the one in hand>.
python3 "${CLAUDE_SKILL_DIR}/scripts/playtest.py" epic T3,T4 "<epic>"   # the stage of play a task is for (or Foundation) — `next` lists tasks the analyst left without one
python3 "${CLAUDE_SKILL_DIR}/../feedback/scripts/feedback.py" add "<what tripped us → how to avoid it>"   # one of the user's own rules — holds in their next game too (--any: whatever the engine)
```

These act on the newest document (for another, `--doc <path>`). Documents written before the kit wrote English use the Korean words — the script reads both; where this page names a word, the older form is in brackets.

## 1. Analysis

1. **Take the list.** Do not polish the user's sentences. If the list is not in the message, ask for it.
   Record the current commit with `git rev-parse --short HEAD`, and say so if there are uncommitted changes.
2. **Call the `gamedev-kit:playtest-analyst` agent.** Pass: the problem list verbatim, the commit hash,
   context the user added (which scene · which device · how many tries). **Do not pass your guesses** — an analyst handed a hypothesis comes back having confirmed it.
3. When it returns, write each of its "Questions for the user" as a decision in this session's cycle document — the one `cycle.py` acts on
   (`python3 "${CLAUDE_SKILL_DIR}/../cycle/scripts/cycle.py" ask Playtest "<question — ① … ② … · recommended: ①>"` — the board's review and the dashboard show only decisions),
   Each line of its "Not this time" marked **new** (something the game does not have yet, not a fix of what the cycle built) goes to the backlog,
   in the user's words — `cycle.py later "<it>"` — where a later cycle takes it; a cycle's playtest fixes what that cycle built.
   Then relay the document path, the task count and the questions with their numbers. For `plan`, stop here. When answered, `cycle.py decide` records it as for any decision.

## 2. Build

1. See the next wave's tasks with `next` — do not read the document whole (it is tens of thousands of tokens).
2. **Pick the tasks to do.** Skip the following — and say you are skipping them:
   - tasks hanging on an unanswered question in "Questions for the user"
   - tasks whose Kind is **design** (older: 분류 **설계**) with no user decision written in the document
   - tasks that depend on a task blocked or failed in an earlier wave
3. **Per wave, one `gamedev-kit:developer` agent per task, with `build T<n>` and `model: sonnet`.** Call a wave's tasks all at once (in one message) —
   the analyst grouped them so they touch different files. Pass three lines — `build T<n>`, the document path, the task-extraction command (`python3 <absolute path to this skill's playtest.py> task T<n> --doc <document>`). Do not copy out the task content.
   Call the next wave after the previous wave has fully returned.
   Where the engine runs one at a time (`"cycle": {"check": "wave"}` in `kit.config.json`), build and check each wave as the cycle skill's "Checked as a wave" says;
   where the game builds in a build folder (`"cycle": {"worktree": …}`), the round runs in this session's cycle's folder and merges as the cycle skill's "In a build folder" says —
   then the play route and the round's commit as below.
   **Before the first wave, take the build turn** — with several sessions at once, one builds at a time in the game's folder.
   **Where the game builds in a build folder** (`"cycle": {"worktree": …}` in `kit.config.json`) **take no turn**: `worktree open` instead (the cycle skill's script),
   build there, and `worktree merge` at the end takes the turn for the merge only. Otherwise:
   `python3 "${CLAUDE_SKILL_DIR}/../cycle/scripts/cycle.py" turn take "playtest <document name>"`. Refused (another session is building) → say so in a line,
   run `until python3 "${CLAUDE_SKILL_DIR}/../cycle/scripts/cycle.py" turn; do sleep 60; done` in the background, and call the wave when it ends.
   Give it back with `turn done` once the step 5 below is through — after its commit.
4. **Record returned results with `mark`** (agents do not edit the document. Do not open the document and edit it by hand):
   - done → `mark T1 done "<its Changed line>"`, one task per call — the dashboard shows it as what changed: one plain sentence, no code names (the script refuses them).
   - blocked · failed → `mark T2 blocked "<reason>"`. **Do not re-analyze and fix it here yourself.**
   - not to be done any more — merged into another task, folded, overtaken by a later round, its condition never came, the user said no →
     `mark T4 dropped "<why>"`. **A task is never left open for that**: an open task stays a Problem on the board for every cycle after, and the board is how the user sees nothing was missed.
5. **When all waves are done, once:**
   - if any task's Kind was balance (older: 밸런스), `export` with the balance-table skill (so the table does not hold old values)
   - if values · rules changed, `/gamedev-kit:gdd-sync to-gdd`
   - the project's verification (CLAUDE.md "Verification") once in full — conflicts between tasks show up here
   - **shoot the play route** — `python3 "${CLAUDE_SKILL_DIR}/../board/scripts/board.py" play playtest <document>` (the cycle skill's "Shoot the play route");
     the dashboard's Play tab shows the run beside the ones before
   - **commit the round** — `python3 "${CLAUDE_SKILL_DIR}/../cycle/scripts/cycle.py" commit playtest <document>`: what this round changed, nothing another session has in hand.
     Each round of fixes is its own commit, so what the user plays next is one. A round does not close the cycle — the user's checks and word do (the cycle skill)
6. **Report:**

   ```
   ## Playtest — <document>
   - Done: T3, T1 · Blocked: T2 (why) · Skipped: T4 (waiting on a question)
   - For you to answer: <the document's questions>
   - To play and check yourself: <what to look at, task by task>
   ```

   If any task is blocked, ask whether to re-analyze. Re-analysis means calling the analyst again with that task's "Why blocked" attached.
7. **What was learned — now, not later.** From the reasons tasks were blocked and the "Deviations from the document" that came back this round: what tripped us up · engine settings done by hand · a newly found way to check.
   Sort each one of two ways, as it is written:
   - Only this game (relies on its structure · rules · names) → ask whether to write it in the project's CLAUDE.md "Pitfalls".
   - Would trip this user again in another game (their engine, their genre, their tools, their way of working) → one of their own rules, `feedback.py add` (`--any` when it holds whatever the engine),
     written so it makes sense without the game's names · files · numbers. It holds from the next session in every game of theirs; nothing is asked.
     Whether it holds for every game is not judged here — the feedback skill sends rules to the kit, and the kit's sweep sorts them.

   If there is nothing, write nothing.

## status

Relay the output of `playtest.py status` as-is.

## Keep the documents

Do not delete finished documents either. If the same problem comes up in the next playtest, the analyst can read the earlier document and start from "we fixed it this way last time, so why again".
