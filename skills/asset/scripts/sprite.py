#!/usr/bin/env python3
"""스프라이트 — 설명 한 줄에서 게임에 넣을 2D 그림과 움직이는 시트까지 (Ludo): 그림 → 승인 → 움직임.

  python3 sprite.py new <이름> [--type <종류>] [--ref <그림> [--as-is]] "<무엇인지 — 영어로>"
  python3 sprite.py image <이름>... [--ref <그림>]     멈춘 그림 한 장을 만든다
  python3 sprite.py approve <이름>...                  사람이 그림을 보고 난 뒤. 게임 폴더에 놓인다
  python3 sprite.py reject <이름> "<사용자의 말>"      물린다 — 왜 물렸는지를 기록에 남기고 승인을 푼다
  python3 sprite.py animate <이름> <동작> [--seconds <초>] [--frames <수>] "<어떤 움직임인지 — 영어로>"
                                                       승인한 그림을 움직여 시트로 만든다. 크레딧이 든다
  python3 sprite.py status                             스프라이트마다 어디까지 왔는지 · 시트의 칸
  python3 sprite.py credits                            남은 크레딧

스프라이트 하나가 폴더 하나다: <work>/<이름>/ 에 기록(sprite.json) · 멈춘 그림(still.png) · 동작마다 시트와 미리보기(<동작>.png · .gif).
승인한 그림은 <sprite.dir>/<이름>.png 에, 시트는 <sprite.dir>/<이름>_<동작>.png 에 놓인다. 같은 동작을 다시 만들면 시트를 덮는다.
시트의 칸(열 · 행 · 프레임 수 · 한 칸의 픽셀)은 기록에 적히고 status 가 보여 준다 — 엔진에서 자를 때 쓴다.

--type 은 Ludo 의 image_type 이다 (sprite · icon · ui_asset · tile · texture · item-icon · portrait …). 생략하면 설정의 것.
--ref 는 그 스프라이트의 레퍼런스 그림이다 (루트 기준 경로) — 글로 옮기지 않고 그림을 그대로 보여 주며 그리게 한다.
--as-is 면 다시 그리지 않고 그 그림을 멈춘 그림으로 쓴다 (png 여야 한다).

모든 설명 뒤에는 asset.py 와 같은 글(화풍 · 세계 · 배운 것)이 붙는다 — `asset.py look` · `asset.py learn`.
설정은 프로젝트 루트 kit.config.json 의 "asset" 안 "sprite".

키는 저장소 밖에 둔다 — 환경 변수 LUDO_API_KEY, 없으면 asset.env_file
(기본 ~/.config/gamedev-kit/asset.env) 안의 같은 이름 줄.
"""
import datetime
import hashlib
import json
import mimetypes
import os
import re
import shutil
import struct
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asset  # 같은 스킬의 것 — 루트 찾기 · 키 · 기록 폴더 · 모든 에셋에 붙는 글

SECTION = "sprite"
DEFAULTS = {
    "dir": "",                                   # 끝난 그림과 시트가 놓이는 폴더 (루트 기준)
    "style_ref": "",                             # 화풍 기준 그림 (루트 기준 경로). 있으면 모든 그림을 이것의 화풍에 맞춘다
    "view": "",                                  # 시점을 말로 — 모든 설명 뒤에 붙는다 (영어 한 줄)
    "image": {"image_type": "sprite"},           # Ludo 의 그림 요청에 그대로 (art_style · perspective · aspect_ratio 를 더해도 된다)
    "animate": {"model": "hydra", "duration": 3},  # Ludo 의 움직임 요청에 그대로 (frames · frame_size · loop 를 더해도 된다)
}
LUDO = os.environ.get("LUDO_API_BASE", "https://api.ludo.ai/api")  # 테스트가 바꾼다
KEY = "LUDO_API_KEY"
POLL = float(os.environ.get("ASSET_POLL_SEC", "2"))
WAIT = 30 * 60
DONE = ("succeeded", "failed", "canceled")
FRAMES = (4, 9, 16, 25, 36, 49, 64)

# 그림이 스프라이트로 쓰이려면 지켜야 하는 것. 화풍과 상관없이 늘 붙는다
FOR_2D = "A single subject, whole inside the frame with a margin around it. No text, no labels, no cast shadow, no ground."
SUBJECT_REF = ("The image shows the subject: redraw this exact subject — the same silhouette, proportions, colours and "
               "distinctive details — as described here.")

CFG = dict(DEFAULTS)


class Failed(RuntimeError):
    """Ludo 가 작업을 실패 · 취소로 끝냈다."""


def setup(root=None):
    global CFG
    asset.ROOT = os.path.abspath(root) if root else asset.find_root(os.getcwd())
    have = json.load(open(os.path.join(asset.ROOT, asset.CONFIG_NAME), encoding="utf-8")).get(asset.SECTION, {})
    asset.CFG = dict(asset.DEFAULTS, **have)
    mine = have.get(SECTION, {})
    CFG = dict(DEFAULTS, **mine)
    for key in ("image", "animate"):  # 일부만 적어도 나머지는 기본값
        CFG[key] = dict(DEFAULTS[key], **mine.get(key, {}))
    if not CFG["dir"]:
        sys.exit(f"{asset.CONFIG_NAME} 의 {asset.SECTION}.{SECTION}.dir 이 비어 있다 — 스프라이트를 놓을 폴더를 적는다 (asset 스킬의 설정 절)")


def http(url, body=None, method=None, auth=True, content_type="application/json"):
    headers = {"Authorization": f"ApiKey {asset.key(KEY)}"} if auth else {}  # 받은 주소(파일)에는 키를 보내지 않는다
    if body is not None:
        headers["Content-Type"] = content_type
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(text)
            text = err["error"]["message"] if isinstance(err.get("error"), dict) else err.get("message", text)
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        hint = " — 크레딧이 모자란다 (sprite.py credits)" if e.code == 402 else ""
        raise RuntimeError(f"{url.split('?')[0]} → {e.code}: {str(text)[:500]}{hint}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"{url.split('?')[0]} → {e.reason}")


def call(path, body=None):
    return json.loads(http(LUDO + path, None if body is None else json.dumps(body).encode()))


def upload(path):
    """게임의 그림을 Ludo 에 올리고 그 주소를 받는다."""
    data, mime = open(path, "rb").read(), mimetypes.guess_type(path)[0] or "image/png"
    slot = call("/assets/uploads", {"mime_type": mime, "size": len(data)})
    http(slot["upload_url"], data, method="PUT", auth=False, content_type=mime)
    return slot["file_url"]


def run(rec, slot, label, path, body):
    """작업 하나를 걸고 끝까지 기다린다 → (결과, 든 크레딧). 걸자마자 적는다 — 끊겨도 같은 작업을 다시 사지 않게."""
    job = slot.get("job") or {}
    if not (job.get("id") and job.get("status") not in DONE):
        made = call(path, body())
        if not (isinstance(made, dict) and made.get("id") and made.get("status")):
            return made, None  # 작업이 아니라 결과가 바로 왔다
        job = slot["job"] = {"id": made["id"], "status": made["status"]}
        save(rec)
        print(f"{label}: Ludo 작업 {job['id']}", flush=True)
    until = time.time() + WAIT
    while True:
        got = call(f"/assets/jobs/{job['id']}?wait=30")
        job["status"] = got["status"]
        if got["status"] in DONE:
            job["credits"] = got.get("credits_charged")
            save(rec)
            if got["status"] != "succeeded":
                raise Failed(f"{label}: Ludo {got['status']} — {(got.get('error') or {}).get('message', '')} (크레딧은 돌아온다)")
            return got.get("result"), got.get("credits_charged")
        print(f"{label}: {got['status']}", flush=True)
        if time.time() > until:
            sys.exit(f"{label}: 아직 안 끝났다 — 같은 명령을 다시 돌리면 이어서 기다린다")
        time.sleep(POLL)


# ── 기록 ──────────────────────────────────────────────────────────────

def load(name):
    path = os.path.join(asset.folder(name), "sprite.json")
    if not os.path.exists(path):
        sys.exit(f"{name}: 기록이 없다 — sprite.py new {name} \"<무엇인지>\"")
    return json.load(open(path, encoding="utf-8"))


def save(rec):
    path = os.path.join(asset.folder(rec["name"]), "sprite.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")


def still_path(name):
    return os.path.join(asset.folder(name), "still.png")


def rel(path):
    return os.path.relpath(path, asset.ROOT)


def approved(rec):
    """승인한 그 그림이 지금도 그대로인가."""
    path = still_path(rec["name"])
    return bool(rec.get("approved")) and os.path.exists(path) and asset.sha(path) == rec["approved"]


def png_size(path):
    head = open(path, "rb").read(24)
    return struct.unpack(">II", head[16:24]) if head[:8] == b"\x89PNG\r\n\x1a\n" else (0, 0)


def stage(rec):
    if approved(rec):
        return "승인 — animate 할 수 있다"
    if os.path.exists(still_path(rec["name"])):
        return "그림 — 보고 approve"
    return "새로 — image"


# ── 그림 ──────────────────────────────────────────────────────────────

def image(name, ref=None):
    rec, words = load(name), asset.look()
    if ref:
        rec["ref"] = ref
    subject = os.path.join(asset.ROOT, rec["ref"]) if rec.get("ref") else ""
    if subject and not os.path.exists(subject):
        sys.exit(f"{name}: 레퍼런스가 없다 — {rec['ref']} (게임 루트 기준 경로)")
    style_ref = os.path.join(asset.ROOT, CFG["style_ref"]) if CFG["style_ref"] else ""
    if style_ref and not os.path.exists(style_ref):
        sys.exit(f"{asset.SECTION}.{SECTION}.style_ref: {CFG['style_ref']} 가 없다")
    out, credits = still_path(name), None
    os.makedirs(asset.folder(name), exist_ok=True)
    if subject and rec.get("as_is"):
        prompt = f"(레퍼런스를 그대로 썼다: {rec['ref']})"
        shutil.copyfile(subject, out)
    else:
        view = CFG["view"].strip().rstrip(".")
        said = " ".join(x for x in (rec["subject"] + ".", view + "." if view else "", words, FOR_2D) if x)
        kind = {"image_type": rec.get("type") or CFG["image"]["image_type"]}
        if subject:
            prompt = f"{SUBJECT_REF} {said}"
            path, body = "/assets/image/edit", lambda: dict(kind, image=upload(subject), prompt=prompt,
                                                           **({"reference_image": upload(style_ref)} if style_ref else {}))
        elif style_ref:
            prompt = said
            path, body = "/assets/image/style", lambda: dict(kind, style_image=upload(style_ref), prompt=prompt)
        else:
            prompt = said
            path, body = "/assets/image", lambda: dict(CFG["image"], **kind, prompt=prompt)
        result, credits = run(rec, rec, name, path, body)
        open(out, "wb").write(http(result[0]["url"], auth=False))
    rec.setdefault("prompts", {})["still"] = prompt
    rec["approved"] = None  # 그림이 바뀌면 승인도 다시
    rec["image"] = dict(CFG["image"], style_ref=CFG["style_ref"], credits=credits,
                        style=hashlib.sha1(asset.style().encode()).hexdigest()[:8])  # 어느 화풍으로 그렸나
    save(rec)
    print(f"{name}: {rel(out)} — {' × '.join(str(x) for x in png_size(out))} px" + (f" · 크레딧 {credits}" if credits is not None else ""), flush=True)


def approve(name):
    rec = load(name)
    if not os.path.exists(still_path(name)):
        sys.exit(f"{name}: 그림이 없다 — sprite.py image {name}")
    out = os.path.join(asset.ROOT, CFG["dir"], f"{name}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copyfile(still_path(name), out)
    rec["approved"], rec["out"] = asset.sha(still_path(name)), rel(out)
    save(rec)
    print(f"{name}: 승인 — {rec['out']}")


def reject(name, said):
    """사용자가 물렸다 — 그 말이 "배운 것" 의 재료다. 승인을 푼다."""
    rec = load(name)
    rec.setdefault("said", []).append({"date": str(datetime.date.today()), "said": " ".join(said.split())})
    rec["approved"] = None
    save(rec)
    print(f"{name}: 물림을 적었다 ({len(rec['said'])}번째). 다른 에셋에도 맞는 말이면 `asset.py learn` 으로 한 줄 보탠다")


# ── 움직임 ────────────────────────────────────────────────────────────

def animate(name, motion, prompt, seconds, frames):
    rec = load(name)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", motion):
        sys.exit(f"동작의 이름은 소문자 · 숫자 · 밑줄이다: {motion!r}")
    if not approved(rec):
        sys.exit(f"{name}: 승인된 그림이 없다 — 사람이 그림을 보고 난 뒤 sprite.py approve {name}")
    m = rec.setdefault("motions", {}).setdefault(motion, {})
    m["prompt"] = prompt
    ask = dict(CFG["animate"], **({"duration": seconds} if seconds else {}), **({"frames": frames} if frames else {}))
    result, credits = run(rec, m, f"{name} {motion}", "/assets/sprite/animate",
                          lambda: dict(ask, motion_prompt=prompt, initial_image=upload(still_path(name)), gif=True))
    sheet = os.path.join(asset.folder(name), f"{motion}.png")
    open(sheet, "wb").write(http(result["spritesheet_url"], auth=False))
    gif = ""
    if result.get("gif_url"):
        gif = os.path.join(asset.folder(name), f"{motion}.gif")
        open(gif, "wb").write(http(result["gif_url"], auth=False))
    out = os.path.join(asset.ROOT, CFG["dir"], f"{name}_{motion}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copyfile(sheet, out)
    (w, h), cols, rows = png_size(sheet), result.get("num_cols") or 0, result.get("num_rows") or 0
    m.update(out=rel(out), frames=result.get("num_frames"), cols=cols, rows=rows, cell=[w // cols, h // rows] if cols and rows else None,
             seconds=result.get("duration"), asked=ask, credits=credits, made=m.get("made", 0) + 1)
    save(rec)
    print(f"{name} {motion}: {m['out']} — {grid(m)}" + (f" · 크레딧 {credits}" if credits is not None else "")
          + (f"\n미리보기 (사용자가 본다): {rel(gif)}" if gif else ""))


def grid(m):
    cell = " × ".join(str(x) for x in m["cell"]) + " px" if m.get("cell") else "?"
    return f"{m.get('frames', '?')}프레임 · {m.get('cols', '?')}열 × {m.get('rows', '?')}행 · 한 칸 {cell}"


def status():
    work = os.path.join(asset.ROOT, asset.CFG["work"])
    names = sorted(n for n in os.listdir(work) if os.path.exists(os.path.join(work, n, "sprite.json"))) \
        if os.path.isdir(work) else []
    if not names:
        print("스프라이트가 없다 — sprite.py new <이름> \"<무엇인지>\"")
    for n in names:
        rec = load(n)
        print(f"{n:<24} {stage(rec):<28} {rec['subject'][:50]}")
        for motion, m in (rec.get("motions") or {}).items():
            if m.get("out"):
                print(f"  {motion:<22} {m['out']} — {grid(m)}")
            else:
                print(f"  {motion:<22} 만드는 중 — 같은 animate 명령으로 잇는다")


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--type", "--ref", "--seconds", "--frames"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    as_is = "--as-is" in args
    args = [a for a in args if a != "--as-is"]
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd not in ("new", "image", "approve", "reject", "animate", "status", "credits") or (cmd not in ("status", "credits") and not rest):
        sys.exit(__doc__)
    setup(opts.get("--root"))
    ref = opts.get("--ref")
    if ref and not os.path.exists(os.path.join(asset.ROOT, ref)):
        sys.exit(f"{ref}: 레퍼런스가 없다 (게임 루트 기준 경로)")
    if as_is and (cmd != "new" or not ref or not ref.lower().endswith(".png")):
        sys.exit("--as-is 는 new 에서, png 인 --ref 와 같이 쓴다")
    try:
        seconds = float(opts["--seconds"]) if "--seconds" in opts else None
        frames = int(opts["--frames"]) if "--frames" in opts else None
        if (seconds is not None and seconds <= 0) or (frames is not None and frames not in FRAMES):
            raise ValueError
    except ValueError:
        sys.exit("--seconds 는 0 보다 큰 초, --frames 는 " + " · ".join(str(x) for x in FRAMES) + " 중 하나다")
    try:
        if cmd == "new":
            if len(rest) != 2:
                sys.exit(__doc__)
            name, subject = rest[0], rest[1].strip().rstrip(".")
            if os.path.exists(os.path.join(asset.folder(name), "sprite.json")):
                sys.exit(f"{name}: 이미 있다 — 다른 이름을 쓰거나 {rel(asset.folder(name))}/sprite.json 을 고친다")
            rec = {"name": name, "kind": "스프라이트", "subject": subject, "type": opts.get("--type"), "created": str(datetime.date.today())}
            if ref:
                rec.update(ref=ref, as_is=as_is)
            save(rec)
            print(f"{name}: {rel(asset.folder(name))}/sprite.json" + (f" · 레퍼런스 {ref}" + (" (그대로 쓴다)" if as_is else "") if ref else ""))
        elif cmd == "image":
            for name in rest:
                image(name, ref)
        elif cmd == "approve":
            for name in rest:
                approve(name)
        elif cmd == "reject":
            if len(rest) != 2:
                sys.exit(__doc__)
            reject(*rest)
        elif cmd == "animate":
            if len(rest) != 3:
                sys.exit(__doc__)
            animate(rest[0], rest[1], " ".join(rest[2].split()), seconds, frames)
        elif cmd == "credits":
            got = call("/assets/account")
            credits = got.get("credits") or {}
            print(f"남은 크레딧: {credits.get('available', credits)}")
        else:
            status()
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
