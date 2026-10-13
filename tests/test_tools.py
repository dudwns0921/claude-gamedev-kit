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
            self.assertEqual(got["BAL.PLAYER.WALK_SPEED"]["new_status"], "동기", "4.0 inside the range 3~5")
            self.assertEqual(got["BAL.COIN.VALUE"]["new_status"], "불일치")
            self.assertEqual(got["BAL.NOT.YET"]["new_status"], "미구현")
            self.assertEqual(got["RULE.COIN.PICKUP"]["new_status"], "동기?")
            self.assertEqual(got["RULE.COIN.PICKUP"]["hits"][0]["symbol"], CODE[engine][1])
            self.assertEqual(list(data["orphans"]), ["BAL.STRAY.ONE"])

            run(REPORT, root, "--write")
            gdd = open(os.path.join(root, "docs/GDD.md"), encoding="utf-8").read()
            self.assertIn(f"| BAL.PLAYER.HP | 100 | 4 | {rel}:PLAYER_HP | 동기 |", gdd)
            self.assertIn(f"| BAL.COIN.VALUE | 7 | 4 | {rel}:COIN_VALUE | 불일치 |", gdd, "the 값 column stays as it is")
            self.assertIn("| BAL.OLD.THING | — | 4 | — | 폐기 |", gdd)
            self.assertIn(f"| RULE.COIN.PICKUP | 닿으면 줍는다 | 4 | {rel}:{CODE[engine][1]} | 동기 |", gdd)

    def test_balance_table(self):
        for _engine, root, code, table, _rel in self.each():
            before = open(code, encoding="utf-8").read()
            self.assertIn("5 lines", run(TABLE, root, "export").stdout)
            self.assertIn("code match", run(TABLE, root, "check").stdout)
            first = open(table, "rb").read()
            run(TABLE, root, "export")
            self.assertEqual(first, open(table, "rb").read(), "same values, same file")

            excel_save(table, {"PLAYER_HP": "120", "PLAYER_WALK_SPEED": "4.25", "COIN_VALUE": "5",
                               "UNMARKED": "3", "NO_SUCH_NAME": "1"})
            p = run(TABLE, root, "check", ok=False)
            self.assertEqual(p.returncode, 1)
            self.assertIn("PLAYER_HP: code 100 · table 120", p.stdout)
            self.assertIn("only in the table (ignored): NO_SUCH_NAME", p.stdout)
            self.assertRegex(p.stdout, r"only in the code \(not in the table\): [A-Z_]+\n", "a value new in the code and missing from the table is reported")
            excel_save(table, {"PLAYER_HP": "100"})
            self.assertRegex(run(TABLE, root, "check").stdout, r"The table and the code match — but \d value\(s\) are only in the code")
            excel_save(table, {"PLAYER_HP": "120", "PLAYER_WALK_SPEED": "4.25", "COIN_VALUE": "5", "UNMARKED": "3", "NO_SUCH_NAME": "1"})

            run(TABLE, root, "bake")
            after = open(code, encoding="utf-8").read()
            expect = before
            for old, new in (("100", "120"), ("4.0", "4.25"), ("2.5", "3.0")):
                self.assertEqual(expect.count(old), 1)
                expect = expect.replace(old, new)
            self.assertEqual(after, expect, "only the values change; every other character stays")
            self.assertIn("code match", run(TABLE, root, "check").stdout)

            excel_save(table, {"PLAYER_HP": "120.5"})
            self.assertIn("for an integer value", run(TABLE, root, "check", ok=False).stderr)

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
        self.assertNotEqual(one["stamp"], two["stamp"], "saving changes the stamp")
        self.assertEqual(two["values"], {"PLAYER_HP": 80.0}, "cells that are not numbers are skipped")

        # some clients put the whole address on the request line
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
        self.assertEqual(e.exception.code, 503, "a half-read file")

    def test_init(self):
        init = os.path.join(KIT, "skills/init/scripts/init.py")
        for engine in CODE:
            with self.subTest(engine=engine):
                root = tempfile.mkdtemp(prefix=f"kit-init-{engine}-")
                self.addCleanup(shutil.rmtree, root, True)
                out = run(init, root, engine).stdout
                self.assertIn("new      kit.config.json", out)
                claude = open(os.path.join(root, "CLAUDE.md"), encoding="utf-8").read()
                self.assertIn("/gamedev-kit:gdd-sync", claude)
                extra = os.path.join(KIT, "engines", engine, "CLAUDE.md")
                if os.path.exists(extra):
                    self.assertIn(open(extra, encoding="utf-8").read().strip(), claude)
                self.rules_block(init, root, engine, claude)
                open(os.path.join(root, "CLAUDE.md"), "w", encoding="utf-8").write("내 규칙")
                again = run(init, root, engine).stdout
                self.assertNotIn("  new      ", again, "the second run creates nothing")
                self.assertEqual(open(os.path.join(root, "CLAUDE.md"), encoding="utf-8").read(), "내 규칙")
                self.assertIn("no block — `--rules`", again)
                self.assertNotIn("sections missing", again, "a config installed just now lacks no section")
                engine_files = os.path.join(KIT, "engines", engine, "files")
                if os.path.exists(engine_files):  # a project that moved the value file — reinstalling does not bring the template back
                    moved = json.load(open(os.path.join(root, "kit.config.json"), encoding="utf-8"))["balance-table"]["code"]
                    os.remove(os.path.join(root, moved))
                    whole = open(os.path.join(root, "kit.config.json"), encoding="utf-8").read()
                    cfg = json.loads(whole)
                    cfg.pop("deploy")
                    cfg["balance-table"].pop("table")
                    json.dump(cfg, open(os.path.join(root, "kit.config.json"), "w"))
                    third = run(init, root, engine).stdout
                    self.assertIn("skipped  engine templates: 1", third)
                    self.assertFalse(os.path.exists(os.path.join(root, moved)))
                    self.assertIn("sections missing from kit.config.json: ", third)
                    self.assertIn("deploy · balance-table.table", third.split("sections missing from kit.config.json: ")[1])
                    self.assertIn("new      " + moved, run(init, root, engine, "--files").stdout)
                    open(os.path.join(root, "kit.config.json"), "w", encoding="utf-8").write(whole)
                if os.path.exists(os.path.join(KIT, "engines", engine, "files")):
                    self.assertIn("The table and the code match", (run(TABLE, root, "export"), run(TABLE, root, "check"))[1].stdout)
                    self.assertIn("| 동기 | 3 |", run(REPORT, root).stdout, "the template's three example rows pair with the value file")

    def test_init_project(self):
        """Recognises an engine project · finds the editor and modules · creates one. The editor is fake — what differs per engine comes only from engines/<engine>/project.json."""
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
        self.assertIn("not an engine project — engines to choose from: godot · unity", out)
        self.assertIn("the kit is not installed yet", out)
        self.assertIn("points to does not exist", init("unity", "--editor", ok=False, UNITY=os.path.join(top, "없다")))
        if "modules" in spec["editor"].get(sys.platform, {}):
            out = init("unity", "--editor", ok=False, UNITY=unity)
            self.assertIn(f"Unity 6000.1.2f1 — {unity}", out)
            self.assertIn("missing  Android Build Support", out)
            self.assertIn("install-modules --version 6000.1.2f1 -m android android-sdk-ndk-tools android-open-jdk", out)
            for part in ("SDK", "NDK"):
                os.makedirs(os.path.join(modules, "AndroidPlayer", part))
            self.assertIn("OpenJDK not found in it", init("unity", "--editor", ok=False, UNITY=unity))
            os.makedirs(os.path.join(modules, "AndroidPlayer", "OpenJDK"))
            out = init("unity", "--editor", UNITY=unity)
            self.assertIn("found    Android Build Support (SDK · NDK · OpenJDK)", out)
            self.assertIn(f"Write under `## This game's rules` in CLAUDE.md (that heading already exists — do not create a new one): editor executable `{unity}` · installed modules Android Build Support", out)

        self.assertIn("created the unity project", init("unity", "--create", UNITY=unity))
        self.assertTrue(os.path.exists(os.path.join(root, "docs")), "what was there is untouched")
        self.assertIn("unity — ProjectSettings/ProjectVersion.txt exists", init("--detect"))
        self.assertIn("already a unity project", init("unity", "--create", UNITY=unity))
        self.assertIn("already a unity project — not creating a godot project on top of it", init("godot", "--create", ok=False))
        out = init("unity")
        self.assertIn("added    .gitignore (unity — 10 lines: Temp/", out, "the two lines already there are not written again")
        self.assertNotIn("not a unity project yet", out)
        self.assertIn("the kit is already installed as unity", init("--detect"))
        self.assertIn("every line is already there", init("unity", "--gitignore"))
        ignore = open(os.path.join(root, ".gitignore"), encoding="utf-8").read().split("\n")
        for line in open(os.path.join(KIT, "engines/unity/gitignore"), encoding="utf-8").read().split():
            self.assertEqual(ignore.count(line), 1, line)
        self.assertNotIn("error", init("unity", "--import", UNITY=unity))
        open(os.path.join(root, "BROKEN"), "w").close()
        self.assertIn("error CS1002", init("unity", "--import", ok=False, UNITY=unity))

        # Godot has no create command — one file is the project. It is created even without the editor
        root = os.path.join(top, "game2")
        os.makedirs(root)
        self.assertIn("not a godot project yet", init("godot"))
        self.assertIn("created the godot project", init("godot", "--create"))
        self.assertIn('config/version="0.1.0"', open(os.path.join(root, "project.godot"), encoding="utf-8").read())
        self.assertIn("godot — project.godot exists", init("--detect"))
        self.assertIn("--headless --path", init("godot", "--import", GODOT=unity))

        # with several versions, the newest — compared as numbers. The script knows no engine's name: one folder is one engine
        engines = os.path.join(top, "engines")
        os.makedirs(os.path.join(engines, "toy"))
        json.dump({"engine": "toy"}, open(os.path.join(engines, "toy", "kit.config.json"), "w"))
        toy = {"marker": "toy.project", "create": {"files": {"toy.project": ""}}, "modules": [{"name": "모듈", "dir": "m"}],
               "editor": {"name": "Toy", "env": "TOY", "version": "/ed/([^/]+)/", "missing": ["Toy 를 깐다"],
                          sys.platform: {"glob": [os.path.join(top, "ed", "*", "toy")], "modules": "mods"}}}
        json.dump(toy, open(os.path.join(engines, "toy", "project.json"), "w"))
        self.assertIn("Toy editor not found — the user installs it:\n  Toy 를 깐다", init("toy", "--editor", ok=False, GAMEDEV_KIT_ENGINES=engines))
        for version in ("9.2", "10.1"):
            os.makedirs(os.path.join(top, "ed", version, "mods", "m"))
            open(os.path.join(top, "ed", version, "toy"), "w").close()
        out = init("toy", "--editor", GAMEDEV_KIT_ENGINES=engines)
        self.assertIn(f"Toy 10.1 — {os.path.join(top, 'ed', '10.1', 'toy')}", out)
        self.assertIn("installed versions 9.2 · 10.1 — picked the newest", out)
        self.assertIn("found    모듈", out)

    def rules_block(self, init, root, engine, fresh):
        """In CLAUDE.md the kit's part is one block — when the version goes up only that span changes and the outside stays."""
        path = os.path.join(root, "CLAUDE.md")
        text = lambda: open(path, encoding="utf-8").read()
        put = lambda s: open(path, "w", encoding="utf-8").write(s)
        check = lambda: subprocess.run([sys.executable, init, "--rules-check"], cwd=root, capture_output=True, text=True).stdout
        self.assertRegex(fresh, r"<!-- gamedev-kit 시작 · [0-9a-f]{8} ")
        self.assertIn("<!-- gamedev-kit 끝 -->\n\n## This game's rules", fresh)
        self.assertIn("match the current version", run(init, root, engine, "--rules").stdout)
        self.assertEqual(check(), "", "silent when they match")

        old = "## 옛 규칙\n옛 말"
        mark = __import__("hashlib").sha1(old.encode()).hexdigest()[:8]
        put(f"# 내 게임\n\n<!-- gamedev-kit 시작 · {mark} — 옛 판 -->\n{old}\n<!-- gamedev-kit 끝 -->\n\n## 이 게임의 규칙\n내가 쓴 함정\n")
        self.assertIn("an older version — `--rules`", run(init, root, engine).stdout)
        self.assertIn("replaced the kit rules block in CLAUDE.md with the current version", run(init, root, engine, "--rules").stdout)
        stale = text()
        put(f"# 내 게임\n\n<!-- gamedev-kit 시작 · {mark} — 옛 판 -->\n{old}\n<!-- gamedev-kit 끝 -->\n\n## 이 게임의 규칙\n내가 쓴 함정\n")
        self.assertIn("replaced with the current version (outside the block is untouched)", check(), "the hook aligns it by itself when a session starts")
        self.assertEqual(text(), stale)
        self.assertTrue(text().startswith("# 내 게임\n\n<!-- gamedev-kit 시작 · "))
        self.assertTrue(text().endswith("<!-- gamedev-kit 끝 -->\n\n## 이 게임의 규칙\n내가 쓴 함정\n"), "outside the block is untouched")
        self.assertNotIn("옛 말", text())
        self.assertIn("/gamedev-kit:gdd-sync", text())
        self.assertEqual(check(), "")

        put(text().replace("## The GDD and the code must always agree", "## 가끔 같아도 된다"))
        self.assertIn("edited by hand", check())
        self.assertIn("not overwriting", run(init, root, engine, "--rules", ok=False).stderr)
        self.assertIn("가끔 같아도 된다", text())
        run(init, root, engine, "--rules", "--force")
        self.assertNotIn("가끔 같아도 된다", text())

        put("# 옛 게임\n\n## Balance values are edited in the table\n이 게임에서 고쳐 쓴 말\n")
        self.assertIn("has no kit rules block", check())
        out = run(init, root, engine, "--rules").stdout
        self.assertIn("appended the kit rules block at the end of CLAUDE.md", out)
        self.assertIn("sections with the same titles remain outside the block (copied from an older version): Balance values are edited in the table", out)
        self.assertTrue(text().startswith("# 옛 게임\n\n## Balance values are edited in the table\n이 게임에서 고쳐 쓴 말\n\n<!-- gamedev-kit 시작"))
        put("# 옛 게임\n")
        cfg_path = os.path.join(root, "kit.config.json")
        whole = open(cfg_path, encoding="utf-8").read()
        json.dump(dict(json.loads(whole), init={"rules": False}), open(cfg_path, "w"))
        self.assertEqual(check(), "", "silent when told not to report")
        open(cfg_path, "w", encoding="utf-8").write(whole)
        os.remove(path)
        self.assertEqual(check(), "")
        self.assertIn("created CLAUDE.md", run(init, root, engine, "--rules").stdout)
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
        self.assertIn("me/game · version 0.3.0", run(DEPLOY, root, "check").stdout)
        self.assertIn("no build in", run(DEPLOY, root, "push", "--dry-run", ok=False).stderr)
        self.assertIn("1 file(s)", run(DEPLOY, root, "build").stdout)
        self.assertIn("not uploaded", run(DEPLOY, root, "push", "html5", "--dry-run").stdout)
        run(DEPLOY, root, "push")
        out = os.path.join(os.path.realpath(root), "out")
        self.assertEqual(open(log).read().replace(os.path.join(root, "out"), out).split("\n")[:2],
                         [f"push {out} me/game:html5 --userversion 0.3.0 --dry-run",
                          f"push {out} me/game:html5 --userversion 0.3.0"])
        self.assertIn("unknown channel", run(DEPLOY, root, "build", "win", ok=False).stderr)

        write(pre=["false"])
        self.assertIn("pre-check failed", run(DEPLOY, root, "push", ok=False).stderr)
        self.assertEqual(len(open(log).read().strip().split("\n")), 2, "butler is not called when a check fails")
        write(itch="game")
        self.assertIn("user/game", run(DEPLOY, root, "check", ok=False).stderr)
        write(butler=os.path.join(root, "no-butler"))
        self.assertIn("butler not found", run(DEPLOY, root, "check", ok=False).stderr)

    def test_deploy_engine_config(self):
        for engine in CODE:
            with self.subTest(engine=engine):
                root = tempfile.mkdtemp(prefix=f"kit-deploy-{engine}-")
                self.addCleanup(shutil.rmtree, root, True)
                shutil.copy(os.path.join(KIT, "engines", engine, "kit.config.json"), os.path.join(root, "kit.config.json"))
                cfg = json.load(open(os.path.join(root, "kit.config.json"), encoding="utf-8"))
                self.assertNotIn("promo", cfg)
                self.assertIn("deploy.itch", run(DEPLOY, root, "check", "--dirty", ok=False).stderr, "right after install the target is empty")
                if engine in VERSION_LINE:
                    path = os.path.join(root, cfg["deploy"]["version"]["file"])
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    open(path, "w").write("앞줄\n" + VERSION_LINE[engine] + "\n")
                    self.assertEqual(run(DEPLOY, root, "version").stdout.strip(), "1.2.3")
                if not cfg["deploy"]["channels"]:
                    self.assertIn("channels in kit.config.json is empty", run(DEPLOY, root, "build", ok=False).stderr)

    def asset_project(self, blender):
        """Fake OpenAI · Meshy server and a project pointed at it. (root, the function to call, the requests the server got)"""
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
                done = polls >= 2  # the first poll says not yet
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
        self.assertIn("already exists", asset("new", "crate", "--size", "1", "x", ok=False))
        self.assertIn("lowercase", asset("new", "Big-Crate", "--size", "1", "x", ok=False))
        self.assertIn("asset-style", asset("image", "crate", ok=False), "no art style, no drawing")
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("# 규칙\n<!-- asset-style -->\nChunky low-poly,\nmuted palette.\n<!-- /asset-style -->\n")
        self.assertIn("OPENAI_API_KEY is missing", asset("image", "crate", ok=False, env={k: v for k, v in env.items() if k != "OPENAI_API_KEY"}))
        self.assertEqual(seen, [])

        asset("image", "crate")
        first = posts("/images/generations")[0]
        self.assertIn("A wooden crate with iron corners. Front view", first["prompt"])
        self.assertIn("Chunky low-poly, muted palette.", first["prompt"])
        self.assertEqual((first["background"], first["model"]), ("transparent", "gpt-image-2.5-flare"))
        back = posts("/images/edits")[0]
        self.assertIn(b"back view", back)
        self.assertIn(b'name="image[]"; filename="front.png"', back, "the back is drawn from the front")
        self.assertIn("The object is: A wooden crate with iron corners. Draw what is really seen from this side — do not mirror".encode(), back,
                      "drawn from the front image alone, it comes out as the front mirrored — say what it is and not to flip it")
        self.assertIn("look, then approve", asset("status"))
        os.makedirs(os.path.join(root, "assets/_gen/loose"))
        open(os.path.join(root, "assets/_gen/loose/asset.json"), "w").write('{"name": "loose"}')
        self.assertIn("loose", asset("status"), "a hand-written record with fields missing does not crash it")
        shutil.rmtree(os.path.join(root, "assets/_gen/loose"))

        self.assertIn("no approved images", asset("mesh", "crate", ok=False))
        asset("approve", "crate")
        self.assertIn("--note goes with --view", asset("image", "crate", "--note", "x", ok=False))
        asset("image", "crate", "--view", "back", "--note", "The hinge  side faces the viewer")
        self.assertIn(b"show the side this view faces. The hinge side faces the viewer. Chunky low-poly", posts("/images/edits")[-1], "text for that view only")
        self.assertEqual(rec("crate")["notes"], {"back": "The hinge side faces the viewer"})
        self.assertIn("no approved images", asset("mesh", "crate", ok=False), "a redrawn image needs approval again")
        self.assertEqual(posts("/multi-image-to-3d"), [])
        asset("approve", "crate")

        out = asset("mesh", "crate")
        self.assertIn("IN_PROGRESS 40%", out)
        self.assertIn("assets/models/crate.glb — triangles 2 · 1 × 1.2 × 1 m", out)
        made = posts("/multi-image-to-3d")
        self.assertEqual(len(made), 1)
        self.assertEqual(len(made[0]["image_urls"]), 2)
        self.assertTrue(made[0]["image_urls"][0].startswith("data:image/png;base64,"))
        self.assertEqual((made[0]["target_polycount"], made[0]["should_remesh"], made[0]["target_formats"]), (5000, True, ["glb"]))
        self.assertEqual(open(os.path.join(root, "assets/models/crate.glb"), "rb").read(), raw_glb())
        self.assertEqual((rec("crate")["meshy"]["credits"], rec("crate")["out"]), (20, "assets/models/crate.glb"))
        self.assertNotIn("image_urls", json.dumps(rec("crate")), "the record does not hold whole images")
        self.assertIn("done", asset("status"))

        asset("mesh", "crate")
        self.assertEqual(len(posts("/multi-image-to-3d")), 1, "a finished task is not bought again")
        self.assertIn("× 2.0 ×", asset("finish", "crate", "--size", "2"))
        self.assertEqual(len(posts("/multi-image-to-3d")), 1, "changing only the size does not call Meshy again")

        # Interrupted after the task was made — rerunning keeps waiting on that task
        asset("new", "barrel", "--size", "1", "--poly", "800", "A barrel")
        asset("image", "barrel")
        asset("approve", "barrel")
        r = rec("barrel")
        r["meshy"] = {"id": "old-task", "status": "IN_PROGRESS", "images": r["approved"]}
        json.dump(r, open(os.path.join(root, "assets/_gen/barrel/asset.json"), "w"))
        asset("mesh", "barrel")
        self.assertEqual(len(posts("/multi-image-to-3d")), 1)
        self.assertIn(("GET", "/multi-image-to-3d/old-task", None), seen)

        # What is attached to every asset has three layers — 화풍 (fixed) · 세계 · 배운 것. Words of a rejection go in the record, words that hold for all in 배운 것
        design = os.path.join(root, "docs/DESIGN.md")
        self.assertIn("asset-learned", asset("learn", "Metal is matte", ok=False), "with no place for it, it says to add one")
        open(design, "a").write("<!-- asset-world -->\nBronze age,\nweathered wood.\n<!-- /asset-world -->\n<!-- asset-learned -->\n<!-- /asset-learned -->\n")
        self.assertIn("rejection recorded (#1)", asset("reject", "barrel", "쇠가 너무 번쩍여. 다시"))
        self.assertEqual(rec("barrel")["said"][0]["said"], "쇠가 너무 번쩍여. 다시")
        self.assertIsNone(rec("barrel")["approved"], "a rejection lifts the approval")
        self.assertIn("배운 것 1 line(s)", asset("learn", "Metal is matte, never glossy."))
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

        # Reference photo — the photo is shown to draw from, not put into words
        self.assertIn("reference not found", asset("new", "lamp", "--size", "0.3", "--ref", "ref/lamp.jpg", "An oil lamp", ok=False))
        os.makedirs(os.path.join(root, "ref"))
        open(os.path.join(root, "ref/lamp.jpg"), "wb").write(b"JPEG-lamp")
        open(os.path.join(root, "ref/jar.png"), "wb").write(b"PNG-jar")
        self.assertIn("reference ref/lamp.jpg", asset("new", "lamp", "--size", "0.3", "--ref", "ref/lamp.jpg", "An oil lamp"))
        before = len(posts("/images/generations"))
        asset("image", "lamp")
        self.assertEqual(len(posts("/images/generations")), before, "with a reference, it is not drawn from words alone")
        drew = posts("/images/edits")[-2]
        self.assertIn(b'filename="lamp.jpg"\r\nContent-Type: image/jpeg\r\n\r\nJPEG-lamp', drew)
        self.assertIn(b"The first attached image shows the subject: redraw this exact object", drew)
        self.assertIn(b"An oil lamp. Front view", drew)
        self.assertIn(b'filename="front.png"', posts("/images/edits")[-1], "the other views are drawn from the drawn front")
        asset("image", "urn", "--ref", "ref/jar.png")
        self.assertEqual(rec("urn")["ref"], "ref/jar.png", "a reference can also be given later")
        self.assertIn("--as-is goes with", asset("new", "pot", "--size", "1", "--ref", "ref/lamp.jpg", "--as-is", "A pot", ok=False))
        asset("new", "jar", "--size", "0.4", "--ref", "ref/jar.png", "--as-is", "A jar")
        edits = len(posts("/images/edits"))
        asset("image", "jar")
        self.assertEqual(open(os.path.join(root, "assets/_gen/jar/front.png"), "rb").read(), b"PNG-jar", "used as is, it is not redrawn")
        self.assertEqual(len(posts("/images/edits")), edits + 1, "only the back is drawn")

        # Asset sheet — everything side by side on one screen. When the art style paragraph changes, what was drawn before gets marked
        cfg_path = os.path.join(root, "kit.config.json")
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        cfg["asset"]["refs"] = ["assets/_gen/crate/front.png"]
        json.dump(cfg, open(cfg_path, "w"))
        self.assertIn("docs/board/index.html", run(BOARD, root).stdout)
        sheet = open(os.path.join(root, "docs/board/assets.html"), encoding="utf-8").read()
        index = open(os.path.join(root, "docs/board/index.html"), encoding="utf-8").read()
        self.assertIn('<a class="tile go" href="assets.html"><span class="lab">models · images 5 · sounds 0</span><b>Asset sheet →</b></a>', index)
        self.assertLess(index.index('href="assets.html"'), index.index('class="flow"'), "the way to the sheet sits above the stage cards, always in view")
        self.assertIn("Chunky low-poly, muted palette.", sheet)
        self.assertIn("Bronze age, weathered wood.", sheet)
        self.assertIn("Faces are simple", sheet)
        tile = lambda n: sheet.split(f"<span>{n}</span>")[1].split("</div></div>")[0]
        self.assertIn("in the game", tile("crate"))
        self.assertIn("sample", tile("crate"))
        self.assertIn('title="쇠가 너무 번쩍여. 다시">rejected 1', tile("barrel"))
        self.assertIn("reference", tile("lamp"))
        self.assertNotIn("old style", sheet)
        changed = open(design).read().replace("muted palette.", "bright palette.")
        open(design, "w").write(changed)
        run(BOARD, root, "--if-stale")
        sheet = open(os.path.join(root, "docs/board/assets.html"), encoding="utf-8").read()
        self.assertIn("drawn in an old style 4", sheet, "a photo used as is has nothing to do with the art style")

        # What is in the game without a record also goes on the sheet. If the page is missing (after a kit upgrade) the hook redraws it
        os.makedirs(os.path.join(root, "assets/ui"))
        open(os.path.join(root, "assets/ui/icon.png"), "wb").write(b"PNG")
        open(os.path.join(root, "assets/models/hand.glb"), "wb").write(b"glb")
        open(os.path.join(root, "assets/models/hand_normal.png"), "wb").write(b"PNG")  # textures unpacked from a model are not placed
        os.remove(os.path.join(root, "docs/board/assets.html"))
        run(BOARD, root, "--if-stale")
        sheet = open(os.path.join(root, "docs/board/assets.html"), encoding="utf-8").read()
        self.assertIn("In the game without a record<small>2</small>", sheet)
        self.assertIn("<span>icon.png</span>", sheet)
        self.assertIn("<span>hand.glb</span>", sheet)
        self.assertNotIn("<span>crate.glb</span>", sheet, "a model with a record is not placed twice")
        cfg["asset"]["work"] = "art/_gen"
        json.dump(cfg, open(cfg_path, "w"))
        os.rename(os.path.join(root, "assets/_gen"), os.path.join(root, "art_tmp"))
        os.makedirs(os.path.join(root, "art"))
        os.rename(os.path.join(root, "art_tmp"), os.path.join(root, "art/_gen"))
        run(BOARD, root)
        self.assertIn("<span>lamp</span>", open(os.path.join(root, "docs/board/assets.html"), encoding="utf-8").read(), "move the asset records and the board follows")
        self.assertNotIn("old style", sheet.split("<span>jar</span>")[1].split("</div></div>")[0])

    @unittest.skipUnless(shutil.which("blender"), "blender not found")
    def test_start(self):
        """An empty game on its way to the first cycle — where it stands is read from files. Concept pictures are drawn by a fake API server."""
        none = tempfile.mkdtemp(prefix="kit-start-none-")
        self.addCleanup(shutil.rmtree, none, True)
        self.assertIn("/gamedev-kit:init", run(START, none, "status", ok=False).stderr)
        p = subprocess.run([sys.executable, START, "status"], cwd=none, capture_output=True, text=True)
        self.assertEqual((p.returncode, "/gamedev-kit:init" in p.stderr), (1, True))

        root, _asset, seen, env = self.asset_project("blender")
        self.assertIn("the template appears", run(START, root, "status", ok=False).stderr)
        gdd = os.path.join(root, "docs/GDD.md")
        shutil.copy(os.path.join(KIT, "templates/GDD.md"), gdd)

        def fill(title):
            text = open(gdd, encoding="utf-8").read()
            open(gdd, "w", encoding="utf-8").write(text.replace(f"{title}\n", f"{title}\n\n정한 것\n", 1))

        out = run(START, root, "status").stdout
        self.assertIn("[to do] GDD (docs/GDD.md) — empty sections: 개요 · 게임 구조 · 규칙 · 제작 범위 · sections that may stay empty: 톤 · 사운드", out, "lines that came with the template are not text")
        self.assertIn("next: GDD stage", out)
        self.assertTrue(os.path.exists(out.strip().split(": ")[-1]), out)
        self.assertTrue(out.strip().endswith(os.path.join("stages", "gdd.md")))
        for title in ("## 1. 개요", "## 2. 게임 구조", "## 4. 규칙과 시스템"):
            fill(title)
        self.assertIn("empty sections: 제작 범위", run(START, root, "status").stdout)
        self.assertIn("GDD stage: skipped —", run(START, root, "skip", "gdd").stdout)
        self.assertIn("gdd · concept", run(START, root, "skip", "goal", ok=False).stderr)
        out = run(START, root, "status").stdout
        self.assertIn("[skipped] GDD", out)
        self.assertIn("skipped stages: GDD", out)
        self.assertIn("next: concept stage", out)
        self.assertEqual(json.load(open(os.path.join(root, "docs/start/state.json"), encoding="utf-8")), {"skip": ["gdd"]})
        run(START, root, "unskip", "gdd")
        fill("## 7. 제작 범위")
        out = run(START, root, "status").stdout
        self.assertIn("[done] GDD (docs/GDD.md) — sections with text: 개요 · 게임 구조 · 규칙 · 제작 범위 · sections that may stay empty: 톤 · 사운드\n", out)
        self.assertNotIn("skipped stages", out)
        self.assertIn("the 아트 방향 section of docs/GDD.md is empty · no pictures in docs/concept/", out)
        self.assertTrue(out.strip().endswith(os.path.join("stages", "concept.md")))

        def concept(*args, ok=True, env=env):
            p = subprocess.run([sys.executable, CONCEPT, "--root", root, *args], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
            return p.stdout + p.stderr

        posts = lambda path: [b for m, p, b in seen if m == "POST" and p == path]
        self.assertIn("no pictures in docs/concept/", concept("list"))
        self.assertIn("OPENAI_API_KEY is not set", concept("new", "look_a", "x", ok=False, env={k: v for k, v in env.items() if k != "OPENAI_API_KEY"}))
        self.assertIn("lowercase", concept("new", "Look A", "x", ok=False))
        self.assertEqual(seen, [])
        self.assertIn("docs/concept/look_a.png — the user opens it", concept("new", "look_a", "A small room seen from above,\n soft light"))
        first = posts("/images/generations")[0]
        self.assertEqual((first["prompt"], first["size"], first["model"], first["quality"]),
                         ("A small room seen from above, soft light", "1024x1536", "gpt-image-2.5-flare", "medium"))
        self.assertNotIn("background", first, "a concept picture does not get an empty background")
        self.assertEqual(open(os.path.join(root, "docs/concept/look_a.png"), "rb").read(), b"png1")
        self.assertIn("already exists — not overwriting", concept("new", "look_a", "another", ok=False))
        self.assertEqual(len(seen), 1, "an existing name is not drawn")
        self.assertIn("reference not found", concept("new", "look_b", "--ref", "nothing", "x", ok=False))
        concept("new", "look_b", "--size", "1536x1024", "--ref", "look_a", "warmer light")
        edit = posts("/images/edits")[0]
        self.assertIn(b'name="image[]"; filename="look_a.png"', edit, "the redraw is shown the picture the user liked")
        self.assertIn(b"png1", edit)
        self.assertIn(b"Change only what is asked below and leave everything else as it is. warmer light", edit)
        self.assertIn(b"1536x1024", edit)
        open(os.path.join(root, "docs/concept/photo.jpg"), "wb").write(b"jpg")
        out = concept("list")
        self.assertIn("docs/concept/look_a.png — 1024x1536 · A small room seen from above, soft light", out)
        self.assertIn("docs/concept/look_b.png — 1536x1024 · redrawn from docs/concept/look_a.png · warmer light", out)
        self.assertIn("docs/concept/photo.jpg — a picture the user put in", out)

        out = run(START, root, "status").stdout
        self.assertIn("[to do] concept — the 아트 방향 section of docs/GDD.md is empty", out)
        self.assertNotIn("no pictures", out)
        fill("## 5. 아트 방향")
        out = run(START, root, "status").stdout
        self.assertIn("[done] concept — the art direction is written and there are 3 pictures", out)
        self.assertIn("next: first goal stage", out)
        self.assertTrue(out.strip().endswith(os.path.join("stages", "goal.md")))
        run(CYCLE, root, "new", "first", "한 바퀴를 돈다")
        out = run(START, root, "status").stdout
        self.assertIn("the start is over — a cycle document exists (docs/cycle/01-first.md). Continue with `/gamedev-kit:cycle`", out)
        self.assertNotIn("next:", out)

        # a game that keeps the GDD elsewhere · a GDD rewritten away from the template — a missing title is not called empty
        other = tempfile.mkdtemp(prefix="kit-start-other-")
        self.addCleanup(shutil.rmtree, other, True)
        json.dump({"gdd-sync": {"gdd": "design/GDD.md"}}, open(os.path.join(other, "kit.config.json"), "w"))
        os.makedirs(os.path.join(other, "design"))
        open(os.path.join(other, "design/GDD.md"), "w", encoding="utf-8").write("# 게임\n\n## 개요\n글\n\n## 규칙\n\n## 부록 A\n")
        out = run(START, other, "status").stdout
        self.assertIn("[to do] GDD (design/GDD.md) — empty sections: 규칙 · sections with text: 개요 · sections not checked for lack of the template's title: 게임 구조 · 제작 범위 · 아트 방향", out)

    def test_asset_blender(self):
        root, asset, seen, _env = self.asset_project("blender")
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("<!-- asset-style -->\nLow-poly.\n<!-- /asset-style -->\n")
        asset("new", "pillar", "--size", "1.5", "--poly", "800", "A stone pillar")
        asset("image", "pillar")
        asset("approve", "pillar")
        self.assertIn("triangles 2 · 0.75 × 1.5 × 0.375 m", asset("mesh", "pillar"))
        self.assertEqual([b["target_polycount"] for m, p, b in seen if p == "/multi-image-to-3d" and m == "POST"], [800])
        d = open(os.path.join(root, "assets/models/pillar.glb"), "rb").read()
        g = json.loads(d[20:20 + struct.unpack("<I", d[12:16])[0]])
        box = next(a for a in g["accessors"] if "min" in a)
        for got, want in zip(box["min"] + box["max"], [-0.375, 0, -0.1875, 0.375, 1.5, 0.1875]):
            self.assertAlmostEqual(got, want, places=4, msg="longest side 1.5 m, base at 0, origin at the center")
        self.assertNotIn("translation", g["nodes"][0])
        self.assertNotIn("scale", g["nodes"][0])

    def test_sprite(self):
        """2D: picture → approval → animated sheet. Fake Ludo server — start a job, poll for the result, download the files from the addresses given."""
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
                if sum(1 for m, p, _a, _b in seen if m == "GET" and p == self.path) < 2:  # the first poll says not yet
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
        self.assertIn("already exists", sprite("new", "cook", "x", ok=False))
        self.assertIn("asset-style", sprite("image", "cook", ok=False), "no art style, no drawing")
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("<!-- asset-style -->\nFlat shapes,\nwarm palette.\n<!-- /asset-style -->\n")
        self.assertIn("LUDO_API_KEY is missing", sprite("image", "cook", ok=False, env={k: v for k, v in env.items() if k != "LUDO_API_KEY"}))
        self.assertEqual(seen, [])

        out = sprite("image", "cook")
        self.assertIn("assets/_gen/cook/still.png — 1024 × 1024 px · credits 0.5", out)
        first = posts("/assets/image")[0]
        self.assertEqual(first["image_type"], "sprite")
        self.assertTrue(first["prompt"].startswith("A cook in an apron. Seen from directly above. Flat shapes, warm palette. A single subject"), first["prompt"])
        self.assertEqual({a for m, p, a, _b in seen if not p.startswith("/file/")}, {"ApiKey k4"})
        self.assertEqual({a for m, p, a, _b in seen if p.startswith("/file/")}, {None}, "no key is sent to the addresses given")
        self.assertIn("look, then approve", sprite("status"))

        # Only an approved picture is animated. Approving puts it in the game folder
        self.assertIn("no approved picture", sprite("animate", "cook", "walk", "walking", ok=False))
        self.assertIn("approved — assets/sprites/cook.png", sprite("approve", "cook"))
        self.assertIn("--frames is one of", sprite("animate", "cook", "walk", "--frames", "12", "walking", ok=False))
        out = sprite("animate", "cook", "walk", "--seconds", "4", "--frames", "16", "walking forward")
        self.assertIn("assets/sprites/cook_walk.png — 14 frames · 4 cols × 4 rows · cell 128 × 64 px · credits 9", out)
        self.assertIn("assets/_gen/cook/walk.gif", out)
        ask = posts("/assets/sprite/animate")[0]
        self.assertEqual((ask["motion_prompt"], ask["duration"], ask["frames"], ask["model"], ask["gif"]), ("walking forward", 4.0, 16, "hydra", True))
        self.assertTrue(ask["initial_image"].endswith(f"/up/{len(seen) - [s[1] for s in seen[::-1]].index('/assets/uploads')}"), "the picture is uploaded and its address handed over")
        put = [s for s in seen if s[0] == "PUT"][0]
        self.assertEqual((put[2], put[3]), (None, open(os.path.join(root, "assets/_gen/cook/still.png"), "rb").read()))
        self.assertEqual(rec("cook")["motions"]["walk"]["cell"], [128, 64])
        self.assertIn("cook_walk.png — 14 frames", sprite("status"))
        self.assertIn("87.5", sprite("credits"))

        # An interrupted job continues with the same command — it is not bought anew
        r = rec("cook")
        r["motions"]["walk"]["job"] = {"id": "job-old", "status": "running"}
        json.dump(r, open(os.path.join(root, "assets/_gen/cook/sprite.json"), "w"))
        jobs["job-old"] = "/assets/sprite/animate"
        sprite("animate", "cook", "walk", "walking forward")
        self.assertEqual(len(posts("/assets/sprite/animate")), 1)
        self.assertEqual(rec("cook")["motions"]["walk"]["made"], 2)

        # A rejection lifts the approval. So does redrawing
        self.assertIn("rejection recorded (#1)", sprite("reject", "cook", "앞치마가 너무 커"))
        self.assertIn("no approved picture", sprite("animate", "cook", "idle", "breathing", ok=False))

        # With an art style reference picture it matches that style; with a reference it redraws that. --as-is uses it as is
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
        self.assertEqual(len(seen), n, "used as is, nothing is called")
        sprite("new", "boom", "터진다")
        self.assertIn("400: 안 된다", sprite("image", "boom", ok=False))

        # A WebP that is .png in name only is converted to PNG with a tool on this machine. With no tool, it keeps what came and stops
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
        self.assertIn("still.webp: the downloaded picture is not a PNG (webp) and there is no tool to convert it", sprite("image", "bat", ok=False, env=dict(env, PATH=os.path.join(tools, "none"))))
        self.assertEqual(sorted(n for n in os.listdir(os.path.join(root, "assets/_gen/bat")) if n.startswith("still")), ["still.webp"])
        del webp[:]

        # The board places sprites too
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

        self.assertIn("ELEVENLABS_API_KEY is missing", sound("sfx", "coin", "x", ok=False, env={k: v for k, v in env.items() if k != "ELEVENLABS_API_KEY"}))
        self.assertIn("0.5~30 s", sound("sfx", "coin", "--seconds", "40", "x", ok=False))
        self.assertIn("lowercase", sound("sfx", "Coin", "x", ok=False))
        self.assertEqual(seen, [])

        self.assertIn("assets/sounds/coin.mp3", sound("sfx", "coin", "--seconds", "0.8", "A metal coin on stone, one bright ping."))
        path, key, body = seen[0]
        self.assertEqual((path, key), ("/sound-generation?output_format=mp3_44100_128", "k3"))
        self.assertEqual(body, {"text": "A metal coin on stone, one bright ping", "prompt_influence": 0.3, "loop": False, "duration_seconds": 0.8})
        first = open(os.path.join(root, "assets/sounds/coin.mp3"), "rb").read()

        os.makedirs(os.path.join(root, "docs"))
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("<!-- sound-style -->\n8-bit,\ndry.\n<!-- /sound-style -->\n<!-- music-style -->\nChiptune,\nslow.\n<!-- /music-style -->\n")
        self.assertIn("take 2", sound("again", "coin"))
        self.assertEqual(seen[1][2]["text"], "A metal coin on stone, one bright ping. 8-bit, dry.", "the sound style follows the description")
        self.assertNotEqual(open(os.path.join(root, "assets/sounds/coin.mp3"), "rb").read(), first)

        self.assertIn("looping sound", sound("sfx", "wind", "--loop", "--influence", "0.6", "Wind over a ridge"))
        self.assertEqual((seen[2][2]["loop"], seen[2][2]["prompt_influence"]), (True, 0.6))
        self.assertNotIn("duration_seconds", seen[2][2], "with no length given, it is left to decide")

        self.assertIn("must fit in 450", sound("sfx", "long", "가" * 445, ok=False), "measured after the sound style paragraph is attached")
        self.assertEqual(len(seen), 3)
        self.assertIn("3~600 s", sound("music", "theme", "--seconds", "1", "x", ok=False))
        sound("music", "theme", "--seconds", "45", "Calm exploration theme")
        self.assertEqual(seen[3][0].split("?")[0], "/music")
        self.assertEqual(seen[3][2], {"prompt": "Calm exploration theme. Chiptune, slow.", "music_length_ms": 45000,  # the sound effect style is not attached to music
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
        """Footage that looks filmed (Higgsfield) — against a fake server: upload the picture, send, wait, download. The key goes to Higgsfield only."""
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
        self.assertIn("HF_API_KEY_ID is missing", out)
        self.assertIn("HF_API_KEY_SECRET is missing", out)
        out = clip("check")
        self.assertIn("Model: higgsfield/cinema-studio/4.0", out)
        self.assertIn("Ready to run", out)
        self.assertIn("No clips", clip("status"))

        self.assertIn("picture not found", clip("new", "gate", "--for", "game", "--image", "ref.png", "x", ok=False))
        open(os.path.join(root, "ref.png"), "wb").write(b"\x89PNG pic")
        os.makedirs(os.path.join(root, "docs"))
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("<!-- footage-style -->\nHand-painted,\nmuted.\n<!-- /footage-style -->\n")
        out = clip("new", "gate", "--for", "game", "--seconds", "6", "--image", "ref.png", "A stone gate opens slowly.")
        self.assertIn("waiting for approval — description · reference images", out)
        self.assertIn("Prompt to send: A stone gate opens slowly. Hand-painted, muted.", out, "the footage style is appended to the description")
        self.assertIn("not approved", clip("make", "gate", ok=False))
        self.assertEqual(seen, [], "nothing goes out before approval")
        clip("approve", "gate")
        out = clip("make", "gate")
        self.assertIn("video/gate/clip.mp4", out)
        ask, put, send, got = seen
        self.assertEqual(ask[:3] + ask[4:], ("POST", "/files/generate-upload-url", "Key kid:sec", {"content_type": "image/png"}))
        self.assertEqual(put[:4], ("PUT", "/store/in.png", None, "retention=temporary"), "no key goes to the storage, and the headers it gave are sent as they are")
        self.assertEqual(put[4], b"\x89PNG pic")
        self.assertEqual(send[:3], ("POST", "/higgsfield/cinema-studio/4.0", "Key kid:sec"))
        self.assertEqual(send[3], rec("gate")["request"]["key"])
        self.assertEqual(send[4], {"resolution": "720p", "prompt": "A stone gate opens slowly. Hand-painted, muted.", "duration": 6,
                                   "aspect_ratio": "16:9", "image_urls": [f"http://127.0.0.1:{server.server_port}/cdn/in.png"]})
        self.assertEqual(got[:3], ("GET", "/cdn/r3.mp4", None))
        self.assertEqual(polls, ["r3", "r3"])
        self.assertIn("a human's turn to watch", clip("status"))
        self.assertIn("already made", clip("make", "gate", ok=False))
        self.assertEqual(len(seen), 4, "the same thing is not made twice")

        # placed after a human has watched — what plays in the game goes in the format the engine reads
        self.assertIn("assets/video/gate.ogv", clip("place", "gate"))
        self.assertIn("libtheora", open(os.path.join(root, "assets/video/gate.ogv")).read())
        self.assertIn("placed — assets/video/gate.ogv", clip("status"))

        # what was sent and then cut off is waited on — not sent again
        made = rec("gate")
        made["request"]["mark"] = made["made"]["mark"]
        del made["made"]
        json.dump(made, open(os.path.join(root, "video/gate/clip.json"), "w"))
        self.assertIn("in the making", clip("status"))
        clip("make", "gate")
        self.assertEqual([s[:2] for s in seen[4:]], [("GET", "/cdn/r3.mp4")])
        clip("make", "gate", "--again")
        self.assertEqual(seen[-2][1], "/higgsfield/cinema-studio/4.0")
        self.assertNotEqual(seen[-2][3], send[3], "one more take is a new request")

        # a changed description needs approval again
        clip("new", "gate", "--for", "page", "--size", "portrait", "A stone gate closes.")
        self.assertIn("not approved", clip("make", "gate", ok=False))
        self.assertIn("no footage made from the current description", clip("place", "gate", ok=False))
        clip("approve", "gate")
        clip("make", "gate")
        self.assertEqual(seen[-2][4], {"resolution": "720p", "prompt": "A stone gate closes. Hand-painted, muted.", "duration": 5, "aspect_ratio": "9:16"})
        self.assertIn("docs/video/gate.mp4", clip("place", "gate"))

        # input names differ per model — the config sets them
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
        self.assertIn("blocked by the content check", clip("make", "bad", ok=False))
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
        self.assertIn("docs/board/index.html — GDD synced 1/5 · mismatched 0 · cycles 0", run(BOARD, root).stdout)

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
        self.assertIn("<title>게임 — chart</title>", chart)
        self.assertIn('href="stage-1.html"', chart, "첫 화면의 카드는 단계의 쪽으로 간다")
        self.assertIn('href="assets.html">Asset sheet →</a>', open(os.path.join(root, "docs/board/stage-1.html"), encoding="utf-8").read(), "단계의 쪽에서 에셋 시트로 간다")
        self.assertIn("<h2>규칙 &lt;b&gt;</h2>", chart, "flow 가 없으면 GDD 절마다 단계 하나")
        self.assertIn("<em>1/5</em>", chart, "기능 칸은 GDD 표의 상태를 센다")
        stage = open(os.path.join(root, "docs/board/stage-1.html"), encoding="utf-8").read()
        self.assertIn("<code>BAL.PLAYER.HP</code>", stage)
        self.assertIn("Cycle 01 — coins", stage, "그 단계를 건드린 사이클이 검증 칸에 선다")
        self.assertIn("<b>T1</b> 동전을 줍는다", stage, "그 단계를 건드린 작업")
        self.assertIn("D2 소리", chart, "답 없는 결정은 못 정한 것으로 선다")
        self.assertIn("동전을 줍는다", stage)
        self.assertNotIn("log.html", chart + stage)
        self.assertIn("unanswered decisions 1", run(BOARD, root).stdout)
        self.assertNotIn("Unsorted", run(BOARD, root).stdout, "어느 단계에도 안 든 것이 없으면 말하지 않는다")
        self.assertIn("<b>0</b>", chart)
        os.makedirs(os.path.join(root, "assets/sounds"))
        open(os.path.join(root, "assets/sounds/zzz_orphan.mp3"), "w").write("x")
        self.assertIn("Unsorted 1 (assets 1 — outside the %)", run(BOARD, root).stdout, "완성 % 에 안 드는 것은 그 수가 같이 보인다")
        chart = open(out, encoding="utf-8").read()
        self.assertIn('<div class="tile warn"><span class="lab">Unsorted · outside %</span><b>1</b></div>', chart)
        self.assertIn("of these, Unsorted 1 (assets 1) is outside the %", chart)
        self.assertIn("<b>Unsorted 1</b><span>assets 1</span>", chart)
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
        self.assertIn("no cycle document in docs/cycle/", run(CYCLE, root, "next", ok=False).stderr)
        self.assertIn("docs/cycle/01-dash.md", run(CYCLE, root, "new", "dash", "대시를 넣자").stdout)
        out = run(CYCLE, root, "new", "shop", "상점").stdout
        self.assertIn("docs/cycle/02-shop.md", out)
        self.assertIn("the previous cycle is still at stage 목표: docs/cycle/01-dash.md", out, "a cycle that never reached 플레이 is not closed")
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
        self.assertIn("open decisions 2", out)
        self.assertIn("next wave: 1\n", out)
        self.assertIn("T2. 값을 붙인다 — waiting on D1", out)
        self.assertNotIn("T3", out)
        run(CYCLE, root, "decide", "D1", "고정으로 가자")
        self.assertRegex(text(), r"- \[x\] D1\. 값을 어떻게 — ① 고정 ② 변동 · 권함: ① \(기획\) → 고정으로 가자 \(\d{4}-\d\d-\d\d\)")
        self.assertNotIn("waiting on D1", run(CYCLE, root, "next").stdout)

        out = run(CYCLE, root, "task", "T2").stdout
        self.assertIn("### [ ] T2. 값을 붙인다", out)
        self.assertIn("decisions it depends on:\n- [x] D1.", out)
        self.assertNotIn("T1", out, "other tasks are not pulled out")
        self.assertNotIn("D2", out, "decisions it does not depend on are not pulled out")

        run(CYCLE, root, "mark", "T1,T2", "done")
        run(CYCLE, root, "mark", "T3", "blocked", "sign.gd 가 없다")
        self.assertIn("### [x] T2. 값을 붙인다", text())
        self.assertIn("### [!] T3. 간판을 단다\n- **고칠 곳**: sign.gd\n- **막힘**: sign.gd 가 없다\n\n## 순서", text())
        self.assertIn("blocked task: T3", run(CYCLE, root, "next").stdout)
        run(CYCLE, root, "mark", "T3", "done", "sign.tscn 에 달았다")
        self.assertIn("no tasks left", run(CYCLE, root, "next").stdout)
        run(CYCLE, root, "stage", "플레이")
        out = run(CYCLE, root, "status").stdout.strip().split("\n")
        self.assertEqual(len(out), 2)
        self.assertIn("02-shop.md — stage: 플레이 · tasks [x] 3 · [ ] 0 · [!] 0 · open decisions 1", out[1])
        self.assertIn("stage: 목표", run(CYCLE, root, "next", "--doc", "docs/cycle/01-dash.md").stdout)
        self.assertIn("T9: no such task", run(CYCLE, root, "task", "T9", ok=False).stderr)

        # the way a lesson goes back to the kit
        open(os.path.join(root, "kit.config.json"), "w").write('{"engine": "godot"}')
        run(CYCLE, root, "lesson", "헤드리스는 셰이더를  컴파일하지 않는다 → 창으로 한 번 돌린다")
        run(CYCLE, root, "lesson", "둘째 줄")
        fb = lambda *a, ok=True: subprocess.run([sys.executable, FEEDBACK, *a], capture_output=True, text=True)
        out = fb("list", root, os.path.join(root, "없는곳")).stdout
        self.assertRegex(out, r"1\. \(godot · 사이클 02 · \d{4}-\d\d-\d\d\) 헤드리스는 셰이더를 컴파일하지 않는다 → 창으로 한 번 돌린다\n  2\. ")
        self.assertIn("kit-feedback.md not found", out)
        self.assertIn("1 lines: [x]", fb("done", root, "1", "0.7.2").stdout)
        out = fb("list", root).stdout
        self.assertIn("1 lines", out)
        self.assertIn("1. (godot · 사이클 02", out)
        self.assertIn("둘째 줄", out)
        self.assertIn("창으로 한 번 돌린다 — 키트 0.7.2", open(os.path.join(root, "docs/kit-feedback.md"), encoding="utf-8").read())
        self.assertNotEqual(fb("done", root, "5", "x").returncode, 0)

        # there is no closing stage — a cycle standing at 플레이 becomes 끝 when the next cycle is made, and what is left · deferred is reported
        run(CYCLE, root, "later", "간판에  불을 켜는 건 다음에")
        self.assertIn("## 플레이\n- 다음에: 간판에 불을 켜는 건 다음에\n", text())
        self.assertNotIn("## 회고", text())
        out = run(CYCLE, root, "new", "auto", "알아서").stdout
        self.assertIn("closed: docs/cycle/02-shop.md", out)
        self.assertIn("left in the previous cycle: open decisions 1", out)
        self.assertIn("deferred: 간판에 불을 켜는 건 다음에", out)
        self.assertIn("단계: 끝", text())

        # auto mode — what was decided in the user's place is [~]. Tasks depending on it run, and it stays unconfirmed until the user accepts or overturns it
        auto = os.path.join(root, "docs/cycle/03-auto.md")
        atext = lambda: open(auto, encoding="utf-8").read()
        for q in ("문 — ① 연다 ② 닫는다 · 권함: ①", "색 — ① 빨강 ② 파랑 · 권함: ①", "값 — ① 싸게 ② 비싸게", "길 — ① 짧게 ② 길게 · 권함: ②"):
            run(CYCLE, root, "ask", "기획", q)
        planned = atext().replace("## 작업\n", "## 작업\n\n### [ ] T1. 문\n- **대기**: D1\n\n### [ ] T2. 값\n- **대기**: D3\n")
        open(auto, "w", encoding="utf-8").write(planned.replace("## 순서\n", "## 순서\n- 1차: T1, T2\n"))
        self.assertIn("D1: decided in the user's place (unconfirmed)", run(CYCLE, root, "decide", "D1", "②", "--proxy", "V3, V5").stdout)
        run(CYCLE, root, "decide", "D2", "①", "--proxy", "권함")
        run(CYCLE, root, "decide", "D4", "②", "--proxy", "V7")
        self.assertRegex(atext(), r"- \[~\] D1\. 문 — ① 연다 ② 닫는다 · 권함: ① \(기획\) → ② · 대리 V3, V5 \(\d{4}-\d\d-\d\d\)")
        out = run(CYCLE, root, "next").stdout
        self.assertIn("open decisions 1 · proxy decisions 3 (unconfirmed)", out)
        self.assertIn("proxy decision (unconfirmed): D1.", out)
        self.assertIn("open decision: D3.", out)
        self.assertIn("  T1. 문\n", out, "a task depending on a proxy decision runs")
        self.assertIn("T2. 값 — waiting on D3", out, "a task depending on a decision nobody made stands still")
        self.assertIn("D3: not a proxy decision awaiting confirmation", run(CYCLE, root, "confirm", "D3", ok=False).stderr)
        self.assertIn("accepted: D1", run(CYCLE, root, "confirm", "D1").stdout)
        self.assertRegex(atext(), r"- \[x\] D1\. 문 — ① 연다 ② 닫는다 · 권함: ① \(기획\) → ② — 대리\(V3, V5\)를 받아들임 \(\d{4}")
        run(CYCLE, root, "decide", "D2", "파랑으로 하자")
        self.assertRegex(atext(), r"- \[x\] D2\. 색 — ① 빨강 ② 파랑 · 권함: ① \(기획\) → 파랑으로 하자 \(\d{4}")
        self.assertIn("D2: the user already answered", run(CYCLE, root, "decide", "D2", "①", "--proxy", "V1", ok=False).stderr)
        self.assertIn("accepted: D4", run(CYCLE, root, "confirm", "all").stdout)
        self.assertIn("open decisions 1\n", run(CYCLE, root, "status").stdout.split("03-auto")[1] + "\n")
        out = subprocess.run([sys.executable, VOICE, "--root", root, "collect"], capture_output=True, text=True,
                             env=dict(os.environ, GAMEDEV_KIT_VOICE=os.path.join(root, "voice-home"))).stdout
        self.assertIn("03 D1 [받음]", out, "an accepted proxy decision is counted apart from one the user picked")
        self.assertIn("받음 2", out)
        run(CYCLE, root, "decide", "D3", "①")

    def test_voice(self):
        top = tempfile.mkdtemp(prefix="kit-voice-")
        self.addCleanup(shutil.rmtree, top, True)
        root, other, home = (os.path.join(top, n) for n in ("first game", "second", "home"))
        for game, cfg in ((root, "{}"), (other, '{"voice": {"name": "둘째"}}')):
            os.makedirs(game)
            open(os.path.join(game, "kit.config.json"), "w", encoding="utf-8").write(cfg)
        os.environ["GAMEDEV_KIT_VOICE"] = home  # the voice lives outside the game
        self.addCleanup(os.environ.pop, "GAMEDEV_KIT_VOICE")
        self.assertIn("no voice yet", run(VOICE, root, "path", ok=False).stderr)
        self.assertIn("no answered decisions", run(VOICE, root, "collect").stdout)
        run(CYCLE, root, "new", "dash", "대시를\n넣자")
        run(CYCLE, root, "ask", "기획", "대시 뒤 — ① 무적 ② 그대로 · 권함: ①")
        run(CYCLE, root, "ask", "디자인", "잔상 — ① 있다 ② 없다 · 권함: ①")
        run(CYCLE, root, "ask", "계획", "범위 — ① 전부 ② 반만 · 권함: ②")
        run(CYCLE, root, "ask", "계획", "순서 — ① 화면 먼저 ② 값 먼저")
        log = lambda: open(os.path.join(home, "log.md"), encoding="utf-8").read()

        # a prediction needs its principle to be in the voice
        self.assertIn("principle not in", run(VOICE, root, "predict", "D1", "②", "V1", ok=False).stderr)
        os.makedirs(home)
        open(os.path.join(home, "VOICE.md"), "w", encoding="utf-8").write(
            "# 보이스\n\n갱신: 2000-01-01 · 결정 2개 · 게임 1개에서\n\n## 원칙\n- V1. 봐주는 규칙은 넣지 않는다\n- V2. 작게 자른다\n")
        self.assertEqual(run(VOICE, root, "path").stdout.strip(), os.path.join(home, "VOICE.md"))
        self.assertIn("first-game 01 D1 (기획) → ② · V1", run(VOICE, root, "predict", "D1", "2", "V1").stdout)
        run(VOICE, root, "predict", "D2", "②", "V1,V2")
        run(VOICE, root, "predict", "D3", "②", "V2")
        self.assertIn("not an option in the question", run(VOICE, root, "predict", "D4", "③", "V1", ok=False).stderr)
        self.assertIn("→ 모름", run(VOICE, root, "predict", "D4", "-").stdout)
        self.assertIn("prediction already written", run(VOICE, root, "predict", "D1", "①", "V1", ok=False).stderr)
        self.assertIn("no prediction to score", run(VOICE, root, "score").stdout)

        run(CYCLE, root, "decide", "D1", "②. 봐주지 말자")
        run(CYCLE, root, "decide", "D2", "1번으로")
        run(CYCLE, root, "decide", "D3", "일단 반만 하자")
        run(CYCLE, root, "decide", "D4", "① 화면부터")
        self.assertIn("already answered", run(VOICE, root, "predict", "D4", "①", "V1", ok=False).stderr)
        out = run(VOICE, root, "score").stdout
        self.assertIn("01 D1: hit — predicted ② (V1)", out)
        self.assertIn("01 D2: miss — predicted ② (V1, V2) · answer: 1번으로", out)
        self.assertIn("cannot tell: 01 D3 predicted ② · answer: 일단 반만 하자", out)
        self.assertIn("no prediction to score", run(VOICE, root, "score", "01", "D1", "hit", ok=False).stderr)
        self.assertIn("01 D3: hit", run(VOICE, root, "score", "01", "D3", "hit").stdout)
        self.assertRegex(log(), r"- \[o\] first-game 01 D1 \(기획\) → ② · V1 \(\d{4}-\d\d-\d\d\)\n- \[x\] first-game 01 D2 .*\n"
                                r"- \[o\] first-game 01 D3 .*\n- \[-\] first-game 01 D4 \(계획\) → 모름")
        out = run(VOICE, root, "stats").stdout
        self.assertIn("hits 2/3 (66%) · 모름 1 · unscored 0 · predictions 4", out)
        self.assertIn("계획: 1/1 (100%) · 모름 1", out)
        self.assertIn("V1: 1/2 (50%)", out)
        self.assertIn("V2: 1/2 (50%)", out)
        self.assertNotIn("first-game:", out, "with one game there are no per-game lines")

        out = run(VOICE, root, "collect").stdout
        self.assertIn("game: first-game\n\n사이클 01 — dash\ngoal: 대시를 넣자\n", out)
        self.assertIn("first-game 01 D1 [갈림] (기획) 대시 뒤 — ① 무적 ② 그대로 · 권함: ① → ②. 봐주지 말자 (", out)
        self.assertIn("01 D2 [같음]", out)
        self.assertIn("01 D3 [?]", out)
        self.assertIn("decisions 4 · 갈림 1 · 같음 1 · to read 2", out)

        # a decision the voice has read does not come up again at the next update
        self.assertIn("decisions 4", run(VOICE, root, "collect", "new").stdout)
        self.assertIn("recorded 4 as read", run(VOICE, root, "collect", "done").stdout)
        self.assertIn("no answered decisions (among those not read yet)", run(VOICE, root, "collect", "new").stdout)
        run(CYCLE, root, "ask", "기획", "문 — ① 연다 ② 닫는다 · 권함: ①")
        run(CYCLE, root, "decide", "D5", "①")
        out = run(VOICE, root, "collect", "new").stdout
        self.assertIn("01 D5 [같음]", out)
        self.assertIn("decisions 1 ·", out)
        self.assertIn("decisions 5 ·", run(VOICE, root, "collect").stdout)

        # a decision whose answer changed — both answers come out together, and it comes up again even after being read. The picked option is told from the last answer
        run(VOICE, root, "collect", "done")
        self.assertIn("no answered decisions", run(VOICE, root, "collect", "new").stdout)
        run(CYCLE, root, "decide", "D5", "해 보니 좁다. ② 로 바꾸자")
        out = run(VOICE, root, "collect", "new").stdout
        self.assertRegex(out, r"01 D5 \[바꿈\] \(기획\) 문 — ① 연다 ② 닫는다 · 권함: ① → ① \(\d{4}-\d\d-\d\d\) → 해 보니 좁다. ② 로 바꾸자 \(")
        self.assertIn("decisions 1 · 갈림 0 · 같음 0 · to read 0 · 바꿈 1", out)
        run(VOICE, root, "collect", "done")
        self.assertIn("first-game 01 D5 #2\n", open(os.path.join(home, "seen.txt"), encoding="utf-8").read())
        self.assertIn("no answered decisions", run(VOICE, root, "collect", "new").stdout)
        run(CYCLE, root, "ask", "기획", "창 — ① 연다 ② 닫는다 · 권함: ①")
        run(VOICE, root, "predict", "D6", "②", "V1")
        run(CYCLE, root, "decide", "D6", "①")
        run(CYCLE, root, "decide", "D6", "아니 ②")
        self.assertIn("01 D6: hit", run(VOICE, root, "score").stdout, "scored against the changed answer")

        # another game's decisions pile up in the same voice — every line says which game it is from
        run(CYCLE, other, "new", "shop", "상점")
        run(CYCLE, other, "ask", "계획", "범위 — ① 전부 ② 반만 · 권함: ①")
        self.assertIn("둘째 01 D1 (계획) → ② · V2", run(VOICE, other, "predict", "D1", "②", "V2").stdout)
        run(CYCLE, other, "decide", "D1", "②")
        self.assertIn("no prediction to score", run(VOICE, root, "score").stdout, "another game's predictions are not scored")
        self.assertIn("01 D1: hit", run(VOICE, other, "score").stdout)
        self.assertIn("decisions 1 · 갈림 1", run(VOICE, other, "collect", "new").stdout)
        out = run(VOICE, other, "stats").stdout
        self.assertIn("hits 4/5 (80%) · 모름 1 · unscored 0 · predictions 6", out)
        self.assertIn("first-game: 3/4 (75%) · 모름 1", out)
        self.assertIn("둘째: 1/1 (100%) · 모름 0", out)
        self.assertIn("V2: 2/3 (66%)", out)
        self.assertFalse(os.path.exists(os.path.join(root, "docs/VOICE.md")), "the voice is not kept in the game repository")

    def test_voice_sync(self):
        """The voice folder is a clone of a private repository — two machines line up through the same repository. Only the git that reads without a login is fake."""
        top = tempfile.mkdtemp(prefix="kit-voice-sync-")
        self.addCleanup(shutil.rmtree, top, True)
        remote, a, b, bin_dir = (os.path.join(top, n) for n in ("remote.git", "a", "b", "bin"))
        subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
        os.makedirs(bin_dir)
        anon = os.path.join(bin_dir, "anon-git")  # readable without a login (0) means public
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
        self.assertIn("is not a repository", voice(a, "sync"))
        self.assertIn("public repository", voice(a, "setup", remote, public=True, ok=False))
        self.assertFalse(os.path.exists(a))

        # a machine that already has a voice — that folder becomes the repository
        os.makedirs(a)
        put(a, "# 보이스\n- V1. 하나\n")
        self.assertIn("made the existing voice a repository", voice(a, "setup", remote))
        out = voice(a, "sync", "voice: 첫 판")
        self.assertIn("committed", out)
        self.assertIn("unpushed commits 1 — ask the user", out)
        self.assertIn("not a repository confirmed private", voice(a, "autopush", "on", public=True, ok=False))
        self.assertIn("pushes without asking", voice(a, "autopush", "on"))
        self.assertIn("pushed — commits 1", voice(a, "sync"))
        self.assertIn("same as the repository", voice(a, "sync"))

        # another machine — cloning is all it takes to have the same voice. The permission is per machine
        self.assertIn("clone failed", voice(b, "setup", os.path.join(top, "없는곳.git"), ok=False))
        self.assertFalse(os.path.exists(b))
        self.assertIn("— cloned", voice(b, "setup", remote))
        self.assertIn("V1. 하나", open(os.path.join(b, "VOICE.md"), encoding="utf-8").read())
        open(os.path.join(b, "log.md"), "w", encoding="utf-8").write("- [o] 둘째 01 D1 (계획) → ② · V1\n")
        self.assertIn("unpushed commits 1", voice(b, "sync"))
        self.assertIn("pushed — commits 1", voice(b, "sync", "--push"))
        put(a, "# 보이스\n- V1. 하나\n- V2. 둘\n")
        out = voice(a, "sync")
        self.assertIn("pulled — commits 1", out)
        self.assertIn("pushed — commits 1", out)
        self.assertTrue(os.path.exists(os.path.join(a, "log.md")))

        # two machines edited the same line differently — stop and hand it to a person. This machine's copy is untouched
        put(b, "# 보이스\n- V1. 다르게\n")
        self.assertIn("merge by hand", voice(b, "sync", ok=False))
        self.assertIn("V1. 다르게", open(os.path.join(b, "VOICE.md"), encoding="utf-8").read())

        # a voice both in the repository and on this machine — it does not choose
        c = os.path.join(top, "c")
        os.makedirs(c)
        put(c, "# 보이스\n")
        self.assertIn("the user decides which one to keep", voice(c, "setup", remote, ok=False))
        self.assertFalse(os.path.exists(os.path.join(c, ".git")))

        # an SSH address (an alias in ~/.ssh/config) lets the key log in — without a login it asks the https address of the same repository. A fake ssh serves the repository above
        ssh, asked = os.path.join(bin_dir, "ssh"), os.path.join(top, "asked.txt")
        open(ssh, "w").write(f'#!/bin/sh\nexec git upload-pack "{remote}"\n')
        os.chmod(ssh, 0o755)
        open(anon, "w").write(f'#!/bin/sh\necho "$@" >> "{asked}"\n[ "$FAKE_PUBLIC" = 1 ]\n')
        base.update(GIT_SSH_COMMAND=ssh, GIT_SSH_VARIANT="simple")
        alias = "git@github.com-someone:owner/repo.git"
        d, e2 = os.path.join(top, "d"), os.path.join(top, "e")
        self.assertIn("public repository", voice(d, "setup", alias, public=True, ok=False))
        self.assertIn("private repository", voice(d, "setup", alias))
        self.assertIn("V1. 하나", open(os.path.join(d, "VOICE.md"), encoding="utf-8").read())
        self.assertIn("pushes without asking", voice(d, "autopush", "on"))
        lines = open(asked, encoding="utf-8").read().strip().split("\n")
        self.assertTrue(all(line.endswith("ls-remote https://github.com/owner/repo.git") for line in lines), lines)
        os.remove(asked)
        out = voice(e2, "setup", "git@git.example.com:owner/repo.git")  # a host that cannot be converted — says neither public nor private
        self.assertIn("— cloned", out)
        self.assertIn("could not confirm it is private", out)
        self.assertIn("not a repository confirmed private", voice(e2, "autopush", "on", ok=False))
        self.assertFalse(os.path.exists(asked), "an address that carries a key is not asked")

    def test_private(self):
        """No individual records (games' names · dates) in the public repository — the blocked words are read from a file outside the repository."""
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
        self.assertIn("commit message:1: blocked word", check("--message", msg, GAMEDEV_KIT_VOICE=home).stderr)
        open(msg, "w", encoding="utf-8").write("0.1.0 — 2026-01-01 에 잰 것\n")
        self.assertIn("commit message:1: date", check("--message", msg, GAMEDEV_KIT_VOICE=home).stderr)

    def test_feedback(self):
        """Piled-up lines go out as issues on the kit — against a fake gh and a fake GitHub server. A line with a name in it does not go out."""
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
        self.assertIn("kit-feedback.md not found", send("list"))
        open(os.path.join(root, "docs/GDD.md"), "w", encoding="utf-8").write("# 달의 게임 — 게임 디자인 문서\n")
        run(PLAYTEST, root, "lesson", "헤드리스는 셰이더를 컴파일하지 않는다 → 창으로 한 번 돌린다")
        run(PLAYTEST, root, "lesson", "달의 게임의 문은 씬을 다시 열어야 보인다 → 씬을 다시 연다")
        run(PLAYTEST, root, "lesson", "웹 내보내기는 폴더를 만들지 않는다 → 먼저 만든다")
        fb = os.path.join(root, "docs/kit-feedback.md")
        open(fb, "a", encoding="utf-8").write("- [ ] 손으로 적은 줄\n")
        self.assertIn("`/gamedev-kit:feedback` 이 키트 저장소의 이슈로 보낸다", open(fb, encoding="utf-8").read())

        out = send("list")
        self.assertIn("— 4 unsent lines", out)
        self.assertIn("  1. (godot) 헤드리스는 셰이더를 컴파일하지 않는다 → 창으로 한 번 돌린다\n", out, "the date and the cycle number do not go out")
        self.assertIn("  4. (godot) 손으로 적은 줄", out)
        self.assertIn("! words that seem to be this game's: ‘달의 게임’", out)
        out = send("preview", "all")
        self.assertIn("Goes to: https://github.com/me/kit/issues\n", out)
        self.assertRegex(out, r"\[1\] feedback\(godot\): 헤드리스는 셰이더를 컴파일하지 않는다\n.*→ 창으로 한 번 돌린다\n\n엔진: godot · 키트: \d+\.\d+\.\d+\n~ similar issue #7")
        self.assertNotIn("#8", out, "another engine's issue does not count as similar")
        self.assertNotIn("#9", out)
        self.assertFalse(os.path.exists(log), "a preview sends nothing")

        self.assertIn("line 2 has words that seem to be this game's", send("send", "1,2", ok=False))
        self.assertFalse(os.path.exists(log), "if any one is caught, nothing is sent")
        self.assertIn("opened issue #12: https://github.com/me/kit/issues/12", send("send", "3"))
        self.assertIn("commented on issue #7", send("send", "1", "--to", "#7"))
        self.assertEqual(open(log).read().split("\n")[:2], ["issue create --repo me/kit --title", "issue comment 7 --repo me/kit"])
        text = open(fb, encoding="utf-8").read()
        self.assertRegex(text, r"- \[>\] \(godot · 플레이테스트 · [\d-]+\) 헤드리스는 .* — 이슈 #7\n")
        self.assertRegex(text, r"- \[>\] \(godot · 플레이테스트 · [\d-]+\) 웹 내보내기는 .* — 이슈 #12\n")
        self.assertIn("--to takes one line only", send("send", "all", "--to", "7", ok=False))
        send("skip", "1", "이 게임만의  것")
        self.assertIn("씬을 다시 연다 — 안 보냄: 이 게임만의 것\n", open(fb, encoding="utf-8").read())
        self.assertIn("no such number — there are 1 unsent lines", send("send", "2", ok=False))

        # without gh it gives a pre-filled address, and the number is recorded after the user posts it
        write(gh=os.path.join(home, "no-gh"))
        out = send("send", "1")
        self.assertIn("gh not found — the user posts it by hand: https://github.com/me/kit/issues/new?title=feedback%28godot%29%3A%20", out)
        self.assertIn("- [ ] 손으로 적은 줄", open(fb, encoding="utf-8").read())
        send("sent", "1", "#15")
        self.assertIn("- [>] 손으로 적은 줄 — 이슈 #15", open(fb, encoding="utf-8").read())
        self.assertIn("— 0 unsent lines", send("list"))
        self.assertIn("— 0 lines", subprocess.run([sys.executable, FEEDBACK, "list", root], capture_output=True, text=True).stdout,
                      "sent lines drop out of the kit-side list too")

        # at session start: one line only when lines have piled up, no looking outside, and always exit 0
        self.assertEqual(send("--notice", cwd=root), "")
        open(fb, "a", encoding="utf-8").write("".join(f"- [ ] 줄 {n}\n" for n in range(5)))
        os.makedirs(os.path.join(root, "game"))
        self.assertIn("5 lessons for the kit have piled up", send("--notice", cwd=os.path.join(root, "game")))
        write(notice=False)
        self.assertEqual(send("--notice", cwd=root), "")
        open(os.path.join(root, "kit.config.json"), "w").write("{깨진")
        self.assertEqual(send("--notice", cwd=root), "")
        self.assertEqual(send("--notice", cwd=home), "")

    def test_sheet(self):
        """The sheet for decisions chosen by eye — one page per question, shot as a picture when there is a browser (a fake browser)."""
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
        self.assertIn('style="width: 200.0000%; left: -50.0000%; top: -80.0000%"', first, "the cropped spot fills the frame")
        self.assertIn("<h1>2. 둘째</h1>", open(os.path.join(root, "docs/cycle/sheets/sheet-2.html"), encoding="utf-8").read())
        shots = [l for l in open(log).read().split("\n") if "--screenshot" in l]
        self.assertIn("--window-size=1080,777 --screenshot=", shots[0], "shot at the height the page measured")

        asked[1]["images"][0]["crop"] = [0, 0, 10, 10]
        self.assertIn("question 2: shots/photo.jpg is not a png and cannot be cropped", sheet("--name", "x", ok=False).stderr)
        self.assertFalse(os.path.exists(os.path.join(root, "docs/cycle/sheets/x-1.html")), "if any one is wrong, nothing is written")
        asked[1]["images"][0] = {"path": "shots/now.png", "crop": [300, 0, 200, 100]}
        self.assertIn("inside the image (400 × 300)", sheet(ok=False).stderr)
        asked[1]["images"][0] = {"path": "shots/none.png"}
        self.assertIn("image not found — shots/none.png", sheet(ok=False).stderr)
        del asked[1]
        json.dump({"engine": "godot", "cycle": {"browser": os.path.join(root, "no-browser")}}, open(os.path.join(root, "kit.config.json"), "w"))
        out = sheet("--name", "grip", "--out", "docs/ask").stdout
        self.assertIn("docs/ask/grip-1.html\nno browser, so no picture was taken", out)

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
        self.assertIn("next wave: 1\n", out)
        self.assertNotIn("for the user", out)
        out = run(PLAYTEST, root, "task", "T2").stdout
        self.assertIn("걷는 속도가 가장 크다", out)
        self.assertIn("### [ ] T2. 문을 고친다", out)
        self.assertNotIn("T1", out)
        run(PLAYTEST, root, "mark", "T1", "done")
        run(PLAYTEST, root, "mark", "T2", "blocked", "문이 없다")
        self.assertIn("### [!] T2. 문을 고친다\n- **분류**: 버그\n- **막힘**: 문이 없다\n\n## 순서", open(doc, encoding="utf-8").read())
        self.assertIn("tasks [x] 1 · [ ] 0 · [!] 1", run(PLAYTEST, root, "status").stdout)
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
        self.assertIn("main session 2 turns · context average 151k · max 251k", out, "a response logged on two lines is counted once")
        self.assertIn("gamedev-kit:developer", out)

        def watch(cwd, session="t1"):
            p = subprocess.run([sys.executable, WATCH], capture_output=True, text=True, env=dict(os.environ, TMPDIR=root),
                               input=json.dumps({"transcript_path": log, "cwd": cwd, "session_id": session}))
            self.assertEqual(p.returncode, 0)
            return p.stdout

        out = watch(root)
        self.assertIn("about 251k tokens", out)
        self.assertIn("/gamedev-kit:handoff resume", out)
        self.assertEqual(watch(root), "", "it does not speak again at the same size")
        self.assertEqual(watch(tempfile.gettempdir(), "t2"), "", "it does not speak outside a game repository")
        open(log, "a").write(turn(3, 320_000) + "\n")
        self.assertIn("about 321k tokens", watch(root), "another 100k and it speaks again")
        open(log, "a").write(turn(4, 40_000) + "\n")
        self.assertEqual(watch(root), "", "silent when it shrinks")
        open(log, "a").write(turn(5, 210_000) + "\n")
        self.assertIn("about 211k tokens", watch(root), "shrinking and then passing the line again makes it speak again")
        self.assertEqual(subprocess.run([sys.executable, WATCH], input="깨진 입력", capture_output=True, text=True).returncode, 0)

    def test_asset_no_config(self):
        root = tempfile.mkdtemp(prefix="kit-none-")
        self.addCleanup(shutil.rmtree, root, True)
        open(os.path.join(root, "kit.config.json"), "w").write("{}")
        self.assertIn("asset.dir", run(ASSET, root, "status", ok=False).stderr)


if __name__ == "__main__":
    unittest.main(warnings="ignore")
