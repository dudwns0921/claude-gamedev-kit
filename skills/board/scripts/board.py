#!/usr/bin/env python3
"""현황판 — GDD 동기화 표와 사이클 문서를 읽어 HTML 한 장으로 그린다. 모델이 그리지 않는다.

  python3 board.py              <out>(기본 docs/board/index.html)을 다시 쓰고 경로와 한 줄 요약을 적는다
  python3 board.py --if-stale   판이 이미 있고 원천이 더 새로울 때만 다시 쓴다. 아무것도 적지 않고 늘 0 으로 끝난다 (훅이 부른다)

위 절반은 "기획한 것 중 얼마나 됐나" — GDD 부록 A 의 행을 출처 절(4.1 · 4.2 …)마다 묶어 상태(동기 · 불일치 · 미구현 · 폐기)를 센다.
상태는 표에 적힌 그대로다 (gdd-sync 가 맞춘다 — 여기서 코드를 다시 뒤지지 않는다). 행마다 그것을 건드린 사이클의 작업이 붙는다.
아래 절반은 "일이 어떻게 흘렀나" — 사이클마다 단계 · 사용자의 결정(말 그대로) · 차수별 작업.

읽기만 한다 — 쓰는 파일은 <out> 하나다. 설정은 프로젝트 루트 kit.config.json 의 "board" (없어도 된다).
"""
import datetime
import html
import json
import os
import re
import sys

CONFIG_NAME = "kit.config.json"
SECTION = "board"
DEFAULTS = {
    "out": "docs/board/index.html",
    "gdd": "docs/GDD.md",
    "appendix_heading": "## 부록 A",
    "cycles": "docs/cycle",
    "reload_sec": 30,   # 열어 둔 판이 스스로 다시 읽는 간격. 0 이면 안 한다
}
STAGES = ["목표", "기획", "디자인", "계획", "구현", "플레이", "배포", "회고"]
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
    return {"num": num, "done": mark == "x", "title": title.strip(), "options": options.strip(), "pick": pick.strip(),
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
                      "ids": ID_RE.findall(line("GDD")), "blocked": line("막힘"), "did": line("한 것")})
    num = head.group(1) if head else os.path.basename(path).split("-")[0]
    return {"num": num, "name": head.group(2).strip() if head else os.path.basename(path)[:-3],
            "stage": stage.group(1) if stage else "?", "start": start.group(1) if start else "",
            "goal": " ".join(section(text, "목표").split()),
            "decisions": [decision(*m.groups()) for m in DECISION_RE.finditer(section(text, "결정"))], "tasks": tasks}


# ── 그리기 ────────────────────────────────────────────────────────────

def bar(counts):
    total = sum(counts.values()) or 1
    return '<div class="bar">' + "".join(
        f'<i class="s-{s}" style="width:{counts[s] * 100 / total:.2f}%" title="{s} {counts[s]}"></i>'
        for s in STATES if counts.get(s)) + "</div>"


def count(rows):
    return {s: sum(1 for r in rows if r["state"] == s) for s in STATES}


def legend(c):
    return " · ".join(f'<span class="k s-{s}">{s} {c[s]}</span>' for s in STATES if c[s])


def gdd_html(titles, rows, touched):
    groups = {}
    for r in rows:
        groups.setdefault(r["src"], []).append(r)
    order = sorted(groups, key=lambda s: [int(x) for x in s.split(".")] if s else [999])
    out = []
    for src in order:
        rs, c = groups[src], count(groups[src])
        live = len(rs) - c["폐기"]
        lines = []
        for r in rs:
            tags = "".join(f'<a class="tag" href="#c{n}" title="{e(title)}">{e(n)}·{t}</a>' for n, t, title in touched.get(r["id"], []))
            lines.append(f'<li class="row" data-state="{r["state"]}" data-kind="{r["id"].split(".")[0]}">'
                         f'<span class="dot s-{r["state"]}" title="{r["state"]}"></span><code>{e(r["id"])}</code>'
                         f'<b>{e(r["value"])}</b><span class="note">{e(r["note"])}</span>{tags}'
                         + (f'<span class="where">{e(r["where"])}</span>' if r["where"] not in ("", "—") else "") + "</li>")
        name = f"{src} {titles.get(src, '')}".strip() if src else "출처 없음"
        out.append(f'<details class="card" id="g{e(src)}"><summary><h3>{e(name)}</h3>'
                   f'<span class="num">{c["동기"]}<small>/{live}</small></span>{bar(c)}<p>{legend(c)}</p></summary>'
                   f'<ul>{"".join(lines)}</ul></details>')
    return "".join(out)


def cycle_html(c, latest):
    at = next((i for i, s in enumerate(STAGES) if c["stage"].startswith(s)), -1)
    steps = "".join(f'<li class="{"past" if i < at else "now" if i == at else ""}">{s}</li>' for i, s in enumerate(STAGES))
    marks = [t["mark"] for t in c["tasks"]]
    waiting = sum(1 for d in c["decisions"] if not d["done"])
    ds = "".join(
        f'<li class="decision{"" if d["done"] else " open"}"><div class="q"><b>{d["num"]}</b> {e(d["title"])}'
        f'<small>{e(" · ".join(x for x in (d["who"], d["date"]) if x))}</small></div>'
        + (f'<blockquote>{e(d["answer"])}</blockquote>' if d["done"] else '<blockquote class="wait">답을 기다린다</blockquote>')
        + (f'<details><summary>선택지 · 권함 {e(d["pick"])}</summary><p>{e(d["options"])}</p></details>' if d["options"] else "")
        + "</li>" for d in c["decisions"])
    cols = []
    for w in sorted({t["wave"] for t in c["tasks"]}, key=lambda w: w or 999):
        cards = "".join(
            f'<li class="task m-{ {"x": "done", "!": "blocked"}.get(t["mark"], "open")}" title="{e(t["did"] or t["blocked"])}">'
            f'<b>{t["num"]}</b> {e(t["title"])}'
            + (f'<small class="why">막힘: {e(t["blocked"])}</small>' if t["mark"] == "!" and t["blocked"] else "")
            + (f'<small>GDD {len(t["ids"])}</small>' if t["ids"] else "") + "</li>"
            for t in c["tasks"] if t["wave"] == w)
        cols.append(f'<div class="wave"><h4>{f"{w}차" if w else "차수 없음"}</h4><ul>{cards}</ul></div>')
    return (f'<details class="cycle" id="c{e(c["num"])}"{" open" if latest else ""}><summary>'
            f'<h3><span class="n">{e(c["num"])}</span> {e(c["name"])}</h3><ol class="steps">{steps}</ol>'
            f'<p>{e(c["start"])} · 작업 {marks.count("x")}/{len(marks)}'
            + (f' · <span class="k s-불일치">막힘 {marks.count("!")}</span>' if "!" in marks else "")
            + (f' · <span class="k s-불일치">답 없는 결정 {waiting}</span>' if waiting else "") + "</p></summary>"
            + (f'<blockquote class="goal">{e(c["goal"])}</blockquote>' if c["goal"] else "")
            + (f'<h4>결정 — 사용자의 말 그대로</h4><ul class="decisions">{ds}</ul>' if ds else "")
            + (f'<h4>작업</h4><div class="waves">{"".join(cols)}</div>' if cols else "") + "</details>")


CSS = """
:root{--bg:#f6f5f1;--card:#fff;--ink:#1c1b19;--dim:#6b6860;--line:#dedbd2;--ok:#2f8f5b;--bad:#c8402f;--todo:#b9b5aa;--drop:#d9d6cd;--user:#b4530a;--now:#1c1b19}
@media (prefers-color-scheme:dark){:root{--bg:#0e0f11;--card:#17191c;--ink:#ecebe6;--dim:#9a988f;--line:#2a2d32;--ok:#4cc38a;--bad:#f0604d;--todo:#4a4d54;--drop:#2a2d32;--user:#f0a35a;--now:#ecebe6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,"Pretendard","Apple SD Gothic Neo","Noto Sans KR",sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 16px 80px}
header h1{font-size:28px;margin:0 0 2px;letter-spacing:-.02em}header p,summary p,small,.note,.where{color:var(--dim)}
header p{margin:0 0 20px;font-size:13px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}
.stats div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.stats b{display:block;font-size:26px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}.stats span{font-size:12px;color:var(--dim)}
h2{font-size:13px;letter-spacing:.08em;color:var(--dim);margin:36px 0 12px;font-weight:600}
h3{font-size:16px;margin:0}h4{font-size:12px;color:var(--dim);margin:18px 0 8px;font-weight:600}
.bar{display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--drop);margin:8px 0}
.bar i{display:block}.s-동기{--c:var(--ok)}.s-불일치{--c:var(--bad)}.s-미구현{--c:var(--todo)}.s-폐기{--c:var(--drop)}
.bar i,.dot{background:var(--c)}.k{font-size:12px}.k::before{content:"";display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--c);margin-right:5px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 14px}
.chips button{font:inherit;font-size:12px;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:99px;padding:4px 11px;cursor:pointer}
.chips button[aria-pressed=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:10px;align-items:start}
details.card,details.cycle{background:var(--card);border:1px solid var(--line);border-radius:10px}
details.card[open]{grid-column:1/-1}
summary{list-style:none;cursor:pointer;padding:14px 16px;position:relative}summary::-webkit-details-marker{display:none}
summary p{margin:0;font-size:12px}.card .num{position:absolute;right:16px;top:12px;font-size:20px;font-variant-numeric:tabular-nums}.card .num small{font-size:13px}
.card h3{padding-right:70px}
ul,ol{list-style:none;margin:0;padding:0}.card ul{border-top:1px solid var(--line);padding:6px 16px 12px}
.row{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--line);font-size:13px}.row:last-child{border:0}
.row[data-state=폐기] code,.row[data-state=폐기] b{text-decoration:line-through;color:var(--dim)}
.dot{width:8px;height:8px;border-radius:50%;flex:none;align-self:center}
code,.where{font:12px ui-monospace,SFMono-Regular,Menlo,monospace}.note{flex:1 1 260px;min-width:0}.where{flex-basis:100%;padding-left:18px;overflow-wrap:anywhere}
.tag{font-size:11px;color:var(--user);border:1px solid currentColor;border-radius:4px;padding:0 5px;text-decoration:none}
.cycle{margin-bottom:10px}.cycle>summary{display:grid;gap:8px}.cycle>:not(summary){margin-left:16px;margin-right:16px}.cycle>:last-child{margin-bottom:16px}
.n{color:var(--dim);font-variant-numeric:tabular-nums;margin-right:4px}
.steps{display:flex;flex-wrap:wrap;gap:4px}.steps li{font-size:12px;padding:2px 9px;border-radius:99px;border:1px solid var(--line);color:var(--dim)}
.steps .past{background:var(--drop);color:var(--ink);border-color:transparent}.steps .now{background:var(--now);color:var(--bg);border-color:var(--now);font-weight:600}
blockquote{margin:0;padding:8px 12px;border-left:3px solid var(--user);background:color-mix(in srgb,var(--user) 8%,transparent);border-radius:0 6px 6px 0;font-size:14px}
.goal{font-size:14px}.wait{border-color:var(--bad);color:var(--bad);background:color-mix(in srgb,var(--bad) 8%,transparent)}
.decisions{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
.decision{border:1px solid var(--line);border-radius:8px;padding:10px 12px;display:grid;gap:8px;align-content:start}.decision.open{border-color:var(--bad)}
.q{font-size:13px}.q small{display:block;font-size:11px}.decision summary{padding:0;font-size:12px;color:var(--dim)}.decision details p{font-size:12px;color:var(--dim);margin:6px 0 0}
.waves{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px}.wave{flex:0 0 220px}.wave h4{margin-top:0}
.task{border:1px solid var(--line);border-left:3px solid var(--todo);border-radius:6px;padding:7px 10px;margin-bottom:6px;font-size:13px}
.task small{display:block;font-size:11px}.task .why{color:var(--bad)}.m-done{border-left-color:var(--ok)}.m-blocked{border-left-color:var(--bad)}
.hide{display:none!important}
"""
JS = """
const K='board:'+location.pathname, keep=()=>{try{sessionStorage.setItem(K,JSON.stringify([...document.querySelectorAll('details[id][open]')].map(d=>d.id)))}catch(e){}};
try{const o=JSON.parse(sessionStorage.getItem(K)||'null');if(o)document.querySelectorAll('details[id]').forEach(d=>d.open=o.includes(d.id))}catch(e){}
document.addEventListener('toggle',keep,true);
let pick='';document.querySelectorAll('.chips button').forEach(b=>b.onclick=()=>{pick=pick===b.dataset.f?'':b.dataset.f;
 document.querySelectorAll('.chips button').forEach(x=>x.setAttribute('aria-pressed',x.dataset.f===pick));
 document.querySelectorAll('.row').forEach(r=>r.classList.toggle('hide',!!pick&&r.dataset.state!==pick&&r.dataset.kind!==pick));
 document.querySelectorAll('details.card').forEach(c=>{const n=c.querySelectorAll('.row:not(.hide)').length;c.classList.toggle('hide',!n);if(pick)c.open=n>0&&n<40})});
const every=RELOAD;if(every)setInterval(()=>{if(!document.hidden&&!pick){keep();location.reload()}},every*1000);
"""


def build():
    name, titles, rows = gdd()
    cycles = [cycle(p) for p in cycle_docs()]
    touched = {}
    for c in cycles:
        for t in c["tasks"]:
            for i in t["ids"]:
                touched.setdefault(i, []).append((c["num"], t["num"], t["title"]))
    c = count(rows)
    live = len(rows) - c["폐기"]
    now = cycles[-1] if cycles else None
    waiting = sum(1 for cy in cycles for d in cy["decisions"] if not d["done"])
    stats = [(f'{c["동기"] * 100 // live if live else 0}%', f'GDD 항목 {live}개 중 동기 {c["동기"]}'), (c["불일치"], "불일치"), (c["미구현"], "미구현"),
             (f'{now["num"]} · {now["stage"]}' if now else "—", "지금 사이클 · 단계"), (waiting, "답 없는 결정")]
    kinds = sorted({r["id"].split(".")[0] for r in rows})
    chips = "".join(f'<button data-f="{e(f)}" aria-pressed="false">{e(f)}</button>' for f in [s for s in STATES if c[s]] + kinds)
    page = (f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(name)} 현황판</title><style>{CSS}</style><main><header><h1>{e(name)}</h1>'
            f'<p>{datetime.datetime.now():%Y-%m-%d %H:%M} 에 그렸다 · 상태는 GDD 표에 적힌 그대로다 (gdd-sync 가 맞춘다)</p>'
            '<div class="stats">' + "".join(f"<div><b>{e(str(v))}</b><span>{e(k)}</span></div>" for v, k in stats) + f"</div>{bar(c)}</header>"
            + (f'<h2>기획한 것 중 얼마나 됐나 — GDD 절마다</h2><div class="chips">{chips}</div><div class="grid">{gdd_html(titles, rows, touched)}</div>'
               if rows else f'<h2>GDD</h2><p>{e(CFG["gdd"])} 의 부록 A 에 행이 없다.</p>')
            + ('<h2>일이 어떻게 흘렀나 — 사이클마다</h2>' + "".join(cycle_html(cy, cy is now) for cy in reversed(cycles)) if cycles else "")
            + f'</main><script>{JS.replace("RELOAD", str(int(CFG["reload_sec"])))}</script></html>\n')
    return page, f'GDD 동기 {c["동기"]}/{live} · 불일치 {c["불일치"]} · 사이클 {len(cycles)}개 · 답 없는 결정 {waiting}'


def sources():
    return [os.path.join(ROOT, CFG["gdd"]), os.path.join(ROOT, CONFIG_NAME)] + cycle_docs()


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
        page, line = build()
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(page)
        if not quiet:
            print(f"{os.path.relpath(out, ROOT)} — {line}")
    except Exception as err:  # 훅으로 돌 때는 무슨 일이 있어도 사용자의 턴을 막지 않는다
        if not quiet:
            sys.exit(str(err))


if __name__ == "__main__":
    main()
