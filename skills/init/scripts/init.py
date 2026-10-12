#!/usr/bin/env python3
"""게임 저장소에 gamedev-kit 이 쓰는 파일을 깐다. 게임 저장소 루트에서 돌린다.

  python3 init.py              깔 수 있는 엔진을 적는다
  python3 init.py --detect     이 폴더가 이미 어느 엔진의 프로젝트인지 (아니면 고를 수 있는 엔진)
  python3 init.py <엔진> --editor     이 기기의 에디터 실행 파일과 빌드에 드는 모듈 — 없으면 무엇을 깔아야 하는지 적고 1 로 끝난다
  python3 init.py <엔진> --create     엔진 프로젝트가 없으면 이 폴더에 만든다 (.git · docs/ 가 이미 있어도 된다)
  python3 init.py <엔진>       설정 · GDD 틀 · 런타임 틀을 깐다. 엔진의 .gitignore 줄도 더한다
  python3 init.py <엔진> --import     깐 파일을 엔진이 한 번 읽게 한다 (컴파일 · 임포트). 오류 줄이 있으면 1 로 끝난다
  python3 init.py <엔진> --gitignore  엔진의 .gitignore 줄만 더한다 (이미 있는 줄은 다시 적지 않는다)
  python3 init.py <엔진> --files   이미 깐 프로젝트에서 엔진 틀(값 파일 · 런타임)도 없는 것을 다시 깐다
  python3 init.py <엔진> --rules   CLAUDE.md 의 키트 규칙 블록을 지금 판으로 맞춘다 (없으면 끝에 붙인다). 블록 밖은 건드리지 않는다
  python3 init.py --rules-check    세션이 시작될 때 훅이 부른다: 블록이 옛 판이면 지금 판으로 바꾸고 한 줄 적는다. 블록이 없거나 손으로 고쳐졌으면 알리기만 한다. 같으면 조용하다

이미 있는 파일은 건드리지 않는다 — 몇 번을 돌려도 같다.
이미 깐 프로젝트(kit.config.json 이 있다)에서 다시 돌리면 엔진 틀은 건너뛴다: 값 파일을 옮겼거나 틀을 일부러 지운 프로젝트에
같은 파일을 또 만들지 않게 (Godot 은 `class_name` 이 둘이면 뜨지 않는다). 대신 그 뒤로 키트에 생긴 설정 절을 알려 준다.

CLAUDE.md 에서 키트의 것은 `<!-- gamedev-kit 시작 … -->` 과 `<!-- gamedev-kit 끝 -->` 사이뿐이다 (공통 규칙 + 엔진 규칙).
키트가 판을 올리면 --rules 가 그 사이만 통째로 바꾼다 — 게임의 규칙은 블록 밖에 있고 건드리지 않는다.
블록 안을 손으로 고쳤으면 덮지 않고 멈춘다 (고친 것을 밖으로 옮기거나 --force).

엔진 프로젝트를 알아보고 · 에디터를 찾고 · 만드는 법은 engines/<엔진>/project.json 에 있다 (게임에 복사되지 않는다):
  marker    이 파일이 있으면 그 엔진의 프로젝트다
  editor    env(실행 파일을 가리키는 환경 변수) · path(PATH 에서 찾을 이름) · <sys.platform>.glob(깔리는 자리 — 여럿이면 version 정규식으로 가장 새 것) ·
            <sys.platform>.modules(실행 파일의 폴더에서 모듈 폴더까지) · missing(없을 때 사용자에게 할 말)
  modules   빌드에 드는 모듈마다 name · dir · must(그 안에 있어야 하는 것) · install(없을 때 할 말. {version} 이 채워진다)
  create · import   files(없으면 쓰는 파일) · run(명령들 — {editor} · {root} · {log}) · error(출력에서 찾을 오류 줄의 정규식)
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
ENGINES = os.environ.get("GAMEDEV_KIT_ENGINES") or os.path.join(KIT, "engines")  # 테스트가 바꾼다
LOCK_LINE = "~$*.xlsx"
START, END = "<!-- gamedev-kit 시작", "<!-- gamedev-kit 끝 -->"
BLOCK_RE = re.compile(re.escape(START) + r" · ([0-9a-f]+)[^\n]*-->\n(.*?)\n" + re.escape(END), re.S)
OWN = """
## This game's rules

Structure, pitfalls and verification methods specific to this game go here. Where they disagree with the block above, what is written here wins.
"""


def engines():
    return sorted(d for d in os.listdir(ENGINES) if os.path.exists(os.path.join(ENGINES, d, "kit.config.json")))


def project(engine):
    """그 엔진의 프로젝트를 알아보고 · 에디터를 찾고 · 만드는 법. 게임의 설정(kit.config.json)과 달리 게임에 복사되지 않는다."""
    path = os.path.join(ENGINES, engine, "project.json")
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}


def detect(root):
    """이 폴더가 이미 프로젝트인 엔진들 — 보통 하나이거나 없다."""
    return [e for e in engines() if project(e).get("marker") and os.path.exists(os.path.join(root, project(e)["marker"]))]


def find_editor(engine):
    """(실행 파일, 판, 깔린 판 전부). 환경 변수 → PATH → 깔리는 자리 순서. 없으면 (None, "", [])."""
    ed = project(engine).get("editor", {})

    def version(path):
        m = re.search(ed["version"], path.replace(os.sep, "/")) if ed.get("version") else None
        return m.group(1) if m else ""

    named = os.environ.get(ed.get("env") or "", "")
    if named:
        if not os.path.exists(named):
            sys.exit(f"환경 변수 {ed['env']} 가 가리키는 파일이 없다: {named}")
        return named, version(named), []
    for name in ed.get("path", []):
        if shutil.which(name):
            return shutil.which(name), "", []
    found = [p for pattern in ed.get(sys.platform, {}).get("glob", []) for p in glob.glob(os.path.expanduser(pattern))]
    if not found:
        return None, "", []
    found.sort(key=lambda p: [int(n) for n in re.findall(r"\d+", version(p))])  # 판은 숫자끼리 견준다 (10 이 9 보다 새것이다)
    return found[-1], version(found[-1]), [version(p) for p in found if version(p)]


def need_editor(engine):
    exe, version, _all = find_editor(engine)
    if not exe:
        ed = project(engine).get("editor", {})
        sys.exit(f"{ed.get('name', engine)} 에디터를 찾지 못했다 — 사용자가 깐다:\n" + "\n".join(f"  {line}" for line in ed.get("missing", [])))
    return exe, version


def cmd_editor(engine):
    spec = project(engine)
    ed = spec.get("editor", {})
    exe, version = need_editor(engine)
    versions = find_editor(engine)[2]
    print(f"{ed.get('name', engine)} {version} — {exe}".replace("  ", " ")
          + (f"\n  깔린 판 {' · '.join(versions)} 가운데 가장 새 것을 골랐다 (다른 판을 쓰려면 환경 변수 {ed['env']})" if len(versions) > 1 else ""))
    base, have, lack = ed.get(sys.platform, {}).get("modules"), [], []
    for mod in spec.get("modules", []):
        if base is None:
            print(f"  모름  {mod['name']} — 이 기기에서는 어디에 깔리는지 모른다. 에디터에서 직접 본다")
            continue
        folder = os.path.normpath(os.path.join(os.path.dirname(exe), base, mod["dir"]))
        gone = [m for m in mod.get("must", []) if not os.path.exists(os.path.join(folder, m))]
        if os.path.isdir(folder) and not gone:
            have.append(mod["name"])
            print(f"  있음  {mod['name']}" + (f" ({' · '.join(mod['must'])})" if mod.get("must") else ""))
        else:
            lack.append(mod["name"])
            print(f"  없음  {mod['name']} — " + (f"{' · '.join(gone)} 가 빠졌다" if os.path.isdir(folder) else f"{folder} 가 없다"))
            print("\n".join(f"        {line.replace('{version}', version)}" for line in mod.get("install", [])))
    print("\nCLAUDE.md 의 `## This game's rules` 아래에 적는다 (그 제목은 이미 있다 — 새로 만들지 않는다): "
          f"에디터 실행 파일 `{exe}`" + (f" · 깔린 모듈 {' · '.join(have)}" if have else ""))
    if lack:
        sys.exit(f"\n빌드에 드는 모듈이 없다: {' · '.join(lack)} — 까는 것은 사용자가 정한다 (받는 양이 크다). 깐 뒤 다시 돌린다")


def run_step(engine, step, root):
    """project.json 의 create · import 를 돌린다: 없는 파일을 쓰고, 에디터 명령을 돌리고, 출력에서 오류 줄을 찾는다."""
    spec = project(engine).get(step)
    if not spec:
        return print(f"{engine}: {step} 에 할 일이 없다")
    for rel, text in spec.get("files", {}).items():
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w", encoding="utf-8").write(text)
            print(f"  새로    {rel}")
    if not spec.get("run"):
        return None
    exe = need_editor(engine)[0]
    for argv in spec["run"]:
        log = os.path.join(tempfile.mkdtemp(prefix="kit-init-"), "editor.log")
        cmd = [a.replace("{editor}", exe).replace("{root}", root).replace("{log}", log) for a in argv]
        print("  돌린다  " + " ".join(cmd) + "  (몇 분 걸릴 수 있다)", flush=True)
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        out = p.stdout + p.stderr + (open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else "")
        shutil.rmtree(os.path.dirname(log), True)
        bad = [line for line in out.split("\n") if spec.get("error") and re.search(spec["error"], line)]
        if p.returncode or bad:
            tail = bad[:20] or out.strip().split("\n")[-20:]
            sys.exit(f"{step} 이 실패했다 (종료 코드 {p.returncode}" + (f" · 오류 줄 {len(bad)}" if bad else "") + ") — 에디터가 이 프로젝트를 열고 있으면 닫는다:\n"
                     + "\n".join(tail))


def cmd_create(engine, root):
    marker = project(engine).get("marker")
    if not marker:
        sys.exit(f"{engine}: engines/{engine}/project.json 에 만드는 법이 없다")
    here = detect(root)
    if engine in here:
        return print(f"이미 {engine} 프로젝트다 ({marker}) — 만들지 않는다")
    if here:
        sys.exit(f"이 폴더는 이미 {' · '.join(here)} 프로젝트다 — {engine} 프로젝트를 그 위에 만들지 않는다")
    run_step(engine, "create", root)
    if not os.path.exists(os.path.join(root, marker)):
        sys.exit(f"만들었다는데 {marker} 가 없다 — 에디터의 로그를 본다")
    print(f"{engine} 프로젝트를 만들었다 ({marker}). 이어서 키트 파일을 깐다: `init.py {engine}` → `init.py {engine} --import`")


def add_ignore(engine, root, done):
    """엔진의 .gitignore 줄 가운데 아직 없는 것만 끝에 붙인다."""
    src = os.path.join(ENGINES, engine, "gitignore")
    if not os.path.exists(src):
        return
    path = os.path.join(root, ".gitignore")
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    have = {line.strip() for line in text.split("\n")}
    new = [line.strip() for line in open(src, encoding="utf-8") if line.strip() and line.strip() not in have]
    if new:
        with open(path, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n") + f"\n# {engine} 이 만드는 것 · 저장소에 두지 않는 것\n" + "\n".join(new) + "\n")
    done.append(f"  {'더함  ' if new else '그대로'}  .gitignore ({engine} — " + (f"{len(new)}줄: {' · '.join(new)}" if new else "줄이 이미 다 있다") + ")")


def rules(engine):
    """(머리, 규칙 본문) — 본문은 공통 틀의 절들과 그 엔진의 규칙이다."""
    head, body = open(os.path.join(KIT, "templates", "CLAUDE.md"), encoding="utf-8").read().split("\n## ", 1)
    extra = os.path.join(ENGINES, engine, "CLAUDE.md")  # 그 엔진에서만 맞는 규칙 (실행 · 검증 · 함정)
    more = open(extra, encoding="utf-8").read().strip() if os.path.exists(extra) else ""
    return head.strip() + "\n", ("## " + body.strip() + ("\n\n" + more if more else "")).strip()


def digest(body):
    return hashlib.sha1(body.strip().encode("utf-8")).hexdigest()[:8]


def block(body):
    return (f"{START} · {digest(body)} — kit rules. Do not edit between these markers (`/gamedev-kit:init rules` replaces the whole block). "
            f"This game's own rules go outside the block. -->\n{body.strip()}\n{END}\n")


def rules_state(root, engine):
    """none(블록이 없다) · same · stale(키트가 판을 올렸다) · edited(블록 안을 손으로 고쳤다). CLAUDE.md 가 없으면 None."""
    path = os.path.join(root, "CLAUDE.md")
    if not os.path.exists(path):
        return None
    m = BLOCK_RE.search(open(path, encoding="utf-8").read())
    if not m:
        return "none"
    if digest(m.group(2)) != m.group(1):
        return "edited"
    return "same" if m.group(1) == digest(rules(engine)[1]) else "stale"


def sync_rules(root, engine, force):
    path = os.path.join(root, "CLAUDE.md")
    head, body = rules(engine)
    state = rules_state(root, engine)
    if state is None:
        open(path, "w", encoding="utf-8").write(head + "\n" + block(body) + OWN)
        return print("CLAUDE.md 를 새로 만들었다 — `<게임 이름>` 을 채운다")
    text = open(path, encoding="utf-8").read()
    if state == "same":
        return print("CLAUDE.md 의 키트 규칙은 지금 판과 같다")
    if state == "edited" and not force:
        sys.exit("CLAUDE.md 의 키트 규칙 블록 안이 손으로 고쳐졌다 — 덮지 않는다. 고친 것을 블록 밖으로 옮기고 다시 돌리거나, 버려도 되면 --force")
    if state == "none":
        titles = [t for t in re.findall(r"^## (.+)$", body, re.M) if re.search(rf"^## {re.escape(t)}\s*$", text, re.M)]
        open(path, "w", encoding="utf-8").write(text.rstrip("\n") + "\n\n" + block(body))
        print("CLAUDE.md 끝에 키트 규칙 블록을 붙였다 — 있던 글은 그대로다")
        if titles:
            print("블록 밖에 같은 제목의 절이 남아 있다 (옛 판을 옮겨 적은 것): " + " · ".join(titles)
                  + "\n겹치는 말은 블록 밖에서 지우고, 이 게임에서 고쳐 쓴 말만 밖에 남긴다 — 지우기 전에 사용자에게 보인다")
        return None
    open(path, "w", encoding="utf-8").write(BLOCK_RE.sub(lambda m: block(body).rstrip("\n"), text, count=1))
    print("CLAUDE.md 의 키트 규칙 블록을 지금 판으로 바꿨다 — 블록 밖은 그대로다")


def check_rules():
    """세션이 시작될 때 훅이 부른다. 할 말이 없으면 조용하다. 무슨 일이 있어도 0 으로 끝난다."""
    d = os.getcwd()
    while not os.path.exists(os.path.join(d, "kit.config.json")):
        if os.path.dirname(d) == d:
            return
        d = os.path.dirname(d)
    cfg = json.load(open(os.path.join(d, "kit.config.json"), encoding="utf-8"))
    if cfg.get("engine") not in engines() or cfg.get("init", {}).get("rules") is False:
        return
    state = rules_state(d, cfg["engine"])
    if state == "stale":  # 블록은 키트의 것이다 — 손대지 않은 블록은 묻지 않고 맞춘다
        path = os.path.join(d, "CLAUDE.md")
        text = open(path, encoding="utf-8").read()
        open(path, "w", encoding="utf-8").write(BLOCK_RE.sub(lambda m: block(rules(cfg["engine"])[1]).rstrip("\n"), text, count=1))
        return print("[gamedev-kit] 키트가 규칙을 고쳐서 CLAUDE.md 의 키트 규칙 블록을 지금 판으로 바꿨다 (블록 밖은 그대로다). "
                     "바뀐 것은 `git diff CLAUDE.md` — 끊을 자리에서 사용자에게 한 줄로 알린다. "
                     "스스로 맞추지 않게 하려면 kit.config.json 에 `\"init\": {\"rules\": false}`.")
    say = {"none": "CLAUDE.md 에 키트 규칙 블록이 없다 (키트의 새 규칙이 이 프로젝트에 들어오지 않는다)",
           "edited": "CLAUDE.md 의 키트 규칙 블록 안이 손으로 고쳐져 있다 (판을 맞출 수 없다)"}.get(state)
    if say:
        print(f"[gamedev-kit] {say}. 하던 일을 막지 않는다 — 끊을 자리에서 사용자에게 한 줄로 알린다: `/gamedev-kit:init rules` 로 맞출 수 있다. "
              "알리지 않게 하려면 kit.config.json 에 `\"init\": {\"rules\": false}`.")


def place(src, dst, root, done):
    rel = os.path.relpath(dst, root)
    if os.path.exists(dst):
        done.append(f"  그대로  {rel}")
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(src, dst)
    done.append(f"  새로    {rel}")
    return True


def main():
    args = sys.argv[1:]
    root = os.getcwd()
    if "--root" in args:  # 테스트용
        i = args.index("--root")
        root = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    if "--rules-check" in args:
        try:
            check_rules()
        except Exception:
            pass
        return
    if "--detect" in args:
        here, config = detect(root), os.path.join(root, "kit.config.json")
        has = json.load(open(config, encoding="utf-8")).get("engine", "") if os.path.exists(config) else ""
        print("\n".join(f"{e} — {project(e)['marker']} 가 있다" for e in here)
              or "엔진 프로젝트가 아니다 — 고를 수 있는 엔진: " + " · ".join(engines()))
        return print(f"키트는 {has} 로 이미 깔려 있다 (kit.config.json)" if has else "키트는 아직 깔리지 않았다 (kit.config.json 이 없다)")
    again_files, only_rules, force = "--files" in args, "--rules" in args, "--force" in args
    steps = [a for a in args if a in ("--editor", "--create", "--import", "--gitignore")]
    args = [a for a in args if a not in ("--files", "--rules", "--force", *steps)]
    if not args:
        sys.exit("엔진을 고른다: " + " · ".join(engines()))
    engine = args[0]
    if engine not in engines():
        sys.exit(f"모르는 엔진 {engine} — " + " · ".join(engines()))
    src = os.path.join(ENGINES, engine)
    done = []
    if only_rules:
        return sync_rules(root, engine, force)
    if steps:  # 엔진 프로젝트 쪽 일 — 하나씩 따로 부른다
        if steps[0] == "--editor":
            return cmd_editor(engine)
        if steps[0] == "--create":
            return cmd_create(engine, root)
        if steps[0] == "--import":
            return run_step(engine, "import", root)
        add_ignore(engine, root, done)
        return print("\n".join(done) or f"{engine}: 더할 .gitignore 줄이 없다")

    config = os.path.join(root, "kit.config.json")
    had = os.path.exists(config)
    if had:
        has = json.load(open(config, encoding="utf-8")).get("engine", "")
        if has != engine:
            sys.exit(f"kit.config.json 은 이미 {has or '다른'} 엔진으로 깔려 있다 — 바꾸려면 그 파일을 먼저 지운다")
    place(os.path.join(src, "kit.config.json"), config, root, done)

    files = os.path.join(src, "files")
    skipped = []
    for dirpath, _dirs, names in os.walk(files):
        for name in sorted(names):
            path = os.path.join(dirpath, name)
            dst = os.path.join(root, os.path.relpath(path, files))
            if had and not again_files and not os.path.exists(dst):
                skipped.append(os.path.relpath(dst, root))
            else:
                place(path, dst, root, done)
    if skipped:
        done.append(f"  건너뜀  엔진 틀 {len(skipped)}개 — 이미 깐 프로젝트다. 옮겼거나 지운 것이면 그대로 두고, 다시 깔려면 --files: " + " · ".join(skipped))

    place(os.path.join(KIT, "templates", "GDD.md"), os.path.join(root, "docs", "GDD.md"), root, done)
    place(os.path.join(KIT, "templates", "DESIGN.md"), os.path.join(root, "docs", "DESIGN.md"), root, done)
    made_claude = not os.path.exists(os.path.join(root, "CLAUDE.md"))
    if made_claude:
        head, body = rules(engine)
        open(os.path.join(root, "CLAUDE.md"), "w", encoding="utf-8").write(head + "\n" + block(body) + OWN)
    done.append(f"  {'새로  ' if made_claude else '그대로'}  CLAUDE.md")

    ignore = os.path.join(root, ".gitignore")
    text = open(ignore, encoding="utf-8").read() if os.path.exists(ignore) else ""
    if LOCK_LINE not in text:
        with open(ignore, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n")
                    + "\n# 엑셀이 파일을 열어 둔 동안 만드는 잠금 파일\n" + LOCK_LINE + "\n")
        done.append("  더함    .gitignore (엑셀 잠금 파일)")
    add_ignore(engine, root, done)

    print(f"gamedev-kit — {engine}\n" + "\n".join(done))
    if had:  # 그 뒤로 키트에 생긴 설정 절
        want = json.load(open(os.path.join(src, "kit.config.json"), encoding="utf-8"))
        have = json.load(open(config, encoding="utf-8"))
        missing = [k for k in want if k not in have] + [f"{k}.{s}" for k, v in want.items() if isinstance(v, dict) and isinstance(have.get(k), dict)
                                                         for s in v if s not in have[k]]
        if missing:
            print(f"\nkit.config.json 에 없는 절: {' · '.join(missing)} — 쓰려면 이 틀에서 옮겨 적는다: {os.path.join(src, 'kit.config.json')}")
    state = rules_state(root, engine)
    if state != "same":
        print("\nCLAUDE.md 의 키트 규칙: " + {"none": "블록이 없다 — `--rules` 가 끝에 붙인다 (있던 글은 건드리지 않는다)",
                                           "stale": "옛 판이다 — `--rules` 가 블록만 바꾼다",
                                           "edited": "블록 안이 손으로 고쳐졌다 — 고친 것을 밖으로 옮긴 뒤 `--rules`"}[state])
    marker = project(engine).get("marker")
    if marker and not os.path.exists(os.path.join(root, marker)):
        print(f"\n이 폴더는 아직 {engine} 프로젝트가 아니다 ({marker} 가 없다) — `init.py {engine} --create` 가 만든다")
    notes = os.path.join(src, "NOTES.md")
    if os.path.exists(notes):
        print("\n" + open(notes, encoding="utf-8").read().strip())


if __name__ == "__main__":
    main()
