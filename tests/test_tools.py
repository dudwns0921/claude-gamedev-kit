#!/usr/bin/env python3
"""도구 검사 — engines/ 의 엔진 설정마다 임시 프로젝트를 만들어 gdd-sync 와 balance-table 을 끝까지 돌린다.

  python3 tests/test_tools.py

엔진은 필요 없다. 엔진 문법(GDScript · Luau · C#)으로 적힌 값 파일을 도구가 읽고 고치는지만 본다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(KIT, "skills/gdd-sync/scripts/sync_report.py")
TABLE = os.path.join(KIT, "skills/balance-table/scripts/balance_table.py")

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
    "roblox": ("""local Balance = {}
--- 시작 체력
Balance.PLAYER_HP = 100 -- GDD: BAL.PLAYER.HP
Balance.PLAYER_WALK_SPEED = 4.0 -- GDD: BAL.PLAYER.WALK_SPEED
Balance.COIN_VALUE = 5 -- GDD: BAL.COIN.VALUE
Balance.UNMARKED = 2.5 -- 표식 없는 값

local function canPickup() -- GDD: RULE.COIN.PICKUP
	return true
end

Balance.STRAY = 1 -- GDD: BAL.STRAY.ONE
return Balance
""", "canPickup"),
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
        root, _code, table, _rel = self.project("roblox")
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

        open(table, "wb").write(b"PK\x03\x04 broken")
        with self.assertRaises(urllib.error.HTTPError) as e:
            get()
        self.assertEqual(e.exception.code, 503, "읽다 만 파일")

    def test_no_config(self):
        root = tempfile.mkdtemp(prefix="kit-none-")
        self.addCleanup(shutil.rmtree, root, True)
        open(os.path.join(root, "kit.config.json"), "w").write("{}")
        self.assertIn("code_ext", run(REPORT, root, ok=False).stderr)
        self.assertIn("balance-table.code", run(TABLE, root, "check", ok=False).stderr)


if __name__ == "__main__":
    unittest.main(warnings="ignore")
