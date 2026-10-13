#!/usr/bin/env python3
"""Say so once when the session's context grows large (UserPromptSubmit hook).

Every turn the model re-reads the whole conversation so far. Carry a cycle on in one session for days and that grows to hundreds
of thousands of tokens, which eats most of the tokens and the time. The cycle document lets a new session pick the work up
(what it does not hold is left in it first, with the cycle skill's `carry`) — this makes that get said in time.

Only inside a game repository (where kit.config.json is): one line when the context passes 200k tokens, then one for every 100k more.
When nothing is up it prints nothing (what it prints goes into the context). It always exits 0 — it never blocks the user's input.
"""
import json
import os
import sys
import tempfile

FIRST, STEP = 200_000, 100_000
TAIL = 600_000  # read only this much from the end of the log


def in_game(cwd):
    d = os.path.abspath(cwd or ".")
    while True:
        if os.path.exists(os.path.join(d, "kit.config.json")):
            return True
        up = os.path.dirname(d)
        if up == d:
            return False
        d = up


def context_size(path):
    """Tokens read by the last response in the log."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - TAIL))
        lines = f.read().decode("utf-8", "replace").split("\n")
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        u = (d.get("message") or {}).get("usage")
        if d.get("type") == "assistant" and u and not d.get("isSidechain"):
            return u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    return 0


def main():
    data = json.load(sys.stdin)
    path = data.get("transcript_path") or ""
    if not os.path.exists(path) or not in_game(data.get("cwd")):
        return
    size = context_size(path)
    level = 0 if size < FIRST else 1 + (size - FIRST) // STEP
    mark = os.path.join(tempfile.gettempdir(), "gamedev-kit-context", str(data.get("session_id") or "session"))
    try:
        told = int(open(mark).read())
    except (OSError, ValueError):
        told = 0
    if level != told:
        os.makedirs(os.path.dirname(mark), exist_ok=True)
        with open(mark, "w") as f:
            f.write(str(level))
    if level > told:
        print(f"[gamedev-kit] This session's context is about {size // 1000}k tokens — that much is re-read every turn. "
              "At the next stopping point in the work in hand (where a decision is asked · where a round ends · where it is time to play), suggest in one line to the user: "
              "a new session is lighter — `/gamedev-kit:cycle next` in the new session picks the work up (the cycle document holds the state; "
              "work in hand that is not in it is left there first — the cycle skill's \"Leaving a session\"). "
              "Only suggest; if the user says to keep going, carry on with the work.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
