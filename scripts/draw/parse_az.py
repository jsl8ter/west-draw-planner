"""Arizona draw statistics (discovery stage)."""
import re, time, requests
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
BUCKETS = ["https://azgfd-portal-wordpress-pantheon.s3.us-west-2.amazonaws.com",
           "https://azgfd-live-portal-wordpress-pantheon.s3.us-west-2.amazonaws.com",
           "https://s3.amazonaws.com/azgfd-portal-wordpress"]

def get(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=90, **kw)
        LOG.append(f"GET {url[:160]} -> {r.status_code} {len(r.content)}")
        return r
    except Exception as e:
        LOG.append(f"GET {url[:160]} error {e}")

def parse():
    for b in BUCKETS:
        r = get(b + "/?list-type=2&max-keys=20&prefix=wp-content/uploads/")
        if r is not None: LOG.append("  " + r.text[:400].replace("\n", " "))
    for host in ["azgfd-portal-wordpress-pantheon.s3.us-west-2.amazonaws.com", "azgfd-live-portal-wordpress-pantheon.s3.us-west-2.amazonaws.com",
                 "s3-us-west-2.amazonaws.com/azgfd-portal-wordpress-pantheon", "s3.amazonaws.com/azgfd-portal-wordpress", "www.azgfd.com/wp-content"]:
        time.sleep(6)
        r = get("https://web.archive.org/cdx/search/cdx", params={"url": host + "/*", "output": "txt", "fl": "original",
                "collapse": "urlkey", "filter": "original:.*(?i)(draw|odds|bonus).*", "limit": "3000"})
        if r is not None and r.ok:
            for line in sorted(set(r.text.split())):
                if re.search(r"(?i)(odds|draw-report|statistic|bonus-point|drawreport)", line) and re.search(r"20(19|2\d)", line):
                    LOG.append("CDX " + line)
    return {"state": "AZ", "system": "az", "point_label": "bonus points", "sources": [], "hunts": []}
