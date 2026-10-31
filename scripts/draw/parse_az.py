"""Arizona draw statistics.

Sources (AZGFD public S3 bucket; azgfd.com itself returns 403 to scripts):
  * "<year> AZ <Species> Draw Odds" PDFs -> hunt metadata (unit, method, dates, hunt type), 1st-choice applicants, permits issued
  * "Draw Report - Bonus Pass" and "Draw Report - 1-2 Pass" PDFs -> authorized permits (All / Res / NonRes cap),
    first-choice applicants and first-choice drawn per residency
  * "Bonus Point Report" PDFs -> per hunt, per bonus-point level: 1st-choice applicants and permits issued
    (bonus pass + 1-2 pass) by residency
Draw "M" = elk/pronghorn draw (hunt numbers 2xxx pronghorn, 3xxx elk); "F" = fall draw (1xxx deer).
"""
import io, re, os, requests
from concurrent.futures import ProcessPoolExecutor

LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
B = "https://azgfd-portal-wordpress-pantheon.s3.us-west-2.amazonaws.com/wp-content/uploads/"
FILES = {  # year -> kind -> paths
    2022: {"odds": ["archive/2022-AZ-Deer-Draw-Odds.pdf", "archive/2022-AZ-Elk-Draw-Odds.pdf", "archive/2022-AZ-Pronghorn-Antelope-Draw-Odds.pdf"],
           "bpr": ["archive/Bonus-Point-Report-2022-Elk-Pronghorn-Draw.pdf", "archive/Bonus-Point-Report-2022-Fall-Draw.pdf"],
           "dr12": ["2026/09/04141201/2022-Elk-and-Pronghorn-Draw-Report-1-2-Pass.pdf", "2026/09/04141812/2022-Fall-Draw-Report-1-2-Pass.pdf"],
           "drbp": ["2026/09/04141207/2022-Elk-and-Pronghorn-Draw-Report-Bonus-Pass.pdf", "2026/09/04141756/2022-Fall-Draw-Report-Bonus-Point-Pass.pdf"]},
    2023: {"odds": ["2024/01/03130748/2023-AZ-Deer-Draw-Odds.pdf", "2024/01/03130751/2023-AZ-Elk-Draw-Odds.pdf", "2024/01/03130802/2023-AZ-Pronghorn-Draw-Odds.pdf"],
           "bpr": ["2023/05/05093904/2023_Mid_Bonus-Point-Report.pdf", "2023/08/17094611/2023-Fall-Draw-Bonus-Point-Report.pdf"],
           "dr12": ["2023/05/05093908/2023_Mid_Draw-Report_1-2-Pass.pdf", "2024/05/30093736/2023-Fall-Draw-Report-1-2-Pass.pdf"],
           "drbp": ["2023/05/05093917/2023_Mid_Draw-Report_Bonus-Pass.pdf", "2023/08/17094622/2023-Fall-Draw-Report-Bonus-Pass.pdf"]},
    2024: {"odds": ["2024/12/02085502/2024-AZ-Deer-Draw-Odds.pdf", "2024/12/02085505/2024-AZ-Elk-Draw-Odds.pdf", "2024/12/02085516/2024-AZ-Pronghorn-Draw-Odds.pdf"],
           "bpr": ["2024/03/28135125/2024-Elk-Pronghorn-Bonus-Point-Report.pdf", "2024/09/03155509/2024-Fall-Bonus-Point-Report.pdf"],
           "dr12": ["2024/03/28135129/2024-Elk-Pronghorn-Draw-Report-1-2-Pass.pdf", "2024/07/17132550/2024-Fall-Draw-Report-1-2-Pass.pdf"],
           "drbp": ["2024/03/28135136/2024-Elk-Pronghorn-Draw-Report-Bonus-Pass.pdf", "2024/07/17132558/2024-Fall-Draw-Report-Bonus-Pass.pdf"]},
    2025: {"odds": ["2025/08/22144535/2025-AZ-Deer-Draw-Odds.pdf", "2025/08/22144539/2025-AZ-Elk-Draw-Odds.pdf", "2025/08/22144552/2025-AZ-Pronghorn-Draw-Odds.pdf"],
           "bpr": ["2025/05/15151918/2025-Bonus-Point-Report.pdf", "2025/07/17111316/2025-Fall-Bonus-Point-Report.pdf"],
           "dr12": ["2025/05/15151926/2025-Elk-Pronghorn-Draw-Report-1-2-Pass.pdf"],
           "drbp": ["2025/05/15151934/2025-Elk-Pronghorn-Draw-Report-Bonus-Pass.pdf"]},
    2026: {"odds": [],
           "bpr": ["2026/03/27091508/2026-M-Bonus-Point-Report.pdf", "2026/08/16185459/2026-F-Bonus-Point-Report.pdf"],
           "dr12": ["2026/03/27091608/2026-M-Draw-Report-1-2-Pass.pdf", "2026/08/05153607/2026-F-Draw-Report-1-2-Pass.pdf"],
           "drbp": ["2026/03/27091637/2026-M-Draw-Report-Bonus-Pass.pdf", "2026/08/05153620/2026-F-Draw-Report-Bonus-Point-Pass.pdf"]},
}
DATE = r"\d{1,2}/\d{1,2}/\d{4}"
ODDS = re.compile(rf"^(\S+) (\d{{4}}) (20\d\d) (.+?) ({DATE}) ({DATE}) (.+?) (\d+) (\d+) (\d+) (\S+)$")
BPR = re.compile(r"^(\d{4}) (\d{1,2})((?: \d+){15})$")
NUMS = re.compile(r"^(All|Res|NonRes) ([\d. ]+)$")


def text_of(path):
    """Download a PDF and return (path, list of page texts) or (path, error string)."""
    import pdfplumber
    try:
        r = requests.get(B + path, headers=UA, timeout=180); r.raise_for_status()
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return path, [(p.extract_text() or "") for p in pdf.pages]
    except Exception as e:
        return path, f"ERROR {e!r}"


def species_of(num, htype):
    t = htype.lower()
    if num.startswith("3") or "elk" in t: return "E"
    if num.startswith("2") or "pronghorn" in t or "antelope" in t: return "P"
    if num.startswith("1"):
        return "C" if "whitetail" in t else "D"
    return None


def weapon_of(method):
    m = method.lower()
    if "archery" in m: return "archery"
    if "muzzle" in m: return "muzzleloader"
    if re.search(r"\bham\b|limited weapon", m): return "other"
    if "general" in m: return "any"
    return "other"


def sex_of(htype):
    t = htype.lower()
    if "antlerless" in t or "doe" in t or "cow" in t: return "female"
    if "bull" in t or "antlered" in t or "buck" in t: return "male"
    if "any" in t or "either" in t: return "either"
    return None


def unit_list(u):
    return [re.sub(r"^0+(?=\d)", "", x) for x in u.split("/") if x]


def date_key(d):
    mo, dy, yr = (int(x) for x in d.split("/"))
    return (yr, mo, dy)


def parse_odds(year, path, pages, meta, bad):
    n = 0
    for pg in pages:
        for line in pg.splitlines():
            line = line.strip()
            m = ODDS.match(line)
            if not m:
                if re.match(r"^\S+ \d{4} 20\d\d ", line) and len(bad) < 50: bad.append(f"{year} odds unparsed: {line}")
                continue
            unit, num, yr, method, op, cl, htype, a1, a2, issued, _ = m.groups()
            if int(yr) != year: continue
            meta[num] = {"unit": unit, "method": method, "open": op, "close": cl, "type": htype,
                         "apps1": int(a1), "issued": int(issued)}
            n += 1
    LOG.append(f"{year} odds {B + path}: {n} hunts")


def parse_dr(year, path, pages, out):
    """Draw report: out[num][grp] = list of ints (All has 11, Res/NonRes 10)."""
    cur, n = None, 0
    for pg in pages:
        for line in pg.splitlines():
            line = line.strip()
            m = re.match(r"^(\d{4})(?: \d+)*$", line)
            if m: cur = m.group(1); continue
            m = NUMS.match(line)
            if m and cur:
                vals = m.group(2).split()
                if any("." in v for v in vals): continue
                out.setdefault(cur, {})[m.group(1)] = [int(v) for v in vals]
                if m.group(1) == "All": n += 1
    LOG.append(f"{year} draw report {B + path}: {n} hunts")
    if n == 0 and pages: LOG.append("   first lines: " + " | ".join(pages[0].splitlines()[:12]))


def parse_bpr(year, path, pages, out):
    n = 0
    for pg in pages:
        for line in pg.splitlines():
            m = BPR.match(line.strip())
            if not m: continue
            v = [int(x) for x in m.group(3).split()]
            # v: 1st T,R,NR | 2nd T,R,NR | 1+2 T,R,NR | issued bonus pass T,R,NR | issued bonus+1-2 pass T,R,NR
            out.setdefault(m.group(1), {})[int(m.group(2))] = v
            n += 1
    LOG.append(f"{year} bonus point report {B + path}: {n} rows")
    if n == 0 and pages: LOG.append("   first lines: " + " | ".join(pages[0].splitlines()[:12]))


def norm_type(t):
    return re.sub(r"[^a-z]+", " ", t.lower().replace("antelope", "pronghorn")).strip()


def norm_method(mth):
    return re.sub(r"[^a-z]+", " ", mth.lower().replace("-only", "")).strip()


def year_rec(y, num, m, dr12, drbp, bpr, bad):
    rec = {"T": {}, "R": {}, "NR": {}}
    if dr12 and "All" in dr12:
        rec["T"]["tags"] = dr12["All"][0]
        if "NonRes" in dr12: rec["NR"]["tags"] = dr12["NonRes"][0]
    else:
        rec["T"]["tags"] = m["issued"]
    if bpr:
        for gi, g in ((0, "T"), (1, "R"), (2, "NR")):
            rec[g]["apps"] = sum(v[gi] for v in bpr.values())
            if g != "T":
                rec[g]["by_pts"] = [[p, v[gi], v[12 + gi]] for p, v in sorted(bpr.items(), reverse=True) if v[gi] or v[12 + gi]]
                bp = [p for p, v in bpr.items() if v[9 + gi] > 0]
                if bp: rec[g]["min_pts"] = min(bp)
        if rec["T"]["apps"] != m["apps1"] and len(bad) < 50:
            bad.append(f"{y} {num}: Bonus Point Report 1st-choice apps {rec['T']['apps']} != Draw Odds {m['apps1']}")
    else:
        rec["T"]["apps"] = m["apps1"]
    if dr12 and drbp and all(g in dr12 and g in drbp for g in ("All", "Res", "NonRes")):
        for g, k in (("All", "T"), ("Res", "R"), ("NonRes", "NR")):
            rec[k]["drawn"] = dr12[g][5] + drbp[g][5]
    elif bpr:
        for gi, g in ((0, "T"), (1, "R"), (2, "NR")):
            rec[g]["drawn"] = sum(v[12 + gi] for v in bpr.values())
    return {k: v for k, v in rec.items() if v}


def parse():
    paths = [p for d in FILES.values() for ps in d.values() for p in ps]
    with ProcessPoolExecutor(max_workers=4) as ex:
        texts = dict(ex.map(text_of, paths))
    bad, sources, per_year = [], [], {}
    for y, d in FILES.items():
        meta, dr12, drbp, bpr = {}, {}, {}, {}
        for k, ps in d.items():
            for p in ps:
                t = texts[p]
                if isinstance(t, str):
                    LOG.append(f"{y} {k} {B + p}: {t}"); continue
                if k == "odds": parse_odds(y, p, t, meta, bad)
                elif k == "dr12": parse_dr(y, p, t, dr12)
                elif k == "drbp": parse_dr(y, p, t, drbp)
                else: parse_bpr(y, p, t, bpr)
                fall = re.search(r"Fall|-F-", p) is not None
                sp = {"odds": "E" if "Elk" in p else "P" if "Pronghorn" in p else "D,C"}.get(k, "D,C" if fall else "E,P")
                sources.append({"year": y, "species": sp, "url": B + p, "title": os.path.basename(p)})
        per_year[y] = (meta, dr12, drbp, bpr)

    # Hunt identity: (species, units, method, hunt type) + ordinal by season open date.
    hunts, by_key = {}, {}
    for y in sorted(per_year, reverse=True):
        meta, dr12, drbp, bpr = per_year[y]
        if not meta:
            if bpr: LOG.append(f"{y}: no Draw Odds hunt list published; {len(bpr)} hunts in the bonus point reports NOT included (no unit/type metadata)")
            continue
        groups = {}
        for num, m in meta.items():
            sp = species_of(num, m["type"])
            if sp is None or re.search(r"youth", m["method"] + m["type"], re.I): continue
            base = (sp, tuple(sorted(unit_list(m["unit"]))), norm_method(m["method"]), norm_type(m["type"]))
            groups.setdefault(base, []).append(num)
        for base, nums in groups.items():
            nums.sort(key=lambda n: (date_key(meta[n]["open"]), n))
            for i, num in enumerate(nums):
                m = meta[num]
                h = by_key.get(base + (i,))
                if h is None:
                    hid = num if num not in hunts else f"{num} ({y})"
                    h = {"id": hid, "species": base[0], "units": unit_list(m["unit"]),
                         "label": f"{m['unit']} {m['type']} - {m['method']} {m['open']}-{m['close']}",
                         "weapon": weapon_of(m["method"]),
                         "kind": "special" if re.search(r"limited opp|champ", m["method"], re.I) else "limited",
                         "years": {}}
                    s = sex_of(m["type"])
                    if s: h["sex"] = s
                    hunts[hid] = h; by_key[base + (i,)] = h
                h["years"][str(y)] = year_rec(y, num, m, dr12.get(num), drbp.get(num), bpr.get(num), bad)
    LOG.extend(bad[:50])
    LOG.append("apps = first-choice applicants (Bonus Point Report sums; Draw Odds if missing). drawn = first-choice drawn in bonus pass + 1-2 pass "
               "(Draw Reports); where those are missing (2025 fall deer), drawn = permits issued in bonus + 1-2 pass (1st or 2nd choice) from the Bonus Point Report.")
    LOG.append("by_pts = [points, first-choice applicants, permits issued in bonus + 1-2 pass at that level (includes 2nd-choice draws)]. "
               "min_pts = lowest point level that drew in the bonus (max-point) pass.")
    LOG.append("T.tags = authorized permits (Draw Report); NR.tags = nonresident cap (Draw Report NonRes 'Authorized Permits'). "
               "Residents may fill all permits, so R.tags is omitted. Without a Draw Report (2025 fall), T.tags = permits issued from Draw Odds.")
    LOG.append("Species: deer hunt types containing 'whitetail' -> C; other deer (incl. 'Any antlered deer') -> D. Youth-only hunts skipped. "
               "AZ reuses hunt numbers for different hunts, so hunts are matched across years by units+method+hunt type+season order; id = most recent number.")
    out = sorted(hunts.values(), key=lambda h: h["id"])
    return {"state": "AZ", "system": "az", "point_label": "bonus points", "sources": sources, "hunts": out}
