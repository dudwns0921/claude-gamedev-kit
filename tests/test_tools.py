#!/usr/bin/env python3
"""도구 검사 — engines/ 의 엔진 설정마다 임시 프로젝트를 만들어 gdd-sync 와 balance-table 을 끝까지 돌린다.
init 의 엔진 프로젝트 만들기는 가짜 에디터로, deploy 는 가짜 butler 로, asset 과 start 의 컨셉 그림은 가짜 API 서버로, video 는 가짜 Higgsfield 서버 · 가짜 ffmpeg 로 돌린다 — 밖으로는 아무것도 나가지 않는다.

  python3 tests/test_tools.py

엔진은 필요 없다. 엔진 문법(GDScript)으로 적힌 값 파일을 도구가 읽고 고치는지만 본다.
"""
import base64
import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import zipfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(KIT, "skills/gdd-sync/scripts/sync_report.py")
TABLE = os.path.join(KIT, "skills/balance-table/scripts/balance_table.py")
DEPLOY = os.path.join(KIT, "skills/deploy/scripts/deploy.py")
ASSET = os.path.join(KIT, "skills/asset/scripts/asset.py")
SOUND = os.path.join(KIT, "skills/asset/scripts/sound.py")
SPRITE = os.path.join(KIT, "skills/asset/scripts/sprite.py")
CLIP = os.path.join(KIT, "skills/video/scripts/clip.py")
BOARD = os.path.join(KIT, "skills/board/scripts/board.py")
CYCLE = os.path.join(KIT, "skills/cycle/scripts/cycle.py")
SHEET = os.path.join(KIT, "skills/cycle/scripts/sheet.py")
PLAYTEST = os.path.join(KIT, "skills/playtest/scripts/playtest.py")
VOICE = os.path.join(KIT, "skills/voice/scripts/voice.py")
INIT = os.path.join(KIT, "skills/init/scripts/init.py")
START = os.path.join(KIT, "skills/start/scripts/start.py")
CONCEPT = os.path.join(KIT, "skills/start/scripts/concept.py")
WATCH = os.path.join(KIT, "hooks/context_watch.py")
USAGE = os.path.join(KIT, "tools/session_usage.py")
FEEDBACK = os.path.join(KIT, "tools/kit_feedback.py")
SEND = os.path.join(KIT, "skills/feedback/scripts/feedback.py")
PRIVATE = os.path.join(KIT, "tools/private_check.py")


def raw_glb():
    """Meshy 가 줄 법한 메쉬: 삼각형 둘, 높이 4, 원점도 크기도 어긋나 있다 (x 0~2 · y 1~5 · z 0~1, 노드에 이동과 배율)."""
    b = b"".join(struct.pack("<3f", *p) for p in [(0, 1, 0), (2, 1, 0), (0, 5, 1), (2, 5, 1)]) + struct.pack("<6H", 0, 1, 2, 1, 3, 2)
    g = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
         "nodes": [{"mesh": 0, "translation": [10, 0, 0], "scale": [3, 3, 3]}],
         "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
         "buffers": [{"byteLength": len(b)}],
         "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 48, "target": 34962},
                         {"buffer": 0, "byteOffset": 48, "byteLength": 12, "target": 34963}],
         "accessors": [{"bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3", "min": [0, 1, 0], "max": [2, 5, 1]},
                       {"bufferView": 1, "componentType": 5123, "count": 6, "type": "SCALAR"}]}
    j = json.dumps(g).encode()
    j += b" " * (-len(j) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 28 + len(j) + len(b)) + struct.pack("<I4s", len(j), b"JSON") + j
            + struct.pack("<I4s", len(b), b"BIN\0") + b)

# 엔진이 버전을 적어 두는 파일의 한 줄 (deploy.version 이 이것을 집어야 한다)
VERSION_LINE = {"godot": 'config/version="1.2.3"', "unity": "  bundleVersion: 1.2.3"}

GDD = """# 게임

## 4. 규칙

체력은 100 이고 걷는 속도는 4 다.

## 부록 A. 동기화 표

### A.1 밸런스 수치

| ID | 값 | 출처 | 코드 위치 | 상태 | 비고 |
|---|---|---|---|---|---|
| BAL.PLAYER.HP | 100 | 4 | — | 미구현 | 시작 체력 |
| BAL.PLAYER.WALK_SPEED | 3~5 | 4 | — | 미구현 | 걷는 속도 |
| BAL.COIN.VALUE | 7 | 4 | — | 미구현 | 동전 값 |
| BAL.OLD.THING | — | 4 | — | 폐기 | 폐기 |
| BAL.NOT.YET | 3 | 4 | — | 미구현 | |

### A.3 규칙

| ID | 규칙 | 출처 | 코드 위치 | 상태 | 비고 |
|---|---|---|---|---|---|
| RULE.COIN.PICKUP | 닿으면 줍는다 | 4 | — | 미구현 | |
"""

# 엔진별 값 파일. HP 100 · WALK_SPEED 4.0 · COIN_VALUE 5 (GDD 는 7 — 불일치) · 표에 없는 ID 하나(고아)
CODE = {
    "godot": ("""class_name Balance
## 시작 체력
static var PLAYER_HP := 100  # GDD: BAL.PLAYER.HP
static var PLAYER_WALK_SPEED := 4.0  # GDD: BAL.PLAYER.WALK_SPEED
static var COIN_VALUE := 5  # GDD: BAL.COIN.VALUE
static var UNMARKED := 2.5  # 표식 없는 값

static func can_pickup() -> bool:  # GDD: RULE.COIN.PICKUP
	return true

static var STRAY := 1  # GDD: BAL.STRAY.ONE
""", "can_pickup"),
    "unity": ("""public static class Balance
{
    /// 시작 체력
    public static int PLAYER_HP = 100; // GDD: BAL.PLAYER.HP
    public static float PLAYER_WALK_SPEED = 4.0f; // GDD: BAL.PLAYER.WALK_SPEED
    public static int COIN_VALUE = 5; // GDD: BAL.COIN.VALUE
    public static float UNMARKED = 2.5f; // 표식 없는 값

    public static bool CanPickup() // GDD: RULE.COIN.PICKUP
    {
        return true;
    }

    public static int STRAY = 1; // GDD: BAL.STRAY.ONE
}
""", "CanPickup"),
}


def run(script, root, *args, ok=True):
    p = subprocess.run([sys.executable, script, "--root", root, *args], capture_output=True, text=True)
    if ok and p.returncode != 0:
        raise AssertionError(f"{os.path.basename(script)} {' '.join(args)} → {p.returncode}\n{p.stdout}\n{p.stderr}")
    return p


def excel_save(path, values):
    """엑셀이 저장하는 모양으로 쓴다: 글자는 sharedStrings 에 모으고(발음 표기 <rPh> 포함) 칸에는 번호만."""
    shared, rows = ["이름", "값"], ['<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>']
    for r, (name, value) in enumerate(values.items(), 2):
        shared.append(name)
        rows.append(f'<row r="{r}"><c r="A{r}" t="s"><v>{len(shared) - 1}</v></c><c r="B{r}"><v>{value}</v></c></row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    strings = "".join(f'<si><r><t>{s}</t></r><rPh sb="0" eb="1"><t>발음</t></rPh></si>' for s in shared)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<?xml version="1.0"?><sst {ns}>{strings}</sst>')
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<?xml version="1.0"?><worksheet {ns}><sheetData>{"".join(rows)}</sheetData></worksheet>')


class Tools(unittest.TestCase):
    def project(self, engine):
        root = tempfile.mkdtemp(prefix=f"kit-{engine}-")
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copy(os.path.join(KIT, "engines", engine, "kit.config.json"), os.path.join(root, "kit.config.json"))
        cfg = json.load(open(os.path.join(root, "kit.config.json"), encoding="utf-8"))["balance-table"]
        code = os.path.join(root, cfg["code"])
        os.makedirs(os.path.dirname(code))
        open(code, "w", encoding="utf-8").write(CODE[engine][0])
        os.makedirs(os.path.join(root, "docs"))
        open(os.path.join(root, "docs/GDD.md"), "w", encoding="utf-8").write(GDD)
        return root, code, os.path.join(root, cfg["table"]), cfg["code"]

    def each(self):
        for engine in CODE:
            with self.subTest(engine=engine):
                yield (engine,) + self.project(engine)

    def test_gdd_sync(self):
        for engine, root, _code, _table, rel in self.each():
            data = json.loads(run(REPORT, root, "--json").stdout)
            got = {i["id"]: i for i in data["items"]}
            self.assertEqual(got["BAL.PLAYER.HP"]["new_status"], "동기")
            self.assertEqual(got["BAL.PLAYER.HP"]["hits"][0]["symbol"], "PLAYER_HP")
            self.assertEqual(got["BAL.PLAYER.WALK_SPEED"]["new_status"], "동기", "범위 3~5 안의 4.0")
            self.assertEqual(got["BAL.COIN.VALUE"]["new_status"], "불일치")
            self.assertEqual(got["BAL.NOT.YET"]["new_status"], "미구현")
            self.assertEqual(got["RULE.COIN.PICKUP"]["new_status"], "동기?")
            self.assertEqual(got["RULE.COIN.PICKUP"]["hits"][0]["symbol"], CODE[engine][1])
            self.assertEqual(list(data["orphans"]), ["BAL.STRAY.ONE"])

            run(REPORT, root, "--write")
            gdd = open(os.path.join(root, "docs/GDD.md"), encoding="utf-8").read()
            self.assertIn(f"| BAL.PLAYER.HP | 100 | 4 | {rel}:PLAYER_HP | 동기 |", gdd)
            self.assertIn(f"| BAL.COIN.VALUE | 7 | 4 | {rel}:COIN_VALUE | 불일치 |", gdd, "값 열은 그대로")
            self.assertIn("| BAL.OLD.THING | — | 4 | — | 폐기 |", gdd)
            self.assertIn(f"| RULE.COIN.PICKUP | 닿으면 줍는다 | 4 | {rel}:{CODE[engine][1]} | 동기 |", gdd)

    def test_balance_table(self):
        for _engine, root, code, table, _rel in self.each():
            before = open(code, encoding="utf-8").read()
            self.assertIn("5줄", run(TABLE, root, "export").stdout)
            self.assertIn("같다", run(TABLE, root, "check").stdout)
            first = open(table, "rb").read()
            run(TABLE, root, "export")
            self.assertEqual(first, open(table, "rb").read(), "같은 값이면 같은 파일")

            excel_save(table, {"PLAYER_HP": "120", "PLAYER_WALK_SPEED": "4.25", "COIN_VALUE": "5",
                               "UNMARKED": "3", "NO_SUCH_NAME": "1"})
            p = run(TABLE, root, "check", ok=False)
            self.assertEqual(p.returncode, 1)
            self.assertIn("PLAYER_HP: 코드 100 · 표 120", p.stdout)
            self.assertIn("표에만 있다 (무시): NO_SUCH_NAME", p.stdout)
            self.assertRegex(p.stdout, r"코드에만 있다 \(표에 없다\): [A-Z_]+\n", "코드에 새로 생긴 값이 표에 없으면 말한다")
            excel_save(table, {"PLAYER_HP": "100"})
            self.assertRegex(run(TABLE, root, "check").stdout, r"표와 코드가 같다 — 다만 코드에만 있는 값이 \d개다")
            excel_save(table, {"PLAYER_HP": "120", "PLAYER_WALK_SPEED": "4.25", "COIN_VALUE": "5", "UNMARKED": "3", "NO_SUCH_NAME": "1"})

            run(TABLE, root, "bake")
            after = open(code, encoding="utf-8").read()
            expect = before
            for old, new in (("100", "120"), ("4.0", "4.25"), ("2.5", "3.0")):
                self.assertEqual(expect.count(old), 1)
                expect = expect.replace(old, new)
            self.assertEqual(after, expect, "값만 바뀌고 나머지 글자는 그대로")
            self.assertIn("같다", run(TABLE, root, "check").stdout)

            excel_save(table, {"PLAYER_HP": "120.5"})
            self.assertIn("정수 값에 소수", run(TABLE, root, "check", ok=False).stderr)

    def test_serve(self):
        root, _code, table, _rel = self.project("godot")
        run(TABLE, root, "export")
        p = subprocess.Popen([sys.executable, TABLE, "--root", root, "serve", "0"], stdout=subprocess.PIPE, text=True)
        self.addCleanup(p.kill)
        url = p.stdout.readline().split(" ")[0]

        def get():
            return json.load(urllib.request.urlopen(url, timeout=5))

        one = get()
        self.assertEqual(one["values"], {"PLAYER_HP": 100.0, "PLAYER_WALK_SPEED": 4.0, "COIN_VALUE": 5.0,
                                         "UNMARKED": 2.5, "STRAY": 1.0})
        time.sleep(0.05)
        excel_save(table, {"PLAYER_HP": "80", "COIN_VALUE": "많이"})
        two = get()
        self.assertNotEqual(one["stamp"], two["stamp"], "저장하면 도장이 바뀐다")
        self.assertEqual(two["values"], {"PLAYER_HP": 80.0}, "숫자가 아닌 칸은 넘긴다")

        # 주소 전체를 요청 줄에 적는 클라이언트도 있다
        host, port = url.split("/")[2].split(":")
        with socket.create_connection((host, int(port)), timeout=5) as sock:
            sock.sendall(f"GET {url}?x=1 HTTP/1.0\r\n\r\n".encode())
            self.assertIn(b"200 OK", sock.makefile("rb").readline())
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(url + "x", timeout=5)
        self.assertEqual(e.exception.code, 404)

        open(table, "wb").write(b"PK\x03\x04 broken")
        with self.assertRaises(urllib.error.HTTPError) as e:
            get()
        self.assertEqual(e.exception.code, 503, "읽다 만 파일")

    def test_init(self):
        init = os.path.join(KIT, "skills/init/scripts/init.py")
        for engine in CODE:
            with self.subTest(engine=engine):
                root = tempfile.mkdtemp(prefix=f"kit-init-{engine}-")
                self.addCleanup(shutil.rmtree, root, True)
                out = run(init, root, engine).stdout
                self.assertIn("새로    kit.config.json", out)
                claude = open(os.path.join(root, "CLAUDE.md"), encoding="utf-8").read()
                self.assertIn("/gamedev-kit:gdd-sync", claude)
                extra = os.path.join(KIT, "engines", engine, "CLAUDE.md")
                if os.path.exists(extra):
                    self.assertIn(open(extra, encoding="utf-8").read().strip(), claude)
                self.rules_block(init, root, engine, claude)
                open(os.path.join(root, "CLAUDE.md"), "w", encoding="utf-8").write("내 규칙")
                again = run(init, root, engine).stdout
                self.assertNotIn("새로", again, "두 번째에는 아무것도 만들지 않는다")
                self.assertEqual(open(os.path.join(root, "CLAUDE.md"), encoding="utf-8").read(), "내 규칙")
                self.assertIn("블록이 없다 — `--rules`", again)
                self.assertNotIn("없는 절", again, "방금 깐 설정에는 빠진 절이 없다")
                engine_files = os.path.join(KIT, "engines", engine, "files")
                if os.path.exists(engine_files):  # 값 파일을 옮긴 프로젝트 — 다시 깔아도 틀이 또 생기지 않는다
                    moved = json.load(open(os.path.join(root, "kit.config.json"), encoding="utf-8"))["balance-table"]["code"]
                    os.remove(os.path.join(root, moved))
                    whole = open(os.path.join(root, "kit.config.json"), encoding="utf-8").read()
                    cfg = json.loads(whole)
                    cfg.pop("deploy")
                    cfg["balance-table"].pop("table")
                    json.dump(cfg, open(os.path.join(root, "kit.config.json"), "w"))
                    third = run(init, root, engine).stdout
                    self.assertIn("건너뜀  엔진 틀 1개", third)
                    self.assertFalse(os.path.exists(os.path.join(root, moved)))
                    self.assertIn("없는 절: ", third)
                    self.assertIn("deploy · balance-table.table", third.split("없는 절: ")[1])
                    self.assertIn("새로    " + moved, run(init, root, engine, "--files").stdout)
                    open(os.path.join(root, "kit.config.json"), "w", encoding="utf-8").write(whole)
                if os.path.exists(os.path.join(KIT, "engines", engine, "files")):
                    self.assertIn("같다", (run(TABLE, root, "export"), run(TABLE, root, "check"))[1].stdout)
                    self.assertIn("| 동기 | 3 |", run(REPORT, root).stdout, "틀의 예시 세 행이 값 파일과 짝이 맞는다")

    def test_init_project(self):
        """엔진 프로젝트를 알아보고 · 에디터와 모듈을 찾고 · 만든다. 에디터는 가짜다 — 엔진마다 다른 것은 engines/<엔진>/project.json 에서만 온다."""
        top = tempfile.mkdtemp(prefix="kit-init-project-")
        self.addCleanup(shutil.rmtree, top, True)
        home = os.path.join(top, "Hub", "Editor", "6000.1.2f1")
        unity = os.path.join(home, "Unity.app", "Contents", "MacOS", "Unity")
        os.makedirs(os.path.dirname(unity))
        open(unity, "w").write("""#!/bin/sh
while [ $# -gt 0 ]; do
  case "$1" in
    -createProject) mkdir -p "$2/ProjectSettings" && echo "m_EditorVersion: 6000.1.2f1" > "$2/ProjectSettings/ProjectVersion.txt"; shift;;
    -projectPath|--path) [ -f "$2/BROKEN" ] && echo "Assets/A.cs(1,1): error CS1002: ; expected"; shift;;
  esac
  shift
done
exit 0
""")
        os.chmod(unity, 0o755)
        spec = json.load(open(os.path.join(KIT, "engines/unity/project.json"), encoding="utf-8"))
        modules = os.path.normpath(os.path.join(os.path.dirname(unity), spec["editor"].get(sys.platform, {}).get("modules", "x")))
        root = os.path.join(top, "game")
        os.makedirs(os.path.join(root, "docs"))
        open(os.path.join(root, ".gitignore"), "w").write("Library/\n*.keystore")

        def init(*args, ok=True, **env):
            p = subprocess.run([sys.executable, INIT, "--root", root, *args], capture_output=True, text=True,
                               env=dict({k: v for k, v in os.environ.items() if k not in ("UNITY", "GODOT")}, **env))
            self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
            return p.stdout + p.stderr

        out = init("--detect")
        self.assertIn("엔진 프로젝트가 아니다 — 고를 수 있는 엔진: godot · unity", out)
        self.assertIn("아직 깔리지 않았다", out)
        self.assertIn("가리키는 파일이 없다", init("unity", "--editor", ok=False, UNITY=os.path.join(top, "없다")))
        if "modules" in spec["editor"].get(sys.platform, {}):
            out = init("unity", "--editor", ok=False, UNITY=unity)
            self.assertIn(f"Unity 6000.1.2f1 — {unity}", out)
            self.assertIn("없음  Android Build Support", out)
            self.assertIn("install-modules --version 6000.1.2f1 -m android android-sdk-ndk-tools android-open-jdk", out)
            for part in ("SDK", "NDK"):
                os.makedirs(os.path.join(modules, "AndroidPlayer", part))
            self.assertIn("OpenJDK 가 빠졌다", init("unity", "--editor", ok=False, UNITY=unity))
            os.makedirs(os.path.join(modules, "AndroidPlayer", "OpenJDK"))
            out = init("unity", "--editor", UNITY=unity)
            self.assertIn("있음  Android Build Support (SDK · NDK · OpenJDK)", out)
            self.assertIn(f"`## This game's rules` 아래에 적는다 (그 제목은 이미 있다 — 새로 만들지 않는다): 에디터 실행 파일 `{unity}` · 깔린 모듈 Android Build Support", out)

        self.assertIn("unity 프로젝트를 만들었다", init("unity", "--create", UNITY=unity))
        self.assertTrue(os.path.exists(os.path.join(root, "docs")), "있던 것은 그대로다")
        self.assertIn("unity — ProjectSettings/ProjectVersion.txt 가 있다", init("--detect"))
        self.assertIn("이미 unity 프로젝트다", init("unity", "--create", UNITY=unity))
        self.assertIn("이미 unity 프로젝트다 — godot 프로젝트를 그 위에 만들지 않는다", init("godot", "--create", ok=False))
        out = init("unity")
        self.assertIn("더함    .gitignore (unity — 10줄: Temp/", out, "이미 있는 두 줄은 다시 적지 않는다")
        self.assertNotIn("아직 unity 프로젝트가 아니다", out)
        self.assertIn("키트는 unity 로 이미 깔려 있다", init("--detect"))
        self.assertIn("줄이 이미 다 있다", init("unity", "--gitignore"))
        ignore = open(os.path.join(root, ".gitignore"), encoding="utf-8").read().split("\n")
        for line in open(os.path.join(KIT, "engines/unity/gitignore"), encoding="utf-8").read().split():
            self.assertEqual(ignore.count(line), 1, line)
        self.assertNotIn("error", init("unity", "--import", UNITY=unity))
        open(os.path.join(root, "BROKEN"), "w").close()
        self.assertIn("error CS1002", init("unity", "--import", ok=False, UNITY=unity))

        # Godot 은 만드는 명령이 없다 — 파일 하나가 프로젝트다. 에디터가 없어도 만든다
        root = os.path.join(top, "game2")
        os.makedirs(root)
        self.assertIn("아직 godot 프로젝트가 아니다", init("godot"))
        self.assertIn("godot 프로젝트를 만들었다", init("godot", "--create"))
        self.assertIn('config/version="0.1.0"', open(os.path.join(root, "project.godot"), encoding="utf-8").read())
        self.assertIn("godot — project.godot 가 있다", init("--detect"))
        self.assertIn("--headless --path", init("godot", "--import", GODOT=unity))

        # 판이 여럿이면 가장 새 것 — 숫자로 견준다. 스크립트는 엔진의 이름을 모른다: 폴더 하나가 엔진 하나다
        engines = os.path.join(top, "engines")
        os.makedirs(os.path.join(engines, "toy"))
        json.dump({"engine": "toy"}, open(os.path.join(engines, "toy", "kit.config.json"), "w"))
        toy = {"marker": "toy.project", "create": {"files": {"toy.project": ""}}, "modules": [{"name": "모듈", "dir": "m"}],
               "editor": {"name": "Toy", "env": "TOY", "version": "/ed/([^/]+)/", "missing": ["Toy 를 깐다"],
                          sys.platform: {"glob": [os.path.join(top, "ed", "*", "toy")], "modules": "mods"}}}
        json.dump(toy, open(os.path.join(engines, "toy", "project.json"), "w"))
        self.assertIn("Toy 에디터를 찾지 못했다 — 사용자가 깐다:\n  Toy 를 깐다", init("toy", "--editor", ok=False, GAMEDEV_KIT_ENGINES=engines))
        for version in ("9.2", "10.1"):
            os.makedirs(os.path.join(top, "ed", version, "mods", "m"))
            open(os.path.join(top, "ed", version, "toy"), "w").close()
        out = init("toy", "--editor", GAMEDEV_KIT_ENGINES=engines)
        self.assertIn(f"Toy 10.1 — {os.path.join(top, 'ed', '10.1', 'toy')}", out)
        self.assertIn("깔린 판 9.2 · 10.1 가운데 가장 새 것을 골랐다", out)
        self.assertIn("있음  모듈", out)

    def rules_block(self, init, root, engine, fresh):
        """CLAUDE.md 에서 키트의 것은 블록 하나다 — 판이 오르면 그 사이만 바뀌고 밖은 그대로다."""
        path = os.path.join(root, "CLAUDE.md")
        text = lambda: open(path, encoding="utf-8").read()
        put = lambda s: open(path, "w", encoding="utf-8").write(s)
        check = lambda: subprocess.run([sys.executable, init, "--rules-check"], cwd=root, capture_output=True, text=True).stdout
        self.assertRegex(fresh, r"<!-- gamedev-kit 시작 · [0-9a-f]{8} ")
        self.assertIn("<!-- gamedev-kit 끝 -->\n\n## This game's rules", fresh)
        self.assertIn("지금 판과 같다", run(init, root, engine, "--rules").stdout)
        self.assertEqual(check(), "", "같으면 조용하다")

        old = "## 옛 규칙\n옛 말"
        mark = __import__("hashlib").sha1(old.encode()).hexdigest()[:8]
        put(f"# 내 게임\n\n<!-- gamedev-kit 시작 · {mark} — 옛 판 -->\n{old}\n<!-- gamedev-kit 끝 -->\n\n## 이 게임의 규칙\n내가 쓴 함정\n")
        self.assertIn("옛 판이다 — `--rules`", run(init, root, engine).stdout)
        self.assertIn("지금 판으로 바꿨다", run(init, root, engine, "--rules").stdout)
        stale = text()
        put(f"# 내 게임\n\n<!-- gamedev-kit 시작 · {mark} — 옛 판 -->\n{old}\n<!-- gamedev-kit 끝 -->\n\n## 이 게임의 규칙\n내가 쓴 함정\n")
        self.assertIn("지금 판으로 바꿨다 (블록 밖은 그대로다)", check(), "세션이 시작될 때 훅이 스스로 맞춘다")
        self.assertEqual(text(), stale)
        self.assertTrue(text().startswith("# 내 게임\n\n<!-- gamedev-kit 시작 · "))
        self.assertTrue(text().endswith("<!-- gamedev-kit 끝 -->\n\n## 이 게임의 규칙\n내가 쓴 함정\n"), "블록 밖은 그대로다")
        self.assertNotIn("옛 말", text())
        self.assertIn("/gamedev-kit:gdd-sync", text())
        self.assertEqual(check(), "")

        put(text().replace("## The GDD and the code must always agree", "## 가끔 같아도 된다"))
        self.assertIn("손으로 고쳐져", check())
        self.assertIn("덮지 않는다", run(init, root, engine, "--rules", ok=False).stderr)
        self.assertIn("가끔 같아도 된다", text())
        run(init, root, engine, "--rules", "--force")
        self.assertNotIn("가끔 같아도 된다", text())

        put("# 옛 게임\n\n## Balance values are edited in the table\n이 게임에서 고쳐 쓴 말\n")
        self.assertIn("블록이 없다", check())
        out = run(init, root, engine, "--rules").stdout
        self.assertIn("끝에 키트 규칙 블록을 붙였다", out)
        self.assertIn("같은 제목의 절이 남아 있다 (옛 판을 옮겨 적은 것): Balance values are edited in the table", out)
        self.assertTrue(text().startswith("# 옛 게임\n\n## Balance values are edited in the table\n이 게임에서 고쳐 쓴 말\n\n<!-- gamedev-kit 시작"))
        put("# 옛 게임\n")
        cfg_path = os.path.join(root, "kit.config.json")
        whole = open(cfg_path, encoding="utf-8").read()
        json.dump(dict(json.loads(whole), init={"rules": False}), open(cfg_path, "w"))
        self.assertEqual(check(), "", "알리지 말라고 했으면 조용하다")
        open(cfg_path, "w", encoding="utf-8").write(whole)
        os.remove(path)
        self.assertEqual(check(), "")
        self.assertIn("새로 만들었다", run(init, root, engine, "--rules").stdout)
        self.assertEqual(text().replace("\r", ""), fresh)

    def test_no_config(self):
        root = tempfile.mkdtemp(prefix="kit-none-")
        self.addCleanup(shutil.rmtree, root, True)
        open(os.path.join(root, "kit.config.json"), "w").write("{}")
        self.assertIn("code_ext", run(REPORT, root, ok=False).stderr)
        self.assertIn("balance-table.code", run(TABLE, root, "check", ok=False).stderr)

    def test_deploy(self):
        root = tempfile.mkdtemp(prefix="kit-deploy-")
        self.addCleanup(shutil.rmtree, root, True)
        butler, log = os.path.join(root, "butler"), os.path.join(root, "butler.log")
        open(butler, "w").write(f"#!/bin/sh\necho \"$@\" >> '{log}'\n")
        os.chmod(butler, 0o755)
        cfg = {"itch": "me/game", "butler": butler, "version": {"file": "VERSION", "regex": "v=(\\S+)"},
               "pre": ["true"], "channels": {"html5": {"build": "mkdir -p out && echo hi > out/index.html",
                                                        "dir": "out", "must": "index.html"}}}

        def write(**over):
            json.dump({"deploy": dict(cfg, **over)}, open(os.path.join(root, "kit.config.json"), "w"))

        write()
        open(os.path.join(root, "VERSION"), "w").write("v=0.3.0\n")
        self.assertIn("me/game · 버전 0.3.0", run(DEPLOY, root, "check").stdout)
        self.assertIn("빌드가 없다", run(DEPLOY, root, "push", "--dry-run", ok=False).stderr)
        self.assertIn("파일 1개", run(DEPLOY, root, "build").stdout)
        self.assertIn("올리지 않는다", run(DEPLOY, root, "push", "html5", "--dry-run").stdout)
        run(DEPLOY, root, "push")
        out = os.path.join(os.path.realpath(root), "out")
        self.assertEqual(open(log).read().replace(os.path.join(root, "out"), out).split("\n")[:2],
                         [f"push {out} me/game:html5 --userversion 0.3.0 --dry-run",
                          f"push {out} me/game:html5 --userversion 0.3.0"])
        self.assertIn("모르는 채널", run(DEPLOY, root, "build", "win", ok=False).stderr)

        write(pre=["false"])
        self.assertIn("사전 검사 실패", run(DEPLOY, root, "push", ok=False).stderr)
        self.assertEqual(len(open(log).read().strip().split("\n")), 2, "검사가 실패하면 butler 를 부르지 않는다")
        write(itch="game")
        self.assertIn("사용자/게임", run(DEPLOY, root, "check", ok=False).stderr)
        write(butler=os.path.join(root, "no-butler"))
        self.assertIn("butler 가 없다", run(DEPLOY, root, "check", ok=False).stderr)

    def test_deploy_engine_config(self):
        for engine in CODE:
            with self.subTest(engine=engine):
                root = tempfile.mkdtemp(prefix=f"kit-deploy-{engine}-")
                self.addCleanup(shutil.rmtree, root, True)
                shutil.copy(os.path.join(KIT, "engines", engine, "kit.config.json"), os.path.join(root, "kit.config.json"))
                cfg = json.load(open(os.path.join(root, "kit.config.json"), encoding="utf-8"))
                self.assertNotIn("promo", cfg)
                self.assertIn("deploy.itch", run(DEPLOY, root, "check", "--dirty", ok=False).stderr, "깔린 직후에는 대상이 비어 있다")
                if engine in VERSION_LINE:
                    path = os.path.join(root, cfg["deploy"]["version"]["file"])
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    open(path, "w").write("앞줄\n" + VERSION_LINE[engine] + "\n")
                    self.assertEqual(run(DEPLOY, root, "version").stdout.strip(), "1.2.3")
                if not cfg["deploy"]["channels"]:
                    self.assertIn("channels 가 비어", run(DEPLOY, root, "build", ok=False).stderr)

    def asset_project(self, blender):
        """가짜 OpenAI · Meshy 서버와 그것을 보는 프로젝트. (root, 부르는 함수, 서버가 받은 요청들)"""
        seen = []

        class Fake(http.server.BaseHTTPRequestHandler):
            def reply(self, body, raw=None):
                seen.append((self.command, self.path, body))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(raw if raw is not None else json.dumps(self.answer(body)).encode())

            def answer(self, body):
                if self.path.startswith("/images/"):
                    return {"data": [{"b64_json": base64.b64encode(f"png{len(seen)}".encode()).decode()}]}
                if self.command == "POST":
                    return {"result": f"task{len(seen)}"}
                polls = sum(1 for m, p, _b in seen if m == "GET" and p == self.path)
                done = polls >= 2  # 첫 물음에는 아직이라고 한다
                return {"status": "SUCCEEDED" if done else "IN_PROGRESS", "progress": 100 if done else 40, "consumed_credits": 20,
                        "model_urls": {"glb": f"http://127.0.0.1:{self.server.server_port}/file.glb"}}

            def do_GET(self):
                self.reply(None, raw_glb() if self.path == "/file.glb" else None)

            def do_POST(self):
                data = self.rfile.read(int(self.headers["Content-Length"]))
                self.reply(json.loads(data) if self.headers["Content-Type"] == "application/json" else data)

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        root = tempfile.mkdtemp(prefix="kit-asset-")
        self.addCleanup(shutil.rmtree, root, True)
        cfg = json.load(open(os.path.join(KIT, "engines/godot/kit.config.json"), encoding="utf-8"))
        cfg["asset"].update(blender=blender, env_file=os.path.join(root, "none.env"))
        json.dump(cfg, open(os.path.join(root, "kit.config.json"), "w"))
        os.makedirs(os.path.join(root, "docs"))
        base = f"http://127.0.0.1:{server.server_port}"
        env = dict(os.environ, OPENAI_API_BASE=base, MESHY_API_BASE=base, ASSET_POLL_SEC="0",
                   OPENAI_API_KEY="k1", MESHY_API_KEY="k2")

        def asset(*args, ok=True, env=env):
            p = subprocess.run([sys.executable, ASSET, "--root", root, *args], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
            return p.stdout + p.stderr

        return root, asset, seen, env

    def test_asset(self):
        blender = os.path.join(tempfile.mkdtemp(prefix="kit-blender-"), "blender")
        self.addCleanup(shutil.rmtree, os.path.dirname(blender), True)
        open(blender, "w").write("""#!/bin/sh
for a; do shift; [ "$a" = "--" ] && break; done
cp "$1" "$2" && echo "FINISH {\\"tris\\": 2, \\"size\\": [1, $3, 1]}"
""")
        os.chmod(blender, 0o755)
        root, asset, seen, env = self.asset_project(blender)
        rec = lambda n: json.load(open(os.path.join(root, "assets/_gen", n, "asset.json"), encoding="utf-8"))
        posts = lambda path: [b for m, p, b in seen if m == "POST" and p == path]

        asset("new", "crate", "--size", "1.2", "A wooden crate with iron corners")
        self.assertIn("이미 있다", asset("new", "crate", "--size", "1", "x", ok=False))
        self.assertIn("소문자", asset("new", "Big-Crate", "--size", "1", "x", ok=False))
        self.assertIn("asset-style", asset("image", "crate", ok=False), "화풍이 없으면 그리지 않는다")
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("# 규칙\n<!-- asset-style -->\nChunky low-poly,\nmuted palette.\n<!-- /asset-style -->\n")
        self.assertIn("OPENAI_API_KEY 가 없다", asset("image", "crate", ok=False, env={k: v for k, v in env.items() if k != "OPENAI_API_KEY"}))
        self.assertEqual(seen, [])

        asset("image", "crate")
        first = posts("/images/generations")[0]
        self.assertIn("A wooden crate with iron corners. Front view", first["prompt"])
        self.assertIn("Chunky low-poly, muted palette.", first["prompt"])
        self.assertEqual((first["background"], first["model"]), ("transparent", "gpt-image-2.5-flare"))
        back = posts("/images/edits")[0]
        self.assertIn(b"back view", back)
        self.assertIn(b'name="image[]"; filename="front.png"', back, "뒷면은 앞면을 보고 그린다")
        self.assertIn("The object is: A wooden crate with iron corners. Draw what is really seen from this side — do not mirror".encode(), back,
                      "앞 그림만 보고 그리면 앞을 뒤집어 베낀다 — 무엇인지와 뒤집지 말 것을 같이 말한다")
        self.assertIn("보고 approve", asset("status"))
        os.makedirs(os.path.join(root, "assets/_gen/loose"))
        open(os.path.join(root, "assets/_gen/loose/asset.json"), "w").write('{"name": "loose"}')
        self.assertIn("loose", asset("status"), "손으로 적어 빠진 것이 있는 기록에도 죽지 않는다")
        shutil.rmtree(os.path.join(root, "assets/_gen/loose"))

        self.assertIn("승인된 이미지가 없다", asset("mesh", "crate", ok=False))
        asset("approve", "crate")
        self.assertIn("--note 는 --view 와 같이", asset("image", "crate", "--note", "x", ok=False))
        asset("image", "crate", "--view", "back", "--note", "The hinge  side faces the viewer")
        self.assertIn(b"show the side this view faces. The hinge side faces the viewer. Chunky low-poly", posts("/images/edits")[-1], "그 면에만 붙는 글")
        self.assertEqual(rec("crate")["notes"], {"back": "The hinge side faces the viewer"})
        self.assertIn("승인된 이미지가 없다", asset("mesh", "crate", ok=False), "이미지를 다시 그리면 승인도 다시")
        self.assertEqual(posts("/multi-image-to-3d"), [])
        asset("approve", "crate")

        out = asset("mesh", "crate")
        self.assertIn("IN_PROGRESS 40%", out)
        self.assertIn("assets/models/crate.glb — 삼각형 2 · 1 × 1.2 × 1 m", out)
        made = posts("/multi-image-to-3d")
        self.assertEqual(len(made), 1)
        self.assertEqual(len(made[0]["image_urls"]), 2)
        self.assertTrue(made[0]["image_urls"][0].startswith("data:image/png;base64,"))
        self.assertEqual((made[0]["target_polycount"], made[0]["should_remesh"], made[0]["target_formats"]), (5000, True, ["glb"]))
        self.assertEqual(open(os.path.join(root, "assets/models/crate.glb"), "rb").read(), raw_glb())
        self.assertEqual((rec("crate")["meshy"]["credits"], rec("crate")["out"]), (20, "assets/models/crate.glb"))
        self.assertNotIn("image_urls", json.dumps(rec("crate")), "기록에 이미지를 통째로 넣지 않는다")
        self.assertIn("끝", asset("status"))

        asset("mesh", "crate")
        self.assertEqual(len(posts("/multi-image-to-3d")), 1, "끝난 작업을 다시 사지 않는다")
        self.assertIn("× 2.0 ×", asset("finish", "crate", "--size", "2"))
        self.assertEqual(len(posts("/multi-image-to-3d")), 1, "크기만 바꾸는 데 Meshy 를 다시 부르지 않는다")

        # 작업을 만든 뒤 끊겼다 — 다시 돌리면 그 작업을 이어서 기다린다
        asset("new", "barrel", "--size", "1", "--poly", "800", "A barrel")
        asset("image", "barrel")
        asset("approve", "barrel")
        r = rec("barrel")
        r["meshy"] = {"id": "old-task", "status": "IN_PROGRESS", "images": r["approved"]}
        json.dump(r, open(os.path.join(root, "assets/_gen/barrel/asset.json"), "w"))
        asset("mesh", "barrel")
        self.assertEqual(len(posts("/multi-image-to-3d")), 1)
        self.assertIn(("GET", "/multi-image-to-3d/old-task", None), seen)

        # 모든 에셋에 붙는 글은 세 겹이다 — 화풍(고정) · 세계 · 배운 것. 물린 말은 기록에, 두루 맞는 말은 배운 것에
        design = os.path.join(root, "docs/DESIGN.md")
        self.assertIn("asset-learned", asset("learn", "Metal is matte", ok=False), "자리가 없으면 넣으라고 한다")
        open(design, "a").write("<!-- asset-world -->\nBronze age,\nweathered wood.\n<!-- /asset-world -->\n<!-- asset-learned -->\n<!-- /asset-learned -->\n")
        self.assertIn("물림을 적었다 (1번째)", asset("reject", "barrel", "쇠가 너무 번쩍여. 다시"))
        self.assertEqual(rec("barrel")["said"][0]["said"], "쇠가 너무 번쩍여. 다시")
        self.assertIsNone(rec("barrel")["approved"], "물리면 승인이 풀린다")
        self.assertIn("배운 것 1줄", asset("learn", "Metal is matte, never glossy."))
        asset("learn", "Faces are simple")
        self.assertIn("<!-- asset-learned -->\n- Metal is matte, never glossy\n- Faces are simple\n<!-- /asset-learned -->", open(design).read())
        out = asset("look")
        self.assertIn("세계: Bronze age, weathered wood.", out)
        self.assertIn("배운 것: Metal is matte, never glossy / Faces are simple", out)
        asset("new", "urn", "--size", "0.5", "A clay urn")
        asset("image", "urn")
        self.assertIn("A clay urn. Front view, straight on, camera at the object's mid height. Chunky low-poly, muted palette. "
                      "Bronze age, weathered wood. Metal is matte, never glossy. Faces are simple. A single object", posts("/images/generations")[-1]["prompt"])
        self.assertEqual(rec("urn")["image"]["style"], __import__("hashlib").sha1(b"Chunky low-poly, muted palette.").hexdigest()[:8])

        # 레퍼런스 사진 — 글로 옮기지 않고 사진을 보여 주며 그리게 한다
        self.assertIn("레퍼런스가 없다", asset("new", "lamp", "--size", "0.3", "--ref", "ref/lamp.jpg", "An oil lamp", ok=False))
        os.makedirs(os.path.join(root, "ref"))
        open(os.path.join(root, "ref/lamp.jpg"), "wb").write(b"JPEG-lamp")
        open(os.path.join(root, "ref/jar.png"), "wb").write(b"PNG-jar")
        self.assertIn("레퍼런스 ref/lamp.jpg", asset("new", "lamp", "--size", "0.3", "--ref", "ref/lamp.jpg", "An oil lamp"))
        before = len(posts("/images/generations"))
        asset("image", "lamp")
        self.assertEqual(len(posts("/images/generations")), before, "레퍼런스가 있으면 글만으로 그리지 않는다")
        drew = posts("/images/edits")[-2]
        self.assertIn(b'filename="lamp.jpg"\r\nContent-Type: image/jpeg\r\n\r\nJPEG-lamp', drew)
        self.assertIn(b"The first attached image shows the subject: redraw this exact object", drew)
        self.assertIn(b"An oil lamp. Front view", drew)
        self.assertIn(b'filename="front.png"', posts("/images/edits")[-1], "나머지 면은 그린 앞면을 보고")
        asset("image", "urn", "--ref", "ref/jar.png")
        self.assertEqual(rec("urn")["ref"], "ref/jar.png", "나중에 레퍼런스를 줄 수도 있다")
        self.assertIn("--as-is 는", asset("new", "pot", "--size", "1", "--ref", "ref/lamp.jpg", "--as-is", "A pot", ok=False))
        asset("new", "jar", "--size", "0.4", "--ref", "ref/jar.png", "--as-is", "A jar")
        edits = len(posts("/images/edits"))
        asset("image", "jar")
        self.assertEqual(open(os.path.join(root, "assets/_gen/jar/front.png"), "rb").read(), b"PNG-jar", "그대로 쓰면 다시 그리지 않는다")
        self.assertEqual(len(posts("/images/edits")), edits + 1, "뒷면만 그린다")

        # 에셋 시트 — 전부를 한 화면에 나란히. 화풍 문단이 바뀌면 그 전에 그린 것에 표시가 선다
        cfg_path = os.path.join(root, "kit.config.json")
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        cfg["asset"]["refs"] = ["assets/_gen/crate/front.png"]
        json.dump(cfg, open(cfg_path, "w"))
        self.assertIn("docs/board/index.html", run(BOARD, root).stdout)
        sheet = open(os.path.join(root, "docs/board/assets.html"), encoding="utf-8").read()
        index = open(os.path.join(root, "docs/board/index.html"), encoding="utf-8").read()
        self.assertIn('<a class="tile go" href="assets.html"><span class="lab">모델 · 그림 5 · 소리 0</span><b>에셋 시트 →</b></a>', index)
        self.assertLess(index.index('href="assets.html"'), index.index('class="flow"'), "시트로 가는 길은 단계 카드 위, 늘 보이는 자리에 있다")
        self.assertIn("Chunky low-poly, muted palette.", sheet)
        self.assertIn("Bronze age, weathered wood.", sheet)
        self.assertIn("Faces are simple", sheet)
        tile = lambda n: sheet.split(f"<span>{n}</span>")[1].split("</div></div>")[0]
        self.assertIn("게임에 있음", tile("crate"))
        self.assertIn("견본", tile("crate"))
        self.assertIn('title="쇠가 너무 번쩍여. 다시">물림 1', tile("barrel"))
        self.assertIn("레퍼런스", tile("lamp"))
        self.assertNotIn("옛 화풍", sheet)
        changed = open(design).read().replace("muted palette.", "bright palette.")
        open(design, "w").write(changed)
        run(BOARD, root, "--if-stale")
        sheet = open(os.path.join(root, "docs/board/assets.html"), encoding="utf-8").read()
        self.assertIn("옛 화풍으로 그린 것 4", sheet, "그대로 쓴 사진은 화풍과 상관없다")

        # 기록 없이 게임에 든 것도 시트에 놓인다. 쪽이 빠져 있으면(키트를 올린 뒤) 훅이 다시 그린다
        os.makedirs(os.path.join(root, "assets/ui"))
        open(os.path.join(root, "assets/ui/icon.png"), "wb").write(b"PNG")
        open(os.path.join(root, "assets/models/hand.glb"), "wb").write(b"glb")
        open(os.path.join(root, "assets/models/hand_normal.png"), "wb").write(b"PNG")  # 모델에서 풀려 나온 텍스처는 놓지 않는다
        os.remove(os.path.join(root, "docs/board/assets.html"))
        run(BOARD, root, "--if-stale")
        sheet = open(os.path.join(root, "docs/board/assets.html"), encoding="utf-8").read()
        self.assertIn("기록 없이 든 것<small>2</small>", sheet)
        self.assertIn("<span>icon.png</span>", sheet)
        self.assertIn("<span>hand.glb</span>", sheet)
        self.assertNotIn("<span>crate.glb</span>", sheet, "기록이 있는 모델을 두 번 놓지 않는다")
        cfg["asset"]["work"] = "art/_gen"
        json.dump(cfg, open(cfg_path, "w"))
        os.rename(os.path.join(root, "assets/_gen"), os.path.join(root, "art_tmp"))
        os.makedirs(os.path.join(root, "art"))
        os.rename(os.path.join(root, "art_tmp"), os.path.join(root, "art/_gen"))
        run(BOARD, root)
        self.assertIn("<span>lamp</span>", open(os.path.join(root, "docs/board/assets.html"), encoding="utf-8").read(), "에셋 기록의 자리를 옮기면 판도 따라간다")
        self.assertNotIn("옛 화풍", sheet.split("<span>jar</span>")[1].split("</div></div>")[0])

    @unittest.skipUnless(shutil.which("blender"), "blender 가 없다")
    def test_start(self):
        """빈 게임이 첫 사이클에 닿기까지 — 어디에 서 있는지는 파일에서 읽는다. 컨셉 그림은 가짜 API 서버가 그린다."""
        none = tempfile.mkdtemp(prefix="kit-start-none-")
        self.addCleanup(shutil.rmtree, none, True)
        self.assertIn("/gamedev-kit:init", run(START, none, "status", ok=False).stderr)
        p = subprocess.run([sys.executable, START, "status"], cwd=none, capture_output=True, text=True)
        self.assertEqual((p.returncode, "/gamedev-kit:init" in p.stderr), (1, True))

        root, _asset, seen, env = self.asset_project("blender")
        self.assertIn("틀이 생긴다", run(START, root, "status", ok=False).stderr)
        gdd = os.path.join(root, "docs/GDD.md")
        shutil.copy(os.path.join(KIT, "templates/GDD.md"), gdd)

        def fill(title):
            text = open(gdd, encoding="utf-8").read()
            open(gdd, "w", encoding="utf-8").write(text.replace(f"{title}\n", f"{title}\n\n정한 것\n", 1))

        out = run(START, root, "status").stdout
        self.assertIn("[할 것] GDD (docs/GDD.md) — 비어 있는 절: 개요 · 게임 구조 · 규칙 · 제작 범위 · 비어 있어도 되는 절: 톤 · 사운드", out, "틀에 있던 줄은 글이 아니다")
        self.assertIn("다음: GDD 단계", out)
        self.assertTrue(os.path.exists(out.strip().split(": ")[-1]), out)
        self.assertTrue(out.strip().endswith(os.path.join("stages", "gdd.md")))
        for title in ("## 1. 개요", "## 2. 게임 구조", "## 4. 규칙과 시스템"):
            fill(title)
        self.assertIn("비어 있는 절: 제작 범위", run(START, root, "status").stdout)
        self.assertIn("건너뛴다", run(START, root, "skip", "gdd").stdout)
        self.assertIn("gdd · concept", run(START, root, "skip", "goal", ok=False).stderr)
        out = run(START, root, "status").stdout
        self.assertIn("[건너뜀] GDD", out)
        self.assertIn("건너뛴 단계: GDD", out)
        self.assertIn("다음: 컨셉 단계", out)
        self.assertEqual(json.load(open(os.path.join(root, "docs/start/state.json"), encoding="utf-8")), {"skip": ["gdd"]})
        run(START, root, "unskip", "gdd")
        fill("## 7. 제작 범위")
        out = run(START, root, "status").stdout
        self.assertIn("[됨] GDD (docs/GDD.md) — 글이 있는 절: 개요 · 게임 구조 · 규칙 · 제작 범위 · 비어 있어도 되는 절: 톤 · 사운드\n", out)
        self.assertNotIn("건너뛴 단계", out)
        self.assertIn("아트 방향 절이 비어 있다 · docs/concept/ 에 그림이 없다", out)
        self.assertTrue(out.strip().endswith(os.path.join("stages", "concept.md")))

        def concept(*args, ok=True, env=env):
            p = subprocess.run([sys.executable, CONCEPT, "--root", root, *args], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
            return p.stdout + p.stderr

        posts = lambda path: [b for m, p, b in seen if m == "POST" and p == path]
        self.assertIn("그림이 없다", concept("list"))
        self.assertIn("OPENAI_API_KEY 가 없다", concept("new", "look_a", "x", ok=False, env={k: v for k, v in env.items() if k != "OPENAI_API_KEY"}))
        self.assertIn("소문자", concept("new", "Look A", "x", ok=False))
        self.assertEqual(seen, [])
        self.assertIn("docs/concept/look_a.png — 사용자가 열어 본다", concept("new", "look_a", "A small room seen from above,\n soft light"))
        first = posts("/images/generations")[0]
        self.assertEqual((first["prompt"], first["size"], first["model"], first["quality"]),
                         ("A small room seen from above, soft light", "1024x1536", "gpt-image-2.5-flare", "medium"))
        self.assertNotIn("background", first, "컨셉 그림은 배경을 비우지 않는다")
        self.assertEqual(open(os.path.join(root, "docs/concept/look_a.png"), "rb").read(), b"png1")
        self.assertIn("이미 있다 — 덮어쓰지 않는다", concept("new", "look_a", "another", ok=False))
        self.assertEqual(len(seen), 1, "있는 이름이면 그리지 않는다")
        self.assertIn("레퍼런스가 없다", concept("new", "look_b", "--ref", "nothing", "x", ok=False))
        concept("new", "look_b", "--size", "1536x1024", "--ref", "look_a", "warmer light")
        edit = posts("/images/edits")[0]
        self.assertIn(b'name="image[]"; filename="look_a.png"', edit, "마음에 든 그림을 보고 고쳐 그린다")
        self.assertIn(b"png1", edit)
        self.assertIn(b"Change only what is asked below and leave everything else as it is. warmer light", edit)
        self.assertIn(b"1536x1024", edit)
        open(os.path.join(root, "docs/concept/photo.jpg"), "wb").write(b"jpg")
        out = concept("list")
        self.assertIn("docs/concept/look_a.png — 1024x1536 · A small room seen from above, soft light", out)
        self.assertIn("docs/concept/look_b.png — 1536x1024 · docs/concept/look_a.png 에서 고쳐 그림 · warmer light", out)
        self.assertIn("docs/concept/photo.jpg — 사용자가 넣은 그림", out)

        out = run(START, root, "status").stdout
        self.assertIn("[할 것] 컨셉 — docs/GDD.md 의 아트 방향 절이 비어 있다", out)
        self.assertNotIn("그림이 없다", out)
        fill("## 5. 아트 방향")
        out = run(START, root, "status").stdout
        self.assertIn("[됨] 컨셉 — 아트 방향이 적혀 있고 그림이 3장 있다", out)
        self.assertIn("다음: 첫 목표 단계", out)
        self.assertTrue(out.strip().endswith(os.path.join("stages", "goal.md")))
        run(CYCLE, root, "new", "first", "한 바퀴를 돈다")
        out = run(START, root, "status").stdout
        self.assertIn("시작은 끝났다 — 사이클 문서가 있다 (docs/cycle/01-first.md). 이어 가는 것은 `/gamedev-kit:cycle`", out)
        self.assertNotIn("다음:", out)

        # GDD 를 다른 자리에 둔 게임 · 틀을 고쳐 쓴 GDD — 없는 제목은 비었다고 하지 않는다
        other = tempfile.mkdtemp(prefix="kit-start-other-")
        self.addCleanup(shutil.rmtree, other, True)
        json.dump({"gdd-sync": {"gdd": "design/GDD.md"}}, open(os.path.join(other, "kit.config.json"), "w"))
        os.makedirs(os.path.join(other, "design"))
        open(os.path.join(other, "design/GDD.md"), "w", encoding="utf-8").write("# 게임\n\n## 개요\n글\n\n## 규칙\n\n## 부록 A\n")
        out = run(START, other, "status").stdout
        self.assertIn("[할 것] GDD (design/GDD.md) — 비어 있는 절: 규칙 · 글이 있는 절: 개요 · 틀의 제목이 없어 보지 못한 절: 게임 구조 · 제작 범위 · 아트 방향", out)

    def test_asset_blender(self):
        root, asset, seen, _env = self.asset_project("blender")
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("<!-- asset-style -->\nLow-poly.\n<!-- /asset-style -->\n")
        asset("new", "pillar", "--size", "1.5", "--poly", "800", "A stone pillar")
        asset("image", "pillar")
        asset("approve", "pillar")
        self.assertIn("삼각형 2 · 0.75 × 1.5 × 0.375 m", asset("mesh", "pillar"))
        self.assertEqual([b["target_polycount"] for m, p, b in seen if p == "/multi-image-to-3d" and m == "POST"], [800])
        d = open(os.path.join(root, "assets/models/pillar.glb"), "rb").read()
        g = json.loads(d[20:20 + struct.unpack("<I", d[12:16])[0]])
        box = next(a for a in g["accessors"] if "min" in a)
        for got, want in zip(box["min"] + box["max"], [-0.375, 0, -0.1875, 0.375, 1.5, 0.1875]):
            self.assertAlmostEqual(got, want, places=4, msg="가장 긴 변이 1.5 m, 바닥이 0, 가운데가 원점")
        self.assertNotIn("translation", g["nodes"][0])
        self.assertNotIn("scale", g["nodes"][0])

    def test_sprite(self):
        """2D: 그림 → 승인 → 움직이는 시트. 가짜 Ludo 서버 — 작업을 걸고, 물어서 받고, 받은 주소에서 파일을 내려받는다."""
        seen, jobs, webp = [], {}, []
        png = lambda w, h: b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sII", 13, b"IHDR", w, h)

        class Fake(http.server.BaseHTTPRequestHandler):
            def reply(self, body, code=200):
                self.send_response(code)
                self.end_headers()
                self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

            def read(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_POST(self):
                body, here = json.loads(self.read()), f"http://127.0.0.1:{self.server.server_port}"
                seen.append(("POST", self.path, self.headers.get("Authorization"), body))
                if self.path == "/assets/uploads":
                    return self.reply({"upload_url": f"{here}/put/{len(seen)}", "file_url": f"{here}/up/{len(seen)}"})
                if "터진다" in body.get("prompt", ""):
                    return self.reply({"message": "안 된다"}, 400)
                jobs[f"job{len(seen)}"] = self.path
                self.reply({"id": f"job{len(seen)}", "status": "queued"}, 202)

            def do_PUT(self):
                seen.append(("PUT", self.path, self.headers.get("Authorization"), self.read()))
                self.reply(b"")

            def do_GET(self):
                here, path = f"http://127.0.0.1:{self.server.server_port}", self.path.split("?")[0]
                seen.append(("GET", self.path, self.headers.get("Authorization"), None))
                if path == "/assets/account":
                    return self.reply({"credits": {"available": 87.5}})
                if path.startswith("/file/") and webp:
                    return self.reply(b"RIFF\x10\x00\x00\x00WEBPVP8 ")
                if path.startswith("/file/"):
                    return self.reply(png(512, 256) if "sheet" in path else png(1024, 1024) + path.encode())
                job = path.rsplit("/", 1)[1]
                if sum(1 for m, p, _a, _b in seen if m == "GET" and p == self.path) < 2:  # 첫 물음에는 아직이라고 한다
                    return self.reply({"id": job, "status": "running", "poll_after_ms": 1})
                if jobs[job] == "/assets/sprite/animate":
                    result = {"spritesheet_url": f"{here}/file/sheet-{job}.png", "gif_url": f"{here}/file/{job}.gif",
                              "num_frames": 14, "num_cols": 4, "num_rows": 4, "duration": 2.8}
                else:
                    result = [{"url": f"{here}/file/{job}.png"}]
                self.reply({"id": job, "status": "succeeded", "credits_charged": 9 if isinstance(result, dict) else 0.5, "result": result})

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        root = tempfile.mkdtemp(prefix="kit-sprite-")
        self.addCleanup(shutil.rmtree, root, True)
        cfg = json.load(open(os.path.join(KIT, "engines/godot/kit.config.json"), encoding="utf-8"))
        cfg["asset"]["env_file"] = os.path.join(root, "none.env")

        def write(**over):
            cfg["asset"]["sprite"].update(over)
            json.dump(cfg, open(os.path.join(root, "kit.config.json"), "w"))

        write(view="Seen from directly above")
        os.makedirs(os.path.join(root, "docs"))
        env = dict(os.environ, LUDO_API_BASE=f"http://127.0.0.1:{server.server_port}", LUDO_API_KEY="k4", ASSET_POLL_SEC="0")

        def sprite(*args, ok=True, env=env):
            p = subprocess.run([sys.executable, SPRITE, "--root", root, *args], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
            return p.stdout + p.stderr

        rec = lambda n: json.load(open(os.path.join(root, "assets/_gen", n, "sprite.json"), encoding="utf-8"))
        posts = lambda path: [b for m, p, _a, b in seen if m == "POST" and p == path]

        sprite("new", "cook", "A cook in an apron")
        self.assertIn("이미 있다", sprite("new", "cook", "x", ok=False))
        self.assertIn("asset-style", sprite("image", "cook", ok=False), "화풍이 없으면 그리지 않는다")
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("<!-- asset-style -->\nFlat shapes,\nwarm palette.\n<!-- /asset-style -->\n")
        self.assertIn("LUDO_API_KEY 가 없다", sprite("image", "cook", ok=False, env={k: v for k, v in env.items() if k != "LUDO_API_KEY"}))
        self.assertEqual(seen, [])

        out = sprite("image", "cook")
        self.assertIn("assets/_gen/cook/still.png — 1024 × 1024 px · 크레딧 0.5", out)
        first = posts("/assets/image")[0]
        self.assertEqual(first["image_type"], "sprite")
        self.assertTrue(first["prompt"].startswith("A cook in an apron. Seen from directly above. Flat shapes, warm palette. A single subject"), first["prompt"])
        self.assertEqual({a for m, p, a, _b in seen if not p.startswith("/file/")}, {"ApiKey k4"})
        self.assertEqual({a for m, p, a, _b in seen if p.startswith("/file/")}, {None}, "받은 주소에는 키를 보내지 않는다")
        self.assertIn("보고 approve", sprite("status"))

        # 승인한 그림만 움직인다. 승인하면 게임 폴더에 놓인다
        self.assertIn("승인된 그림이 없다", sprite("animate", "cook", "walk", "walking", ok=False))
        self.assertIn("승인 — assets/sprites/cook.png", sprite("approve", "cook"))
        self.assertIn("--frames 는", sprite("animate", "cook", "walk", "--frames", "12", "walking", ok=False))
        out = sprite("animate", "cook", "walk", "--seconds", "4", "--frames", "16", "walking forward")
        self.assertIn("assets/sprites/cook_walk.png — 14프레임 · 4열 × 4행 · 한 칸 128 × 64 px · 크레딧 9", out)
        self.assertIn("assets/_gen/cook/walk.gif", out)
        ask = posts("/assets/sprite/animate")[0]
        self.assertEqual((ask["motion_prompt"], ask["duration"], ask["frames"], ask["model"], ask["gif"]), ("walking forward", 4.0, 16, "hydra", True))
        self.assertTrue(ask["initial_image"].endswith(f"/up/{len(seen) - [s[1] for s in seen[::-1]].index('/assets/uploads')}"), "그림을 올리고 그 주소를 건넨다")
        put = [s for s in seen if s[0] == "PUT"][0]
        self.assertEqual((put[2], put[3]), (None, open(os.path.join(root, "assets/_gen/cook/still.png"), "rb").read()))
        self.assertEqual(rec("cook")["motions"]["walk"]["cell"], [128, 64])
        self.assertIn("cook_walk.png — 14프레임", sprite("status"))
        self.assertIn("87.5", sprite("credits"))

        # 끊긴 작업은 같은 명령으로 잇는다 — 새로 사지 않는다
        r = rec("cook")
        r["motions"]["walk"]["job"] = {"id": "job-old", "status": "running"}
        json.dump(r, open(os.path.join(root, "assets/_gen/cook/sprite.json"), "w"))
        jobs["job-old"] = "/assets/sprite/animate"
        sprite("animate", "cook", "walk", "walking forward")
        self.assertEqual(len(posts("/assets/sprite/animate")), 1)
        self.assertEqual(rec("cook")["motions"]["walk"]["made"], 2)

        # 물리면 승인이 풀린다. 다시 그려도 풀린다
        self.assertIn("물림을 적었다 (1번째)", sprite("reject", "cook", "앞치마가 너무 커"))
        self.assertIn("승인된 그림이 없다", sprite("animate", "cook", "idle", "breathing", ok=False))

        # 화풍 기준 그림이 있으면 그 화풍에 맞추고, 레퍼런스가 있으면 그것을 다시 그린다. --as-is 는 그대로 쓴다
        os.makedirs(os.path.join(root, "ref"))
        open(os.path.join(root, "ref/hero.png"), "wb").write(png(300, 200))
        write(style_ref="assets/_gen/cook/still.png")
        sprite("new", "sink", "--type", "tile", "A steel sink")
        sprite("image", "sink")
        styled = posts("/assets/image/style")[0]
        self.assertEqual(styled["image_type"], "tile")
        self.assertIn("/up/", styled["style_image"])
        sprite("new", "hero", "--ref", "ref/hero.png", "A hero")
        sprite("image", "hero")
        edit = posts("/assets/image/edit")[0]
        self.assertTrue(edit["prompt"].startswith("The image shows the subject"))
        self.assertTrue("/up/" in edit["image"] and "/up/" in edit["reference_image"] and edit["image"] != edit["reference_image"])
        n = len(seen)
        sprite("new", "ghost", "--ref", "ref/hero.png", "--as-is", "A ghost")
        self.assertIn("300 × 200 px", sprite("image", "ghost"))
        self.assertEqual(len(seen), n, "그대로 쓰면 아무것도 부르지 않는다")
        sprite("new", "boom", "터진다")
        self.assertIn("400: 안 된다", sprite("image", "boom", ok=False))

        # 이름만 .png 인 WebP 가 오면 이 기기의 도구로 PNG 로 바꿔 놓는다. 도구가 없으면 받은 것을 두고 멈춘다
        webp.append(1)
        tools = os.path.join(root, "bin")
        os.makedirs(os.path.join(tools, "none"))
        open(os.path.join(tools, "ffmpeg"), "w").write(f"#!{sys.executable}\nimport struct, sys\n"
                                                       "open(sys.argv[-1], 'wb').write(b'\\x89PNG\\r\\n\\x1a\\n' + struct.pack('>I4sII', 13, b'IHDR', 640, 320))\n")
        os.chmod(os.path.join(tools, "ffmpeg"), 0o755)
        sprite("new", "owl", "An owl")
        self.assertIn("assets/_gen/owl/still.png — 640 × 320 px", sprite("image", "owl", env=dict(env, PATH=tools + os.pathsep + env["PATH"])))
        self.assertEqual(os.listdir(os.path.join(root, "assets/_gen/owl")).count("still.webp"), 0)
        sprite("new", "bat", "A bat")
        self.assertIn("still.webp: 받은 그림이 PNG 가 아닌데(webp) 바꿀 도구가 없다", sprite("image", "bat", ok=False, env=dict(env, PATH=os.path.join(tools, "none"))))
        self.assertEqual(sorted(n for n in os.listdir(os.path.join(root, "assets/_gen/bat")) if n.startswith("still")), ["still.webp"])
        del webp[:]

        # 현황판은 스프라이트도 놓는다
        run(BOARD, root)
        sheet = open(os.path.join(root, "docs/board/assets.html"), encoding="utf-8").read()
        self.assertIn("<span>cook</span>", sheet)

    def test_sound(self):
        seen = []

        class Fake(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append((self.path, self.headers["xi-api-key"], body))
                bad = "터진다" in body.get("text", "")
                self.send_response(422 if bad else 200)
                self.end_headers()
                self.wfile.write(json.dumps({"detail": {"message": "안 된다"}}).encode() if bad else f"소리{len(seen)}".encode() * 4)

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        root = tempfile.mkdtemp(prefix="kit-sound-")
        self.addCleanup(shutil.rmtree, root, True)
        cfg = json.load(open(os.path.join(KIT, "engines/godot/kit.config.json"), encoding="utf-8"))
        cfg["asset"]["env_file"] = os.path.join(root, "none.env")

        def write(**over):
            cfg["asset"]["sound"].update(over)
            json.dump(cfg, open(os.path.join(root, "kit.config.json"), "w"))

        write()
        env = dict(os.environ, ELEVENLABS_API_BASE=f"http://127.0.0.1:{server.server_port}", ELEVENLABS_API_KEY="k3")

        def sound(*args, ok=True, env=env):
            p = subprocess.run([sys.executable, SOUND, "--root", root, *args], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
            return p.stdout + p.stderr

        self.assertIn("ELEVENLABS_API_KEY 가 없다", sound("sfx", "coin", "x", ok=False, env={k: v for k, v in env.items() if k != "ELEVENLABS_API_KEY"}))
        self.assertIn("0.5~30초", sound("sfx", "coin", "--seconds", "40", "x", ok=False))
        self.assertIn("소문자", sound("sfx", "Coin", "x", ok=False))
        self.assertEqual(seen, [])

        self.assertIn("assets/sounds/coin.mp3", sound("sfx", "coin", "--seconds", "0.8", "A metal coin on stone, one bright ping."))
        path, key, body = seen[0]
        self.assertEqual((path, key), ("/sound-generation?output_format=mp3_44100_128", "k3"))
        self.assertEqual(body, {"text": "A metal coin on stone, one bright ping", "prompt_influence": 0.3, "loop": False, "duration_seconds": 0.8})
        first = open(os.path.join(root, "assets/sounds/coin.mp3"), "rb").read()

        os.makedirs(os.path.join(root, "docs"))
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("<!-- sound-style -->\n8-bit,\ndry.\n<!-- /sound-style -->\n<!-- music-style -->\nChiptune,\nslow.\n<!-- /music-style -->\n")
        self.assertIn("2번째", sound("again", "coin"))
        self.assertEqual(seen[1][2]["text"], "A metal coin on stone, one bright ping. 8-bit, dry.", "소리의 결이 설명 뒤에 붙는다")
        self.assertNotEqual(open(os.path.join(root, "assets/sounds/coin.mp3"), "rb").read(), first)

        self.assertIn("이어지는 소리", sound("sfx", "wind", "--loop", "--influence", "0.6", "Wind over a ridge"))
        self.assertEqual((seen[2][2]["loop"], seen[2][2]["prompt_influence"]), (True, 0.6))
        self.assertNotIn("duration_seconds", seen[2][2], "길이를 안 주면 알아서 정하게 둔다")

        self.assertIn("450자 안이어야", sound("sfx", "long", "가" * 445, ok=False), "결 문단이 붙은 뒤의 길이로 잰다")
        self.assertEqual(len(seen), 3)
        self.assertIn("3~600초", sound("music", "theme", "--seconds", "1", "x", ok=False))
        sound("music", "theme", "--seconds", "45", "Calm exploration theme")
        self.assertEqual(seen[3][0].split("?")[0], "/music")
        self.assertEqual(seen[3][2], {"prompt": "Calm exploration theme. Chiptune, slow.", "music_length_ms": 45000,  # 효과음의 결은 음악에 붙지 않는다
                                      "model_id": "music_v1", "force_instrumental": True})

        self.assertIn("422: 안 된다", sound("sfx", "boom", "터진다", ok=False))
        self.assertFalse(os.path.exists(os.path.join(root, "assets/sounds/boom.mp3")))
        out = sound("status")
        self.assertEqual([line.split()[0] for line in out.strip().split("\n")], ["coin", "theme", "wind"])

        write(format="pcm_22050")
        sound("sfx", "step", "A footstep on gravel")
        with __import__("wave").open(os.path.join(root, "assets/sounds/step.wav")) as w:
            self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (22050, 1, 2))
        write(dir="")
        self.assertIn("asset.sound.dir", sound("status", ok=False))

    def test_clip(self):
        """찍은 듯한 영상(Higgsfield) — 가짜 서버로: 그림을 올리고, 보내고, 기다리고, 받는다. 키는 Higgsfield 에만 붙는다."""
        seen, polls = [], []

        class Fake(http.server.BaseHTTPRequestHandler):
            def reply(self, code, body=b"", ctype="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.end_headers()
                self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

            def read(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_POST(self):
                body, here = json.loads(self.read()), f"http://127.0.0.1:{self.server.server_port}"
                seen.append(("POST", self.path, self.headers.get("Authorization"), self.headers.get("Idempotency-Key"), body))
                if self.path == "/files/generate-upload-url":
                    return self.reply(200, {"public_url": f"{here}/cdn/in.png", "upload_url": f"{here}/store/in.png",
                                            "upload_headers": {"Content-Type": body["content_type"], "x-amz-tagging": "retention=temporary"}})
                if "터진다" in body.get("prompt", ""):
                    return self.reply(422, {"detail": "안 된다"})
                rid = "bad" if "야한" in body.get("prompt", "") else f"r{len(seen)}"
                self.reply(200, {"status": "queued", "request_id": rid, "status_url": f"{here}/requests/{rid}/status"})

            def do_PUT(self):
                seen.append(("PUT", self.path, self.headers.get("Authorization"), self.headers.get("x-amz-tagging"), self.read()))
                self.reply(200)

            def do_GET(self):
                if self.path.startswith("/cdn/"):
                    seen.append(("GET", self.path, self.headers.get("Authorization"), None, None))
                    return self.reply(200, f"영상 {self.path}".encode() * 9, "video/mp4")
                rid = self.path.split("/")[2]
                polls.append(rid)
                if rid == "bad":
                    return self.reply(200, {"status": "nsfw", "request_id": rid})
                self.reply(200, {"status": "in_progress", "request_id": rid} if polls.count(rid) < 2 else
                           {"status": "completed", "request_id": rid, "video": {"url": f"http://127.0.0.1:{self.server.server_port}/cdn/{rid}.mp4"}})

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        root = tempfile.mkdtemp(prefix="kit-clip-")
        self.addCleanup(shutil.rmtree, root, True)
        ffmpeg = os.path.join(root, "ffmpeg")
        open(ffmpeg, "w").write('#!/bin/sh\nfor a; do last=$a; done\necho "$@" > "$last"\n')
        os.chmod(ffmpeg, 0o755)
        cfg = json.load(open(os.path.join(KIT, "engines/godot/kit.config.json"), encoding="utf-8"))
        cfg["video"].update(env_file=os.path.join(root, "none.env"), ffmpeg=ffmpeg)

        def write(**clip):
            cfg["video"]["clip"] = dict(cfg["video"].get("clip", {}), **clip)
            json.dump(cfg, open(os.path.join(root, "kit.config.json"), "w"))

        write()
        env = dict(os.environ, HIGGSFIELD_API_BASE=f"http://127.0.0.1:{server.server_port}", VIDEO_POLL_SEC="0.01",
                   HF_API_KEY_ID="kid", HF_API_KEY_SECRET="sec")

        def clip(*args, ok=True, env=env):
            p = subprocess.run([sys.executable, CLIP, "--root", root, *args], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
            return p.stdout + p.stderr

        rec = lambda name: json.load(open(os.path.join(root, "video", name, "clip.json"), encoding="utf-8"))
        nokey = {k: v for k, v in env.items() if not k.startswith("HF_")}
        out = clip("check", ok=False, env=nokey)
        self.assertIn("HF_API_KEY_ID 가 없다", out)
        self.assertIn("HF_API_KEY_SECRET 가 없다", out)
        out = clip("check")
        self.assertIn("모델: higgsfield/cinema-studio/4.0", out)
        self.assertIn("돌릴 수 있다", out)
        self.assertIn("클립이 없다", clip("status"))

        self.assertIn("그림이 없다", clip("new", "gate", "--for", "game", "--image", "ref.png", "x", ok=False))
        open(os.path.join(root, "ref.png"), "wb").write(b"\x89PNG pic")
        os.makedirs(os.path.join(root, "docs"))
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("<!-- footage-style -->\nHand-painted,\nmuted.\n<!-- /footage-style -->\n")
        out = clip("new", "gate", "--for", "game", "--seconds", "6", "--image", "ref.png", "A stone gate opens slowly.")
        self.assertIn("승인을 기다린다 — 설명 · 기준 그림", out)
        self.assertIn("보낼 설명: A stone gate opens slowly. Hand-painted, muted.", out, "화면의 결이 설명 뒤에 붙는다")
        self.assertIn("승인이 없다", clip("make", "gate", ok=False))
        self.assertEqual(seen, [], "승인 전에는 아무것도 나가지 않는다")
        clip("approve", "gate")
        out = clip("make", "gate")
        self.assertIn("video/gate/clip.mp4", out)
        ask, put, send, got = seen
        self.assertEqual(ask[:3] + ask[4:], ("POST", "/files/generate-upload-url", "Key kid:sec", {"content_type": "image/png"}))
        self.assertEqual(put[:4], ("PUT", "/store/in.png", None, "retention=temporary"), "저장소에는 키를 보내지 않고, 받은 헤더를 그대로 붙인다")
        self.assertEqual(put[4], b"\x89PNG pic")
        self.assertEqual(send[:3], ("POST", "/higgsfield/cinema-studio/4.0", "Key kid:sec"))
        self.assertEqual(send[3], rec("gate")["request"]["key"])
        self.assertEqual(send[4], {"resolution": "720p", "prompt": "A stone gate opens slowly. Hand-painted, muted.", "duration": 6,
                                   "aspect_ratio": "16:9", "image_urls": [f"http://127.0.0.1:{server.server_port}/cdn/in.png"]})
        self.assertEqual(got[:3], ("GET", "/cdn/r3.mp4", None))
        self.assertEqual(polls, ["r3", "r3"])
        self.assertIn("사람이 볼 차례", clip("status"))
        self.assertIn("이미 만들었다", clip("make", "gate", ok=False))
        self.assertEqual(len(seen), 4, "같은 것을 두 번 만들지 않는다")

        # 사람이 본 뒤에 놓는다 — 게임 안의 것은 엔진이 읽는 형식으로
        self.assertIn("assets/video/gate.ogv", clip("place", "gate"))
        self.assertIn("libtheora", open(os.path.join(root, "assets/video/gate.ogv")).read())
        self.assertIn("놓았다 — assets/video/gate.ogv", clip("status"))

        # 보내고 끊긴 것은 이어서 기다린다 — 다시 보내지 않는다
        made = rec("gate")
        made["request"]["mark"] = made["made"]["mark"]
        del made["made"]
        json.dump(made, open(os.path.join(root, "video/gate/clip.json"), "w"))
        self.assertIn("만드는 중", clip("status"))
        clip("make", "gate")
        self.assertEqual([s[:2] for s in seen[4:]], [("GET", "/cdn/r3.mp4")])
        clip("make", "gate", "--again")
        self.assertEqual(seen[-2][1], "/higgsfield/cinema-studio/4.0")
        self.assertNotEqual(seen[-2][3], send[3], "한 번 더 뽑을 때는 새 요청이다")

        # 설명이 바뀌면 승인도 다시
        clip("new", "gate", "--for", "page", "--size", "portrait", "A stone gate closes.")
        self.assertIn("승인이 없다", clip("make", "gate", ok=False))
        self.assertIn("지금 설명으로 만든 영상이 없다", clip("place", "gate", ok=False))
        clip("approve", "gate")
        clip("make", "gate")
        self.assertEqual(seen[-2][4], {"resolution": "720p", "prompt": "A stone gate closes. Hand-painted, muted.", "duration": 5, "aspect_ratio": "9:16"})
        self.assertIn("docs/video/gate.mp4", clip("place", "gate"))

        # 모델마다 입력의 이름이 다르다 — 설정이 정한다
        write(model="kling-video/v2.5-turbo/pro/image-to-video", params={"cfg_scale": 0.5},
              fields={"aspect": "", "images": "", "image": "image_url"})
        clip("new", "walk", "--for", "page", "--image", "ref.png", "She walks.")
        clip("approve", "walk")
        clip("make", "walk")
        self.assertEqual(seen[-2][1], "/kling-video/v2.5-turbo/pro/image-to-video")
        self.assertEqual(seen[-2][4], {"cfg_scale": 0.5, "prompt": "She walks. Hand-painted, muted.", "duration": 5,
                                       "image_url": f"http://127.0.0.1:{server.server_port}/cdn/in.png"})

        clip("new", "bad", "--for", "page", "야한 것")
        clip("approve", "bad")
        self.assertIn("내용 검사에 걸렸다", clip("make", "bad", ok=False))
        clip("new", "boom", "--for", "page", "터진다")
        clip("approve", "boom")
        self.assertIn("422: 안 된다", clip("make", "boom", ok=False))
        self.assertFalse(os.path.exists(os.path.join(root, "video/boom/clip.mp4")))

    def test_board(self):
        """GDD 표와 사이클 문서가 판 한 장이 된다. 훅은 판이 있고 원천이 더 새로울 때만 다시 그린다."""
        root = tempfile.mkdtemp(prefix="kit-board-")
        self.addCleanup(shutil.rmtree, root, True)
        open(os.path.join(root, "kit.config.json"), "w").write("{}")
        os.makedirs(os.path.join(root, "docs/cycle"))
        gdd = os.path.join(root, "docs/GDD.md")
        open(gdd, "w", encoding="utf-8").write(GDD.replace("# 게임", "# 게임 — 기획서").replace("## 4. 규칙", "## 4. 규칙 <b>")
                                               .replace("| BAL.PLAYER.HP | 100 | 4 | — | 미구현 |", "| BAL.PLAYER.HP | 100 | 4 | a.gd:HP | 동기 |"))
        out = os.path.join(root, "docs/board/index.html")
        self.assertEqual(run(BOARD, root, "--if-stale").stdout, "")
        self.assertFalse(os.path.exists(out), "한 번도 그리지 않은 판은 훅이 만들지 않는다")
        self.assertIn("docs/board/index.html — GDD 동기 1/5 · 불일치 0 · 사이클 0개", run(BOARD, root).stdout)

        run(CYCLE, root, "new", "coins", "동전을 <줍게> 하자")
        doc = os.path.join(root, "docs/cycle/01-coins.md")
        run(CYCLE, root, "ask", "기획", "동전의 값 (지금 — 5) — ① 5 ② 7 · 권함: ②")
        run(CYCLE, root, "ask", "디자인", "소리 — ① 있음 ② 없음 · 권함: ①")
        run(CYCLE, root, "decide", "D1", "7 로 가자 → 아니 5")
        text = open(doc, encoding="utf-8").read()
        text = text.replace("## 작업\n", "## 작업\n\n### [x] T1. 동전을 줍는다\n- **GDD**: BAL.COIN.VALUE · RULE.COIN.PICKUP(새)\n\n"
                            "### [!] T2. 소리를 낸다\n- **막힘**: 소리가 없다\n").replace("## 순서\n", "## 순서\n- 1차 (끝): T1\n- 2차: T2 — T1 뒤\n")
        open(doc, "w", encoding="utf-8").write(text)
        before = os.path.getmtime(out)
        os.utime(out, (before - 10, before - 10))
        self.assertEqual(run(BOARD, root, "--if-stale").stdout, "")
        chart = open(out, encoding="utf-8").read()
        self.assertGreater(os.path.getmtime(out), before - 10, "원천이 더 새로우면 다시 그린다")
        self.assertIn("<title>게임 항해도</title>", chart)
        self.assertIn('href="stage-1.html"', chart, "첫 화면의 카드는 단계의 쪽으로 간다")
        self.assertIn('href="assets.html">에셋 시트 →</a>', open(os.path.join(root, "docs/board/stage-1.html"), encoding="utf-8").read(), "단계의 쪽에서 에셋 시트로 간다")
        self.assertIn("<h2>규칙 &lt;b&gt;</h2>", chart, "flow 가 없으면 GDD 절마다 단계 하나")
        self.assertIn("<em>1/5</em>", chart, "기능 칸은 GDD 표의 상태를 센다")
        stage = open(os.path.join(root, "docs/board/stage-1.html"), encoding="utf-8").read()
        self.assertIn("<code>BAL.PLAYER.HP</code>", stage)
        self.assertIn("사이클 01 — coins", stage, "그 단계를 건드린 사이클이 검증 칸에 선다")
        self.assertIn("<b>T1</b> 동전을 줍는다", stage, "그 단계를 건드린 작업")
        self.assertIn("D2 소리", chart, "답 없는 결정은 못 정한 것으로 선다")
        self.assertIn("동전을 줍는다", stage)
        self.assertNotIn("log.html", chart + stage)
        self.assertIn("답 없는 결정 1", run(BOARD, root).stdout)
        self.assertNotIn("미분류", run(BOARD, root).stdout, "어느 단계에도 안 든 것이 없으면 말하지 않는다")
        self.assertIn("<b>0</b>", chart)
        os.makedirs(os.path.join(root, "assets/sounds"))
        open(os.path.join(root, "assets/sounds/zzz_orphan.mp3"), "w").write("x")
        self.assertIn("미분류 1 (에셋 1 — 완성 % 밖)", run(BOARD, root).stdout, "완성 % 에 안 드는 것은 그 수가 같이 보인다")
        chart = open(out, encoding="utf-8").read()
        self.assertIn('<div class="tile warn"><span class="lab">미분류 · % 밖</span><b>1</b></div>', chart)
        self.assertIn("이 가운데 미분류 1 (에셋 1) 은 완성 % 밖", chart)
        self.assertIn("<b>미분류 1</b><span>에셋 1</span>", chart)
        os.remove(os.path.join(root, "assets/sounds/zzz_orphan.mp3"))
        run(BOARD, root)
        stamp = os.path.getmtime(out)
        run(BOARD, root, "--if-stale")
        self.assertEqual(os.path.getmtime(out), stamp, "바뀐 것이 없으면 다시 그리지 않는다")

        empty = tempfile.mkdtemp(prefix="kit-none-")
        self.addCleanup(shutil.rmtree, empty, True)
        p = subprocess.run([sys.executable, BOARD, "--if-stale"], cwd=empty, capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""), "게임 저장소 밖에서는 아무 일도 없다")

    def test_cycle(self):
        root = tempfile.mkdtemp(prefix="kit-cycle-")
        self.addCleanup(shutil.rmtree, root, True)
        open(os.path.join(root, "kit.config.json"), "w").write("{}")
        self.assertIn("문서가 없다", run(CYCLE, root, "next", ok=False).stderr)
        self.assertIn("docs/cycle/01-dash.md", run(CYCLE, root, "new", "dash", "대시를 넣자").stdout)
        out = run(CYCLE, root, "new", "shop", "상점").stdout
        self.assertIn("docs/cycle/02-shop.md", out)
        self.assertIn("앞 사이클이 아직 목표 단계다: docs/cycle/01-dash.md", out, "플레이까지 못 간 사이클은 닫지 않는다")
        doc = os.path.join(root, "docs/cycle/02-shop.md")
        text = lambda: open(doc, encoding="utf-8").read()
        self.assertIn("## 목표\n상점\n", text())

        self.assertEqual(run(CYCLE, root, "ask", "기획", "값을 어떻게 — ① 고정 ② 변동 · 권함: ①").stdout.strip(), "D1")
        self.assertEqual(run(CYCLE, root, "ask", "디자인", "간판 색 — ① 빨강 ② 파랑").stdout.strip(), "D2")
        self.assertIn("- [ ] D2. 간판 색 — ① 빨강 ② 파랑 (디자인)\n\n## 기획", text())
        filled = text().replace("## 작업\n", """## 작업

### [ ] T1. 상점 화면을 만든다
- **고칠 곳**: shop.gd

### [ ] T2. 값을 붙인다
- **고칠 곳**: balance.gd — D1 의 답대로
- **대기**: D1

### [ ] T3. 간판을 단다
- **고칠 곳**: sign.gd
""").replace("## 순서\n", "## 순서\n- 1차: T1, T2 — 서로 다른 파일\n- 2차: T3 — T1 이 만든 화면에 단다\n")
        open(doc, "w", encoding="utf-8").write(filled)

        out = run(CYCLE, root, "next").stdout
        self.assertIn("답 없는 결정 2", out)
        self.assertIn("다음 차수: 1차", out)
        self.assertIn("T2. 값을 붙인다 — 대기 D1", out)
        self.assertNotIn("T3", out)
        run(CYCLE, root, "decide", "D1", "고정으로 가자")
        self.assertRegex(text(), r"- \[x\] D1\. 값을 어떻게 — ① 고정 ② 변동 · 권함: ① \(기획\) → 고정으로 가자 \(\d{4}-\d\d-\d\d\)")
        self.assertNotIn("대기 D1", run(CYCLE, root, "next").stdout)

        out = run(CYCLE, root, "task", "T2").stdout
        self.assertIn("### [ ] T2. 값을 붙인다", out)
        self.assertIn("걸린 결정:\n- [x] D1.", out)
        self.assertNotIn("T1", out, "다른 작업은 꺼내지 않는다")
        self.assertNotIn("D2", out, "걸리지 않은 결정은 꺼내지 않는다")

        run(CYCLE, root, "mark", "T1,T2", "done")
        run(CYCLE, root, "mark", "T3", "blocked", "sign.gd 가 없다")
        self.assertIn("### [x] T2. 값을 붙인다", text())
        self.assertIn("### [!] T3. 간판을 단다\n- **고칠 곳**: sign.gd\n- **막힘**: sign.gd 가 없다\n\n## 순서", text())
        self.assertIn("막힌 작업: T3", run(CYCLE, root, "next").stdout)
        run(CYCLE, root, "mark", "T3", "done", "sign.tscn 에 달았다")
        self.assertIn("남은 작업이 없다", run(CYCLE, root, "next").stdout)
        run(CYCLE, root, "stage", "플레이")
        out = run(CYCLE, root, "status").stdout.strip().split("\n")
        self.assertEqual(len(out), 2)
        self.assertIn("02-shop.md — 단계: 플레이 · 작업 [x] 3 · [ ] 0 · [!] 0 · 답 없는 결정 1", out[1])
        self.assertIn("단계: 목표", run(CYCLE, root, "next", "--doc", "docs/cycle/01-dash.md").stdout)
        self.assertIn("그런 작업이 없다", run(CYCLE, root, "task", "T9", ok=False).stderr)

        # 배운 것이 키트로 돌아가는 길
        open(os.path.join(root, "kit.config.json"), "w").write('{"engine": "godot"}')
        run(CYCLE, root, "lesson", "헤드리스는 셰이더를  컴파일하지 않는다 → 창으로 한 번 돌린다")
        run(CYCLE, root, "lesson", "둘째 줄")
        fb = lambda *a, ok=True: subprocess.run([sys.executable, FEEDBACK, *a], capture_output=True, text=True)
        out = fb("list", root, os.path.join(root, "없는곳")).stdout
        self.assertRegex(out, r"1\. \(godot · 사이클 02 · \d{4}-\d\d-\d\d\) 헤드리스는 셰이더를 컴파일하지 않는다 → 창으로 한 번 돌린다\n  2\. ")
        self.assertIn("kit-feedback.md 가 없다", out)
        self.assertIn("1줄: [x]", fb("done", root, "1", "0.7.2").stdout)
        out = fb("list", root).stdout
        self.assertIn("1줄", out)
        self.assertIn("1. (godot · 사이클 02", out)
        self.assertIn("둘째 줄", out)
        self.assertIn("창으로 한 번 돌린다 — 키트 0.7.2", open(os.path.join(root, "docs/kit-feedback.md"), encoding="utf-8").read())
        self.assertNotEqual(fb("done", root, "5", "x").returncode, 0)

        # 닫는 단계는 없다 — 플레이에 서 있던 사이클은 다음 사이클이 생길 때 끝이 되고, 남은 것 · 미뤄 둔 것을 알린다
        run(CYCLE, root, "later", "간판에  불을 켜는 건 다음에")
        self.assertIn("## 플레이\n- 다음에: 간판에 불을 켜는 건 다음에\n", text())
        self.assertNotIn("## 회고", text())
        out = run(CYCLE, root, "new", "auto", "알아서").stdout
        self.assertIn("닫았다: docs/cycle/02-shop.md", out)
        self.assertIn("앞 사이클에 남은 것: 답 없는 결정 1", out)
        self.assertIn("미뤄 둔 것: 간판에 불을 켜는 건 다음에", out)
        self.assertIn("단계: 끝", text())

        # 자동 모드 — 대신 정한 것은 [~]. 걸린 작업은 돌고, 사용자가 받아들이거나 뒤집을 때까지 확인 전이다
        auto = os.path.join(root, "docs/cycle/03-auto.md")
        atext = lambda: open(auto, encoding="utf-8").read()
        for q in ("문 — ① 연다 ② 닫는다 · 권함: ①", "색 — ① 빨강 ② 파랑 · 권함: ①", "값 — ① 싸게 ② 비싸게", "길 — ① 짧게 ② 길게 · 권함: ②"):
            run(CYCLE, root, "ask", "기획", q)
        planned = atext().replace("## 작업\n", "## 작업\n\n### [ ] T1. 문\n- **대기**: D1\n\n### [ ] T2. 값\n- **대기**: D3\n")
        open(auto, "w", encoding="utf-8").write(planned.replace("## 순서\n", "## 순서\n- 1차: T1, T2\n"))
        self.assertIn("대신 정했다", run(CYCLE, root, "decide", "D1", "②", "--proxy", "V3, V5").stdout)
        run(CYCLE, root, "decide", "D2", "①", "--proxy", "권함")
        run(CYCLE, root, "decide", "D4", "②", "--proxy", "V7")
        self.assertRegex(atext(), r"- \[~\] D1\. 문 — ① 연다 ② 닫는다 · 권함: ① \(기획\) → ② · 대리 V3, V5 \(\d{4}-\d\d-\d\d\)")
        out = run(CYCLE, root, "next").stdout
        self.assertIn("답 없는 결정 1 · 대리 결정 3 (확인 전)", out)
        self.assertIn("대리 결정 (확인 전): D1.", out)
        self.assertIn("답 없는 결정: D3.", out)
        self.assertIn("  T1. 문\n", out, "대신 정한 결정에 걸린 작업은 돈다")
        self.assertIn("T2. 값 — 대기 D3", out, "아무도 정하지 않은 결정에 걸린 작업은 서 있다")
        self.assertIn("확인을 기다리는 대리 결정이 아니다", run(CYCLE, root, "confirm", "D3", ok=False).stderr)
        self.assertIn("받아들였다: D1", run(CYCLE, root, "confirm", "D1").stdout)
        self.assertRegex(atext(), r"- \[x\] D1\. 문 — ① 연다 ② 닫는다 · 권함: ① \(기획\) → ② — 대리\(V3, V5\)를 받아들임 \(\d{4}")
        run(CYCLE, root, "decide", "D2", "파랑으로 하자")
        self.assertRegex(atext(), r"- \[x\] D2\. 색 — ① 빨강 ② 파랑 · 권함: ① \(기획\) → 파랑으로 하자 \(\d{4}")
        self.assertIn("사용자가 이미 답했다", run(CYCLE, root, "decide", "D2", "①", "--proxy", "V1", ok=False).stderr)
        self.assertIn("받아들였다: D4", run(CYCLE, root, "confirm", "all").stdout)
        self.assertIn("답 없는 결정 1\n", run(CYCLE, root, "status").stdout.split("03-auto")[1] + "\n")
        out = subprocess.run([sys.executable, VOICE, "--root", root, "collect"], capture_output=True, text=True,
                             env=dict(os.environ, GAMEDEV_KIT_VOICE=os.path.join(root, "voice-home"))).stdout
        self.assertIn("03 D1 [받음]", out, "받아들인 대리 결정은 스스로 고른 것과 가려 센다")
        self.assertIn("대리를 받음 2", out)
        run(CYCLE, root, "decide", "D3", "①")

    def test_voice(self):
        top = tempfile.mkdtemp(prefix="kit-voice-")
        self.addCleanup(shutil.rmtree, top, True)
        root, other, home = (os.path.join(top, n) for n in ("first game", "second", "home"))
        for game, cfg in ((root, "{}"), (other, '{"voice": {"name": "둘째"}}')):
            os.makedirs(game)
            open(os.path.join(game, "kit.config.json"), "w", encoding="utf-8").write(cfg)
        os.environ["GAMEDEV_KIT_VOICE"] = home  # 보이스는 게임 밖에 산다
        self.addCleanup(os.environ.pop, "GAMEDEV_KIT_VOICE")
        self.assertIn("보이스가 아직 없다", run(VOICE, root, "path", ok=False).stderr)
        self.assertIn("답이 난 결정이 없다", run(VOICE, root, "collect").stdout)
        run(CYCLE, root, "new", "dash", "대시를\n넣자")
        run(CYCLE, root, "ask", "기획", "대시 뒤 — ① 무적 ② 그대로 · 권함: ①")
        run(CYCLE, root, "ask", "디자인", "잔상 — ① 있다 ② 없다 · 권함: ①")
        run(CYCLE, root, "ask", "계획", "범위 — ① 전부 ② 반만 · 권함: ②")
        run(CYCLE, root, "ask", "계획", "순서 — ① 화면 먼저 ② 값 먼저")
        log = lambda: open(os.path.join(home, "log.md"), encoding="utf-8").read()

        # 근거가 될 원칙이 보이스에 있어야 예측한다
        self.assertIn("근거 원칙이", run(VOICE, root, "predict", "D1", "②", "V1", ok=False).stderr)
        os.makedirs(home)
        open(os.path.join(home, "VOICE.md"), "w", encoding="utf-8").write(
            "# 보이스\n\n갱신: 2000-01-01 · 결정 2개 · 게임 1개에서\n\n## 원칙\n- V1. 봐주는 규칙은 넣지 않는다\n- V2. 작게 자른다\n")
        self.assertEqual(run(VOICE, root, "path").stdout.strip(), os.path.join(home, "VOICE.md"))
        self.assertIn("first-game 01 D1 (기획) → ② · V1", run(VOICE, root, "predict", "D1", "2", "V1").stdout)
        run(VOICE, root, "predict", "D2", "②", "V1,V2")
        run(VOICE, root, "predict", "D3", "②", "V2")
        self.assertIn("질문에 없는 선택지", run(VOICE, root, "predict", "D4", "③", "V1", ok=False).stderr)
        self.assertIn("→ 모름", run(VOICE, root, "predict", "D4", "-").stdout)
        self.assertIn("이미 예측을 적었다", run(VOICE, root, "predict", "D1", "①", "V1", ok=False).stderr)
        self.assertIn("채점할 예측이 없다", run(VOICE, root, "score").stdout)

        run(CYCLE, root, "decide", "D1", "②. 봐주지 말자")
        run(CYCLE, root, "decide", "D2", "1번으로")
        run(CYCLE, root, "decide", "D3", "일단 반만 하자")
        run(CYCLE, root, "decide", "D4", "① 화면부터")
        self.assertIn("이미 답이 났다", run(VOICE, root, "predict", "D4", "①", "V1", ok=False).stderr)
        out = run(VOICE, root, "score").stdout
        self.assertIn("01 D1: 맞음 — 예측 ② (V1)", out)
        self.assertIn("01 D2: 빗나감 — 예측 ② (V1, V2) · 답: 1번으로", out)
        self.assertIn("가릴 수 없다: 01 D3 예측 ② · 답: 일단 반만 하자", out)
        self.assertIn("채점할 예측이 없다", run(VOICE, root, "score", "01", "D1", "hit", ok=False).stderr)
        self.assertIn("01 D3: 맞음", run(VOICE, root, "score", "01", "D3", "hit").stdout)
        self.assertRegex(log(), r"- \[o\] first-game 01 D1 \(기획\) → ② · V1 \(\d{4}-\d\d-\d\d\)\n- \[x\] first-game 01 D2 .*\n"
                                r"- \[o\] first-game 01 D3 .*\n- \[-\] first-game 01 D4 \(계획\) → 모름")
        out = run(VOICE, root, "stats").stdout
        self.assertIn("적중 2/3 (66%) · 모름 1 · 채점 전 0 · 예측 4", out)
        self.assertIn("계획: 1/1 (100%) · 모름 1", out)
        self.assertIn("V1: 1/2 (50%)", out)
        self.assertIn("V2: 1/2 (50%)", out)
        self.assertNotIn("first-game:", out, "게임이 하나면 게임별 줄은 없다")

        out = run(VOICE, root, "collect").stdout
        self.assertIn("게임: first-game\n\n사이클 01 — dash\n목표: 대시를 넣자\n", out)
        self.assertIn("first-game 01 D1 [갈림] (기획) 대시 뒤 — ① 무적 ② 그대로 · 권함: ① → ②. 봐주지 말자 (", out)
        self.assertIn("01 D2 [같음]", out)
        self.assertIn("01 D3 [?]", out)
        self.assertIn("결정 4 · 권함과 갈림 1 · 같음 1 · 읽어서 가릴 것 2", out)

        # 보이스에 읽힌 결정은 다음 갱신에서 다시 나오지 않는다
        self.assertIn("결정 4", run(VOICE, root, "collect", "new").stdout)
        self.assertIn("4개를 읽힌 것으로 적었다", run(VOICE, root, "collect", "done").stdout)
        self.assertIn("답이 난 결정이 없다 (아직 읽히지 않은 것 가운데)", run(VOICE, root, "collect", "new").stdout)
        run(CYCLE, root, "ask", "기획", "문 — ① 연다 ② 닫는다 · 권함: ①")
        run(CYCLE, root, "decide", "D5", "①")
        out = run(VOICE, root, "collect", "new").stdout
        self.assertIn("01 D5 [같음]", out)
        self.assertIn("결정 1 ·", out)
        self.assertIn("결정 5 ·", run(VOICE, root, "collect").stdout)

        # 답을 바꾼 결정 — 앞의 답과 뒤의 답이 같이 나오고, 읽힌 뒤에도 다시 나온다. 고른 번호는 마지막 답에서 가린다
        run(VOICE, root, "collect", "done")
        self.assertIn("답이 난 결정이 없다", run(VOICE, root, "collect", "new").stdout)
        run(CYCLE, root, "decide", "D5", "해 보니 좁다. ② 로 바꾸자")
        out = run(VOICE, root, "collect", "new").stdout
        self.assertRegex(out, r"01 D5 \[바꿈\] \(기획\) 문 — ① 연다 ② 닫는다 · 권함: ① → ① \(\d{4}-\d\d-\d\d\) → 해 보니 좁다. ② 로 바꾸자 \(")
        self.assertIn("결정 1 · 권함과 갈림 0 · 같음 0 · 읽어서 가릴 것 0 · 답을 바꿈 1", out)
        run(VOICE, root, "collect", "done")
        self.assertIn("first-game 01 D5 #2\n", open(os.path.join(home, "seen.txt"), encoding="utf-8").read())
        self.assertIn("답이 난 결정이 없다", run(VOICE, root, "collect", "new").stdout)
        run(CYCLE, root, "ask", "기획", "창 — ① 연다 ② 닫는다 · 권함: ①")
        run(VOICE, root, "predict", "D6", "②", "V1")
        run(CYCLE, root, "decide", "D6", "①")
        run(CYCLE, root, "decide", "D6", "아니 ②")
        self.assertIn("01 D6: 맞음", run(VOICE, root, "score").stdout, "바꾼 답으로 채점한다")

        # 다른 게임의 결정이 같은 보이스에 쌓인다 — 줄마다 어느 게임의 것인지 적힌다
        run(CYCLE, other, "new", "shop", "상점")
        run(CYCLE, other, "ask", "계획", "범위 — ① 전부 ② 반만 · 권함: ①")
        self.assertIn("둘째 01 D1 (계획) → ② · V2", run(VOICE, other, "predict", "D1", "②", "V2").stdout)
        run(CYCLE, other, "decide", "D1", "②")
        self.assertIn("채점할 예측이 없다", run(VOICE, root, "score").stdout, "다른 게임의 예측은 채점하지 않는다")
        self.assertIn("01 D1: 맞음", run(VOICE, other, "score").stdout)
        self.assertIn("결정 1 · 권함과 갈림 1", run(VOICE, other, "collect", "new").stdout)
        out = run(VOICE, other, "stats").stdout
        self.assertIn("적중 4/5 (80%) · 모름 1 · 채점 전 0 · 예측 6", out)
        self.assertIn("first-game: 3/4 (75%) · 모름 1", out)
        self.assertIn("둘째: 1/1 (100%) · 모름 0", out)
        self.assertIn("V2: 2/3 (66%)", out)
        self.assertFalse(os.path.exists(os.path.join(root, "docs/VOICE.md")), "게임 저장소에는 보이스를 두지 않는다")

    def test_voice_sync(self):
        """보이스 폴더는 비공개 저장소의 클론이다 — 기기 둘이 같은 저장소로 맞춘다. 로그인 없이 읽어 보는 git 만 가짜다."""
        top = tempfile.mkdtemp(prefix="kit-voice-sync-")
        self.addCleanup(shutil.rmtree, top, True)
        remote, a, b, bin_dir = (os.path.join(top, n) for n in ("remote.git", "a", "b", "bin"))
        subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
        os.makedirs(bin_dir)
        anon = os.path.join(bin_dir, "anon-git")  # 로그인 없이 읽히면(0) 공개다
        open(anon, "w").write('#!/bin/sh\n[ "$FAKE_PUBLIC" = 1 ]\n')
        os.chmod(anon, 0o755)
        base = dict(os.environ, VOICE_ANON_GIT=anon, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")

        def voice(home, *args, public=False, ok=True):
            p = subprocess.run([sys.executable, VOICE, *args], capture_output=True, text=True,
                               env=dict(base, GAMEDEV_KIT_VOICE=home, FAKE_PUBLIC="1" if public else "0"))
            self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
            return p.stdout + p.stderr

        put = lambda home, text: open(os.path.join(home, "VOICE.md"), "w", encoding="utf-8").write(text)
        self.assertIn("저장소가 아니다", voice(a, "sync"))
        self.assertIn("공개 저장소다", voice(a, "setup", remote, public=True, ok=False))
        self.assertFalse(os.path.exists(a))

        # 보이스가 이미 있는 기기 — 그 폴더가 저장소가 된다
        os.makedirs(a)
        put(a, "# 보이스\n- V1. 하나\n")
        self.assertIn("저장소로 만들었다", voice(a, "setup", remote))
        out = voice(a, "sync", "voice: 첫 판")
        self.assertIn("커밋했다", out)
        self.assertIn("올리지 않은 커밋 1 — 사용자에게 묻고", out)
        self.assertIn("확인된 저장소가 아니다", voice(a, "autopush", "on", public=True, ok=False))
        self.assertIn("묻지 않고 올린다", voice(a, "autopush", "on"))
        self.assertIn("올렸다 — 커밋 1", voice(a, "sync"))
        self.assertIn("저장소와 같다", voice(a, "sync"))

        # 다른 기기 — 받기만 하면 같은 보이스다. 허락은 기기마다 따로다
        self.assertIn("받지 못했다", voice(b, "setup", os.path.join(top, "없는곳.git"), ok=False))
        self.assertFalse(os.path.exists(b))
        self.assertIn("받았다", voice(b, "setup", remote))
        self.assertIn("V1. 하나", open(os.path.join(b, "VOICE.md"), encoding="utf-8").read())
        open(os.path.join(b, "log.md"), "w", encoding="utf-8").write("- [o] 둘째 01 D1 (계획) → ② · V1\n")
        self.assertIn("올리지 않은 커밋 1", voice(b, "sync"))
        self.assertIn("올렸다 — 커밋 1", voice(b, "sync", "--push"))
        put(a, "# 보이스\n- V1. 하나\n- V2. 둘\n")
        out = voice(a, "sync")
        self.assertIn("받았다 — 커밋 1", out)
        self.assertIn("올렸다 — 커밋 1", out)
        self.assertTrue(os.path.exists(os.path.join(a, "log.md")))

        # 같은 줄을 두 기기가 다르게 고쳤다 — 멈추고 사람에게 넘긴다. 이 기기의 것은 그대로다
        put(b, "# 보이스\n- V1. 다르게\n")
        self.assertIn("손으로 합친다", voice(b, "sync", ok=False))
        self.assertIn("V1. 다르게", open(os.path.join(b, "VOICE.md"), encoding="utf-8").read())

        # 저장소에도 이 기기에도 보이스가 있으면 고르지 않는다
        c = os.path.join(top, "c")
        os.makedirs(c)
        put(c, "# 보이스\n")
        self.assertIn("어느 쪽을 남길지", voice(c, "setup", remote, ok=False))
        self.assertFalse(os.path.exists(os.path.join(c, ".git")))

        # SSH 주소(~/.ssh/config 의 별칭)는 키가 로그인해 버린다 — 로그인 없이는 같은 저장소의 https 주소로 묻는다. 가짜 ssh 가 위의 저장소를 내준다
        ssh, asked = os.path.join(bin_dir, "ssh"), os.path.join(top, "asked.txt")
        open(ssh, "w").write(f'#!/bin/sh\nexec git upload-pack "{remote}"\n')
        os.chmod(ssh, 0o755)
        open(anon, "w").write(f'#!/bin/sh\necho "$@" >> "{asked}"\n[ "$FAKE_PUBLIC" = 1 ]\n')
        base.update(GIT_SSH_COMMAND=ssh, GIT_SSH_VARIANT="simple")
        alias = "git@github.com-someone:owner/repo.git"
        d, e2 = os.path.join(top, "d"), os.path.join(top, "e")
        self.assertIn("공개 저장소다", voice(d, "setup", alias, public=True, ok=False))
        self.assertIn("비공개 저장소다", voice(d, "setup", alias))
        self.assertIn("V1. 하나", open(os.path.join(d, "VOICE.md"), encoding="utf-8").read())
        self.assertIn("묻지 않고 올린다", voice(d, "autopush", "on"))
        lines = open(asked, encoding="utf-8").read().strip().split("\n")
        self.assertTrue(all(line.endswith("ls-remote https://github.com/owner/repo.git") for line in lines), lines)
        os.remove(asked)
        out = voice(e2, "setup", "git@git.example.com:owner/repo.git")  # 바꿀 수 없는 호스트 — 공개라고도 비공개라고도 하지 않는다
        self.assertIn("받았다", out)
        self.assertIn("확인하지 못했다", out)
        self.assertIn("확인된 저장소가 아니다", voice(e2, "autopush", "on", ok=False))
        self.assertFalse(os.path.exists(asked), "키가 붙는 주소로는 묻지 않는다")

    def test_private(self):
        """공개 저장소에 낱낱의 기록(게임의 이름 · 날짜)이 없다 — 막을 낱말은 저장소 밖의 파일에서 읽는다."""
        check = lambda *a, **env: subprocess.run([sys.executable, PRIVATE, *a], capture_output=True, text=True, env=dict(os.environ, **env))
        p = check()
        self.assertEqual(p.returncode, 0, p.stderr)
        home = tempfile.mkdtemp(prefix="kit-private-")
        self.addCleanup(shutil.rmtree, home, True)
        open(os.path.join(home, "private-words.txt"), "w", encoding="utf-8").write("# 게임의 이름\nHiggsfield\n")
        p = check(GAMEDEV_KIT_VOICE=home)
        self.assertEqual(p.returncode, 1)
        self.assertIn("README.md:", p.stderr)
        msg = os.path.join(home, "msg")
        open(msg, "w", encoding="utf-8").write("0.1.0 — 고쳤다\n# 2026-01-01 은 git 이 붙인 주석이다\n")
        self.assertEqual(check("--message", msg, GAMEDEV_KIT_VOICE=home).returncode, 0)
        open(msg, "w", encoding="utf-8").write("0.1.0 — higgsfield 에서 배운 것\n")
        self.assertIn("커밋 메시지:1: 막을 낱말", check("--message", msg, GAMEDEV_KIT_VOICE=home).stderr)
        open(msg, "w", encoding="utf-8").write("0.1.0 — 2026-01-01 에 잰 것\n")
        self.assertIn("날짜가 있다", check("--message", msg, GAMEDEV_KIT_VOICE=home).stderr)

    def test_feedback(self):
        """쌓인 줄이 키트의 이슈로 나간다 — 가짜 gh 와 가짜 GitHub 서버로. 이름이 섞인 줄은 나가지 않는다."""
        class Fake(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps([
                    {"number": 7, "title": "feedback(godot): 헤드리스는 셰이더를 컴파일하지 않는다", "body": "창으로 한 번 돌린다"},
                    {"number": 8, "title": "feedback(unity): 헤드리스는 셰이더를 컴파일하지 않는다", "body": ""},
                    {"number": 9, "title": "다른 이슈", "body": "헤드리스는 셰이더를 컴파일하지 않는다"}]).encode())

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        home = tempfile.mkdtemp(prefix="kit-send-")
        self.addCleanup(shutil.rmtree, home, True)
        root = os.path.join(home, "moongame")
        os.makedirs(os.path.join(root, "docs"))
        gh, log = os.path.join(home, "gh"), os.path.join(home, "gh.log")
        open(gh, "w").write(f"#!/bin/sh\necho \"$1 $2 $3 $4 $5\" >> '{log}'\n[ \"$2\" = create ] && echo https://github.com/me/kit/issues/12\nexit 0\n")
        os.chmod(gh, 0o755)

        def write(**over):
            json.dump({"engine": "godot", "feedback": dict({"repo": "me/kit", "gh": gh}, **over)}, open(os.path.join(root, "kit.config.json"), "w"))

        env = dict(os.environ, GAMEDEV_KIT_GITHUB_API=f"http://127.0.0.1:{server.server_port}", GAMEDEV_KIT_VOICE=os.path.join(home, "voice"))

        def send(*args, ok=True, cwd=None):
            p = subprocess.run([sys.executable, SEND] + ([] if cwd else ["--root", root]) + list(args), capture_output=True, text=True, env=env, cwd=cwd)
            self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
            return p.stdout + p.stderr

        write()
        self.assertIn("kit-feedback.md 가 없다", send("list"))
        open(os.path.join(root, "docs/GDD.md"), "w", encoding="utf-8").write("# 달의 게임 — 게임 디자인 문서\n")
        run(PLAYTEST, root, "lesson", "헤드리스는 셰이더를 컴파일하지 않는다 → 창으로 한 번 돌린다")
        run(PLAYTEST, root, "lesson", "달의 게임의 문은 씬을 다시 열어야 보인다 → 씬을 다시 연다")
        run(PLAYTEST, root, "lesson", "웹 내보내기는 폴더를 만들지 않는다 → 먼저 만든다")
        fb = os.path.join(root, "docs/kit-feedback.md")
        open(fb, "a", encoding="utf-8").write("- [ ] 손으로 적은 줄\n")
        self.assertIn("`/gamedev-kit:feedback` 이 키트 저장소의 이슈로 보낸다", open(fb, encoding="utf-8").read())

        out = send("list")
        self.assertIn("안 보낸 줄 4개", out)
        self.assertIn("  1. (godot) 헤드리스는 셰이더를 컴파일하지 않는다 → 창으로 한 번 돌린다\n", out, "날짜와 사이클 번호는 나가지 않는다")
        self.assertIn("  4. (godot) 손으로 적은 줄", out)
        self.assertIn("! 이 게임의 것으로 보이는 낱말: ‘달의 게임’", out)
        out = send("preview", "all")
        self.assertIn("보낼 곳: https://github.com/me/kit/issues\n", out)
        self.assertRegex(out, r"\[1\] feedback\(godot\): 헤드리스는 셰이더를 컴파일하지 않는다\n.*→ 창으로 한 번 돌린다\n\n엔진: godot · 키트: \d+\.\d+\.\d+\n~ 비슷한 이슈 #7")
        self.assertNotIn("#8", out, "다른 엔진의 이슈는 비슷한 것으로 치지 않는다")
        self.assertNotIn("#9", out)
        self.assertFalse(os.path.exists(log), "미리 보기는 아무것도 보내지 않는다")

        self.assertIn("2번 줄에 이 게임의 것으로 보이는 낱말이 있다", send("send", "1,2", ok=False))
        self.assertFalse(os.path.exists(log), "하나라도 걸리면 아무것도 보내지 않는다")
        self.assertIn("이슈 #12 을 열었다: https://github.com/me/kit/issues/12", send("send", "3"))
        self.assertIn("이슈 #7 에 달았다", send("send", "1", "--to", "#7"))
        self.assertEqual(open(log).read().split("\n")[:2], ["issue create --repo me/kit --title", "issue comment 7 --repo me/kit"])
        text = open(fb, encoding="utf-8").read()
        self.assertRegex(text, r"- \[>\] \(godot · 플레이테스트 · [\d-]+\) 헤드리스는 .* — 이슈 #7\n")
        self.assertRegex(text, r"- \[>\] \(godot · 플레이테스트 · [\d-]+\) 웹 내보내기는 .* — 이슈 #12\n")
        self.assertIn("--to 는 줄 하나에만", send("send", "all", "--to", "7", ok=False))
        send("skip", "1", "이 게임만의  것")
        self.assertIn("씬을 다시 연다 — 안 보냄: 이 게임만의 것\n", open(fb, encoding="utf-8").read())
        self.assertIn("번호가 없다 — 안 보낸 줄은 1개다", send("send", "2", ok=False))

        # gh 를 못 쓰면 내용이 채워진 주소를 주고, 사용자가 올린 뒤 번호를 적는다
        write(gh=os.path.join(home, "no-gh"))
        out = send("send", "1")
        self.assertIn("gh 가 없다 — 사용자가 손수 올린다: https://github.com/me/kit/issues/new?title=feedback%28godot%29%3A%20", out)
        self.assertIn("- [ ] 손으로 적은 줄", open(fb, encoding="utf-8").read())
        send("sent", "1", "#15")
        self.assertIn("- [>] 손으로 적은 줄 — 이슈 #15", open(fb, encoding="utf-8").read())
        self.assertIn("안 보낸 줄 0개", send("list"))
        self.assertIn("— 0줄", subprocess.run([sys.executable, FEEDBACK, "list", root], capture_output=True, text=True).stdout,
                      "보낸 줄은 키트 쪽 목록에서도 빠진다")

        # 세션이 시작될 때: 쌓였을 때만 한 줄, 밖을 보지 않고, 무슨 일이 있어도 0 으로 끝난다
        self.assertEqual(send("--notice", cwd=root), "")
        open(fb, "a", encoding="utf-8").write("".join(f"- [ ] 줄 {n}\n" for n in range(5)))
        os.makedirs(os.path.join(root, "game"))
        self.assertIn("키트로 올릴 배움이 5줄 쌓여 있다", send("--notice", cwd=os.path.join(root, "game")))
        write(notice=False)
        self.assertEqual(send("--notice", cwd=root), "")
        open(os.path.join(root, "kit.config.json"), "w").write("{깨진")
        self.assertEqual(send("--notice", cwd=root), "")
        self.assertEqual(send("--notice", cwd=home), "")

    def test_sheet(self):
        """눈으로 고르는 결정을 묻는 시트 — 물음 하나에 쪽 하나, 브라우저가 있으면 그림으로 찍는다 (가짜 브라우저)."""
        root = tempfile.mkdtemp(prefix="kit-sheet-")
        self.addCleanup(shutil.rmtree, root, True)
        fake, log = os.path.join(root, "browser"), os.path.join(root, "browser.log")
        open(fake, "w").write(f"#!/bin/sh\necho \"$@\" >> '{log}'\nfor a; do case \"$a\" in --dump-dom) echo '<html data-h=\"777\">';; "
                              "--screenshot=*) echo shot > \"${a#--screenshot=}\";; esac; done\n")
        os.chmod(fake, 0o755)
        json.dump({"engine": "godot", "cycle": {"browser": fake}}, open(os.path.join(root, "kit.config.json"), "w"))
        os.makedirs(os.path.join(root, "shots"))
        for n in ("now", "b"):
            open(os.path.join(root, "shots", f"{n}.png"), "wb").write(b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sII", 13, b"IHDR", 400, 300))
        open(os.path.join(root, "shots/photo.jpg"), "wb").write(b"\xff\xd8jpg")
        asked = [{"id": "D3", "question": "손의 자리 <어디>", "options": [{"mark": "ⓐ", "text": "지금 그대로"}, {"mark": "ⓑ", "text": "세운다", "recommend": True}],
                  "images": [{"label": "지금", "path": "shots/now.png", "crop": [100, 80, 200, 100]}, {"label": "ⓑ", "path": "shots/b.png"}]},
                 {"question": "둘째", "images": [{"path": "shots/photo.jpg"}]}]
        spec = os.path.join(root, "q.json")

        def sheet(*args, ok=True):
            json.dump(asked, open(spec, "w"))
            return run(SHEET, root, spec, *args, ok=ok)

        self.assertEqual(sheet().stdout.split(), ["docs/cycle/sheets/sheet-1.png", "docs/cycle/sheets/sheet-2.png"])
        first = open(os.path.join(root, "docs/cycle/sheets/sheet-1.html"), encoding="utf-8").read()
        self.assertIn("<h1>D3. 손의 자리 &lt;어디&gt;</h1>", first)
        self.assertIn('<li class="pick"><b>ⓑ</b>세운다<small>← 권함</small></li>', first)
        self.assertIn('style="aspect-ratio: 200 / 100"><img src="data:image/png;base64,', first)
        self.assertIn('style="width: 200.0000%; left: -50.0000%; top: -80.0000%"', first, "자른 자리가 틀을 채운다")
        self.assertIn("<h1>2. 둘째</h1>", open(os.path.join(root, "docs/cycle/sheets/sheet-2.html"), encoding="utf-8").read())
        shots = [l for l in open(log).read().split("\n") if "--screenshot" in l]
        self.assertIn("--window-size=1080,777 --screenshot=", shots[0], "쪽이 잰 높이만큼 찍는다")

        asked[1]["images"][0]["crop"] = [0, 0, 10, 10]
        self.assertIn("png 가 아니라 자를 수 없다", sheet("--name", "x", ok=False).stderr)
        self.assertFalse(os.path.exists(os.path.join(root, "docs/cycle/sheets/x-1.html")), "하나라도 틀리면 아무것도 쓰지 않는다")
        asked[1]["images"][0] = {"path": "shots/now.png", "crop": [300, 0, 200, 100]}
        self.assertIn("그림(400 × 300) 안의", sheet(ok=False).stderr)
        asked[1]["images"][0] = {"path": "shots/none.png"}
        self.assertIn("그림이 없다 — shots/none.png", sheet(ok=False).stderr)
        del asked[1]
        json.dump({"engine": "godot", "cycle": {"browser": os.path.join(root, "no-browser")}}, open(os.path.join(root, "kit.config.json"), "w"))
        out = sheet("--name", "grip", "--out", "docs/ask").stdout
        self.assertIn("docs/ask/grip-1.html\n브라우저가 없어 그림으로 찍지 못했다", out)

    def test_playtest_ledger(self):
        root = tempfile.mkdtemp(prefix="kit-playtest-")
        self.addCleanup(shutil.rmtree, root, True)
        open(os.path.join(root, "kit.config.json"), "w").write("{}")
        os.makedirs(os.path.join(root, "docs/playtest"))
        doc = os.path.join(root, "docs/playtest/2026-10-08-a.md")
        open(doc, "w", encoding="utf-8").write("""# 분석

## 요약
걷는 속도가 가장 크다.

## 사용자에게 물을 것
없음

## 작업

### [ ] T1. 걷는 속도를 낮춘다
- **분류**: 밸런스

### [ ] T2. 문을 고친다
- **분류**: 버그

## 순서
- 1차: T1, T2 — 서로 다른 파일

## 이번에 하지 않는 것
""")
        out = run(PLAYTEST, root, "next").stdout
        self.assertIn("T1. 걷는 속도를 낮춘다 (밸런스)", out)
        self.assertNotIn("물을 것", out)
        out = run(PLAYTEST, root, "task", "T2").stdout
        self.assertIn("걷는 속도가 가장 크다", out)
        self.assertIn("### [ ] T2. 문을 고친다", out)
        self.assertNotIn("T1", out)
        run(PLAYTEST, root, "mark", "T1", "done")
        run(PLAYTEST, root, "mark", "T2", "blocked", "문이 없다")
        self.assertIn("### [!] T2. 문을 고친다\n- **분류**: 버그\n- **막힘**: 문이 없다\n\n## 순서", open(doc, encoding="utf-8").read())
        self.assertIn("작업 [x] 1 · [ ] 0 · [!] 1", run(PLAYTEST, root, "status").stdout)
        open(os.path.join(root, "kit.config.json"), "w").write('{"engine": "godot"}')
        run(PLAYTEST, root, "lesson", "문은 씬을 다시 열어야 보인다 → 씬을 다시 연다")
        self.assertRegex(open(os.path.join(root, "docs/kit-feedback.md"), encoding="utf-8").read(),
                         r"- \[ \] \(godot · 플레이테스트 · \d{4}-\d\d-\d\d\) 문은 씬을 다시 열어야 보인다 → 씬을 다시 연다\n")

    def test_session_tools(self):
        root = tempfile.mkdtemp(prefix="kit-session-")
        self.addCleanup(shutil.rmtree, root, True)
        open(os.path.join(root, "kit.config.json"), "w").write("{}")
        log = os.path.join(root, "s1.jsonl")
        turn = lambda i, read: json.dumps({"type": "assistant", "timestamp": f"2026-10-08T00:0{i}:00Z", "message": {
            "id": f"m{i}", "model": "opus", "usage": {"input_tokens": 10, "cache_creation_input_tokens": 1000,
                                                        "cache_read_input_tokens": read, "output_tokens": 50}}})
        open(log, "w").write(turn(1, 50_000) + "\n" + turn(1, 50_000) + "\n" + turn(2, 250_000) + "\n")
        os.makedirs(os.path.join(root, "s1/subagents"))
        open(os.path.join(root, "s1/subagents/agent-a.jsonl"), "w").write(turn(1, 0) + "\n")
        open(os.path.join(root, "s1/subagents/agent-a.meta.json"), "w").write('{"agentType": "gamedev-kit:developer"}')

        out = subprocess.run([sys.executable, USAGE, log], capture_output=True, text=True).stdout
        self.assertIn("메인 세션 2턴 · 컨텍스트 평균 151k · 최대 251k", out, "같은 응답이 두 줄로 적혀도 한 번만 센다")
        self.assertIn("gamedev-kit:developer", out)

        def watch(cwd, session="t1"):
            p = subprocess.run([sys.executable, WATCH], capture_output=True, text=True, env=dict(os.environ, TMPDIR=root),
                               input=json.dumps({"transcript_path": log, "cwd": cwd, "session_id": session}))
            self.assertEqual(p.returncode, 0)
            return p.stdout

        out = watch(root)
        self.assertIn("약 25만 토큰", out)
        self.assertIn("/gamedev-kit:handoff resume", out)
        self.assertEqual(watch(root), "", "같은 크기에서는 다시 말하지 않는다")
        self.assertEqual(watch(tempfile.gettempdir(), "t2"), "", "게임 저장소 밖에서는 말하지 않는다")
        open(log, "a").write(turn(3, 320_000) + "\n")
        self.assertIn("약 32만 토큰", watch(root), "10만이 더 늘면 다시 말한다")
        open(log, "a").write(turn(4, 40_000) + "\n")
        self.assertEqual(watch(root), "", "줄어들면 조용하다")
        open(log, "a").write(turn(5, 210_000) + "\n")
        self.assertIn("약 21만 토큰", watch(root), "줄었다가 다시 넘으면 다시 말한다")
        self.assertEqual(subprocess.run([sys.executable, WATCH], input="깨진 입력", capture_output=True, text=True).returncode, 0)

    def test_asset_no_config(self):
        root = tempfile.mkdtemp(prefix="kit-none-")
        self.addCleanup(shutil.rmtree, root, True)
        open(os.path.join(root, "kit.config.json"), "w").write("{}")
        self.assertIn("asset.dir", run(ASSET, root, "status", ok=False).stderr)


if __name__ == "__main__":
    unittest.main(warnings="ignore")
