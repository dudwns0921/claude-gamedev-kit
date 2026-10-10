#!/usr/bin/env python3
"""보이스(사용자의 판단을 모은 한 장)의 재료와 채점 — 사이클 문서의 결정 줄만 꺼내고, 묻기 전에 적은 예측을 답과 견준다.

보이스는 게임이 아니라 사람의 것이라 게임 저장소 밖에 산다: ~/.config/gamedev-kit/voice/ (환경 변수 GAMEDEV_KIT_VOICE 로 바꾼다).
거기에 VOICE.md(사람이 읽고 고치는 것) · log.md(예측 장부) · seen.txt(보이스에 이미 읽힌 결정)가 있고, 줄마다 어느 게임의 것인지 적힌다.
게임의 이름은 게임 폴더의 이름이다 (kit.config.json 의 "voice": {"name": …} 로 바꾼다).

  python3 voice.py path                    보이스 문서의 경로. 아직 없으면 그렇다고 하고 1 로 끝난다
  python3 voice.py collect                 이 게임의 사이클마다 목표와 답이 난 결정. 권함과 답이 갈렸는지, 답을 바꿨는지([바꿈]) 표시한다
  python3 voice.py collect new             보이스에 아직 읽히지 않은 것만
  python3 voice.py collect done            지금 답이 난 결정을 전부 읽힌 것으로 적는다 (보이스를 쓴 뒤에)
  python3 voice.py predict D2 ② V3,V5      묻기 전에 예측을 적는다 — 고를 것과 근거 원칙. 답이 난 결정에는 적지 못한다
  python3 voice.py predict D2 -            근거가 될 원칙이 없다 (모름)
  python3 voice.py score                   답이 난 결정의 예측을 채점한다. 답에서 번호를 가릴 수 없는 것은 줄로 내놓는다
  python3 voice.py score 03 D2 hit         가릴 수 없던 것을 손으로 (hit · miss)
  python3 voice.py stats                   적중률 — 전체 · 게임별 · 누가 물은 것 · 원칙별

보이스 폴더는 비공개 git 저장소의 클론이다 — 복사본을 두지 않는다. 다른 기기에서는 같은 저장소를 받는다.

  python3 voice.py setup <저장소 주소>     폴더가 없으면 받고(clone), 보이스가 이미 있으면 그 폴더를 저장소로 만들어 원격을 붙인다. 공개 저장소면 멈춘다
  python3 voice.py autopush on             묻지 않고 올려도 된다는 사용자의 허락을 이 기기에 적는다 (off 로 거둔다). 비공개로 확인된 저장소만
                                           (로그인 없이는 읽히지 않는 저장소 — git 이 가진 로그인으로 본다)
  python3 voice.py sync ["<한 줄>"]         바뀐 것을 커밋하고, 원격의 것을 받고, 허락이 있으면 올린다. 읽기 전과 쓴 뒤에 돌린다
  python3 voice.py sync --push             허락이 없을 때 — 사용자에게 묻고 난 뒤 한 번 올린다

predict 는 가장 새 사이클 문서(번호가 가장 큰 것)의 결정을 본다. 다른 문서면 `--doc <경로>`.
"""
import datetime
import json
import os
import re
import subprocess
import sys

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "cycle")
HOME = os.path.expanduser(os.environ.get("GAMEDEV_KIT_VOICE") or "~/.config/gamedev-kit/voice")
VOICE = os.path.join(HOME, "VOICE.md")
LOG = os.path.join(HOME, "log.md")
SEEN = os.path.join(HOME, "seen.txt")
LOG_HEAD = """# 보이스 예측 장부

결정을 묻기 전에 보이스(VOICE.md)로 적은 예측과 그 채점 (`voice.py predict` · `score`). 손으로 고치지 않는다.
`[ ]` 채점 전 · `[o]` 맞음 · `[x]` 빗나감 · `[-]` 모름 (근거가 될 원칙이 없어 예측하지 않음)

"""
ANON_GIT = os.environ.get("VOICE_ANON_GIT", "git")  # 테스트가 바꾼다
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
DECISION_RE = re.compile(r"^- \[(.)\] (D\d+)\.(.*)$", re.M)
PARTS_RE = re.compile(r"^(?P<q>.*?)(?: \((?P<who>기획|디자인|계획)\))?(?: → (?P<a>.*?)(?: \((?P<date>\d{4}-\d\d-\d\d)\))?)?$")
LOG_RE = re.compile(r"^- \[(.)\] (\S+) (\d+) (D\d+) \(([^)]*)\) → (\S+)(?: · (V\d+(?:, V\d+)*))?", re.M)
WORD = {"o": "맞음", "x": "빗나감"}

ROOT = ""
GAME = ""


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
    """결정 번호 → 질문 · 누가 물었나 · 권함 · 답 · 답한 날 · 답에서 가린 번호 · 답이 몇 번 났나.
    답을 바꾸면 앞의 답 뒤에 ` → 새 답` 이 붙는다 — 고른 번호는 마지막 답에서 가린다."""
    out = {}
    for mark, num, rest in DECISION_RE.findall(section(text, "결정")):
        p = PARTS_RE.match(rest.strip()).groupdict()
        rec = re.search(rf"권함: *([{CIRCLED}])", p["q"])
        answered = mark == "x" and p["a"] is not None
        chain = p["a"].split(" → ") if answered else []
        out[num] = {"q": p["q"].strip(), "who": p["who"] or "?", "rec": rec.group(1) if rec else "",
                    "answer": p["a"] if answered else None, "date": p["date"] or "",
                    "chose": choice(chain[-1]) if answered else "", "answers": len(chain)}
    return out


def split_tag(d):
    if "를 받아들임" in d["answer"]:  # 자동 모드가 대신 정한 것을 받아들였다 — 스스로 고른 것보다 약한 근거다
        return "받음"
    if d["answers"] > 1:  # 답을 바꿨다 — 무엇이 달라져서 바꿨는가가 보이스에 가장 쓸모 있다
        return "바꿈"
    if not d["rec"] or not d["chose"]:
        return "?"
    return "같음" if d["rec"] == d["chose"] else "갈림"


def cmd_collect(mode):
    seen = set(read(SEEN).split("\n")) if os.path.exists(SEEN) else set()
    # 답을 바꾼 결정은 읽힌 뒤에도 다시 나온다 — 몇 번째 답인지가 이름에 붙는다
    key = lambda path, num, d: f"{GAME} {number(path)} {num}" + (f" #{d['answers']}" if d["answers"] > 1 else "")
    count = {"갈림": 0, "같음": 0, "?": 0, "받음": 0, "바꿈": 0}
    if mode == "done":
        new = [key(p, num, d) for p in docs() for num, d in decisions(read(p)).items() if d["answer"] is not None and key(p, num, d) not in seen]
        if new:
            write(SEEN, "\n".join(sorted(seen - {""}) + new) + "\n")
        return print(f"{len(new)}개를 읽힌 것으로 적었다")
    print(f"게임: {GAME}")
    for path in docs():
        text = read(path)
        rows = [(num, d) for num, d in decisions(text).items()
                if d["answer"] is not None and not (mode == "new" and key(path, num, d) in seen)]
        if not rows:
            continue
        title = re.match(r"# *(.*)", text)
        print(f"\n{title.group(1) if title else os.path.basename(path)}")
        print("목표: " + " ".join(section(text, "목표").split()))
        for num, d in rows:
            tag = split_tag(d)
            count[tag] += 1
            print(f"  {GAME} {number(path)} {num} [{tag}] ({d['who']}) {d['q']} → {d['answer']}" + (f" ({d['date']})" if d["date"] else ""))
    total = sum(count.values())
    if not total:
        return print("답이 난 결정이 없다" + (" (아직 읽히지 않은 것 가운데)" if mode == "new" else ""))
    print(f"\n결정 {total} · 권함과 갈림 {count['갈림']} · 같음 {count['같음']} · 읽어서 가릴 것 {count['?']}"
          + (f" · 대리를 받음 {count['받음']}" if count["받음"] else "") + (f" · 답을 바꿈 {count['바꿈']}" if count["바꿈"] else ""))


def log_text():
    return read(LOG) if os.path.exists(LOG) else LOG_HEAD


def cmd_predict(path, num, pick, cites):
    ds = decisions(read(path))
    if num not in ds:
        sys.exit(f"{num}: 그런 결정이 없다 — " + " · ".join(ds))
    if ds[num]["answer"] is not None:
        sys.exit(f"{num}: 이미 답이 났다 — 예측은 묻기 전에 적는다")
    log = log_text()
    if re.search(rf"^- \[.\] {re.escape(GAME)} {number(path)} {num} ", log, re.M):
        sys.exit(f"{num}: 이미 예측을 적었다")
    if pick == "-":
        line = f"- [-] {GAME} {number(path)} {num} ({ds[num]['who']}) → 모름"
    else:
        pick = CIRCLED[int(pick) - 1] if re.fullmatch(r"[1-9]", pick) else pick
        if pick not in CIRCLED or pick not in ds[num]["q"]:
            sys.exit(f"{pick}: 질문에 없는 선택지다 — {ds[num]['q']}")
        known = re.findall(r"^- (V\d+)\.", read(VOICE), re.M) if os.path.exists(VOICE) else []
        used = [v for v in cites.split(",") if v]
        bad = [v for v in used if v not in known]
        if not used or bad:
            sys.exit(f"근거 원칙이 {VOICE} 에 없다: {' · '.join(bad) or '(안 적음)'} — 근거가 없으면 `predict {num} -`")
        line = f"- [ ] {GAME} {number(path)} {num} ({ds[num]['who']}) → {pick} · {', '.join(used)}"
    write(LOG, log.rstrip("\n") + f"\n{line} ({datetime.date.today()})\n")
    print(line[2:])


def cmd_score(manual):
    log = log_text()
    by_num = {number(p): p for p in docs()}
    marked, unclear = [], []
    for m in LOG_RE.finditer(log):
        mark, game, doc, num, pick = m.group(1, 2, 3, 4, 6)
        if mark != " " or game != GAME:
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
        marked.append(f"{doc} {num}: {WORD[new]} — 예측 {pick}" + (f" ({m.group(7)})" if m.group(7) else "") + f" · 답: {d['answer']}")
    if manual and not any(line.startswith(f"{manual[0]} {manual[1]}:") for line in marked):
        sys.exit(f"{manual[0]} {manual[1]}: 채점할 예측이 없다 (예측이 없거나, 답이 아직 없거나, 이미 채점했다)")
    if marked:
        write(LOG, log)
    print("\n".join(marked + unclear) or "채점할 예측이 없다")


def git(*args):
    return subprocess.run(["git", "-C", HOME, *args], capture_output=True, text=True)


def is_repo():
    return os.path.isdir(os.path.join(HOME, ".git"))


def is_private(url):
    """로그인 없이도 읽히면 공개다. 로그인해야만 읽히면 True, 로그인 없이 읽히면 False, 아예 닿지 않으면 None.
    git 이 이미 가진 로그인만 쓴다 — 따로 깔거나 로그인할 것이 없다."""
    if subprocess.run(["git", "ls-remote", url], capture_output=True, text=True).returncode:
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_ASKPASS", "SSH_ASKPASS")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    anon = subprocess.run([ANON_GIT, "-c", "credential.helper=", "ls-remote", url], capture_output=True, text=True, env=env)
    return anon.returncode != 0


def cmd_setup(url):
    private = is_private(url)
    if private is False:
        sys.exit(f"{url}: 공개 저장소다 — 보이스에는 사용자의 성향과 편향이 적힌다. 비공개로 바꾼 뒤 다시 돌린다")
    if is_repo():
        origin = git("remote", "get-url", "origin").stdout.strip()
        if origin and origin != url:
            sys.exit(f"{HOME} 은 이미 다른 저장소의 것이다: {origin}")
        if not origin:
            git("remote", "add", "origin", url)
        print(f"{HOME} — 이미 저장소다")
    elif not os.path.isdir(HOME) or not os.listdir(HOME):
        os.makedirs(os.path.dirname(HOME), exist_ok=True)
        p = subprocess.run(["git", "clone", "-q", url, HOME], capture_output=True, text=True)
        if p.returncode:
            sys.exit(f"받지 못했다: {p.stderr.strip()}")
        print(f"{HOME} — 받았다" + ("" if os.path.exists(VOICE) else " (아직 빈 저장소다)"))
    else:
        heads = subprocess.run(["git", "ls-remote", "--heads", url], capture_output=True, text=True)
        if heads.returncode:
            sys.exit(f"저장소에 닿지 못했다: {heads.stderr.strip()}")
        if heads.stdout.strip():
            sys.exit(f"저장소에도 이 기기({HOME})에도 보이스가 있다 — 어느 쪽을 남길지 사용자가 정한다. 이 기기의 것을 옮겨 두고 다시 돌리면 저장소의 것을 받는다")
        git("init", "-q")
        git("remote", "add", "origin", url)
        print(f"{HOME} — 있던 보이스를 저장소로 만들었다. `sync` 가 커밋하고 올린다")
    if private is None:
        print("저장소에 닿지 못해 비공개인지 확인하지 못했다 — 주소와 git 로그인을 본다. 묻지 않고 올리기는 켤 수 없다")
    else:
        print("비공개 저장소다. 묻지 않고 올려도 되는지 사용자에게 묻는다 — 된다고 하면 `autopush on`")


def cmd_autopush(state):
    if not is_repo():
        sys.exit(f"{HOME} 은 저장소가 아니다 — `setup <저장소 주소>`")
    if state == "on" and is_private(git("remote", "get-url", "origin").stdout.strip()) is not True:
        sys.exit("비공개로 확인된 저장소가 아니다 — 묻지 않고 올리지 않는다")
    git("config", "voice.autopush", "true" if state == "on" else "false")
    print("묻지 않고 올린다 (이 기기에서)" if state == "on" else "올리기 전에 묻는다")


def cmd_sync(push, message):
    if not is_repo():
        return print(f"{HOME} 은 저장소가 아니다 — 보이스가 이 기기에만 남는다. `setup <비공개 저장소 주소>`")
    if git("status", "--porcelain").stdout.strip():
        git("add", "-A")
        p = git("commit", "-q", "-m", message or f"voice: {datetime.date.today()}")
        if p.returncode:
            sys.exit(f"커밋하지 못했다: {(p.stderr or p.stdout).strip()}")
        print("커밋했다")
    if git("remote", "get-url", "origin").returncode:
        return print("원격이 없다 — `setup <저장소 주소>`")
    if git("fetch", "-q", "origin").returncode:
        return print("원격에 닿지 못했다 — 이 기기의 것으로 계속한다")
    branch = git("symbolic-ref", "--short", "HEAD").stdout.strip()
    remote = f"origin/{branch}"
    has = lambda ref: git("rev-parse", "-q", "--verify", ref).returncode == 0
    count = lambda span: int(git("rev-list", "--count", span).stdout.strip() or 0)
    if has(remote) and (not has("HEAD") or count(f"HEAD..{remote}")):
        behind = count(f"HEAD..{remote}") if has("HEAD") else count(remote)
        if git("pull", "-q", "--rebase", "origin", branch).returncode:
            git("rebase", "--abort")
            sys.exit(f"두 기기의 보이스가 서로 다르게 고쳐졌다 — {HOME} 에서 손으로 합친다 (git pull --rebase). 그 전에는 보이스를 쓰지 않는다")
        print(f"받았다 — 커밋 {behind}")
    ahead = count(f"{remote}..HEAD" if has(remote) else "HEAD") if has("HEAD") else 0
    if not ahead:
        return print("저장소와 같다")
    if not push and git("config", "voice.autopush").stdout.strip() != "true":
        return print(f"올리지 않은 커밋 {ahead} — 사용자에게 묻고 `sync --push` (늘 올려도 되면 `autopush on`)")
    p = git("push", "-q", "-u", "origin", branch)
    print(f"올렸다 — 커밋 {ahead}" if p.returncode == 0 else f"올리지 못했다: {p.stderr.strip()}")


def cmd_stats():
    rows = LOG_RE.findall(log_text())
    if not rows:
        return print(f"{LOG} 에 예측이 없다")
    rate = lambda hit, miss: f"{hit}/{hit + miss}" + (f" ({100 * hit // (hit + miss)}%)" if hit + miss else "")
    tally = lambda picked: (sum(1 for r in picked if r[0] == "o"), sum(1 for r in picked if r[0] == "x"))
    marks = [r[0] for r in rows]
    print(f"적중 {rate(*tally(rows))} · 모름 {marks.count('-')} · 채점 전 {marks.count(' ')} · 예측 {len(rows)}")
    if len({r[1] for r in rows}) > 1:
        for game in dict.fromkeys(r[1] for r in rows):
            mine = [r for r in rows if r[1] == game]
            print(f"  {game}: {rate(*tally(mine))} · 모름 {sum(1 for r in mine if r[0] == '-')}")
    for who in dict.fromkeys(r[4] for r in rows):
        mine = [r for r in rows if r[4] == who]
        print(f"  {who}: {rate(*tally(mine))} · 모름 {sum(1 for r in mine if r[0] == '-')}")
    for v in sorted({v for r in rows for v in re.findall(r"V\d+", r[6])}, key=lambda v: int(v[1:])):
        print(f"  {v}: {rate(*tally([r for r in rows if v in re.findall(r'V[0-9]+', r[6])]))}")


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--doc"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    push = "--push" in args
    args = [a for a in args if a != "--push"]
    cmd, rest = (args[0] if args else ""), args[1:]
    need = {"path": (0,), "collect": (0, 1), "predict": (2, 3), "score": (0, 3), "stats": (0,),
            "setup": (1,), "autopush": (1,), "sync": (0, 1)}
    if cmd not in need or len(rest) not in need[cmd] or (cmd == "autopush" and rest[0] not in ("on", "off")):
        sys.exit(__doc__)
    if cmd == "setup":
        return cmd_setup(rest[0])
    if cmd == "autopush":
        return cmd_autopush(rest[0])
    if cmd == "sync":
        return cmd_sync(push, rest[0] if rest else "")
    if cmd == "path":
        if not os.path.exists(VOICE):
            sys.exit(f"보이스가 아직 없다 ({VOICE}) — /gamedev-kit:voice 로 쓴다")
        return print(VOICE)
    if cmd == "stats":
        return cmd_stats()
    global ROOT, GAME
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    name = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get("voice", {}).get("name")
    GAME = "-".join((name or os.path.basename(ROOT)).split())
    if cmd == "collect":
        if rest and rest[0] not in ("new", "done"):
            sys.exit(__doc__)
        cmd_collect(rest[0] if rest else "")
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


if __name__ == "__main__":
    main()
