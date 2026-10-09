---
name: cycle
description: >-
  Drives one game-dev cycle — 목표 → 기획 → 디자인 → 계획 → 구현 → 플레이 → 배포 → 회고 — through a single document (docs/cycle/).
  Systems designer, designer, developer and deploy agents work stage by stage; every decision goes back to the user.
  Use when the user states a bundle of goals ("이번 사이클", "다음 버전 만들자", "이번엔 ○○ 를 넣자"); says "사이클 이어서",
  "다음 단계", "어디까지 했지"; or answers a decision ("D2 는 ①로"). Not for one-line fixes.
---

# cycle

One cycle runs **until one goal reaches the player's hands**. At each stage the agent in charge works, and results accumulate in one cycle document —
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
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" ask <기획|디자인|계획> "<question — ① … ② … · 권함: ①>"
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" decide D2 "<the user's answer verbatim>"
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" stage <stage>
python3 "${CLAUDE_SKILL_DIR}/scripts/cycle.py" lesson "<what tripped us → how to avoid it>"   # to send up to the kit (in 회고)
```

These act on the newest document (for another, `--doc <path>`). Use Edit only for writing long sections (플레이 · 배포 · 회고) — and even then read only that section's line range, not the whole document.

**Break sessions.** All state is in the document, so a new session continues with one `next`. There are three places to break —
where you asked decisions and stopped, where the build is done and it is the user's turn to play, where the cycle ended. On reaching one, recommend in one line:
"Opening a new session here and continuing with `/gamedev-kit:cycle next` is lighter." If the user says just go on, go on.
Do not chain two or more cycles in one session. If you were also doing work outside the cycle (assets · settings · another repo), leave a note with the handoff skill and move on.

**Not done in this session**: reading code · reading images · reading logs. Agents do all of it and only summaries come back. When relaying an agent's report to the user, do not expand it at length again.

**The user decides.** No agent decides for them. Agents return "Decisions needed" as options plus one recommendation,
this skill collects and asks them, and writes the answers in the document's "결정" section in the user's own words (verbatim). Do not do work that hangs on an unanswered decision.

| Call | Meaning |
|---|---|
| `/gamedev-kit:cycle <goal>` | New cycle. Runs through spec · design · plan, then asks the decisions |
| `/gamedev-kit:cycle next` | Next stage of the newest cycle |
| `/gamedev-kit:cycle status` | Per cycle: current stage · remaining tasks · unanswered decisions |

## Stages

| | Stage | Who | Document section | Stops at |
|---|---|---|---|---|
| 1 | 목표 | user | 목표 | |
| 2 | 기획 | `gamedev-kit:systems-designer` `spec` | 기획 | |
| 3 | 디자인 | `gamedev-kit:designer` `design` | 디자인 | |
| 4 | 계획 | `gamedev-kit:developer` `plan` | 작업 · 순서 | **ask the decisions** |
| 5 | 구현 | `gamedev-kit:developer` `build T<n>`, one per task | task checkboxes | |
| 6 | 플레이 | user (problems go to `/gamedev-kit:playtest`) | 플레이 | **ask whether to ship** |
| 7 | 배포 | deploy skill | 배포 | |
| 8 | 회고 | this session writes, the user corrects | 회고 | **the user sets the next goal** |

### 1. 목표

Create the document with `new` — pass the goal in the user's words as-is, unpolished. Even if the goal looks several cycles big, do not shrink it — whether to shrink is asked as an option at the 계획 stage.
The script creates `docs/cycle/NN-<short-name>.md` from the template below and records the current commit. If it reports uncommitted changes, say so.
If the previous cycle's "회고" has a "다음에", remind the user in one line.

### 2. 기획 · 3. 디자인 · 4. 계획

Who owns what: the **systems designer** owns how the game works (rules · balance numbers · structure and dimensions of spaces), the **designer** owns how it looks and sounds
(UI appearance · effects · sound · assets), the **developer** owns how to build it. A later agent does not edit earlier sections; it takes them as given.

Call them one at a time in the order systems designer → designer → developer (`plan`). Call the next only after the previous returns. Pass only the cycle document path and the mode. Do not attach your own thoughts.

- If the systems designer returns "nothing touches the rules", go straight to 디자인.
- Of the systems designer's "Decisions needed", those that split a rule (is this rule A or B) are **asked first, before going to 디자인** — what the next two write changes wholesale with the answer.
  Do not ask about "시작" values of numbers. They are tuned in the table after the build.
- If the designer or developer returns "Questions for spec", call the systems designer again with them attached, and if the "기획" section changed, call the asker again.
  Do not answer in their place.

If the "디자인" section's "필요한 에셋" lists a 3D model or sound that does not exist, tell the user — whether to make it (asset skill) or go with a placeholder asset is asked as a decision.
If the answer is to make it, follow the asset skill's procedure alongside the build. Approving images and listening to sounds are done by the user in that skill.

Number the "Decisions needed" from all three consecutively (D1 …), write them into the document's "결정" with `ask`, and ask the user all at once —
options · what each costs · the recommendation. Then show the task count and waves. **Stop here.**

If `docs/VOICE.md` exists, between `ask` and asking the user, follow the voice skill's "Predict": read that document and record one prediction per decision
(`python3 "${CLAUDE_SKILL_DIR}/../voice/scripts/voice.py" predict D2 ② V3`, or `predict D2 -` when no principle applies). Do not show the predictions with the questions —
the user still answers every one.

When answers come, record them with `decide D1 "<the user's words verbatim>"` — then, if predictions were recorded, the voice skill's "Score" (`voice.py score`) and relay hits and misses in a line each. If an answer changes the spec · design · plan (scope cut · a different option chosen),
call that agent again to fix its section, and realign the sections of the stages after it. The same goes when the user asks to change the plan directly.

### 5. 구현

`next` lists the next wave's tasks (pending ones are shown as 대기 — do not run them). Per wave, one developer agent per task. Call the same wave all at once in one message.
Pass three lines — `build T<n>`, the document path, and the task-extraction command (`python3 <absolute path to this skill's cycle.py> task T<n> --doc <document>`). **Do not copy out the task content.**
Things that apply identically to every task, like the engine executable's path, are written once in the project's CLAUDE.md — do not repeat them to each agent.
Record returned results with `mark` (agents do not edit the document): done → `mark T1,T3 done`, blocked · failed → `mark T2 blocked "<reason>"`.
Do not fix a blocked task here yourself — ask the user whether to call `plan` again with "Why blocked" attached.

When all waves are done, once: if values · rules changed, `/gamedev-kit:gdd-sync to-gdd`; if the balance value file changed, the balance-table skill's `export`;
the project's full verification (CLAUDE.md "Verification"). Then tell the user what to play and look at, collected from the tasks' "For a human to check", the spec's "플레이해서 볼 것" and the design's "사람이 봐야 아는 것".
The spec's numbers went in as "시작" values — also say which values in the table (`data/balance.xlsx`) to try moving.

### 6. 플레이

The user does this. If a problem list comes, hand it to `/gamedev-kit:playtest` and write that document's path in the "플레이" section.
If given screenshots, you may call the designer with `review`. Any number of rounds is fine.
If the user says they settled values in the table: balance-table skill's `bake` → `/gamedev-kit:gdd-sync to-gdd`.
**The user says whether to ship.** Ask but do not recommend — if `[ ]` · `[!]` tasks or open playtest documents remain, state only those as facts.

### 7. 배포

When the user says ship, follow the deploy skill's procedure. That word is consent up to preparation; the answer given after you show target · version · size before uploading is the consent to upload.
Deploy goes as far as a draft itch.io devlog to attach to the build — the deploy skill writes it, the user pastes it.
If the cycle is not deployed (an internal-only build), skip and record that.

### 8. 회고

Write the "회고" section — facts only: which goals were met and which were not, tasks that were blocked and why, how many playtest rounds, what was deferred.
Under it, in "다음에", list deferred items and things that came out of play as candidates. Do not pick.
**Split what was learned in two.** Collect what tripped this cycle up · engine settings done by hand · newly found ways to check (from the reasons tasks were blocked, the agents' returned "Deviations from the document",
and the playtest documents) and look at each:

- **Specific to this game** (relies on this game's structure · rules · names) → ask whether to write it in the project's CLAUDE.md "Pitfalls".
- **Not specific to this game** (another game on the same engine would hit it, or a kit tool fell short) → add one line each to `docs/kit-feedback.md` with `lesson`.
  Write it so it makes sense without the game's names · files · numbers: "what tripped us → how to avoid (check) it". If the project's CLAUDE.md needs it too, write it in both.

If the split is hard, ask: "Would you need to know this when making another game next time?" If there is nothing, write nothing — do not force-fill.

If this cycle answered decisions, recommend in one line bringing the voice up to date (`/gamedev-kit:voice`) — the first time, once two cycles' decisions exist.

## Cycle document

```markdown
# 사이클 NN — <short name>

시작: <date> · 커밋 <7-char hash> · 단계: 목표

## 목표
In the user's own words (verbatim).

## 결정
- [ ] D1. <question> — ① … ② … · 권함: ① (who recommended it: 기획 | 디자인 | 계획)
- [x] D2. <question> → <the user's answer verbatim> (<date>)

## 기획
## 디자인
## 작업
## 순서
## 플레이
## 배포
## 회고
```

Update the header's `단계:` with `stage` every time the stage changes. `next` and `status` read that line. Keep the stage name short — circumstances go in that section.

## next

Run `cycle.py next` and continue from there — do not read the document. If a document without a `## 기획` section (made before this stage existed) stands before 디자인 or 계획,
call spec first — the systems designer creates the section. A document whose build has already started continues as-is. If it stands at a stopping point (decisions · whether to ship), ask again — do not move on without an answer.

## status

Relay the output of `cycle.py status` as-is.

## Keep the documents

Do not delete finished cycle documents either. The next cycle's systems designer · designer · developer read the previous cycles' decisions and do not ask the same questions again.
