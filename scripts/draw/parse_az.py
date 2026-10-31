"""Arizona draw statistics (discovery stage)."""
import re, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
PAGES = ["https://www.azgfd.com/hunting/hunt-draw-and-licenses/harvest-reporting/",
         "https://www.azgfd.com/Hunting/surveydata/",
         "https://www.azgfd.com/hunting/hunt-draw-and-licenses/big-game-draw/bonus-point-process/"]

def fetch(u):
    for url in (u, "https://web.archive.org/web/2026/" + u):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            LOG.append(f"GET {url} -> {r.status_code} {len(r.content)}")
            if r.ok: return r.text
        except Exception as e:
            LOG.append(f"GET {url} error {e}")
    return ""

def parse():
    for p in PAGES:
        h = fetch(p)
        for href, txt in re.findall(r'href="([^"]+)"[^>]*>(.{0,200}?)</a', h, re.S):
            t = re.sub(r"<[^>]+>|\s+", " ", txt).strip()
            if re.search(r"draw|odds|bonus|\.pdf|\.xls", href + t, re.I):
                LOG.append(f"LINK {t[:100]} | {href}")
    return {"state": "AZ", "system": "az", "point_label": "bonus points", "sources": [], "hunts": []}
