#!/usr/bin/env python3
"""배포 — 게임을 빌드해 butler 로 itch.io 에 올린다.

  python3 deploy.py check                  올려도 되는가: butler · 대상 · 커밋 안 된 변경 · 사전 검사
  python3 deploy.py build [채널]           설정의 빌드 명령을 돌리고 결과 폴더를 확인한다
  python3 deploy.py push [채널] [--dry-run]  butler push. --dry-run 이면 무엇이 올라갈지만 본다
  python3 deploy.py status                 itch.io 가 가진 채널과 빌드
  python3 deploy.py version                올릴 때 붙는 버전

채널을 생략하면 설정의 채널 전부. check 와 push 는 커밋 안 된 변경이 있으면 멈춘다 (--dirty 로 넘긴다).

무엇을 어떻게 빌드해 어디로 올리는지는 프로젝트 루트 kit.config.json 의 "deploy" 에 있다:

  "deploy": {
    "itch": "사용자/게임",
    "version": { "file": "project.godot", "regex": "config/version=\\"([^\\"]+)\\"" },
    "pre": ["사전 검사 명령", ...],
    "channels": { "html5": { "build": "빌드 명령", "dir": "build/web", "must": "index.html" } }
  }

로그인은 사용자가 한 번 한다: butler login (또는 환경 변수 BUTLER_API_KEY).
"""
import json
import os
import re
import shutil
import subprocess
import sys

CONFIG_NAME = "kit.config.json"
SECTION = "deploy"
DEFAULTS = {
    "itch": "",                          # 사용자/게임
    "butler": "butler",
    "version": {"file": "", "regex": ""},  # 버전이 적힌 파일과 그것을 집는 정규식(그룹 1). 비면 커밋 해시
    "pre": [],                           # 올리기 전에 통과해야 하는 명령 (루트에서 돈다)
    "channels": {},                      # 채널 이름 → { build, dir, must }
}

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


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def version():
    v = CFG["version"] or {}
    if v.get("file") and v.get("regex"):
        path = os.path.join(ROOT, v["file"])
        m = re.search(v["regex"], open(path, encoding="utf-8").read()) if os.path.exists(path) else None
        if not m:
            sys.exit(f"{SECTION}.version: {v['file']} 에서 버전을 찾지 못했다 — 정규식의 그룹 1 이 버전이어야 한다")
        return m.group(1)
    return git("rev-parse", "--short", "HEAD") or sys.exit(
        f"버전을 정할 수 없다 — {SECTION}.version 을 채우거나 커밋을 하나 만든다")


def channels(name):
    all_ = CFG["channels"]
    if not all_:
        sys.exit(f"{CONFIG_NAME} 의 {SECTION}.channels 가 비어 있다 — 채널마다 build · dir 을 적는다 (deploy 스킬의 설정 절)")
    if name is None:
        return list(all_.items())
    if name not in all_:
        sys.exit(f"모르는 채널 {name} — " + " · ".join(all_))
    return [(name, all_[name])]


def problems(dirty):
    """올리면 안 되는 이유들. 비어 있으면 올려도 된다."""
    bad = []
    if not shutil.which(CFG["butler"]):
        bad.append(f"butler 가 없다 ({CFG['butler']}) — https://itch.io/docs/butler/ 에서 받고 `butler login`")
    if not re.fullmatch(r"[^/\s:]+/[^/\s:]+", CFG["itch"]):
        bad.append(f"{SECTION}.itch 가 `사용자/게임` 모양이 아니다: {CFG['itch']!r}")
    if not CFG["channels"]:
        bad.append(f"{SECTION}.channels 가 비어 있다")
    changed = git("status", "--porcelain")
    if changed and not dirty:
        bad.append("커밋 안 된 변경이 있다 — 올라간 빌드가 어느 커밋인지 알 수 없게 된다\n" + changed)
    for cmd in CFG["pre"]:
        p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
        print(f"  {'통과' if p.returncode == 0 else '실패'}  {cmd}")
        if p.returncode != 0:
            bad.append(f"사전 검사 실패: {cmd}\n{(p.stdout + p.stderr).strip()[-2000:]}")
    return bad


def check(dirty):
    bad = problems(dirty)
    if bad:
        sys.exit("올릴 수 없다:\n- " + "\n- ".join(bad))
    print(f"올려도 된다 — {CFG['itch']} · 버전 {version()} · 채널 " + " · ".join(CFG["channels"]))


def built(name, ch):
    """빌드 결과 폴더가 올릴 만한지 본다. (폴더, 파일 수, 바이트)"""
    if not ch.get("dir"):
        sys.exit(f"{SECTION}.channels.{name}.dir 이 비어 있다")
    d = os.path.join(ROOT, ch["dir"])
    files = [os.path.join(p, n) for p, _dirs, names in os.walk(d) for n in names]
    if not files:
        sys.exit(f"{name}: {ch['dir']} 에 빌드가 없다 — deploy.py build {name}")
    if ch.get("must") and not os.path.exists(os.path.join(d, ch["must"])):
        sys.exit(f"{name}: {ch['dir']}/{ch['must']} 이 없다 — 빌드가 덜 됐다")
    return d, len(files), sum(os.path.getsize(f) for f in files)


def build(name):
    for name, ch in channels(name):
        if ch.get("build"):
            os.makedirs(os.path.join(ROOT, ch.get("dir") or "."), exist_ok=True)
            print(f"{name}: {ch['build']}", flush=True)
            if subprocess.run(ch["build"], shell=True, cwd=ROOT).returncode != 0:
                sys.exit(f"{name}: 빌드 실패")
        _d, n, size = built(name, ch)
        print(f"{name}: {ch['dir']} — 파일 {n}개 · {size / 1e6:.1f} MB")


def push(name, dry, dirty):
    if not dry:
        check(dirty)
    ver = version()
    for name, ch in channels(name):
        d, n, size = built(name, ch)
        target = f"{CFG['itch']}:{name}"
        cmd = [CFG["butler"], "push", d, target, "--userversion", ver] + (["--dry-run"] if dry else [])
        print(f"{name}: {ch['dir']} (파일 {n}개 · {size / 1e6:.1f} MB) → {target} · 버전 {ver}"
              + (" · 올리지 않는다" if dry else ""), flush=True)
        if subprocess.run(cmd, cwd=ROOT).returncode != 0:
            sys.exit(f"{name}: butler push 실패")


def main():
    args = sys.argv[1:]
    root = None
    if "--root" in args:  # 테스트용
        i = args.index("--root")
        root = args[i + 1]
        del args[i:i + 2]
    flags = {a for a in args if a.startswith("--")}
    args = [a for a in args if not a.startswith("--")]
    cmd = args[0] if args else ""
    if cmd not in ("check", "build", "push", "status", "version") or flags - {"--dry-run", "--dirty"}:
        sys.exit(__doc__)
    setup(root)
    name = args[1] if len(args) > 1 else None
    if cmd == "check":
        check("--dirty" in flags)
    elif cmd == "build":
        build(name)
    elif cmd == "push":
        push(name, "--dry-run" in flags, "--dirty" in flags)
    elif cmd == "status":
        sys.exit(subprocess.run([CFG["butler"], "status", CFG["itch"]], cwd=ROOT).returncode)
    else:
        print(version())


if __name__ == "__main__":
    main()
