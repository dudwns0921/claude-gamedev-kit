---
name: voice
description: >-
  Keeps the user's voice — one short document of how this user decides, whatever the game or engine: the principles their past decisions
  follow, their biases, and what is not yet known. It lives outside the game repos (~/.config/gamedev-kit/voice/, a private repository)
  and grows across games. It works behind the cycle without being shown: predicts each answer before a decision is asked, scores the
  prediction against what the user said, and folds the answer into the voice — and in the cycle's auto mode it is what decides in the
  user's place. The user sees it only when they ask or when a cycle ends. Use when the user says "보이스 보자", "보이스 보여줘",
  "내 판단 정리해줘", "내 편향이 뭐야", "보이스 고쳐줘", "예측 얼마나 맞아", "적중률"; when the cycle skill asks decisions (predict),
  gets the answers (score · learn), decides in auto mode (decide), or writes the 회고 (review); when tying the voice to its repository (setup).
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

**It stays in the background.** Predicting, scoring and learning happen without a word to the user — no predictions, no hit rates, no "I updated your voice".
The user sees the voice at two moments only: when a cycle ends (회고) and when they ask ("보이스 보자"). Everything else in this skill is done silently and briefly.

| Call | Meaning |
|---|---|
| `/gamedev-kit:voice` | Review — show what the voice has picked up since the user last looked, and correct it |
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
(`collect new` prints any), "Learn". One call from the user should end with a voice in the repository.

**Pushing is going outward, so it is asked.** Ask once: "may the voice be pushed to this repository without asking each time?" — if yes, `voice.py autopush on`
(kept on this machine only; the script refuses unless the repository is private). Without that, `sync` reports unpushed commits and you ask before `sync --push`.

If `sync` says the home is not a repository, say in one line that the voice stays on this machine until `/gamedev-kit:voice setup <private repo url>` — once, not every time.

## Learn — folding answers into the voice

Done silently: after "Score" in a cycle, at setup, and whenever `collect new` has decisions the voice has not read.

1. Run `sync`, then `collect new` — in a game the voice has never read, that is everything. `[갈림]` marks an answer that went against the recommendation, `[같음]` one that followed it,
   `[?]` one where the answer names no option — read those and tell which way it went. `[받음]` is a proxy decision (auto mode) the user accepted — it counts like `같음`,
   never as proof of the principle that made it. `[바꿈]` is a decision the user answered and later answered again — both answers are on the line, old → new.
   It comes back in `collect new` even if the voice read the first answer. **This is the best material there is: read what changed between the two answers** —
   what was built, played or learned in between — and which way the user moved.
2. Read `VOICE.md` (it is short) and change only what the new decisions move: add the decision to the principle it agrees with, note the one it goes against,
   promote a "모르는 것" that now has two decisions behind it. If nothing moves, change nothing.
   **When an answer goes against a principle** — a missed prediction, an overturned proxy, a `[바꿈]`, a `[갈림]` the principle did not expect — do not strike the principle first.
   The same person answers the same question differently when the situation differs, so look for the situation:
   - **The answer says why** ("because it has to run on the web", "it felt slow once I played it") → write that as a condition on the principle, in the user's words:
     `V7. … — 다만 <그 상황>이면 <반대쪽>`. Cite the decision.
   - **The answer does not say why** → do not guess the reason. Add one line under "모르는 것": `왜 달랐나 — V7 인데 <게임> 03 D2 는 ②: "<the answer verbatim>"`. It is asked at "Review".
   - Strike or reword the principle only when it has gone wrong twice with no situation that explains it.
3. **End every line you added or reworded with `· 안 봄`** — the user has not seen it yet. A line that only gained a citation keeps its state.
4. Run `collect done`, then `sync "<what changed, one line>"`. Say nothing to the user.

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
- **A principle may carry its conditions.** "Picks the cheap route first — 다만 it is the heart of the project and the costly route is clearly better, then straight to that" is one principle,
  not two that contradict. A condition is added only from a reason the user gave; a principle with more than two conditions is really two principles — split it.
- **A principle settles a split.** "prefers simplicity" predicts nothing; "between a new rule and stretching an existing one, stretches the existing one" does.
  If it could not pick between two options of a real decision, it is not a principle yet.
- `갈림` weighs more than `같음` — following the recommendation says little about the user; going against it says a lot. Count them in the citation.
- **편향** is described, not corrected and not obeyed. It is where the user's pull is strongest, so it is also where a prediction should say that the pull is at work.
- **Numbers are never reused.** The prediction log cites `V3`; when a principle turns out wrong, strike it through (`~~V3. …~~`) and add a new number.
- Keep the document under sixty lines. When it grows past that, merge principles that always fire together.
- Set `갱신:` to today and bring the counts up to date.
- **What the user wrote or corrected outranks what was inferred** — keep it in their words, cite it as `근거: 사용자가 적음 (<date>)`, and do not reword it when learning.

## Predict — before decisions are asked

Called from the cycle skill, once the decisions are numbered (`cycle.py ask`) and before the user sees them. Run `sync`, then `path` — skip the rest if there is no voice yet. Silent.

Read the voice. For each unanswered decision, either a principle picks one option — `predict D2 ② V3` — or none does — `predict D2 -`.
**Do not stretch a principle to cover a decision it does not speak to;** 모름 is an answer, and a forced guess makes the hit rate mean nothing.
The script refuses a prediction for a decision that already has an answer, so this cannot be done afterwards.

**Do not show the predictions, with the questions or after.** A prediction beside a question pulls the answer toward it, and then the score measures the pull.

## Score — after the answers

Once the answers are recorded (`cycle.py decide`), run `score`. It compares the option each answer names with the prediction. Where an answer names no option
it prints the line — judge it and run `score <cycle> <D> hit|miss`. An answer that takes neither option as offered is a miss.
A principle that has missed twice (`stats` shows it) is reworded or struck in "Learn". Then go on to "Learn". **Relay none of this.**

## Decide — in the cycle's auto mode

Called from the cycle skill's "Auto mode" in place of asking. Run `sync`, read the voice, and for each unanswered decision:

- **A principle picks an option** → `predict D2 ② V3`, then `cycle.py decide D2 "②" --proxy V3`. A `한 게임` principle decides in the game it came from; in another game it decides
  only if nothing in "편향" or "모르는 것" speaks against it.
- **No principle speaks to it** → `predict D2 -`, then take the asking agent's recommendation: `cycle.py decide D2 "①" --proxy 권함`. This is not the voice deciding — it is the fallback,
  and it is reported first when the user is back.
- **Never decided in the user's place**, whatever the voice says — leave these unanswered: anything that spends money or credits (generating assets), shipping or posting anything outward,
  deleting or discarding the user's work, and a decision with no recommendation and no principle.

Proxy decisions are written `[~]` and are **not evidence**: the voice learns from them only after the user accepts (`cycle.py confirm`) or overturns (`cycle.py decide`) them —
an overturned one is a miss for the principle that made it.

## Review — when a cycle ends, or the user asks

The one place the voice is shown. Run `sync` and read the voice.

- **At 회고** (called from the cycle skill): if any line ends with `· 안 봄`, show those lines only, one per line in plain words, and ask if any is wrong. If none, say nothing.
- **When the user asks** ("보이스 보자"): show the whole voice — 원칙 · 편향 · 모르는 것 — in plain words, the `안 봄` lines marked as new, and one line from `stats`.

**Then ask why, for what went against a principle without a reason** — the `왜 달랐나` lines under "모르는 것". At most three per review, the newest first, one line each:
what the principle says, what they chose that time, "what was different?". The answer becomes a condition on that principle in their words; "no reason, I just changed my mind" or
no answer → drop the line and count it as a plain miss. This is the only place such a question is asked — never during a cycle's decisions.

Take corrections in the user's words (cite `근거: 사용자가 적음 (<date>)`); strike what they reject (`~~V3. …~~`). Then remove `· 안 봄` from every line shown and `sync "<what changed>"`.
The user may also edit `VOICE.md` by hand at any time — treat what you find there as theirs.

## stats

Relay the output of `stats` as-is: the hit rate overall, per game (once there are two), per asker (기획 · 디자인 · 계획) and per principle, and how many decisions the voice had nothing to say about.
