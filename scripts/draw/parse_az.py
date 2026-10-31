"""Arizona draw statistics (discovery stage: list AZGFD S3 bucket)."""
import re, requests, xml.etree.ElementTree as ET
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
BUCKET = "https://azgfd-portal-wordpress-pantheon.s3.us-west-2.amazonaws.com"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

def parse():
    tok, n, hits = None, 0, []
    while True:
        p = {"list-type": "2", "prefix": "wp-content/uploads/"}
        if tok: p["continuation-token"] = tok
        r = requests.get(BUCKET + "/", params=p, headers=UA, timeout=90); r.raise_for_status()
        root = ET.fromstring(r.content)
        for c in root.iter(NS + "Contents"):
            k = c.find(NS + "Key").text; n += 1
            if re.search(r"\.(pdf|xlsx?|csv)$", k, re.I) and re.search(r"(?i)odds|draw.?report|statistic|bonus.?point|draw.?result|hunt.?draw", k) \
               and re.search(r"20(19|2\d)", k) and not re.search(r"(?i)turkey|javelina|bison|sheep|bear|lion|spring|waterfowl|dove|fish", k):
                hits.append(k)
        t = root.find(NS + "NextContinuationToken")
        if t is None: break
        tok = t.text
    LOG.append(f"listed {n} keys, {len(hits)} hits")
    LOG.extend("KEY " + k for k in hits[-280:])
    return {"state": "AZ", "system": "az", "point_label": "bonus points", "sources": [], "hunts": []}
