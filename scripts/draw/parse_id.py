"""Idaho explorer (temporary)."""
import re, time, json, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest",
      "Referer": "https://idfg.idaho.gov/ifwis/huntplanner/odds/"}
def parse():
    s = requests.Session(); s.headers.update(UA)
    t = s.get("https://idfg.idaho.gov/ifwis/huntplanner/odds/", timeout=60).text
    i = t.find("function queryParams"); LOG.append(re.sub(r"\s+"," ",t[i:i+1500]))
    i = t.find("function areaFormatter"); LOG.append(re.sub(r"\s+"," ",t[i:i+1500]))
    for q in ("?biggame=3&yr=2025&draw=1", "?BigGame=3&Yr=2025&Draw=1"):
        time.sleep(3)
        r = s.get("https://idfg.idaho.gov/ifwis/huntplanner/api/1.1/odds/" + q, timeout=60)
        LOG.append(f"=== {q} {r.status_code} {r.headers.get('content-type')} {len(r.text)}")
        LOG.append(r.text[:4000])
    return {"state": "ID", "system": "random", "hunts": []}
