#!/usr/bin/env python3
"""현황판 — GDD 동기화 표 · 에셋 기록 · 사이클 · 플레이테스트 문서를 읽어 HTML 로 그린다. 모델이 그리지 않는다.

  python3 board.py              <out>(기본 docs/board/index.html)과 그 곁의 쪽들을 다시 쓰고 경로와 한 줄 요약을 적는다
  python3 board.py --if-stale   판이 이미 있고 원천이 더 새로울 때만 다시 쓴다. 아무것도 적지 않고 늘 0 으로 끝난다 (훅이 부른다)

index.html 은 항해도 — 플레이 순서의 단계마다 카드 하나, 기능 · 아트 · 사운드 · 검증이 얼마나 됐나. stage-N.html 은 단계 하나의 속.
상태는 적힌 그대로다 (여기서 코드를 뒤지지 않는다).

읽기만 한다 — 쓰는 것은 <out> 의 폴더 안뿐이다. 설정은 프로젝트 루트 kit.config.json 의 "board" (없어도 된다).
"""
import datetime
import fnmatch
import html
import json
import os
import re
import sys
import urllib.parse

CONFIG_NAME = "kit.config.json"
SECTION = "board"
DEFAULTS = {
    "out": "docs/board/index.html",
    "gdd": "docs/GDD.md",
    "appendix_heading": "## 부록 A",
    "cycles": "docs/cycle",
    "reload_sec": 30,   # 열어 둔 판이 스스로 다시 읽는 간격. 0 이면 안 한다
    "playtests": "docs/playtest",
    "gen": "assets/_gen",          # 에셋 기록 (asset 스킬이 남긴다)
    "assets": "assets",
    "notes": "docs/board-notes.md",  # 사용자가 해 보고 적는 것: `- 단계 | 칸 | 문제 | 글`
    "open_heading": "미정",         # GDD 에서 "아직 못 정한 것" 을 적는 절의 제목에 든 말
    "common": "미분류",             # 어느 단계에도 안 드는 것이 모이는 곳 — 완성 % 에는 들지 않는다
    "ignore": [],                  # 세지 않을 에셋 이름 (glob) — 계획만 되고 버린 것
    "flow": [],                    # 플레이 순서의 단계들. 비면 GDD 절마다 하나
}
STATES = ["동기", "불일치", "미구현", "폐기"]
ROW_RE = re.compile(r"^\|\s*([A-Z]+(?:\.[A-Z0-9_]+)+)\s*\|(.*)$")
ID_RE = re.compile(r"[A-Z]+(?:\.[A-Z0-9_]+)+")
TASK_RE = re.compile(r"^### \[(.)\] (T\d+)\.(.*)$", re.M)
DECISION_RE = re.compile(r"^- \[(.)\] (D\d+)\.(.*)$", re.M)

ROOT = ""
CFG = dict(DEFAULTS)
e = html.escape


def find_root(start):
    """kit.config.json 이 있는 폴더를 지금 폴더에서 위로 올라가며 찾는다. 없으면 None."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def read(path):
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def cycle_docs():
    d = os.path.join(ROOT, CFG["cycles"])
    return sorted(os.path.join(d, n) for n in os.listdir(d) if re.match(r"\d+-.*\.md$", n)) if os.path.isdir(d) else []


# ── 읽기 ──────────────────────────────────────────────────────────────

def gdd():
    """(게임 이름, 절 번호 → 제목, 부록 A 의 행들)."""
    text = read(os.path.join(ROOT, CFG["gdd"]))
    name = re.search(r"^# (.+)$", text, re.M)
    titles = {m.group(1): m.group(2).strip() for m in re.finditer(r"^#{2,4} (\d+(?:\.\d+)*)\.? +(.+)$", text, re.M)}
    rows, inside = [], False
    for line in text.split("\n"):
        inside = inside or line.startswith(CFG["appendix_heading"])
        m = ROW_RE.match(line) if inside else None
        cells = [c.strip() for c in m.group(2).split("|")] if m else []
        if len(cells) < 5:
            continue
        src = re.search(r"\d+(?:\.\d+)*", cells[1])
        state = cells[3] if cells[3] in STATES else "미구현"
        rows.append({"id": m.group(1), "value": cells[0], "src": src.group(0) if src else "", "where": cells[2],
                     "state": state, "note": cells[4]})
    return (name.group(1).split("—")[0].strip() if name else os.path.basename(ROOT)), titles, rows


def section(text, title):
    m = re.search(rf"^## {re.escape(title)}[ \t]*$", text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end():m.end() + nxt.start() if nxt else len(text)]


def decision(mark, num, rest):
    """`질문 — ① … ② … · 권함: ① (기획) → 사용자의 답 (날짜)` 를 가른다."""
    ask, _, answer = rest.strip().partition(" → ")
    date = re.search(r"\s*\((\d{4}-\d\d-\d\d)\)\s*$", answer)
    who = re.search(r"\s*\(([^()]{1,8})\)\s*$", ask)
    ask = ask[:who.start()] if who else ask
    ask, _, pick = ask.partition(" · 권함:")
    cut = re.search(r" — (?=①)", ask) or re.search(r" — ", ask)  # 제목 안의 줄표가 아니라 선택지 앞의 것
    title, options = (ask[:cut.start()], ask[cut.end():]) if cut else (ask, "")
    pick = re.sub(r"\s*\([^()]*\)\s*$", "", pick)
    return {"num": num, "done": mark == "x", "proxy": mark == "~", "title": title.strip(), "options": options.strip(), "pick": pick.strip(),
            "who": who.group(1) if who else "", "answer": (answer[:date.start()] if date else answer).strip(),
            "date": date.group(1) if date else ""}


def cycle(path):
    text = read(path)
    head = re.search(r"^# 사이클 (\S+) — (.+)$", text, re.M)
    stage = re.search(r"단계: *(\S+)", text)
    start = re.search(r"시작: *(\d{4}-\d\d-\d\d)", text)
    waves = {}
    for line in section(text, "순서").split("\n"):
        m = re.match(r"- *(\d+) *차[^:]*:(.*)", line.strip())  # `1차 (끝):` 도
        for t in re.findall(r"T\d+", m.group(2).split("—")[0]) if m else []:
            waves[t] = int(m.group(1))
    tasks, hits = [], list(TASK_RE.finditer(text))
    for m in hits:
        nxt = re.search(r"^##+ ", text[m.end():], re.M)
        block = text[m.end():m.end() + nxt.start() if nxt else len(text)]
        line = lambda key: (re.search(rf"^- \*\*{key}\*\*:(.*)$", block, re.M) or [None, ""])[1].strip()
        tasks.append({"num": m.group(2), "mark": m.group(1), "title": m.group(3).strip(), "wave": waves.get(m.group(2), 0),
                      "ids": ID_RE.findall(line("GDD")), "blocked": line("막힘"), "did": line("한 것"),
                      "all_ids": ID_RE.findall(block), "block": block})
    num = head.group(1) if head else os.path.basename(path).split("-")[0]
    needs = []
    nm = re.search(r"^### 필요한 에셋[ \t]*$", text, re.M)
    if nm:
        end = re.search(r"^##+ ", text[nm.end():], re.M)
        for row in text[nm.end():nm.end() + end.start() if end else len(text)].split("\n"):
            cells = [c.strip() for c in row.strip().strip("|").split("|")] if row.startswith("|") else []
            name = cells[0].split(" — ")[0].strip("` ") if cells else ""
            if len(cells) >= 4 and re.fullmatch(r"[a-z][a-z0-9_]*", name):
                needs.append({"name": name, "what": cells[0].partition(" — ")[2], "kind": cells[1], "have": cells[3]})
    return {"needs": needs, "file": os.path.basename(path), "num": num, "name": head.group(2).strip() if head else os.path.basename(path)[:-3],
            "stage": stage.group(1) if stage else "?", "start": start.group(1) if start else "",
            "goal": " ".join(section(text, "목표").split()),
            "decisions": [decision(*m.groups()) for m in DECISION_RE.finditer(section(text, "결정"))], "tasks": tasks}


# ── 항해도 — 플레이 순서대로, 한 화면 ─────────────────────────────────
#
# 첫 화면(index)은 단계 카드만. 카드를 누르면 그 단계의 쪽(stage-N.html)으로 간다.
# 단계는 kit.config.json 의 board.flow 가 정한다 (없으면 GDD 절마다 하나). 상태는 전부 읽어서 뽑는다:
#   기능   — GDD 부록 A 의 행 (동기 · 미구현 · 불일치)
#   아트 · 사운드 — 에셋 기록(assets/_gen)과 사이클 문서의 "필요한 에셋" 표 (없음 · 임시)
#   검증   — 그 단계를 건드린 사이클이 플레이 단계를 지났는가, 플레이테스트 문서의 작업, 사용자가 적은 것(board-notes)

LANES = ["기능", "아트", "사운드", "검증"]
WEIGHT = {"done": 1.0, "temp": 0.5, "none": 0.0, "bad": 0.0}
WORD = {"done": "됨", "temp": "임시", "none": "안 만듦", "bad": "문제"}
ORDER = ["bad", "none", "temp", "done"]
NOTE_WORD = {"문제": "bad", "임시": "temp", "됨": "done", "없음": "none", "안 만듦": "none"}
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
SOUND_EXT = (".mp3", ".ogg", ".wav")
MODEL_EXT = (".glb", ".gltf", ".fbx", ".obj")
OUTDIR = ""


def playtest_docs():
    d = os.path.join(ROOT, CFG["playtests"])
    return sorted(os.path.join(d, n) for n in os.listdir(d) if n.endswith(".md")) if os.path.isdir(d) else []


def rel(path):
    """판이 놓인 폴더에서 본 길 (그림 · 소리를 복사하지 않고 가리킨다)."""
    return urllib.parse.quote(os.path.relpath(path, OUTDIR).replace(os.sep, "/")) if path else ""


def item(st, title, sub="", note="", img="", audio="", tags=(), code=""):
    return {"st": st, "title": title, "sub": sub, "note": note, "img": img, "audio": audio, "tags": list(tags), "code": code}


def make_stages(titles, rows):
    flow = CFG["flow"]
    if not flow:
        srcs = sorted({r["src"] for r in rows if r["src"]}, key=lambda s: [int(x) for x in s.split(".")])
        flow = [{"name": titles.get(s, s), "sections": [s]} for s in srcs]
    blank = {"about": "", "sections": [], "ids": [], "assets": [], "words": [], "image": "", "loop": False}
    out = [dict(blank, **f, common=False) for f in flow] + [dict(blank, name=CFG["common"], common=True)]
    for i, s in enumerate(out):
        s.update(i=i, lanes={lane: [] for lane in LANES}, open=[], work=[])
    return out


def place_row(st, r):
    for s in st:
        if any(fnmatch.fnmatchcase(r["id"], g) for g in s["ids"]):
            return s
    best, n = st[-1], -1
    for s in st:
        for sec in map(str, s["sections"]):
            if (r["src"] == sec or r["src"].startswith(sec + ".")) and len(sec) > n:
                best, n = s, len(sec)
    return best


def place_words(st, text):
    hits = [(sum(text.count(w) for w in s["words"]), -s["i"], s) for s in st]
    top = max(hits, key=lambda h: h[:2]) if hits else (0,)
    return top[2] if top[0] else None


def place_ids(st, where, ids):
    n = {}
    for i in ids:
        if i in where:
            n[where[i]] = n.get(where[i], 0) + 1
    return st[max(n, key=lambda k: (n[k], -k))] if n else None


def load_json(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def asset_items(st, where, cycles, tasks):
    adir, gdir = os.path.join(ROOT, CFG["assets"]), os.path.abspath(os.path.join(ROOT, CFG["gen"]))
    files = {}
    for base, _dirs, names in os.walk(adir):
        if os.path.abspath(base).startswith(gdir):
            continue
        for n in sorted(names):
            if not n.endswith(".import"):
                files.setdefault(n.split(".")[0], os.path.join(base, n))
    picture = lambda p: p if p and p.lower().endswith(IMG_EXT) else ""
    sound = lambda p: p if p and p.lower().endswith(SOUND_EXT) else ""
    found = {}
    for name in sorted(os.listdir(gdir)) if os.path.isdir(gdir) else []:
        for fn, lane in (("asset.json", "아트"), ("sound.json", "사운드")):
            rec = load_json(os.path.join(gdir, name, fn))
            if not isinstance(rec, dict):
                continue
            out = os.path.join(ROOT, rec["out"]) if rec.get("out") else ""
            out = out if out and os.path.exists(out) else files.get(name, "")
            if not out:  # 기록만 있고 게임에 안 들어간 것 (버린 시도) 은 세지 않는다
                continue
            front = os.path.join(gdir, name, "front.png")
            found[name] = dict(item("done", name, " · ".join(x for x in (rec.get("kind") or ("모델" if lane == "아트" else ""),
                                                                         rec.get("made") or rec.get("created") or "") if x),
                                    img=front if os.path.exists(front) else picture(out), audio=out if lane == "사운드" else ""), lane=lane)
    made = set(found)
    for c in cycles:
        for n in c["needs"]:
            lane = "사운드" if re.search(r"sound|music|소리|음악|효과음", n["kind"], re.I) else "아트"
            it = found.get(n["name"]) or dict(item("none", n["name"], n["kind"], img=picture(files.get(n["name"], ""))), lane=lane)
            have = n["have"].strip()
            cited = re.findall(r"`([^`]+\.[A-Za-z0-9]+)`", have)  # 있는가 칸에 적힌 파일 — 지금도 있어야 됨이다
            there = (n["name"] in made or n["name"] in files or (any(os.path.exists(os.path.join(ROOT, c)) for c in cited) if cited
                                                                 else not (have.startswith("없음") or have in ("", "—"))))
            it["st"] = "temp" if "임시" in have else "done" if there else "none"
            it["note"] = n["what"] + (f" — {have}" if it["st"] == "temp" else " — 적힌 파일이 없다" if cited and not there else "")
            it["tags"] = [f'사이클 {c["num"]}']
            it["audio"] = it["audio"] or sound(files.get(n["name"], ""))
            found[n["name"]] = it
    for name, path in files.items():  # 기록 없이 게임에 든 소리 · 모델도 센다 (손으로 넣은 것)
        if name not in found and path.lower().endswith(SOUND_EXT + MODEL_EXT):
            found[name] = dict(item("done", name, "기록 없음", audio=sound(path)), lane="사운드" if sound(path) else "아트")
    for name, it in found.items():
        if any(fnmatch.fnmatchcase(name, g) for g in CFG["ignore"]):
            continue
        s = next((s for s in st if any(fnmatch.fnmatchcase(name, g) for g in s["assets"])), None)
        if not s:
            pat = re.compile(rf"(?<![a-z0-9_]){re.escape(name)}(?![a-z0-9_])")
            s = (place_ids(st, where, [i for t in tasks if pat.search(t["block"]) for i in t["all_ids"]])
                 or place_words(st, name + " " + it["note"]) or st[-1])
        s["lanes"][it.pop("lane")].append(it)


def check_items(st, where, cycles, playtests):
    for c in cycles:
        state = "done" if re.match(r"회고|배포", c["stage"]) else "temp" if c["stage"].startswith("플레이") else "none"
        said = {"done": "해 봤다", "temp": "해 볼 차례", "none": f'{c["stage"]} 단계'}[state]
        hit = {}
        for t in c["tasks"]:
            for i in {where[x] for x in t["ids"] if x in where}:
                hit.setdefault(i, []).append(t)
        for i, ts in hit.items():
            st[i]["lanes"]["검증"].append(item(state, f'사이클 {c["num"]} — {c["name"]}', said))
            st[i]["work"].append((c, ts))
    for p in playtests:
        date = re.match(r"\d{4}-\d\d-\d\d", p["file"])
        for t in p["tasks"]:
            s = place_ids(st, where, t["all_ids"]) or place_words(st, t["title"]) or st[-1]
            s["lanes"]["검증"].append(item("done" if t["mark"] == "x" else "bad", t["title"],
                                         f'플레이테스트 {date.group(0) if date else ""} · {"고쳤다" if t["mark"] == "x" else "아직"}'))
    for line in read(os.path.join(ROOT, CFG["notes"])).split("\n"):
        cells = [c.strip() for c in line.lstrip("-* ").split("|")] if line.strip().startswith(("-", "*")) else []
        if len(cells) < 4:
            continue
        s = next((s for s in st if cells[0] and cells[0] in s["name"]), st[-1])
        s["lanes"][cells[1] if cells[1] in LANES else "검증"].append(item(NOTE_WORD.get(cells[2], "bad"), " | ".join(cells[3:]), "사용자가 적었다"))


def open_questions(st, cycles):
    """GDD 의 '미정' 절에서 줄이 그어지지 않은 것과, 답이 없는 결정."""
    text = read(os.path.join(ROOT, CFG["gdd"]))
    m = re.search(rf"^## .*{re.escape(CFG['open_heading'])}.*$", text, re.M)
    out = []
    if m:
        nxt = re.search(r"^(## |---)", text[m.end():], re.M)
        for b in re.findall(r"^- (.+)$", text[m.end():m.end() + nxt.start() if nxt else len(text)], re.M):
            if b.startswith("~~"):
                continue
            t = re.match(r"\*\*(.+?)\*\*:?\s*(.*)", b) or re.match(r"(.+?)(?: — |: | \(|\. )(.*)", b)  # 굵은 제목이 없으면 첫 마디
            out.append({"title": (t.group(1) if t else b).replace("**", ""), "text": (t.group(2) if t else "").replace("**", ""), "from": "GDD"})
    for c in cycles:
        out += [{"title": f'{d["num"]} {d["title"]}', "text": "대신 정했다 — 확인을 기다린다" if d["proxy"] else "답을 기다린다", "from": f'사이클 {c["num"]}'} for d in c["decisions"] if not d["done"]]
    for q in out:
        s = place_words(st, q["title"] + " " + q["text"]) or st[-1]
        q["stage"] = s["i"]
        s["open"].append(q)
    return out


def score(items):
    return sum(WEIGHT[i["st"]] for i in items) / len(items) if items else None


def stage_pct(s):
    v = [x for x in (score(s["lanes"][lane]) for lane in LANES) if x is not None]
    return round(sum(v) * 100 / len(v)) if v else None


def tally(items):
    return {k: sum(1 for i in items if i["st"] == k) for k in ORDER}


def meter(items):
    if not items:
        return '<div class="seg empty"></div>'
    c = tally(items)
    return '<div class="seg">' + "".join(f'<i class="s-{k}" style="flex:{c[k]}"></i>' for k in ("done", "temp", "none", "bad") if c[k]) + "</div>"


def ring(p, cls=""):
    return f'<div class="ring {cls}" style="--p:{p or 0}"><b>{"—" if p is None else p}</b></div>'


def hero_of(s):
    if s["image"]:
        return rel(os.path.join(ROOT, s["image"]))
    return next((rel(i["img"]) for i in s["lanes"]["아트"] if i["img"]), "")


def stage_label(s, lead=""):
    return " · ".join(x for x in ("%s%02d" % (lead, s["i"] + 1), e(sections_label(s))) if x)


def sections_label(s):
    return "GDD " + " · ".join(map(str, s["sections"])) if s["sections"] else ""


CHART_CSS = """
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css");
@property --p{syntax:'<number>';inherits:true;initial-value:0}
:root{--bg:#08080C;--bg2:#101017;--card:#14141C;--card2:#1B1B26;--line:#262632;--line2:#35354A;--gold:#E6BD3C;--gold2:#FFE08A;--sea:#2FD6C8;--red:#E10600;--red2:#FF4A3D;
--tx:#F0F1F5;--tx2:#A9AFBA;--tx3:#6E7480;--mono:"D2Coding",ui-monospace,"SFMono-Regular",Menlo,Consolas,monospace}
*{box-sizing:border-box}html,body{min-height:100%}
body{margin:0;color:var(--tx);font:14px/1.5 "Pretendard Variable",Pretendard,-apple-system,"Apple SD Gothic Neo",system-ui,sans-serif;
background:radial-gradient(900px 500px at 12% -10%,rgba(230,189,60,.16),transparent 60%),radial-gradient(900px 600px at 95% 110%,rgba(47,214,200,.13),transparent 60%),
radial-gradient(circle at 1px 1px,#1c1c26 1px,transparent 1.2px) 0 0/16px 16px,var(--bg);background-attachment:fixed}
a{color:inherit;text-decoration:none}ul{list-style:none;margin:0;padding:0}
.lab{font:10px/1.4 var(--mono);letter-spacing:.1em;color:var(--tx3);text-transform:uppercase}
.page{padding:22px 28px 26px;display:flex;flex-direction:column;gap:16px;min-height:100vh}
header{display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap}
h1{margin:2px 0 0;font-size:34px;font-weight:800;letter-spacing:-.03em;display:flex;align-items:center;gap:12px;line-height:1.1}
h1::before{content:"";width:12px;height:12px;background:var(--gold);transform:rotate(45deg);box-shadow:0 0 18px var(--gold)}
h1 span{font-weight:300;color:var(--tx3)}
.sub{color:var(--tx2);font-size:12px;margin-top:4px}
.tiles{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.tile{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line2);padding:7px 14px 8px;min-width:96px;clip-path:polygon(0 0,calc(100% - 10px) 0,100% 10px,100% 100%,0 100%)}
.tile b{display:block;font-size:22px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.15}
.tile.gold{border-color:var(--gold);background:linear-gradient(180deg,rgba(230,189,60,.22),var(--card))}.tile.gold b{color:var(--gold2);text-shadow:0 0 16px rgba(230,189,60,.7)}
.tile.red{border-color:#7a1a14;background:linear-gradient(180deg,rgba(225,6,0,.2),var(--card))}.tile.red b{color:var(--red2)}
.total{display:flex;gap:4px;height:10px}
.total div{background:#1b1b25;position:relative;overflow:hidden}
.total i{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,var(--gold),var(--gold2));box-shadow:0 0 14px var(--gold);animation:grow 1.1s cubic-bezier(.2,.8,.2,1) both}
.total i::after{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 30%,rgba(255,255,255,.75) 50%,transparent 70%);transform:translateX(-120%);animation:sheen 3.2s 1.2s infinite}
@keyframes grow{from{width:0}}@keyframes sheen{to{transform:translateX(120%)}}
.legend{display:flex;gap:16px;font-size:11px;color:var(--tx2);align-items:center;flex-wrap:wrap}
.legend i{display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:-1px}
.s-done{background:var(--gold)}.s-temp{background:repeating-linear-gradient(45deg,var(--gold) 0 2px,rgba(230,189,60,.12) 2px 5px)}.s-none{background:#2b2b3a}.s-bad{background:var(--red);box-shadow:0 0 8px var(--red)}
.asks{display:flex;gap:8px;overflow:hidden}
.ask{flex:1 1 0;min-width:0;border:1px solid #5a1712;border-top:2px solid var(--red);background:linear-gradient(180deg,rgba(225,6,0,.14),rgba(20,10,12,.9));padding:6px 10px;font-size:12px;color:var(--tx2);clip-path:polygon(0 0,calc(100% - 9px) 0,100% 9px,100% 100%,0 100%)}
.ask b{color:var(--tx);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ask span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ask.more{flex:0 0 auto;display:grid;place-items:center;color:var(--red2);font:700 13px var(--mono)}
.flow{--g:30px;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:var(--g);position:relative;flex:1;align-items:stretch;margin-top:8px}
.loop{position:absolute;top:-14px;bottom:-12px;border:1px dashed rgba(47,214,200,.5);border-radius:2px;pointer-events:none;
left:calc((100% + var(--g))/var(--n)*var(--a) - var(--g)/2);width:calc((100% + var(--g))/var(--n)*var(--c))}
.loop span{position:absolute;top:-9px;left:14px;background:var(--bg);padding:0 8px;color:var(--sea)}
.slot{position:relative;display:flex;animation:rise .6s cubic-bezier(.2,.8,.2,1) both;animation-delay:calc(var(--i)*70ms)}
@keyframes rise{from{opacity:0;transform:translateY(18px)}}
.slot:not(:last-child)::after{content:"";position:absolute;right:calc(var(--g)*-1);top:92px;width:var(--g);height:2px;
background:linear-gradient(90deg,var(--gold) 0 40%,transparent 40% 60%,var(--gold) 60%) 0 0/14px 2px;animation:run .7s linear infinite;filter:drop-shadow(0 0 4px var(--gold))}
@keyframes run{to{background-position:14px 0}}
.node{position:relative;flex:1;display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line2);border-left:3px solid var(--gold);
clip-path:polygon(0 0,calc(100% - 16px) 0,100% 16px,100% 100%,0 100%);overflow:hidden;transition:transform .2s,box-shadow .2s,border-color .2s;min-height:330px}
.slot:hover{z-index:2}.slot:hover .node{transform:translateY(-5px);border-color:var(--gold)}
.slot:hover{filter:drop-shadow(0 12px 26px rgba(230,189,60,.28))}
.node.low{border-left-color:var(--tx3)}.node.warn{border-left-color:var(--red)}
.hero{flex:1 1 132px;min-height:132px;background:#0d0d14 center/cover no-repeat;position:relative;transition:transform .5s}
.hero.none{background:repeating-linear-gradient(135deg,#12121a 0 10px,#15151e 10px 20px)}
.slot:hover .hero{transform:scale(1.06)}
.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(8,8,12,.1) 0%,rgba(20,20,28,.55) 60%,var(--card) 100%)}
.ghost{position:absolute;right:8px;top:70px;font:800 92px/1 var(--mono);color:rgba(255,255,255,.07);letter-spacing:-.06em;pointer-events:none}
.ring{--s:58px;width:var(--s);height:var(--s);border-radius:50%;display:grid;place-items:center;position:relative;
background:conic-gradient(var(--gold) calc(var(--p)*1%),#2a2a38 0);animation:spin 1.2s cubic-bezier(.2,.8,.2,1) both;filter:drop-shadow(0 0 8px rgba(230,189,60,.55))}
.ring::before{content:"";position:absolute;inset:5px;border-radius:50%;background:#0c0c12}
.ring b{position:relative;font:800 17px var(--mono);color:var(--gold2)}.ring b::after{content:"%";font-size:9px;color:var(--tx3);margin-left:1px}
.ring.big{--s:112px}.ring.big::before{inset:9px}.ring.big b{font-size:34px}.ring.big b::after{font-size:13px}
@keyframes spin{from{--p:0}}
.node .ring{position:absolute;right:20px;top:14px}
.body{padding:0 14px 14px;margin-top:-34px;position:relative;display:flex;flex-direction:column;gap:8px}
.node h2{margin:0;font-size:20px;font-weight:800;letter-spacing:-.02em;text-shadow:0 2px 12px #000}
.node p{margin:0 0 4px;font-size:12px;color:var(--tx2);min-height:36px}
.lane{display:grid;grid-template-columns:42px 1fr 44px;gap:8px;align-items:center;font:11px var(--mono);color:var(--tx2)}
.lane em{font-style:normal;text-align:right;color:var(--tx3)}
.seg{display:flex;gap:2px;height:8px}.seg i{display:block;min-width:3px}.seg.empty{border:1px dashed var(--line2)}
.chips{display:flex;gap:6px;flex-wrap:wrap;min-height:20px;align-items:center}
.chip{font:10px var(--mono);padding:2px 7px;border:1px solid var(--line2);color:var(--tx2)}
.chip.bad{border-color:var(--red);color:var(--red2)}.chip.go{margin-left:auto;border-color:var(--gold);color:var(--gold2)}
.rest{display:flex;gap:14px;align-items:center;border:1px solid var(--line);background:rgba(16,16,23,.8);padding:8px 14px;font-size:12px;color:var(--tx2)}
.tile.warn b{color:var(--gold)}.rest b{color:var(--tx)}.rest .lane{flex:1;max-width:220px}
footer{display:flex;gap:16px;font:10px var(--mono);color:var(--tx3)}footer a{color:var(--tx2);border-bottom:1px solid var(--line2)}
/* 단계 쪽 */
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.btn{font:11px var(--mono);padding:6px 12px;border:1px solid var(--line2);background:var(--card);color:var(--tx2)}
.btn:hover{border-color:var(--gold);color:var(--tx)}.btn.on{border-color:var(--gold);color:var(--gold2);background:rgba(230,189,60,.12);box-shadow:0 0 14px rgba(230,189,60,.25)}
.tabs{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}
.banner{position:relative;border:1px solid var(--line2);background:var(--card);overflow:hidden;padding:22px 24px;display:flex;gap:22px;align-items:center;
clip-path:polygon(0 0,calc(100% - 22px) 0,100% 22px,100% 100%,0 100%);min-height:170px}
.banner .pic{position:absolute;inset:0 0 0 35%;background:center/cover no-repeat;opacity:.75;animation:drift 22s ease-in-out infinite alternate}
@keyframes drift{from{transform:scale(1.02)}to{transform:scale(1.12) translateX(-2%)}}
.banner::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,var(--card) 30%,rgba(20,20,28,.75) 55%,rgba(20,20,28,.15))}
.banner::after{pointer-events:none}.banner>*{position:relative;z-index:1}.banner .pic{position:absolute;z-index:0;border:0;padding:0}
.banner h1{font-size:40px}.banner .tiles{margin-left:auto}
.cols{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr;gap:14px;align-items:start}
@media(max-width:1100px){.cols{grid-template-columns:1fr 1fr}}
.col{background:rgba(16,16,23,.82);border:1px solid var(--line);padding:12px 14px}
.col>h3{margin:0 0 4px;font-size:15px;display:flex;align-items:baseline;gap:8px}.col>h3 small{margin-left:auto;font:11px var(--mono);color:var(--tx3)}
.col .seg{margin-bottom:12px}
.it{display:flex;gap:9px;align-items:flex-start;padding:7px 0;border-top:1px solid var(--line);font-size:12.5px}
.it>i{flex:none;width:9px;height:9px;margin-top:5px}
.it .t{flex:1;min-width:0}.it .t b{font-weight:600;overflow-wrap:anywhere}.it .t small{display:block;color:var(--tx3);font-size:11px;overflow-wrap:anywhere}
.it code{font:11px var(--mono);color:var(--gold2)}
.it.st-none b{color:var(--tx2)}.it.st-bad b{color:var(--red2)}
.tag{font:10px var(--mono);color:var(--sea);border:1px solid rgba(47,214,200,.45);padding:0 5px;margin-left:5px}
.thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:8px}
.thumb{background:var(--card2);border:1px solid var(--line2);position:relative;clip-path:polygon(0 0,calc(100% - 9px) 0,100% 9px,100% 100%,0 100%)}
.thumb .im{aspect-ratio:1;background:#0d0d14 center/contain no-repeat;display:grid;place-items:center;color:var(--tx3);font:10px var(--mono)}
.thumb:hover .im{background-color:#181824}
.zoom{cursor:zoom-in}button.im{width:100%;border:0;padding:0;display:block}
#box{position:fixed;inset:0;z-index:9;background:rgba(4,4,8,.92);display:none;flex-direction:column;align-items:center;justify-content:center;gap:12px;cursor:zoom-out;backdrop-filter:blur(6px)}
#box.on{display:flex;animation:fade .18s}#box img{max-width:92vw;max-height:84vh;object-fit:contain;filter:drop-shadow(0 0 40px rgba(230,189,60,.25))}
#box span{font:12px var(--mono);color:var(--gold2);letter-spacing:.08em}@keyframes fade{from{opacity:0}}
.thumb span{display:block;padding:4px 7px 5px;font:10.5px var(--mono);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.thumb>i{position:absolute;left:6px;top:6px;width:9px;height:9px}
.thumb.st-none{border-style:dashed}.thumb.st-none .im{opacity:.5}
.play{flex:none;width:26px;height:26px;border:1px solid var(--gold);background:rgba(230,189,60,.1);color:var(--gold2);font-size:10px;cursor:pointer;border-radius:50%}
.play.on{background:var(--gold);color:#000;box-shadow:0 0 14px var(--gold)}
details>summary{cursor:pointer;color:var(--tx3);font:11px var(--mono);padding:8px 0;border-top:1px solid var(--line)}
.under{display:grid;grid-template-columns:1fr 2fr;gap:14px;align-items:start}
.task{display:inline-block;font-size:12px;border:1px solid var(--line2);border-left:3px solid var(--gold);padding:3px 8px;margin:0 6px 6px 0;background:var(--card)}
.task.open{border-left-color:var(--tx3)}.task.blocked{border-left-color:var(--red)}
.col h4{margin:10px 0 6px;font:11px var(--mono);color:var(--tx3)}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""
CHART_JS = """
let a=null,on=null;document.querySelectorAll('.play').forEach(b=>b.onclick=()=>{if(a){a.pause();on.classList.remove('on');on.textContent='▶';if(on===b){a=on=null;return}}
 a=new Audio(b.dataset.src);on=b;b.classList.add('on');b.textContent='■';a.play();a.onended=()=>{b.classList.remove('on');b.textContent='▶';a=on=null}});
const box=document.createElement('div');box.id='box';box.innerHTML='<img alt=""><span></span>';document.body.appendChild(box);
document.querySelectorAll('.zoom').forEach(z=>z.onclick=ev=>{ev.preventDefault();box.firstChild.src=z.dataset.zoom;box.lastChild.textContent=z.dataset.cap||'';box.classList.add('on')});
box.onclick=()=>box.classList.remove('on');addEventListener('keydown',ev=>{if(ev.key==='Escape')box.classList.remove('on')});
const every=RELOAD;if(every)setInterval(()=>{if(!document.hidden&&!a&&!box.classList.contains('on'))location.reload()},every*1000);
"""


def shell(title, body):
    return (f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)}</title><style>{CHART_CSS}</style><div class="page">{body}</div>'
            f'<script>{CHART_JS.replace("RELOAD", str(int(CFG["reload_sec"])))}</script></html>\n')


def lane_rows(s):
    out = []
    for lane in LANES:
        items = s["lanes"][lane]
        done = sum(1 for i in items if i["st"] == "done")
        out.append(f'<div class="lane"><span>{lane}</span>{meter(items)}<em>{f"{done}/{len(items)}" if items else "없음"}</em></div>')
    return "".join(out)


def ask_href(q):
    return "stage-%d.html" % (q["stage"] + 1)


def stray_of(st):
    """어느 단계에도 안 든 것의 수 — 완성 % 에 들지 않으니 따로 보여야 놓치지 않는다. (전부, 그 가운데 에셋)"""
    lanes = st[-1]["lanes"]
    return sum(len(v) for v in lanes.values()), len(lanes["아트"]) + len(lanes["사운드"])


def index_html(name, st, asks, now, stamp):
    flow = [s for s in st if not s["common"]]
    stray, stray_assets = stray_of(st)
    everything = [i for s in st for lane in LANES for i in s["lanes"][lane]]
    c = tally(everything)
    pcts = [p for p in (stage_pct(s) for s in flow) if p is not None]
    total = round(sum(pcts) / len(pcts)) if pcts else 0
    tiles = [("gold", "완성", f"{total}%"), ("warn" if stray else "", f'{CFG["common"]} · % 밖', stray), ("", "지금", f'{now["num"]} · {now["stage"]}' if now else "—"), ("", "임시로 둔 것", c["temp"]),
             ("", "안 만든 것", c["none"]), ("red" if c["bad"] else "", "문제", c["bad"]), ("red" if asks else "", "못 정한 것", len(asks))]
    cards = []
    for s in flow:
        p, items = stage_pct(s), [i for lane in LANES for i in s["lanes"][lane]]
        t, pic = tally(items), hero_of(s)
        chips = "".join(f'<span class="chip{cls}">{label} {n}</span>' for label, n, cls in
                        (("문제", t["bad"], " bad"), ("안 만듦", t["none"], ""), ("임시", t["temp"], ""), ("못 정함", len(s["open"]), " bad")) if n)
        cls = " warn" if t["bad"] else " low" if (p or 0) < 50 else ""
        cards.append(
            f'<div class="slot" style="--i:{s["i"]}"><a class="node{cls}" href="stage-{s["i"] + 1}.html">'
            + (f'<div class="hero" style="background-image:url({pic})"></div>' if pic else '<div class="hero none"></div>')
            + f'<span class="ghost">{s["i"] + 1:02d}</span>{ring(p)}<div class="body"><span class="lab">{stage_label(s)}</span>'
            f'<h2>{e(s["name"])}</h2><p>{e(s["about"])}</p>{lane_rows(s)}<div class="chips">{chips}<span class="chip go">자세히 →</span></div></div></a></div>')
    loops = [s["i"] for s in flow if s["loop"]]
    loop = (f'<div class="loop" style="--a:{loops[0]};--c:{loops[-1] - loops[0] + 1}"><span class="lab">{e(str(CFG.get("loop_label", "반복")))}</span></div>'
            if loops else "")
    shown = asks[:6]
    strip = "".join(f'<a class="ask" href="{ask_href(q)}">'
                    f'<b>{e(q["title"])}</b><span>{e(q["text"]) or "&nbsp;"}</span></a>' for q in shown)
    strip += f'<span class="ask more">+{len(asks) - len(shown)}</span>' if len(asks) > len(shown) else ""
    rest = st[-1]
    rest_html = (f'<a class="rest" href="stage-{rest["i"] + 1}.html"><span class="lab">어느 단계에도 안 든 것 — 완성 % 에 들지 않는다</span>'
                 f'<b>{e(rest["name"])} {stray}</b><span>에셋 {stray_assets}</span>{lane_rows(rest)}'
                 f'<span class="chip go" style="margin-left:auto">자세히 →</span></a>') if any(rest["lanes"].values()) or rest["open"] else ""
    body = (f'<header><div><div class="lab">항해도 · 플레이어가 겪는 순서대로</div><h1>{e(name)} <span>완성까지</span></h1>'
            f'<div class="sub">겪는 것 {len(everything)}가지 — 됨 {c["done"]} · 임시 {c["temp"]} · 안 만듦 {c["none"]} · 문제 {c["bad"]}{f" · 이 가운데 {e(CFG['common'])} {stray} (에셋 {stray_assets}) 은 완성 % 밖" if stray else ""}</div></div>'
            '<div class="tiles">' + "".join(f'<div class="tile {cls}"><span class="lab">{k}</span><b>{e(str(v))}</b></div>' for cls, k, v in tiles) + "</div></header>"
            '<div class="total">' + "".join(f'<div style="flex:1" title="{e(s["name"])}"><i style="width:{stage_pct(s) or 0}%"></i></div>' for s in flow) + "</div>"
            '<div class="legend"><span><i class="s-done"></i>됨</span><span><i class="s-temp"></i>임시 — 돌아가지만 다시 만들 것</span>'
            '<span><i class="s-none"></i>안 만듦</span><span><i class="s-bad"></i>문제 · 못 정함</span></div>'
            + (f'<div><div class="lab" style="color:var(--red2);margin-bottom:5px">못 정한 것 {len(asks)}</div><div class="asks">{strip}</div></div>' if asks else "")
            + f'<div class="flow" style="--n:{len(flow) or 1}">{loop}{"".join(cards)}</div>{rest_html}'
            f'<footer><span>{stamp} 에 그렸다 · 상태는 GDD 표 · 에셋 기록 · 사이클 · 플레이테스트 문서에서 읽은 그대로다</span>'
            '</footer>')
    return shell(f"{name} 항해도", body), total


def it_html(i):
    tags = "".join(f'<span class="tag">{e(t)}</span>' for t in i["tags"])
    play = f'<button class="play" data-src="{rel(i["audio"])}">▶</button>' if i["audio"] else ""
    head = f'<code>{e(i["code"])}</code> ' if i["code"] else ""
    return (f'<li class="it st-{i["st"]}"><i class="s-{i["st"]}" title="{WORD[i["st"]]}"></i>{play}<div class="t">{head}<b>{e(i["title"])}</b>{tags}'
            + (f'<small>{e(" · ".join(x for x in (i["sub"], i["note"]) if x))}</small>' if i["sub"] or i["note"] else "") + "</div></li>")


def col_html(lane, items):
    items = sorted(items, key=lambda i: ORDER.index(i["st"]))
    done = sum(1 for i in items if i["st"] == "done")
    head = f'<h3>{lane}<small>{f"{done}/{len(items)}" if items else "없음"}</small></h3>{meter(items)}'
    if not items:
        return f'<section class="col">{head}<p class="sub">이 단계에서 읽힌 것이 없다.</p></section>'
    if lane == "아트":
        body = '<div class="thumbs">' + "".join(
            f'<div class="thumb st-{i["st"]}" title="{e(i["note"] or i["sub"])}"><i class="s-{i["st"]}"></i>'
            + (f'<button class="im zoom" data-zoom="{rel(i["img"])}" data-cap="{e(i["title"])}" style="background-image:url({rel(i["img"])})"></button>' if i["img"] else f'<div class="im">{WORD[i["st"]]}</div>')
            + f'<span>{e(i["title"])}</span></div>' for i in items) + "</div>"
        notes = [i for i in items if i["st"] != "done"]
        return f'<section class="col">{head}{body}' + (f'<ul style="margin-top:10px">{"".join(map(it_html, notes))}</ul>' if notes else "") + "</section>"
    todo, rest = [i for i in items if i["st"] != "done"], [i for i in items if i["st"] == "done"]
    body = f'<ul>{"".join(map(it_html, todo))}</ul>' if todo else ""
    if rest:
        inner = f'<ul>{"".join(map(it_html, rest))}</ul>'
        body += inner if len(rest) <= 10 and not todo else f'<details{"" if todo or len(rest) > 14 else " open"}><summary>됨 {len(rest)}개 펼치기</summary>{inner}</details>'
    return f'<section class="col">{head}{body}</section>'


def stage_html(name, s, st):
    p, pic = stage_pct(s), hero_of(s)
    tabs = "".join(f'<a class="btn{" on" if x is s else ""}" href="stage-{x["i"] + 1}.html">{x["i"] + 1:02d} {e(x["name"])}</a>'
                   for x in st if not x["common"] or any(x["lanes"].values()) or x["open"])
    tiles = "".join(f'<div class="tile"><span class="lab">{lane}</span><b>{"—" if score(s["lanes"][lane]) is None else str(round(score(s["lanes"][lane]) * 100)) + "%"}</b></div>'
                    for lane in LANES)
    asks = "".join(f'<div class="ask" style="margin-bottom:6px"><b style="white-space:normal">{e(q["title"])}</b>'
                   f'<span style="white-space:normal">{e(q["text"])} <em class="lab">{e(q["from"])}</em></span></div>' for q in s["open"])
    mark = {"x": "", "!": " blocked"}
    work = "".join(f'<h4>사이클 {e(c["num"])} — {e(c["name"])} · {e(c["stage"])}</h4>'
                   + "".join(f'<span class="task{mark.get(t["mark"], " open")}" title="{e(t["did"])}"><b>{t["num"]}</b> {e(t["title"])}</span>' for t in ts)
                   for c, ts in reversed(s["work"]))
    body = (f'<div class="bar"><a class="btn" href="index.html">← 항해도</a><div class="tabs">{tabs}</div></div>'
            f'<div class="banner">' + (f'<button class="pic zoom" data-zoom="{pic}" data-cap="{e(s["name"])}" style="background-image:url({pic})"></button>' if pic else "") + ring(p, "big")
            + f'<div><div class="lab">{stage_label(s, "단계 ")}</div><h1>{e(s["name"])}</h1><div class="sub">{e(s["about"])}</div></div>'
            f'<div class="tiles">{tiles}</div></div>'
            f'<div class="cols">{"".join(col_html(lane, s["lanes"][lane]) for lane in LANES)}</div>'
            '<div class="under">'
            f'<section class="col"><h3 style="color:var(--red2)">못 정한 것<small>{len(s["open"])}</small></h3>{asks or "<p class=sub>없다.</p>"}</section>'
            f'<section class="col"><h3>이 단계를 건드린 작업</h3>{work or "<p class=sub>없다.</p>"}</section></div>')
    return shell(f'{s["name"]} · {name} 항해도', body)


def build(outdir, index_name):
    global OUTDIR
    OUTDIR = outdir
    name, titles, rows = gdd()
    cycles = [cycle(p) for p in cycle_docs()]
    playtests = [cycle(p) for p in playtest_docs()]
    live = [r for r in rows if r["state"] != "폐기"]
    waiting = sum(1 for c in cycles for d in c["decisions"] if not d["done"])
    line = (f'GDD 동기 {sum(1 for r in live if r["state"] == "동기")}/{len(live)} · 불일치 {sum(1 for r in live if r["state"] == "불일치")}'
            f' · 사이클 {len(cycles)}개 · 답 없는 결정 {waiting}')
    st = make_stages(titles, rows)
    touched, where = {}, {}
    for c in cycles:
        for t in c["tasks"]:
            for i in t["ids"]:
                touched.setdefault(i, []).append(f'{c["num"]}·{t["num"]}')
    for r in rows:
        s = place_row(st, r)
        if r["state"] != "폐기":
            where[r["id"]] = s["i"]
            s["lanes"]["기능"].append(item({"동기": "done", "불일치": "bad"}.get(r["state"], "none"), r["value"], r["note"], code=r["id"],
                                         tags=touched.get(r["id"], [])[-3:]))
    asset_items(st, where, cycles, [t for d in cycles + playtests for t in d["tasks"]])
    check_items(st, where, cycles, playtests)
    asks = open_questions(st, cycles)
    stamp = f"{datetime.datetime.now():%Y-%m-%d %H:%M}"
    index, total = index_html(name, st, asks, cycles[-1] if cycles else None, stamp)
    pages = {index_name: index}
    pages.update({f'stage-{s["i"] + 1}.html': stage_html(name, s, st) for s in st})
    stray, stray_assets = stray_of(st)
    return pages, f"{line} · 완성 {total}%" + (f' · {CFG["common"]} {stray} (에셋 {stray_assets} — 완성 % 밖)' if stray else "")


def sources():
    gen = os.path.join(ROOT, CFG["gen"])
    return ([os.path.join(ROOT, CFG["gdd"]), os.path.join(ROOT, CONFIG_NAME), os.path.join(ROOT, CFG["notes"]), gen]
            + cycle_docs() + playtest_docs() + ([os.path.join(gen, n) for n in os.listdir(gen)] if os.path.isdir(gen) else []))


def main():
    global ROOT, CFG
    args = sys.argv[1:]
    root = None
    if "--root" in args:  # 테스트용
        i = args.index("--root")
        root = args[i + 1]
        del args[i:i + 2]
    quiet = args == ["--if-stale"]
    if args and not quiet:
        sys.exit(__doc__)
    try:
        ROOT = os.path.abspath(root) if root else find_root(os.getcwd())
        if not ROOT:
            raise RuntimeError(f"{CONFIG_NAME} 을 찾지 못했다 — 게임 저장소 안에서 돌리고 있는가, /gamedev-kit:init 을 했는가")
        CFG = dict(DEFAULTS, **json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get(SECTION, {}))
        out = os.path.join(ROOT, CFG["out"])
        if quiet and (not os.path.exists(out)
                      or os.path.getmtime(out) >= max(os.path.getmtime(p) for p in sources() if os.path.exists(p))):
            return
        pages, line = build(os.path.dirname(out), os.path.basename(out))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        old = os.path.join(os.path.dirname(out), "log.html")  # 0.12.0 이 쓰던 쪽 — 이제 그리지 않는다
        if os.path.exists(old):
            os.remove(old)
        for fn, page in pages.items():
            with open(os.path.join(os.path.dirname(out), fn), "w", encoding="utf-8") as f:
                f.write(page)
        if not quiet:
            print(f"{os.path.relpath(out, ROOT)} — {line}")
    except Exception as err:  # 훅으로 돌 때는 무슨 일이 있어도 사용자의 턴을 막지 않는다
        if not quiet:
            sys.exit(str(err))


if __name__ == "__main__":
    main()
