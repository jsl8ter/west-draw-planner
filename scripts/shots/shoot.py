"""Phone-size screenshots of the live site with real map tiles (runs on GitHub Actions)."""
import asyncio, os, sys
from playwright.async_api import async_playwright
URL = "https://jsl8ter.github.io/west-draw-planner/"
OUT = "shots"
CASES = sys.argv[1:] or ["E:pts", "D:pts", "P:pts", "E:odds", "D:trophy"]
async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 400, "height": 860}, device_scale_factor=2)
        logs = []
        pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
        await pg.goto(URL + "?v=" + os.environ.get("GITHUB_SHA", "x")[:7], wait_until="networkidle", timeout=120000)
        await pg.wait_for_timeout(8000)
        for case in CASES:
            sp, metric = case.split(":")
            await pg.select_option("#hunt-sel", f"{sp}|antlered")
            await pg.select_option("#cm-metric", metric)
            await pg.wait_for_timeout(2500)
            await pg.locator(".mapbox").screenshot(path=f"{OUT}/{sp}-{metric}.png")
        await pg.screenshot(path=f"{OUT}/top.png")
        await pg.select_option("#hunt-sel", "E|antlered"); await pg.select_option("#cm-metric", "pts")
        for name, lat, lng, z in [("ut_state", 39.4, -111.6, 6.5), ("ut_central", 38.6, -111.9, 8.5), ("co_nm", 37.25, -107.6, 8.5)]:
            await pg.evaluate(f"void map.setView([{lat},{lng}],{z})"); await pg.wait_for_timeout(3500)
            await pg.locator(".mapbox").screenshot(path=f"{OUT}/zoom_{name}.png")
        await pg.click("#t-plan"); await pg.wait_for_timeout(3000)
        await pg.screenshot(path=f"{OUT}/plan.png", full_page=True)
        await pg.click(".pick .maplink"); await pg.wait_for_timeout(5000)
        await pg.locator(".mapbox").screenshot(path=f"{OUT}/jump.png")
        await pg.locator("#sheet").screenshot(path=f"{OUT}/jump_sheet.png")
        open(f"{OUT}/console.txt", "w").write("\n".join(logs[:200]))
        await b.close()
asyncio.run(main())
