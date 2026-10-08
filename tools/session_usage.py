#!/usr/bin/env python3
"""세션 기록에서 토큰이 어디로 갔는지 센다 — 메인 세션과 에이전트 종류별로. 고치기 전과 뒤를 견줄 때 쓴다.

  python3 tools/session_usage.py <게임 저장소 경로>             그 저장소의 가장 새 세션
  python3 tools/session_usage.py <게임 저장소 경로> --all       모든 세션을 하나씩
  python3 tools/session_usage.py <세션.jsonl>

읽기만 한다. "무게" 는 값을 어림한 것이다: 새 입력 1 · 캐시 쓰기 1.25 · 캐시 읽기 0.1 · 출력 5. 모델의 값 차이는 넣지 않았다.
견줄 숫자 — 메인 세션의 평균 컨텍스트(턴마다 다시 읽는 양), 에이전트 한 번의 캐시 쓰기(그 에이전트가 새로 읽은 양)와 걸린 시간.
"""
import collections
import datetime
import glob
import json
import os
import re
import sys


def scan(path):
    """(토큰 합, 턴 수, 모델, 걸린 초, 턴마다의 컨텍스트 크기)"""
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
            seen[m.get("id") or d.get("uuid")] = (m.get("model"), m["usage"])  # 같은 응답이 여러 줄로 적힌다
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
    rows["(메인 세션)"] = [tot, 1, turns, 0.0, {model}]
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
    print(f"{os.path.basename(session)} — 메인 세션 {turns}턴 · 컨텍스트 평균 {sum(sizes) // max(1, len(sizes)) // 1000}k · 최대 {max(sizes or [0]) // 1000}k")
    print(f"{'누가':30}{'횟수':>5}{'턴':>6}{'한 번에 캐시쓰기k':>12}{'캐시읽기M':>9}{'출력k':>8}{'무게%':>7}{'한 번에 분':>8}  모델")
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
        sys.exit(f"{logs} 에 세션 기록이 없다")
    for s in sessions if "--all" in sys.argv else sessions[-1:]:
        report(s)


if __name__ == "__main__":
    main()
