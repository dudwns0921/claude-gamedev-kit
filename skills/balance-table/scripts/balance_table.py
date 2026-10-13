#!/usr/bin/env python3
"""Balance table — ties the Excel table (xlsx) to the balance value file in code.

  python3 balance_table.py export          (re)make the table from the values in code
  python3 balance_table.py bake            write the table's values into the code
  python3 balance_table.py check           if the two differ, print the differing lines and exit 1
  python3 balance_table.py serve [port]    serve the table as JSON (for engines that cannot read disk, default 8765)

The table is where balancing happens. Once a value is settled, bake it into the code — a deploy build does not read the table, only the baked values.
After baking, /gamedev-kit:gdd-sync to-gdd.

Which file is the value file and what one line looks like is in "balance-table" in the project root's kit.config.json.
Runs with no external packages. An xlsx is a zip of XML, so the standard library reads and writes it.
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
    "code": "",                    # the balance value file (relative to the root)
    "table": "data/balance.xlsx",
    # One value line. Five groups: (before) (name) (between) (number) (after). Only lines set by a single number go into the table
    "line": "",
    "doc_prefix": "",              # the prefix of the description comment directly above a value line (`##` · `---` · `///`)
    "comment": "",                 # the prefix of an end-of-line comment (`#` · `--` · `//`)
}

MARK_RE = re.compile(r"GDD:\s*([A-Z][A-Z0-9_.]*)")
# The header row is for people — reading goes by column (A name · B value), so a table with the older Korean header row reads the same
HEADER = ["Name", "Value", "Code value", "Group", "GDD ID", "Note"]
WIDTHS = [30, 10, 10, 12, 30, 90]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

ROOT = ""
CFG = dict(DEFAULTS)
CODE = ""
TABLE = ""
LINE_RE = None


def find_root(start):
    """Walk up from the current folder to the one holding kit.config.json. The tools live in the plugin; the game lives elsewhere."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            sys.exit(f"{CONFIG_NAME} not found — run this inside a game repository, after /gamedev-kit:init")
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
            sys.exit(f"{SECTION}.{key} in {CONFIG_NAME} is empty — install the engine config with /gamedev-kit:init")
    CODE = os.path.join(ROOT, CFG["code"])
    TABLE = os.path.join(ROOT, CFG["table"])
    LINE_RE = re.compile(CFG["line"])
    if LINE_RE.groups != 5:
        sys.exit(f"{SECTION}.line must have five groups: (before)(name)(between)(number)(after)")


def read_code():
    """(name, value string, GDD ID, description) from the value file, in line order."""
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


# ── Write ─────────────────────────────────────────────────────────────────────

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
        # 0 normal · 1 header · 2 value (the cell to edit, yellow fill) · 3 code value (grey text)
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
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))  # same values, same file — git stays quiet
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text)


# ── Read ─────────────────────────────────────────────────────────────────────

def read_table():
    """{name: value string} from the table. Also reads files saved by Excel (shared strings · phonetic runs)."""
    with zipfile.ZipFile(TABLE) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{NS}si"):
                # <rPh> is the phonetic run that Korean · Japanese Excel attaches — not text
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
    """The table's number in the form to write into code. A value that was an integer stays an integer; a float keeps its decimal point."""
    number = float(text)
    if "." not in was:
        if number != int(number):
            raise ValueError(f"decimal {text} for an integer value")
        return str(int(number))
    out = f"{round(number, 6):.6f}".rstrip("0")
    return out + "0" if out.endswith(".") else out


def diff():
    """([(name, code value, table value)] — in the table and different from the code, [names only in the code])."""
    table = read_table()
    changed, unknown, missing = [], set(table), []
    for name, value, _gdd, _note in read_code():
        unknown.discard(name)
        if name not in table:
            missing.append(name)
            continue
        try:
            new = as_code(table[name], value)
        except ValueError as e:
            sys.exit(f"{name}: not a number — {e}")
        if float(new) != float(value):
            changed.append((name, value, new))
    for name in sorted(unknown):
        print(f"  only in the table (ignored): {name}")
    return changed, missing


def bake():
    changed = {name: new for name, _old, new in diff()[0]}
    lines = open(CODE, encoding="utf-8").read().split("\n")
    for i, line in enumerate(lines):
        m = LINE_RE.match(line)
        if m and m.group(2) in changed:
            lines[i] = m.group(1) + m.group(2) + m.group(3) + changed[m.group(2)] + m.group(5)
            print(f"  {m.group(2)}: {m.group(4)} → {changed[m.group(2)]}")
    open(CODE, "w", encoding="utf-8").write("\n".join(lines))
    write_table(read_code())  # the Code value column takes the new values
    print(f"Baked {len(changed)}. Next: /gamedev-kit:gdd-sync to-gdd" if changed else "No values changed")


# ── Serve ───────────────────────────────────────────────────────────────────

def snapshot():
    """{"stamp": when the table was saved, "values": {name: number}}. None if it cannot be read because Excel is mid-save."""
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
            pass  # cells that are not numbers are skipped
    return {"stamp": stamp, "values": values}


def serve(port):
    """Serve the table so a running game can fetch it. Open only on this machine (127.0.0.1)."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # some clients put the whole address on the request line (GET http://127.0.0.1:8765/balance)
            if urlparse(self.path).path.rstrip("/") != "/balance":
                snap, status = {"error": "only /balance exists"}, 404
            else:
                snap = snapshot()
                snap, status = (snap, 200) if snap else ({"error": "could not read the table"}, 503)
            body = json.dumps(snap).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass  # logging a request every 0.5 s would flood the terminal

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"http://127.0.0.1:{server.server_address[1]}/balance — {os.path.relpath(TABLE, ROOT)} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    args = [a for a in sys.argv[1:]]
    root = None
    if "--root" in args:  # for tests
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
        print(f"{os.path.relpath(TABLE, ROOT)} — {len(rows)} lines")
    elif cmd == "bake":
        bake()
    elif cmd == "check":
        changed, missing = diff()
        for name, old, new in changed:
            print(f"  {name}: code {old} · table {new}")
        for name in missing:  # values new in the code — the table neither shows nor edits them
            print(f"  only in the code (not in the table): {name}")
        if changed:
            sys.exit("The table and the code differ — balance_table.py bake")
        print("The table and the code match" + (f" — but {len(missing)} value(s) are only in the code: balance_table.py export puts them in the table" if missing else ""))
    else:
        serve(int(args[1]) if len(args) > 1 else 8765)


if __name__ == "__main__":
    main()
