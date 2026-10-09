---
name: voice
description: >-
  Keeps the user's voice — one short document of how this user decides, whatever the game or engine: the principles their past decisions
  follow, their biases, and what is not yet known — written from the decisions recorded in every game's cycle documents (docs/cycle/).
  It lives outside the game repos (~/.config/gamedev-kit/voice/) and grows across games.
  Before decisions are asked it records a prediction of each answer, then scores the predictions against what the user actually said,
  so the hit rate shows how far the voice can be trusted. It does not decide for the user. Use when the user says "보이스 만들어줘",
  "보이스 갱신", "내 판단 정리해줘", "내 성향 문서", "내 편향이 뭐야", "예측 얼마나 맞아", "적중률"; when the cycle skill reaches the point
  of asking decisions and a voice exists (predict), gets the answers (score), or writes the 회고 (update).
---

# voice

The cycle documents hold every decision the user made — the question, the options, what the agent recommended, and the answer in the user's own words.
The voice is what those answers have in common, written short enough to read before every round of decisions.

**The voice belongs to the person, not to a game.** It lives in the voice home — `~/.config/gamedev-kit/voice/`, or wherever `GAMEDEV_KIT_VOICE` points —
and every game the user makes adds to the same document. Where a game is headed is that game's GDD; the voice holds only what would still be true in the next game.

| In the voice home | |
|---|---|
| `VOICE.md` | the voice — written here, corrected by the user |
| `log.md` | predictions and their scores — the script only |
| `seen.txt` | which decisions the voice has already been written from — the script only |

**The home is a clone of one private git repository** — that repository is where the voice is kept; there are no copies to keep in step. `sync` commits what changed,
takes what another machine pushed, and pushes. Run it **before reading the voice and after writing to it** (it says so in one line; relay only what is not "저장소와 같다").
If it stops because two machines edited the same lines, do not write to the voice until the user has merged it.

It is **a measured guess, not a stand-in.** The user still answers every decision. What this skill adds is a prediction written down before the question is asked
and scored after — the hit rate says which kinds of decisions the voice already gets right.

| Call | Meaning |
|---|---|
| `/gamedev-kit:voice` | Write the voice, or bring it up to date with the decisions made since |
| `/gamedev-kit:voice stats` | The hit rate of the predictions so far |
| `/gamedev-kit:voice setup <repo url>` | Tie the voice home to the user's private repository — once per machine |

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" path             # where the voice is — exits 1 if there is none yet
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" collect          # this game, per cycle: the goal and the answered decisions, tagged 갈림 · 같음 · ?
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" collect new      # only the decisions the voice has not been written from yet
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" collect done     # after writing: mark them read
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" predict D2 ② V3  # before asking. no principle applies → predict D2 -
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" score            # after the answers are recorded
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" stats
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" sync "<one line: what changed>"   # before reading · after writing
```

**Do not read the cycle documents to do any of this.** `collect` pulls out the decision lines; that is all the voice is written from.

## setup — once per machine

The user makes an empty **private** repository themselves and gives its address. Nothing else to install or log in to — the script uses the login git already has.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/voice.py" setup <repo url>
```

On a machine with no voice it clones; on a machine that already has one it turns that folder into the repository. It stops if the repository can be read without logging in
(public), and if both the repository and this machine hold a voice — which one stays is the user's call.

Then go straight on, without waiting to be asked for each step: `sync` → the one question below → if this is a game with decisions the voice has not read
(`collect new` prints any), "Writing · updating". One call from the user should end with a voice in the repository.

**Pushing is going outward, so it is asked.** Ask once: "may the voice be pushed to this repository without asking each time?" — if yes, `voice.py autopush on`
(kept on this machine only; the script refuses unless the repository is private). Without that, `sync` reports unpushed commits and you ask before `sync --push`.

If `sync` says the home is not a repository, say in one line that the voice stays on this machine until `/gamedev-kit:voice setup <private repo url>` — once, not every time.

## Writing · updating

1. Run `sync`, then `path`. Then `collect new` — in a game the voice has never read, that is everything. `[갈림]` marks an answer that went against the recommendation, `[같음]` one that followed it,
   `[?]` one where the answer names no option — read those and tell which way it went.
2. Write `VOICE.md` in the voice home in the shape below. When updating, read the document (it is short) and change only what the new decisions move.
3. Show the user what was added or changed, principle by principle, and ask what is wrong. **What the user corrects outranks what was inferred** —
   write it in their words and cite it as `근거: 사용자가 적음 (<date>)`.
4. Run `collect done`, so the next update starts after these, then `sync "<what changed, one line>"`.

```markdown
# 보이스

갱신: <date> · 결정 <n>개 · 게임 <n>개에서

## 원칙
- V1. <when a decision splits this way, the user goes that way — one line> — 근거: <게임> 02 D3 · <게임> 03 D1 · 갈림 2
- V2. … — 근거: … · 한 게임

## 편향
- <the side the user keeps taking against the recommendation, and what it has cost or bought> — 근거: <게임> 02 D3 · <게임> 04 D2

## 모르는 것
- <a kind of decision with one answer behind it, or answers that pull apart> — <게임> 03 D4
```

- **Write what holds in the next game.** A principle is about how the user decides — scope, difficulty, how much to explain, when to cut — not about this game's rules,
  names or numbers. If it cannot be stated without the game's nouns, it belongs in that game's GDD, not here.
- A principle seen in one game only is marked `한 게임`. It predicts in that game as usual; in another game treat it as weaker, and drop the mark when a second game agrees.

- **A principle needs two decisions behind it.** One answer goes under "모르는 것" until a second agrees. Do not fill a principle in from what seems likely of the user.
- **A principle settles a split.** "prefers simplicity" predicts nothing; "between a new rule and stretching an existing one, stretches the existing one" does.
  If it could not pick between two options of a real decision, it is not a principle yet.
- `갈림` weighs more than `같음` — following the recommendation says little about the user; going against it says a lot. Count them in the citation.
- **편향** is described, not corrected and not obeyed. It is where the user's pull is strongest, so it is also where a prediction should say that the pull is at work.
- **Numbers are never reused.** The prediction log cites `V3`; when a principle turns out wrong, strike it through (`~~V3. …~~`) and add a new number.
- Keep the document under sixty lines. When it grows past that, merge principles that always fire together.
- Set `갱신:` to today and bring the counts up to date.

## Predict — before decisions are asked

Called from the cycle skill, once the decisions are numbered (`cycle.py ask`) and before the user sees them. Run `sync`, then `path` — skip the rest if there is no voice yet.

Read the voice. For each unanswered decision, either a principle picks one option — `predict D2 ② V3` — or none does — `predict D2 -`.
**Do not stretch a principle to cover a decision it does not speak to;** 모름 is an answer, and a forced guess makes the hit rate mean nothing.
The script refuses a prediction for a decision that already has an answer, so this cannot be done afterwards.

**Do not show the predictions with the questions.** A prediction beside a question pulls the answer toward it, and then the score measures the pull.

## Score — after the answers

Once the answers are recorded (`cycle.py decide`), run `score`. It compares the option each answer names with the prediction. Where an answer names no option
it prints the line — judge it and run `score <cycle> <D> hit|miss`. An answer that takes neither option as offered is a miss.

Then `sync`. Relay the result in one line per decision, then one line of `stats`. For each miss, say which principle it was predicted from — a principle that misses twice is rewritten at the next update.

## stats

Relay the output of `stats` as-is: the hit rate overall, per game (once there are two), per asker (기획 · 디자인 · 계획) and per principle, and how many decisions the voice had nothing to say about.
