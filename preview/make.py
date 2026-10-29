#!/usr/bin/env python3
"""Make the preview images. Run:  python3 preview/make.py
Everything on the sample pages is invented. They use AO3's real page structure, with AO3's own
stylesheets (preview/ao3/, not committed) underneath, and then the real Archive Neue CSS on top:
  desktop = the userstyle, phone = the skin file of the same theme.
Output goes to preview/out/ (not committed). Needs Google Chrome; no other dependencies."""
import html as htmllib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
OUT = HERE / "out"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

THEMES = {"light": 1, "dark": 2, "slate": 3, "paper": 4}      # value of the userstyle's "Colour theme" setting
DESKTOP, PHONE = 1280, 390

AO3_CSS = ('<link rel="stylesheet" media="screen" href="../ao3/1_site_screen_.css">'
           '<link rel="stylesheet" media="only screen and (max-width: 62em), handheld" href="../ao3/4_site_midsize.handheld_.css">'
           '<link rel="stylesheet" media="only screen and (max-width: 42em), handheld" href="../ao3/5_site_narrow.handheld_.css">')

# ---------------------------------------------------------------- invented content

HEADER = """
<header id="header" class="region">
  <h1 class="heading"><a href="#"><span>Archive of Our Own</span><img alt="Archive of Our Own" class="logo" src="../ao3/logo_42.png"></a></h1>
  <nav id="greeting" aria-label="User">
    <ul class="user navigation actions">
      <li class="dropdown"><a href="#">Hi, reader!</a></li>
      <li class="dropdown"><a href="#">Post</a></li>
      <li><a href="#">Log Out</a></li>
    </ul>
  </nav>
  <nav aria-label="Site">
    <ul class="primary navigation actions">
      <li class="dropdown"><a href="#">Fandoms</a></li>
      <li class="dropdown"><a href="#">Browse</a></li>
      <li class="dropdown"><a href="#">Search</a></li>
      <li class="dropdown"><a href="#">About</a></li>
      <li class="search"><form class="search" id="search" role="search" action="#" method="get"><fieldset><p>
        <label class="landmark" for="site_search">Work Search</label>
        <input class="text" id="site_search" type="text" name="q">
        <span class="submit actions"><input type="submit" value="Search" class="button"></span></p></fieldset></form></li>
    </ul>
  </nav>
  <div class="clear"></div>
</header>"""

FOOTER = """
<div id="footer" role="contentinfo" class="region"><h3 class="landmark heading">Footer</h3>
  <ul class="navigation actions">
    <li class="module group"><h4 class="heading">About the Archive</h4><ul class="menu">
      <li><a href="#">Site Map</a></li><li><a href="#">Terms of Service</a></li><li><a href="#">Privacy Policy</a></li></ul></li>
    <li class="module group"><h4 class="heading">Contact Us</h4><ul class="menu">
      <li><a href="#">Technical Support &amp; Feedback</a></li><li><a href="#">Donate or Volunteer</a></li></ul></li>
  </ul>
</div>"""


def tags(fandom, rel, chars, free):
    li = lambda cls, items: "".join(f'<li class="{cls}"><a class="tag" href="#">{t}</a></li> ' for t in items)
    return ('<li class="warnings"><strong><a class="tag" href="#">No Archive Warnings Apply</a></strong></li> '
            + li("relationships", rel) + li("characters", chars) + li("freeforms", free))


def blurb(n, title, author, fandom, rating, wip, date, tag_html, summary, stats):
    icons = {"g": ("rating-general-audience", "General Audiences"), "t": ("rating-teen", "Teen And Up Audiences"),
             "m": ("rating-mature", "Mature")}
    rc, rt = icons[rating]
    done = ("complete-yes", "Complete Work") if not wip else ("complete-no", "Work in Progress")
    st = "".join(f'<div class="{k}"><dt class="{k}">{k.capitalize()}:</dt><dd class="{k}">{v}</dd></div>' for k, v in stats)
    return f"""
<li id="work_{n}" class="work blurb group" role="article">
  <div class="header module">
    <h4 class="heading"><a href="#">{title}</a> by <a rel="author" href="#">{author}</a></h4>
    <h5 class="fandoms heading"><span class="landmark">Fandoms:</span> <a class="tag" href="#">{fandom}</a> &nbsp;</h5>
    <ul class="required-tags">
      <li><a class="help symbol question modal" href="#"><span class="{rc} rating" title="{rt}"><span class="text">{rt}</span></span></a></li>
      <li><a class="help symbol question modal" href="#"><span class="warning-no warnings" title="No Archive Warnings Apply"><span class="text">No Archive Warnings Apply</span></span></a></li>
      <li><a class="help symbol question modal" href="#"><span class="category-gen category" title="Gen"><span class="text">Gen</span></span></a></li>
      <li><a class="help symbol question modal" href="#"><span class="{done[0]} iswip" title="{done[1]}"><span class="text">{done[1]}</span></span></a></li>
    </ul>
    <p class="datetime">{date}</p>
  </div>
  <h6 class="landmark heading">Tags</h6>
  <ul class="tags commas">{tag_html}</ul>
  <h6 class="landmark heading">Summary</h6>
  <blockquote class="userstuff summary"><p>{summary}</p></blockquote>
  <dl class="stats"><div class="language"><dt class="language">Language:</dt><dd class="language">English</dd></div>{st}</dl>
</li>"""


WORKS = [
    blurb(1001, "Salt and Lanternlight", "Wren Calloway", "Original Work", "t", True, "12 Oct 2026",
          tags("", [], ["Original Characters"], ["Slow Burn", "Found Family", "Coastal Town", "Winter", "Hurt/Comfort"]),
          "Mara takes the lighthouse keeper's cottage for one winter, meaning to be alone. The village has other ideas.",
          [("words", "48,310"), ("chapters", "14/20"), ("comments", "212"), ("kudos", "1,408"), ("bookmarks", "96"), ("hits", "21,905")]),
    blurb(1002, "The Cartographer's Apprentice", "ink_and_orchard", "Original Work", "g", False, "03 Oct 2026",
          tags("", [], ["Original Characters"], ["Adventure", "Mapmaking", "Mentor/Protégé", "Happy Ending"]),
          "Ten maps, one missing island, and a teacher who will not say why she stopped drawing.",
          [("words", "12,044"), ("chapters", "5/5"), ("comments", "58"), ("kudos", "730"), ("bookmarks", "41"), ("hits", "6,310")]),
    blurb(1003, "Seven Letters from Harrow Street", "Pell Aldous", "Original Work", "m", False, "28 Sep 2026",
          tags("", [], ["Original Characters"], ["Epistolary", "Second Chances", "Slow Burn", "Letters", "Angst with a Happy Ending"]),
          "Two people who agreed never to speak again, and the seven letters that break the agreement one at a time.",
          [("words", "9,876"), ("chapters", "7/7"), ("comments", "134"), ("kudos", "2,012"), ("bookmarks", "188"), ("hits", "15,442")]),
    blurb(1004, "Small Hours at the Night Library", "quill_and_kettle", "Original Work", "g", False, "19 Sep 2026",
          tags("", [], ["Original Characters"], ["Cozy", "Libraries", "Fluff", "One Shot"]),
          "The library never closes, and the night staff have a ritual involving tea, one very old cat, and a book that returns itself.",
          [("words", "3,502"), ("chapters", "1/1"), ("comments", "27"), ("kudos", "615"), ("bookmarks", "52"), ("hits", "4,118")]),
]

LIST_PAGE = f"""
<div id="inner" class="wrapper"><div id="main" class="works-index filtered region" role="main">
  <h2 class="heading">1 - 20 of 4,812 Works in <a class="tag" href="#">Original Work</a></h2>
  <div class="navigation actions module"><h3 class="landmark heading">Navigation and Actions</h3>
    <ul class="user navigation actions"><li><span class="current">Works</span></li><li><a href="#">Bookmarks</a></li>
    <li><form class="ajax-create-destroy" action="#" method="post"><input type="submit" value="Favorite Tag"></form></li></ul></div>
  <ol class="pagination actions pagy" role="navigation"><li class="previous"><span class="disabled">← Previous</span></li>
    <li><a class="current">1</a></li><li><a href="#">2</a></li><li><a href="#">3</a></li><li><a href="#">4</a></li><li class="next"><a href="#">Next →</a></li></ol>
  <ol class="work index group">{"".join(WORKS)}</ol>
</div></div>"""

STATS_WORK = ('<dl class="stats"><div class="published"><dt class="published">Published:</dt><dd class="published">2026-09-14</dd></div>'
              '<div class="words"><dt class="words">Words:</dt><dd class="words">2 840</dd></div>'
              '<div class="chapters"><dt class="chapters">Chapters:</dt><dd class="chapters">1/1</dd></div>'
              '<div class="comments"><dt class="comments">Comments:</dt><dd class="comments">41</dd></div>'
              '<div class="kudos"><dt class="kudos">Kudos:</dt><dd class="kudos">902</dd></div>'
              '<div class="bookmarks"><dt class="bookmarks">Bookmarks:</dt><dd class="bookmarks">77</dd></div>'
              '<div class="hits"><dt class="hits">Hits:</dt><dd class="hits">7 316</dd></div></dl>')


def meta_row(cls, label, items):
    links = "".join(f'<li><a class="tag" href="#">{i}</a></li>' for i in items)
    return f'<dt class="{cls} tags">{label}</dt><dd class="{cls} tags"><ul class="commas">{links}</ul></dd>'


WORK_PAGE = f"""
<div id="inner" class="wrapper"><div id="main" class="chapters-show region" role="main">
<div class="work">
  <ul class="work navigation actions">
    <li class="bookmark"><a href="#">Bookmark</a></li>
    <li class="mark"><form class="button_to" method="post" action="#"><button type="submit">Mark for Later</button></form></li>
    <li class="comments"><a href="#">Comments</a></li>
    <li class="subscribe"><form class="ajax-create-destroy" action="#" method="post"><input type="submit" value="Subscribe"></form></li>
  </ul>
  <div class="wrapper"><dl class="work meta group">
    {meta_row("rating", "Rating:", ["Teen And Up Audiences"])}
    {meta_row("warning", "Archive Warning:", ["No Archive Warnings Apply"])}
    {meta_row("fandom", "Fandom:", ["Original Work"])}
    {meta_row("freeform", "Additional Tags:", ["Slow Burn", "Found Family", "Coastal Town", "Winter", "Hurt/Comfort", "Happy Ending"])}
    <dt class="language">Language:</dt><dd class="language">English</dd>
    <dt class="stats">Stats:</dt><dd class="stats">{STATS_WORK}</dd>
  </dl></div>
  <div id="workskin">
    <div class="preface group"><h2 class="title heading">The Weather in Small Rooms</h2>
      <h3 class="byline heading"><a rel="author" href="#">Wren Calloway</a></h3>
      <div id="summary" class="summary module"><h3 class="heading">Summary:</h3>
        <blockquote class="userstuff"><p>A winter by the sea, a borrowed cottage, and a neighbour who keeps leaving soup on the step.</p></blockquote></div>
    </div>
    <div id="chapters"><div class="chapter" id="chapter-1">
      <div class="userstuff module" role="article"><h3 class="landmark heading" id="work">Chapter Text</h3>
        <p>The first thing Mara noticed about the cottage was the quiet. It was not the empty kind. It was the quiet of a place that had been waiting, patiently, for someone to come in out of the rain and put the kettle on.</p>
        <p>She set her bag down by the door and listened. Somewhere above her the wind found a loose slate and worried at it, a small, steady, almost friendly sound. Outside, the sea kept its own counsel.</p>
        <p>By the third day she had learned which stair complained, which window stuck, and which of the neighbours would wave. By the fourth, there was soup on the step.</p>
        <p>She stood looking at it for a long time. It was still warm.</p>
      </div></div></div>
  </div>
</div></div></div>"""

PAGES = {"list": LIST_PAGE, "work": WORK_PAGE}


# ---------------------------------------------------------------- CSS for each layout

def userstyle_css(theme):
    css = (ROOT / "archive-neue.user.css").read_text()
    head, body = css.split("==/UserStyle== */", 1)
    body = re.sub(r"^@-moz-document[^{]*\{", "", body, flags=re.M | re.S, count=1).rstrip()
    body = body[:-1] if body.endswith("}") else body            # the closing brace of @-moz-document
    imports = "".join(re.findall(r'@import url\("[^"]*"\);', body))
    body = body.replace(imports, "")
    return imports + f":root{{--theme:{theme};}}" + body


def skin_css(name):
    return (ROOT / "skin" / f"archive-neue-skin-{name}.css").read_text()


def page_html(page, css):
    # @import must come first in a stylesheet, so the CSS gets its own <style> and the imports stay on top
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">{AO3_CSS}<style>{css}</style></head>'
            f'<body class="logged-in"><div id="outer" class="wrapper">{HEADER}{PAGES[page]}{FOOTER}</div></body></html>')


def host_html(inner, width):
    """The page sits in an iframe of the exact width: headless Chrome won't make a window narrower than 500px,
    and the media queries (and so the phone layout) must see the real width. The host measures the page."""
    return (f'<!doctype html><html><body style="margin:0"><iframe id="f" width="{width}" height="3000" style="border:0;display:block;margin-left:{max(500 - width, 0) // 2}px" '
            f'srcdoc="{htmllib.escape(inner, quote=True)}"></iframe><script>'
            "const f=document.getElementById('f');"
            "f.addEventListener('load',()=>setTimeout(()=>{const h=Math.ceil(f.contentDocument.getElementById('outer')"
            ".getBoundingClientRect().bottom)+24;f.style.height=h+'px';document.title=h;},2000));</script></body></html>")


def chrome(args):
    return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                           "--virtual-time-budget=8000", *args], capture_output=True, text=True)


def shoot(html_path, png_path, width):
    url = html_path.resolve().as_uri()
    dom = chrome([f"--window-size={max(width, 500)},3000", "--dump-dom", url]).stdout
    height = int(re.search(r"<title>(\d+)</title>", dom).group(1))
    chrome([f"--window-size={max(width, 500)},{height}", f"--screenshot={png_path.resolve()}", url])
    if width < 500:                                               # crop away the margins (the page sits centred)
        subprocess.run(["sips", "--cropToHeightWidth", str(height), str(width), str(png_path)],
                       capture_output=True)
    return height


def sheet(name, images, cols, cell_w, cell_h, scale, gap=24, pad=32, bg="#e9e7e2"):
    """Lay the top part of several renders out on one image (the lineups). scale shrinks desktop renders to fit."""
    cells = "".join(f'<div style="width:{cell_w}px;height:{cell_h}px;overflow:hidden;border-radius:10px;'
                    f'box-shadow:0 1px 6px #0003"><img src="{(OUT / i).resolve().as_uri()}" width="{round(w * scale)}"></div>'
                    for i, w in images)
    width = pad * 2 + cols * cell_w + (cols - 1) * gap
    rows = -(-len(images) // cols)
    height = pad * 2 + rows * cell_h + (rows - 1) * gap
    page = HERE / "pages" / f"{name}.html"
    page.write_text(f'<!doctype html><body style="margin:0;background:{bg}"><div style="display:grid;'
                    f'grid-template-columns:repeat({cols},{cell_w}px);gap:{gap}px;padding:{pad}px">{cells}</div></body>')
    chrome([f"--window-size={max(width, 500)},{height}", f"--screenshot={(OUT / (name + '.png')).resolve()}", page.resolve().as_uri()])
    print(name + ".png", width, height)


def lineups():
    names = list(THEMES)
    sheet("themes-desktop", [(f"work-desktop-{t}.png", DESKTOP) for t in names], 2, 640, 480, 0.5)
    sheet("themes-phone", [(f"work-phone-{t}.png", PHONE) for t in names], 4, 300, 640, 300 / PHONE)


def main():
    pages_dir = HERE / "pages"
    pages_dir.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    only = sys.argv[1:]                                           # e.g. "paper" to render one theme
    for theme, value in THEMES.items():
        if only and theme not in only:
            continue
        for layout, width, css in (("desktop", DESKTOP, userstyle_css(value)), ("phone", PHONE, skin_css(theme))):
            for page in PAGES:
                html = pages_dir / f"{page}-{layout}-{theme}.html"
                html.write_text(host_html(page_html(page, css), width))
                png = OUT / f"{page}-{layout}-{theme}.png"
                print(png.name, shoot(html, png, width))
    if not only:
        lineups()


if __name__ == "__main__":
    main()
