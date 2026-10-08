#!/usr/bin/env python3
"""도구 검사 — engines/ 의 엔진 설정마다 임시 프로젝트를 만들어 gdd-sync 와 balance-table 을 끝까지 돌린다.
deploy 는 가짜 butler 로, asset 은 가짜 API 서버로, video 는 가짜 hyperframes · ffmpeg 로 돌린다 — 밖으로는 아무것도 나가지 않는다.

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
VIDEO = os.path.join(KIT, "skills/video/scripts/video.py")
BOARD = os.path.join(KIT, "skills/board/scripts/board.py")
CYCLE = os.path.join(KIT, "skills/cycle/scripts/cycle.py")
PLAYTEST = os.path.join(KIT, "skills/playtest/scripts/playtest.py")
WATCH = os.path.join(KIT, "hooks/context_watch.py")
USAGE = os.path.join(KIT, "tools/session_usage.py")
FEEDBACK = os.path.join(KIT, "tools/kit_feedback.py")


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
VERSION_LINE = {"godot": 'config/version="1.2.3"'}

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
        self.assertIn("옛 판이다", check())
        self.assertIn("옛 판이다 — `--rules`", run(init, root, engine).stdout)
        self.assertIn("지금 판으로 바꿨다", run(init, root, engine, "--rules").stdout)
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
        self.assertIn("보고 approve", asset("status"))

        self.assertIn("승인된 이미지가 없다", asset("mesh", "crate", ok=False))
        asset("approve", "crate")
        asset("image", "crate", "--view", "back")
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

    @unittest.skipUnless(shutil.which("blender"), "blender 가 없다")
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
        open(os.path.join(root, "docs/DESIGN.md"), "w").write("<!-- sound-style -->\n8-bit,\ndry.\n<!-- /sound-style -->\n")
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
        self.assertEqual(seen[3][2], {"prompt": "Calm exploration theme. 8-bit, dry.", "music_length_ms": 45000,
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

    def test_video(self):
        """컷 표 → 승인 → 컴포지션 → 렌더. 승인하지 않은 표는 컴포지션이 되지 않고, 표가 바뀌면 승인이 풀린다."""
        for engine in CODE:
            with self.subTest(engine=engine):
                root = tempfile.mkdtemp(prefix=f"kit-video-{engine}-")
                self.addCleanup(shutil.rmtree, root, True)
                log = os.path.join(root, "calls.log")
                hf, ff = os.path.join(root, "hyperframes"), os.path.join(root, "ffmpeg")
                open(hf, "w").write(f"""#!/bin/sh
echo "hf $HYPERFRAMES_SKIP_SKILLS $@" >> '{log}'
case "$1" in
  init) mkdir -p "$2" && echo '<div></div>' > "$2/index.html" ;;
  lint) [ ! -e "$2/broken" ] ;;
  snapshot) mkdir -p "$2/snapshots" && echo png > "$2/snapshots/frame-1.png" ;;
  render) echo mp4 > "$4" ;;
esac
""")
                open(ff, "w").write(f"#!/bin/sh\necho \"ff $@\" >> '{log}'\nfor a; do out=$a; done\necho converted > \"$out\"\n")
                os.chmod(hf, 0o755)
                os.chmod(ff, 0o755)
                cfg = json.load(open(os.path.join(KIT, "engines", engine, "kit.config.json"), encoding="utf-8"))
                game = cfg["video"]["game"]
                cfg["video"].update(hyperframes=hf, ffmpeg=ff)
                json.dump(cfg, open(os.path.join(root, "kit.config.json"), "w"))
                os.makedirs(os.path.join(root, "docs"))
                design = os.path.join(root, "docs/DESIGN.md")
                shutil.copy(os.path.join(KIT, "templates/DESIGN.md"), design)

                def video(*args, ok=True, stdin=None):
                    p = subprocess.run([sys.executable, VIDEO, "--root", root, *args], capture_output=True, text=True, input=stdin)
                    if ok and p.returncode != 0:
                        raise AssertionError(f"video.py {' '.join(args)} → {p.returncode}\n{p.stdout}\n{p.stderr}")
                    return p

                self.assertIn("영상의 결이 비어 있다", video("check", ok=False).stderr)
                text = open(design, encoding="utf-8").read()
                open(design, "w", encoding="utf-8").write(text.replace("<!-- video-style -->", "<!-- video-style -->\nDark, slow,\n one line at a time."))
                self.assertIn("만들 수 있다 — page · game", video("check").stdout)

                self.assertIn("video/intro/video.json", video("new", "intro", "--for", "game", "게임을 켜면 나오는 것").stdout)
                self.assertIn("이미 있다", video("new", "intro", "--for", "game", "또", ok=False).stderr)
                self.assertIn("python3 video.py", video("new", "x", "--for", "tv", "어디", ok=False).stderr)
                self.assertIn("컷 표 없음 — 승인한 컷 표만", video("compose", "intro", ok=False).stderr)
                self.assertIn("2번째 줄", video("cuts", "intro", "-", stdin="2 | 제목\n셋 | 글자\n", ok=False).stderr)
                out = video("cuts", "intro", "-", stdin="# 머리\n2.5 | 제목 | 떨어진다\n1 | 이 글자는 일 초에 읽기에는 너무 길다\n4 |  | 화면 셋이 지나간다\n").stdout
                self.assertIn(" 2    2.5s +1s  이 글자는 일 초에 읽기에는 너무 길다 ← 읽기 빠듯하다", out)
                self.assertIn(" 3    3.5s +4s  (글자 없음)\n      움직임: 화면 셋이 지나간다", out)
                self.assertIn("모두 7.5초 · 컷 3개", out)
                self.assertNotIn("빠듯", out.split("\n")[0])
                self.assertIn("승인한 컷 표만", video("render", "intro", ok=False).stderr)
                self.assertFalse(os.path.exists(log), "승인 전에는 아무 도구도 부르지 않는다")

                video("approve", "intro")
                out = video("compose", "intro").stdout
                self.assertIn("컴포지션: video/intro/comp/index.html", out)
                self.assertIn("결: Dark, slow, one line at a time.", out)
                self.assertIn("모두 7.5초", out)
                video("compose", "intro")
                calls = open(log).read().strip().split("\n")
                self.assertEqual(calls, ["hf 1 init comp --non-interactive --resolution landscape"], "틀은 한 번만 만든다")
                self.assertIn("frame-1.png", video("frames", "intro").stdout)
                self.assertIn("--frames 3", open(log).read())

                comp = os.path.join(root, "video/intro/comp")
                open(os.path.join(comp, "broken"), "w").close()
                self.assertIn("검사에 걸렸다", video("render", "intro", ok=False).stderr)
                self.assertNotIn("hf 1 render", open(log).read(), "검사에 걸리면 렌더하지 않는다")
                os.remove(os.path.join(comp, "broken"))
                out = video("render", "intro", "--draft").stdout
                placed = f"{game['dir']}/intro.{game['ext']}"
                self.assertIn(f"intro: {placed} — 7.5초", out)
                self.assertIn("초안 화질", out)
                self.assertEqual(open(os.path.join(root, placed)).read(), "converted\n")
                last = open(log).read().strip().split("\n")[-2:]
                self.assertTrue(last[0].endswith("renders/intro.mp4 --quality draft"), last[0])
                self.assertIn(" ".join(game["convert"]), last[1])
                self.assertIn(f"놓임 {placed} (초안)", video("status").stdout)

                video("cuts", "intro", "-", stdin="3 | 제목\n")
                self.assertIn("컷 표 승인 대기", video("status").stdout, "표가 바뀌면 다시 본다")

                video("new", "trailer", "--for", "page", "--size", "square", "페이지에 거는 것")
                video("cuts", "trailer", "-", stdin="3 | 제목\n")
                video("approve", "trailer")
                video("compose", "trailer")
                self.assertIn("docs/video/trailer.mp4", video("render", "trailer").stdout)
                self.assertEqual(open(os.path.join(root, "docs/video/trailer.mp4")).read(), "mp4\n", "게임 밖 영상은 바꾸지 않는다")
                self.assertIn("--resolution square", open(log).read())
                self.assertTrue(open(log).read().strip().endswith("--quality standard"))

                cfg["video"]["game"] = {"dir": ""}
                json.dump(cfg, open(os.path.join(root, "kit.config.json"), "w"))
                video("approve", "intro")
                self.assertIn("video.game 가 덜 채워졌다", video("render", "intro", ok=False).stderr)
                cfg["video"]["ffmpeg"] = os.path.join(root, "no-ffmpeg")
                json.dump(cfg, open(os.path.join(root, "kit.config.json"), "w"))
                self.assertIn("no-ffmpeg 가 없다", video("check", ok=False).stderr)

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
        self.assertIn("<h2>규칙 &lt;b&gt;</h2>", chart, "flow 가 없으면 GDD 절마다 단계 하나")
        self.assertIn("<em>1/5</em>", chart, "기능 칸은 GDD 표의 상태를 센다")
        stage = open(os.path.join(root, "docs/board/stage-1.html"), encoding="utf-8").read()
        self.assertIn("<code>BAL.PLAYER.HP</code>", stage)
        self.assertIn("사이클 01 — coins", stage, "그 단계를 건드린 사이클이 검증 칸에 선다")
        page = open(os.path.join(root, "docs/board/log.html"), encoding="utf-8").read()
        self.assertIn("<title>게임 기록</title>", page)
        self.assertIn("<h3>4 규칙 &lt;b&gt;</h3>", page, "문서의 글자는 그대로 글자로")
        self.assertIn('href="#c01" title="동전을 줍는다">01·T1</a>', page)
        self.assertIn("<b>D1</b> 동전의 값 (지금 — 5)<small>기획 · ", page)
        self.assertIn("<blockquote>7 로 가자 → 아니 5</blockquote>", page)
        self.assertIn("권함 ②</summary><p>① 5 ② 7</p>", page)
        self.assertIn('<blockquote class="wait">답을 기다린다</blockquote>', page)
        self.assertIn("동전을 &lt;줍게&gt; 하자", page)
        self.assertIn("<h4>1차</h4>", page)
        self.assertIn("막힘: 소리가 없다", page)
        self.assertIn("답 없는 결정 1", run(BOARD, root).stdout)
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
        self.assertIn("docs/cycle/02-shop.md", run(CYCLE, root, "new", "shop", "상점").stdout)
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
