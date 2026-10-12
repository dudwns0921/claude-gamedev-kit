# GDD 단계 — writing the GDD by interview

The user has a game in their head; the GDD template is empty. Your job is to get it out of their head **in their words**, find the holes, and write down only what they confirmed.
You do not design the game. Every rule below exists because the opposite was tried and cost a rewrite.

Before asking anything, read the GDD's body headings once (`docs/GDD.md`, down to `## 부록 A` — not the table rules) so you know where each answer will go.
If some sections already have text (a resumed session), read those and continue from the first topic that has no answer — do not re-ask.

## 1. One loop, in their words

Ask the user to describe **one full loop from the player's seat**, however roughly: who the player is and what they are after, what the hands actually do,
how a round ends, and what carries over to the next one. One open question, no options — options here would put your game in place of theirs.

Then **say it back as nested loops** and let them correct it:

```
몇 초   — <what the hands do once>
한 판   — <how a round starts, what fills it, how it ends>
긴 주기 — <what changes between rounds>
게임 전체 — <where it is going, if anywhere>
```

Mark every line you filled in yourself (`← 내가 채운 것`). A level the user did not mention may simply not exist in this game — ask, do not invent one.
Why this first: every later question ("what squeezes the player?") only has an answer relative to a loop, and a wrong loop found at question eight discards seven answers.

## 2. One question per turn

Then go through the topics below, **one question in one turn**. Each question has:

- **2–4 concrete options**, described by what the player would experience, not by genre words.
- **One marked `권함`, with its reason** in a clause — the reason must come from what this user already said, not from what games usually do.
- **`섞기`** as an option only where a mix is a real design (two pressures at once), not as a way to avoid choosing.

Lead the next turn with the decision restated in one line (`정한 것: …`), then the next question. The restatement is where a misunderstanding gets caught while it is one line old.
Several questions in one turn get one answer and three guesses; a question without options gets "음, 글쎄".

Topic order — each one narrows the next, so keep the order unless the user's answer has already settled a later topic (then skip it and say so):

1. **What squeezes the player during a round** — a clock, a stamina-like resource, or nothing (the player sets the pace).
2. **How time passes** — real time, only when the player acts, or in phases.
3. **What a round is judged by** — what number or state says "that went well".
4. **Can the player lose mid-game** — and if so, what stands between a crisis and an ending (a warning, a buffer, a way to buy back).
5. **Does the game end** — an ending, endless, or seasons.
6. **The list of things the hands do, and the input for each.** Keep the number of distinct inputs small — every extra one is taught, drawn and tested. If two actions can share an input, say so and ask.
7. **The long-lived values** — how many, and which are shown to the player and which are hidden. Each one is a HUD element and a balance axis.
8. **Length of a round, and how much fits in it.**
9. **Scope of the first version** — what is in, and by name what is not.

It is fine to stop at the end of a topic group (after 3, after 5, after 7, after 9) — see "Writing" below; what is confirmed is in the file by then.

## While interviewing

- **Never fill silently.** When you write or assume something the user did not say, state it as a default they can change: `기본으로 둔 것: … — 다르면 말해 달라`. A silent default reads, a week later, as the user's decision.
- **A contradiction is raised in the turn it appears.** When an answer conflicts with something already decided, show both lines, ask which stands, and fix the earlier text when writing. Do not carry it forward hoping it resolves.
- **"Which is better?" gets an answer**: one recommendation and **the single criterion that decides it** ("round 이 2분 안쪽이면 ①, 넘으면 ②"). Laying out pros and cons again hands the question back.
- **Numbers are ranges with the arithmetic shown, never fixed values.** E.g. `한 판 90~150초 — 손이 하는 일 하나가 4~6초 × 한 판에 15~25번 = 60~150초, 여기에 고르는 시간`. The user picks; the range goes into the GDD as a range (`90~150`) until play settles it.
- **Do not create extra planning documents.** No notes file, no question list, no summary document — the GDD is the record. What is not decided goes under the GDD's `미정 사항`.
- Use neutral placeholders in examples you give (`<자원>`, `<적>`). An example with content becomes the content.

## Writing

**Write to the GDD only after a chunk is confirmed.** A chunk is one topic group.

- **The first chunk: show the draft in chat first**, exactly as it would go into the file, and write it after a yes. This is where the user sees how their words turn into GDD text — tone and level of detail are corrected once, here.
- Later chunks may be written straight after a clear yes to the decisions; say in one line which sections changed.
- Where it goes: the loop → `개요` · `게임 구조`; pressure, time, judgement, losing, ending, actions, values → `규칙과 시스템`; first version → `제작 범위`; anything open → `미정 사항` (one line each, with what it is waiting on).
  `톤` and `사운드` only if the user spoke about them. `아트 방향` is the concept stage's — leave it.
- **부록 A**: for every decided **number · enum · rule · input · HUD element**, add a row to the matching table (A.1–A.5) with a new ID (`분류.대상.속성`), `코드 위치` `—`, `상태` `미구현`.
  Numbers still open stay as ranges. Leave the template's three example rows (`예시 — …`) alone — they pair with the example lines in the installed value file and go when those go.
- Then check that the table still parses — use the **gdd-sync skill's report command** (`/gamedev-kit:gdd-sync`, report only; that skill's document gives the script path). New rows must show as `미구현`. Do not import or copy that script.

## End of the stage

`start.py status` shows no empty required section. Tell the user in two or three lines what the GDD now says and what sits under `미정 사항`, then the one line:
this is a good place to close the session — a new session continues with `/gamedev-kit:start` (next: 컨셉).
