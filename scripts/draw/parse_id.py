"""Idaho explorer (temporary)."""
import re, time, json, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def parse():
    s = requests.Session(); s.headers.update(UA)
    t = s.get("https://idfg.idaho.gov/ifwis/huntplanner/filter", timeout=60).text
    for m in re.finditer(r'<input[^>]*class="check-(\w+)"[^>]*value="([^"]*)"[^>]*>([^<]{0,60})', t):
        LOG.append(f"CHECK {m.group(1)}={m.group(2)} {m.group(3).strip()}")
    for q in ("start=2025-1-1&end=2025-12-31&limit=3&offset=0",
              "start=2025-1-1&end=2025-12-31&game=2&limit=3&offset=0&search=Controlled"):
        time.sleep(3)
        r = s.get("https://idfg.idaho.gov/ifwis/huntplanner/api/1.1/list/?" + q, timeout=60,
                  headers={"X-Requested-With": "XMLHttpRequest"})
        LOG.append(f"=== {q} {r.status_code} {len(r.text)}")
        LOG.append(r.text[:3000])
    return {"state": "ID", "system": "random", "hunts": []}
