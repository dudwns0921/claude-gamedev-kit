#!/usr/bin/env python3
"""눈으로 고르는 결정을 묻는 시트 — 물음 하나에 그림 한 장. 물음 · 보기와, 견줄 그림들을 한 장에 놓는다.

  python3 sheet.py <물음들.json> [--name <이름>] [--out <폴더>]

화면 · 자세 · 쥠처럼 보고 고르는 결정은 글과 그림을 따로 주면 (특히 폰에서) 고르지 못한다. 그래서 한 장 안에:
맨 위에 번호 붙은 물음과 보기(한 줄 대가 · 권하는 쪽), 그 아래 보기마다 대상 둘레를 크게 자른 그림을 라벨과 함께 나란히.
물음이 여럿이면 번호 매긴 장 여럿이 나온다 — 사용자는 "1 은 ⓑ, 2 는 지금" 처럼 번호로 답한다.

물음들.json (경로는 게임 루트 기준):
  [{"id": "D3", "question": "활을 쥔 손의 자리",
    "options": [{"mark": "ⓐ", "text": "지금 그대로 — 고칠 것 없음"},
                {"mark": "ⓑ", "text": "손목을 세운다 — 클립 둘을 다시 잰다", "recommend": true}],
    "images": [{"label": "지금", "path": "shots/now.png", "crop": [420, 180, 600, 600]},
               {"label": "ⓑ 바꾼 것", "path": "shots/b.png", "crop": [420, 180, 600, 600]}]}]
  id 가 없으면 차례대로 1, 2, … 다. crop 은 [x, y, 너비, 높이] 픽셀 — 없으면 그림 전체. 자르는 그림은 png 여야 한다.

<폴더>/<이름>-<번호>.html 이 나온다 (그림이 안에 들어 있어 파일 하나로 열린다). 이 기기에 Chrome 계열 브라우저가 있으면
같은 이름의 .png 도 찍는다 — 사용자에게 건네는 것은 그 그림이다. 브라우저의 자리는 kit.config.json 의 cycle.browser.
폴더는 기본 docs/cycle/sheets.
"""
import base64
import html
import json
import mimetypes
import os
import re
import shutil
import struct
import subprocess
import sys

CONFIG_NAME = "kit.config.json"
OUT = os.path.join("docs", "cycle", "sheets")
WIDTH = 1080  # 폰 화면 한 폭에 읽히는 너비
BROWSERS = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "google-chrome", "chromium", "chromium-browser", "chrome", "msedge")
PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
html {{ background: #fff; }}
body {{ margin: 0; padding: 28px; width: {inner}px; font: 30px/1.4 -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif; color: #111; }}
h1 {{ font-size: 44px; line-height: 1.25; margin: 0 0 18px; }}
ul {{ list-style: none; margin: 0 0 24px; padding: 0; }}
li {{ padding: 10px 14px; margin-bottom: 8px; border: 2px solid #ccc; border-radius: 10px; }}
li.pick {{ border-color: #111; background: #f2f2f2; }}
li b {{ margin-right: 10px; }}
li small {{ font-size: 24px; font-weight: 700; margin-left: 10px; }}
.row {{ display: flex; flex-wrap: wrap; gap: 14px; }}
figure {{ margin: 0; flex: 1 1 {cell}px; min-width: 0; }}
figcaption {{ font-weight: 700; padding: 6px 0; }}
.crop {{ position: relative; overflow: hidden; border: 2px solid #111; }}
.crop img {{ position: absolute; display: block; max-width: none; }}
figure > img {{ display: block; width: 100%; border: 2px solid #111; box-sizing: border-box; }}
</style></head><body>
<h1>{title}</h1>
<ul>{options}</ul>
<div class="row">{images}</div>
<script>addEventListener("load", function () {{ document.documentElement.setAttribute("data-h", Math.ceil(document.body.getBoundingClientRect().height)); }});</script>
</body></html>
"""

ROOT = ""


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


def png_size(data):
    return struct.unpack(">II", data[16:24]) if data[:8] == b"\x89PNG\r\n\x1a\n" else None


def figure(where, img):
    path = os.path.join(ROOT, img.get("path", ""))
    if not os.path.isfile(path):
        sys.exit(f"{where}: 그림이 없다 — {img.get('path')} (게임 루트 기준 경로)")
    data = open(path, "rb").read()
    src = f"data:{mimetypes.guess_type(path)[0] or 'image/png'};base64,{base64.b64encode(data).decode()}"
    label = f"<figcaption>{html.escape(img.get('label', ''))}</figcaption>"
    crop, size = img.get("crop"), png_size(data)
    if not crop:
        return f"<figure>{label}<img src=\"{src}\"></figure>"
    if not size:
        sys.exit(f"{where}: {img['path']} 는 png 가 아니라 자를 수 없다 — crop 을 빼거나 png 로 준다")
    try:
        x, y, w, h = (float(v) for v in crop)
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > size[0] or y + h > size[1]:
            raise ValueError
    except (TypeError, ValueError):
        sys.exit(f"{where}: crop 은 그림({size[0]} × {size[1]}) 안의 [x, y, 너비, 높이] 다 — {crop}")
    pct = lambda v, of: f"{100 * v / of:.4f}%"  # 틀의 너비에 견준 값 — 틀이 어느 폭이 되든 같은 자리가 보인다
    return (f"<figure>{label}<div class=\"crop\" style=\"aspect-ratio: {w:g} / {h:g}\">"
            f"<img src=\"{src}\" style=\"width: {pct(size[0], w)}; left: -{pct(x, w)}; top: -{pct(y, h)}\"></div></figure>")


def page(n, q):
    where = f"물음 {n}"
    if not isinstance(q, dict) or not q.get("question") or not q.get("images"):
        sys.exit(f"{where}: question 과 images 가 있어야 한다")
    options = "".join(
        f"<li class=\"{'pick' if o.get('recommend') else ''}\"><b>{html.escape(str(o.get('mark', '')))}</b>{html.escape(str(o.get('text', '')))}"
        + ("<small>← 권함</small>" if o.get("recommend") else "") + "</li>" for o in q.get("options", []))
    images = q["images"]
    return PAGE.format(title=html.escape(f"{q.get('id', n)}. {q['question']}"), options=options, inner=WIDTH - 56,
                       cell=(WIDTH - 56 - 14 * (min(len(images), 3) - 1)) // min(len(images), 3) - 1,
                       images="".join(figure(where, i) for i in images))


def browser():
    cfg = json.load(open(os.path.join(ROOT, CONFIG_NAME), encoding="utf-8")).get("cycle", {}).get("browser")
    for name in ([cfg] if cfg else BROWSERS):
        found = name if os.path.isfile(name) else shutil.which(name)
        if found:
            return found
    return None


def shoot(tool, page_path, out):
    """쪽을 그 높이만큼 찍는다. 높이는 쪽이 스스로 재어 적은 것을 먼저 읽는다."""
    url, run = "file://" + page_path, lambda *a: subprocess.run([tool, "--headless", "--disable-gpu", "--hide-scrollbars", *a], capture_output=True, text=True, timeout=90)
    try:
        m = re.search(r'data-h="(\d+)"', run(f"--window-size={WIDTH},800", "--dump-dom", url).stdout)
        if not m:
            return False
        if os.path.exists(out):
            os.remove(out)
        run(f"--window-size={WIDTH},{m.group(1)}", f"--screenshot={out}", url)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return os.path.exists(out)


def main():
    args, opts = sys.argv[1:], {}
    for flag in ("--root", "--name", "--out"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__)
    global ROOT
    ROOT = os.path.abspath(opts["--root"]) if "--root" in opts else find_root(os.getcwd())
    try:
        asked = json.load(open(args[0], encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"{args[0]}: 읽지 못했다 — {e}")
    if not isinstance(asked, list) or not asked:
        sys.exit(f"{args[0]}: 물음의 목록이어야 한다 ([{{...}}, ...])")
    name = opts.get("--name", "sheet")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        sys.exit(f"이름은 영문 · 숫자 · 붙임표 · 밑줄이다: {name!r}")
    pages = [page(n, q) for n, q in enumerate(asked, 1)]  # 하나라도 틀리면 아무것도 쓰지 않는다
    folder = os.path.join(ROOT, opts.get("--out", OUT))
    os.makedirs(folder, exist_ok=True)
    tool = browser()
    for n, text in enumerate(pages, 1):
        path = os.path.join(folder, f"{name}-{n}.html")
        open(path, "w", encoding="utf-8").write(text)
        shot = os.path.splitext(path)[0] + ".png"
        print(os.path.relpath(shot if tool and shoot(tool, path, shot) else path, ROOT))
    if not tool:
        print("브라우저가 없어 그림으로 찍지 못했다 — 쪽(.html)을 건넨다. Chrome 계열을 깔거나 kit.config.json 의 cycle.browser 에 자리를 적는다")


if __name__ == "__main__":
    main()
