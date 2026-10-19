#!/usr/bin/env python3
"""Matches the GDD sync table (GDD Appendix A) against the `GDD: <ID>` markers in code.

Usage:
  python3 sync_report.py                 # print the report (markdown)
  python3 sync_report.py --json          # print JSON
  python3 sync_report.py --write         # update the 'Code location' and 'State' columns of the GDD table (the Value column is never touched)
  python3 sync_report.py --only BAL.CYCLE.ACTIVE_SEC   # one ID only

Why a script: once there are dozens of items, matching by hand misses some every time. The script finds "what is where";
"which side is right" is judged by a person (or Claude). So --write writes only location and state, never a value.

What differs per engine (code extensions · folders to skip · the regex that picks a symbol) is in "gdd-sync" in the project root's kit.config.json.
The marker does not care about the comment sign — `# GDD: X` · `-- GDD: X` · `// GDD: X` are all found as `GDD: X`.

The words are English; a GDD written before that (Korean heading and states) is read the same — see APPENDIX and LEGACY.
A state cell this script rewrites is written in English.
"""
import argparse, json, os, re, sys

CONFIG_NAME = "kit.config.json"
SECTION = "gdd-sync"
DEFAULTS = {
    "gdd": "docs/GDD.md",
    "appendix_heading": "## Appendix A",
    "code_ext": [],
    "skip_dirs": [".git", ".claude", "docs", "build"],
    # The regex that picks the symbol name from before the marker. Group 1 is the name
    "symbol": r"(?:local\s+function|const|var|local|function|func|enum|class)\s+([A-Za-z_][A-Za-z0-9_.:]*)",
    # Categories whose values are numbers, so they can be compared automatically
    "numeric_prefixes": ["BAL", "HUD"],
}

ROW_RE = re.compile(r"^\|\s*([A-Z]+(?:\.[A-Z0-9_]+)+)\s*\|(.*)$")
MARK_RE = re.compile(r"GDD:\s*([A-Z]+(?:\.[A-Z0-9_]+)+)")
NUM_RE = re.compile(r"(?<![A-Z_\d.])-?\d+(?:\.\d+)?")   # not the digits of a reference such as `D24`

# The document's words: written in English, read in both forms.
APPENDIX = ("## Appendix A", "## 부록 A")   # with the default config both headings are found
LEGACY = {"동기": "synced", "불일치": "mismatch", "미구현": "missing", "폐기": "retired"}

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
    """Each row of Appendix A as a dict. Column order: ID | Value (or Rule) | Source | Code location | State | Note.
    'status' is the state cell in its English form, whichever form the document has."""
    rows, lines = [], open(path, encoding="utf-8").read().split("\n")
    in_appendix = False
    heads = APPENDIX if CFG["appendix_heading"] in APPENDIX else (CFG["appendix_heading"],)
    for i, line in enumerate(lines):
        if line.startswith(heads):
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
                     "status": LEGACY.get(cells[3], cells[3]), "note": cells[4] if len(cells) > 4 else "", "line": i})
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
    """'12' → (12,12); '20~25' → (20,25); '4x' → (4,4); None if there is no number."""
    nums = NUM_RE.findall(value)
    if not nums:
        return None
    if "~" in value and len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    return float(nums[0]), float(nums[0])


def judge(row, hits):
    if not hits:
        return "missing", ""
    rng = gdd_numbers(row["value"]) if row["id"].split(".")[0] in CFG["numeric_prefixes"] else None
    vals = [h["value"] for h in hits if h["value"] is not None]
    if rng and vals:
        lo, hi = rng
        bad = [v for v in vals if not (lo <= v <= hi)]
        if bad:
            return "mismatch", f"GDD={row['value']} code={', '.join(str(int(v) if v.is_integer() else v) for v in bad)}"
        return "synced", ""
    # For items that cannot be compared as numbers (enums · rules · inputs), a marker only confirms the location.
    # Whether the content matches is for a person to see — so it is marked 'synced?' to ask for a judgment.
    return "synced?", "marker found, but the value cannot be compared automatically. Read the code and judge"


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
        counts["retired"] = sum(1 for r in report if r["status"] == "retired")
        counts["missing"] = counts.get("missing", 0) - counts["retired"]
        for k in ("synced", "synced?", "mismatch", "missing", "retired"):
            if counts.get(k):
                print(f"| {k} | {counts[k]} |")
        print()
        for label, pred in (("## mismatch — needs a human decision", lambda r: r["new_status"] == "mismatch"),
                            ("## synced? — read the code and check", lambda r: r["new_status"] == "synced?"),
                            ("## synced", lambda r: r["new_status"] == "synced")):
            sel = [r for r in report if pred(r)]
            if not sel:
                continue
            print(label + "\n\n| ID | GDD | Code location | Note |\n|---|---|---|---|")
            for r in sel:
                print(f"| {r['id']} | {r['value']} | {location_str(r['hits'])} | {r['detail']} |")
            print()
        # A retired item is naturally absent from code — mixed into the missing list it becomes noise to read past every time
        missing = [r["id"] for r in report if r["new_status"] == "missing" and r["status"] != "retired"]
        if missing:
            print(f"## missing ({len(missing)})\n\n" + ", ".join(missing) + "\n")
        if orphans:
            print("## Orphan markers — IDs in code but not in the table\n")
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
            # 'retired' is a person's note that "this item is gone now". Having no marker in code is natural, so
            # turning it back to 'missing' automatically would erase the mark every time.
            if r["status"] == "retired":
                continue
            loc = location_str(r["hits"]) or "—"
            st = r["new_status"].replace("synced?", "synced")  # the table keeps only three states
            if r["new_status"] == "synced?" and r["status"] == "mismatch":
                st = "mismatch"  # a mismatch written by a person is not cleared automatically
            line = lines[r["line"]]
            cells = line.split("|")
            # cells[0] is an empty string, cells[1]=ID, [2]=Value, [3]=Source, [4]=Code location, [5]=State
            # A row that already says the same thing in the old words is left as it is; a row that changes is written in English
            if cells[4].strip() != loc or r["status"] != st:
                cells[4], cells[5] = f" {loc} ", f" {st} "
                lines[r["line"]] = "|".join(cells)
                changed += 1
        if changed:
            open(gdd, "w", encoding="utf-8").write("\n".join(lines))
        print(f"[write] GDD table updated: {changed} rows", file=sys.stderr)


if __name__ == "__main__":
    main()
