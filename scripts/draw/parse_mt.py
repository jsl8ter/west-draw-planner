"""Montana explorer (temporary)."""
import re, time, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def parse():
    s = requests.Session(); s.headers.update(UA)
    r = s.get("https://myfwp.mt.gov/fwpPub/drawingStatistics", timeout=60)
    for oid in ("28562", "94776"):
        r = s.post("https://myfwp.mt.gov/fwpPub/repositoryList_input.action", data={"repositoryObjectId": oid},
                   headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://myfwp.mt.gov/fwpPub/drawingStatistics"}, timeout=60)
        t = r.text
        LOG.append(f"=== {oid} status {r.status_code} {r.headers.get('content-type')} len {len(t)}")
        LOG.append(re.sub(r"\s+", " ", t)[:20000])
        time.sleep(2)
    return {"state": "MT", "system": "bonus_sq", "hunts": []}
