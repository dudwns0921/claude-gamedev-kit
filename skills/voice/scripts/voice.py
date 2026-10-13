#!/usr/bin/env python3
"""The voice (one page of how the user decides): its material and its scoring — pulls only the decision lines out of the cycle documents, and checks the prediction written before asking against the answer.

The voice belongs to a person, not a game, so it lives outside the game repository: ~/.config/gamedev-kit/voice/ (change it with the GAMEDEV_KIT_VOICE environment variable).
There sit VOICE.md (read and edited by people) · log.md (the prediction ledger) · seen.txt (decisions the voice has already read), and every line says which game it is from.
The game's name is the name of the game folder (change it with "voice": {"name": …} in kit.config.json).

  python3 voice.py path                    Path of the voice document. If there is none yet, says so and exits 1
  python3 voice.py collect                 This game, per cycle: the goal and the answered decisions. Marks whether the answer split from the recommendation, and whether it was changed ([바꿈])
  python3 voice.py collect new             Only what the voice has not read yet
  python3 voice.py collect done            Record every decision answered so far as read (after writing the voice)
  python3 voice.py predict D2 ② V3,V5      Write a prediction before asking — the pick and the principles behind it. Not allowed on an answered decision
  python3 voice.py predict D2 -            No principle to go on (모름)
  python3 voice.py score                   Score the predictions of answered decisions. Where no option can be told from the answer, prints a line for it
  python3 voice.py score 03 D2 hit         Those, by hand (hit · miss)
  python3 voice.py stats                   Hit rate — overall · per game · per asker · per principle

The voice folder is a clone of a private git repository — no copies are kept. Another machine clones the same repository.

  python3 voice.py setup <repo url>        No folder: clone. A voice already there: make that folder a repository and attach the remote. Stops on a public repository
  python3 voice.py autopush on             Record on this machine the user's permission to push without asking (off takes it back). Only for a repository confirmed private
                                           (a repository that cannot be read without logging in — checked with the login git already has)
  python3 voice.py sync ["<one line>"]     Commit what changed, take what the remote has, and push if permitted. Run before reading and after writing
  python3 voice.py sync --push             Without the permission — push once, after asking the user

predict looks at the decisions of the newest cycle document (the highest number). For another document, `--doc <path>`.
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
ANON_GIT = os.environ.get("VOICE_ANON_GIT", "git")  # the tests change this
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
DECISION_RE = re.compile(r"^- \[(.)\] (D\d+)\.(.*)$", re.M)
PARTS_RE = re.compile(r"^(?P<q>.*?)(?: \((?P<who>기획|디자인|계획)\))?(?: → (?P<a>.*?)(?: \((?P<date>\d{4}-\d\d-\d\d)\))?)?$")
LOG_RE = re.compile(r"^- \[(.)\] (\S+) (\d+) (D\d+) \(([^)]*)\) → (\S+)(?: · (V\d+(?:, V\d+)*))?", re.M)
WORD = {"o": "hit", "x": "miss"}

ROOT = ""
GAME = ""


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
    """The one option picked in the text (①, `2번`). None, or more than one: empty string — what a person says is an answer even without a number."""
    found = set(re.findall(f"[{CIRCLED}]", text)) | {CIRCLED[int(n) - 1] for n in re.findall(r"(?<!\d)([1-9])번", text)}
    return found.pop() if len(found) == 1 else ""


def decisions(text):
    """Decision number → question · who asked · recommendation · answer · date answered · the option told from the answer · how many times it was answered.
    A changed answer is appended to the earlier one as ` → new answer` — the picked option is told from the last answer."""
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
    if "를 받아들임" in d["answer"]:  # accepted what auto mode decided in their place — weaker evidence than a pick of their own
        return "받음"
    if d["answers"] > 1:  # changed the answer — what changed to make them do so is the most useful thing for the voice
        return "바꿈"
    if not d["rec"] or not d["chose"]:
        return "?"
    return "같음" if d["rec"] == d["chose"] else "갈림"


def cmd_collect(mode):
    seen = set(read(SEEN).split("\n")) if os.path.exists(SEEN) else set()
    # a decision whose answer changed shows up again even after it was read — the key carries which answer it is
    key = lambda path, num, d: f"{GAME} {number(path)} {num}" + (f" #{d['answers']}" if d["answers"] > 1 else "")
    count = {"갈림": 0, "같음": 0, "?": 0, "받음": 0, "바꿈": 0}
    if mode == "done":
        new = [key(p, num, d) for p in docs() for num, d in decisions(read(p)).items() if d["answer"] is not None and key(p, num, d) not in seen]
        if new:
            write(SEEN, "\n".join(sorted(seen - {""}) + new) + "\n")
        return print(f"recorded {len(new)} as read")
    print(f"game: {GAME}")
    for path in docs():
        text = read(path)
        rows = [(num, d) for num, d in decisions(text).items()
                if d["answer"] is not None and not (mode == "new" and key(path, num, d) in seen)]
        if not rows:
            continue
        title = re.match(r"# *(.*)", text)
        print(f"\n{title.group(1) if title else os.path.basename(path)}")
        print("goal: " + " ".join(section(text, "목표").split()))
        for num, d in rows:
            tag = split_tag(d)
            count[tag] += 1
            print(f"  {GAME} {number(path)} {num} [{tag}] ({d['who']}) {d['q']} → {d['answer']}" + (f" ({d['date']})" if d["date"] else ""))
    total = sum(count.values())
    if not total:
        return print("no answered decisions" + (" (among those not read yet)" if mode == "new" else ""))
    print(f"\ndecisions {total} · 갈림 {count['갈림']} · 같음 {count['같음']} · to read {count['?']}"
          + (f" · 받음 {count['받음']}" if count["받음"] else "") + (f" · 바꿈 {count['바꿈']}" if count["바꿈"] else ""))


def log_text():
    return read(LOG) if os.path.exists(LOG) else LOG_HEAD


def cmd_predict(path, num, pick, cites):
    ds = decisions(read(path))
    if num not in ds:
        sys.exit(f"{num}: no such decision — " + " · ".join(ds))
    if ds[num]["answer"] is not None:
        sys.exit(f"{num}: already answered — a prediction is written before asking")
    log = log_text()
    if re.search(rf"^- \[.\] {re.escape(GAME)} {number(path)} {num} ", log, re.M):
        sys.exit(f"{num}: prediction already written")
    if pick == "-":
        line = f"- [-] {GAME} {number(path)} {num} ({ds[num]['who']}) → 모름"
    else:
        pick = CIRCLED[int(pick) - 1] if re.fullmatch(r"[1-9]", pick) else pick
        if pick not in CIRCLED or pick not in ds[num]["q"]:
            sys.exit(f"{pick}: not an option in the question — {ds[num]['q']}")
        known = re.findall(r"^- (V\d+)\.", read(VOICE), re.M) if os.path.exists(VOICE) else []
        used = [v for v in cites.split(",") if v]
        bad = [v for v in used if v not in known]
        if not used or bad:
            sys.exit(f"principle not in {VOICE}: {' · '.join(bad) or '(none given)'} — with no principle to go on, `predict {num} -`")
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
            unclear.append(f"cannot tell: {doc} {num} predicted {pick} · answer: {d['answer']} — `score {doc} {num} hit|miss`")
            continue
        log = log.replace(m.group(0), m.group(0).replace("- [ ]", f"- [{new}]", 1), 1)
        marked.append(f"{doc} {num}: {WORD[new]} — predicted {pick}" + (f" ({m.group(7)})" if m.group(7) else "") + f" · answer: {d['answer']}")
    if manual and not any(line.startswith(f"{manual[0]} {manual[1]}:") for line in marked):
        sys.exit(f"{manual[0]} {manual[1]}: no prediction to score (no prediction, no answer yet, or already scored)")
    if marked:
        write(LOG, log)
    print("\n".join(marked + unclear) or "no prediction to score")


def git(*args):
    return subprocess.run(["git", "-C", HOME, *args], capture_output=True, text=True)


def is_repo():
    return os.path.isdir(os.path.join(HOME, ".git"))


def anon_url(url):
    """The address to ask without a login. Asking an SSH address as it is lets the SSH key log in, so a private repository is read too (same for an alias in ~/.ssh/config) —
    a GitHub one becomes the https address of the same repository; an SSH address on a host that cannot be converted gives None (cannot be asked)."""
    m = re.match(r"ssh://(?:[^@/]+@)?([^:/]+)(?::\d+)?/(.+)$", url) or ("://" not in url and re.match(r"(?:[^@/:]+@)?([^:/]+):(.+)$", url))
    if not m or os.path.exists(url):  # https · a path on this machine and the like carry no key
        return url
    host, path = m.group(1).lower(), m.group(2).strip("/")
    if host == "github.com" or host.startswith("github.com-"):
        return f"https://github.com/{path}" + ("" if path.endswith(".git") else ".git")
    return None


def is_private(url):
    """Readable without a login means public. True if it reads only with a login, False if it reads without one, None if it cannot be reached or cannot be asked without a login.
    Uses only the login git already has — nothing more to install or log in to."""
    if subprocess.run(["git", "ls-remote", url], capture_output=True, text=True).returncode:
        return None
    ask = anon_url(url)
    if ask is None:
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_ASKPASS", "SSH_ASKPASS")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    anon = subprocess.run([ANON_GIT, "-c", "credential.helper=", "ls-remote", ask], capture_output=True, text=True, env=env)
    return anon.returncode != 0


def cmd_setup(url):
    private = is_private(url)
    if private is False:
        sys.exit(f"{url}: public repository — the voice holds the user's leanings and biases. Make it private, then run again")
    if is_repo():
        origin = git("remote", "get-url", "origin").stdout.strip()
        if origin and origin != url:
            sys.exit(f"{HOME} already belongs to another repository: {origin}")
        if not origin:
            git("remote", "add", "origin", url)
        print(f"{HOME} — already a repository")
    elif not os.path.isdir(HOME) or not os.listdir(HOME):
        os.makedirs(os.path.dirname(HOME), exist_ok=True)
        p = subprocess.run(["git", "clone", "-q", url, HOME], capture_output=True, text=True)
        if p.returncode:
            sys.exit(f"clone failed: {p.stderr.strip()}")
        print(f"{HOME} — cloned" + ("" if os.path.exists(VOICE) else " (the repository is still empty)"))
    else:
        heads = subprocess.run(["git", "ls-remote", "--heads", url], capture_output=True, text=True)
        if heads.returncode:
            sys.exit(f"could not reach the repository: {heads.stderr.strip()}")
        if heads.stdout.strip():
            sys.exit(f"there is a voice both in the repository and on this machine ({HOME}) — the user decides which one to keep. Move this machine's aside and run again to take the repository's")
        git("init", "-q")
        git("remote", "add", "origin", url)
        print(f"{HOME} — made the existing voice a repository. `sync` commits and pushes")
    if private is None:
        print("could not confirm it is private — the repository could not be reached (check the address and the git login), or it is an SSH address that cannot be asked without a login. Pushing without asking cannot be turned on")
    else:
        print("private repository. Ask the user whether it may be pushed without asking — if yes, `autopush on`")


def cmd_autopush(state):
    if not is_repo():
        sys.exit(f"{HOME} is not a repository — `setup <repo url>`")
    if state == "on" and is_private(git("remote", "get-url", "origin").stdout.strip()) is not True:
        sys.exit("not a repository confirmed private — will not push without asking")
    git("config", "voice.autopush", "true" if state == "on" else "false")
    print("pushes without asking (on this machine)" if state == "on" else "asks before pushing")


def cmd_sync(push, message):
    if not is_repo():
        return print(f"{HOME} is not a repository — the voice stays on this machine only. `setup <private repo url>`")
    if git("status", "--porcelain").stdout.strip():
        git("add", "-A")
        p = git("commit", "-q", "-m", message or f"voice: {datetime.date.today()}")
        if p.returncode:
            sys.exit(f"commit failed: {(p.stderr or p.stdout).strip()}")
        print("committed")
    if git("remote", "get-url", "origin").returncode:
        return print("no remote — `setup <repo url>`")
    if git("fetch", "-q", "origin").returncode:
        return print("could not reach the remote — carrying on with this machine's copy")
    branch = git("symbolic-ref", "--short", "HEAD").stdout.strip()
    remote = f"origin/{branch}"
    has = lambda ref: git("rev-parse", "-q", "--verify", ref).returncode == 0
    count = lambda span: int(git("rev-list", "--count", span).stdout.strip() or 0)
    if has(remote) and (not has("HEAD") or count(f"HEAD..{remote}")):
        behind = count(f"HEAD..{remote}") if has("HEAD") else count(remote)
        if git("pull", "-q", "--rebase", "origin", branch).returncode:
            git("rebase", "--abort")
            sys.exit(f"the voice was edited differently on two machines — merge by hand in {HOME} (git pull --rebase). Do not use the voice until then")
        print(f"pulled — commits {behind}")
    ahead = count(f"{remote}..HEAD" if has(remote) else "HEAD") if has("HEAD") else 0
    if not ahead:
        return print("same as the repository")
    if not push and git("config", "voice.autopush").stdout.strip() != "true":
        return print(f"unpushed commits {ahead} — ask the user, then `sync --push` (if it may always be pushed, `autopush on`)")
    p = git("push", "-q", "-u", "origin", branch)
    print(f"pushed — commits {ahead}" if p.returncode == 0 else f"push failed: {p.stderr.strip()}")


def cmd_stats():
    rows = LOG_RE.findall(log_text())
    if not rows:
        return print(f"no predictions in {LOG}")
    rate = lambda hit, miss: f"{hit}/{hit + miss}" + (f" ({100 * hit // (hit + miss)}%)" if hit + miss else "")
    tally = lambda picked: (sum(1 for r in picked if r[0] == "o"), sum(1 for r in picked if r[0] == "x"))
    marks = [r[0] for r in rows]
    print(f"hits {rate(*tally(rows))} · 모름 {marks.count('-')} · unscored {marks.count(' ')} · predictions {len(rows)}")
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
            sys.exit(f"no voice yet ({VOICE}) — write it with /gamedev-kit:voice")
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
            sys.exit(f"no cycle document in {DIR}/")
        cmd_predict(path, rest[0], rest[1], rest[2] if len(rest) > 2 else "")
    elif cmd == "score":
        if rest and rest[2] not in ("hit", "miss"):
            sys.exit("a score is hit · miss")
        cmd_score(rest)


if __name__ == "__main__":
    main()
