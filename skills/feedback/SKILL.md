---
name: feedback
description: >-
  Sends what this game learned that other games would also hit (the lines in docs/kit-feedback.md) to the kit's repository as GitHub issues,
  so the kit grows from every game that uses it — list, preview, send, skip. A script strips dates and cycle numbers, stops on anything that
  looks like the game's name, and finds similar open issues; nothing goes out until the user has seen the exact text and said yes.
  Use when the user says "피드백 보내줘" ("send the feedback"), "키트에 올려줘" ("send it up to the kit"), "배운 거 올리자" ("let's send what we learned"),
  "kit-feedback 보내" ("send kit-feedback"), "이슈로 올려줘" ("open it as an issue"), "쌓인 피드백 보자" ("show the piled-up feedback");
  when the session-start notice says lessons have piled up and the user wants to deal with them. Not for writing a lesson down
  (→ `lesson` of the cycle or playtest skill), and not for a problem in the game itself.
---

# feedback

Lessons pile up in `docs/kit-feedback.md` one line at a time, written where the game tripped (`lesson` of the cycle · playtest skills).
This skill is the way out of the game: each line becomes an issue in the kit's repository, where lines from every game meet.

An issue is public and stays public. So it is split in two: **list · preview** run without asking; **send** runs only after
the user has seen the exact text of each issue and said to send it.

| Call | Meaning |
|---|---|
| `/gamedev-kit:feedback` | Show what has not been sent, preview, and send on approval |
| `/gamedev-kit:feedback list` | Only show the unsent lines |

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" list
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" preview 1,3      # or: all
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" send 1,3
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" send 2 --to 14   # add to issue #14 instead of opening a new one
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" sent 2 14        # the user opened it by hand
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" skip 4 "<why>"
python3 "${CLAUDE_SKILL_DIR}/scripts/feedback.py" state 12,14      # where those issues stand: open · closed (completed) · closed (not planned)
python3 "${CLAUDE_SKILL_DIR}/../voice/scripts/voice.py" rule list --tagged    # the user's own rules already sent to the kit, with their issue numbers
python3 "${CLAUDE_SKILL_DIR}/../voice/scripts/voice.py" rule tag R3 12        # this rule went out as issue #12
```

Numbers count unsent lines only, so they shift after every `send` · `sent` · `skip` — run `list` again before using a number.

The file is `# For the kit`, one line per lesson: `- [ ] (<engine> · cycle 3 · <date>) <what tripped us → how to avoid it>`. A sent line becomes
`[>] … — issue #12`, a skipped one `[-] … — not sent: <why>`. Older files use the Korean words (`# 키트로 올릴 것` · `사이클 3` · `이슈 #12` · `안 보냄: …`) —
the script reads both, and what goes out to an issue is the same either way.

## Procedure

1. **`list`.** Then look at what came back from the kit: `voice.py rule list --tagged` gives the user's own rules that were sent, each with its issue number —
   pass those numbers to `state`. For a rule whose issue is `closed (completed)`, the kit now carries it: ask the user, one line per rule, whether to drop the personal copy
   (`voice.py rule drop R<n>`). **Do not drop without the answer** — and leave alone a rule whose issue is open, closed for another reason, or could not be read.
   If there is nothing unsent and nothing to ask, say so and stop.
2. **Sort the lines before previewing.** Read each one as a stranger on another game would:
   - Relies on this game's structure · rules · names → it should not have been written here. Ask whether to `skip` it (and whether it belongs in the project's CLAUDE.md "Pitfalls").
   - Two lines say the same thing → send one, `skip` the other with "same as: <the other line>".
   - Makes sense without this game → a candidate.
3. **`preview` the candidates.** The output is what goes out: title, body, the engine and the kit version. Two marks need a decision:
   - `!` — a word that looks like this game's name, or a date. Rewrite that line in `docs/kit-feedback.md` so it stands without it, then preview again.
     The script refuses to send it otherwise. `--as-is` only when the user, having seen the word, says to send it as written.
   - `~` — an open issue that looks similar. Decide whether it is the same pitfall (same cause, same way out). The same → `send <n> --to <issue>`;
     it adds one "seen here too" comment, and that count is how the kit knows what to harden first. Not the same → a new issue.
4. **Show the preview as is and ask.** One question for the batch: which numbers go, which join an existing issue. Do not paraphrase the text —
   the user is approving these words. Do not send a line the user did not answer for.
5. **`send` what was approved.** Report the issue numbers.
   Each line sent this way is also one of the user's own rules (a lesson for the kit is a personal rule first). Find it in `voice.py rule list` and write the issue on it —
   `voice.py rule tag R<n> <issue>` — for a new issue and for one joined with `--to` alike. That tag is how step 1 later knows the kit took it in. No matching rule → tag nothing.
   If the script answers with an address instead (no `gh`, or `gh` is not logged in), pass the address on as is — the user opens it and submits.
   When they give the issue number, `list` again and write it with `sent`, and tag the matching rule the same way. Do not log in to `gh` for them.

The script reads the kit's open issues without logging in. If it could not read them it says so — send anyway if the user wants; a duplicate is cheap to merge later.

## Config

Nothing is needed. To change the defaults, in `kit.config.json`:

```json
"feedback": {
  "notice": 5,
  "private": ["a word that must not go out"],
  "repo": "owner/name",
  "gh": "/path/to/gh"
}
```

- `notice` — how many unsent lines before the session-start notice speaks. `false` turns it off.
- `private` — more words to stop on, besides the repository folder's name and the GDD's title.
- `repo` — where the issues go. Left out, it is the repository in the plugin's manifest.
