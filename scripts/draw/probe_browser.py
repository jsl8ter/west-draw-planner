"""Open a JavaScript page in Chromium, click around a little, and record every JSON/XHR response it loads.
Usage: probe_browser.py ST URL   -> data/draw/probe/ST/browser.txt (+ browser.png)"""
import json, os, sys
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
st, url = sys.argv[1], sys.argv[2]
out_dir = os.path.join(ROOT, "data", "draw", "probe", st); os.makedirs(out_dir, exist_ok=True)
log = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    def on_resp(r):
        ct = r.headers.get("content-type", "")
        if r.request.resource_type in ("xhr", "fetch") or "json" in ct:
            try: body = r.text()[:4000]
            except Exception as e: body = f"<{e}>"
            log.append(f"### {r.request.method} {r.url} [{r.status}] {ct}\nPOST: {(r.request.post_data or '')[:1000]}\n{body}\n")
    pg.on("response", on_resp)
    try:
        pg.goto(url, wait_until="networkidle", timeout=90000)
    except Exception as e:
        log.append(f"goto error {e}")
    pg.wait_for_timeout(5000)
    log.insert(0, "PAGE TEXT:\n" + pg.inner_text("body")[:6000] + "\n\nSELECTS:\n" + json.dumps(pg.eval_on_selector_all("select", "els=>els.map(e=>({id:e.id,name:e.name,opts:[...e.options].slice(0,60).map(o=>o.value+'='+o.text)}))"))[:6000]
               + "\n\nLINKS:\n" + "\n".join(pg.eval_on_selector_all("a", "els=>els.map(a=>a.href+' | '+a.innerText.trim().slice(0,60))")[:200]))
    # try the first select / button to trigger data loads
    try:
        sels = pg.query_selector_all("select")
        for s in sels[:3]:
            opts = s.eval_on_selector_all("option", "o=>o.map(x=>x.value)")
            if len(opts) > 1: s.select_option(opts[1]); pg.wait_for_timeout(2500)
        btn = pg.query_selector("button[type=submit], button:has-text('Search'), button:has-text('View'), button:has-text('Submit')")
        if btn: btn.click(); pg.wait_for_timeout(5000)
    except Exception as e:
        log.append(f"interaction error {e}")
    pg.screenshot(path=os.path.join(out_dir, "browser.png"), full_page=True)
    b.close()
open(os.path.join(out_dir, "browser.txt"), "w").write("\n".join(log))
print("\n".join(log)[:5000])
