"""Idaho explorer (temporary)."""
import re, time, json, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def parse():
    s = requests.Session(); s.headers.update(UA)
    for u in ("https://idfg.idaho.gov/ifwis/huntplanner/filter", "https://idfg.idaho.gov/ifwis/huntplanner/filter/"):
        r = s.get(u, timeout=60); t = r.text
        LOG.append(f"=== {u} {r.status_code} {len(t)}")
        for m in re.finditer(r"url\s*:\s*[\"'][^\"']+[\"']|api/[\w./?=&-]+|data-field=\"\w+\"|<option value=\"[^\"]*\"[^>]*>[^<]*", t):
            LOG.append(m.group(0))
        time.sleep(3)
        if r.ok: break
    i = t.find("function queryParams"); LOG.append(re.sub(r"\s+"," ",t[i:i+1500]))
    i = t.find("id=\"scope\""); LOG.append(re.sub(r"\s+"," ",t[i:i+3000]))
    r = s.get("https://idfg.idaho.gov/ifwis/huntplanner/hunt/82029", timeout=60); t = r.text
    for m in re.finditer(r"api/[\w./?=&-]+|url\s*:\s*[\"'][^\"']+[\"']", t): LOG.append("hunt page: " + m.group(0))
    return {"state": "ID", "system": "random", "hunts": []}
