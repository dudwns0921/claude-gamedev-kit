#!/usr/bin/env python3
"""게임에 쌓인 "키트로 올릴 것"(docs/kit-feedback.md)을 키트 저장소의 이슈로 보낸다 — 배운 것이 키트로 돌아가는 길.

  python3 feedback.py list                 아직 안 보낸 줄을 번호와 함께 — 나갈 글 그대로 (날짜 · 사이클 번호는 뗀다)
  python3 feedback.py preview 1,3          나갈 이슈의 제목 · 본문과, 키트에 이미 열려 있는 비슷한 이슈. 아무것도 보내지 않는다 (`all` 은 전부)
  python3 feedback.py send 1,3             이슈를 새로 연다 (gh). gh 를 못 쓰면 내용이 채워진 "새 이슈" 주소를 준다
  python3 feedback.py send 2 --to 14       새로 열지 않고 이슈 #14 에 "여기서도 봤다" 를 단다
  python3 feedback.py sent 2 14            주소로 손수 올린 줄에 이슈 번호를 적는다
  python3 feedback.py skip 4 "<이유>"      보내지 않기로 한 줄 (이 게임만의 것이었다)
  python3 feedback.py --notice             세션이 시작될 때 훅이 부른다: 안 보낸 줄이 쌓였으면 한 줄

번호는 안 보낸 줄([ ])끼리 매긴다 — 보내거나 건너뛰면 당겨지니 다시 `list` 한다. 보낸 줄은 [>], 건너뛴 줄은 [-] 가 된다.
나가기 전에 이 게임의 것으로 보이는 낱말(저장소 폴더의 이름 · GDD 의 제목 · kit.config.json 의 feedback.private ·
보이스 폴더의 private-words.txt)과 날짜를 찾아, 있으면 멈춘다. `--as-is` 는 사용자가 그대로 보내라고 했을 때만 붙인다.

어디로 가는가: 플러그인 매니페스트의 repository (kit.config.json 의 feedback.repo 로 바꾼다). gh 의 자리는 feedback.gh.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

CONFIG_NAME = "kit.config.json"
FEEDBACK = os.path.join("docs", "kit-feedback.md")
PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                      ".claude-plugin", "plugin.json")
WEB = "https://github.com"
API = os.environ.get("GAMEDEV_KIT_GITHUB_API") or "https://api.github.com"
VOICE = os.path.expanduser(os.environ.get("GAMEDEV_KIT_VOICE") or "~/.config/gamedev-kit/voice")
OPEN_RE = re.compile(r"^- \[ \] (.*)$")
META_RE = re.compile(r"^\(([^)]*)\)\s*(.*)$")
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
WORD_RE = re.compile(r"[0-9A-Za-z_가-힣]{2,}")
NOTICE = 5  # 안 보낸 줄이 이만큼 쌓이면 세션이 시작될 때 알린다
NEAR = 0.25  # 낱말이 이만큼 겹치면 비슷한 이슈로 보여 준다 — 같은지는 읽는 쪽이 가린다

ROOT = ""


def find_root(start):
    """kit.config.json 이 있는 폴더를 지금 폴더에서 위로 올라가며 찾는다. 도구는 플러그인 안에 있고 게임은 밖에 있다."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def config():
    return json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8"))


def kit():
    """(이슈가 갈 저장소 `owner/name`, 키트의 판)"""
    plugin = json.load(open(PLUGIN, encoding="utf-8"))
    repo = config().get("feedback", {}).get("repo") or plugin["repository"]
    return repo.replace(WEB + "/", "").strip("/"), plugin["version"]


def lines():
    path = os.path.join(ROOT, FEEDBACK)
    return open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else []


def todo():
    """안 보낸 줄: [(파일의 줄 번호, 엔진, 나갈 글)]. 머리의 (엔진 · 사이클 · 날짜) 에서 엔진만 남긴다."""
    out = []
    for i, line in enumerate(lines()):
        m = OPEN_RE.match(line)
        if not m:
            continue
        meta = META_RE.match(m.group(1))
        engine = meta.group(1).split("·")[0].strip() if meta else config().get("engine", "?")
        out.append((i, engine, (meta.group(2) if meta else m.group(1)).strip()))
    return out


def pick(arg):
    """`1,3` · `all` → [(번호, (파일의 줄 번호, 엔진, 글))]"""
    items = todo()
    if arg == "all":
        return list(enumerate(items, 1))
    try:
        want = sorted({int(n) for n in arg.split(",")})
    except ValueError:
        sys.exit(f"{arg}: 번호는 `1,3` 이나 `all` 로 준다")
    if not want or not set(want) <= set(range(1, len(items) + 1)):
        sys.exit(f"번호가 없다 — 안 보낸 줄은 {len(items)}개다")
    return [(n, items[n - 1]) for n in want]


def mark(done):
    """{파일의 줄 번호: (상자, 꼬리)} 대로 줄을 바꾼다."""
    out = lines()
    for i, (box, tail) in done.items():
        out[i] = f"- [{box}] {OPEN_RE.match(out[i]).group(1)} — {tail}"
    with open(os.path.join(ROOT, FEEDBACK), "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def private():
    """이 게임의 것으로 보이는 낱말 — 공개 저장소로 나가면 안 되는 것."""
    words = [os.path.basename(ROOT)] + list(config().get("feedback", {}).get("private", []))
    gdd = os.path.join(ROOT, "docs", "GDD.md")
    if os.path.exists(gdd):
        head = open(gdd, encoding="utf-8").readline().lstrip("# ").split("—")[0].strip()
        if "<" not in head:
            words.append(head)
    mine = os.path.join(VOICE, "private-words.txt")
    if os.path.exists(mine):
        words += [w.strip() for w in open(mine, encoding="utf-8") if w.strip() and not w.startswith("#")]
    return sorted({w.lower() for w in words if len(w.strip()) >= 3})


def leaks(text, block):
    low = text.lower()
    return [f"‘{w}’" for w in block if w in low] + (["날짜"] if DATE_RE.search(text) else [])


def title(engine, text):
    head = text.split("→")[0].strip()
    return f"feedback({engine}): " + (head if len(head) <= 80 else head[:79].rstrip() + "…")


def body(engine, text, version):
    return f"{text}\n\n엔진: {engine} · 키트: {version}"


def open_issues(repo):
    """키트에 열려 있는 feedback 이슈. 못 읽으면 None — 보내는 일을 막지 않는다."""
    out = []
    try:
        for page in (1, 2, 3):
            req = urllib.request.Request(f"{API}/repos/{repo}/issues?state=open&per_page=100&page={page}",
                                         headers={"Accept": "application/vnd.github+json", "User-Agent": "gamedev-kit"})
            got = json.load(urllib.request.urlopen(req, timeout=10))
            out += [i for i in got if "pull_request" not in i and i.get("title", "").startswith("feedback(")]
            if len(got) < 100:
                break
    except Exception:
        return None
    return out


def near(engine, text, issues):
    """같은 엔진의 열린 이슈 가운데 낱말이 겹치는 것, 많이 겹치는 순으로 셋."""
    mine, found = set(WORD_RE.findall(text.lower())), []
    for i in issues:
        if not i["title"].startswith(f"feedback({engine})"):
            continue
        theirs = set(WORD_RE.findall((i["title"] + " " + (i.get("body") or "")).lower()))
        score = len(mine & theirs) / max(1, min(len(mine), len(theirs)))
        if score >= NEAR:
            found.append((score, i["number"], i["title"]))
    return sorted(found, reverse=True)[:3]


def gh():
    name = config().get("feedback", {}).get("gh") or "gh"
    return name if os.path.exists(name) else shutil.which(name)


def cmd_list():
    items, block = todo(), private()
    print(f"{FEEDBACK} — 안 보낸 줄 {len(items)}개" if lines() else f"{FEEDBACK} 가 없다")
    for n, (_i, engine, text) in enumerate(items, 1):
        bad = leaks(text, block)
        print(f"  {n}. ({engine}) {text}" + (f"\n     ! 이 게임의 것으로 보이는 낱말: {' · '.join(bad)}" if bad else ""))


def cmd_preview(arg):
    repo, version = kit()
    issues, block = open_issues(repo), private()
    print(f"보낼 곳: {WEB}/{repo}/issues" + ("" if issues is not None else " (열려 있는 이슈를 읽지 못했다 — 비슷한 것이 있는지 못 봤다)"))
    for n, (_i, engine, text) in pick(arg):
        print(f"\n[{n}] {title(engine, text)}\n{body(engine, text, version)}")
        bad = leaks(text, block)
        if bad:
            print(f"! 이 게임의 것으로 보이는 낱말: {' · '.join(bad)} — 줄을 고쳐 적기 전에는 보내지 않는다")
        for _s, num, name in near(engine, text, issues or []):
            print(f"~ 비슷한 이슈 #{num}: {name}")


def cmd_send(arg, to, as_is):
    repo, version = kit()
    chosen, block = pick(arg), private()
    if to and len(chosen) != 1:
        sys.exit("--to 는 줄 하나에만 쓴다")
    for n, (_i, _engine, text) in chosen:  # 하나라도 걸리면 아무것도 보내지 않는다
        bad = leaks(text, block)
        if bad and not as_is:
            sys.exit(f"{n}번 줄에 이 게임의 것으로 보이는 낱말이 있다 ({' · '.join(bad)}) — {FEEDBACK} 의 그 줄을 고쳐 적는다. 아무것도 보내지 않았다")
    tool, done = gh(), {}
    for n, (i, engine, text) in chosen:
        if to:
            said = f"여기서도 봤다 (엔진: {engine} · 키트: {version})\n\n{text}"
            args, by_hand = ["issue", "comment", to, "--repo", repo, "--body", said], f"{WEB}/{repo}/issues/{to} 에 이 글을 단다:\n{said}"
        else:
            args = ["issue", "create", "--repo", repo, "--title", title(engine, text), "--body", body(engine, text, version)]
            by_hand = (f"{WEB}/{repo}/issues/new?title={urllib.parse.quote(title(engine, text))}"
                       f"&body={urllib.parse.quote(body(engine, text, version))}")
        p = subprocess.run([tool] + args, capture_output=True, text=True) if tool else None
        if p is None or p.returncode != 0:
            why = "gh 가 없다" if p is None else "gh 가 올리지 못했다: " + (p.stderr.strip().split("\n")[-1] if p.stderr.strip() else "?")
            print(f"[{n}] {why} — 사용자가 손수 올린다: {by_hand}\n    올린 뒤 `sent <번호> <이슈 번호>` 로 적는다 (번호는 다시 `list` 해서 본다)")
            continue
        num = to or (re.findall(r"/issues/(\d+)", p.stdout) or ["?"])[-1]
        done[i] = (">", f"이슈 #{num}")
        print(f"[{n}] " + (f"이슈 #{num} 에 달았다" if to else f"이슈 #{num} 을 열었다: {WEB}/{repo}/issues/{num}"))
    mark(done)


def cmd_close(arg, box, tail):
    chosen = pick(arg)
    if len(chosen) != 1:
        sys.exit("한 번에 한 줄이다")
    mark({chosen[0][1][0]: (box, tail)})
    print(f"{FEEDBACK} 에 적었다")


def notice():
    """세션이 시작될 때 훅이 부른다. 할 말이 없으면 조용하다. 밖을 보지 않는다."""
    global ROOT
    ROOT = find_root(os.getcwd())
    if not ROOT:
        return
    limit = config().get("feedback", {}).get("notice", NOTICE)
    count = sum(1 for line in lines() if OPEN_RE.match(line))
    if limit is False or count < limit:
        return
    print(f"[gamedev-kit] 키트로 올릴 배움이 {count}줄 쌓여 있다 ({FEEDBACK}). 하던 일을 막지 않는다 — 끊을 자리에서 사용자에게 한 줄로 알린다: "
          "`/gamedev-kit:feedback` 으로 보낼 수 있다. 알리지 않게 하려면 kit.config.json 에 `\"feedback\": {\"notice\": false}`.")


def main():
    args = sys.argv[1:]
    if "--notice" in args:
        try:
            notice()
        except Exception:  # 훅은 무슨 일이 있어도 세션을 막지 않는다
            pass
        return
    opts = {}
    for flag in ("--root", "--to"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    as_is = "--as-is" in args
    args = [a for a in args if a != "--as-is"]
    cmd, rest = (args[0] if args else ""), args[1:]
    need = {"list": 0, "preview": 1, "send": 1, "sent": 2, "skip": 2}
    if need.get(cmd) != len(rest):
        sys.exit(__doc__)
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    if not ROOT or not os.path.exists(os.path.join(ROOT, CONFIG_NAME)):
        sys.exit(f"{CONFIG_NAME} 을 찾지 못했다 — 게임 저장소 안에서 돌리고 있는가, /gamedev-kit:init 을 했는가")
    if cmd == "list":
        cmd_list()
    elif cmd == "preview":
        cmd_preview(rest[0])
    elif cmd == "send":
        cmd_send(rest[0], opts.get("--to", "").lstrip("#"), as_is)
    elif cmd == "sent":
        cmd_close(rest[0], ">", f"이슈 #{rest[1].lstrip('#')}")
    else:
        cmd_close(rest[0], "-", f"안 보냄: {' '.join(rest[1].split())}")


if __name__ == "__main__":
    main()
