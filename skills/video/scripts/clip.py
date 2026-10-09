#!/usr/bin/env python3
"""클립 — 설명 한 줄에서 찍은 듯한 영상까지: 설명(· 기준 그림) → 승인 → 생성(Higgsfield) → 사람이 본다 → 게임 폴더나 문서 폴더.

  python3 clip.py check                                    돌릴 수 있는가: 키 · 모델 · 놓을 곳 · 화면의 결 문단
  python3 clip.py new <이름> --for game|page [--seconds <초>] [--size landscape|portrait|square] [--image <그림>]... "<무슨 장면인지 — 영어로>"
  python3 clip.py approve <이름>...                        사람이 설명과 기준 그림을 보고 난 뒤. 승인한 것만 만든다
  python3 clip.py make <이름>... [--again]                 Higgsfield 로 만들고 받는다. 크레딧이 든다. 만들던 것은 이어서 기다린다
  python3 clip.py place <이름>...                          사람이 영상을 보고 난 뒤. 쓰이는 곳에 놓는다
  python3 clip.py status                                   클립마다 어디까지 왔는지

클립 하나가 폴더 하나다: <work>/<이름>/ 에 기록(clip.json) · 받은 영상(clip.mp4).
쓰이는 곳이 둘이다 — page 는 게임 밖이라 mp4 그대로 <page.dir> 에, game 은 엔진이 읽는 형식으로 바꿔(<game.convert>) <game.dir> 에 놓는다.

모델은 설정이 정한다 — video.clip.model 이 Higgsfield 의 엔드포인트 ID 이고, 모델마다 다른 입력 이름은 video.clip.fields 에,
늘 같이 보낼 값은 video.clip.params 에 적는다. 화면의 결은 video.style_file(기본 docs/DESIGN.md)의
`<!-- footage-style -->` 와 `<!-- /footage-style -->` 사이 — 있으면 모든 설명 뒤에 그대로 붙는다.

키는 저장소 밖에 둔다 — 환경 변수 HF_API_KEY_ID · HF_API_KEY_SECRET, 없으면 video.env_file
(기본 ~/.config/gamedev-kit/asset.env) 안의 같은 이름 줄.
"""
import datetime
import hashlib
import json
import mimetypes
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

CONFIG_NAME = "kit.config.json"
SECTION = "video"
DEFAULTS = {
    "work": "video",
    "style_file": "docs/DESIGN.md",
    "ffmpeg": "ffmpeg",
    "size": "landscape",
    "page": {"dir": "docs/video"},
    "game": {"dir": "", "ext": "", "convert": []},
    "env_file": "~/.config/gamedev-kit/asset.env",
    "clip": {
        "model": "higgsfield/cinema-studio/4.0",   # 엔드포인트 ID — 콘솔에서 고른 모델의 문서에 있다
        "seconds": 5,
        "params": {},                              # 늘 같이 보낼 값 (resolution · generate_audio …)
        # 이 도구의 말 → 그 모델의 입력 이름. 비우면 보내지 않는다. 그림은 images(여러 장) 나 image(한 장) 가운데 모델이 받는 쪽
        "fields": {"prompt": "prompt", "seconds": "duration", "aspect": "aspect_ratio", "images": "image_urls", "image": ""},
    },
}
API = os.environ.get("HIGGSFIELD_API_BASE", "https://api.higgsfield.ai")  # 테스트가 바꾼다
POLL = float(os.environ.get("VIDEO_POLL_SEC", "2"))
WAIT = 30 * 60
ASPECT = {"landscape": "16:9", "portrait": "9:16", "square": "1:1"}
OPEN, CLOSE = "<!-- footage-style -->", "<!-- /footage-style -->"
DONE = ("completed", "failed", "nsfw", "canceled")

ROOT = ""
CFG = {}


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
    clip = have.get("clip", {})
    CFG["clip"] = dict(DEFAULTS["clip"], **clip)
    CFG["clip"]["fields"] = dict(DEFAULTS["clip"]["fields"], **clip.get("fields", {}))


def key(name, need=True):
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.expanduser(CFG["env_file"])
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == name and v:
                return v.strip("\"'")
    if need:
        sys.exit(f"{name} 가 없다 — {path} 에 `{name}=...` 한 줄을 적는다 (video 스킬의 '처음 한 번')")
    return ""


def http(url, body=None, headers=None, method=None, auth=True):
    """Higgsfield 에는 키를 붙이고, 올리는 곳 · 받는 곳(저장소 · CDN)에는 붙이지 않는다."""
    headers = dict(headers or {})
    if auth:
        headers["Authorization"] = f"Key {key('HF_API_KEY_ID')}:{key('HF_API_KEY_SECRET')}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(text)
            text = err.get("detail") or err.get("message") or err.get("error") or text
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(f"{url.split('?')[0]} → {e.code}: {str(text)[:500]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"{url.split('?')[0]} → {e.reason}")


# ── 기록 ──────────────────────────────────────────────────────────────

def folder(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
        sys.exit(f"이름은 소문자 · 숫자 · 밑줄이다: {name!r}")
    return os.path.join(ROOT, CFG["work"], name)


def load(name):
    path = os.path.join(folder(name), "clip.json")
    if not os.path.exists(path):
        sys.exit(f"{name}: 기록이 없다 — clip.py new {name} --for game|page \"<무슨 장면인지>\"")
    return json.load(open(path, encoding="utf-8"))


def save(rec):
    os.makedirs(folder(rec["name"]), exist_ok=True)
    with open(os.path.join(folder(rec["name"]), "clip.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")


def style():
    path = os.path.join(ROOT, CFG["style_file"])
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    return " ".join(text.split(OPEN, 1)[1].split(CLOSE, 1)[0].split()) if OPEN in text and CLOSE in text else ""


def prompt(rec):
    return " ".join(f"{rec['what'].rstrip('.')}. {style()}".split())


def mark(rec):
    """무엇을 만들지가 바뀌면 달라지는 값 — 승인은 이 값에 걸린다."""
    shas = [hashlib.sha1(open(os.path.join(ROOT, p), "rb").read()).hexdigest() for p in rec["images"]]
    seed = json.dumps([prompt(rec), rec["seconds"], rec["size"], shas, CFG["clip"]["model"], CFG["clip"]["params"]], ensure_ascii=False)
    return hashlib.sha1(seed.encode()).hexdigest()[:12]


def stage(rec):
    if rec.get("out") and rec.get("made", {}).get("mark") == mark(rec):
        return f"놓았다 — {rec['out']}"
    if rec.get("made", {}).get("mark") == mark(rec):
        return "사람이 볼 차례 — 본 뒤 place"
    if rec.get("request", {}).get("mark") == mark(rec):
        return "만드는 중 — make 가 이어서 기다린다"
    if rec.get("approved") == mark(rec):
        return "만들 차례 — make (크레딧이 든다)"
    return "승인을 기다린다 — 설명" + (" · 기준 그림" if rec["images"] else "") + "을 사람이 본다"


# ── 만들기 ────────────────────────────────────────────────────────────

def upload(path):
    ctype = mimetypes.guess_type(path)[0] or "image/png"
    made = json.loads(http(f"{API}/files/generate-upload-url", json.dumps({"content_type": ctype}).encode(),
                           {"Content-Type": "application/json"}))
    http(made["upload_url"], open(path, "rb").read(), made.get("upload_headers") or {"Content-Type": ctype}, method="PUT", auth=False)
    return made["public_url"]


def body(rec):
    clip, out = CFG["clip"], dict(CFG["clip"]["params"])
    names = clip["fields"]
    values = {"prompt": prompt(rec), "seconds": rec["seconds"], "aspect": ASPECT[rec["size"]]}
    for word, value in values.items():
        if names.get(word):
            out[names[word]] = value
    if rec["images"]:
        if not names.get("images") and not names.get("image"):
            sys.exit(f"{rec['name']}: 기준 그림이 있는데 {SECTION}.clip.fields 의 images · image 가 비어 있다 — 이 모델이 그림을 받는 입력 이름을 적는다")
        urls = [upload(os.path.join(ROOT, p)) for p in rec["images"]]
        if names.get("images"):
            out[names["images"]] = urls
        else:
            out[names["image"]] = urls[0]
    return out


def make(name, again):
    rec = load(name)
    now = mark(rec)
    if rec.get("approved") != now:
        sys.exit(f"{name}: 승인이 없다 (승인한 뒤 설명 · 그림 · 모델이 바뀌었으면 다시) — 사람이 본 뒤 clip.py approve {name}")
    if rec.get("made", {}).get("mark") == now and not again:
        sys.exit(f"{name}: 이미 만들었다 — 같은 설명으로 한 번 더 뽑으려면 --again (크레딧이 또 든다)")
    req = rec.get("request", {})
    if req.get("mark") != now or (again and rec.get("made", {}).get("id") == req.get("id")):
        req = {"mark": now, "key": str(uuid.uuid4()), "model": CFG["clip"]["model"], "prompt": prompt(rec)}
        payload = body(rec)
        rec["request"] = req
        save(rec)  # 보내기 전에 적는다 — 끊겨도 같은 키로 다시 보내면 두 번 만들지 않는다
        sent = json.loads(http(f"{API}/{req['model']}", json.dumps(payload).encode(),
                               {"Content-Type": "application/json", "Idempotency-Key": req["key"]}))
        req.update(id=sent["request_id"], status_url=sent["status_url"])
        save(rec)
        print(f"{name}: 보냈다 — {req['model']} · {rec['seconds']}초")
    elif not req.get("status_url"):
        sys.exit(f"{name}: 보내다 끊겼다 — 기록의 request 를 지우고 다시 make")
    delay, until = POLL, time.time() + WAIT
    while True:
        state = json.loads(http(req["status_url"]))
        if state["status"] in DONE:
            break
        if time.time() > until:
            sys.exit(f"{name}: {WAIT // 60}분을 기다렸다 — 다시 make 하면 이어서 기다린다")
        time.sleep(delay)
        delay = min(delay * 1.5, max(POLL, 10.0)) if POLL >= 1 else POLL
    if state["status"] != "completed":
        del rec["request"]
        save(rec)
        why = {"nsfw": "내용 검사에 걸렸다 — 설명이나 그림을 고친다", "canceled": "취소됐다"}.get(state["status"], str(state.get("error") or "실패"))
        sys.exit(f"{name}: {why}")
    url = (state.get("video") or {}).get("url")
    if not url:
        sys.exit(f"{name}: 끝났는데 영상이 없다 — 이 모델은 영상을 내는 모델인가 ({req['model']})")
    mp4 = os.path.join(folder(name), "clip.mp4")
    with open(mp4, "wb") as f:
        f.write(http(url, auth=False))
    rec["made"] = {"mark": now, "id": req["id"], "date": str(datetime.date.today()), "model": req["model"], "prompt": req["prompt"]}
    rec.pop("out", None)
    save(rec)
    print(f"{name}: {os.path.relpath(mp4, ROOT)} — {os.path.getsize(mp4) / 1e6:.1f} MB\n움직임은 사용자가 본다 — 경로를 건넨다. 좋다고 하면 place")


def place(name):
    rec = load(name)
    mp4 = os.path.join(folder(name), "clip.mp4")
    if rec.get("made", {}).get("mark") != mark(rec) or not os.path.exists(mp4):
        sys.exit(f"{name}: 지금 설명으로 만든 영상이 없다 — clip.py make {name}")
    where = CFG[rec["for"]]
    ext = "mp4" if rec["for"] == "page" else where["ext"]
    if not where["dir"] or not ext or (rec["for"] == "game" and not where["convert"]):
        sys.exit(f"{CONFIG_NAME} 의 {SECTION}.{rec['for']} 가 덜 채워졌다 — dir" + (" · ext · convert" if rec["for"] == "game" else ""))
    out = os.path.join(ROOT, where["dir"], f"{name}.{ext}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if rec["for"] == "page":
        shutil.copyfile(mp4, out)
    elif subprocess.run(shlex.split(CFG["ffmpeg"]) + ["-y", "-i", mp4, *where["convert"], out], cwd=ROOT).returncode != 0 \
            or not os.path.exists(out):
        sys.exit(f"{name}: {ext} 로 바꾸지 못했다 — {SECTION}.game.convert 를 본다")
    rec["out"] = os.path.relpath(out, ROOT)
    save(rec)
    print(f"{name}: {rec['out']} — {os.path.getsize(out) / 1e6:.1f} MB")


def check():
    bad = [f"{n} 가 없다 — {os.path.expanduser(CFG['env_file'])} 에 `{n}=...`" for n in ("HF_API_KEY_ID", "HF_API_KEY_SECRET") if not key(n, need=False)]
    if not CFG["clip"]["model"]:
        bad.append(f"{SECTION}.clip.model 이 비어 있다 — Higgsfield 콘솔에서 고른 모델의 엔드포인트 ID")
    if not CFG["game"]["dir"] or not CFG["game"]["convert"]:
        bad.append(f"{SECTION}.game 이 덜 채워졌다 — 게임 안에서 트는 클립은 놓지 못한다 (page 는 된다)")
    print(f"모델: {CFG['clip']['model']} · 기본 {CFG['clip']['seconds']}초 · 늘 보내는 값 {json.dumps(CFG['clip']['params'], ensure_ascii=False)}")
    print("화면의 결: " + (style() or f"없다 — {CFG['style_file']} 의 `{OPEN}` … `{CLOSE}` 사이에 영어 한 문단 (없어도 돈다. 클립마다 결이 달라진다)"))
    print("\n".join(bad) if bad else "돌릴 수 있다")
    sys.exit(1 if bad else 0)


def status():
    base = os.path.join(ROOT, CFG["work"])
    names = sorted(n for n in os.listdir(base) if os.path.exists(os.path.join(base, n, "clip.json"))) if os.path.isdir(base) else []
    for n in names:
        rec = load(n)
        print(f"{n} ({rec['for']} · {rec['seconds']}초) — {stage(rec)}")
    if not names:
        print("클립이 없다")


def main():
    args = sys.argv[1:]
    opts, images = {}, []
    for flag in ("--root", "--for", "--seconds", "--size"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    while "--image" in args:
        i = args.index("--image")
        images.append(args[i + 1])
        del args[i:i + 2]
    again = "--again" in args
    args = [a for a in args if a != "--again"]
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd not in ("check", "new", "approve", "make", "place", "status") or (cmd in ("approve", "make", "place") and not rest):
        sys.exit(__doc__)
    setup(opts.get("--root"))
    if cmd == "check":
        check()
    elif cmd == "status":
        status()
    elif cmd == "new":
        if len(rest) != 2 or opts.get("--for") not in ("game", "page") or opts.get("--size", CFG["size"]) not in ASPECT:
            sys.exit(__doc__)
        for p in images:
            if not os.path.exists(os.path.join(ROOT, p)):
                sys.exit(f"{p}: 그림이 없다 (게임 루트 기준 경로)")
        old = load(rest[0]) if os.path.exists(os.path.join(folder(rest[0]), "clip.json")) else {}
        rec = dict(old, name=rest[0], what=" ".join(rest[1].split()), images=images, size=opts.get("--size", CFG["size"]),
                   seconds=int(opts.get("--seconds", CFG["clip"]["seconds"])))
        rec["for"] = opts["--for"]
        save(rec)
        print(f"{rec['name']}: {stage(rec)}\n보낼 설명: {prompt(rec)}")
    else:
        for name in rest:
            try:
                if cmd == "approve":
                    rec = load(name)
                    rec["approved"] = mark(rec)
                    save(rec)
                    print(f"{name}: 승인 — {rec['seconds']}초 · {CFG['clip']['model']}")
                elif cmd == "make":
                    make(name, again)
                else:
                    place(name)
            except RuntimeError as e:
                sys.exit(f"{name}: {e}")


if __name__ == "__main__":
    main()
