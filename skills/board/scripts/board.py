#!/usr/bin/env python3
"""Status board — reads the GDD sync table · asset records · cycle · playtest documents and draws them as HTML. No model draws it.

  python3 board.py              rewrite <out> (default docs/board/index.html) and the pages beside it; print the path and a one-line summary
  python3 board.py --if-stale   rewrite only when the board exists and a source is newer. Prints nothing and always exits 0 (the hook calls it)
  python3 board.py share        bundle the board and the review page into one page for a private claude.ai link — writes <share_dir>/ and its publish.json
  python3 board.py share --done <url>   after the publish went through: remember the link (board.share in kit.config.json) and what was sent
  python3 board.py answers <folder|rows.json>  the answers tapped on the shared review page (its "answers" collection, saved as files) → what each one asks for

index.html is the chart — one card per stage of play, in play order: how far Function · Art · Sound · Verified have come.
When the game has a balance table, a tile on it opens the table and says so when it is in step with the value file (the two files carry the same time).
stage-N.html is the inside of one stage. Every state is read as written (the code is not searched here).
review.html is what waits on the user, with a button per answer: the newest cycle's open decisions (with their comparison pictures, from the
question files the cycle's sheet script keeps), asset images not yet approved, and — once the cycle is at Play — what to check by playing.

Read-only towards the documents — it writes inside the folder of <out> (and, for `share --done`, the link into kit.config.json). Config is "board" in kit.config.json at the project root (optional).

Documents are read in both vocabularies: the English words the kit writes now and the Korean words older documents hold.
"""
import datetime
import fnmatch
import hashlib
import html
import json
import os
import re
import shutil
import struct
import sys
import urllib.parse

CONFIG_NAME = "kit.config.json"
SECTION = "board"
DEFAULTS = {
    "out": "docs/board/index.html",
    "gdd": "docs/GDD.md",
    "appendix_heading": "## Appendix A",
    "cycles": "docs/cycle",
    "reload_sec": 30,   # how often an open board reloads itself. 0 = never
    "playtests": "docs/playtest",
    "gen": "assets/_gen",          # asset records (left by the asset skill)
    "assets": "assets",
    "design": "docs/DESIGN.md",    # the document holding Art style · World · Learned — shown at the head of the asset sheet
    "notes": "docs/board-notes.md",  # what the user notes after playing: `- stage | lane | problem | text`
    "open_heading": "Open questions",  # words in the heading of the GDD section that lists what is not decided yet
    "common": "Unsorted",          # where things that fit no stage gather — not counted in the %
    "ignore": [],                  # asset names not to count (glob) — planned, then dropped
    "flow": [],                    # the stages of play, in order. Empty = one per GDD section
    "sheets": "docs/cycle/sheets", # the question files of the cycle's sheet script — the pictures of a decision chosen by eye
    "share_dir": "docs/board/share",  # where `share` bundles the page and the files it shows
    "share": "",                   # the private link the board was published to (written by `share --done`)
}
# Document words: the English form is written now, the Korean one is in older documents. Both are read.
LEGACY = {"appendix_heading": "## 부록 A", "open_heading": "미정"}  # read too while the config holds the default
STATE = {"동기": "synced", "불일치": "mismatch", "미구현": "missing", "폐기": "retired"}  # GDD table states → the English form
STAGE_LABEL = {"목표": "Goal", "기획": "Spec", "디자인": "Design", "계획": "Plan", "구현": "Build", "플레이": "Play", "끝": "Closed"}
STAGE_DONE = r"Closed|끝|회고|배포"  # the last two are stages older documents hold
STAGE_PLAY = r"Play|플레이"
CYCLE_HEAD = r"^# (?:Cycle|사이클) (\S+) — (.+)$"
STAGE_LINE = r"(?:\bStage|단계): *(\S+)"
START_LINE = r"(?:\bStarted|시작): *(\d{4}-\d\d-\d\d)"
WAVE_LINE = r"- *(?:Wave *(\d+)|(\d+) *차)[^:]*:(.*)"  # `Wave 1 (done):` · `1차 (끝):` too
RECOMMENDED = r" · (?:recommended|권함):"
SEC = {"goal": ("Goal", "목표"), "decisions": ("Decisions", "결정"), "order": ("Order", "순서")}
FIELD = {"blocked": "Blocked|막힘", "done": "Done|한 것"}
NEEDS_HEAD = r"^### (?:Assets needed|필요한 에셋)[ \t]*$"
HAVE_NONE = ("none", "없음")
HAVE_TEMP = r"placeholder|임시"
SOUND_KIND = r"sound|music|소리|음악|효과음"
ROW_RE = re.compile(r"^\|\s*([A-Z]+(?:\.[A-Z0-9_]+)+)\s*\|(.*)$")
ID_RE = re.compile(r"[A-Z]+(?:\.[A-Z0-9_]+)+")
TASK_RE = re.compile(r"^### \[(.)\] (T\d+)\.(.*)$", re.M)
DECISION_RE = re.compile(r"^- \[(.)\] (D\d+)\.(.*)$", re.M)

ROOT = ""
CFG = dict(DEFAULTS)
e = html.escape


def md(text):
    """Document text as shown: escaped, with the inline marks the documents use (~~struck~~, **bold**, `code`) drawn instead of printed."""
    t = e(str(text))
    t = re.sub(r"~~(.+?)~~", r"<s>\1</s>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)


def find_root(start):
    """The folder holding kit.config.json, searched upward from the current folder. None if there is none."""
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


# ── Reading ───────────────────────────────────────────────────────────

def gdd():
    """(game name, section number → title, the rows of appendix A)."""
    text = read(os.path.join(ROOT, CFG["gdd"]))
    name = re.search(r"^# (.+)$", text, re.M)
    titles = {m.group(1): m.group(2).strip() for m in re.finditer(r"^#{2,4} (\d+(?:\.\d+)*)\.? +(.+)$", text, re.M)}
    rows, inside = [], False
    for line in text.split("\n"):
        inside = inside or line.startswith(both("appendix_heading"))
        m = ROW_RE.match(line) if inside else None
        cells = [c.strip() for c in m.group(2).split("|")] if m else []
        if len(cells) < 5:
            continue
        src = re.search(r"\d+(?:\.\d+)*", cells[1])
        state = STATE.get(cells[3], cells[3])
        state = state if state in STATE.values() else "missing"
        rows.append({"id": m.group(1), "value": cells[0], "src": src.group(0) if src else "", "where": cells[2],
                     "state": state, "note": cells[4]})
    return (name.group(1).split("—")[0].strip() if name else os.path.basename(ROOT)), titles, rows


def both(key):
    """The config value — and, while it is the default, the Korean form older documents hold."""
    return (CFG[key], LEGACY[key]) if CFG[key] == DEFAULTS[key] else (CFG[key],)


def section(text, key):
    m = re.search(rf"^## (?:{'|'.join(SEC[key])})[ \t]*$", text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end():m.end() + nxt.start() if nxt else len(text)]


PROXY_LINE = re.compile(r"^(.*) → (.*? · (?:proxy|대리) .*?)$")  # the arrow before the answer is the last one — the options may hold arrows too


def decision(mark, num, rest):
    """Splits `question — ① … ② … · recommended: ① (Spec) → the user's answer (date)`."""
    proxy = PROXY_LINE.match(rest.strip()) if mark == "~" else None
    ask, _, answer = (proxy.group(1), "", proxy.group(2)) if proxy else rest.strip().partition(" → ")
    date = re.search(r"\s*\((\d{4}-\d\d-\d\d)\)\s*$", answer)
    who = re.search(r"\s*\(([^()]{1,8})\)\s*$", ask)
    ask = ask[:who.start()] if who else ask
    ask, pick = (re.split(RECOMMENDED, ask, 1) + [""])[:2]
    cut = re.search(r" — (?=①)", ask) or re.search(r" — ", ask)  # the dash before the options, not one inside the title
    title, options = (ask[:cut.start()], ask[cut.end():]) if cut else (ask, "")
    pick = re.sub(r"\s*\([^()]*\)\s*$", "", pick)
    return {"num": num, "done": mark == "x", "proxy": mark == "~", "title": title.strip(), "options": options.strip(), "pick": pick.strip(),
            "who": who.group(1) if who else "", "answer": (answer[:date.start()] if date else answer).strip(),
            "date": date.group(1) if date else ""}


def cycle(path):
    text = read(path)
    head = re.search(CYCLE_HEAD, text, re.M)
    stage = re.search(STAGE_LINE, text)
    start = re.search(START_LINE, text)
    waves = {}
    for line in section(text, "order").split("\n"):
        m = re.match(WAVE_LINE, line.strip())
        for t in re.findall(r"T\d+", m.group(3).split("—")[0]) if m else []:
            waves[t] = int(m.group(1) or m.group(2))
    tasks, hits = [], list(TASK_RE.finditer(text))
    for m in hits:
        nxt = re.search(r"^##+ ", text[m.end():], re.M)
        block = text[m.end():m.end() + nxt.start() if nxt else len(text)]
        line = lambda key: (re.search(rf"^- \*\*(?:{key})\*\*:(.*)$", block, re.M) or [None, ""])[1].strip()  # key: one name, or alternatives
        tasks.append({"num": m.group(2), "mark": m.group(1), "title": m.group(3).strip(), "wave": waves.get(m.group(2), 0),
                      "ids": ID_RE.findall(line("GDD")), "blocked": line(FIELD["blocked"]), "did": line(FIELD["done"]),
                      "all_ids": ID_RE.findall(block), "block": block})
    num = head.group(1) if head else os.path.basename(path).split("-")[0]
    needs = []
    nm = re.search(NEEDS_HEAD, text, re.M)
    if nm:
        end = re.search(r"^##+ ", text[nm.end():], re.M)
        for row in text[nm.end():nm.end() + end.start() if end else len(text)].split("\n"):
            cells = [c.strip() for c in row.strip().strip("|").split("|")] if row.startswith("|") else []
            name = cells[0].split(" — ")[0].strip("` ") if cells else ""
            if len(cells) >= 4 and re.fullmatch(r"[a-z][a-z0-9_]*", name) and cells[1].strip("—–- "):  # no Kind: a row saying nothing is needed
                needs.append({"name": name, "what": cells[0].partition(" — ")[2], "kind": cells[1], "have": cells[3]})
    return {"needs": needs, "file": os.path.basename(path), "num": num, "name": head.group(2).strip() if head else os.path.basename(path)[:-3],
            "stage": stage.group(1) if stage else "?", "start": start.group(1) if start else "",
            "goal": " ".join(section(text, "goal").split()),
            "decisions": [decision(*m.groups()) for m in DECISION_RE.finditer(section(text, "decisions"))], "tasks": tasks}


# ── The chart — in play order, one screen ─────────────────────────────
#
# The first screen (index) holds only the stage cards. A card opens that stage's page (stage-N.html).
# The stages come from board.flow in kit.config.json (without it, one per GDD section). Every state is read:
#   function    — the rows of GDD appendix A (synced · missing · mismatch)
#   art · sound — asset records (assets/_gen) and the "Assets needed" table of the cycle documents (none · placeholder)
#   verified    — whether a cycle that touched the stage has passed Play, playtest tasks, the user's notes (board-notes)

LANES = ["function", "art", "sound", "verified"]  # the keys used inside
LANE_LABEL = {"function": "Function", "art": "Art", "sound": "Sound", "verified": "Verified"}  # the names on screen and in board-notes
LANE_KEY = dict({v.lower(): k for k, v in LANE_LABEL.items()}, **{"기능": "function", "아트": "art", "사운드": "sound", "검증": "verified"})
WEIGHT = {"done": 1.0, "temp": 0.5, "none": 0.0, "bad": 0.0}
WORD = {"done": "Done", "temp": "Placeholder", "none": "Not made", "bad": "Problem"}
ORDER = ["bad", "none", "temp", "done"]
NOTE_WORD = {"문제": "bad", "임시": "temp", "됨": "done", "없음": "none", "안 만듦": "none",
             "problem": "bad", "placeholder": "temp", "done": "done", "none": "none", "not made": "none"}
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
SOUND_EXT = (".mp3", ".ogg", ".wav")
MODEL_EXT = (".glb", ".gltf", ".fbx", ".obj")
OUTDIR = ""


def playtest_docs():
    d = os.path.join(ROOT, CFG["playtests"])
    return sorted(os.path.join(d, n) for n in os.listdir(d) if n.endswith(".md")) if os.path.isdir(d) else []


SHARED = None  # while bundling for a link: published name → the file it is a copy of


def rel(path):
    """The path as seen from the board's folder (pictures and sounds are pointed at, not copied).
    While bundling for a link, the file is named by its content under f/ instead — the bundle carries it."""
    if not path:
        return ""
    if SHARED is not None:
        if not os.path.isfile(path):
            return ""
        pub = "f/" + hashlib.sha1(open(path, "rb").read()).hexdigest()[:16] + os.path.splitext(path)[1].lower()
        SHARED[pub] = os.path.abspath(path)
        return pub
    return urllib.parse.quote(os.path.relpath(path, OUTDIR).replace(os.sep, "/"))


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
        for fn, lane in (("asset.json", "art"), ("sprite.json", "art"), ("sound.json", "sound")):
            rec = load_json(os.path.join(gdir, name, fn))
            if not isinstance(rec, dict):
                continue
            out = os.path.join(ROOT, rec["out"]) if rec.get("out") else ""
            out = out if out and os.path.exists(out) else files.get(name, "")
            if not out:  # a record whose file never reached the game (a dropped attempt) is not counted
                continue
            front = os.path.join(gdir, name, "still.png" if fn == "sprite.json" else "front.png")
            found[name] = dict(item("done", name, " · ".join(x for x in (rec.get("kind") or ("model" if lane == "art" else ""),
                                                                         rec.get("made") or rec.get("created") or "") if x),
                                    img=front if os.path.exists(front) else picture(out), audio=out if lane == "sound" else ""), lane=lane)
    made = set(found)
    for c in cycles:
        for n in c["needs"]:
            lane = "sound" if re.search(SOUND_KIND, n["kind"], re.I) else "art"
            it = found.get(n["name"]) or dict(item("none", n["name"], n["kind"], img=picture(files.get(n["name"], ""))), lane=lane)
            have = n["have"].strip()
            cited = re.findall(r"`([^`]+\.[A-Za-z0-9]+)`", have)  # a file named in the Have cell — it must still exist to count as done
            there = (n["name"] in made or n["name"] in files or (any(os.path.exists(os.path.join(ROOT, c)) for c in cited) if cited
                                                                 else not (have.startswith(HAVE_NONE) or have in ("", "—"))))
            it["st"] = "temp" if re.search(HAVE_TEMP, have) else "done" if there else "none"
            it["note"] = n["what"] + (f" — {have}" if it["st"] == "temp" else " — the file named is missing" if cited and not there else "")
            it["tags"] = [f'Cycle {c["num"]}']
            it["audio"] = it["audio"] or sound(files.get(n["name"], ""))
            found[n["name"]] = it
    for name, path in files.items():  # sounds and models in the game without a record count too (put in by hand)
        if name not in found and path.lower().endswith(SOUND_EXT + MODEL_EXT):
            found[name] = dict(item("done", name, "no record", audio=sound(path)), lane="sound" if sound(path) else "art")
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
        state = "done" if re.match(STAGE_DONE, c["stage"]) else "temp" if re.match(STAGE_PLAY, c["stage"]) else "none"
        said = {"done": "played", "temp": "your turn to play", "none": f'at {stage_word(c["stage"])}'}[state]
        hit = {}
        for t in c["tasks"]:
            for i in {where[x] for x in t["ids"] if x in where}:
                hit.setdefault(i, []).append(t)
        for i, ts in hit.items():
            st[i]["lanes"]["verified"].append(item(state, f'Cycle {c["num"]} — {c["name"]}', said))
            st[i]["work"].append((c, ts))
    for p in playtests:
        date = re.match(r"\d{4}-\d\d-\d\d", p["file"])
        for t in p["tasks"]:
            s = place_ids(st, where, t["all_ids"]) or place_words(st, t["title"]) or st[-1]
            s["lanes"]["verified"].append(item("done" if t["mark"] == "x" else "bad", t["title"],
                                         f'Playtest {date.group(0) if date else ""} · {"fixed" if t["mark"] == "x" else "open"}'))
    for line in read(os.path.join(ROOT, CFG["notes"])).split("\n"):
        cells = [c.strip() for c in line.lstrip("-* ").split("|")] if line.strip().startswith(("-", "*")) else []
        if len(cells) < 4:
            continue
        s = next((s for s in st if cells[0] and cells[0] in s["name"]), st[-1])
        lane = LANE_KEY.get(cells[1].lower(), "verified")
        s["lanes"][lane].append(item(NOTE_WORD.get(cells[2].lower(), "bad"), " | ".join(cells[3:]), "noted by the user"))


def open_questions(st, cycles):
    """The unstruck bullets of the GDD's open-questions section, and the decisions without an answer."""
    text = read(os.path.join(ROOT, CFG["gdd"]))
    m = re.search(rf"^## .*(?:{'|'.join(map(re.escape, both('open_heading')))}).*$", text, re.M)
    out = []
    if m:
        nxt = re.search(r"^(## |---)", text[m.end():], re.M)
        for b in re.findall(r"^- (.+)$", text[m.end():m.end() + nxt.start() if nxt else len(text)], re.M):
            if b.startswith("~~"):
                continue
            t = re.match(r"\*\*(.+?)\*\*:?\s*(.*)", b) or re.match(r"(.+?)(?: — |: | \(|\. )(.*)", b)  # without a bold title, the first phrase
            out.append({"title": (t.group(1) if t else b).replace("**", ""), "text": (t.group(2) if t else "").replace("**", ""), "from": "GDD"})
    for c in cycles:
        out += [{"title": f'{d["num"]} {d["title"]}', "text": "decided for you — waiting for your confirmation" if d["proxy"] else "waiting for your answer", "from": f'Cycle {c["num"]}'} for d in c["decisions"] if not d["done"]]
    for q in out:
        s = place_words(st, q["title"] + " " + q["text"]) or st[-1]
        q["stage"] = s["i"]
        s["open"].append(q)
    return out


def stage_word(stage):
    """The stage name written in a cycle document, as the word shown on screen."""
    return STAGE_LABEL.get(stage, stage)


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
    return next((rel(i["img"]) for i in s["lanes"]["art"] if i["img"]), "")


def stage_label(s, lead=""):
    return " · ".join(x for x in ("%s%02d" % (lead, s["i"] + 1), e(sections_label(s))) if x)


def sections_label(s):
    return "GDD " + " · ".join(map(str, s["sections"])) if s["sections"] else ""


CHART_CSS = """
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css");
@property --p{syntax:'<number>';inherits:true;initial-value:0}
:root{color-scheme:dark;--bg:#07110E;--bg2:#0B1A17;--card:#0D1B22;--card2:#10262B;--line:#17332D;--line2:#27504A;--mint:#3DFFB0;--lime:#D8FF5A;--sun:#FFD24A;--sky:#8AD8FF;--pink:#FF8AD1;--red:#FF5A6A;--red2:#FF8A96;
--tx:#F0F1F5;--tx2:#A9AFBA;--tx3:#7C8792;--rainbow:linear-gradient(90deg,#3DFFB0,#D8FF5A 45%,#FFD24A 80%,#FF8AD1);--mono:"D2Coding",ui-monospace,"SFMono-Regular",Menlo,Consolas,monospace}
*{box-sizing:border-box}html,body{min-height:100%}[hidden]{display:none!important}
body{margin:0;color:var(--tx);font:14px/1.5 "Pretendard Variable",Pretendard,-apple-system,"Apple SD Gothic Neo",system-ui,sans-serif;
background:radial-gradient(900px 520px at 12% -10%,rgba(61,255,176,.2),transparent 60%),radial-gradient(900px 620px at 95% 110%,rgba(176,108,255,.22),transparent 60%),
linear-gradient(rgba(61,255,176,.05) 1px,transparent 1px) 0 0/40px 40px,linear-gradient(90deg,rgba(61,255,176,.05) 1px,transparent 1px) 0 0/40px 40px,
linear-gradient(135deg,#07110E,#0B2A22 55%,#1A1033);background-color:var(--bg)}
a{color:inherit;text-decoration:none}ul{list-style:none;margin:0;padding:0}
.lab{font:10px/1.4 var(--mono);letter-spacing:.1em;color:var(--tx3);text-transform:uppercase}
.page{padding:22px 28px 26px;display:flex;flex-direction:column;gap:16px;min-height:100vh}
header{display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap}
h1{margin:2px 0 0;font-size:36px;font-weight:900;letter-spacing:-.03em;display:flex;align-items:center;gap:12px;line-height:1.15;
color:transparent;background:var(--rainbow);-webkit-background-clip:text;background-clip:text}
h1::before{content:"";width:20px;height:20px;background:var(--mint);clip-path:polygon(50% 0,62% 38%,100% 50%,62% 62%,50% 100%,38% 62%,0 50%,38% 38%)}
h1 span{font-weight:400;-webkit-text-fill-color:var(--tx2)}
.sub{color:var(--tx2);font-size:12px;margin-top:4px}
.tiles{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.tile{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line2);border-radius:14px;padding:7px 14px 8px;min-width:96px}
.tile .lab{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tile b{display:block;font-size:22px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.15}
.tile.gold{border-color:var(--mint);background:linear-gradient(180deg,rgba(61,255,176,.2),var(--card))}.tile.gold b{color:var(--lime);text-shadow:0 0 16px rgba(61,255,176,.6)}
.tile.red{border-color:rgba(255,90,106,.6);background:linear-gradient(180deg,rgba(255,90,106,.18),var(--card))}.tile.red b{color:var(--red2)}
.total{display:flex;gap:6px;height:10px}
.total div{background:#10241F;border-radius:999px;position:relative;overflow:hidden}
.total i{position:absolute;inset:0 auto 0 0;border-radius:999px;background:linear-gradient(90deg,var(--mint),var(--lime));box-shadow:0 0 14px var(--mint);animation:grow 1.1s cubic-bezier(.2,.8,.2,1) both}
@keyframes grow{from{width:0}}
.legend{display:flex;gap:16px;font-size:11px;color:var(--tx2);align-items:center;flex-wrap:wrap}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}
.s-done{background:var(--mint)}.s-temp{background:repeating-linear-gradient(45deg,var(--mint) 0 2px,rgba(61,255,176,.12) 2px 5px)}.s-none{background:#24403F}.s-bad{background:var(--red);box-shadow:0 0 8px var(--red)}
.asks{display:flex;gap:8px;overflow:hidden}
.ask{flex:1 1 0;min-width:0;border:2px dashed var(--red);border-radius:14px;background:rgba(255,90,106,.08);padding:6px 12px;font-size:12px;color:var(--tx2)}
.ask b{color:var(--tx);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ask span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ask.more{flex:0 0 auto;display:grid;place-items:center;color:var(--red2);font:700 13px var(--mono)}
.flow{--g:30px;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:var(--g);position:relative;flex:1;align-items:stretch;margin-top:8px}
.loop{position:absolute;top:-14px;bottom:-12px;border:2px dashed var(--pink);border-radius:26px;pointer-events:none;filter:drop-shadow(0 0 5px rgba(255,138,209,.45));
left:calc((100% + var(--g))/var(--n)*var(--a) - var(--g)/2);width:calc((100% + var(--g))/var(--n)*var(--c))}
.loop span{position:absolute;top:-9px;left:22px;background:#0A211C;border-radius:999px;padding:0 8px;color:#FFC4E8;font-weight:700}
.slot{position:relative;display:flex;animation:rise .6s cubic-bezier(.2,.8,.2,1) both;animation-delay:calc(var(--i)*70ms)}
@keyframes rise{from{opacity:0;transform:translateY(18px)}}
.slot:not(:last-child)::after{content:"→";position:absolute;right:calc(var(--g)*-1);top:80px;width:var(--g);text-align:center;font:800 20px/24px system-ui,sans-serif;color:var(--sun)}
.node{position:relative;flex:1;display:flex;flex-direction:column;background:var(--card);border:2px solid rgba(138,216,255,.7);border-radius:22px;box-shadow:0 0 16px rgba(138,216,255,.18);
overflow:hidden;transition:transform .2s,box-shadow .2s,border-color .2s;min-height:330px}
@media(hover:hover){.slot:hover{z-index:2}.slot:hover .node{transform:translateY(-5px);border-color:var(--mint)}
.slot:hover{filter:drop-shadow(0 12px 26px rgba(61,255,176,.25))}.slot:hover .hero{transform:scale(1.06)}}
.node.low{border-color:var(--line2);box-shadow:none}.node.warn{border-color:var(--red);box-shadow:0 0 16px rgba(255,90,106,.25)}
.hero{flex:1 1 132px;min-height:132px;background:#0A1512 center/cover no-repeat;position:relative;transition:transform .5s}
.hero.none{background:repeating-linear-gradient(135deg,#0B1A17 0 10px,#0E201C 10px 20px)}
.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(7,17,14,.1) 0%,rgba(13,27,34,.55) 60%,var(--card) 100%)}
.ghost{position:absolute;right:8px;top:70px;font:800 92px/1 var(--mono);color:rgba(255,255,255,.07);letter-spacing:-.06em;pointer-events:none}
.ring{--s:58px;width:var(--s);height:var(--s);border-radius:50%;display:grid;place-items:center;position:relative;
background:conic-gradient(var(--mint) calc(var(--p)*1%),#1F3A38 0);animation:spin 1.2s cubic-bezier(.2,.8,.2,1) both;filter:drop-shadow(0 0 8px rgba(61,255,176,.5))}
.ring::before{content:"";position:absolute;inset:5px;border-radius:50%;background:#08130F}
.ring b{position:relative;font:800 17px var(--mono);color:var(--lime)}.ring b::after{content:"%";font-size:9px;color:var(--tx3);margin-left:1px}
.ring.big{--s:112px}.ring.big::before{inset:9px}.ring.big b{font-size:34px}.ring.big b::after{font-size:13px}
@keyframes spin{from{--p:0}}
.node .ring{position:absolute;right:16px;top:14px}
.body{padding:0 14px 14px;margin-top:-34px;position:relative;display:flex;flex-direction:column;gap:8px}
.node h2{margin:0;font-size:20px;font-weight:800;letter-spacing:-.02em;text-shadow:0 2px 12px #000}
.node p{margin:0 0 4px;font-size:12px;color:var(--tx2);min-height:36px}
.lane{display:grid;grid-template-columns:58px 1fr 44px;gap:8px;align-items:center;font:11px var(--mono);color:var(--tx2)}
.lane em{font-style:normal;text-align:right;color:var(--tx3)}
.seg{display:flex;gap:2px;height:8px}.seg i{display:block;min-width:3px;border-radius:999px}.seg.empty{border:1px dashed var(--line2);border-radius:999px}
.chips{display:flex;gap:6px;flex-wrap:wrap;min-height:20px;align-items:center}
.chip{font:10px var(--mono);padding:2px 9px;border:1px solid var(--line2);border-radius:999px;color:var(--tx2)}
.chip.bad{border-color:var(--red);color:var(--red2)}.chip.go{margin-left:auto;border-color:var(--mint);color:#5DFFC0;background:rgba(61,255,176,.08)}
.rest{display:flex;gap:14px;align-items:center;border:1px solid var(--line2);border-radius:16px;background:rgba(11,26,23,.8);padding:8px 16px;font-size:12px;color:var(--tx2)}
.tile.warn b{color:var(--sun)}
a.tile.go{border-color:var(--sky);background:linear-gradient(180deg,rgba(138,216,255,.22),var(--card));box-shadow:0 0 18px rgba(138,216,255,.25);transition:transform .15s,box-shadow .15s}
a.tile.go b{color:var(--sky);white-space:nowrap}a.tile.go .lab{color:var(--tx2)}a.tile.go:hover{transform:translateY(-3px);box-shadow:0 0 26px rgba(138,216,255,.5)}
a.btn.go{border-color:var(--sky);color:var(--sky);background:rgba(138,216,255,.1)}.rest b{color:var(--tx)}.rest .lane{flex:1;max-width:220px}
footer{display:flex;gap:16px;font:10px var(--mono);color:var(--tx3)}footer a{color:var(--tx2);border-bottom:1px solid var(--line2)}
/* stage page */
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.btn{font:11px var(--mono);padding:6px 14px;border:1px solid var(--line2);border-radius:999px;background:var(--card);color:var(--tx2)}
.btn:hover{border-color:var(--mint);color:var(--tx)}.btn.on{border-color:var(--mint);color:#5DFFC0;background:rgba(61,255,176,.12);box-shadow:0 0 14px rgba(61,255,176,.25)}
.tabs{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}
.banner{position:relative;border:3px solid transparent;border-radius:26px;background:linear-gradient(var(--card),var(--card)) padding-box,var(--rainbow) border-box;overflow:hidden;padding:22px 26px;display:flex;gap:22px;align-items:center;
min-height:170px;box-shadow:0 14px 50px rgba(61,255,176,.14)}
.banner .pic{position:absolute;inset:0 0 0 35%;background:center/cover no-repeat;opacity:.75}
.banner::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,var(--card) 30%,rgba(13,27,34,.75) 55%,rgba(13,27,34,.15))}
.banner::after{pointer-events:none}.banner>*{position:relative;z-index:1}.banner .pic{position:absolute;z-index:0;border:0;padding:0}
.banner h1{font-size:40px}.banner .tiles{margin-left:auto}
.cols{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr;gap:14px;align-items:start}
@media(max-width:1100px){.cols{grid-template-columns:1fr 1fr}}
.col{background:rgba(11,26,23,.82);border:1px solid var(--line2);border-radius:18px;padding:12px 16px}
.col>h3{margin:0 0 4px;font-size:15px;display:flex;align-items:baseline;gap:8px}.col>h3 small{margin-left:auto;font:11px var(--mono);color:var(--tx3)}
.col .seg{margin-bottom:12px}
.it{display:flex;gap:9px;align-items:flex-start;padding:7px 0;border-top:1px solid var(--line);font-size:12.5px}
.it>i{flex:none;width:9px;height:9px;border-radius:50%;margin-top:5px}
.it .t{flex:1;min-width:0}.it .t b{font-weight:600;overflow-wrap:anywhere}.it .t small{display:block;color:var(--tx3);font-size:11px;overflow-wrap:anywhere}
.it code{font:11px var(--mono);color:var(--lime)}
.it.st-none b{color:var(--tx2)}.it.st-bad b{color:var(--red2)}
.tag{font:10px var(--mono);color:var(--sky);border:1px solid rgba(138,216,255,.5);border-radius:999px;padding:0 7px;margin-left:5px}
.thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:8px}
.thumb{background:var(--card2);border:1px solid var(--line2);border-radius:12px;overflow:hidden;position:relative}
.thumb .im{aspect-ratio:1;background:#0A1512 center/contain no-repeat;display:grid;place-items:center;color:var(--tx3);font:10px var(--mono)}
.thumb:hover .im{background-color:#12262A}
.zoom{cursor:zoom-in}button.im{width:100%;border:0;padding:0;display:block}
#box{position:fixed;inset:0;z-index:9;background:rgba(3,10,8,.92);display:none;flex-direction:column;align-items:center;justify-content:center;gap:12px;cursor:zoom-out;backdrop-filter:blur(6px)}
#box.on{display:flex;animation:fade .18s}#box img{max-width:92vw;max-height:84vh;object-fit:contain;filter:drop-shadow(0 0 40px rgba(61,255,176,.25))}
#box span{font:12px var(--mono);color:var(--lime);letter-spacing:.08em}@keyframes fade{from{opacity:0}}
.thumb span{display:block;padding:4px 7px 5px;font:10.5px var(--mono);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.thumb>i{position:absolute;left:7px;top:7px;width:9px;height:9px;border-radius:50%}
.thumb.st-none{border-style:dashed}.thumb.st-none .im{opacity:.5}
.play{flex:none;width:26px;height:26px;border:1px solid var(--mint);background:rgba(61,255,176,.1);color:#5DFFC0;font-size:10px;cursor:pointer;border-radius:50%}
.play.on{background:var(--mint);color:#04261A;box-shadow:0 0 14px var(--mint)}
details>summary{cursor:pointer;color:var(--tx3);font:11px var(--mono);padding:8px 0;border-top:1px solid var(--line)}
.under{display:grid;grid-template-columns:1fr 2fr;gap:14px;align-items:start}
.task{display:inline-block;font-size:12px;border:1px solid var(--mint);border-radius:999px;padding:3px 11px;margin:0 6px 6px 0;background:var(--card)}
.task.open{border-color:var(--line2)}.task.blocked{border-color:var(--red)}
.col h4{margin:10px 0 6px;font:11px var(--mono);color:var(--tx3)}
/* review page */
a.tile.rv{border-color:var(--red);background:linear-gradient(180deg,rgba(255,90,106,.22),var(--card));box-shadow:0 0 18px rgba(255,90,106,.25)}a.tile.rv b{color:var(--red2)}
a.btn.rv{border-color:var(--red);color:var(--red2);background:rgba(255,90,106,.1)}
.rvs{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(360px,100%),1fr));gap:14px;align-items:start}
.card{background:rgba(11,26,23,.86);border:1px solid var(--line2);border-radius:18px;padding:14px 16px;display:flex;flex-direction:column;gap:10px;transition:border-color .2s}
.card.done{border-color:var(--mint);box-shadow:0 0 16px rgba(61,255,176,.15)}
.card h3{margin:0;font-size:16px;line-height:1.35}.card h3 code{font:700 12px var(--mono);color:var(--lime);margin-right:6px}
.card .was{font-size:12.5px;color:var(--sun)}
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}
.figs figure{margin:0}.figs figcaption{font:10.5px var(--mono);color:var(--tx2);padding:0 0 4px}
.figs .im{aspect-ratio:1;background:#0A1512 center/contain no-repeat;border:1px solid var(--line2);border-radius:10px;width:100%;padding:0;display:block}
.crop{position:relative;overflow:hidden;border:1px solid var(--line2);border-radius:10px}.crop img{position:absolute;display:block;max-width:none}
.opts{display:flex;flex-direction:column;gap:6px}
.opt{font-size:14px;line-height:1.4;font-family:inherit;text-align:left;color:var(--tx);background:var(--card2);border:1px solid var(--line2);border-radius:12px;padding:10px 12px;cursor:pointer;display:flex;gap:8px;align-items:baseline}
.opt b{font-family:var(--mono);color:var(--sky)}.opt em{margin-left:auto;font:10px var(--mono);font-style:normal;color:var(--mint);white-space:nowrap}
.opt:hover{border-color:var(--mint)}.opt.on{border-color:var(--mint);background:rgba(61,255,176,.16);box-shadow:0 0 14px rgba(61,255,176,.3)}
.opt.no.on{border-color:var(--red);background:rgba(255,90,106,.16);box-shadow:0 0 14px rgba(255,90,106,.3)}
.pair{flex-direction:row}.pair .opt{flex:1;justify-content:center;text-align:center}
.note{width:100%;min-height:40px;resize:vertical;font-size:13px;line-height:1.4;font-family:inherit;color:var(--tx);background:#08130F;border:1px solid var(--line2);border-radius:10px;padding:8px 10px}
.note:focus{outline:none;border-color:var(--mint)}
.state{font:10px var(--mono);color:var(--mint)}.state:empty{display:none}
.clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.basis>summary{list-style:none;cursor:pointer;border:0;padding:0}.basis>summary::-webkit-details-marker{display:none}.basis>summary h3{margin:0;font-size:15px;color:var(--tx);font-family:inherit;display:flex;align-items:baseline;gap:8px}.basis>summary h3::before{content:"▸";color:var(--tx3);font-size:11px}.basis[open]>summary h3::before{content:"▾"}.basis>summary h3 small{margin-left:auto;font:11px var(--mono);color:var(--tx3)}.basis[open]>summary{margin-bottom:6px}
.dock{position:sticky;bottom:0;z-index:5;display:flex;gap:12px;align-items:center;flex-wrap:wrap;border:1px solid var(--line2);border-radius:16px;
background:rgba(8,19,15,.94);backdrop-filter:blur(8px);padding:10px 16px calc(10px + env(safe-area-inset-bottom,0px));font-size:12px;color:var(--tx2)}
.dock b{font:800 18px var(--mono);color:var(--lime)}.dock .copy{margin-left:auto;cursor:pointer}.dock .out{flex:1 1 100%;min-height:60px}
@media(max-width:760px){
.page{padding:14px 16px 18px;gap:12px}h1{font-size:26px}.banner h1{font-size:28px}.banner{padding:16px;min-height:0;flex-wrap:wrap}.banner .pic{inset:0;opacity:.3}
header .tiles,.banner .tiles{margin-left:0}.tile{min-width:0;flex:1 1 30%;padding:6px 10px}.tile b{font-size:18px}
.flow{grid-template-columns:1fr;--g:14px;flex:none}.slot:not(:last-child)::after{content:"↓";right:auto;left:50%;top:auto;bottom:calc(var(--g)*-1);height:var(--g);line-height:var(--g);transform:translateX(-50%)}
.loop{display:none}.node{min-height:0}.hero{flex-basis:96px;min-height:96px}.body{margin-top:-24px}.asks{flex-direction:column}
.cols,.under{grid-template-columns:1fr}.tabs{margin-left:0}
.tile.minor,.ghost,.legend,.ask span,.asks .ask:nth-child(n+4),.node p,header .sub,.chip.go,.ask.more,a.tile.go .lab{display:none}
a.tile.go{flex:1 1 40%}a.tile.go b{font-size:15px;white-space:normal}.tile{overflow:hidden}
.tabs{flex-wrap:nowrap;overflow-x:auto;max-width:100%;padding-bottom:2px}.tabs .btn{white-space:nowrap}.banner .tiles .tile{flex:1 1 20%}
.it .t small{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.opt{padding:9px 11px;font-size:13.5px}.rvs{grid-template-columns:minmax(0,1fr)}.card{min-width:0}.rest{flex-wrap:wrap}footer{flex-wrap:wrap}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
.still *{animation:none!important}
"""
CHART_JS = """
let a=null,on=null;document.querySelectorAll('.play').forEach(b=>b.onclick=()=>{if(a){a.pause();on.classList.remove('on');on.textContent='▶';if(on===b){a=on=null;return}}
 a=new Audio(b.dataset.src);on=b;b.classList.add('on');b.textContent='■';a.play();a.onended=()=>{b.classList.remove('on');b.textContent='▶';a=on=null}});
const box=document.createElement('div');box.id='box';box.innerHTML='<img alt=""><span></span>';document.body.appendChild(box);
document.querySelectorAll('.zoom').forEach(z=>z.onclick=ev=>{ev.preventDefault();box.firstChild.src=z.dataset.zoom;box.lastChild.textContent=z.dataset.cap||'';box.classList.add('on')});
box.onclick=()=>box.classList.remove('on');addEventListener('keydown',ev=>{if(ev.key==='Escape')box.classList.remove('on')});
const typing=()=>document.activeElement&&document.activeElement.classList.contains('note');
const every=RELOAD;if(every)setInterval(()=>{if(!document.hidden&&!a&&!box.classList.contains('on')&&!typing())location.reload()},every*1000);
"""
# The review page's buttons. On a claude.ai link the page holds the `db` capability: a tap is saved to the "answers" collection at once,
# and the session reads that collection back. Anywhere else (the local file, a copy) the answers stay in this browser and are copied out by hand.
REVIEW_JS = """
(()=>{const cards=[...document.querySelectorAll('.card[data-key]')],dock=document.getElementById('dock');if(!cards.length||!dock)return;
let A={},DB=null;try{A=JSON.parse(localStorage.getItem('kit-review')||'{}')}catch(_){}
const keep=()=>{try{localStorage.setItem('kit-review',JSON.stringify(A))}catch(_){}};
const here=k=>cards.some(c=>c.dataset.key===k);
function paint(){cards.forEach(c=>{const v=A[c.dataset.key];c.classList.toggle('done',!!(v&&v.pick));
 c.querySelectorAll('.opt').forEach(b=>b.classList.toggle('on',!!v&&v.pick===b.dataset.pick));
 const n=c.querySelector('.note');if(n&&v&&document.activeElement!==n)n.value=v.note||'';
 const s=c.querySelector('.state');if(s)s.textContent=!v?'':v.failed?'not saved — '+v.failed:DB?(v.saved?'saved ✓':'saving…'):''});
 dock.querySelector('b').textContent=Object.keys(A).filter(k=>here(k)&&A[k].pick).length+' / '+cards.length;
 dock.querySelector('.how').textContent=DB?'Saved for Claude':'Copy, then paste in the chat';
 dock.querySelector('.copy').hidden=!!DB}
function text(){return cards.map(c=>{const v=A[c.dataset.key];return v&&(v.pick||v.note)?c.dataset.label+' → '+(v.pick||'')+(v.note?' — '+v.note:''):''}).filter(Boolean).join('\\n')}
async function save(k){keep();paint();if(!DB)return;const v=A[k];
 try{await DB.doc('answers/'+k).set({key:k,pick:v.pick||'',note:v.note||'',at:Date.now()});v.saved=true;v.failed=''}catch(err){v.saved=false;v.failed=(err&&err.code)||'error'}paint()}
cards.forEach(c=>{const k=c.dataset.key;
 c.querySelectorAll('.opt').forEach(b=>b.onclick=()=>{A[k]=Object.assign(A[k]||{},{pick:b.dataset.pick,saved:false});save(k)});
 const n=c.querySelector('.note');if(n){let t=0;n.oninput=()=>{A[k]=Object.assign(A[k]||{pick:''},{note:n.value,saved:false});clearTimeout(t);t=setTimeout(()=>save(k),700)}}});
dock.querySelector('.copy').onclick=ev=>{const t=text(),b=ev.target;const show=()=>{let o=dock.querySelector('.out');if(!o){o=document.createElement('textarea');o.className='note out';o.readOnly=true;dock.appendChild(o)}o.value=t;o.focus();o.select()};
 try{navigator.clipboard.writeText(t).then(()=>b.textContent='Copied ✓',show)}catch(_){show()}};
paint();
(async()=>{const c=window.claude;if(!c||!c.use)return;const db=await c.use('db').catch(()=>null);if(!db)return;DB=db;paint();
 db.collection('answers').onSnapshot(s=>{s.docs.forEach(d=>{const v=d.data();if(v&&v.key&&here(v.key))A[v.key]={pick:v.pick,note:v.note,saved:true}});keep();paint()},()=>{})})();})();
"""
# The bundle for a link holds every page in one document (a page's capabilities reach that page only). Links become #names that the page
# switches itself on a tap — the viewer around the link does not pass in-page navigation through, so nothing may depend on the address changing.
ROUTER_JS = """
const P=[...document.querySelectorAll('.page[data-page]')];
function show(name){const hit=P.find(p=>p.dataset.page===name)||P[0];P.forEach(p=>p.hidden=p!==hit);scrollTo(0,0)}
document.addEventListener('click',ev=>{const a=ev.target.closest('a[href^="#"]');if(!a)return;ev.preventDefault();
 document.documentElement.classList.add('still');show(decodeURIComponent(a.getAttribute('href').slice(1)))});
show(decodeURIComponent(location.hash.slice(1))||P[0].dataset.page);
"""
HEAD = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
# The cards rise and the rings fill once — not again on every self-reload or page switch, where it reads as the page shaking
STILL = "<script>try{if(sessionStorage.getItem('kit-board-seen'))document.documentElement.classList.add('still');sessionStorage.setItem('kit-board-seen','1')}catch(_){}</script>"


def shell(title, body):
    return (f'{HEAD}<title>{e(title)}</title><style>{CHART_CSS}</style>{STILL}<div class="page">{body}</div>'
            f'<script>{CHART_JS.replace("RELOAD", str(int(CFG["reload_sec"])))}{REVIEW_JS}</script></html>\n')


def bundle(pages, first, title):
    """Every page in one document, for the link. Links between pages turn into #names; nothing reloads — the link is redrawn by publishing again."""
    css = re.sub(r'@import url\("[^"]*"\);', "", CHART_CSS)  # a published page loads styles from Google Fonts only — the system font stands in
    order = [first] + [n for n in pages if n != first]
    body = "".join(f'<div class="page" data-page="{n}"{"" if n == first else " hidden"}>'
                   + re.sub(r'href="((?:index|assets|review|stage-\d+)\.html)"', r'href="#\1"', pages[n][1]) + "</div>" for n in order)
    # No doctype or head of its own: the link wraps the page in its skeleton (charset, viewport, safe-area padding) when it is published
    return (f'<title>{e(title)}</title><style>{css}</style>{body}'
            f'<script>{ROUTER_JS}{CHART_JS.replace("RELOAD", "0")}{REVIEW_JS}</script>\n')


def lane_rows(s):
    out = []
    for lane in LANES:
        items = s["lanes"][lane]
        done = sum(1 for i in items if i["st"] == "done")
        out.append(f'<div class="lane"><span>{LANE_LABEL[lane]}</span>{meter(items)}<em>{f"{done}/{len(items)}" if items else "none"}</em></div>')
    return "".join(out)


def ask_href(q):
    return "review.html" if q["from"].startswith("Cycle") else "stage-%d.html" % (q["stage"] + 1)


def stray_of(st):
    """How many things fit no stage — they are outside the %, so they are shown apart or they get missed. (all, the assets among them)"""
    lanes = st[-1]["lanes"]
    return sum(len(v) for v in lanes.values()), len(lanes["art"]) + len(lanes["sound"])


def index_html(name, st, asks, now, stamp, sheet, review):
    flow = [s for s in st if not s["common"]]
    stray, stray_assets = stray_of(st)
    everything = [i for s in st for lane in LANES for i in s["lanes"][lane]]
    c = tally(everything)
    pcts = [p for p in (stage_pct(s) for s in flow) if p is not None]
    total = round(sum(pcts) / len(pcts)) if pcts else 0
    tiles = [("gold", "Complete", f"{total}%"), (("warn" if stray else "") + " minor", f'{CFG["common"]} · outside %', stray),
             ("", "Now", f'{now["num"]} · {stage_word(now["stage"])}' if now else "—"), ("minor", "Placeholders", c["temp"]),
             ("minor", "Not made", c["none"]), ("red" if c["bad"] else "", "Problems", c["bad"]), ("red" if asks else "", "Undecided", len(asks))]
    cards = []
    for s in flow:
        p, items = stage_pct(s), [i for lane in LANES for i in s["lanes"][lane]]
        t, pic = tally(items), hero_of(s)
        chips = "".join(f'<span class="chip{cls}">{label} {n}</span>' for label, n, cls in
                        (("Problem", t["bad"], " bad"), ("Not made", t["none"], ""), ("Placeholder", t["temp"], ""), ("Undecided", len(s["open"]), " bad")) if n)
        cls = " warn" if t["bad"] else " low" if (p or 0) < 50 else ""
        cards.append(
            f'<div class="slot" style="--i:{s["i"]}"><a class="node{cls}" href="stage-{s["i"] + 1}.html">'
            + (f'<div class="hero" style="background-image:url({pic})"></div>' if pic else '<div class="hero none"></div>')
            + f'<span class="ghost">{s["i"] + 1:02d}</span>{ring(p)}<div class="body"><span class="lab">{stage_label(s)}</span>'
            f'<h2>{e(s["name"])}</h2><p>{e(s["about"])}</p>{lane_rows(s)}<div class="chips">{chips}<span class="chip go">Details →</span></div></div></a></div>')
    loops = [s["i"] for s in flow if s["loop"]]
    loop = (f'<div class="loop" style="--a:{loops[0]};--c:{loops[-1] - loops[0] + 1}"><span class="lab">{e(str(CFG.get("loop_label", "loop")))}</span></div>'
            if loops else "")
    shown = asks[:6]
    strip = "".join(f'<a class="ask" href="{ask_href(q)}">'
                    f'<b>{md(q["title"])}</b><span>{md(q["text"]) or "&nbsp;"}</span></a>' for q in shown)
    strip += f'<span class="ask more">+{len(asks) - len(shown)}</span>' if len(asks) > len(shown) else ""
    rest = st[-1]
    rest_html = (f'<a class="rest" href="stage-{rest["i"] + 1}.html"><span class="lab">In no stage — not counted in the %</span>'
                 f'<b>{e(rest["name"])} {stray}</b><span>assets {stray_assets}</span>{lane_rows(rest)}'
                 f'<span class="chip go" style="margin-left:auto">Details →</span></a>') if any(rest["lanes"].values()) or rest["open"] else ""
    outside = f" · of these, {e(CFG['common'])} {stray} (assets {stray_assets}) is outside the %" if stray else ""  # 3.9 cannot reuse the same quote inside an f-string
    body = (f'<header><div><div class="lab">Chart · in the order the player meets it</div><h1>{e(name)} <span>to completion</span></h1>'
            f'<div class="sub">{len(everything)} things the player meets — done {c["done"]} · placeholder {c["temp"]} · not made {c["none"]} · problem {c["bad"]}{outside}</div></div>'
            '<div class="tiles">' + "".join(f'<div class="tile {cls}"><span class="lab">{k}</span><b>{e(str(v))}</b></div>' for cls, k, v in tiles) + review_link(review) + sheet_link(sheet) + table_link() + "</div></header>"
            '<div class="total">' + "".join(f'<div style="flex:1" title="{e(s["name"])}"><i style="width:{stage_pct(s) or 0}%"></i></div>' for s in flow) + "</div>"
            '<div class="legend"><span><i class="s-done"></i>Done</span><span><i class="s-temp"></i>Placeholder — works, to be remade</span>'
            '<span><i class="s-none"></i>Not made</span><span><i class="s-bad"></i>Problem · undecided</span></div>'
            + (f'<div><div class="lab" style="color:var(--red2);margin-bottom:5px">Undecided {len(asks)}</div><div class="asks">{strip}</div></div>' if asks else "")
            + f'<div class="flow" style="--n:{len(flow) or 1}">{loop}{"".join(cards)}</div>{rest_html}'
            f'<footer><span>Drawn {stamp} · every state is read as written in the GDD table · asset records · cycle · playtest documents</span>'
            '</footer>')
    return (f"{name} — chart", body), total


def it_html(i):
    tags = "".join(f'<span class="tag">{e(t)}</span>' for t in i["tags"])
    play = f'<button class="play" data-src="{rel(i["audio"])}">▶</button>' if i["audio"] else ""
    head = f'<code>{e(i["code"])}</code> ' if i["code"] else ""
    return (f'<li class="it st-{i["st"]}"><i class="s-{i["st"]}" title="{WORD[i["st"]]}"></i>{play}<div class="t">{head}<b>{md(i["title"])}</b>{tags}'
            + (f'<small>{e(" · ".join(x for x in (i["sub"], i["note"]) if x))}</small>' if i["sub"] or i["note"] else "") + "</div></li>")


def col_html(lane, items):
    items = sorted(items, key=lambda i: ORDER.index(i["st"]))
    done = sum(1 for i in items if i["st"] == "done")
    head = f'<h3>{LANE_LABEL[lane]}<small>{f"{done}/{len(items)}" if items else "none"}</small></h3>{meter(items)}'
    if not items:
        return f'<section class="col">{head}<p class="sub">Nothing read for this stage.</p></section>'
    if lane == "art":
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
        body += inner if len(rest) <= 10 and not todo else f'<details{"" if todo or len(rest) > 14 else " open"}><summary>Show {len(rest)} done</summary>{inner}</details>'
    return f'<section class="col">{head}{body}</section>'


def design_block(tag):
    """The text between `<!-- tag -->` and `<!-- /tag -->` in the design document."""
    text = read(os.path.join(ROOT, CFG["design"]))
    a, b = f"<!-- {tag} -->", f"<!-- /{tag} -->"
    return text.split(a, 1)[1].split(b, 1)[0].strip() if a in text and b in text else ""


def sheet_data():
    """What goes on the asset sheet — one per asset record (asset.json · sprite.json · sound.json). The board only reads the records."""
    gdir = os.path.join(ROOT, CFG["gen"])
    style = " ".join(design_block("asset-style").split())
    mark = hashlib.sha1(style.encode()).hexdigest()[:8]
    refs = (load_json(os.path.join(ROOT, CONFIG_NAME)) or {}).get("asset", {}).get("refs", [])  # the art style sample images (config of the asset skill)
    models, sounds = [], []
    for name in sorted(os.listdir(gdir)) if os.path.isdir(gdir) else []:
        for fn, sides in (("asset.json", ("front", "left", "right", "back")), ("sprite.json", ("still",))):
            rec = load_json(os.path.join(gdir, name, fn))
            if not isinstance(rec, dict):
                continue
            views = [os.path.join(gdir, name, f"{v}.png") for v in sides]
            front = next((p for p in views if os.path.exists(p)), "")
            placed = bool(rec.get("out")) and os.path.exists(os.path.join(ROOT, rec["out"]))
            drawn = (rec.get("image") or {}).get("style") or ""
            first = next(iter((rec.get("prompts") or {}).values()), "")
            # Was it drawn under a different art style than the current one — by the recorded mark; for older records, by whether that prompt holds the current paragraph
            old = bool(style) and not rec.get("as_is") and (drawn != mark if drawn else bool(first) and style not in first)
            here = os.path.abspath(front) if front else ""
            models.append({"name": name, "img": front, "tool": fn.split(".")[0], "views": [p for p in views if os.path.exists(p)],
                           "st": "done" if placed else "temp" if rec.get("approved") else "none",
                           "state": "in the game" if placed else "approved" if rec.get("approved") else "image only" if front else "no image",
                           "old": old, "ref": bool(here) and any(os.path.abspath(os.path.join(ROOT, r)) == here for r in refs),
                           "from": rec.get("ref") or "", "said": rec.get("said") or [], "what": rec.get("subject", "")})
        rec = load_json(os.path.join(gdir, name, "sound.json"))
        if isinstance(rec, dict) and rec.get("out") and os.path.exists(os.path.join(ROOT, rec["out"])):
            sub = " · ".join(x for x in (rec.get("kind", ""), f'{rec["seconds"]:g}s' if rec.get("seconds") else "") if x)
            sounds.append(item("done", name, sub, rec.get("subject", ""), audio=os.path.join(ROOT, rec["out"])))
    # Things in the game without a record (pictures · models · sounds put in by hand) go on too — off the sheet, they are missed when judging consistency
    adir, loose = os.path.join(ROOT, CFG["assets"]), []
    recs = [r for n in (os.listdir(gdir) if os.path.isdir(gdir) else []) for fn in ("asset.json", "sprite.json", "sound.json")
            for r in [load_json(os.path.join(gdir, n, fn))] if isinstance(r, dict)]
    known = {os.path.abspath(os.path.join(ROOT, x["out"])) for r in recs  # a sprite has one more sheet per motion
             for x in [r, *(r.get("motions") or {}).values()] if isinstance(x, dict) and x.get("out")}
    names = {m["name"] for m in models}
    for base, _dirs, files in os.walk(adir):
        if os.path.abspath(base).startswith(os.path.abspath(gdir)):
            continue
        beside = [f.split(".")[0] for f in files if f.lower().endswith(MODEL_EXT)]  # the models in this folder
        for fn in sorted(files):
            path, stem, low = os.path.join(base, fn), fn.split(".")[0], fn.lower()
            if os.path.abspath(path) in known or fn.endswith(".import"):
                continue
            if low.endswith(IMG_EXT) and any(stem.startswith(m + "_") for m in beside):
                continue  # a texture unpacked beside a model under its name — not an asset of its own
            if low.endswith(SOUND_EXT):
                sounds.append(item("done", stem, "no record", os.path.relpath(path, ROOT), audio=path))
            elif low.endswith(IMG_EXT + MODEL_EXT) and stem not in names:
                loose.append({"name": fn, "img": path if low.endswith(IMG_EXT) else "", "tool": "", "views": [], "st": "done", "state": "no record", "old": False, "ref": False,
                              "from": "", "said": [], "what": os.path.relpath(path, ROOT)})
    return {"loose": loose, "style": style, "world": " ".join(design_block("asset-world").split()),
            "learned": [re.sub(r"^[-*]\s*", "", x.strip()) for x in design_block("asset-learned").split("\n") if x.strip()],
            "sound": " ".join(design_block("sound-style").split()),
            "refs": [os.path.join(ROOT, r) for r in refs if os.path.exists(os.path.join(ROOT, r))], "models": models, "sounds": sounds}


def sheet_tile(m):
    said = " / ".join(s["said"] for s in m["said"])
    chips = (f'<span class="chip">{m["state"]}</span>' + ('<span class="chip bad">old style</span>' if m["old"] else "")
             + ('<span class="chip go" style="margin-left:0">sample</span>' if m["ref"] else "")
             + ('<span class="chip">reference</span>' if m["from"] else "")
             + (f'<span class="chip bad" title="{e(said)}">rejected {len(m["said"])}</span>' if m["said"] else ""))
    pic = (f'<button class="im zoom" data-zoom="{rel(m["img"])}" data-cap="{e(m["name"])}" style="background-image:url({rel(m["img"])})"></button>'
           if m["img"] else '<div class="im">no image</div>')
    return (f'<div class="thumb st-{m["st"]}" title="{e(m["what"])}"><i class="s-{m["st"]}"></i>{pic}<span>{e(m["name"])}</span>'
            f'<div class="chips" style="padding:0 6px 6px">{chips}</div></div>')


def sheet_html(name, d):
    """Asset sheet — every asset side by side on one screen. Consistency only shows side by side."""
    old = sum(1 for m in d["models"] if m["old"])
    refs = "".join(f'<div class="thumb"><button class="im zoom" data-zoom="{rel(r)}" data-cap="sample" style="background-image:url({rel(r)})"></button>'
                   f'<span>{e(os.path.basename(r))}</span></div>' for r in d["refs"])
    learned = "".join(f'<li class="it"><div class="t">{e(x)}</div></li>' for x in d["learned"])
    none = '<p class="sub" style="margin:0 0 6px">None.</p>'

    def rule(title, text, empty):
        return f'<h4>{title}</h4><p class="sub" style="margin:0 0 6px">{e(text) if text else empty}</p>'

    wide = 'style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))"'
    grid = (f'<div class="thumbs" {wide}>{"".join(map(sheet_tile, d["models"]))}</div>' if d["models"] else '<p class="sub">No asset records.</p>')
    if d["loose"]:
        grid += (f'<h3 style="margin-top:16px">In the game without a record<small>{len(d["loose"])}</small></h3>'
                 f'<div class="thumbs" {wide}>{"".join(map(sheet_tile, d["loose"]))}</div>')
    body = ('<div class="bar"><a class="btn" href="index.html">← Chart</a><a class="btn rv" href="review.html">Review →</a></div>'
            f'<div class="banner"><div><div class="lab">Asset sheet · side by side</div><h1>{e(name)}</h1>'
            f'<div class="sub">models · images {len(d["models"])} · sounds {len(d["sounds"])}'
            + (f' · <b style="color:var(--red2)">drawn in an old style {old}</b>' if old else "") + "</div></div></div>"
            '<div class="under"><section class="col"><details class="basis"><summary><h3>Basis<small>attached to every asset</small></h3></summary>'
            + rule("Art style — fixed", d["style"], "Empty. Set it before making the first asset.") + rule("World — what exists", d["world"], "None.")
            + f'<h4>Learned — said when rejecting {len(d["learned"])}</h4>' + (f"<ul>{learned}</ul>" if learned else none)
            + rule("Sound style", d["sound"], "None.")
            + (f'<h4>Samples {len(d["refs"])}</h4><div class="thumbs">{refs}</div>' if refs else "") + "</details></section>"
            f'<section class="col"><h3>Models · images<small>{len(d["models"])}</small></h3>{grid}'
            f'<h3 style="margin-top:16px">Sounds<small>{len(d["sounds"])}</small></h3>'
            + (f'<ul>{"".join(map(it_html, d["sounds"]))}</ul>' if d["sounds"] else '<p class="sub">None.</p>') + "</section></div>")
    return f"Asset sheet · {name}", body


def sheet_link(d):
    if not d["models"] and not d["sounds"] and not d["loose"]:
        return ""
    old = sum(1 for m in d["models"] if m["old"])
    return (f'<a class="tile go" href="assets.html"><span class="lab">models · images {len(d["models"])} · sounds {len(d["sounds"])}'
            + (f" · old style {old}" if old else "") + (f' · no record {len(d["loose"])}' if d["loose"] else "") + "</span><b>Asset sheet →</b></a>")


def table_files():
    """(the balance table, the value file) — the paths the balance-table skill keeps in its section of the config. This script only looks at the files."""
    section = (load_json(os.path.join(ROOT, CONFIG_NAME)) or {}).get("balance-table", {})
    return os.path.join(ROOT, section.get("table") or "data/balance.xlsx"), os.path.join(ROOT, section["code"]) if section.get("code") else ""


def table_link():
    """The tile that opens the balance table. A table the balance-table script wrote carries the value file's time, so equal times say the two are in step.
    Unequal times say nothing sure — an edit in the spreadsheet, a table from a kit that did not stamp it, and a fresh clone all look alike — so the tile claims nothing then."""
    table, code = table_files()
    if not os.path.isfile(table) or SHARED is not None:  # a spreadsheet does not open from the link
        return ""
    said = "the game's numbers"
    if code and os.path.isfile(code):
        said = "in step with the value file" if os.stat(table).st_mtime_ns == os.stat(code).st_mtime_ns else said
    return f'<a class="tile go" href="{rel(table)}"><span class="lab">{said}</span><b>Balance table →</b></a>'


def stage_html(name, s, st):
    p, pic = stage_pct(s), hero_of(s)
    tabs = "".join(f'<a class="btn{" on" if x is s else ""}" href="stage-{x["i"] + 1}.html">{x["i"] + 1:02d} {e(x["name"])}</a>'
                   for x in st if not x["common"] or any(x["lanes"].values()) or x["open"])
    tiles = "".join(f'<div class="tile"><span class="lab">{LANE_LABEL[lane]}</span><b>{"—" if score(s["lanes"][lane]) is None else str(round(score(s["lanes"][lane]) * 100)) + "%"}</b></div>'
                    for lane in LANES)
    asks = "".join(f'<div class="ask" style="margin-bottom:6px"><b style="white-space:normal">{md(q["title"])}</b>'
                   f'<span style="white-space:normal">{md(q["text"])} <em class="lab">{e(q["from"])}</em></span></div>' for q in s["open"])
    mark = {"x": "", "!": " blocked"}
    work = "".join(f'<h4>Cycle {e(c["num"])} — {e(c["name"])} · {e(stage_word(c["stage"]))}</h4>'
                   + "".join(f'<span class="task{mark.get(t["mark"], " open")}" title="{e(t["did"])}"><b>{t["num"]}</b> {e(t["title"])}</span>' for t in ts)
                   for c, ts in reversed(s["work"]))
    body = (f'<div class="bar"><a class="btn" href="index.html">← Chart</a><a class="btn go" href="assets.html">Asset sheet →</a><a class="btn rv" href="review.html">Review →</a><div class="tabs">{tabs}</div></div>'
            f'<div class="banner">' + (f'<button class="pic zoom" data-zoom="{pic}" data-cap="{e(s["name"])}" style="background-image:url({pic})"></button>' if pic else "") + ring(p, "big")
            + f'<div><div class="lab">{stage_label(s, "Stage ")}</div><h1>{e(s["name"])}</h1><div class="sub">{e(s["about"])}</div></div>'
            f'<div class="tiles">{tiles}</div></div>'
            f'<div class="cols">{"".join(col_html(lane, s["lanes"][lane]) for lane in LANES)}</div>'
            '<div class="under">'
            f'<section class="col"><h3 style="color:var(--red2)">Undecided<small>{len(s["open"])}</small></h3>{asks or "<p class=sub>None.</p>"}</section>'
            f'<section class="col"><h3>Tasks that touched this stage</h3>{work or "<p class=sub>None.</p>"}</section></div>')
    return f'{s["name"]} · {name} — chart', body


# ── Review — what waits on the user, one button per answer ───────────
#
# Every item has a key that changes when what is asked changes (the cycle and decision number, the image's content, the check's words),
# so an answer saved for an earlier version of a question never answers the new one.

MARKS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ"
CHECK_HEADS = r"^###\s+(?:To see by playing|For a human to see)[ \t]*$"


def short(text):
    return hashlib.sha1(text.encode()).hexdigest()[:8]


def png_size(path):
    head = open(path, "rb").read(24)
    return struct.unpack(">II", head[16:24]) if head[:8] == b"\x89PNG\r\n\x1a\n" else None


def sheet_questions():
    """Decision id → the latest question file entry the cycle's sheet script kept (its options and the pictures to compare)."""
    d = os.path.join(ROOT, CFG["sheets"])
    files = sorted((os.path.join(d, n) for n in os.listdir(d) if n.endswith(".json")), key=os.path.getmtime) if os.path.isdir(d) else []
    out = {}
    for path in files:
        for q in load_json(path) if isinstance(load_json(path), list) else []:
            if isinstance(q, dict) and q.get("id"):
                out[str(q["id"])] = q
    return out


def split_options(text):
    """`① Keep it — free ② Raise it — two clips` → [(①, Keep it — free), (②, Raise it — two clips)]."""
    return [(m, t.strip(" ·;,")) for m, t in re.findall(rf"([{MARKS}])\s*([^{MARKS}]*)", text)]


def check_lines(path):
    """The lines under the spec's "To see by playing" and the design's "For a human to see" — what to check by playing."""
    text, out = read(path), []
    for m in re.finditer(CHECK_HEADS, text, re.M):
        nxt = re.search(r"^#{1,3} ", text[m.end():], re.M)
        block = text[m.end():m.end() + nxt.start() if nxt else len(text)]
        lines = [x.strip() for x in block.split("\n") if x.strip() and not x.strip().startswith(("<!--", "|"))]
        bullets = [re.sub(r"^(?:[-*]|\d+[.)])\s+", "", x) for x in lines if re.match(r"^(?:[-*]|\d+[.)])\s+", x)]
        out += bullets or lines
    return out


def review_items(cycles, sheet):
    items = []
    c = cycles[-1] if cycles else None
    if c:
        pics = sheet_questions()
        for d in c["decisions"]:
            if d["done"]:
                continue
            q = pics.get(d["num"], {})
            opts = [(str(o.get("mark", "")), str(o.get("text", ""))) for o in q.get("options", []) if isinstance(o, dict)] or split_options(d["options"])
            rec = next((str(o.get("mark")) for o in q.get("options", []) if isinstance(o, dict) and o.get("recommend")), d["pick"])
            items.append({"key": f'c{c["num"]}-{d["num"]}', "kind": "decision", "ref": d["num"], "cycle": c["num"], "title": d["title"],
                          "who": d["who"], "options": opts, "recommend": rec, "proxy": re.sub(r"\s*· (?:proxy|대리) .*$", "", d["answer"]) if d["proxy"] else "",
                          "pictures": [i for i in q.get("images", []) if isinstance(i, dict)]})
    for m in sheet["models"]:
        if m["state"] == "image only" and m["views"]:
            stamp = short("".join(hashlib.sha1(open(p, "rb").read()).hexdigest() for p in m["views"]))
            items.append({"key": f'{m["tool"]}-{m["name"]}-{stamp}', "kind": "asset", "ref": m["name"], "tool": m["tool"],
                          "title": m["name"], "what": m["what"], "views": m["views"], "said": m["said"], "old": m["old"]})
    if c and re.match(STAGE_PLAY, c["stage"]):
        for line in check_lines(os.path.join(ROOT, CFG["cycles"], c["file"])):
            items.append({"key": f'c{c["num"]}-chk-{short(line)}', "kind": "check", "ref": line, "cycle": c["num"], "title": line})
    return items


def picture(img):
    """One comparison picture of a decision, cropped as the agent that raised it asked."""
    path = os.path.join(ROOT, str(img.get("path", "")))
    cap = f'<figcaption>{e(str(img.get("label", "")))}</figcaption>'
    if not os.path.isfile(path):
        return f'<figure>{cap}<div class="im"></div></figure>'
    src, crop = rel(path), img.get("crop")
    size = png_size(path) if crop else None
    try:
        x, y, w, h = (float(v) for v in crop) if size else (0, 0, 0, 0)
    except (TypeError, ValueError):
        size = None
    if not size or w <= 0 or h <= 0:
        return f'<figure>{cap}<button class="im zoom" data-zoom="{src}" data-cap="{e(str(img.get("label", "")))}" style="background-image:url({src})"></button></figure>'
    pct = lambda v, of: f"{100 * v / of:.4f}%"
    return (f'<figure>{cap}<div class="crop zoom" data-zoom="{src}" style="aspect-ratio:{w:g}/{h:g}">'
            f'<img alt="" src="{src}" style="width:{pct(size[0], w)};left:-{pct(x, w)};top:-{pct(y, h)}"></div></figure>')


def card(i):
    """One question, kept short — it is read on a phone."""
    label = {"decision": lambda: f'{i["ref"]}', "asset": lambda: f'asset {i["ref"]}', "check": lambda: f'check “{i["ref"][:40]}”'}[i["kind"]]()
    head = f'<div class="card" data-key="{e(i["key"])}" data-label="{e(label)}">'
    note = '<textarea class="note" rows="1" placeholder="{}"></textarea><div class="state"></div></div>'
    if i["kind"] == "decision":
        chose = next((ch for ch in i["proxy"] if ch in MARKS), "")
        opts = "".join(f'<button class="opt" data-pick="{e(m)}"><b>{e(m)}</b><span>{md(t)}</span>'
                       + ('<em>for you</em>' if chose and m == chose else '<em>recommended</em>' if m and m == i["recommend"] else "") + "</button>"
                       for m, t in i["options"])
        if i["proxy"]:
            opts = f'<button class="opt" data-pick="accept"><b>✓</b><span>Accept {e(chose or i["proxy"])}</span></button>' + opts
        figs = "".join(picture(p) for p in i["pictures"])
        tag = " · ".join(x for x in (i["who"], "decided for you" if i["proxy"] else "") if x)
        return (head + (f'<span class="lab">{e(tag)}</span>' if tag else "")
                + f'<h3><code>{e(i["ref"])}</code>{md(i["title"])}</h3>' + (f'<div class="figs">{figs}</div>' if figs else "")
                + f'<div class="opts">{opts}</div>' + note.format("Note (optional)"))
    if i["kind"] == "asset":
        figs = "".join(f'<figure><figcaption>{e(os.path.splitext(os.path.basename(v))[0])}</figcaption>'
                       f'<button class="im zoom" data-zoom="{rel(v)}" data-cap="{e(i["ref"])}" style="background-image:url({rel(v)})"></button></figure>'
                       for v in i["views"])
        said = " / ".join(x.get("said", "") for x in i["said"] if isinstance(x, dict))
        return (head + f'<span class="lab">{"3D model" if i["tool"] == "asset" else "sprite"}{" · old style" if i["old"] else ""}</span>'
                f'<h3>{e(i["title"])}</h3>' + (f'<div class="sub clamp">{e(i["what"])}</div>' if i["what"] else "")
                + (f'<div class="was clamp">Turned down: {e(said)}</div>' if said else "") + f'<div class="figs">{figs}</div>'
                '<div class="opts pair"><button class="opt" data-pick="approve">Approve</button><button class="opt no" data-pick="redo">Redo</button></div>'
                + note.format("What is off?"))
    return (head + f'<h3>{md(i["title"])}</h3>'
            '<div class="opts pair"><button class="opt" data-pick="ok">OK</button><button class="opt no" data-pick="problem">Problem</button></div>'
            + note.format("What did you see?"))


def review_html(name, items, stamp):
    cyc = next((i["cycle"] for i in items if i.get("cycle")), "")
    groups = [("decision", f"Decisions · cycle {cyc}"), ("asset", "Assets to approve"), ("check", f"Check by playing · cycle {cyc}")]
    parts = "".join(f'<h2 style="margin:6px 0 0;font-size:18px">{title} <span class="lab">{n}</span></h2><div class="rvs">{"".join(card(i) for i in its)}</div>'
                    for kind, title in groups for its in [[i for i in items if i["kind"] == kind]] for n in [len(its)] if its)
    body = ('<div class="bar"><a class="btn" href="index.html">← Chart</a><a class="btn go" href="assets.html">Asset sheet →</a></div>'
            f'<div class="banner"><div><div class="lab">Review</div><h1>{e(name)}</h1>'
            f'<div class="sub">{len(items)} to answer</div></div></div>'
            + (parts or '<p class="sub">Nothing waits on you.</p>')
            + ('<div class="dock" id="dock"><span class="lab">answered</span><b>0</b><span class="how"></span><button class="btn copy">Copy answers</button></div>' if items else "")
            + f'<footer><span>Drawn {stamp}</span></footer>')
    return f"Review · {name}", body


def review_link(items):
    return f'<a class="tile go rv" href="review.html"><span class="lab">waiting on you</span><b>Review {len(items)} →</b></a>' if items else ""


def build(outdir, index_name):
    global OUTDIR
    OUTDIR = outdir
    name, titles, rows = gdd()
    cycles = [cycle(p) for p in cycle_docs()]
    playtests = [cycle(p) for p in playtest_docs()]
    live = [r for r in rows if r["state"] != "retired"]
    waiting = sum(1 for c in cycles for d in c["decisions"] if not d["done"])
    line = (f'GDD synced {sum(1 for r in live if r["state"] == "synced")}/{len(live)} · mismatched {sum(1 for r in live if r["state"] == "mismatch")}'
            f' · cycles {len(cycles)} · unanswered decisions {waiting}')
    st = make_stages(titles, rows)
    touched, where = {}, {}
    for c in cycles:
        for t in c["tasks"]:
            for i in t["ids"]:
                touched.setdefault(i, []).append(f'{c["num"]}·{t["num"]}')
    for r in rows:
        s = place_row(st, r)
        if r["state"] != "retired":
            where[r["id"]] = s["i"]
            s["lanes"]["function"].append(item({"synced": "done", "mismatch": "bad"}.get(r["state"], "none"), r["value"], r["note"], code=r["id"],
                                         tags=touched.get(r["id"], [])[-3:]))
    asset_items(st, where, cycles, [t for d in cycles + playtests for t in d["tasks"]])
    check_items(st, where, cycles, playtests)
    asks = open_questions(st, cycles)
    stamp = f"{datetime.datetime.now():%Y-%m-%d %H:%M}"
    sheet = sheet_data()
    review = review_items(cycles, sheet)
    index, total = index_html(name, st, asks, cycles[-1] if cycles else None, stamp, sheet, review)
    pages = {index_name: index, "assets.html": sheet_html(name, sheet), "review.html": review_html(name, review, stamp)}
    pages.update({f'stage-{s["i"] + 1}.html': stage_html(name, s, st) for s in st})
    stray, stray_assets = stray_of(st)
    return pages, review, (f"{line} · complete {total}%" + (f' · {CFG["common"]} {stray} (assets {stray_assets} — outside the %)' if stray else "")
                           + f" · review {len(review)}")


def sources():
    gen = os.path.join(ROOT, CFG["gen"])
    sheets = os.path.join(ROOT, CFG["sheets"])
    return ([os.path.join(ROOT, CFG["gdd"]), os.path.join(ROOT, CONFIG_NAME), os.path.join(ROOT, CFG["notes"]), os.path.join(ROOT, CFG["design"]), gen, sheets]
            + ([os.path.join(sheets, n) for n in os.listdir(sheets)] if os.path.isdir(sheets) else [])
            + [p for p in table_files() if p]
            + cycle_docs() + playtest_docs() + ([os.path.join(gen, n) for n in os.listdir(gen)] if os.path.isdir(gen) else []))


PART_FILES = 200            # files per publish — the link takes up to 255 in one go
PART_BYTES = 48 * 1024 * 1024  # and up to 64 MB


def setup(root):
    global ROOT, CFG
    ROOT = os.path.abspath(root) if root else find_root(os.getcwd())
    if not ROOT:
        raise RuntimeError(f"{CONFIG_NAME} not found — run this inside a game repository, after /gamedev-kit:init")
    whole = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8"))
    CFG = dict(DEFAULTS, **whole.get(SECTION, {}))
    if "gen" not in whole.get(SECTION, {}) and whole.get("asset", {}).get("work"):
        CFG["gen"] = whole["asset"]["work"]  # follow the asset skill if it moved the asset records
    return whole


def keep_review(review):
    """What `answers` matches the tapped answers against — beside the board, whichever command drew the page."""
    folder = os.path.dirname(os.path.join(ROOT, CFG["out"]))
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "review.json"), "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in i.items() if k in ("key", "kind", "ref", "cycle", "tool", "proxy", "title")} for i in review], f, ensure_ascii=False, indent=1)


def draw(quiet):
    out = os.path.join(ROOT, CFG["out"])
    if quiet and not os.path.exists(out):
        return
    # Redraw when a source is newer, this script is newer (the kit bumped its version), or a page that should exist is missing
    newest = max(os.path.getmtime(p) for p in sources() + [os.path.abspath(__file__)] if os.path.exists(p))
    folder = os.path.dirname(out)
    if quiet and os.path.getmtime(out) >= newest and all(os.path.exists(os.path.join(folder, n)) for n in ("assets.html", "review.html")):
        return
    pages, review, line = build(folder, os.path.basename(out))
    os.makedirs(folder, exist_ok=True)
    old = os.path.join(folder, "log.html")  # a page 0.12.0 wrote — no longer drawn
    if os.path.exists(old):
        os.remove(old)
    for fn, (title, body) in pages.items():
        with open(os.path.join(folder, fn), "w", encoding="utf-8") as f:
            f.write(shell(title, body))
    keep_review(review)
    if not quiet:
        print(f"{os.path.relpath(out, ROOT)} — {line}")


def load_name():
    return gdd()[0]


def share(whole, done):
    """Bundles the board for the link. Files are named by their content, so only what is new since the last publish is sent."""
    global SHARED
    folder = os.path.join(ROOT, CFG["share_dir"])
    sent_path = os.path.join(folder, "sent.json")
    sent = set(load_json(sent_path) or [])
    if done:
        now = load_json(os.path.join(folder, "publish.json"))
        if not now:
            sys.exit("nothing bundled — run `board.py share` first, publish, then `share --done <url>`")
        json.dump(sorted(now["all"]), open(sent_path, "w", encoding="utf-8"))
        if whole.get(SECTION, {}).get("share") != done:
            whole.setdefault(SECTION, {})["share"] = done
            with open(os.path.join(ROOT, CONFIG_NAME), "w", encoding="utf-8") as f:
                json.dump(whole, f, ensure_ascii=False, indent=2)
                f.write("\n")
        print(f"shared: {done} — {len(now['all'])} files on the link")
        return
    SHARED = {}
    pages, review, line = build(folder, "index.html")
    keep_review(review)
    first = "review.html" if review else "index.html"
    os.makedirs(os.path.join(folder, "f"), exist_ok=True)
    with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
        f.write(bundle(pages, first, f"{load_name()} board"))
    new = sorted(p for p in SHARED if p not in sent)
    for pub in new:
        dst = os.path.join(folder, pub)
        if not os.path.exists(dst):
            shutil.copyfile(SHARED[pub], dst)
    for n in os.listdir(os.path.join(folder, "f")):  # copies already sent are not needed on disk
        if "f/" + n not in new:
            os.remove(os.path.join(folder, "f", n))
    parts, size = [{}], 0
    for pub in new:
        b = os.path.getsize(SHARED[pub])
        if parts[-1] and (len(parts[-1]) >= PART_FILES or size + b > PART_BYTES):
            parts.append({})
            size = 0
        parts[-1][pub] = pub
        size += b
    parts[-1].update({p: None for p in sorted(sent - set(SHARED))})  # no longer shown — dropped from the link
    total = sum(os.path.getsize(SHARED[p]) for p in new)
    rel_folder = os.path.relpath(folder, ROOT)
    json.dump({"page": os.path.join(rel_folder, "index.html"), "root": rel_folder, "url": CFG["share"] or None,
               "parts": [p for p in parts if p] or [{}], "all": sorted(SHARED), "new_bytes": total},
              open(os.path.join(folder, "publish.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{os.path.relpath(os.path.join(folder, 'publish.json'), ROOT)} — {line} · files new {len(new)} ({total / 1048576:.1f} MB)"
          f" · dropped {len(sent - set(SHARED))} · in {max(1, len([p for p in parts if p]))} publish(es)"
          + (f" · to {CFG['share']}" if CFG["share"] else " · first publish — new link"))


def rows_in(data):
    """The saved answers wherever they sit in what was read back — a list of rows, rows with a data field, or a map by id."""
    if isinstance(data, dict):
        if isinstance(data.get("key"), str) and "pick" in data:
            return [data]
        return [r for v in data.values() for r in rows_in(v)]
    if isinstance(data, list):
        return [r for v in data for r in rows_in(v)]
    return []


def answers(path):
    """Prints what each tapped answer asks for — and nothing for answers already relayed or to questions that have since changed."""
    folder = os.path.dirname(os.path.join(ROOT, CFG["out"]))
    items = {i["key"]: i for i in load_json(os.path.join(folder, "review.json")) or []}
    if os.path.isdir(path):  # the folder a read of the collection saved its documents into, one JSON file each
        data = [load_json(os.path.join(d, n)) for d, _dirs, names in os.walk(path) for n in sorted(names) if n.endswith(".json")]
    else:
        data = load_json(path)
    if data is None:
        sys.exit(f"{path}: could not read — save the rows of the \"answers\" collection as JSON")
    seen_path = os.path.join(folder, "answered.json")
    seen = load_json(seen_path) or {}
    groups, stale = {"decision": [], "asset": [], "check": []}, 0
    for r in rows_in(data):
        i, mark = items.get(r["key"]), f'{r.get("pick", "")}|{r.get("note", "")}'
        if not i:
            stale += 1
            continue
        if seen.get(r["key"]) == mark or not (r.get("pick") or r.get("note")):
            continue
        seen[r["key"]] = mark
        groups[i["kind"]].append((i, str(r.get("pick") or ""), " ".join(str(r.get("note") or "").split())))
    note = lambda n: f" — “{n}”" if n else ""
    out = []
    if groups["decision"]:
        out.append(f'Decisions (cycle {groups["decision"][0][0]["cycle"]}) — record each with the cycle skill (decide · confirm), as it does with answers from the chat:')
        for i, pick, n in groups["decision"]:
            was = f' (decided for you: {i["proxy"]})' if i.get("proxy") else ""
            what = "accept" if pick == "accept" else (f"overturn → {pick}" if i.get("proxy") and pick else pick or "(no option)")
            out.append(f'  {i["ref"]}{was} → {what}{note(n)}')
    if groups["asset"]:
        out.append("Assets — the asset skill: approve, or reject with the user's words:")
        out += [f'  {i["ref"]} ({"3D model — asset.py" if i.get("tool") == "asset" else "sprite — sprite.py"}) → {pick or "?"}{note(n)}' for i, pick, n in groups["asset"]]
    if groups["check"]:
        bad = [(i, n) for i, pick, n in groups["check"] if pick == "problem"]
        out.append(f'Checks by playing — {len(groups["check"]) - len(bad)} ok, {len(bad)} problem' + (" (hand the problems to the playtest skill as one list):" if bad else ""))
        out += [f'  ✗ {i["ref"]}{note(n)}' for i, n in bad]
    if stale:
        out.append(f"{stale} saved answer(s) are to questions no longer on the page (answered, or the question changed) — ignored")
    json.dump(seen, open(seen_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(out) if any(groups.values()) else "No new answers." + (f" ({out[-1]})" if stale else ""))


def main():
    args = sys.argv[1:]
    root = None
    if "--root" in args:  # for the tests
        i = args.index("--root")
        root = args[i + 1]
        del args[i:i + 2]
    quiet = args == ["--if-stale"]
    try:
        if not args or quiet:
            setup(root)
            draw(quiet)
        elif args[0] == "share" and (len(args) == 1 or (len(args) == 3 and args[1] == "--done")):
            share(setup(root), args[2] if len(args) == 3 else "")
        elif args[0] == "answers" and len(args) == 2:
            setup(root)
            answers(args[1])
        else:
            sys.exit(__doc__)
    except Exception as err:  # run by the hook, it never blocks the turn of the user, whatever happens
        if not quiet:
            sys.exit(str(err))


if __name__ == "__main__":
    main()
