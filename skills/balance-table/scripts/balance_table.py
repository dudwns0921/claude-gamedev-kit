#!/usr/bin/env python3
"""밸런스 표 — 엑셀 표(xlsx)와 코드의 밸런스 값 파일을 잇는다.

  python3 balance_table.py export          코드의 값으로 표를 (다시) 만든다
  python3 balance_table.py bake            표의 값을 코드에 적는다
  python3 balance_table.py check           둘이 다르면 다른 줄을 적고 1 로 끝난다
  python3 balance_table.py serve [포트]    표를 JSON 으로 내준다 (디스크를 못 읽는 엔진용, 기본 8765)

표가 밸런싱하는 자리다. 값이 정해지면 bake 로 코드에 굽는다 — 배포 빌드는 표를 읽지 않고 구운 값만 쓴다.
구운 뒤에는 /gamedev-kit:gdd-sync to-gdd.

어느 파일이 값 파일이고 한 줄이 어떻게 생겼는지는 프로젝트 루트 kit.config.json 의 "balance-table" 에 있다.
외부 패키지 없이 돈다. xlsx 는 XML 을 담은 zip 이라 표준 라이브러리로 읽고 쓴다.
"""
import json
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

CONFIG_NAME = "kit.config.json"
SECTION = "balance-table"
DEFAULTS = {
    "code": "",                    # 밸런스 값 파일 (루트 기준)
    "table": "data/balance.xlsx",
    # 값 한 줄. 그룹 다섯: (앞) (이름) (사이) (숫자) (뒤). 숫자 하나로 정해지는 줄만 표에 올린다
    "line": "",
    "doc_prefix": "",              # 값 줄 바로 위 설명 주석의 머리 (`##` · `---` · `///`)
    "comment": "",                 # 줄 끝 주석의 머리 (`#` · `--` · `//`)
}

MARK_RE = re.compile(r"GDD:\s*([A-Z][A-Z0-9_.]*)")
HEADER = ["이름", "값", "코드값", "분류", "GDD ID", "설명"]
WIDTHS = [30, 10, 10, 12, 30, 90]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

ROOT = ""
CFG = dict(DEFAULTS)
CODE = ""
TABLE = ""
LINE_RE = None


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
    global ROOT, CFG, CODE, TABLE, LINE_RE
    ROOT = os.path.abspath(root) if root else find_root(os.getcwd())
    CFG = dict(DEFAULTS)
    path = os.path.join(ROOT, CONFIG_NAME)
    if os.path.exists(path):
        section = json.load(open(path, encoding="utf-8")).get(SECTION, {})
        CFG.update({k: v for k, v in section.items() if k in DEFAULTS})
    for key in ("code", "line", "comment"):
        if not CFG[key]:
            sys.exit(f"{CONFIG_NAME} 의 {SECTION}.{key} 가 비어 있다 — /gamedev-kit:init 으로 엔진 설정을 깐다")
    CODE = os.path.join(ROOT, CFG["code"])
    TABLE = os.path.join(ROOT, CFG["table"])
    LINE_RE = re.compile(CFG["line"])
    if LINE_RE.groups != 5:
        sys.exit(f"{SECTION}.line 은 그룹이 다섯이어야 한다: (앞)(이름)(사이)(숫자)(뒤)")


def read_code():
    """값 파일에서 (이름, 값 문자열, GDD ID, 설명) 을 줄 순서대로."""
    rows, doc = [], []
    for line in open(CODE, encoding="utf-8").read().split("\n"):
        if CFG["doc_prefix"] and line.strip().startswith(CFG["doc_prefix"]):
            doc.append(line.strip()[len(CFG["doc_prefix"]):].strip())
            continue
        m = LINE_RE.match(line)
        if m:
            mark = MARK_RE.search(m.group(5))
            gdd = mark.group(1) if mark else ""
            note = " ".join(doc)
            if not note and CFG["comment"] in m.group(5) and not mark:
                note = m.group(5).split(CFG["comment"], 1)[1].strip()
            rows.append((m.group(2), m.group(4), gdd, note))
        doc = []
    return rows


def group_of(name, gdd):
    return gdd.split(".")[1] if gdd.count(".") >= 2 else name.split("_")[0]


# ── 쓰기 ─────────────────────────────────────────────────────────────────────

def col(i):
    return "ABCDEFGHIJ"[i]


def cell(ref, value, style=0, number=False):
    if number:
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'


def write_table(rows):
    out = ['<row r="1">' + "".join(cell(f"{col(i)}1", h, 1) for i, h in enumerate(HEADER)) + "</row>"]
    for r, (name, value, gdd, note) in enumerate(rows, 2):
        out.append(f'<row r="{r}">'
                   + cell(f"A{r}", name)
                   + cell(f"B{r}", value, 2, number=True)
                   + cell(f"C{r}", value, 3, number=True)
                   + cell(f"D{r}", group_of(name, gdd))
                   + cell(f"E{r}", gdd)
                   + cell(f"F{r}", note)
                   + "</row>")
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(WIDTHS))
    last = len(rows) + 1
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    files = {
        "[Content_Types].xml": head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>",
        "_rels/.rels": head + f'<Relationships xmlns="{pkg}">'
        f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": head + f'<workbook xmlns="{main}" xmlns:r="{rel}">'
        '<sheets><sheet name="balance" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": head + f'<Relationships xmlns="{pkg}">'
        f'<Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/sheet1.xml"/>'
        f'<Relationship Id="rId2" Type="{rel}/styles" Target="styles.xml"/></Relationships>',
        # 0 보통 · 1 머리글 · 2 값(고치는 칸, 노란 바탕) · 3 코드값(회색 글자)
        "xl/styles.xml": head + f'<styleSheet xmlns="{main}">'
        '<fonts count="3"><font><sz val="12"/><name val="Calibri"/></font>'
        '<font><b/><sz val="12"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        '<font><sz val="12"/><color rgb="FF8A8A8A"/><name val="Calibri"/></font></fonts>'
        '<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF17120E"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/>'
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
        "</styleSheet>",
        "xl/worksheets/sheet1.xml": head + f'<worksheet xmlns="{main}">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        f"</sheetView></sheetViews><cols>{cols}</cols><sheetData>{''.join(out)}</sheetData>"
        f'<autoFilter ref="A1:F{last}"/></worksheet>',
    }
    os.makedirs(os.path.dirname(TABLE), exist_ok=True)
    with zipfile.ZipFile(TABLE, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))  # 같은 값이면 같은 파일 — git 이 조용하다
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text)


# ── 읽기 ─────────────────────────────────────────────────────────────────────

def read_table():
    """표에서 {이름: 값 문자열}. 엑셀이 저장한 파일(공유 문자열 · 발음 표기)도 읽는다."""
    with zipfile.ZipFile(TABLE) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{NS}si"):
                # <rPh> 는 한글 · 일본어 엑셀이 붙이는 발음 표기다 — 글자가 아니다
                shared.append("".join(t.text or "" for t in si.iter(f"{NS}t") if not _in_phonetic(si, t)))
        sheets = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        sheet = ET.fromstring(z.read(sheets[0]))
    values = {}
    for row in sheet.iter(f"{NS}row"):
        cells = {}
        for c in row.findall(f"{NS}c"):
            letter = re.match(r"[A-Z]+", c.get("r", "")).group(0)
            kind = c.get("t", "n")
            v = c.find(f"{NS}v")
            if kind == "s" and v is not None:
                cells[letter] = shared[int(v.text)]
            elif kind == "inlineStr":
                cells[letter] = "".join(t.text or "" for t in c.iter(f"{NS}t"))
            elif v is not None:
                cells[letter] = v.text or ""
        name = cells.get("A", "").strip()
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", name) and "B" in cells:
            values[name] = cells["B"].strip()
    return values


def _in_phonetic(si, t):
    return any(t in list(ph.iter()) for ph in si.iter(f"{NS}rPh"))


def as_code(text, was):
    """표의 숫자를 코드에 적을 모양으로. 정수였던 값은 정수로, 실수였던 값은 소수점을 남긴다."""
    number = float(text)
    if "." not in was:
        if number != int(number):
            raise ValueError(f"정수 값에 소수 {text}")
        return str(int(number))
    out = f"{round(number, 6):.6f}".rstrip("0")
    return out + "0" if out.endswith(".") else out


def diff():
    """[(이름, 코드값, 표값)] — 표에 있고 코드와 다른 것."""
    table = read_table()
    changed, unknown = [], set(table)
    for name, value, _gdd, _note in read_code():
        unknown.discard(name)
        if name not in table:
            continue
        try:
            new = as_code(table[name], value)
        except ValueError as e:
            sys.exit(f"{name}: 숫자가 아니다 — {e}")
        if float(new) != float(value):
            changed.append((name, value, new))
    for name in sorted(unknown):
        print(f"  표에만 있다 (무시): {name}")
    return changed


def bake():
    changed = {name: new for name, _old, new in diff()}
    lines = open(CODE, encoding="utf-8").read().split("\n")
    for i, line in enumerate(lines):
        m = LINE_RE.match(line)
        if m and m.group(2) in changed:
            lines[i] = m.group(1) + m.group(2) + m.group(3) + changed[m.group(2)] + m.group(5)
            print(f"  {m.group(2)}: {m.group(4)} → {changed[m.group(2)]}")
    open(CODE, "w", encoding="utf-8").write("\n".join(lines))
    write_table(read_code())  # 코드값 열을 새 값으로
    print(f"{len(changed)}개를 구웠다. 이어서 /gamedev-kit:gdd-sync to-gdd" if changed else "바뀐 값이 없다")


# ── 내주기 ───────────────────────────────────────────────────────────────────

def snapshot():
    """{"stamp": 표가 저장된 시각, "values": {이름: 숫자}}. 엑셀이 저장하는 도중이라 못 읽으면 None."""
    try:
        stamp = str(os.stat(TABLE).st_mtime_ns)
        table = read_table()
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError, IndexError):
        return None
    values = {}
    for name, text in table.items():
        try:
            values[name] = float(text)
        except ValueError:
            pass  # 숫자가 아닌 칸은 넘긴다
    return {"stamp": stamp, "values": values}


def serve(port):
    """실행 중인 게임이 표를 가져갈 수 있게 내준다. 이 컴퓨터 안에서만 열린다 (127.0.0.1)."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            snap = snapshot() if self.path.split("?")[0] == "/balance" else None
            body = json.dumps(snap or {"error": "표를 읽지 못했다"}).encode("utf-8")
            self.send_response(200 if snap else 503)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass  # 0.5초마다 오는 요청을 다 적으면 터미널이 넘친다

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"http://127.0.0.1:{server.server_address[1]}/balance — {os.path.relpath(TABLE, ROOT)} (Ctrl+C 로 끈다)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    args = [a for a in sys.argv[1:]]
    root = None
    if "--root" in args:  # 테스트용
        i = args.index("--root")
        root = args[i + 1]
        del args[i:i + 2]
    cmd = args[0] if args else ""
    if cmd not in ("export", "bake", "check", "serve"):
        sys.exit(__doc__)
    setup(root)
    if cmd == "export":
        rows = read_code()
        write_table(rows)
        print(f"{os.path.relpath(TABLE, ROOT)} — {len(rows)}줄")
    elif cmd == "bake":
        bake()
    elif cmd == "check":
        changed = diff()
        for name, old, new in changed:
            print(f"  {name}: 코드 {old} · 표 {new}")
        if changed:
            sys.exit("표와 코드가 다르다 — balance_table.py bake")
        print("표와 코드가 같다")
    else:
        serve(int(args[1]) if len(args) > 1 else 8765)


if __name__ == "__main__":
    main()
