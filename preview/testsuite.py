#!/usr/bin/env python3
"""Make a local test suite from the pages you saved from AO3.

    python3 preview/testsuite.py

Writes, inside "source pages/" (which holds real data and stays out of git):
  index.html          a list of the saved pages, to open in the browser and click through
  styles/*.user.css   Stylus styles for those pages: the userstyle, and each skin as a userstyle

Run it again after changing the userstyle or a skin, then paste the files you want into Stylus.
"""
import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "source pages"
STYLES = SOURCE / "styles"
LOCAL = '@-moz-document url-prefix("file:///")'
SKINS = ["light", "dark", "slate", "paper", "contrast"]

KINDS = {"works-index": "Works list", "bookmarks-index": "Bookmarks list", "series-index": "Series list",
         "collections-index": "Collections list", "subscriptions-index": "Subscriptions", "fandoms-index": "Fandom index",
         "chapters-show": "A work (one chapter)", "works-show": "A work", "works-navigate": "Chapter index",
         "works-search": "Search form", "series-show": "A series"}


def userstyle():
    css = (ROOT / "archive-neue.user.css").read_text()
    css = re.sub(r"^@-moz-document[^{]*\{", LOCAL + " {", css, count=1, flags=re.M)
    css = re.sub(r"^(@name\s+).*$", r"\1Archive Neue (local test)", css, count=1, flags=re.M)
    css = re.sub(r"^(@namespace\s+).*$", r"\1local.archive-neue.test", css, count=1, flags=re.M)
    css = re.sub(r"^@updateURL.*\n", "", css, count=1, flags=re.M)
    return css


def skin(name):
    body = (ROOT / "skin" / f"archive-neue-skin-{name}.css").read_text()
    return ("/* ==UserStyle==\n"
            f"@name        Archive Neue skin, {name} (local test)\n"
            f"@namespace   local.archive-neue-skin-{name}.test\n"
            "@version     test\n"
            "@description The AO3 skin CSS as a userstyle, for the saved pages only (any width, like the skin's blank Media setting)\n"
            "@license     MIT\n"
            "==/UserStyle== */\n\n" + LOCAL + " {\n" + body + "\n}\n")


def page_entry(page):
    text = page.read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", text, re.S)
    title = re.sub(r"\s*[|_\[-]\s*(Archive of Our Own)\]?\s*$", "", html.unescape(title.group(1)).strip()) if title else page.name
    main = re.search(r'<div id="main" class="([^"]*)"', text)
    kind = "Page"
    for c in (main.group(1).split() if main else []):
        if c in KINDS:
            kind = KINDS[c]
            break
    return kind, title, page.name


def index(pages):
    rows = "".join(f'<li><a href="{html.escape(name)}">{html.escape(title)}</a> <span>{kind}</span></li>'
                   for kind, title, name in sorted(pages))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Archive Neue test pages</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem}}
li{{margin:.35rem 0}}li span{{color:#777;font-size:.85rem;margin-left:.5rem}}code{{background:#eee;padding:0 .25rem}}</style></head><body>
<h1>Archive Neue test pages</h1>
<p>Saved AO3 pages, for trying the userstyle and the skins offline. These hold real names and fanworks: keep them private.</p>
<ol><li>In Chrome, open the Stylus extension's details and turn on <b>Allow access to file URLs</b> (once).</li>
<li>Paste one file from <code>styles/</code> into Stylus as a new style: <code>archive-neue-local-test.user.css</code> is the userstyle;
<code>skin-*.user.css</code> are the skins. Keep only one on at a time.</li>
<li>Open a page below. Resize the window to see other widths.</li></ol>
<h2>Pages</h2><ul>{rows}</ul>
<p>Not covered: menus and forms that need AO3's scripts, and any page not saved here.</p></body></html>"""


def main():
    pages = [page_entry(p) for p in sorted(SOURCE.glob("*.html")) if p.name != "index.html"]
    STYLES.mkdir(exist_ok=True)
    (STYLES / "archive-neue-local-test.user.css").write_text(userstyle())
    for name in SKINS:
        (STYLES / f"skin-{name}.user.css").write_text(skin(name))
    (SOURCE / "index.html").write_text(index(pages), encoding="utf-8")
    print(f"{len(pages)} pages, {1 + len(SKINS)} style files in {STYLES}")


if __name__ == "__main__":
    main()
