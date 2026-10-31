"""Crawl each state wildlife agency's draw-statistics pages and catalog report files.

Writes data/draw/inventory.json: per state, every PDF/XLSX/XLS/CSV/ZIP link (and HTML
pages that look like odds tables) whose link text or URL mentions draw/odds/recap/statistics,
plus a fetch log so failures are visible.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "draw")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) west-draw-planner/1.0 (github.com/jsl8ter/west-draw-planner)"}

SEEDS = {
    "CO": ["https://cpw.state.co.us/hunting/big-game/primary-draw", "https://cpw.state.co.us/hunting/big-game/draw-recaps",
           "https://cpw.state.co.us/hunting/big-game/elk", "https://cpw.state.co.us/hunting/big-game/deer",
           "https://cpw.state.co.us/hunting/big-game/hunting-pronghorn", "https://cpw.state.co.us/hunting/big-game/statistics"],
    "WY": ["https://wgfd.wyo.gov/licenses-applications/draw-results-odds", "https://wgfd.wyo.gov/hunting-trapping/draw-odds",
           "https://wgfd.wyo.gov/licenses-applications"],
    "UT": ["https://wildlife.utah.gov/bg-odds.html", "https://wildlife.utah.gov/hunting/main-hunting-page/big-game/big-game-drawing-odds.html",
           "https://wildlife.utah.gov/hunting/main-hunting-page/big-game.html"],
    "AZ": ["https://www.azgfd.com/hunting/draw/", "https://www.azgfd.com/hunting/hunt-draw-and-licenses/",
           "https://www.azgfd.com/hunting/hunt-draw-and-licenses/big-game-draw/", "https://www.azgfd.com/hunting/draw/draw-results/"],
    "NM": ["https://wildlife.dgf.nm.gov/hunting/applications-and-draw-information/", "https://wildlife.dgf.nm.gov/hunting/draw-odds/",
           "https://wildlife.dgf.nm.gov/hunting/"],
    "NV": ["https://www.ndow.org/apply-buy/", "https://www.ndow.org/blog/big-game-draw-results/",
           "https://www.ndow.org/blog/draw-results-statistics/", "https://www.ndow.org/get-outside/plan-your-hunt/"],
    "OR": ["https://myodfw.com/articles/controlled-hunt-draw-results", "https://myodfw.com/articles/big-game-hunting-statistics",
           "https://myodfw.com/big-game-hunting/controlled-hunts", "https://myodfw.com/articles/controlled-hunt-draw-statistics"],
    "ID": ["https://idfg.idaho.gov/hunt/drawodds", "https://idfg.idaho.gov/hunt/draw", "https://idfg.idaho.gov/licenses/tag/controlled",
           "https://idfg.idaho.gov/ifwis/huntplanner/odds/"],
    "MT": ["https://fwp.mt.gov/buyandapply/hunting-licenses/drawing-statistics", "https://fwp.mt.gov/buyandapply/hunting-licenses"],
}
DOMAINS = {"CO": "cpw.state.co.us", "WY": "wgfd.wyo.gov", "UT": "wildlife.utah.gov", "AZ": "azgfd.com", "NM": "dgf.nm.gov",
           "NV": "ndow.org", "OR": "myodfw.com", "ID": "idfg.idaho.gov", "MT": "fwp.mt.gov"}
KEY = re.compile(r"draw|odds|recap|statistic|result|bonus|preference|point|drawn|summary|harvest", re.I)
DOC = re.compile(r"\.(pdf|xlsx?|csv|zip)(\?|$)|/media/\d+/download|/download\b|amazonaws\.com/.+\.(pdf|xlsx?|csv)", re.I)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self._a = None; self._t = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._a = dict(attrs).get("href"); self._t = []

    def handle_data(self, d):
        if self._a is not None:
            self._t.append(d)

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None:
            self.links.append((self._a, " ".join("".join(self._t).split())[:160])); self._a = None


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        ct = r.headers.get("Content-Type", "")
        body = r.read(3_000_000) if "html" in ct else b""
        return r.geturl(), ct, body.decode("utf-8", "replace")


def crawl(st, max_pages=70):
    dom = DOMAINS[st]
    queue = [(u, 0) for u in SEEDS[st]]
    seen, docs, pages, log = set(), {}, [], []
    while queue and len(seen) < max_pages:
        url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            final, ct, html = fetch(url)
        except Exception as e:  # noqa: BLE001
            log.append({"url": url, "error": str(e)[:160]}); continue
        log.append({"url": url, "ok": True, "final": final})
        if not html:
            continue
        p = Links(); p.feed(html)
        title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        pages.append({"url": final, "title": (title.group(1).strip()[:120] if title else "")})
        for href, text in p.links:
            if not href or href.startswith(("mailto:", "tel:", "#", "javascript:")):
                continue
            absu = urllib.parse.urljoin(final, href)
            host = urllib.parse.urlparse(absu).netloc
            blob = f"{absu} {text}"
            if DOC.search(absu) and KEY.search(blob):
                docs.setdefault(absu, {"url": absu, "text": text, "found_on": final})
            elif dom in host and KEY.search(blob) and depth < 2 and absu not in seen:
                queue.append((absu.split("#")[0], depth + 1))
        time.sleep(0.4)
    return {"docs": sorted(docs.values(), key=lambda d: d["url"]), "pages": pages, "log": log}


def main():
    os.makedirs(OUT, exist_ok=True)
    states = sys.argv[1:] or list(SEEDS)
    path = os.path.join(OUT, "inventory.json")
    inv = json.load(open(path)) if os.path.exists(path) else {}
    for st in states:
        r = crawl(st)
        inv[st] = r
        print(st, "docs:", len(r["docs"]), "pages:", len(r["pages"]), "errors:", sum(1 for l in r["log"] if "error" in l), flush=True)
    inv["_generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(inv, open(path, "w"), indent=1)


if __name__ == "__main__":
    main()
