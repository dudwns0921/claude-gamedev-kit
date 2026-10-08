#!/usr/bin/env python3
"""영상 — 대본에서 영상 파일까지: 컷 표(글자 · 초) → 승인 → 컴포지션(HTML, HyperFrames) → 렌더 → 게임 폴더나 문서 폴더.

  python3 video.py check                                   돌릴 수 있는가: Node · HyperFrames · FFmpeg · 영상의 결 문단
  python3 video.py new <이름> --for game|page [--size landscape|portrait|square] "<무슨 영상인지>"
  python3 video.py cuts <이름> [<파일>|-]                  컷 표를 정한다 (줄마다 `초 | 화면 글자 | 움직임`). 파일이 없으면 지금 표를 보여 준다
  python3 video.py approve <이름>                          사람이 컷 표를 보고 난 뒤. 승인한 표만 컴포지션이 된다
  python3 video.py compose <이름>                          컴포지션 폴더를 만들고(처음 한 번) 결 · 컷마다 시작 시각을 적어 준다
  python3 video.py lint <이름>                             컴포지션 검사 (브라우저 없이)
  python3 video.py frames <이름>                           컷 수만큼 정지 화면을 뽑는다 — 렌더 전에 눈으로 본다
  python3 video.py render <이름> [--draft]                 검사 → 렌더 → 쓰이는 곳에 놓는다
  python3 video.py status                                  영상마다 어디까지 왔는지

영상 하나가 폴더 하나다: <work>/<이름>/ 에 기록(video.json) · 컴포지션(comp/) · 렌더(renders/).
쓰이는 곳이 둘이다 — page 는 게임 밖(트레일러 · 페이지 · devlog)이라 mp4 그대로 <page.dir> 에,
game 은 게임 안에서 트는 것이라 엔진이 읽는 형식으로 바꿔(<game.convert> — ffmpeg 인자) <game.dir> 에 놓는다.

결은 한 곳에 있다 — video.style_file(기본 docs/DESIGN.md)의 `<!-- video-style -->` 와 `<!-- /video-style -->` 사이.
설정은 프로젝트 루트 kit.config.json 의 "video". 이 스크립트는 파일을 만들 뿐 어디에도 올리지 않는다.
"""
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

CONFIG_NAME = "kit.config.json"
SECTION = "video"
DEFAULTS = {
    "work": "video",                   # 영상마다 기록 · 컴포지션 · 렌더
    "style_file": "docs/DESIGN.md",
    "hyperframes": "npx hyperframes",  # 부르는 명령
    "ffmpeg": "ffmpeg",
    "size": "landscape",               # landscape | portrait | square
    "quality": "standard",             # hyperframes render --quality. --draft 면 draft
    "read_cps": 8,                     # 화면 글자를 읽는 속도(초당 글자). 이보다 빠듯한 컷을 알린다
    "page": {"dir": "docs/video"},
    "game": {"dir": "", "ext": "", "convert": []},  # 엔진이 트는 형식 — 엔진 설정이 채운다
}
SIZES = ("landscape", "portrait", "square")
OPEN, CLOSE = "<!-- video-style -->", "<!-- /video-style -->"

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


def setup(root=None):
    global ROOT, CFG
    ROOT = os.path.abspath(root) if root else find_root(os.getcwd())
    have = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get(SECTION, {})
    CFG = dict(DEFAULTS, **have)
    for key in ("page", "game"):  # 일부만 적어도 나머지는 기본값
        CFG[key] = dict(DEFAULTS[key], **have.get(key, {}))
    if CFG["size"] not in SIZES:
        sys.exit(f"{SECTION}.size 는 " + " · ".join(SIZES) + " 중 하나다")


def style():
    path = os.path.join(ROOT, CFG["style_file"])
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    m = re.search(re.escape(OPEN) + r"(.*?)" + re.escape(CLOSE), text, re.S)
    return " ".join(m.group(1).split()) if m else ""


def tool(key):
    """설정의 명령을 인자 목록으로. 첫 낱말이 실행 파일이다."""
    return shlex.split(CFG[key])


def hyperframes(*args, cwd=None, capture=False):
    env = dict(os.environ, HYPERFRAMES_SKIP_SKILLS="1")  # init 이 게임 저장소에 스킬을 깔지 않게
    return subprocess.run(tool("hyperframes") + list(args), cwd=cwd or ROOT, env=env, capture_output=capture, text=True)


def problems():
    bad = []
    node = shutil.which("node")
    if not node:
        bad.append("Node.js 가 없다 — HyperFrames 는 22 이상이 필요하다")
    else:
        m = re.match(r"v(\d+)", subprocess.run([node, "-v"], capture_output=True, text=True).stdout)
        if m and int(m.group(1)) < 22:
            bad.append(f"Node.js {m.group(1)} — HyperFrames 는 22 이상이 필요하다")
    for key, why in (("hyperframes", "컴포지션을 검사하고 렌더한다"), ("ffmpeg", "HyperFrames 가 영상으로 묶을 때와 게임용으로 바꿀 때 쓴다")):
        if not shutil.which(tool(key)[0]):
            bad.append(f"{tool(key)[0]} 가 없다 ({SECTION}.{key}) — {why}")
    if not style():
        bad.append(f"영상의 결이 비어 있다 — {CFG['style_file']} 의 `{OPEN}` 와 `{CLOSE}` 사이를 먼저 채운다")
    return bad


# ── 기록 ──────────────────────────────────────────────────────────────

def folder(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
        sys.exit(f"이름은 소문자 · 숫자 · 밑줄이다: {name!r}")
    return os.path.join(ROOT, CFG["work"], name)


def load(name):
    path = os.path.join(folder(name), "video.json")
    if not os.path.exists(path):
        sys.exit(f"{name}: 기록이 없다 — video.py new {name} --for game|page \"<무슨 영상인지>\"")
    return json.load(open(path, encoding="utf-8"))


def save(rec):
    os.makedirs(folder(rec["name"]), exist_ok=True)
    with open(os.path.join(folder(rec["name"]), "video.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")


def comp(name):
    return os.path.join(folder(name), "comp")


def stage(rec):
    if not rec.get("cuts"):
        return "컷 표 없음"
    if not rec.get("approved"):
        return "컷 표 승인 대기"
    if not os.path.exists(os.path.join(comp(rec["name"]), "index.html")):
        return "컴포지션 없음"
    if not rec.get("rendered"):
        return "렌더 안 함"
    return f"놓임 {rec['out']}" + (" (초안)" if rec["rendered"].get("draft") else "")


# ── 컷 표 ─────────────────────────────────────────────────────────────

def table(rec):
    """컷마다 시작 시각을 붙인 표. 컴포지션의 시간은 여기서만 나온다."""
    lines, at = [], 0.0
    for i, c in enumerate(rec.get("cuts", []), 1):
        tight = " ← 읽기 빠듯하다" if len(c["text"].replace(" ", "")) > c["sec"] * CFG["read_cps"] else ""
        lines.append(f"{i:>2}  {at:>5.1f}s +{c['sec']:g}s  {c['text'] or '(글자 없음)'}{tight}"
                     + (f"\n      움직임: {c['motion']}" if c["motion"] else ""))
        at += c["sec"]
    return "\n".join(lines + [f"모두 {at:g}초 · 컷 {len(lines)}개"])


def cuts(name, source):
    rec = load(name)
    if source is None:
        print(table(rec) if rec.get("cuts") else f"{name}: 컷 표가 없다 — 줄마다 `초 | 화면 글자 | 움직임`")
        return
    text = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
    new = []
    for n, line in enumerate((l.strip() for l in text.split("\n")), 1):
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        try:
            sec = float(parts[0])
            if sec <= 0 or len(parts) not in (2, 3):
                raise ValueError
        except ValueError:
            sys.exit(f"{n}번째 줄을 읽지 못했다 — `초 | 화면 글자 | 움직임` 이다 (움직임은 비워도 된다): {line!r}")
        new.append({"sec": sec, "text": parts[1], "motion": parts[2] if len(parts) == 3 else ""})
    if not new:
        sys.exit("컷이 하나도 없다")
    rec["cuts"] = new
    rec.pop("approved", None)  # 표가 바뀌면 다시 본다
    save(rec)
    print(table(rec) + "\n승인 대기 — 사용자가 이 표를 본 뒤 video.py approve " + name)


def approve(name):
    rec = load(name)
    if not rec.get("cuts"):
        sys.exit(f"{name}: 승인할 컷 표가 없다")
    rec["approved"] = str(datetime.date.today())
    save(rec)
    print(f"{name}: 컷 표 승인 — video.py compose {name}")


# ── 컴포지션 · 렌더 ───────────────────────────────────────────────────

def approved(name):
    rec = load(name)
    if not rec.get("approved"):
        sys.exit(f"{name}: {stage(rec)} — 승인한 컷 표만 컴포지션이 된다")
    return rec


def compose(name):
    rec = approved(name)
    index = os.path.join(comp(name), "index.html")
    if not os.path.exists(index):
        if hyperframes("init", "comp", "--non-interactive", "--resolution", rec["size"], cwd=folder(name)).returncode != 0 \
                or not os.path.exists(index):
            sys.exit(f"{name}: hyperframes init 실패 — video.py check")
    print(f"컴포지션: {os.path.relpath(index, ROOT)}\n무슨 영상: {rec['what']} ({rec['for']} · {rec['size']})\n결: {style()}\n\n{table(rec)}")


def lint(name):
    approved(name)
    if hyperframes("lint", comp(name)).returncode != 0:
        sys.exit(f"{name}: 검사에 걸렸다 — 고치고 다시")


def frames(name):
    rec = approved(name)
    if hyperframes("snapshot", comp(name), "--frames", str(len(rec["cuts"]))).returncode != 0:
        sys.exit(f"{name}: 정지 화면을 뽑지 못했다")
    shots = os.path.join(comp(name), "snapshots")
    for f in sorted(os.listdir(shots)) if os.path.isdir(shots) else []:
        print(os.path.relpath(os.path.join(shots, f), ROOT))


def render(name, draft):
    rec = approved(name)
    where = CFG[rec["for"]]
    ext = "mp4" if rec["for"] == "page" else where["ext"]
    if not where["dir"] or not ext or (rec["for"] == "game" and not where["convert"]):
        sys.exit(f"{CONFIG_NAME} 의 {SECTION}.{rec['for']} 가 덜 채워졌다 — dir" + (" · ext · convert" if rec["for"] == "game" else ""))
    lint(name)
    mp4 = os.path.join(folder(name), "renders", f"{name}.mp4")
    os.makedirs(os.path.dirname(mp4), exist_ok=True)
    if hyperframes("render", comp(name), "--output", mp4, "--quality", "draft" if draft else CFG["quality"]).returncode != 0 \
            or not os.path.exists(mp4):
        sys.exit(f"{name}: 렌더 실패")
    out = os.path.join(ROOT, where["dir"], f"{name}.{ext}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if rec["for"] == "page":
        shutil.copyfile(mp4, out)
    elif subprocess.run(tool("ffmpeg") + ["-y", "-i", mp4, *where["convert"], out], cwd=ROOT).returncode != 0 \
            or not os.path.exists(out):
        sys.exit(f"{name}: {ext} 로 바꾸지 못했다 — {SECTION}.game.convert 를 본다")
    rec["out"] = os.path.relpath(out, ROOT)
    rec["rendered"] = {"date": str(datetime.date.today()), "sec": sum(c["sec"] for c in rec["cuts"]), "draft": draft}
    save(rec)
    print(f"{name}: {rec['out']} — {rec['rendered']['sec']:g}초 · {os.path.getsize(out) / 1e6:.1f} MB"
          + (" · 초안 화질" if draft else "") + "\n움직임은 사용자가 본다 — 경로를 건넨다")


def status():
    work = os.path.join(ROOT, CFG["work"])
    names = sorted(n for n in os.listdir(work) if os.path.exists(os.path.join(work, n, "video.json"))) \
        if os.path.isdir(work) else []
    if not names:
        print("영상이 없다 — video.py new <이름> --for game|page \"<무슨 영상인지>\"")
    for n in names:
        rec = load(n)
        print(f"{n:<24} {stage(rec):<32} {rec['for']} · {sum(c['sec'] for c in rec.get('cuts', [])):g}초 · {rec['what'][:40]}")


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--for", "--size"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    draft = "--draft" in args
    args = [a for a in args if a != "--draft"]
    cmd, rest = (args[0] if args else ""), args[1:]
    want = {"check": 0, "status": 0, "new": 2, "cuts": (1, 2), "approve": 1, "compose": 1, "lint": 1, "frames": 1, "render": 1}
    n = want.get(cmd)
    if n is None or not (len(rest) in n if isinstance(n, tuple) else len(rest) == n):
        sys.exit(__doc__)
    setup(opts.get("--root"))
    if cmd == "check":
        bad = problems()
        if bad:
            sys.exit("영상을 만들 수 없다:\n- " + "\n- ".join(bad))
        print("만들 수 있다 — " + " · ".join(k for k in ("page", "game") if CFG[k]["dir"]))
    elif cmd == "status":
        status()
    elif cmd == "new":
        name, what = rest[0], rest[1].strip()
        size = opts.get("--size", CFG["size"])
        if opts.get("--for") not in ("game", "page") or size not in SIZES or not what:
            sys.exit(__doc__)
        if os.path.exists(os.path.join(folder(name), "video.json")):
            sys.exit(f"{name}: 이미 있다 — 다른 이름을 쓰거나 컷 표를 바꾼다 (video.py cuts {name} <파일>)")
        save({"name": name, "for": opts["--for"], "size": size, "what": what, "created": str(datetime.date.today())})
        print(f"{name}: {os.path.relpath(folder(name), ROOT)}/video.json")
    elif cmd == "cuts":
        cuts(rest[0], rest[1] if len(rest) == 2 else None)
    else:
        {"approve": approve, "compose": compose, "lint": lint, "frames": frames}.get(cmd, lambda x: render(x, draft))(rest[0])


if __name__ == "__main__":
    main()
