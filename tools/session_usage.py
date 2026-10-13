#!/usr/bin/env python3
"""Count where the tokens went in the session logs — for the main session and per agent type. For comparing before and after a change.

  python3 tools/session_usage.py <game repo path>             that repository's newest session
  python3 tools/session_usage.py <game repo path> --all       every session, one by one
  python3 tools/session_usage.py <session.jsonl>

Read-only. "weight" is a rough cost: new input 1 · cache write 1.25 · cache read 0.1 · output 5. Price differences between models are left out.
Numbers to compare — the main session's average context (what is re-read every turn), and one agent run's cache writes (what that agent newly read) and duration.
"""
import collections
import datetime
import glob
import json
import os
import re
import sys


def scan(path):
    """(token totals, turns, model, seconds taken, context size at each turn)"""
    seen, first, last = {}, None, None
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("timestamp"):
            first, last = first or d["timestamp"], d["timestamp"]
        m = d.get("message") or {}
        if d.get("type") == "assistant" and m.get("usage"):
            seen[m.get("id") or d.get("uuid")] = (m.get("model"), m["usage"])  # one response is logged on several lines
    tot, sizes, model = collections.Counter(), [], None
    for model, u in seen.values():
        a, w, r = u.get("input_tokens", 0), u.get("cache_creation_input_tokens", 0), u.get("cache_read_input_tokens", 0)
        tot.update({"in": a, "cw": w, "cr": r, "out": u.get("output_tokens", 0)})
        sizes.append(a + w + r)
    t = lambda s: datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return tot, len(seen), model, (t(last) - t(first)).total_seconds() if first else 0, sizes


def weight(t):
    return t["in"] + 1.25 * t["cw"] + 0.1 * t["cr"] + 5 * t["out"]


def report(session):
    rows = {}
    tot, turns, model, _sec, sizes = scan(session)
    rows["(main session)"] = [tot, 1, turns, 0.0, {model}]
    for p in glob.glob(os.path.join(session[:-len(".jsonl")], "subagents", "*.jsonl")):
        meta = p[:-len(".jsonl")] + ".meta.json"
        kind = json.load(open(meta)).get("agentType", "?") if os.path.exists(meta) else "?"
        t, n, m, sec, _s = scan(p)
        row = rows.setdefault(kind, [collections.Counter(), 0, 0, 0.0, set()])
        row[0] += t
        row[1] += 1
        row[2] += n
        row[3] += sec
        row[4].add(m)
    whole = sum(weight(r[0]) for r in rows.values()) or 1
    print(f"{os.path.basename(session)} — main session {turns} turns · context average {sum(sizes) // max(1, len(sizes)) // 1000}k · max {max(sizes or [0]) // 1000}k")
    print(f"{'who':30}{'runs':>5}{'turns':>6}{'cache-w k/run':>14}{'cache-r M':>10}{'out k':>9}{'weight%':>8}{'min/run':>9}   model")
    for kind, (t, n, tn, sec, models) in sorted(rows.items(), key=lambda r: -weight(r[1][0])):
        print(f"{kind:30}{n:>5}{tn:>6}{t['cw'] / n / 1e3:>14.0f}{t['cr'] / 1e6:>10.1f}{t['out'] / 1e3:>9.0f}"
              f"{100 * weight(t) / whole:>8.1f}{sec / n / 60:>9.1f}   {' '.join(sorted(str(m) for m in models))}")
    print()


def main():
    args = [a for a in sys.argv[1:] if a != "--all"]
    if len(args) != 1:
        sys.exit(__doc__)
    target = os.path.abspath(os.path.expanduser(args[0]))
    if target.endswith(".jsonl"):
        return report(target)
    logs = os.path.expanduser("~/.claude/projects/" + re.sub(r"[^A-Za-z0-9]", "-", target))
    sessions = sorted(glob.glob(os.path.join(logs, "*.jsonl")), key=os.path.getmtime)
    if not sessions:
        sys.exit(f"no session logs in {logs}")
    for s in sessions if "--all" in sys.argv else sessions[-1:]:
        report(s)


if __name__ == "__main__":
    main()
