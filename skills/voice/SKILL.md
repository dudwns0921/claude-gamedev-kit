---
name: voice
description: >-
  Keeps the user's voice (docs/VOICE.md) — one short document of how this user decides: where the game is headed, the principles
  their past decisions follow, and their biases — written from the decisions recorded in the cycle documents (docs/cycle/).
  Before decisions are asked it records a prediction of each answer, then scores the predictions against what the user actually said,
  so the hit rate shows how far the voice can be trusted. It does not decide for the user. Use when the user says "보이스 만들어줘",
  "보이스 갱신", "내 판단 정리해줘", "내 성향 문서", "내 편향이 뭐야", "예측 얼마나 맞아", "적중률"; when the cycle skill reaches the point
  of asking decisions and docs/VOICE.md exists (predict), gets the answers (score), or writes the 회고 (update).
---

# voice

The cycle documents hold every decision the user made — the question, the options, what the agent recommended, and the answer in the user's own words.
The voice is what those answers have in common, written short enough to read before every round of decisions.

It is **a measured guess, not a stand-in.** The user still answers every decision. What this skill adds is a prediction written down before the question is asked
and scored after — the hit rate says which kinds of decisions the voice already gets right.

| Call | Meaning |
|---|---|
| `/gamedev-kit:voice` | Write the voice, or bring it up to date with the decisions made since |
| `/gamedev-kit:voice stats` | The hit rate of the predictions so far |

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" collect          # per cycle: the goal and the answered decisions, tagged 갈림 · 같음 · ?
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" collect new      # only those answered since the voice's `갱신:` date
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" predict D2 ② V3  # before asking. no principle applies → predict D2 -
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" score            # after the answers are recorded
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" stats
```

**Do not read the cycle documents to do any of this.** `collect` pulls out the decision lines; that is all the voice is written from.

## Writing · updating

1. Run `collect` (no `docs/VOICE.md` yet) or `collect new` (there is one). `[갈림]` marks an answer that went against the recommendation, `[같음]` one that followed it,
   `[?]` one where the answer names no option — read those and tell which way it went.
2. Write `docs/VOICE.md` in the shape below. When updating, read the document (it is short) and change only what the new decisions move.
3. Show the user what was added or changed, principle by principle, and ask what is wrong. **What the user corrects outranks what was inferred** —
   write it in their words and cite it as `근거: 사용자가 적음 (<date>)`.

```markdown
# 보이스

갱신: <date> · 결정 <n>개에서

## 방향
Where the game is headed — two or three lines, in words the user's goals keep repeating.

## 원칙
- V1. <when a decision splits this way, the user goes that way — one line> — 근거: 02 D3 · 03 D1 · 갈림 2
- V2. …

## 편향
- <the side the user keeps taking against the recommendation, and what it has cost or bought> — 근거: 02 D3 · 04 D2

## 모르는 것
- <a kind of decision with one answer behind it, or answers that pull apart> — 03 D4
```

- **A principle needs two decisions behind it.** One answer goes under "모르는 것" until a second agrees. Do not fill a principle in from what seems likely of the user.
- **A principle settles a split.** "prefers simplicity" predicts nothing; "between a new rule and stretching an existing one, stretches the existing one" does.
  If it could not pick between two options of a real decision, it is not a principle yet.
- `갈림` weighs more than `같음` — following the recommendation says little about the user; going against it says a lot. Count them in the citation.
- **편향** is described, not corrected and not obeyed. It is where the user's pull is strongest, so it is also where a prediction should say that the pull is at work.
- **Numbers are never reused.** The prediction log cites `V3`; when a principle turns out wrong, strike it through (`~~V3. …~~`) and add a new number.
- Keep the document under sixty lines. When it grows past that, merge principles that always fire together.
- Set `갱신:` to today — `collect new` reads from that date.

## Predict — before decisions are asked

Called from the cycle skill, once the decisions are numbered (`cycle.py ask`) and before the user sees them. Skip it if there is no `docs/VOICE.md`.

Read `docs/VOICE.md`. For each unanswered decision, either a principle picks one option — `predict D2 ② V3` — or none does — `predict D2 -`.
**Do not stretch a principle to cover a decision it does not speak to;** 모름 is an answer, and a forced guess makes the hit rate mean nothing.
The script refuses a prediction for a decision that already has an answer, so this cannot be done afterwards.

**Do not show the predictions with the questions.** A prediction beside a question pulls the answer toward it, and then the score measures the pull.

## Score — after the answers

Once the answers are recorded (`cycle.py decide`), run `score`. It compares the option each answer names with the prediction. Where an answer names no option
it prints the line — judge it and run `score <cycle> <D> hit|miss`. An answer that takes neither option as offered is a miss.

Relay the result in one line per decision, then one line of `stats`. For each miss, say which principle it was predicted from — a principle that misses twice is rewritten at the next update.

## stats

Relay the output of `stats` as-is: the hit rate overall, per asker (기획 · 디자인 · 계획) and per principle, and how many decisions the voice had nothing to say about.
