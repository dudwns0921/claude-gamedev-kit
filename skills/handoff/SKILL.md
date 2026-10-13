---
name: handoff
description: >-
  When switching sessions, leaves the work in progress as a short handoff note (docs/handoff/) and continues from it in a new session —
  for moving light to a new session once the conversation and context have grown. Use when the user says "세션 바꾸자" ("let's switch sessions"),
  "새 세션에서 이어가자" ("let's continue in a new session"), "인계 메모 남겨줘" ("leave a handoff note"), "여기까지 정리해줘" ("wrap up where we are"), "handoff";
  in a new session says "이어서 하자" ("let's continue"), "아까 하던 거" ("what we were doing"), "handoff resume";
  or a large-context notice arrived and the current work is not written in a cycle document.
---

# handoff

Every turn the model re-reads the whole conversation so far. The longer the conversation, the more tokens and time the same work costs.
Moving to a new session makes it light, but if the user has to re-explain the context, nobody moves. One note replaces that explanation.

| Call | Meaning |
|---|---|
| `/gamedev-kit:handoff` | Leave the current work as a note |
| `/gamedev-kit:handoff resume` | Read the newest note and continue |

**Work inside a cycle needs no note.** All state is in the cycle document — in the new session, `/gamedev-kit:cycle next`. If you were doing cycle work and other work together,
write only the other work in the note and point to the document for the cycle.

## Leaving a note

1. **Write from what you know now.** Do not re-read files to write the note — that makes the session you are leaving heavier.
   **Point only to files inside the repository.** What lives in the session's own folder (subagent transcripts, journals) is deleted with the session —
   if the next session needs a review's or an analysis's findings, copy them into the cycle document or a file in the repository and point to that.
   Run only `git status --short` and `git rev-parse --short HEAD`.
2. Write it to `docs/handoff/YYYY-MM-DD-HHMM-<short-name>.md`. Shape below, **under forty lines.** The reader is a new session that knows nothing of this conversation —
   it must be able to type its first command from this note alone.

```markdown
# Handoff — <what was in progress, one line>

Left: <date time> · commit <7-char hash> · uncommitted changes: <none | files>

## What was in progress
What the user wanted. One or two lines in the user's own words (verbatim).

## Current state
- Done: <what — file path>
- Unfinished: <what, how far — file:line. where to pick up next>
- Running: <background jobs · things being waited on — drop the line if none>

## Decided
What the user decided in this conversation. In the user's own words (verbatim). So it is not asked again.

## Next
1. <first — down to the command to type or the file to open>
2. …

## Watch out
What tripped this conversation up, what must not be touched. Drop the section if none.

## Questions for the user
Unanswered questions. Drop the section if none.
```

3. **Do not write**: the history of the conversation ("first we tried A, but…"), copies of logs and code, content already in files (only point to it), finished things that need no second look.
   If something came up that belongs in CLAUDE.md (a recurring pitfall · a project rule), ask the user whether to write it there, not in the note.
4. Give the note's path and guide in one line: "Open a new session and run `/gamedev-kit:handoff resume`." Do not continue working in this session.

## Resuming

Notes written before the kit moved to English use the Korean words: `# 인계 — …`, `남김:` · `커밋 안 된 변경:`, the sections 하던 일 · 지금 상태 ·
정해진 것 · 다음에 할 일 · 조심할 것 · 사용자에게 물을 것, and `이어받음:` for `Resumed:`. Read them the same way; whatever you append is English.

1. In `docs/handoff/`, read the newest note without a `Resumed:` (older: `이어받음:`) line. If there is none, say so, and if there is a cycle, recommend `/gamedev-kit:cycle next`.
2. Append one line `Resumed: <date time>` at the end of the note — so the next session does not pick up the same note again.
3. If the note's commit differs from the current commit, or "uncommitted changes" differs from now, say that first — the note is a snapshot of when it was left.
4. Start from the first item of "Next". **Do not scan the project to find out what is not in the note** — open only the files that work needs.
   If there is a "Questions for the user", ask those first.

## Keep the notes

Do not delete resumed notes either. The user decides whether to commit them — if they do not want them in, add `docs/handoff/` to `.gitignore`.
