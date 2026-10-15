---
name: feedback
description: >-
  Keeps the user's own rules — what their games taught that would trip them again (a trap, a way to verify, a way of working), one line each, on this machine
  and loaded into every game of theirs — and sends them to the kit's repository as GitHub issues, so the kit grows from every game that uses it.
  Rules are written where the game trips (add), go to the kit by themselves once the user has said so (auto · push), or when the user sends them
  (preview · send); a script blocks anything that names a game or a date. When the kit has taken a rule in (its issue closed as completed), the user is asked
  whether to drop their copy. Use when a cycle · playtest step writes down a lesson (add); when the user says "내 규칙 보여줘" ("show my rules"),
  "이건 내 규칙으로" ("make this one of my rules"), "내 규칙에서 빼줘" ("drop it from my rules"), "피드백 보내줘" ("send the feedback"),
  "키트에 올려줘" ("send it up to the kit"), "배운 거 올리자" ("let's send what we learned"), "이슈로 올려줘" ("open it as an issue");
  when the session-start notice asks how rules go to the kit, or says some are held back. Not for a problem in the game itself.
---

# feedback

**The user's rules** are what their games taught — one line each, kept outside every game in `~/.config/gamedev-kit/rules/`
(`rules.md` whatever the engine, `rules-<engine>.md` for one engine). The kit rules block of every game's CLAUDE.md imports both files,
so a rule added now holds from the next session, in every game of theirs. Nothing about them is asked: they stay on this machine.

The ones that hold for anyone go on to **the kit**, as issues in its public repository, where rules from every game meet and the kit's sweep turns them into
the kit's own rules. Deciding which lesson holds for every game is not asked of the user, line by line — it is the sweep's job, reading them together.
The user answers once how rules go out, and from then on they go by themselves; what names a game or a date is held back.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" add "<the rule and its reason>"   # a rule for this engine's games (--any: whatever the engine)
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" list            # the rules this game loads, each with its state (--all: every file)
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" drop R3
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" keep R3 "<why>" # the user's alone — never sent
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" auto on         # the user's standing answer: send by themselves (off: only when the user sends)
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" push            # send what can go now (a hook does this after every turn while auto is on)
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" preview R3,R5   # what would go out, and similar open issues
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" send R3,R5      # send these now (--to 14: comment on issue #14 instead)
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" sent R3 14      # the user posted it by hand
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" state           # every sent rule's issue: open · closed (completed) · closed (not planned)
```

The dashboard's Rules page shows the same ledger and runs the same commands.

## Writing a rule (add)

Called from the cycle and playtest skills where the game tripped. A lesson is sorted into one of two places:

- Only this game (its structure · its names · its files) → the game's own CLAUDE.md "Pitfalls", not here.
- Would trip this user again in another game (their engine, genre, tools, way of working) → `add` (`--any` when it holds whatever the engine).

Write the rule so it stands in another game: what to do or check, and why — `<what tripped us> → <how to avoid it>`. The script notes the game it came from;
that name never goes out. Do not tell the user a rule was added unless they asked to see their rules.

## Asking once

When the session-start notice says the user has not been asked, ask at a stopping point — once, in two lines:
"Rules you learn go to the kit's public GitHub as issues, so the next version avoids them for everyone — the kit's maintainer sorts them; anything naming your game or a date is held back.
Send them by themselves from now on?" Yes → `auto on`; no → `auto off` (then they go only when the user sends them, here or on the dashboard). Either can change later.

Sending needs `gh` logged in. If `push` says it waits for gh, tell the user in one line (`gh auth login`); do not log in for them.

## Held back

`list` marks with `!` a rule that names a game (the game folder's name, the GDD's title, the game it came from, `private-words.txt` in the rules folder) or a date.
It does not go out until reworded: offer a rewording that keeps the rule and its reason, and on the user's yes edit that line in the rules file
(`list` shows which). `keep R<n> "<why>"` when the user says it is theirs alone.

## When the user sends (auto off, or "send this now")

1. `preview` the rules — show the output as is; the user is approving these words. `~` marks an open issue that looks similar: the same pitfall (same cause, same way out)
   → `send R<n> --to <issue>`, which adds a "seen here too" comment — that count is how the kit knows what to harden first; otherwise a new issue.
2. `send` what the user said yes to. If the script answers with an address instead (no `gh`), pass it on; when they give the issue number, `sent R<n> <number>`.

## When the kit has taken a rule in

At a stopping point, or when the user asks to see their rules, run `state`. For each `closed (completed)`, the kit carries it now: ask, one line per rule,
whether to drop their copy (`drop R<n>`) — the copy is read on every turn, so dropping saves tokens. **Do not drop without the answer.**
Leave alone a rule whose issue is open, closed as not planned (the kit will not carry it — it stays the user's), or could not be read.

## Config

Nothing is needed. In `kit.config.json`:

```json
"feedback": {
  "notice": 5,
  "private": ["a word that must not go out"],
  "repo": "owner/name",
  "gh": "/path/to/gh"
}
```

- `notice` — with auto off, how many unsent rules from this game before the session-start notice speaks. `false` turns it off.
- `private` — more words to hold back on, besides the game folder's name and the GDD's title.
- `repo` — where the issues go. Left out, it is the repository in the plugin's manifest.

Before the rules folder existed, rules lived in the voice folder (`~/.config/gamedev-kit/voice/`) and lessons for the kit in each game's `docs/kit-feedback.md`.
The first run copies the rules over (the old folder is left as it was), and takes a game's unsent lesson lines in once — a line much like a rule already there is marked as that rule.
