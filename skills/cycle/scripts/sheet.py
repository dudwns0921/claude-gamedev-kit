#!/usr/bin/env python3
"""A sheet for asking decisions that are chosen by eye — one picture per question. Puts the question · its options and the images to compare on one sheet.

  python3 sheet.py <questions.json> [--name <name>] [--out <folder>]

A decision made by looking — a screen, a pose, a grip — cannot be chosen (least of all on a phone) when the text and the images come apart. So on one sheet:
the numbered question and its options at the top (one-line cost · the recommended one), and below, one image per option cropped large around the subject, side by side with labels.
Several questions give several numbered sheets — the user answers by number, like "1 is ⓑ, 2 as it is".

questions.json (paths are relative to the game root):
  [{"id": "D3", "question": "Where the bow hand sits",
    "options": [{"mark": "ⓐ", "text": "As it is — nothing to fix"},
                {"mark": "ⓑ", "text": "Raise the wrist — two clips to re-time", "recommend": true}],
    "images": [{"label": "Now", "path": "shots/now.png", "crop": [420, 180, 600, 600]},
               {"label": "ⓑ changed", "path": "shots/b.png", "crop": [420, 180, 600, 600]}]}]
  Without an id they are 1, 2, … in order. crop is [x, y, width, height] in pixels — the whole image if absent. An image to crop must be a png.

Writes <folder>/<name>-<number>.html (the images are embedded, so it opens as one file). If this machine has a Chrome-family browser,
a .png of the same name is taken too — that picture is what goes to the user. The browser's path is cycle.browser in kit.config.json.
The folder defaults to docs/cycle/sheets.
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
WIDTH = 1080  # a width that reads across one phone screen
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
    """Walk up from the current folder to the one holding kit.config.json. The tools live in the plugin; the game lives elsewhere."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            sys.exit(f"{CONFIG_NAME} not found — run this inside a game repository, after /gamedev-kit:init")
        d = up


def png_size(data):
    return struct.unpack(">II", data[16:24]) if data[:8] == b"\x89PNG\r\n\x1a\n" else None


def figure(where, img):
    path = os.path.join(ROOT, img.get("path", ""))
    if not os.path.isfile(path):
        sys.exit(f"{where}: image not found — {img.get('path')} (path relative to the game root)")
    data = open(path, "rb").read()
    src = f"data:{mimetypes.guess_type(path)[0] or 'image/png'};base64,{base64.b64encode(data).decode()}"
    label = f"<figcaption>{html.escape(img.get('label', ''))}</figcaption>"
    crop, size = img.get("crop"), png_size(data)
    if not crop:
        return f"<figure>{label}<img src=\"{src}\"></figure>"
    if not size:
        sys.exit(f"{where}: {img['path']} is not a png and cannot be cropped — drop crop or give a png")
    try:
        x, y, w, h = (float(v) for v in crop)
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > size[0] or y + h > size[1]:
            raise ValueError
    except (TypeError, ValueError):
        sys.exit(f"{where}: crop is [x, y, width, height] inside the image ({size[0]} × {size[1]}) — {crop}")
    pct = lambda v, of: f"{100 * v / of:.4f}%"  # relative to the frame's width — the same spot shows whatever width the frame ends up
    return (f"<figure>{label}<div class=\"crop\" style=\"aspect-ratio: {w:g} / {h:g}\">"
            f"<img src=\"{src}\" style=\"width: {pct(size[0], w)}; left: -{pct(x, w)}; top: -{pct(y, h)}\"></div></figure>")


def page(n, q):
    where = f"question {n}"
    if not isinstance(q, dict) or not q.get("question") or not q.get("images"):
        sys.exit(f"{where}: question and images are required")
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
    """Shoots the page at its full height. The height is read first from what the page measured and wrote itself."""
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
        sys.exit(f"{args[0]}: could not read — {e}")
    if not isinstance(asked, list) or not asked:
        sys.exit(f"{args[0]}: must be a list of questions ([{{...}}, ...])")
    name = opts.get("--name", "sheet")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        sys.exit(f"the name is letters · digits · hyphens · underscores: {name!r}")
    pages = [page(n, q) for n, q in enumerate(asked, 1)]  # if any one is wrong, nothing is written
    folder = os.path.join(ROOT, opts.get("--out", OUT))
    os.makedirs(folder, exist_ok=True)
    tool = browser()
    for n, text in enumerate(pages, 1):
        path = os.path.join(folder, f"{name}-{n}.html")
        open(path, "w", encoding="utf-8").write(text)
        shot = os.path.splitext(path)[0] + ".png"
        print(os.path.relpath(shot if tool and shoot(tool, path, shot) else path, ROOT))
    if not tool:
        print("no browser, so no picture was taken — hand over the page (.html). Install a Chrome-family browser or set its path in cycle.browser of kit.config.json")


if __name__ == "__main__":
    main()
