#!/usr/bin/env python3
"""보이스(docs/VOICE.md)의 재료와 채점 — 사이클 문서의 결정 줄만 꺼내고, 묻기 전에 적은 예측을 답과 견준다.

  python3 voice.py collect                 사이클마다 목표와 답이 난 결정. 권함과 답이 갈렸는지 표시한다
  python3 voice.py collect new             docs/VOICE.md 의 `갱신:` 날짜부터 답이 난 것만
  python3 voice.py predict D2 ② V3,V5      묻기 전에 예측을 적는다 — 고를 것과 근거 원칙. 답이 난 결정에는 적지 못한다
  python3 voice.py predict D2 -            근거가 될 원칙이 없다 (모름)
  python3 voice.py score                   답이 난 결정의 예측을 채점한다. 답에서 번호를 가릴 수 없는 것은 줄로 내놓는다
  python3 voice.py score 03 D2 hit         가릴 수 없던 것을 손으로 (hit · miss)
  python3 voice.py stats                   적중률 — 전체 · 누가 물은 것 · 원칙별

predict 는 가장 새 사이클 문서(번호가 가장 큰 것)의 결정을 본다. 다른 문서면 `--doc <경로>`.
"""
import datetime
import os
import re
import sys

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "cycle")
VOICE = os.path.join("docs", "VOICE.md")
LOG = os.path.join("docs", "voice-log.md")
LOG_HEAD = """# 보이스 예측 장부

결정을 묻기 전에 보이스(docs/VOICE.md)로 적은 예측과 그 채점 (`voice.py predict` · `score`). 손으로 고치지 않는다.
`[ ]` 채점 전 · `[o]` 맞음 · `[x]` 빗나감 · `[-]` 모름 (근거가 될 원칙이 없어 예측하지 않음)

"""
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
DECISION_RE = re.compile(r"^- \[(.)\] (D\d+)\.(.*)$", re.M)
PARTS_RE = re.compile(r"^(?P<q>.*?)(?: \((?P<who>기획|디자인|계획)\))?(?: → (?P<a>.*?)(?: \((?P<date>\d{4}-\d\d-\d\d)\))?)?$")
LOG_RE = re.compile(r"^- \[(.)\] (\d+) (D\d+) \(([^)]*)\) → (\S+)(?: · (V\d+(?:, V\d+)*))?", re.M)
WORD = {"o": "맞음", "x": "빗나감"}

ROOT = ""


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


def docs():
    d = os.path.join(ROOT, DIR)
    return sorted(os.path.join(d, n) for n in os.listdir(d) if re.match(r"\d+-.*\.md$", n)) if os.path.isdir(d) else []


def read(path):
    return open(path, encoding="utf-8").read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def number(path):
    return re.match(r"\d+", os.path.basename(path)).group(0)


def section(text, title):
    m = re.search(rf"^## {re.escape(title)}[ \t]*$", text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end():m.end() + nxt.start() if nxt else len(text)]


def choice(text):
    """글에서 고른 번호 하나 (①, `2번`). 없거나 둘 이상이면 빈 글 — 사람 말은 번호 없이도 답이다."""
    found = set(re.findall(f"[{CIRCLED}]", text)) | {CIRCLED[int(n) - 1] for n in re.findall(r"(?<!\d)([1-9])번", text)}
    return found.pop() if len(found) == 1 else ""


def decisions(text):
    """결정 번호 → 질문 · 누가 물었나 · 권함 · 답 · 답한 날 · 답에서 가린 번호."""
    out = {}
    for mark, num, rest in DECISION_RE.findall(section(text, "결정")):
        p = PARTS_RE.match(rest.strip()).groupdict()
        rec = re.search(rf"권함: *([{CIRCLED}])", p["q"])
        answered = mark == "x" and p["a"] is not None
        out[num] = {"q": p["q"].strip(), "who": p["who"] or "?", "rec": rec.group(1) if rec else "",
                    "answer": p["a"] if answered else None, "date": p["date"] or "",
                    "chose": choice(p["a"]) if answered else ""}
    return out


def split_tag(d):
    if not d["rec"] or not d["chose"]:
        return "?"
    return "같음" if d["rec"] == d["chose"] else "갈림"


def cmd_collect(only_new):
    since = ""
    if only_new:
        path = os.path.join(ROOT, VOICE)
        m = re.search(r"갱신: *(\d{4}-\d\d-\d\d)", read(path)) if os.path.exists(path) else None
        if not m:
            sys.exit(f"{VOICE} 에 `갱신: <날짜>` 가 없다 — `collect` 로 전부 본다")
        since = m.group(1)
    count = {"갈림": 0, "같음": 0, "?": 0}
    for path in docs():
        text = read(path)
        rows = [(num, d) for num, d in decisions(text).items() if d["answer"] is not None and d["date"] >= since]
        if not rows:
            continue
        title = re.match(r"# *(.*)", text)
        print(f"\n{title.group(1) if title else os.path.basename(path)}")
        print("목표: " + " ".join(section(text, "목표").split()))
        for num, d in rows:
            tag = split_tag(d)
            count[tag] += 1
            print(f"  {number(path)} {num} [{tag}] ({d['who']}) {d['q']} → {d['answer']}" + (f" ({d['date']})" if d["date"] else ""))
    total = sum(count.values())
    if not total:
        return print("답이 난 결정이 없다" + (f" ({since} 부터)" if since else ""))
    print(f"\n결정 {total} · 권함과 갈림 {count['갈림']} · 같음 {count['같음']} · 읽어서 가릴 것 {count['?']}")


def log_text():
    path = os.path.join(ROOT, LOG)
    return read(path) if os.path.exists(path) else LOG_HEAD


def cmd_predict(path, num, pick, cites):
    ds = decisions(read(path))
    if num not in ds:
        sys.exit(f"{num}: 그런 결정이 없다 — " + " · ".join(ds))
    if ds[num]["answer"] is not None:
        sys.exit(f"{num}: 이미 답이 났다 — 예측은 묻기 전에 적는다")
    log = log_text()
    if re.search(rf"^- \[.\] {number(path)} {num} ", log, re.M):
        sys.exit(f"{num}: 이미 예측을 적었다")
    if pick == "-":
        line = f"- [-] {number(path)} {num} ({ds[num]['who']}) → 모름"
    else:
        pick = CIRCLED[int(pick) - 1] if re.fullmatch(r"[1-9]", pick) else pick
        if pick not in CIRCLED or pick not in ds[num]["q"]:
            sys.exit(f"{pick}: 질문에 없는 선택지다 — {ds[num]['q']}")
        voice = os.path.join(ROOT, VOICE)
        known = re.findall(r"^- (V\d+)\.", read(voice), re.M) if os.path.exists(voice) else []
        used = [v for v in cites.split(",") if v]
        bad = [v for v in used if v not in known]
        if not used or bad:
            sys.exit(f"근거 원칙이 {VOICE} 에 없다: {' · '.join(bad) or '(안 적음)'} — 근거가 없으면 `predict {num} -`")
        line = f"- [ ] {number(path)} {num} ({ds[num]['who']}) → {pick} · {', '.join(used)}"
    write(os.path.join(ROOT, LOG), log.rstrip("\n") + f"\n{line} ({datetime.date.today()})\n")
    print(line[2:])


def cmd_score(manual):
    log = log_text()
    by_num = {number(p): p for p in docs()}
    marked, unclear = [], []
    for m in LOG_RE.finditer(log):
        mark, doc, num, _who, pick = m.group(1, 2, 3, 4, 5)
        if mark != " ":
            continue
        d = decisions(read(by_num[doc])).get(num) if doc in by_num else None
        if not d or d["answer"] is None:
            continue
        if manual and manual[:2] == [doc, num]:
            new = "o" if manual[2] == "hit" else "x"
        elif d["chose"]:
            new = "o" if d["chose"] == pick else "x"
        else:
            unclear.append(f"가릴 수 없다: {doc} {num} 예측 {pick} · 답: {d['answer']} — `score {doc} {num} hit|miss`")
            continue
        log = log.replace(m.group(0), m.group(0).replace("- [ ]", f"- [{new}]", 1), 1)
        marked.append(f"{doc} {num}: {WORD[new]} — 예측 {pick}" + (f" ({m.group(6)})" if m.group(6) else "") + f" · 답: {d['answer']}")
    if manual and not any(line.startswith(f"{manual[0]} {manual[1]}:") for line in marked):
        sys.exit(f"{manual[0]} {manual[1]}: 채점할 예측이 없다 (예측이 없거나, 답이 아직 없거나, 이미 채점했다)")
    if marked:
        write(os.path.join(ROOT, LOG), log)
    print("\n".join(marked + unclear) or "채점할 예측이 없다")


def cmd_stats():
    rows = LOG_RE.findall(log_text())
    if not rows:
        return print(f"{LOG} 에 예측이 없다")
    rate = lambda hit, miss: f"{hit}/{hit + miss}" + (f" ({100 * hit // (hit + miss)}%)" if hit + miss else "")
    tally = lambda picked: (sum(1 for r in picked if r[0] == "o"), sum(1 for r in picked if r[0] == "x"))
    marks = [r[0] for r in rows]
    print(f"적중 {rate(*tally(rows))} · 모름 {marks.count('-')} · 채점 전 {marks.count(' ')} · 예측 {len(rows)}")
    for who in dict.fromkeys(r[3] for r in rows):
        mine = [r for r in rows if r[3] == who]
        print(f"  {who}: {rate(*tally(mine))} · 모름 {sum(1 for r in mine if r[0] == '-')}")
    for v in sorted({v for r in rows for v in re.findall(r"V\d+", r[5])}, key=lambda v: int(v[1:])):
        print(f"  {v}: {rate(*tally([r for r in rows if v in re.findall(r'V[0-9]+', r[5])]))}")


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--doc"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    cmd, rest = (args[0] if args else ""), args[1:]
    need = {"collect": (0, 1), "predict": (2, 3), "score": (0, 3), "stats": (0,)}
    if cmd not in need or len(rest) not in need[cmd]:
        sys.exit(__doc__)
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    if cmd == "collect":
        if rest and rest[0] != "new":
            sys.exit(__doc__)
        cmd_collect(bool(rest))
    elif cmd == "predict":
        path = opts.get("--doc") or (docs() or [""])[-1]
        path = path if os.path.isabs(path) else os.path.join(ROOT, path)
        if not os.path.isfile(path):
            sys.exit(f"{DIR}/ 에 사이클 문서가 없다")
        cmd_predict(path, rest[0], rest[1], rest[2] if len(rest) > 2 else "")
    elif cmd == "score":
        if rest and rest[2] not in ("hit", "miss"):
            sys.exit("채점은 hit · miss 다")
        cmd_score(rest)
    else:
        cmd_stats()


if __name__ == "__main__":
    main()
