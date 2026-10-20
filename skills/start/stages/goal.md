# First goal stage — the first cycle's goal

Read the GDD's `Game structure` and `Scope` (`게임 구조` and `제작 범위` in a GDD made before the titles were English) — not the whole document. If `status` listed skipped stages, mention them once here — a cycle can start without them, but its designer will have less to go on.

## Propose the smallest thing that can be played

The first cycle's goal is **one pass of the innermost loop** — the thing the hands do, once around, ending in the state that says how it went.
Everything that makes the loop matter over time is left out: economy, progression, unlocks, story, menus, saving, sound, final art.

Why: until the innermost loop is in the user's hands nobody knows whether it is worth building on, and every meta system built before that is built on a guess.
Placeholder shapes are fine — the look was agreed in the concept stage and comes in when assets are made.

Offer it as:

```
Goal of the first cycle (recommended): <one sentence — what the player can do from start to end of one loop>
In: <the two or three things that sentence needs>
Out: <named, one by one — each with "after the next cycle">
```

**List what is excluded explicitly.** An exclusion not written down comes back mid-cycle as "이것도 같이" ("this one too").
If the user wants more in, do not argue — say what it adds to the first playable (how many more tasks before they can play) and let them choose. The goal is theirs.

## Hand over

When the user agrees on the goal, in their words, **the CEO runs it from here** — the cycles go on in the background and the user only decides and plays:

- Invoke the ceo skill with that goal. It asks once how its workers may run (its "Setting up"), then starts a worker on the goal (`run new`).
  Do not create the cycle document yourself — the worker's `cycle.py new` does, and from then on `start.py status` says the start is over.
- When that worker has stopped and its line is relayed, recommend `/clear` (not while it runs — its ending wakes this window): this conversation carries the interview,
  and a cleared window is the CEO's again at any message ("계속").
- If the user would rather drive the cycle themselves in this window, invoke the cycle skill with the goal instead — say this in one line, once, with the hand-over.
