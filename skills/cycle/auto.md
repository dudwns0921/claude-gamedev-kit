# cycle — auto mode

`/gamedev-kit:cycle auto <goal>` starts a cycle, `/gamedev-kit:cycle auto next` continues the newest one — **for this run only**; a plain `next` later is the ordinary mode again.
It is for when the user is away: the cycle runs from Goal to the end of Build without asking anything, and stops where the user has to play.
It needs a voice (`python3 "${CLAUDE_SKILL_DIR}/../voice/scripts/voice.py" path`). Without one, say so and run the ordinary mode.

Everything in `SKILL.md` holds except what is listed here. What changes from its stages:

- **Nothing is shown at the start.** Skip the voice skill's "Review" in Goal — put what `new` printed about the previous cycle in the last message instead.
- **Decisions are not asked.** Wherever a stage says to ask the user — the rule-splitting decisions before Design, and all of them after Plan — follow the voice skill's "Decide" instead:
  a principle picks (`decide D2 "②" --proxy V3`), or failing that the agent's recommendation stands (`--proxy recommended`). Both are written `[~]`, and work that hangs on them goes ahead.
- **Some decisions stay the user's** and are left unanswered: spending money or credits, anything going outward, discarding the user's work, and anything with neither a principle nor a recommendation.
  Tasks that wait on them do not run — `next` shows them as waiting. Go on with the rest.
- **Assets that do not exist are placeholders.** Do not generate models, sounds or videos — that costs money and needs the user's eye. Write the need down as an unanswered decision (`ask`).
- **A blocked task gets one more try**: call `plan` again with "Why blocked" attached, run the reworked task once. Still blocked → leave it `[!]`.
- **Anything else you would have asked** becomes an unanswered decision (`ask`) and you go on. Do not stop to wait, and do not recommend a new session mid-run.
- **It ends at Play.** After the wrap-up (gdd-sync · table export · the project's verification), set the stage to Play and stop. Never ship, never start a second cycle —
  a cycle built on one nobody played stacks guesses on guesses.

The last message of the run is what the user reads when they are back. Keep it to this:

1. What was built and what to play and look at (as at the end of Build).
2. **Decided in your place** — one line each: the decision, what was chosen, and whether the voice chose it (`V3`) or it was only the agent's recommendation (`recommended`). The `recommended` ones first.
3. **Left for you** — the unanswered decisions and the tasks waiting on them; blocked tasks and why.
4. If verification failed, say so first of all, with what failed.
