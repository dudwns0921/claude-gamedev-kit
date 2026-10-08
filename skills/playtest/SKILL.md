---
name: playtest
description: >-
  Playtest → analysis → build flow. The analyst agent (playtest-analyst, Fable) turns the problem list the user wrote after playing
  into a task document in docs/playtest/, and one developer agent (developer, Opus) per task handles it.
  Use when the user lists several problems or to-dos ("플레이해 봤는데", "해 보니까 이게 문제야", "플레이테스트", "이것들 고쳐줘");
  asks to analyze a problem list or organize feedback; or says "분석 문서대로 구현해줘", "playtest 문서 진행해줘", "T3 부터 해줘".
  Not for a single problem with an obvious cause — just fix that.
---

# playtest

Split analysis from the build, and give both to agents. Finding causes is done once by the expensive model and left as a document.
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
python3 "${CLAUDE_SKILL_DIR}/scripts/playtest.py" mark T1,T3 done # blocked "<reason>" · open
```

These act on the newest document (for another, `--doc <path>`).

## 1. Analysis

1. **Take the list.** Do not polish the user's sentences. If the list is not in the message, ask for it.
   Record the current commit with `git rev-parse --short HEAD`, and say so if there are uncommitted changes.
2. **Call the `gamedev-kit:playtest-analyst` agent.** Pass: the problem list verbatim, the commit hash,
   context the user added (which scene · which device · how many tries). **Do not pass your guesses** — an analyst handed a hypothesis comes back having confirmed it.
3. When it returns, relay the document path, the task count, and "사용자에게 물을 것". For `plan`, stop here.

## 2. Build

1. See the next wave's tasks with `next` — do not read the document whole (it is tens of thousands of tokens).
2. **Pick the tasks to do.** Skip the following — and say you are skipping them:
   - tasks hanging on an unanswered question in "사용자에게 물을 것"
   - tasks whose 분류 is **설계** with no user decision written in the document
   - tasks that depend on a task blocked or failed in an earlier wave
3. **Per wave, one `gamedev-kit:developer` agent per task, with `build T<n>`.** Call a wave's tasks all at once (in one message) —
   the analyst grouped them so they touch different files. Pass three lines — `build T<n>`, the document path, the task-extraction command (`python3 <absolute path to this skill's playtest.py> task T<n> --doc <document>`). Do not copy out the task content.
   Call the next wave after the previous wave has fully returned.
4. **Record returned results with `mark`** (agents do not edit the document. Do not open the document and edit it by hand):
   - done → `mark T1,T3 done`. If there are "Deviations from the document", `mark T1 done "<what and why>"`.
   - blocked · failed → `mark T2 blocked "<reason>"`. **Do not re-analyze and fix it here yourself.**
5. **When all waves are done, once:**
   - if any task's 분류 was 밸런스, `export` with the balance-table skill (so the table does not hold old values)
   - if values · rules changed, `/gamedev-kit:gdd-sync to-gdd`
   - the project's verification (CLAUDE.md "Verification") once in full — conflicts between tasks show up here
6. **Report:**

   ```
   ## 플레이테스트 — <문서>
   - 끝낸 것: T3, T1 · 막힌 것: T2 (이유) · 건너뛴 것: T4 (질문 대기)
   - 답해 주실 것: <문서의 질문>
   - 직접 해 보고 확인할 것: <작업별로 무엇을 보면 되는지>
   ```

   If any task is blocked, ask whether to re-analyze. Re-analysis means calling the analyst again with that task's "Why blocked" attached.

## status

Relay the output of `playtest.py status` as-is.

## Keep the documents

Do not delete finished documents either. If the same problem comes up in the next playtest, the analyst can read the earlier document and start from "we fixed it this way last time, so why again".
