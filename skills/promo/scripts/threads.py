#!/usr/bin/env python3
"""홍보 — docs/promo/ 의 초안을 Threads 에 올린다.

  python3 threads.py check <초안.md>     올릴 글을 그대로 보여 주고 길이를 잰다. 올리지 않는다
  python3 threads.py post <초안.md>      올린다. 글이 여럿이면 첫 글에 답글로 잇는다. 초안에 주소를 적어 둔다
  python3 threads.py whoami              토큰이 어느 계정인지
  python3 threads.py refresh             오래가는 토큰을 새로 받아 토큰 파일에 적는다 (60일마다 끊긴다)

초안에서 올라가는 것은 `<!-- threads -->` 와 `<!-- /threads -->` 사이뿐이다. `---` 한 줄이 글 사이를 가른다.
한 번 올린 초안에는 `게시:` 줄이 붙고, 그런 초안은 다시 올리지 않는다.

토큰은 저장소 밖에 둔다 — 환경 변수 THREADS_ACCESS_TOKEN, 없으면 kit.config.json 의 promo.env_file
(기본 ~/.config/gamedev-kit/threads.env) 안의 `THREADS_ACCESS_TOKEN=...` 줄.
"""
import datetime
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

CONFIG_NAME = "kit.config.json"
SECTION = "promo"
DEFAULTS = {
    "env_file": "~/.config/gamedev-kit/threads.env",
    "confirm": True,  # 스킬이 본다: 올리기 전에 글을 보여 주고 묻는가
}
API = os.environ.get("THREADS_API_BASE", "https://graph.threads.net/v1.0")  # 테스트가 바꾼다
TOKEN_KEY = "THREADS_ACCESS_TOKEN"
OPEN, CLOSE, POSTED = "<!-- threads -->", "<!-- /threads -->", "게시:"
LIMIT = 500
POLL = float(os.environ.get("THREADS_POLL_SEC", "5"))
WAIT = 5 * 60  # 만든 글이 올릴 수 있게 되기를 기다리는 한도

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
    CFG = dict(DEFAULTS)
    CFG.update(json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get(SECTION, {}))


def env_file():
    return os.path.expanduser(CFG["env_file"])


def token():
    """(토큰, 파일에서 왔는가)"""
    if os.environ.get(TOKEN_KEY):
        return os.environ[TOKEN_KEY], False
    if os.path.exists(env_file()):
        for line in open(env_file(), encoding="utf-8"):
            key, _, value = line.strip().partition("=")
            if key == TOKEN_KEY and value:
                return value.strip("\"'"), True
    sys.exit(f"Threads 토큰이 없다 — {env_file()} 에 `{TOKEN_KEY}=...` 한 줄을 적는다 (promo 스킬의 '처음 한 번')")


def call(method, path, **params):
    params["access_token"] = token()[0]
    data = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{API}/{path}" + ("" if method == "POST" else "?" + data),
                                 data=data.encode() if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(body)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            pass
        raise RuntimeError(f"Threads API {e.code} ({path.split('?')[0]}): {body}")


def read_draft(path):
    """(글 목록, 이미 올린 줄 또는 None)"""
    text = open(path, encoding="utf-8").read()
    if OPEN not in text or CLOSE not in text:
        sys.exit(f"{path}: `{OPEN}` 와 `{CLOSE}` 사이에 올릴 글이 있어야 한다")
    body = text.split(OPEN, 1)[1].split(CLOSE, 1)[0]
    posts, cur = [], []
    for line in body.split("\n"):
        if line.strip() == "---":
            posts.append("\n".join(cur).strip())
            cur = []
        else:
            cur.append(line)
    posts.append("\n".join(cur).strip())
    posts = [p for p in posts if p]
    posted = next((line for line in text.split("\n") if line.startswith(POSTED)), None)
    return posts, posted


def length(text):
    """Threads 가 세는 길이. 글자 하나가 1 이고, 이모지는 UTF-8 바이트 수만큼 센다 — 모자라게 세느니 넉넉히 센다."""
    return sum(len(c.encode("utf-8")) if ord(c) > 0xFFFF or unicodedata.category(c) == "So" or c in "\u200d\ufe0f" else 1
               for c in text)


def check(path, show=True):
    posts, posted = read_draft(path)
    if not posts:
        sys.exit(f"{path}: 올릴 글이 비어 있다")
    long = [f"글 {i}: {length(p)}자" for i, p in enumerate(posts, 1) if length(p) > LIMIT]
    if show:
        for i, p in enumerate(posts, 1):
            print(f"── 글 {i}/{len(posts)} · {length(p)}자 ──\n{p}\n")
    if long:
        sys.exit(f"{LIMIT}자를 넘는다 — " + ", ".join(long))
    if posted:
        sys.exit(f"이미 올린 초안이다 — {posted}")
    return posts


def publish(me, text, reply_to=None):
    extra = {"reply_to_id": reply_to} if reply_to else {}
    made = call("POST", f"{me}/threads", media_type="TEXT", text=text, **extra)["id"]
    until = time.time() + WAIT  # 만든 직후에는 아직 올릴 수 없다 — 준비됐다고 할 때까지 묻는다
    while True:
        state = call("GET", made, fields="status,error_message")
        if state.get("status") == "FINISHED":
            return call("POST", f"{me}/threads_publish", creation_id=made)["id"]
        if state.get("status") in ("ERROR", "EXPIRED") or time.time() > until:
            raise RuntimeError(f"글이 준비되지 않았다: {state.get('status')} {state.get('error_message', '')}".strip())
        time.sleep(POLL)


def post(path):
    posts = check(path, show=False)
    me = call("GET", "me", fields="id,username")
    ids, err = [], None
    try:
        for text in posts:
            ids.append(publish(me["id"], text, ids[-1] if ids else None))
    except RuntimeError as e:
        err = e
    if ids:  # 일부만 올라갔어도 적어 둔다 — 다시 돌려 같은 글을 두 번 올리지 않게
        try:
            link = call("GET", ids[0], fields="permalink").get("permalink", ids[0])
        except RuntimeError:
            link = ids[0]
        part = "" if len(ids) == len(posts) else f" — {len(posts)}개 중 {len(ids)}개만"
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n{POSTED} {link} (@{me.get('username', '?')}, {datetime.date.today()}, 글 {len(ids)}개{part})\n")
        print(f"올렸다: {link} · 글 {len(ids)}개{part}")
    if err:
        sys.exit(f"올리다 멈췄다 ({len(ids)}/{len(posts)}): {err}")


def refresh():
    old, from_file = token()
    if not from_file:
        sys.exit(f"토큰이 환경 변수에서 왔다 — 파일({env_file()})에 둔 토큰만 새로 적을 수 있다")
    r = call("GET", "refresh_access_token", grant_type="th_refresh_token")
    lines = [f"{TOKEN_KEY}={r['access_token']}" if line.strip().startswith(TOKEN_KEY + "=") else line.rstrip("\n")
             for line in open(env_file(), encoding="utf-8")]
    fd = os.open(env_file(), os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"토큰을 새로 적었다 — {int(r.get('expires_in', 0)) // 86400}일 뒤 끊긴다")


def main():
    args = sys.argv[1:]
    root = None
    if "--root" in args:  # 테스트용
        i = args.index("--root")
        root = args[i + 1]
        del args[i:i + 2]
    cmd = args[0] if args else ""
    if cmd not in ("check", "post", "whoami", "refresh") or (cmd in ("check", "post") and len(args) != 2):
        sys.exit(__doc__)
    setup(root)
    try:
        if cmd == "check":
            print(f"올릴 수 있다 — 글 {len(check(args[1]))}개")
        elif cmd == "post":
            post(args[1])
        elif cmd == "whoami":
            me = call("GET", "me", fields="id,username")
            print(f"@{me.get('username')} ({me['id']})")
        else:
            refresh()
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
