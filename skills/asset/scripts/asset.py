#!/usr/bin/env python3
"""에셋 — 설명 한 줄에서 게임에 넣을 3D 모델까지: 이미지(OpenAI) → 승인 → 메쉬(Meshy) → 다듬기(Blender).

  python3 asset.py new <이름> --size <미터> [--poly <삼각형 수>] [--ref <사진> [--as-is]] "<무엇인지 — 영어로>"
  python3 asset.py image <이름>... [--view back] [--ref <사진>]   이미지를 만든다. --view 면 그 면만 다시
  python3 asset.py approve <이름>...               사람이 이미지를 보고 난 뒤. 승인한 이미지만 메쉬가 된다
  python3 asset.py reject <이름> "<사용자의 말>"   물린다 — 왜 물렸는지를 기록에 남기고 승인을 푼다
  python3 asset.py learn "<한 줄 — 영어로>"        물리며 배운 것을 "배운 것" 에 한 줄 보탠다. 그 뒤 모든 에셋에 붙는다
  python3 asset.py look                            모든 에셋에 붙는 글 — 화풍 · 세계 · 배운 것
  python3 asset.py mesh <이름>...                  Meshy 로 메쉬를 만들고 받아서 다듬는다. 크레딧이 든다
  python3 asset.py finish <이름>... [--size <미터>]  받은 메쉬를 다시 다듬는다 (크기 · 원점 · 내보내기)
  python3 asset.py status                          에셋마다 어디까지 왔는지

에셋 하나가 폴더 하나다: <work>/<이름>/ 에 기록(asset.json) · 면마다 이미지 · 받은 메쉬(raw.glb).
끝난 모델은 <dir>/<이름>.<format> 에 놓인다. 크기는 가장 긴 변의 길이(미터), 원점은 바닥 가운데.

모든 프롬프트에 붙는 글은 asset.style_file(기본 docs/DESIGN.md)에 세 겹으로 있다:
  `<!-- asset-style -->`    화풍 — 어떻게 그리나. 고정이다 (바꾸면 이미 만든 에셋과 어긋난다)
  `<!-- asset-world -->`    세계 — 이 세계에 무엇이 있나 (시대 · 재질 · 되풀이되는 무늬). 없어도 된다
  `<!-- asset-learned -->`  배운 것 — 물리며 사용자가 한 말에서 나온 줄들. `learn` 이 보탠다. 없어도 된다
설정은 프로젝트 루트 kit.config.json 의 "asset".

--ref 는 그 에셋의 레퍼런스 사진이다 (루트 기준 경로) — 글로 옮기지 않고 사진을 그대로 보여 주며 그리게 한다.
--as-is 면 다시 그리지 않고 그 사진을 첫 면으로 쓴다 (png 여야 한다. 화풍은 사진의 것이 된다).

키는 저장소 밖에 둔다 — 환경 변수 OPENAI_API_KEY · MESHY_API_KEY, 없으면 asset.env_file
(기본 ~/.config/gamedev-kit/asset.env) 안의 같은 이름 줄.
"""
import base64
import datetime
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

CONFIG_NAME = "kit.config.json"
SECTION = "asset"
DEFAULTS = {
    "dir": "",                     # 끝난 모델이 놓이는 폴더 (루트 기준)
    "format": "glb",               # glb | fbx
    "work": "assets/_gen",         # 에셋마다 기록과 중간 파일
    "style_file": "docs/DESIGN.md",
    "refs": [],                    # 화풍 기준 이미지 (루트 기준 경로). 있으면 모든 첫 이미지에 같이 들어간다
    "views": ["front", "back"],    # 만들 면. 첫 면이 기준이고 나머지는 그것을 보고 그린다. 넷까지
    "image": {"model": "gpt-image-2.5-flare", "size": "1024x1024", "quality": "medium"},
    "meshy": {"ai_model": "latest", "target_polycount": 5000, "topology": "triangle", "enable_pbr": False},
    "blender": "blender",
    "env_file": "~/.config/gamedev-kit/asset.env",
}
OPENAI = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")  # 테스트가 바꾼다
MESHY = os.environ.get("MESHY_API_BASE", "https://api.meshy.ai/openapi/v1")
POLL = float(os.environ.get("ASSET_POLL_SEC", "10"))
WAIT = 30 * 60
FINISH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_finish.py")

VIEWS = {
    "front": "front view, straight on, camera at the object's mid height",
    "back": "back view, seen from directly behind, camera at the object's mid height",
    "left": "left side view, exact profile, camera at the object's mid height",
    "right": "right side view, exact profile, camera at the object's mid height",
}
# 이미지가 메쉬가 되려면 지켜야 하는 것. 화풍과 상관없이 늘 붙는다
FOR_3D = ("A single object, centered, the whole object inside the frame with a margin around it. "
          "Transparent background. Flat, even, neutral lighting — no cast shadows, no ground, no rim light. "
          "No text, no labels, no other objects.")
SAME = "The same object as in the first image — identical shape, proportions, colors and materials — shown in"
STYLE_ONLY = "Use the attached images only as a style reference (palette, shading, level of detail); do not copy their subjects."
SUBJECT_REF = ("The first attached image shows the subject: redraw this exact object — the same silhouette, proportions, colours and "
               "distinctive details — in the style described below.")
STYLE_REST = "The other attached images are style references only (palette, shading, level of detail); do not copy their subjects."
OPEN, CLOSE = "<!-- asset-style -->", "<!-- /asset-style -->"
WORLD = ("<!-- asset-world -->", "<!-- /asset-world -->")
LEARNED = ("<!-- asset-learned -->", "<!-- /asset-learned -->")
LEARN_MAX = 12  # 이보다 길어지면 뒤쪽 줄이 먹지 않는다 — 합친다

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
    for key in ("image", "meshy"):  # 일부만 적어도 나머지는 기본값
        CFG[key] = dict(DEFAULTS[key], **have.get(key, {}))
    if not CFG["dir"]:
        sys.exit(f"{CONFIG_NAME} 의 {SECTION}.dir 이 비어 있다 — 모델을 놓을 폴더를 적는다 (asset 스킬의 설정 절)")
    bad = [v for v in CFG["views"] if v not in VIEWS]
    if bad or not 1 <= len(CFG["views"]) <= 4:
        sys.exit(f"{SECTION}.views 는 " + " · ".join(VIEWS) + " 중 하나에서 넷까지다")


def key(name):
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.expanduser(CFG["env_file"])
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == name and v:
                return v.strip("\"'")
    sys.exit(f"{name} 가 없다 — {path} 에 `{name}=...` 한 줄을 적는다 (asset 스킬의 '처음 한 번')")


def http(url, token=None, body=None, content_type="application/json"):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if body is not None:
        headers["Content-Type"] = content_type
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
        raise RuntimeError(f"{url.split('?')[0]} → {e.code}: {str(text)[:500]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"{url.split('?')[0]} → {e.reason}")


# ── 기록 ──────────────────────────────────────────────────────────────

def folder(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
        sys.exit(f"이름은 소문자 · 숫자 · 밑줄이다: {name!r}")
    return os.path.join(ROOT, CFG["work"], name)


def load(name):
    path = os.path.join(folder(name), "asset.json")
    if not os.path.exists(path):
        sys.exit(f"{name}: 기록이 없다 — asset.py new {name} --size <미터> \"<무엇인지>\"")
    return json.load(open(path, encoding="utf-8"))


def save(rec):
    path = os.path.join(folder(rec["name"]), "asset.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")


def sha(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()


def image_path(name, view):
    return os.path.join(folder(name), f"{view}.png")


def out_path(name):
    return os.path.join(ROOT, CFG["dir"], f"{name}.{CFG['format']}")


def approved(rec):
    """승인한 그 이미지들이 지금도 그대로인가."""
    marks = rec.get("approved") or {}
    return bool(marks) and list(marks) == CFG["views"] and all(
        os.path.exists(image_path(rec["name"], v)) and sha(image_path(rec["name"], v)) == h for v, h in marks.items())


def stage(rec):
    if rec.get("out") and os.path.exists(os.path.join(ROOT, rec["out"])):
        return "끝"
    task = rec.get("meshy") or {}
    if task.get("status") == "SUCCEEDED":
        return "메쉬 받음 — finish"
    if task.get("id") and task.get("status") not in ("FAILED", "CANCELED"):
        return "메쉬 만드는 중 — mesh 로 잇는다"
    if approved(rec):
        return "승인 — mesh"
    if all(os.path.exists(image_path(rec["name"], v)) for v in CFG["views"]):
        return "이미지 — 보고 approve"
    return "새로 — image"


# ── 이미지 ────────────────────────────────────────────────────────────

def style():
    path = os.path.join(ROOT, CFG["style_file"])
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    if OPEN not in text or CLOSE not in text:
        sys.exit(f"{CFG['style_file']} 에 `{OPEN}` … `{CLOSE}` 가 없다 — 그 사이에 이 게임의 화풍을 영어 한 문단으로 적는다")
    block = " ".join(text.split(OPEN, 1)[1].split(CLOSE, 1)[0].split())
    if not block:
        sys.exit(f"{CFG['style_file']} 의 화풍 문단이 비어 있다")
    return block


def between(marks):
    """style_file 에서 두 표식 사이의 글. 표식이 없으면 None."""
    path = os.path.join(ROOT, CFG["style_file"])
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    return text.split(marks[0], 1)[1].split(marks[1], 1)[0] if marks[0] in text and marks[1] in text else None


def learned():
    return [re.sub(r"^[-*]\s*", "", line.strip()) for line in (between(LEARNED) or "").split("\n") if line.strip()]


def look():
    """모든 에셋에 붙는 글: 화풍(고정) + 세계 + 배운 것."""
    world = " ".join((between(WORLD) or "").split())
    rules = " ".join(line.rstrip(".") + "." for line in learned())
    return " ".join(x for x in (style(), world, rules) if x)


def multipart(fields, files):
    mark = uuid.uuid4().hex
    parts = [f'--{mark}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    for path in files:
        parts.append(f'--{mark}\r\nContent-Disposition: form-data; name="image[]"; filename="{os.path.basename(path)}"\r\n'
                     f"Content-Type: {mimetypes.guess_type(path)[0] or 'image/png'}\r\n\r\n".encode() + open(path, "rb").read() + b"\r\n")
    return b"".join(parts) + f"--{mark}--\r\n".encode(), f"multipart/form-data; boundary={mark}"


def draw(prompt, inputs):
    """이미지 한 장. inputs 가 있으면 그것을 보고 그린다."""
    fields = dict(CFG["image"], prompt=prompt, background="transparent", output_format="png")
    if inputs:
        body, ctype = multipart(fields, inputs)
        raw = http(f"{OPENAI}/images/edits", key("OPENAI_API_KEY"), body, ctype)
    else:
        raw = http(f"{OPENAI}/images/generations", key("OPENAI_API_KEY"), json.dumps(fields).encode())
    return base64.b64decode(json.loads(raw)["data"][0]["b64_json"])


def image(name, only, ref=None):
    rec, words = load(name), look()
    if ref:
        rec["ref"] = ref
    subject = os.path.join(ROOT, rec["ref"]) if rec.get("ref") else ""
    if subject and not os.path.exists(subject):
        sys.exit(f"{name}: 레퍼런스가 없다 — {rec['ref']} (게임 루트 기준 경로)")
    refs = [os.path.join(ROOT, r) for r in CFG["refs"]]
    for r in refs:
        if not os.path.exists(r):
            sys.exit(f"{SECTION}.refs: {os.path.relpath(r, ROOT)} 가 없다")
    first = CFG["views"][0]
    todo = [only] if only else CFG["views"]
    if only and only not in CFG["views"]:
        sys.exit(f"{only}: 설정의 면이 아니다 — " + " · ".join(CFG["views"]))
    if first not in todo and not os.path.exists(image_path(name, first)):
        sys.exit(f"{name}: 기준 면({first}) 이미지가 먼저 있어야 한다")
    for view in todo:
        if view == first and subject and rec.get("as_is"):
            prompt, data = f"(레퍼런스를 그대로 썼다: {rec['ref']})", open(subject, "rb").read()
        elif view == first:
            lead = f"{SUBJECT_REF} " + (f"{STYLE_REST} " if refs else "") if subject else (f"{STYLE_ONLY} " if refs else "")
            prompt = f"{lead}{rec['subject']}. {VIEWS[view].capitalize()}. {words} {FOR_3D}"
            data = draw(prompt, ([subject] if subject else []) + refs)
        else:
            prompt = f"{SAME} {VIEWS[view]}. {words} {FOR_3D}"
            data = draw(prompt, [image_path(name, first)])
        os.makedirs(folder(name), exist_ok=True)
        open(image_path(name, view), "wb").write(data)
        rec.setdefault("prompts", {})[view] = prompt
        print(f"{name}: {os.path.relpath(image_path(name, view), ROOT)}", flush=True)
    rec["approved"] = None  # 이미지가 바뀌면 승인도 다시
    rec["image"] = dict(CFG["image"], refs=CFG["refs"], style=hashlib.sha1(style().encode()).hexdigest()[:8])  # 어느 화풍으로 그렸나
    save(rec)


def reject(name, said):
    """사용자가 물렸다 — 그 말이 "배운 것" 의 재료다. 승인을 푼다."""
    rec = load(name)
    rec.setdefault("said", []).append({"date": str(datetime.date.today()), "said": " ".join(said.split())})
    rec["approved"] = None
    save(rec)
    print(f"{name}: 물림을 적었다 ({len(rec['said'])}번째). 다른 에셋에도 맞는 말이면 `learn` 으로 한 줄 보탠다")


def learn(line):
    path = os.path.join(ROOT, CFG["style_file"])
    if between(LEARNED) is None:
        sys.exit(f"{CFG['style_file']} 에 `{LEARNED[0]}` … `{LEARNED[1]}` 가 없다 — 화풍 문단 아래에 그 두 줄을 넣는다")
    have = learned()
    if len(have) >= LEARN_MAX:
        sys.exit(f"배운 것이 {len(have)}줄이다 — 더 보태지 않는다. 겹치는 줄을 합치거나, 늘 맞는 말이면 화풍 문단으로 올린다 (사용자와)")
    text = open(path, encoding="utf-8").read()
    head, tail = text.split(LEARNED[0], 1)[0], text.split(LEARNED[1], 1)[1]
    lines = have + [" ".join(line.split()).rstrip(".")]
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + LEARNED[0] + "\n" + "\n".join(f"- {x}" for x in lines) + "\n" + LEARNED[1] + tail)
    print(f"배운 것 {len(lines)}줄 — 이제부터 그리는 에셋에 붙는다:\n" + "\n".join(f"- {x}" for x in lines))


def approve(name):
    rec = load(name)
    missing = [v for v in CFG["views"] if not os.path.exists(image_path(name, v))]
    if missing:
        sys.exit(f"{name}: 이미지가 없다 ({' · '.join(missing)}) — asset.py image {name}")
    rec["approved"] = {v: sha(image_path(name, v)) for v in CFG["views"]}
    save(rec)
    print(f"{name}: 승인 — " + " · ".join(CFG["views"]))


# ── 메쉬 ──────────────────────────────────────────────────────────────

def start(rec):
    name = rec["name"]
    urls = ["data:image/png;base64," + base64.b64encode(open(image_path(name, v), "rb").read()).decode()
            for v in CFG["views"]]
    body = dict(CFG["meshy"], image_urls=urls, should_remesh=True, should_texture=True, target_formats=["glb"])
    if rec.get("poly"):
        body["target_polycount"] = rec["poly"]
    made = json.loads(http(f"{MESHY}/multi-image-to-3d", key("MESHY_API_KEY"), json.dumps(body).encode()))["result"]
    rec["meshy"] = {"id": made, "status": "PENDING", "params": {k: v for k, v in body.items() if k != "image_urls"},
                    "images": dict(rec["approved"])}
    save(rec)  # 만들자마자 적는다 — 끊겨도 같은 작업을 다시 사지 않게
    print(f"{name}: Meshy 작업 {made}", flush=True)


def mesh(names):
    recs = [load(n) for n in names]
    for rec in recs:
        if not approved(rec):
            sys.exit(f"{rec['name']}: 승인된 이미지가 없다 — 사람이 이미지를 보고 난 뒤 asset.py approve {rec['name']}")
    for rec in recs:
        task = rec.get("meshy") or {}
        fresh = task.get("images") == rec["approved"]  # 지금 승인된 이미지로 만든 작업인가
        if not (fresh and task.get("id") and task.get("status") not in ("FAILED", "CANCELED")):
            start(rec)
    waiting, failed, until = [r for r in recs if r["meshy"]["status"] != "SUCCEEDED"], [], time.time() + WAIT
    while waiting:
        for rec in list(waiting):
            task = json.loads(http(f"{MESHY}/multi-image-to-3d/{rec['meshy']['id']}", key("MESHY_API_KEY")))
            rec["meshy"]["status"] = task["status"]
            if task["status"] == "SUCCEEDED":
                rec["meshy"]["credits"] = task.get("consumed_credits")
                open(os.path.join(folder(rec["name"]), "raw.glb"), "wb").write(http(task["model_urls"]["glb"]))
                print(f"{rec['name']}: 메쉬 받음 (크레딧 {task.get('consumed_credits', '?')})", flush=True)
            elif task["status"] in ("FAILED", "CANCELED"):
                rec["meshy"]["error"] = (task.get("task_error") or {}).get("message", "")
                failed.append(f"{rec['name']}: {task['status']} {rec['meshy']['error']}")
            else:
                print(f"{rec['name']}: {task['status']} {task.get('progress', 0)}%", flush=True)
                continue
            save(rec)
            waiting.remove(rec)
        if waiting:
            if time.time() > until:
                for rec in waiting:
                    save(rec)
                sys.exit("아직 안 끝났다: " + " · ".join(r["name"] for r in waiting) + " — 같은 mesh 명령을 다시 돌리면 이어서 기다린다")
            time.sleep(POLL)
    for rec in recs:
        if rec["meshy"]["status"] == "SUCCEEDED":
            finish(rec["name"], None)
    if failed:
        sys.exit("Meshy 실패 (크레딧은 돌아온다):\n- " + "\n- ".join(failed))


def finish(name, size):
    rec = load(name)
    raw = os.path.join(folder(name), "raw.glb")
    if not os.path.exists(raw):
        sys.exit(f"{name}: 받은 메쉬가 없다 — asset.py mesh {name}")
    if size:
        rec["size"] = size
    if not shutil.which(CFG["blender"]):
        sys.exit(f"Blender 가 없다 ({CFG['blender']}) — 깔거나 {SECTION}.blender 에 실행 파일 경로를 적는다")
    out = out_path(name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    p = subprocess.run([CFG["blender"], "--background", "--factory-startup", "--python", FINISH, "--",
                        raw, out, str(rec["size"]), CFG["format"]], capture_output=True, text=True)
    done = re.search(r"^FINISH (.*)$", p.stdout, re.M)
    if p.returncode != 0 or not done or not os.path.exists(out):
        sys.exit(f"{name}: 다듬기 실패\n{(p.stdout + p.stderr).strip()[-2000:]}")
    rec["out"] = os.path.relpath(out, ROOT)
    rec["finished"] = dict(json.loads(done.group(1)), date=str(datetime.date.today()))
    save(rec)
    f = rec["finished"]
    print(f"{name}: {rec['out']} — 삼각형 {f['tris']} · {' × '.join(str(x) for x in f['size'])} m · "
          f"{os.path.getsize(out) / 1e6:.1f} MB")


def status():
    work = os.path.join(ROOT, CFG["work"])
    names = sorted(n for n in os.listdir(work) if os.path.exists(os.path.join(work, n, "asset.json"))) \
        if os.path.isdir(work) else []
    if not names:
        print("에셋이 없다 — asset.py new <이름> --size <미터> \"<무엇인지>\"")
    for n in names:
        rec = load(n)
        print(f"{n:<24} {stage(rec):<28} {rec['size']} m · {rec['subject'][:50]}")


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--size", "--poly", "--view", "--ref"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    as_is = "--as-is" in args
    args = [a for a in args if a != "--as-is"]
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd not in ("new", "image", "approve", "reject", "learn", "look", "mesh", "finish", "status") or (cmd not in ("status", "look") and not rest):
        sys.exit(__doc__)
    setup(opts.get("--root"))
    ref = opts.get("--ref")
    if ref and not os.path.exists(os.path.join(ROOT, ref)):
        sys.exit(f"{ref}: 레퍼런스가 없다 (게임 루트 기준 경로)")
    if as_is and (cmd != "new" or not ref or not ref.lower().endswith(".png")):
        sys.exit("--as-is 는 new 에서, png 인 --ref 와 같이 쓴다")
    try:
        size = float(opts["--size"]) if "--size" in opts else None
        if size is not None and size <= 0:
            raise ValueError
        poly = int(opts["--poly"]) if "--poly" in opts else None
    except ValueError:
        sys.exit("--size 는 0 보다 큰 미터, --poly 는 삼각형 수다")
    try:
        if cmd == "new":
            if len(rest) != 2 or size is None:
                sys.exit(__doc__)
            name, subject = rest[0], rest[1].strip().rstrip(".")
            if os.path.exists(os.path.join(folder(name), "asset.json")):
                sys.exit(f"{name}: 이미 있다 — 다른 이름을 쓰거나 {os.path.relpath(folder(name), ROOT)}/asset.json 을 고친다")
            rec = {"name": name, "subject": subject, "size": size, "poly": poly, "created": str(datetime.date.today())}
            if ref:
                rec.update(ref=ref, as_is=as_is)
            save(rec)
            print(f"{name}: {os.path.relpath(folder(name), ROOT)}/asset.json" + (f" · 레퍼런스 {ref}" + (" (그대로 쓴다)" if as_is else "") if ref else ""))
        elif cmd == "image":
            for name in rest:
                image(name, opts.get("--view"), ref)
        elif cmd == "reject":
            if len(rest) != 2:
                sys.exit(__doc__)
            reject(*rest)
        elif cmd == "learn":
            learn(" ".join(rest))
        elif cmd == "look":
            print(f"화풍: {style()}\n세계: {' '.join((between(WORLD) or '').split()) or '(없다)'}\n배운 것: " + (" / ".join(learned()) or "(없다)")
                  + f"\n— 모든 에셋에 {len(look())}자가 붙는다")
        elif cmd == "approve":
            for name in rest:
                approve(name)
        elif cmd == "mesh":
            mesh(rest)
        elif cmd == "finish":
            for name in rest:
                finish(name, size)
        else:
            status()
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
