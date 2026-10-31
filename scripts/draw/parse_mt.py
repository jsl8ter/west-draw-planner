"""Montana explorer (temporary)."""
import re, time, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def parse():
    s = requests.Session(); s.headers.update(UA)
    r = s.get("https://myfwp.mt.gov/fwpPub/drawingStatistics", timeout=60)
    t = r.text
    LOG.append(f"status {r.status_code} len {len(t)}")
    i = t.find("Drawing Statistics LPT") if "Drawing Statistics LPT" in t else t.find("Animal")
    LOG.append(t[max(0,i-3000):i+9000])
    for m in re.finditer(r"<script[^>]*src=\"[^\"]*\"", t): LOG.append(m.group(0))
    return {"state": "MT", "system": "bonus_sq", "hunts": []}
