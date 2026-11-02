"""Utah moved draw odds to utahdraws.com (JavaScript app) in 2026. Load the page in Chromium and call its
JSON endpoint from inside the page for each hunt type and year -> data/draw/raw/UT/<year>_<typeID>.json
Usage: fetch_ut_api.py [year ...]"""
import json, os, sys
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "draw", "raw", "UT"); os.makedirs(OUT, exist_ok=True)
YEARS = [int(y) for y in sys.argv[1:]] or [2026, 2025]
TYPES = {8: "Big Game", 9: "Big Game", 10: "Big Game", 5: "Big Game"}   # LE buck deer, LE bull elk, LE buck pronghorn, general buck deer
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    pg.goto("https://www.utahdraws.com/internetsales/home/drawodds", wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(3000)
    sup = pg.evaluate("fetch('/internetsales/Home/DrawOddsSupplementData').then(r=>r.json())")
    json.dump(sup, open(os.path.join(OUT, "supplement.json"), "w"))
    for y in YEARS:
        for tid, dn in TYPES.items():
            url = f"/internetsales/Home/DrawOddsData?drawName={dn.replace(' ', '%20')}&licenseYear={y}&masterHuntTypeID={tid}"
            try:
                d = pg.evaluate(f"fetch('{url}').then(r=>r.json())")
                n = len((d or {}).get("Data") or [])
                json.dump(d, open(os.path.join(OUT, f"{y}_{tid}.json"), "w"))
                print(y, tid, "hunts", n)
            except Exception as e:
                print(y, tid, "ERROR", e)
    b.close()
