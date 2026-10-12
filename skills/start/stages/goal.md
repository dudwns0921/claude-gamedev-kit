# 첫 목표 단계 — the first cycle's goal

Read the GDD's `게임 구조` and `제작 범위` (not the whole document). If `status` listed skipped stages, mention them once here — a cycle can start without them, but its designer will have less to go on.

## Propose the smallest thing that can be played

The first cycle's goal is **one pass of the innermost loop** — the thing the hands do, once around, ending in the state that says how it went.
Everything that makes the loop matter over time is left out: economy, progression, unlocks, story, menus, saving, sound, final art.

Why: until the innermost loop is in the user's hands nobody knows whether it is worth building on, and every meta system built before that is built on a guess.
Placeholder shapes are fine — the look was agreed in the concept stage and comes in when assets are made.

Offer it as:

```
첫 사이클의 목표 (권함): <one sentence — what the player can do from start to end of one loop>
들어가는 것: <the two or three things that sentence needs>
들어가지 않는 것: <named, one by one — each with "다음 사이클 이후">
```

**List what is excluded explicitly.** An exclusion not written down comes back mid-cycle as "이것도 같이".
If the user wants more in, do not argue — say what it adds to the first playable (how many more tasks before they can play) and let them choose. The goal is theirs.

## Hand over

When the user agrees on the goal, in their words:

- Say that the next step is `/gamedev-kit:cycle` with that goal, **and recommend a fresh session** — this one carries the interview; the cycle skill reads the GDD and DESIGN.md from the files.
- Give the goal as one line they can paste: `/gamedev-kit:cycle <the goal, in the user's words>`.
- If the user wants to go on in this session, invoke the cycle skill with that goal. Do not create the cycle document yourself — `cycle.py new` does, and from then on `start.py status` says the start is over.
