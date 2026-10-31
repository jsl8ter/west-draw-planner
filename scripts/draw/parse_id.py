"""Idaho explorer (temporary)."""
import re, time, json, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def parse():
    s = requests.Session(); s.headers.update(UA)
    r = s.get("https://idfg.idaho.gov/ifwis/huntplanner/filter", timeout=60); t = r.text
    LOG.append(f"filter {r.status_code} {len(t)}")
    for m in re.finditer(r"<script[^>]*src=\"([^\"]+)\"", t): LOG.append("SRC " + m.group(1))
    for m in re.finditer(r"<script(?![^>]*src)[^>]*>(.*?)</script>", t, re.S):
        c = re.sub(r"\s+", " ", m.group(1))
        if len(c) > 200 and "google-analytics" not in c: LOG.append("INLINE " + c[:8000])
    for src in re.findall(r"<script[^>]*src=\"([^\"]+)\"", t):
        if "huntplanner" in src or src.startswith(("js/", "../js", "scripts")) or "filter" in src:
            u = requests.compat.urljoin("https://idfg.idaho.gov/ifwis/huntplanner/filter", src)
            time.sleep(2); js = s.get(u, timeout=60).text
            LOG.append(f"JS {u} {len(js)}: " + " | ".join(sorted(set(re.findall(r"api/[\w./-]+", js))))[:2000])
    time.sleep(2)
    r = s.get("https://idfg.idaho.gov/ifwis/huntplanner/hunt/82029", timeout=60); t = r.text
    LOG.append(f"hunt {r.status_code} {len(t)}")
    i = t.find("Antlered"); LOG.append("HUNT HTML: " + re.sub(r"\s+", " ", t[max(0,i-3000):i+3000]))
    return {"state": "ID", "system": "random", "hunts": []}
