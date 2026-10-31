"""Wyoming (WGFD) elk / deer / antelope draw statistics.

Source: WGFD "Demand Report" PDFs linked from https://wgfd.wyo.gov/licenses-applications/draw-results-odds
(served as https://wgfd.wyo.gov/media/<id>/download). Every PDF linked there with a residency label is
downloaded and identified from its own header (species, residency, draw type, report date), so the page
layout does not matter. Landowner reports and whitetail-only hunts are skipped.

Report types used (per species and year):
  * Nonresident [Special] Preference Point: per hunt, rows by point level with quota remaining,
    point level, 1st-choice applicants and success odds. This is the 75% preference-point pass.
  * Nonresident [Special] Random: per hunt, random-pool quota and 1st/2nd/3rd-choice applicants.
  * Resident: per hunt, total quota and 1st/2nd/3rd-choice applicants (residents have no points).
  * Doe/Fawn and Cow/Calf (NR and R): random-only antlerless reports, same layout as Random.

Output per hunt/year:
  NR.tags   = PP quota + random quota      NR.apps = 1st-choice applicants in the PP report
  NR.drawn  = PP drawn (sum of round(applicants*odds)) + random 1st-choice drawn
  random 1st-choice drawn = min(random quota, random 1st-choice applicants) (WY fills all 1st choices first)
  R.tags/apps from the Resident report, R.drawn = min(quota, 1st-choice applicants).
  by_pts    = [points, 1st-choice applicants, drawn] from the PP report. Rows printed as "< N" (party
              averages between N-1 and N) are folded into N-1; the last row of a hunt is the remainder of
              all lower point levels and is recorded at its own level (N-1 for "< N", N for "<= N").
  min_pts   = lowest point level that drew in the PP pass.
Special (higher-fee) NR licenses are separate hunts with id suffix "-S" and kind "special".
"""
import io, re, html, concurrent.futures as cf
import requests, pdfplumber

LOG = []
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) west-draw-planner/1.0"}
PAGE = "https://wgfd.wyo.gov/licenses-applications/draw-results-odds"
BASE = "https://wgfd.wyo.gov"
# media ids known from searches, in case the page drops older years
EXTRA = [32451, 32452, 32455, 32686, 32688, 32697, 32703, 32765, 30130, 30447, 30451, 30457]
SPECIES = {"elk": "E", "deer": "D", "antelope": "P"}
REGION_NAMES = {"E": "Eastern", "S": "Southern", "W": "Western", "N": "Northern"}
NUM = r"(\d[\d,]*)"


def get(url):
    r = requests.get(url, headers=UA, timeout=180)
    r.raise_for_status()
    return r


def find_links():
    txt = get(PAGE).text
    links = {}
    for href, label in re.findall(r'href="([^"]*?/media/(?:\d+)/download[^"]*)"[^>]*>\s*([^<]{0,80})<', txt):
        label = html.unescape(label).strip()
        mid = re.search(r"/media/(\d+)/", href).group(1)
        if re.search(r"resident", label, re.I):
            links[int(mid)] = label
    LOG.append(f"page: {len(links)} residency-labelled media links")
    for m in EXTRA:
        links.setdefault(m, "extra")
    return links


def fetch(mid):
    url = f"{BASE}/media/{mid}/download"
    try:
        r = get(url)
        if not r.content.startswith(b"%PDF"):
            return mid, url, None, "not pdf"
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
        return mid, url, pages, r.headers.get("Content-Disposition", "")
    except Exception as e:
        return mid, url, None, str(e)


def classify(pages):
    head = "\n".join(pages[0].splitlines()[:4]) if pages else ""
    m = re.search(r"Demand Report - (Non-Resident|Resident)\s+(.*?)\s+State of Wyoming\s+Date:\s*\d+/\d+/(20\d\d)", head)
    if not m:
        return None
    res = "NR" if m.group(1) == "Non-Resident" else "R"
    sp_txt = m.group(2).lower()
    year = int(m.group(3))
    sp = next((c for k, c in SPECIES.items() if sp_txt.endswith(k)), None)
    line2 = pages[0].splitlines()[1] if len(pages[0].splitlines()) > 1 else ""
    if "landowner" in head.lower() or not sp:
        return None
    antlerless = bool(re.search(r"doe|fawn|cow|calf", sp_txt))
    special = "special" in line2.lower()
    pp = "Pref First Choice" in head or "preference point" in line2.lower()
    return {"res": res, "sp": sp, "year": year, "special": special, "pp": pp, "antlerless": antlerless,
            "title": f"{m.group(1)} {m.group(2)} {line2.split('Wyoming')[0].strip()}"}


HDR_PP = re.compile(r"^(\w{1,4})\s+(?:(\d)\s+)?(.+?)\s+" + NUM + r"\s+(?:" + NUM + r"\s+)?(<=?)?\s*" + NUM + r"\s+" + NUM + r"\s+([\d.]+)%$")
ROW_PP = re.compile(r"^" + NUM + r"\s+(?:" + NUM + r"\s+)?(<=?)?\s*" + NUM + r"\s+" + NUM + r"\s+([\d.]+)%$")
ROW_RND = re.compile(r"^(\w{1,4})\s+(?:(\d)\s+)?(.+?)\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"$")


def i(s):
    return int(s.replace(",", "")) if s else None


def body_lines(page):
    out, started = [], False
    for ln in page.splitlines():
        ln = ln.strip()
        if ln.startswith("----"):
            started = True; continue
        if started and ln:
            out.append(ln)
    return out


def parse_pp(pages, bad):
    """-> {(area, type): {"desc", "quota", "rows": [(rem, op, pts, apps, odds)]}}"""
    hunts, cur = {}, None
    for pg in pages:
        for ln in body_lines(pg):
            m = ROW_PP.match(ln)
            if m and cur is not None:
                rem, _iss, op, pts, apps, odds = m.groups()
                cur["rows"].append((i(rem), op or "", i(pts), i(apps), float(odds)))
                continue
            m = HDR_PP.match(ln)
            if m:
                area, typ, desc, quota, _iss, op, pts, apps, odds = m.groups()
                key = (area, typ or "")
                cur = hunts.setdefault(key, {"desc": desc.strip(" ;,"), "quota": i(quota), "rows": []})
                cur["rows"].append((i(quota), op or "", i(pts), i(apps), float(odds)))
                continue
            bad.append(ln)
    return hunts


def parse_rnd(pages, bad):
    hunts = {}
    for pg in pages:
        for ln in body_lines(pg):
            m = ROW_RND.match(ln)
            if m:
                area, typ, desc, quota, a1, a2, a3 = m.groups()
                hunts[(area, typ or "")] = {"desc": desc.strip(" ;,"), "quota": i(quota), "apps": i(a1)}
            else:
                bad.append(ln)
    return hunts


def pp_stats(h):
    by, drawn_tot, apps_tot = {}, 0, 0
    rows = h["rows"]
    for k, (rem, op, pts, apps, odds) in enumerate(rows):
        drawn = min(rem, int(round(apps * odds / 100.0)))
        lvl = pts - 1 if op == "<" else pts
        if lvl < 0:
            lvl = 0
        a, d = by.get(lvl, (0, 0))
        by[lvl] = (a + apps, d + drawn)
        drawn_tot += drawn; apps_tot += apps
    by_pts = [[p, a, d] for p, (a, d) in sorted(by.items(), reverse=True) if a or d]
    drew = [p for p, a, d in by_pts if d > 0]
    out = {"tags": h["quota"], "apps": apps_tot, "drawn": drawn_tot, "by_pts": by_pts}
    if drew:
        out["min_pts"] = min(drew)
    return out


def describe(sp, desc):
    d = desc.upper()
    if "ARCHERY" in d:
        weapon = "archery"
    elif "MUZZLE" in d:
        weapon = "muzzleloader"
    else:
        weapon = "any"
    if re.search(r"ANTLERLESS|COW|DOE|FAWN|CALF|EWE", d):
        sex = "female"
    elif re.search(r"ANTLERED|BULL|BUCK", d):
        sex = "male"
    else:
        sex = "either"
    return weapon, sex


def unit_for(sp, area):
    if area.isdigit():
        return [str(int(area))]
    if sp == "E":
        return [REGION_NAMES.get(area, area)]
    return [area]


def parse():
    links = find_links()
    reports = []
    with cf.ThreadPoolExecutor(8) as ex:
        for mid, url, pages, info in ex.map(fetch, sorted(links)):
            if pages is None:
                LOG.append(f"skip {url}: {info}"); continue
            c = classify(pages)
            if not c:
                LOG.append(f"skip {url} ({links[mid]}): {pages[0].splitlines()[0][:80] if pages and pages[0] else 'empty'}")
                continue
            c.update(url=url, pages=pages, file=info)
            reports.append(c)
    # newest five years
    years = sorted({r["year"] for r in reports}, reverse=True)[:5]
    LOG.append(f"years found {sorted({r['year'] for r in reports})}, using {sorted(years)}")
    seen = set()
    hunts = {}
    sources = []
    bad_all = []

    def hunt(hid, sp, area, desc, kind):
        h = hunts.get(hid)
        if not h:
            weapon, sex = describe(sp, desc)
            label = (f"Area {int(area)}" if area.isdigit() else f"Region {area}") + f" type {hid.split('-')[1] or 'gen'} - {desc.title()}"
            if kind == "special":
                label += " (NR special)"
            h = hunts[hid] = {"id": hid, "species": sp, "units": unit_for(sp, area), "label": label,
                              "weapon": weapon, "sex": sex, "kind": kind, "years": {}}
        return h

    for r in sorted(reports, key=lambda r: (r["year"], r["sp"], r["res"], r["special"], not r["pp"])):
        if r["year"] not in years:
            continue
        key = (r["year"], r["sp"], r["res"], r["special"], r["pp"], r["antlerless"])
        if key in seen:
            LOG.append(f"duplicate report {key} {r['url']} skipped"); continue
        seen.add(key)
        bad = []
        data = parse_pp(r["pages"], bad) if r["pp"] else parse_rnd(r["pages"], bad)
        n = 0
        for (area, typ), d in data.items():
            if "WHITE-T" in d["desc"].upper() or "WHITETAIL" in d["desc"].upper():
                continue
            general = not area.isdigit()
            kind = "special" if r["special"] else ("general" if general else "limited")
            hid = f"{area}-{typ or 'GEN'}" + ("-S" if r["special"] else "")
            h = hunt(hid, r["sp"], area, d["desc"], kind)
            y = h["years"].setdefault(str(r["year"]), {})
            res = y.setdefault(r["res"], {})
            if r["pp"]:
                st = pp_stats(d)
                res["_pp"] = st
            else:
                res["_rnd"] = {"tags": d["quota"], "apps": d["apps"], "drawn": min(d["quota"], d["apps"])}
            n += 1
        sources.append({"year": r["year"], "species": r["sp"], "url": r["url"], "title": r["title"]})
        LOG.append(f"{r['url']} | {r['year']} {r['sp']} {r['title']} | pages {len(r['pages'])} hunts {n} unparsed {len(bad)}")
        bad_all += [f"  {r['year']} {r['sp']} {r['res']}: {b}" for b in bad]
    LOG.append(f"unparsed rows total {len(bad_all)} (first 50):")
    LOG.extend(bad_all[:50])

    # combine pools
    for h in hunts.values():
        for yr, y in h["years"].items():
            for res in list(y):
                p = y[res]
                pp, rnd = p.pop("_pp", None), p.pop("_rnd", None)
                if pp and rnd:
                    p.update(tags=pp["tags"] + rnd["tags"], apps=pp["apps"], drawn=pp["drawn"] + rnd["drawn"],
                             by_pts=pp["by_pts"])
                    if "min_pts" in pp:
                        p["min_pts"] = pp["min_pts"]
                elif pp:
                    p.update(pp)
                elif rnd:
                    p.update(rnd)
                if not p:
                    del y[res]
            if "NR" in y and "R" in y and h["kind"] != "special":
                y["T"] = {k: y["NR"][k] + y["R"][k] for k in ("tags", "apps", "drawn")}
    out = [h for h in hunts.values() if h["years"]]
    out.sort(key=lambda h: (h["species"], h["id"]))
    LOG.append(f"hunts: E {sum(h['species']=='E' for h in out)} D {sum(h['species']=='D' for h in out)} P {sum(h['species']=='P' for h in out)}")
    LOG.append("apps = 1st-choice applicants (NR: preference-point report; R: resident report). "
               "NR random-pool and resident drawn = min(quota, 1st-choice applicants).")
    return {"state": "WY", "system": "pref75", "point_label": "preference points",
            "sources": sorted(sources, key=lambda s: (s["year"], s["species"])), "hunts": out}
