#!/usr/bin/env python3
"""컨셉 그림 — 게임이 어떻게 보일지를 사용자와 맞추려고 그리는 그림. 게임에 들어가는 에셋이 아니다 (그것은 asset 스킬이 한다).

  python3 concept.py new <이름> [--size 1024x1536] [--ref <그림>] "<무엇을 그리나 — 영어로>"
  python3 concept.py list          있는 그림과 그것을 그린 글

그림은 docs/concept/<이름>.png 에, 그린 글은 옆의 <이름>.json 에 놓인다. **있는 이름은 덮어쓰지 않는다** — 고쳐 그린 것도 새 이름이다 (앞의 것과 견주어 볼 수 있게).
--size 는 화면의 방향이다: 세로 1024x1536 (기본) · 가로 1536x1024 · 정사각 1024x1024.
--ref 는 사용자가 마음에 든 그림이다 (경로, 또는 이미 있는 컨셉의 이름) — 그 그림을 보여 주며 그리게 해서, 마음에 든 것은 남고 말한 것만 바뀐다.

모델과 품질은 kit.config.json 의 asset.image 를 쓴다. 키는 저장소 밖에 둔다 — 환경 변수 OPENAI_API_KEY, 없으면 asset.env_file
(기본 ~/.config/gamedev-kit/asset.env) 안의 같은 이름 줄. 한 장마다 돈이 든다 — 몇 장을 그릴지는 스킬이 사용자에게 먼저 말한다.
"""
import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
import uuid

CONFIG_NAME = "kit.config.json"
DIR = os.path.join("docs", "concept")
IMAGE = {"model": "gpt-image-2.5-flare", "quality": "medium"}  # asset.image 에 적힌 것이 이긴다
ENV_FILE = "~/.config/gamedev-kit/asset.env"
SIZE = "1024x1536"
OPENAI = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")  # 테스트가 바꾼다
KEEP = ("The attached image is the picture to keep: the same composition, palette, shapes and mood. "
        "Change only what is asked below and leave everything else as it is.")

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


def key(name):
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.expanduser(CFG.get("env_file") or ENV_FILE)
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == name and v:
                return v.strip("\"'")
    sys.exit(f"{name} 가 없다 — {path} 에 `{name}=...` 한 줄을 적는다 (사용자가 한다. 키는 저장소에 두지 않는다)")


def http(url, token, body, content_type="application/json"):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": content_type}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(text)
            text = err["error"]["message"] if isinstance(err.get("error"), dict) else err.get("message", text)
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        sys.exit(f"{url} → {e.code}: {str(text)[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"{url} → {e.reason}")


def multipart(fields, path):
    mark = uuid.uuid4().hex
    parts = [f'--{mark}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{mark}\r\nContent-Disposition: form-data; name="image[]"; filename="{os.path.basename(path)}"\r\n'
                 f"Content-Type: {mimetypes.guess_type(path)[0] or 'image/png'}\r\n\r\n".encode() + open(path, "rb").read() + b"\r\n")
    return b"".join(parts) + f"--{mark}--\r\n".encode(), f"multipart/form-data; boundary={mark}"


def picture(name):
    return os.path.join(ROOT, DIR, f"{name}.png")


def find_ref(ref):
    """경로(지금 폴더 · 게임 루트 기준)이거나 이미 있는 컨셉의 이름."""
    for path in (ref, os.path.join(ROOT, ref), picture(ref)):
        if os.path.isfile(path):
            return os.path.abspath(path)
    sys.exit(f"레퍼런스가 없다: {ref} — 경로(게임 루트 기준)나 있는 컨셉의 이름을 적는다 (`list`)")


def cmd_new(name, size, ref, prompt):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        sys.exit(f"이름은 소문자 · 숫자 · 밑줄 · 붙임표다: {name!r}")
    if not re.fullmatch(r"\d+x\d+", size):
        sys.exit(f"--size 는 1024x1536 꼴이다: {size!r}")
    out = picture(name)
    if os.path.exists(out):
        sys.exit(f"{os.path.relpath(out, ROOT)} 가 이미 있다 — 덮어쓰지 않는다. 고쳐 그리는 것도 새 이름으로 한다 ({name}_2 처럼)")
    prompt = " ".join(prompt.split())
    image = dict(IMAGE, **{k: v for k, v in (CFG.get("image") or {}).items() if k in IMAGE})
    fields = dict(image, size=size, output_format="png")
    if ref:
        src = find_ref(ref)
        body, ctype = multipart(dict(fields, prompt=f"{KEEP} {prompt}"), src)
        raw = http(f"{OPENAI}/images/edits", key("OPENAI_API_KEY"), body, ctype)
    else:
        raw = http(f"{OPENAI}/images/generations", key("OPENAI_API_KEY"), json.dumps(dict(fields, prompt=prompt)).encode())
    data = base64.b64decode(json.loads(raw)["data"][0]["b64_json"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "wb").write(data)
    with open(out[:-4] + ".json", "w", encoding="utf-8") as f:
        json.dump(dict(image, name=name, size=size, ref=os.path.relpath(src, ROOT) if ref else None, prompt=prompt), f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{os.path.relpath(out, ROOT)} — 사용자가 열어 본다 (이 세션에서 읽지 않는다)")


def cmd_list():
    d = os.path.join(ROOT, DIR)
    names = sorted(n for n in os.listdir(d) if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))) if os.path.isdir(d) else []
    if not names:
        return print(f"{DIR}/ 에 그림이 없다")
    for n in names:
        note = os.path.join(d, os.path.splitext(n)[0] + ".json")
        if not os.path.exists(note):
            print(f"{DIR}/{n} — 사용자가 넣은 그림")
            continue
        rec = json.load(open(note, encoding="utf-8"))
        print(f"{DIR}/{n} — {rec.get('size', '')}" + (f" · {rec['ref']} 에서 고쳐 그림" if rec.get("ref") else "") + f" · {rec.get('prompt', '')}")


def main():
    global ROOT, CFG
    args = sys.argv[1:]
    root = None
    if "--root" in args:  # 테스트용
        i = args.index("--root")
        root = args[i + 1]
        del args[i:i + 2]
    opts = {"--size": SIZE, "--ref": ""}
    for flag in opts:
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    ROOT = os.path.abspath(root) if root else find_root(os.getcwd())
    CFG = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get("asset") or {}
    if args == ["list"]:
        cmd_list()
    elif len(args) == 3 and args[0] == "new":
        cmd_new(args[1], opts["--size"], opts["--ref"], args[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
