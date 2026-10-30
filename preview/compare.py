#!/usr/bin/env python3
"""Prove that a CSS clean-up changed nothing: render the saved pages with two versions of a stylesheet and
compare what the browser computes for every element (and its ::before / ::after).

    python3 preview/compare.py userstyle <old.css> [new.css]    all four themes (new defaults to archive-neue.user.css)
    python3 preview/compare.py skin <old.css> <new.css>         two built skin files (e.g. skin/archive-neue-skin-dark.css)

Pages come from "source pages/" (real data: it and everything rendered from it stays out of git).
Prints "identical" or the first differences (element, property, old value, new value).
Same page, three widths. A hover or open-menu state is not covered: it only compares how the page first looks.
"""
import html as htmllib
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "source pages"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WIDTHS = [360, 768, 1440]
THEMES = {"light": 1, "dark": 2, "slate": 3, "paper": 4}

DUMP_JS = r"""
<script>addEventListener('load',()=>setTimeout(()=>{
const names=[...getComputedStyle(document.body)].filter(n=>!n.startsWith('--'));const els={};
const path=e=>{const p=[];for(;e&&e!==document.body;e=e.parentElement){const i=[...e.parentElement.children].indexOf(e);p.unshift(e.tagName.toLowerCase()+i)}return p.join('/')};
const grab=(cs,keys)=>keys.map(k=>cs.getPropertyValue(k)).join('\u0001');
const hash=t=>{let h=2166136261;for(let i=0;i<t.length;i++){h^=t.charCodeAt(i);h=Math.imul(h,16777619)}return (h>>>0).toString(36)+t.length};
const pk=['content','display','position','color','background-color','background-image','width','height','top','right','bottom','left','margin-top','margin-right','margin-bottom','margin-left','border-top-width','border-top-color','font-size','font-weight','float','opacity','transform'];
for(const e of document.body.querySelectorAll('*')){if(/^(SCRIPT|STYLE|NOSCRIPT|LINK|META)$/.test(e.tagName))continue;const p=path(e);
{const cs=getComputedStyle(e);els[p]=hash(grab(cs,names))+'\u0001'+grab(cs,pk)}
for(const ps of ['::before','::after']){const cs=getComputedStyle(e,ps);if(cs.content!=='none'&&cs.content!=='normal')els[p+ps]=hash(grab(cs,pk))+'\u0001'+grab(cs,pk)}}
parent.postMessage(JSON.stringify({names,pk,els}),'*')},1500));</script>"""


def pages():
    return sorted(SOURCE.glob("*.html"))


def userstyle_css(text, theme):
    head, body = text.split("==/UserStyle== */", 1)
    body = re.sub(r"^@-moz-document[^{]*\{", "", body, flags=re.M | re.S, count=1).rstrip()
    body = body[:-1] if body.endswith("}") else body
    imports = "".join(re.findall(r'@import url\("[^"]*"\);', body))
    return imports + f":root{{--theme:{theme};}}" + body.replace(imports, "")


def host(url, width):
    return (f'<!doctype html><html><body style="margin:0"><iframe width="{width}" height="3000" style="border:0" src="{url}">'
            '</iframe><pre id="r"></pre><script>addEventListener("message",e=>{document.getElementById("r").textContent=e.data})'
            '</script></body></html>')


def render(job):
    path, width, tag = job
    hostfile = HERE / "pages" / f"cmp-{tag}.html"
    hostfile.write_text(host(path.resolve().as_uri(), width))
    out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                          f"--user-data-dir={tempfile.mkdtemp()}", "--virtual-time-budget=8000",
                          f"--window-size={max(width, 500)},900", "--dump-dom", hostfile.resolve().as_uri()],
                         capture_output=True, text=True, timeout=300).stdout
    m = re.search(r'<pre id="r">(.*?)</pre>', out, re.S)
    hostfile.unlink()
    return json.loads(htmllib.unescape(m.group(1))) if m and m.group(1) else None


def make_copy(page, css, name):
    src = page.read_text(encoding="utf-8")
    src = src.replace("</head>", f"<style>{css}</style></head>", 1).replace("</body>", DUMP_JS + "</body>", 1)
    path = SOURCE / name
    path.write_text(src, encoding="utf-8")
    return path


def compare(variants):
    """variants: {label: (cssA, cssB)}. Returns the number of differing page/width/variant combinations."""
    (HERE / "pages").mkdir(exist_ok=True)
    jobs, keys = [], []
    try:
        for i, page in enumerate(pages(), 1):
            for label, (a, b) in variants.items():
                pa, pb = make_copy(page, a, f"_cmp_{i}_{label}_a.html"), make_copy(page, b, f"_cmp_{i}_{label}_b.html")
                for w in WIDTHS:
                    keys.append((i, label, w))
                    jobs += [(pa, w, f"{i}-{label}-{w}-a"), (pb, w, f"{i}-{label}-{w}-b")]
        with ThreadPoolExecutor(4) as ex:
            results = list(ex.map(render, jobs))
    finally:
        for p in SOURCE.glob("_cmp_*.html"):
            p.unlink()
    bad = 0
    for n, (i, label, w) in enumerate(keys):
        ra, rb = results[2 * n], results[2 * n + 1]
        if ra is None or rb is None:
            print(f"page {i} {label} {w}: no result"); bad += 1; continue
        diffs = []
        names = ra["names"]
        for p in sorted(set(ra["els"]) | set(rb["els"])):
            va, vb = ra["els"].get(p), rb["els"].get(p)
            if va == vb:
                continue
            if va is None or vb is None:
                diffs.append(f"{p}: {'only in old' if vb is None else 'only in new'}")
                continue
            for k, x, y in zip(["(hash)"] + ra["pk"], va.split("\u0001"), vb.split("\u0001")):
                if x != y and k != "(hash)":
                    diffs.append(f"{p} {k}: {x[:40]} -> {y[:40]}")
                    break
            else:
                diffs.append(f"{p}: some other property differs")
        if diffs:
            bad += 1
            print(f"page {i} ({pages()[i - 1].name[:40]}) {label} {w}px: {len(diffs)} elements differ")
            for d in diffs[:4]:
                print("    ", d)
    print("identical" if not bad else f"{bad} combinations differ")
    return bad


if __name__ == "__main__":
    kind, args = sys.argv[1:2], sys.argv[2:]
    if kind == ["userstyle"] and args:
        old = Path(args[0]).read_text()
        new = Path(args[1] if len(args) > 1 else ROOT / "archive-neue.user.css").read_text()
        compare({t: (userstyle_css(old, v), userstyle_css(new, v)) for t, v in THEMES.items()})
    elif kind == ["skin"] and len(args) == 2:
        compare({"skin": (Path(args[0]).read_text(), Path(args[1]).read_text())})
    else:
        print(__doc__)
