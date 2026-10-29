#!/usr/bin/env python3
"""Check the skins on saved AO3 pages at several widths.

    python3 preview/responsive.py check [theme...]            -> preview/out/responsive.json + a summary
    python3 preview/responsive.py shot <page-number> <width> [theme]   -> preview/out/resp-<n>-<theme>-<width>.png

Pages come from "source pages/" (saved from the browser; they hold real data, so that folder and everything
rendered from it stays out of git). The skin is added to each page, then a script inside the page checks:
  overflow - content wider than the screen (the page would scroll sideways)
  contrast - text whose colour is too close to the background behind it (under 3:1 is flagged)
  covered  - links, buttons and fields with something else on top of them (so they can't be clicked)
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
OUT = HERE / "out"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WIDTHS = [360, 600, 768, 1024, 1440]
THEMES = ["dark", "light"]                                        # slate and paper only change colours

CHECK_JS = r"""
<script>addEventListener('load',()=>setTimeout(()=>{
const cv=document.createElement('canvas').getContext('2d',{willReadFrequently:true});
const rgba=c=>{cv.clearRect(0,0,1,1);cv.fillStyle='#000';cv.fillStyle=c;cv.fillRect(0,0,1,1);const d=cv.getImageData(0,0,1,1).data;return[d[0],d[1],d[2],d[3]/255]};
const lum=([r,g,b])=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(r)+.7152*f(g)+.0722*f(b)};
const ratio=(a,b)=>{const x=lum(a),y=lum(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
const over=(top,under)=>{const a=top[3];return[0,1,2].map(i=>top[i]*a+under[i]*(1-a)).concat(1)};
const sel=e=>{const n=x=>x.tagName.toLowerCase()+(x.id?'#'+x.id:'')+(typeof x.className==='string'&&x.className?'.'+x.className.trim().split(/\s+/).slice(0,2).join('.'):'');return(e.parentElement&&e.parentElement!==document.body?n(e.parentElement)+' > ':'')+n(e)};
const shown=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility==='visible'&&+s.opacity>.1&&r.width>1&&r.height>1};
const bgOf=e=>{const layers=[];for(let x=e;x;x=x.parentElement){const s=getComputedStyle(x);if(s.backgroundImage!=='none')return null;const c=rgba(s.backgroundColor);if(c[3]>0)layers.push(c);if(c[3]>=1)break}
let base=[255,255,255,1];for(let i=layers.length-1;i>=0;i--)base=over(layers[i],base);return base};
const res={w:innerWidth,h:document.documentElement.scrollHeight,overflow:0,over:[],contrast:[],lowcount:0,covered:[]};
res.overflow=document.documentElement.scrollWidth-innerWidth;
if(res.overflow>1){for(const e of document.body.querySelectorAll('*')){if(!shown(e))continue;const r=e.getBoundingClientRect();if(r.right>innerWidth+1&&e.parentElement.getBoundingClientRect().right<=innerWidth+1&&res.over.length<6)res.over.push(sel(e)+' ('+Math.round(r.right)+')')}}
const seen=new Set();
const test=(e,text)=>{if(!shown(e))return;const s=getComputedStyle(e),bg=bgOf(e);if(!bg)return;const fg=over(rgba(s.color),bg),r=ratio(fg,bg),key=sel(e)+s.color+bg;
if(r>=4.5||seen.has(key))return;seen.add(key);if(r>=3){res.lowcount++;return}
res.contrast.push({sel:sel(e),text:text.trim().slice(0,30),ratio:Math.round(r*10)/10,fg:s.color,bg:'rgb('+bg.slice(0,3).map(Math.round)+')'})};
const tw=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
while(tw.nextNode()){const n=tw.currentNode;if(n.nodeValue.trim()&&!/^(SCRIPT|STYLE|NOSCRIPT)$/.test(n.parentElement.tagName))test(n.parentElement,n.nodeValue)}
document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]),button,select,textarea').forEach(e=>test(e,e.value||e.textContent||e.placeholder||e.type));
const els=[...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea')].filter(shown).slice(0,500);
for(const e of els){e.scrollIntoView({block:'center'});const r=e.getClientRects()[0],t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
if(t&&t!==e&&!e.contains(t)&&!t.contains(e)&&!(e.labels&&[...e.labels].some(l=>l.contains(t)))&&res.covered.length<10)res.covered.push(sel(e)+' ('+(e.textContent||e.value||'').trim().slice(0,20)+') under '+sel(t))}
scrollTo(0,0);parent.postMessage(JSON.stringify(res),'*')},1500));</script>"""


def pages():
    return sorted(p for p in SOURCE.glob("*.html"))


def host(url, width, height=3000):
    # headless Chrome won't make a window narrower than 500px, so the page sits in an iframe of the real width
    return (f'<!doctype html><html><body style="margin:0"><iframe id="f" width="{width}" height="{height}" '
            f'style="border:0;display:block;margin-left:{max(500 - width, 0) // 2}px" src="{url}"></iframe>'
            '<pre id="r"></pre><script>addEventListener("message",e=>{document.getElementById("r").textContent=e.data;'
            'const d=JSON.parse(e.data);document.getElementById("f").style.height=d.h+"px"})</script></body></html>')


def chrome(args):
    profile = tempfile.mkdtemp()
    return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                           f"--user-data-dir={profile}", "--virtual-time-budget=8000", *args],
                          capture_output=True, text=True, timeout=180)


def test_copy(i, page, theme):
    """The page with the skin added (and the checking script), saved next to the original so its files still load."""
    css = (ROOT / "skin" / f"archive-neue-skin-{theme}.css").read_text()
    src = page.read_text(encoding="utf-8")
    src = src.replace("</head>", f"<style>{css}</style></head>", 1).replace("</body>", CHECK_JS + "</body>", 1)
    path = SOURCE / f"_resp_{i}_{theme}.html"
    path.write_text(src, encoding="utf-8")
    return path


def run_one(job):
    i, theme, width, path = job
    hostfile = HERE / "pages" / f"resp-{i}-{theme}-{width}.html"
    hostfile.write_text(host(path.resolve().as_uri(), width))
    dom = chrome([f"--window-size={max(width, 500)},900", "--dump-dom", hostfile.resolve().as_uri()]).stdout
    m = re.search(r'<pre id="r">(.*?)</pre>', dom, re.S)
    data = json.loads(htmllib.unescape(m.group(1))) if m and m.group(1) else {"error": "no result"}
    return {"page": i, "theme": theme, "width": width, **data}


def check(themes):
    (HERE / "pages").mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    plist = pages()
    jobs = []
    for i, page in enumerate(plist, 1):
        for theme in themes:
            path = test_copy(i, page, theme)
            jobs += [(i, theme, w, path) for w in WIDTHS]
    try:
        with ThreadPoolExecutor(4) as ex:
            results = list(ex.map(run_one, jobs))
    finally:
        for p in SOURCE.glob("_resp_*.html"):
            p.unlink()
    (OUT / "responsive.json").write_text(json.dumps(results, indent=1))
    summarise(plist, results)


def summarise(plist, results):
    print("pages:")
    for i, p in enumerate(plist, 1):
        print(f"  {i:2} {p.name[:80]}")
    print("\nper page and width: O = sideways overflow in px, C = unreadable text items, X = covered controls")
    for theme in sorted({r["theme"] for r in results}):
        print(f"\n[{theme}]       " + "".join(f"{w:>14}" for w in WIDTHS))
        for i in range(1, len(plist) + 1):
            cells = []
            for w in WIDTHS:
                r = next((x for x in results if x["page"] == i and x["theme"] == theme and x["width"] == w), None)
                cells.append("err" if not r or "error" in r else f"O{max(r['overflow'], 0)} C{len(r['contrast'])} X{len(r['covered'])}")
            print(f"  page {i:2}      " + "".join(f"{c:>14}" for c in cells))


def shot(i, width, theme):
    path = test_copy(i, pages()[i - 1], theme)
    hostfile = HERE / "pages" / f"resp-{i}-{theme}-{width}.html"
    hostfile.write_text(host(path.resolve().as_uri(), width))
    try:
        data = run_one((i, theme, width, path))
        height = min(data["h"], 6000)
        png = OUT / f"resp-{i}-{theme}-{width}.png"
        chrome([f"--window-size={max(width, 500)},{height}", f"--screenshot={png.resolve()}", hostfile.resolve().as_uri()])
        if width < 500:
            subprocess.run(["sips", "--cropToHeightWidth", str(height), str(width), str(png)], capture_output=True)
        print(png)
    finally:
        path.unlink()


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["check"]:
        check(sys.argv[2:] or THEMES)
    elif cmd == ["shot"]:
        shot(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else "dark")
    else:
        print(__doc__)
