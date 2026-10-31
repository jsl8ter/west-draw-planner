"""Idaho explorer (temporary)."""
import re, time, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def dump(url, n=12000):
    r = requests.get(url, headers=UA, timeout=60)
    LOG.append(f"=== {url} {r.status_code} {r.headers.get('content-type')} {len(r.text)}")
    t = r.text
    for m in re.finditer(r"<script[^>]*>(.*?)</script>|<form.*?>|<table[^>]*>|<select[^>]*>|data-url=\"[^\"]*\"", t, re.S):
        s = m.group(0)
        LOG.append(s[:3000].replace("\n", " "))
    return t
def parse():
    t = dump("https://idfg.idaho.gov/ifwis/huntplanner/odds/")
    time.sleep(3)
    LOG.append("--- raw main region")
    i = t.find("Game Animal"); LOG.append(t[i-500:i+6000].replace("\n"," "))
    return {"state": "ID", "system": "random", "hunts": []}
