"""Utah (DWR) big game draw statistics.

Sources (per draw year YY):
  https://wildlife.utah.gov/pdf/bg/<year>/<YY>_bg-odds.pdf    limited-entry / OIAL / CWMU bonus point draw, one page per hunt
  https://wildlife.utah.gov/pdf/bg/<year>/<YY>_deer_odds.pdf  general-season buck deer preference point draw, one page per hunt
Each hunt page has, by point level and residency: eligible applicants, bonus-pass permits, regular (random) permits,
total permits. DWR does not print the permit quota in these reports, so `tags` is omitted; `drawn` is total
permits drawn. `apps` = eligible applicants as printed; per-hunt counts sum exactly to the species
"All Applicants" totals, i.e. each applicant is counted once, under the first-choice hunt.
"""
import io, re, collections
import requests, pdfplumber

LOG = []
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) west-draw-planner/1.0"}
YEARS = [2026, 2025, 2024, 2023, 2022, 2021]
MAX_YEARS = 5
SP = {"D": "D", "E": "E", "P": "P"}  # first letter of hunt code
NUM = r"\d[\d,]*"


def n(s):
    return int(s.replace(",", ""))


HALF = r"(Totals|\d+)\s+((?:[\d,]+\s+){3}[\d,]+)\s+(N/A|(?:1\s+)?in\s+[\d.,]+)"
ROW2 = re.compile(rf"^{HALF}\s+{HALF}\s*$")


def fetch(url):
    r = requests.get(url, headers=UA, timeout=300)
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        return None
    return r.content


def split_label(label):
    """'Limited-entry Alw (rifle) Bull Elk - Early - Cache, Meadowville - Any Legal Weapon' -> segments"""
    return [x.strip() for x in re.split(r"\s+-\s*|\s*-\s+", label) if x.strip()]


def weapon_of(w):
    w = w.lower()
    if "archery" in w: return "archery"
    if "muzzle" in w: return "muzzleloader"
    if "any legal" in w or "rifle" in w: return "any"
    return "other"


def parse_pdf(data, url, year, general, bad):
    hunts = {}
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pi, page in enumerate(pdf.pages):
            t = page.extract_text() or ""
            m = re.search(r"^Hunt:\s+([A-Z]{2}\d{4})\s+(.*?)\s+Page\s+\d+\s*$", t, re.M)
            if not m:
                continue
            code, label = m.group(1), m.group(2).strip()
            if code[0] not in SP or code[1] != "B":
                continue  # only buck/bull hunts of D/E/P (DB, EB, PB)
            R, NR = {}, {}
            rows_ok = 0
            for line in t.splitlines():
                mm = ROW2.match(line.strip())
                if not mm:
                    if re.match(r"^(Totals|\d+)\s+\d", line.strip()) and len(bad) < 50:
                        bad.append(f"{year} {code} p{pi+1}: {line.strip()}")
                    continue
                g = mm.groups()
                for side, off in ((R, 0), (NR, 3)):
                    k = g[off]
                    vals = [n(x) for x in g[off + 1].split()]  # eligible, bonus, regular, total
                    ratio = re.search(r"in\s+([\d.,]+)", g[off + 2])
                    if ratio and vals[3] and abs(vals[0] / vals[3] - float(ratio.group(1).replace(",", ""))) > 0.11 and len(bad) < 50:
                        bad.append(f"{year} {code} p{pi+1}: ratio mismatch: {line.strip()}")
                    if vals[1] + vals[2] != vals[3] and len(bad) < 50:
                        bad.append(f"{year} {code} p{pi+1}: bonus+regular != total: {line.strip()}")
                    side["T" if k == "Totals" else int(k)] = vals
                rows_ok += 1
            if "T" not in R:
                if len(bad) < 50: bad.append(f"{year} {code}: no Totals row ({rows_ok} rows)")
                continue
            hunts[code] = {"label": label, "R": R, "NR": NR, "page": pi + 1}
    return hunts


def res_rec(side, general):
    tot = side["T"]
    if tot[0] == 0 and tot[3] == 0:
        return None
    by = [[p, v[0], v[3]] for p, v in sorted(((p, v) for p, v in side.items() if p != "T"), reverse=True) if v[0] or v[3]]
    rec = {"apps": tot[0], "drawn": tot[3]}
    if general:
        drew = [p for p, a, d in by if d > 0]
    else:
        drew = [p for p, v in side.items() if p != "T" and v[1] > 0]  # drawn in the max-point (bonus) pass
    if drew:
        rec["min_pts"] = min(drew)
    rec["by_pts"] = by
    return rec


def parse():
    sources, out, bad = [], {}, []
    years_done = []
    for year in YEARS:
        if len(years_done) >= MAX_YEARS:
            break
        yy = f"{year % 100:02d}"
        got = False
        for fname, general in ((f"{yy}_bg-odds.pdf", False), (f"{yy}_deer_odds.pdf", True)):
            url = f"https://wildlife.utah.gov/pdf/bg/{year}/{fname}"
            try:
                data = fetch(url)
            except Exception as e:
                LOG.append(f"ERROR {url}: {e}"); continue
            if data is None:
                LOG.append(f"not available: {url}"); continue
            got = True
            hs = parse_pdf(data, url, year, general, bad)
            spc = collections.Counter(c[0] for c in hs)
            LOG.append(f"{url}: {len(hs)} D/E/P buck/bull hunts {dict(spc)}")
            # consistency check vs summed bonus+regular
            for code, h in hs.items():
                for r in ("R", "NR"):
                    s = h[r]
                    if "T" in s:
                        rows = [v for p, v in s.items() if p != "T"]
                        if [sum(v[i] for v in rows) for i in range(4)] != s["T"] and len(bad) < 50:
                            bad.append(f"{year} {code} {r}: rows do not sum to Totals")
            sources.append({"year": year, "species": ",".join(sorted(spc)), "url": url,
                            "title": f"{year} {'general-season buck deer' if general else 'limited-entry & OIAL'} draw results"})
            for code, h in hs.items():
                segs = split_label(h["label"])
                has_w = len(segs) >= 2 and re.search(r"archery|legal weapon|muzzle|h\.a\.m|rifle|shotgun", segs[-1], re.I)
                unit = segs[-2] if has_w else segs[-1]
                wtxt = segs[-1] if has_w else h["label"]
                low = h["label"].lower()
                kind = "general" if general else ("special" if "cwmu" in low else "limited")
                rec = out.get(code)
                if rec is None:
                    rec = out[code] = {"id": code, "species": SP[code[0]], "units": [unit], "label": h["label"],
                                       "weapon": weapon_of(wtxt), "sex": "male", "kind": kind,
                                       "years": {}}
                y = {}
                for r in ("R", "NR"):
                    rr = res_rec(h[r], general)
                    if rr: y[r] = rr
                if not y:
                    continue
                y["T"] = {"apps": sum(v["apps"] for v in y.values()), "drawn": sum(v["drawn"] for v in y.values())}
                rec["years"][str(year)] = y
        if got:
            years_done.append(year)
    hunts = [h for h in out.values() if h["years"]]
    cnt = collections.Counter((h["species"], h["kind"]) for h in hunts)
    LOG.append(f"years: {years_done}; hunts by species/kind: {dict(cnt)}")
    LOG.append("NOTE: tags omitted (DWR odds reports do not print quotas); drawn = total permits issued in the draw; "
               "LE min_pts = lowest point level drawn in the bonus (max-point) pass; general deer min_pts = lowest level drawn.")
    LOG.append("NOTE: general-season buck deer is a preference-point draw (kind=general); LE/OIAL/CWMU use bonus points (bonus50). "
               "CWMU public draw permits are kind=special. Dedicated Hunter, youth, lifetime, antlerless excluded.")
    LOG.extend("UNPARSED " + x for x in bad[:50])
    return {"state": "UT", "system": "bonus50", "point_label": "bonus points", "sources": sources,
            "hunts": sorted(hunts, key=lambda h: h["id"])}
