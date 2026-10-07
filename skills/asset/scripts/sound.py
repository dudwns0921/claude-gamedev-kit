#!/usr/bin/env python3
"""소리 — 설명 한 줄에서 효과음과 음악을 만든다 (ElevenLabs).

  python3 sound.py sfx <이름> [--seconds <초>] [--loop] [--influence <0~1>] "<어떤 소리인지 — 영어로>"
  python3 sound.py music <이름> --seconds <초> "<어떤 음악인지 — 영어로>"
  python3 sound.py again <이름>...        기록에 적힌 그대로 다시 만든다 (같은 설명, 다른 결과)
  python3 sound.py status                 만든 소리들

효과음은 0.5~30초(생략하면 길이를 알아서 정한다), 음악은 3~600초. --loop 는 끝과 처음이 이어지는 소리(바람 · 엔진 · 배경).
파일은 <sound.dir>/<이름>.<mp3|wav> 에, 기록은 <work>/<이름>/sound.json 에 놓인다. 같은 이름으로 다시 만들면 파일을 덮는다.

소리의 결은 한 곳에 있다 — asset.style_file(기본 docs/DESIGN.md)의 `<!-- sound-style -->` 와 `<!-- /sound-style -->` 사이.
있으면 모든 설명 뒤에 그대로 붙는다. 설정은 프로젝트 루트 kit.config.json 의 "asset" 안 "sound".

키는 저장소 밖에 둔다 — 환경 변수 ELEVENLABS_API_KEY, 없으면 asset.env_file
(기본 ~/.config/gamedev-kit/asset.env) 안의 같은 이름 줄.
"""
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request
import wave

CONFIG_NAME = "kit.config.json"
SECTION = "asset"
DEFAULTS = {
    "work": "assets/_gen",
    "style_file": "docs/DESIGN.md",
    "env_file": "~/.config/gamedev-kit/asset.env",
    "sound": {
        "dir": "",                      # 끝난 소리가 놓이는 폴더 (루트 기준)
        "format": "mp3_44100_128",      # ElevenLabs 의 output_format. pcm_* 이면 wav 로 싸서 놓는다
        "influence": 0.3,               # 설명을 얼마나 글자 그대로 따르는가 (0~1)
        "music_model": "music_v1",
    },
}
API = os.environ.get("ELEVENLABS_API_BASE", "https://api.elevenlabs.io/v1")  # 테스트가 바꾼다
KEY = "ELEVENLABS_API_KEY"
OPEN, CLOSE = "<!-- sound-style -->", "<!-- /sound-style -->"
LIMITS = {"sfx": (0.5, 30), "music": (3, 600)}

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
    CFG = {k: have.get(k, v) for k, v in DEFAULTS.items()}
    CFG["sound"] = dict(DEFAULTS["sound"], **have.get("sound", {}))
    if not CFG["sound"]["dir"]:
        sys.exit(f"{CONFIG_NAME} 의 {SECTION}.sound.dir 이 비어 있다 — 소리를 놓을 폴더를 적는다 (asset 스킬의 설정 절)")


def key():
    if os.environ.get(KEY):
        return os.environ[KEY]
    path = os.path.expanduser(CFG["env_file"])
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == KEY and v:
                return v.strip("\"'")
    sys.exit(f"{KEY} 가 없다 — {path} 에 `{KEY}=...` 한 줄을 적는다 (asset 스킬의 '처음 한 번')")


def post(path, body):
    req = urllib.request.Request(f"{API}/{path}?output_format={CFG['sound']['format']}", data=json.dumps(body).encode(),
                                 headers={"xi-api-key": key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(text)["detail"]
            text = detail.get("message", text) if isinstance(detail, dict) else json.dumps(detail, ensure_ascii=False)
        except (ValueError, KeyError, TypeError):
            pass
        raise RuntimeError(f"ElevenLabs {path} → {e.code}: {str(text)[:500]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"ElevenLabs {path} → {e.reason}")


def folder(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
        sys.exit(f"이름은 소문자 · 숫자 · 밑줄이다: {name!r}")
    return os.path.join(ROOT, CFG["work"], name)


def style():
    path = os.path.join(ROOT, CFG["style_file"])
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    if OPEN not in text or CLOSE not in text:
        return ""
    return " ".join(text.split(OPEN, 1)[1].split(CLOSE, 1)[0].split())


def write(name, data):
    """받은 소리를 게임 폴더에 놓는다. pcm 이면 wav 머리를 씌운다 (16비트 · 모노)."""
    fmt = CFG["sound"]["format"]
    out = os.path.join(ROOT, CFG["sound"]["dir"], f"{name}.{'wav' if fmt.startswith('pcm_') else fmt.split('_')[0]}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if fmt.startswith("pcm_"):
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(fmt.split("_")[1]))
            w.writeframes(data)
    else:
        open(out, "wb").write(data)
    return out


def make(rec):
    name, kind = rec["name"], rec["kind"]
    lo, hi = LIMITS[kind]
    if rec.get("seconds") is not None and not lo <= rec["seconds"] <= hi:
        sys.exit(f"{name}: {'효과음' if kind == 'sfx' else '음악'}은 {lo}~{hi}초다")
    prompt = rec["subject"] + (f". {style()}" if style() else "")
    if kind == "sfx":
        body = {"text": prompt, "prompt_influence": rec["influence"], "loop": rec["loop"]}
        if rec.get("seconds") is not None:
            body["duration_seconds"] = rec["seconds"]
        data = post("sound-generation", body)
    else:
        data = post("music", {"prompt": prompt, "music_length_ms": int(rec["seconds"] * 1000),
                              "model_id": CFG["sound"]["music_model"], "force_instrumental": True})
    if not data:
        raise RuntimeError(f"{name}: 빈 소리가 돌아왔다")
    out = write(name, data)
    rec.update(prompt=prompt, out=os.path.relpath(out, ROOT), format=CFG["sound"]["format"],
               made=str(datetime.date.today()), takes=rec.get("takes", 0) + 1)
    path = os.path.join(folder(name), "sound.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{name}: {rec['out']} — {len(data) / 1e3:.0f} KB" + (" · 이어지는 소리" if rec.get("loop") else "")
          + (f" · {rec['takes']}번째" if rec["takes"] > 1 else ""))


def records():
    work = os.path.join(ROOT, CFG["work"])
    names = sorted(os.listdir(work)) if os.path.isdir(work) else []
    return [json.load(open(os.path.join(work, n, "sound.json"), encoding="utf-8"))
            for n in names if os.path.exists(os.path.join(work, n, "sound.json"))]


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--root", "--seconds", "--influence"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    loop = "--loop" in args
    args = [a for a in args if a != "--loop"]
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd not in ("sfx", "music", "again", "status") or (cmd in ("sfx", "music") and len(rest) != 2) \
            or (cmd == "again" and not rest) or (cmd == "music" and "--seconds" not in opts):
        sys.exit(__doc__)
    setup(opts.get("--root"))
    try:
        seconds = float(opts["--seconds"]) if "--seconds" in opts else None
        influence = float(opts["--influence"]) if "--influence" in opts else CFG["sound"]["influence"]
        if not 0 <= influence <= 1:
            raise ValueError
    except ValueError:
        sys.exit("--seconds 는 초, --influence 는 0~1 이다")
    try:
        if cmd in ("sfx", "music"):
            name, subject = rest[0], rest[1].strip().rstrip(".")
            folder(name)
            old = next((r for r in records() if r["name"] == name), {})
            rec = {"name": name, "kind": cmd, "subject": subject, "seconds": seconds, "takes": old.get("takes", 0)}
            if cmd == "sfx":
                rec.update(loop=loop, influence=influence)
            make(rec)
        elif cmd == "again":
            have = {r["name"]: r for r in records()}
            for name in rest:
                if name not in have:
                    sys.exit(f"{name}: 기록이 없다 — sound.py sfx {name} \"<어떤 소리인지>\"")
                make(have[name])
        else:
            if not records():
                print("소리가 없다 — sound.py sfx <이름> \"<어떤 소리인지>\"")
            for r in records():
                length = "알아서" if r.get("seconds") is None else f"{r['seconds']}초"
                print(f"{r['name']:<24} {'음악' if r['kind'] == 'music' else '이어짐' if r.get('loop') else '효과음':<6} "
                      f"{length:<8} {r['out']} · {r['subject'][:50]}")
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
