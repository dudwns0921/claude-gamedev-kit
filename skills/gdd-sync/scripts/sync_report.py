#!/usr/bin/env python3
"""Matches the GDD sync table (GDD 부록 A) against the `GDD: <ID>` markers in code.

Usage:
  python3 sync_report.py                 # print the report (markdown)
  python3 sync_report.py --json          # print JSON
  python3 sync_report.py --write         # update the '코드 위치' and '상태' columns of the GDD table (the 값 column is never touched)
  python3 sync_report.py --only BAL.CYCLE.ACTIVE_SEC   # one ID only

Why a script: once there are dozens of items, matching by hand misses some every time. The script finds "what is where";
"which side is right" is judged by a person (or Claude). So --write writes only location and state, never a value.

What differs per engine (code extensions · folders to skip · the regex that picks a symbol) is in "gdd-sync" in the project root's kit.config.json.
The marker does not care about the comment sign — `# GDD: X` · `-- GDD: X` · `// GDD: X` are all found as `GDD: X`.
"""
import argparse, json, os, re, sys

CONFIG_NAME = "kit.config.json"
SECTION = "gdd-sync"
DEFAULTS = {
    "gdd": "docs/GDD.md",
    "appendix_heading": "## 부록 A",
    "code_ext": [],
    "skip_dirs": [".git", ".claude", "docs", "build"],
    # The regex that picks the symbol name from before the marker. Group 1 is the name
    "symbol": r"(?:local\s+function|const|var|local|function|func|enum|class)\s+([A-Za-z_][A-Za-z0-9_.:]*)",
    # Categories whose values are numbers, so they can be compared automatically
    "numeric_prefixes": ["BAL", "HUD"],
}

ROW_RE = re.compile(r"^\|\s*([A-Z]+(?:\.[A-Z0-9_]+)+)\s*\|(.*)$")
MARK_RE = re.compile(r"GDD:\s*([A-Z]+(?:\.[A-Z0-9_]+)+)")
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

ROOT = ""
CFG = dict(DEFAULTS)


def find_root(start):
    """Walk up from the current folder to the one holding kit.config.json. The tools live in the plugin; the game lives elsewhere."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            sys.exit(f"{CONFIG_NAME} not found — run this inside a game repository, after /gamedev-kit:init")
        d = up


def load_config(root):
    cfg = dict(DEFAULTS)
    path = os.path.join(root, CONFIG_NAME)
    if os.path.exists(path):
        section = json.load(open(path, encoding="utf-8")).get(SECTION, {})
        cfg.update({k: v for k, v in section.items() if k in DEFAULTS})
    if not cfg["code_ext"]:
        sys.exit(f"{SECTION}.code_ext in {CONFIG_NAME} is empty — install the engine config with /gamedev-kit:init")
    return cfg


def parse_table(path):
    """Each row of 부록 A as a dict. Column order: ID | 값(또는 규칙) | 출처 | 코드 위치 | 상태 | 비고"""
    rows, lines = [], open(path, encoding="utf-8").read().split("\n")
    in_appendix = False
    for i, line in enumerate(lines):
        if line.startswith(CFG["appendix_heading"]):
            in_appendix = True
        if not in_appendix:
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) < 5:
            continue
        rows.append({"id": m.group(1), "value": cells[0], "source": cells[1], "location": cells[2],
                     "status": cells[3], "note": cells[4] if len(cells) > 4 else "", "line": i})
    return rows, lines


def scan_code():
    """Find the GDD: <ID> markers across the code. The value on the same line is picked up too."""
    found = {}
    exts, skip = set(CFG["code_ext"]), set(CFG["skip_dirs"])
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for fn in sorted(filenames):
            if os.path.splitext(fn)[1] not in exts:
                continue
            p = os.path.join(dirpath, fn)
            try:
                text = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for ln, line in enumerate(text.split("\n"), 1):
                for m in MARK_RE.finditer(line):
                    rel = os.path.relpath(p, ROOT)
                    symbol = extract_symbol(line)
                    value = extract_value(line)
                    found.setdefault(m.group(1), []).append(
                        {"file": rel, "line": ln, "symbol": symbol, "value": value, "text": line.strip()})
    return found


def extract_symbol(line):
    """Pick the symbol name from before the marker. What follows the marker is not looked at — so 'GDD:' itself is not taken as a symbol."""
    before = line.split("GDD:")[0]
    m = re.search(CFG["symbol"], before)
    if m:
        return m.group(1)
    m = re.search(r'"?([A-Za-z_][A-Za-z0-9_]*)"?\s*[:=]', before)
    return m.group(1) if m else ""


def extract_value(line):
    """The one number before the marker, as in `= 12`, `: 12`, `= 12.0,`. None if there is none. A C# suffix like `8f` is dropped."""
    before = line.split("GDD:")[0]
    m = re.search(r"[:=]\s*(-?\d+(?:\.\d+)?)[fFdD]?\s*[,;]?\s*(?:#|//|--)?\s*$", before)
    return float(m.group(1)) if m else None


def gdd_numbers(value):
    """'12' → (12,12); '20~25' → (20,25); '4배' → (4,4); None if there is no number."""
    nums = NUM_RE.findall(value)
    if not nums:
        return None
    if "~" in value and len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    return float(nums[0]), float(nums[0])


def judge(row, hits):
    if not hits:
        return "미구현", ""
    rng = gdd_numbers(row["value"]) if row["id"].split(".")[0] in CFG["numeric_prefixes"] else None
    vals = [h["value"] for h in hits if h["value"] is not None]
    if rng and vals:
        lo, hi = rng
        bad = [v for v in vals if not (lo <= v <= hi)]
        if bad:
            return "불일치", f"GDD={row['value']} code={', '.join(str(int(v) if v.is_integer() else v) for v in bad)}"
        return "동기", ""
    # For items that cannot be compared as numbers (enums · rules · inputs), a marker only confirms the location.
    # Whether the content matches is for a person to see — so it is marked '동기?' to ask for a judgment.
    return "동기?", "marker found, but the value cannot be compared automatically. Read the code and judge"


def location_str(hits):
    return ", ".join(f"{h['file']}:{h['symbol'] or h['line']}" for h in hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--root", help="project root (default: where kit.config.json is). For tests")
    a = ap.parse_args()
    global ROOT, CFG
    ROOT = os.path.abspath(a.root) if a.root else find_root(os.getcwd())
    CFG = load_config(ROOT)
    gdd = os.path.join(ROOT, CFG["gdd"])

    rows, lines = parse_table(gdd)
    found = scan_code()
    report = []
    for r in rows:
        if a.only and r["id"] != a.only:
            continue
        hits = found.get(r["id"], [])
        status, detail = judge(r, hits)
        report.append({**r, "hits": hits, "new_status": status, "detail": detail})

    orphans = sorted(set(found) - {r["id"] for r in rows})
    stale = [r for r in report if r["location"] != "—" and not r["hits"]]

    if a.json:
        print(json.dumps({"items": report, "orphans": {k: found[k] for k in orphans},
                          "stale": [r["id"] for r in stale]}, ensure_ascii=False, indent=2))
    else:
        counts = {}
        for r in report:
            counts[r["new_status"]] = counts.get(r["new_status"], 0) + 1
        print("# GDD sync report\n")
        print("| State | Count |\n|---|---|")
        counts["폐기"] = sum(1 for r in report if r["status"] == "폐기")
        counts["미구현"] = counts.get("미구현", 0) - counts["폐기"]
        for k in ("동기", "동기?", "불일치", "미구현", "폐기"):
            if counts.get(k):
                print(f"| {k} | {counts[k]} |")
        print()
        for label, pred in (("## 불일치 — needs a human decision", lambda r: r["new_status"] == "불일치"),
                            ("## 동기? — read the code and check", lambda r: r["new_status"] == "동기?"),
                            ("## 동기", lambda r: r["new_status"] == "동기")):
            sel = [r for r in report if pred(r)]
            if not sel:
                continue
            print(label + "\n\n| ID | GDD | Code location | Note |\n|---|---|---|---|")
            for r in sel:
                print(f"| {r['id']} | {r['value']} | {location_str(r['hits'])} | {r['detail']} |")
            print()
        # 폐기 is naturally absent from code — mixed into the 미구현 list it becomes noise to read past every time
        missing = [r["id"] for r in report if r["new_status"] == "미구현" and r["status"] != "폐기"]
        if missing:
            print(f"## 미구현 ({len(missing)})\n\n" + ", ".join(missing) + "\n")
        if orphans:
            print("## 고아 표식 — IDs in code but not in the table\n")
            for k in orphans:
                print(f"- {k}: " + location_str(found[k]))
            print()
        if stale:
            print("## Items whose code location in the table no longer holds\n")
            for r in stale:
                print(f"- {r['id']}: the table says `{r['location']}` but no marker was found")
            print()

    if a.write:
        changed = 0
        for r in report:
            # 폐기 is a person's note that "this item is gone now". Having no marker in code is natural, so
            # turning it back to 미구현 automatically would erase the 폐기 mark every time.
            if r["status"] == "폐기":
                continue
            loc = location_str(r["hits"]) or "—"
            st = r["new_status"].replace("동기?", "동기")  # the table keeps only three states
            if r["new_status"] == "동기?" and r["status"] == "불일치":
                st = "불일치"  # a 불일치 written by a person is not cleared automatically
            line = lines[r["line"]]
            cells = line.split("|")
            # cells[0] is an empty string, cells[1]=ID, [2]=값, [3]=출처, [4]=코드 위치, [5]=상태
            if cells[4].strip() != loc or cells[5].strip() != st:
                cells[4], cells[5] = f" {loc} ", f" {st} "
                lines[r["line"]] = "|".join(cells)
                changed += 1
        if changed:
            open(gdd, "w", encoding="utf-8").write("\n".join(lines))
        print(f"[write] GDD table updated: {changed} rows", file=sys.stderr)


if __name__ == "__main__":
    main()
