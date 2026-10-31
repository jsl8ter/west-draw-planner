"""Idaho explorer (temporary)."""
import re, time, json, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def parse():
    s = requests.Session(); s.headers.update(UA)
    t = s.get("https://idfg.idaho.gov/ifwis/huntplanner/filter", timeout=60).text
    for m in re.finditer(r"<script[^>]*>(.*?)</script>", t, re.S):
        c = m.group(1)
        if "bootstrapTable" in c or "api" in c:
            LOG.append("SCRIPT: " + re.sub(r"\s+", " ", c)[:6000])
    for m in re.finditer(r"<select[^>]*>.*?</select>", t, re.S):
        LOG.append("SELECT: " + re.sub(r"\s+", " ", m.group(0))[:1500])
    time.sleep(2)
    t = s.get("https://idfg.idaho.gov/ifwis/huntplanner/hunt/82029", timeout=60).text
    for m in re.finditer(r"<script[^>]*>(.*?)</script>", t, re.S):
        c = m.group(1)
        if "api" in c or "odds" in c.lower():
            LOG.append("HUNT SCRIPT: " + re.sub(r"\s+", " ", c)[:3000])
    i = t.find("Elk Controlled Hunt"); LOG.append("HUNT HTML: " + re.sub(r"\s+", " ", t[i-200:i+5000]))
    return {"state": "ID", "system": "random", "hunts": []}
