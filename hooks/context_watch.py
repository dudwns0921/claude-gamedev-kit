#!/usr/bin/env python3
"""Say so once when the session's context grows large (UserPromptSubmit hook).

Every turn the model re-reads the whole conversation so far. Carry a cycle on in one session for days and that grows to hundreds
of thousands of tokens, which eats most of the tokens and the time. The cycle document lets a cleared session pick the work up
(what it does not hold is left in it first, with the cycle skill's `carry`) — this makes that get said in time.

Only inside a game repository (where kit.config.json is): one line when the context passes 200k tokens, then one for every 100k more.
When nothing is up it prints nothing (what it prints goes into the context). It always exits 0 — it never blocks the user's input.
It also keeps the size where the board reads it (outside the game, in the temp folder, by game). `--record` (the Stop hook) keeps it at the end of a turn
too, and with it whether that turn's answer told the user to `/clear`: the session judges when it is time (the skills and rules say where), and the dashboard
shows only what it said — until a later answer of the same session does not say it, or another session starts. The board decides nothing about it.
"""
import hashlib
import json
import os
import sys
import tempfile
import time

FIRST, STEP = 200_000, 100_000
TAIL = 600_000  # read only this much from the end of the log
KEEP_STEP = 50_000  # the size kept for the board moves in these steps — each step redraws it


def in_game(cwd):
    """The game root above cwd, or None."""
    d = os.path.abspath(cwd or ".")
    while True:
        if os.path.exists(os.path.join(d, "kit.config.json")):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def kept_at(root):
    """Where the size is kept for the board — the same path board.py reads (the tests hold the two together)."""
    return os.path.join(tempfile.gettempdir(), "gamedev-kit-context", "game-" + hashlib.sha1(os.path.realpath(root).encode()).hexdigest()[:16] + ".json")


def keep(root, size, session, said=None):
    """Rewritten only when the session, the size's level or what was said changes — every rewrite makes the board draw again.
    said: whether the turn's answer told the user to /clear (None — not looked at: the prompt hook keeps what the last answer said)."""
    path = kept_at(root)
    level = lambda n: n // KEEP_STEP
    try:
        was = json.load(open(path))
    except (OSError, ValueError):
        was = {}
    same = was.get("session") == session
    pause = (said if said is not None else same and was.get("pause") == session) and session
    if same and level(int(was.get("size") or 0)) == level(size) and (was.get("pause") == session) == bool(pause):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w") as f:
        json.dump(dict({"size": size, "session": session, "at": time.time()}, **({"pause": session} if pause else {})), f)
    os.replace(path + ".part", path)


def said_clear(path):
    """Whether the last answer in the log (the main conversation's, not a subagent's) tells the user to /clear."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - TAIL))
        lines = f.read().decode("utf-8", "replace").split("\n")
    for line in reversed(lines):
        if '"assistant"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "assistant" or d.get("isSidechain"):
            continue
        text = [c.get("text") or "" for c in (d.get("message") or {}).get("content") or [] if isinstance(c, dict) and c.get("type") == "text"]
        if text:
            return "/clear" in "\n".join(text)
    return False


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
    if os.environ.get("KIT_WORKER"):
        return  # a headless worker of the CEO: its size and its words are not the user's window
    data = json.load(sys.stdin)
    path = data.get("transcript_path") or ""
    root = in_game(data.get("cwd"))
    if not root:
        return
    size = context_size(path) if os.path.exists(path) else 0  # a session just cleared has no answer in its log yet
    record = "--record" in sys.argv[1:]
    keep(root, size, str(data.get("session_id") or ""), said_clear(path) if record and os.path.exists(path) else None)
    if record or not os.path.exists(path):
        return
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
              "`/clear` then `/gamedev-kit:cycle next` is lighter — the same window, still connected to the dashboard, picks the work up (the cycle document holds the state; "
              "work in hand that is not in it is left there first — the cycle skill's \"Leaving a session\"). "
              "Only suggest; if the user says to keep going, carry on with the work.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
