#!/usr/bin/env python3
"""GDD 동기화 표(GDD 부록 A)와 코드의 `GDD: <ID>` 표식을 대조한다.

사용법:
  python3 sync_report.py                 # 보고서 출력 (markdown)
  python3 sync_report.py --json          # JSON 출력
  python3 sync_report.py --write         # GDD 표의 '코드 위치'와 '상태' 열을 갱신 (값 열은 건드리지 않는다)
  python3 sync_report.py --only BAL.CYCLE.ACTIVE_SEC   # 특정 ID만

왜 스크립트인가: 항목이 수십 개가 되면 손으로 대조할 때마다 빠뜨린다. 스크립트가 "어디에 무엇이 있는지"를 찾고,
"어느 쪽이 맞는지"는 사람이(또는 Claude 가) 판단한다. 그래서 --write 는 위치와 상태만 쓰고 값은 절대 쓰지 않는다.

엔진마다 다른 것(코드 확장자 · 건너뛸 폴더 · 심볼을 뽑는 정규식)은 프로젝트 루트의 kit.config.json 의 "gdd-sync" 에 있다.
표식은 주석 기호를 가리지 않는다 — `# GDD: X` · `-- GDD: X` · `// GDD: X` 모두 `GDD: X` 로 찾는다.
"""
import argparse, json, os, re, sys

CONFIG_NAME = "kit.config.json"
SECTION = "gdd-sync"
DEFAULTS = {
    "gdd": "docs/GDD.md",
    "appendix_heading": "## 부록 A",
    "code_ext": [],
    "skip_dirs": [".git", ".claude", "docs", "build"],
    # 표식 앞쪽에서 심볼 이름을 뽑는 정규식. 그룹 1 이 이름이다
    "symbol": r"(?:local\s+function|const|var|local|function|func|enum|class)\s+([A-Za-z_][A-Za-z0-9_.:]*)",
    # 값이 숫자여서 자동으로 비교할 수 있는 분류
    "numeric_prefixes": ["BAL", "HUD"],
}

ROW_RE = re.compile(r"^\|\s*([A-Z]+(?:\.[A-Z0-9_]+)+)\s*\|(.*)$")
MARK_RE = re.compile(r"GDD:\s*([A-Z]+(?:\.[A-Z0-9_]+)+)")
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

ROOT = ""
CFG = dict(DEFAULTS)


def find_root(start):
    """kit.config.json 이 있는 폴더를 지금 폴더에서 위로 올라가며 찾는다. 도구는 플러그인 안에 있고 게임은 밖에 있다."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            sys.exit(f"{CONFIG_NAME} 을 찾지 못했다 — 게임 저장소 안에서 돌리고 있는가, /gamedev-kit:init 을 했는가")
        d = up


def load_config(root):
    cfg = dict(DEFAULTS)
    path = os.path.join(root, CONFIG_NAME)
    if os.path.exists(path):
        section = json.load(open(path, encoding="utf-8")).get(SECTION, {})
        cfg.update({k: v for k, v in section.items() if k in DEFAULTS})
    if not cfg["code_ext"]:
        sys.exit(f"{CONFIG_NAME} 의 {SECTION}.code_ext 가 비어 있다 — /gamedev-kit:init 으로 엔진 설정을 깐다")
    return cfg


def parse_table(path):
    """부록 A 의 각 행을 dict 로. 열 순서: ID | 값(또는 규칙) | 출처 | 코드 위치 | 상태 | 비고"""
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
    """코드 전체에서 GDD: <ID> 표식을 찾는다. 같은 줄의 값도 뽑아 둔다."""
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
    """표식 앞쪽에서 심볼 이름을 뽑는다. 표식 뒤는 보지 않는다 — 'GDD:' 자체가 심볼로 잡히는 것을 막는다."""
    before = line.split("GDD:")[0]
    m = re.search(CFG["symbol"], before)
    if m:
        return m.group(1)
    m = re.search(r'"?([A-Za-z_][A-Za-z0-9_]*)"?\s*[:=]', before)
    return m.group(1) if m else ""


def extract_value(line):
    """`= 12`, `: 12`, `= 12.0,` 처럼 표식 앞쪽에 있는 숫자 하나. 없으면 None. `8f` 같은 C# 접미사는 떼고 읽는다."""
    before = line.split("GDD:")[0]
    m = re.search(r"[:=]\s*(-?\d+(?:\.\d+)?)[fFdD]?\s*[,;]?\s*(?:#|//|--)?\s*$", before)
    return float(m.group(1)) if m else None


def gdd_numbers(value):
    """'12' → (12,12); '20~25' → (20,25); '4배' → (4,4); 숫자 없으면 None."""
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
            return "불일치", f"GDD={row['value']} 코드={', '.join(str(int(v) if v.is_integer() else v) for v in bad)}"
        return "동기", ""
    # 숫자 비교가 불가능한 항목(열거·규칙·입력)은 표식이 있으면 위치만 확인된 것이다.
    # 내용이 같은지는 사람이 본다 — 그래서 '동기?' 로 표시해 판단을 요구한다.
    return "동기?", "표식은 있으나 값 자동 비교 불가. 코드를 읽고 판단"


def location_str(hits):
    return ", ".join(f"{h['file']}:{h['symbol'] or h['line']}" for h in hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--root", help="프로젝트 루트 (기본: kit.config.json 이 있는 곳). 테스트용")
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
        print("# GDD 동기화 보고서\n")
        print("| 상태 | 수 |\n|---|---|")
        counts["폐기"] = sum(1 for r in report if r["status"] == "폐기")
        counts["미구현"] = counts.get("미구현", 0) - counts["폐기"]
        for k in ("동기", "동기?", "불일치", "미구현", "폐기"):
            if counts.get(k):
                print(f"| {k} | {counts[k]} |")
        print()
        for label, pred in (("## 불일치 — 사람 판단 필요", lambda r: r["new_status"] == "불일치"),
                            ("## 동기? — 코드를 읽고 확인", lambda r: r["new_status"] == "동기?"),
                            ("## 동기", lambda r: r["new_status"] == "동기")):
            sel = [r for r in report if pred(r)]
            if not sel:
                continue
            print(label + "\n\n| ID | GDD | 코드 위치 | 비고 |\n|---|---|---|---|")
            for r in sel:
                print(f"| {r['id']} | {r['value']} | {location_str(r['hits'])} | {r['detail']} |")
            print()
        # 폐기는 코드에 없는 게 당연하다 — 미구현 목록에 섞이면 매번 읽고 넘겨야 하는 노이즈가 된다
        missing = [r["id"] for r in report if r["new_status"] == "미구현" and r["status"] != "폐기"]
        if missing:
            print(f"## 미구현 ({len(missing)})\n\n" + ", ".join(missing) + "\n")
        if orphans:
            print("## 고아 표식 — 코드에는 있는데 표에 없는 ID\n")
            for k in orphans:
                print(f"- {k}: " + location_str(found[k]))
            print()
        if stale:
            print("## 표의 코드 위치가 더 이상 안 맞는 항목\n")
            for r in stale:
                print(f"- {r['id']}: 표에는 `{r['location']}` 인데 표식을 못 찾음")
            print()

    if a.write:
        changed = 0
        for r in report:
            # 폐기는 사람이 "이 항목은 이제 없다" 고 적어 둔 것이다. 코드에 표식이 없는 건 당연하므로
            # 자동으로 미구현으로 되돌리면 폐기 표시가 매번 사라진다.
            if r["status"] == "폐기":
                continue
            loc = location_str(r["hits"]) or "—"
            st = r["new_status"].replace("동기?", "동기")  # 표에는 세 상태만 둔다
            if r["new_status"] == "동기?" and r["status"] == "불일치":
                st = "불일치"  # 사람이 불일치로 적어 둔 것은 자동으로 풀지 않는다
            line = lines[r["line"]]
            cells = line.split("|")
            # cells[0] 은 빈 문자열, cells[1]=ID, [2]=값, [3]=출처, [4]=코드 위치, [5]=상태
            if cells[4].strip() != loc or cells[5].strip() != st:
                cells[4], cells[5] = f" {loc} ", f" {st} "
                lines[r["line"]] = "|".join(cells)
                changed += 1
        if changed:
            open(gdd, "w", encoding="utf-8").write("\n".join(lines))
        print(f"[write] GDD 표 갱신: {changed}행", file=sys.stderr)


if __name__ == "__main__":
    main()
