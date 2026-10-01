"""Build the static GitHub Pages version of BioLex into ./docs (GitHub Pages serves it from main /docs).

The site is the same web app, with the API answered in the browser from
data/seed.json (static/js/localapi.js) because GitHub Pages has no server.

Usage:  python tools/build_pages.py
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"

shutil.rmtree(OUT, ignore_errors=True)
shutil.copytree(ROOT / "static", OUT)
(OUT / "data").mkdir(exist_ok=True)
shutil.copy2(ROOT / "data" / "seed.json", OUT / "data" / "seed.json")

index = OUT / "index.html"
html = index.read_text(encoding="utf-8")
flag = "<script>window.BIOLEX_STATIC = true;</script>\n"
html = html.replace('<script type="module"', flag + '  <script type="module"', 1)
index.write_text(html, encoding="utf-8")
(OUT / ".nojekyll").write_text("", encoding="utf-8")
print(f"Built static site -> {OUT}")
