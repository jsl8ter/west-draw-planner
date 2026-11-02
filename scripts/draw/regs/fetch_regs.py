"""Fetch hunt tables (with bag limits) from official regulation pages -> data/draw/regs/<ST>.json

Each state entry: list of pages. For each HTML <table> we keep header + rows as text, keyed by page.
A per-state extractor turns rows into {hunt_id: {"name", "bag", "tags", "page"}}.
Raw text of every table is saved to data/draw/regs/<ST>_tables.json for inspection.
"""
import json, os, re, sys, time
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, "data", "draw", "regs")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"}
PAGES = {
    "OR": ["https://www.eregulations.com/oregon/hunting/elk-seasons",
           "https://www.eregulations.com/oregon/hunting/buck-deer-seasons",
           "https://www.eregulations.com/oregon/hunting/antlerless-deer-seasons",
           "https://www.eregulations.com/oregon/hunting/pronghorn-antelope-seasons",
           "https://www.eregulations.com/oregon/hunting/deer-seasons"],
}


def tables(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for t in soup.find_all("table"):
        rows = []
        for tr in t.find_all("tr"):
            cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(cells)
        # nearest preceding heading gives the table's context (e.g. "Controlled Archery Elk")
        h = t.find_previous(["h1", "h2", "h3", "h4", "h5"])
        out.append({"heading": h.get_text(" ", strip=True) if h else "", "rows": rows})
    return out


def extract_or(page_tables):
    hunts = {}
    for page, tbls in page_tables.items():
        for t in tbls:
            hdr = None
            for r in t["rows"]:
                low = [c.lower() for c in r]
                if any("hunt" in c and "#" in c for c in low) or (low and low[0].startswith("hunt")):
                    hdr = low; continue
                if not hdr or not r:
                    continue
                m = re.match(r"^((?:[A-Z]{2}\d{3}|\d{3})[A-Z0-9-]*)\*?$", r[0].replace(" ", ""))
                if not m:
                    continue
                row = dict(zip(hdr, r))
                bag = next((v for k, v in row.items() if "bag" in k), "")
                name = next((v for k, v in row.items() if "name" in k), "")
                tags = next((v for k, v in row.items() if "tags" in k), "")
                hunts.setdefault(m.group(1), {"name": name, "bag": bag, "tags": tags, "page": page, "table": t["heading"]})
    return hunts


EXTRACT = {"OR": extract_or}


def main():
    os.makedirs(OUT, exist_ok=True)
    states = sys.argv[1:] or list(PAGES)
    S = requests.Session(); S.headers.update(UA)
    for st in states:
        got, log = {}, []
        for url in PAGES[st]:
            try:
                r = S.get(url, timeout=90)
                log.append(f"{url} -> {r.status_code} {len(r.content)} bytes")
                if r.status_code == 200:
                    got[url] = tables(r.text)
                    log.append(f"   {len(got[url])} tables")
            except Exception as e:  # noqa: BLE001
                log.append(f"{url} FAILED {e}")
            time.sleep(2)
        hunts = EXTRACT[st](got) if st in EXTRACT else {}
        json.dump(got, open(os.path.join(OUT, f"{st}_tables.json"), "w"), indent=0)
        json.dump({"state": st, "generated": time.strftime("%Y-%m-%d"), "log": log, "hunts": hunts},
                  open(os.path.join(OUT, f"{st}.json"), "w"), indent=1)
        print(st, len(hunts), "hunts", *log, sep="\n")


if __name__ == "__main__":
    main()
