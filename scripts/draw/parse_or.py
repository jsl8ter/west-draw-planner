"""Oregon (ODFW) controlled hunt preference point draw reports -> data/draw/OR.json

Source: myodfw.com/articles/point-summary-reports, "<year> <species> Preference Point Draw Report" (xlsx).
Each hunt row: Tags Authorized, Resident/NR/Total first-choice apps and drawn; then one row per point
level with Applicants, Resident Apps/Drawn, NR Apps/Drawn *in the preference-point phase (75%)*.
Point-level "drawn" counts only the preference phase; the 25% random phase draws are in the hunt totals.
"""
import io, re, time
import requests, openpyxl

LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
B = "https://myodfw.com/sites/default/files/"
# (year, series, url)   series: 100 buck deer, 200 elk, 400 pronghorn, 600 antlerless deer
FILES = [
    (2026, 100, B + "2026-07/2026%20Buck%20Deer%20Preference%20Point%20Draw%20Report.xlsx"),
    (2026, 200, B + "2026-07/2026%20Elk%20Preference%20Point%20Draw%20Report.xlsx"),
    (2026, 400, B + "2026-07/2026%20Pronghorn%20Antelope%20Preference%20Point%20Draw%20Report.xlsx"),
    (2026, 600, B + "2026-08/2026%20Antlerless%20Deer%20Preference%20Point%20Draw%20Report_0.xlsx"),
    (2025, 100, B + "2025-11/2025_buck_points.xlsx"),
    (2025, 200, B + "2025-11/2025_elk_points.xlsx"),
    (2025, 400, B + "2025-11/2025_pronghorn_points.xlsx"),
    (2025, 600, B + "2025-11/2025_anterless_points.xlsx"),
    (2024, 100, B + "2025-09/2024%20Preference%20Point%20Draw%20Report%20Buck%20Deer.xlsx"),
    (2024, 200, B + "2025-09/2024%20Preference%20Point%20Draw%20Report%20Elk.xlsx"),
    (2024, 400, B + "2025-09/2024%20Preference%20Point%20Draw%20Report%20Pronghorn.xlsx"),
    (2024, 600, B + "2025-09/2024%20Preference%20Point%20Draw%20Report%20Antlerless%20Deer.xlsx"),
    (2023, 100, B + "2025-09/2023%20Buck%20Deer%20Preference%20Point%20Draw%20Report.xlsx"),
    (2023, 200, B + "2025-09/2023%20Elk%20Preference%20Point%20Draw%20Report.xlsx"),
    (2023, 400, B + "2025-09/2023%20Pronghorn%20Antelope%20Preference%20Point%20Draw%20Report.xlsx"),
    (2023, 600, B + "2025-09/2023%20Antlerless%20Deer%20Preference%20Point%20Draw%20Report.xlsx"),
    (2022, 100, B + "2025-09/2022%20Buck%20Deer%20Preference%20Point%20Draw%20Report.xlsx"),
    (2022, 200, B + "2022-12/2022%20Elk%20Preference%20Point%20Draw%20Report.xlsx"),
    (2022, 400, "https://myodfw.com/media/5547/download"),
    (2022, 600, "https://myodfw.com/media/5142/download"),
]
SERIES = {100: ("D", "Buck Deer", "male"), 200: ("E", "Elk", None), 400: ("P", "Pronghorn Antelope", None),
          600: ("D", "Antlerless Deer", "female")}

# ODFW wildlife management units (as in data/OR.geojson), title case
WMUS = ["Alsea", "Applegate", "Beatys Butte", "Beulah", "Biggs", "Catherine Creek", "Chesnimnus", "Chetco",
        "Columbia Basin", "Desolation", "Dixon", "Evans Creek", "Fort Rock", "Fossil", "Grizzly", "Heppner",
        "Hood", "Imnaha", "Indigo", "Interstate", "Juniper", "Keating", "Keno", "Klamath Falls", "Lookout Mtn",
        "Malheur River", "Maupin", "Maury", "McKenzie", "Melrose", "Metolius", "Minam", "Mount Emily",
        "Murderers Creek", "Northside", "Ochoco", "Owyhee", "Paulina", "Pine Creek", "Powers", "Rogue",
        "Saddle Mtn", "Santiam", "Scappoose", "Silver Lake", "Silvies", "Siuslaw", "Sixes", "Sled Springs",
        "Snake River", "Sprague", "Starkey", "Steens Mtn", "Stott Mtn", "Sumpter", "Tioga", "Trask", "Ukiah",
        "Upper Deschutes", "Wagontire", "Walla Walla", "Warner", "Wenaha", "White River", "Whitehorse",
        "Willamette", "Wilson"]


def norm(s):
    s = " " + re.sub(r"[^a-z0-9]+", " ", s.lower()) + " "
    for a, b in ((" cr ", " creek "), (" crk ", " creek "), (" mt emily ", " mount emily "),
                 (" mtn ", " mtn "), (" mountain ", " mtn "), (" r ", " river "), (" rvr ", " river "),
                 (" steens mt ", " steens mtn "), (" upr ", " upper "), (" mckenzie ", " mckenzie ")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


WMU_N = [(w, norm(w)) for w in WMUS]


def units_for(name):
    n = norm(name)
    found = []
    for w, wn in WMU_N:
        i = n.find(wn)
        if i >= 0:
            found.append((i, w))
    # drop names contained in a longer match (e.g. "Biggs" inside "West Biggs" is fine, but keep unique)
    found.sort()
    out = []
    for _, w in found:
        if w not in out:
            out.append(w)
    if out:
        return out
    c = re.sub(r"\(.*?\)", "", name)
    c = re.sub(r"\b(Private Lands|Private|Agri|Mule Deer|Unit|Units|Muzzleloader|Bow|Archery|Youth|Late|Early|Whitetail|Traditional|No\.?\s*\d+|\d{1,2})\b", "", c, flags=re.I)
    c = re.sub(r"\s+", " ", c).strip(" -,")
    return [c or name.strip()]


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(round(v))
    s = str(v).strip().replace(",", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return int(round(float(s)))
    return None


HUNT_RE = re.compile(r"^[A-Z]{0,3}\d{3}[A-Z0-9-]*$")  # 2026 deer uses new codes like AD101, HX601-1


def fetch(url):
    for i in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=120)
            r.raise_for_status()
            return r.content
        except Exception as e:
            err = e
            time.sleep(5 * (i + 1))
    raise err


def parse_file(data):
    """yield (hunt_id, name, head[12 values], points rows list[(pts, apps, rapps, rdrawn, nrapps, nrdrawn)])"""
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    hunts, order, bad = {}, [], []
    cur = None
    started = False
    for row in ws.iter_rows(values_only=True):
        row = list(row) + [None] * (18 - len(row))
        c0 = "" if row[0] is None else str(row[0]).strip()
        if not started:
            if c0.lower().startswith("hunt number"):
                started = True
            continue
        if HUNT_RE.match(c0):
            if c0 not in hunts:
                head = [num(x) for x in row[2:12]]
                hunts[c0] = {"name": str(row[1] or "").strip(), "head": head, "pts": []}
                order.append(c0)
            cur = hunts[c0]
        elif c0:
            if len(bad) < 50 and not c0.lower().startswith(("points", "total", "processed")):
                bad.append(row[:18])
            continue
        if cur is None:
            continue
        p = [num(x) for x in row[12:18]]
        if p[0] is not None and p[1] is not None:
            cur["pts"].append(tuple(p))
    return [(h, hunts[h]) for h in order], bad


def skip(hid, name):
    n = name.lower()
    return hid.endswith("T") or "youth" in n or "landowner" in n or "mentor" in n or "auction" in n or "raffle" in n


def weapon(hid, name):
    n = name.lower()
    if hid.endswith("R") or re.search(r"\bbow\b|archery", n):
        return "archery"
    if hid.endswith("M") or "muzzle" in n:
        return "muzzleloader"
    return "any"


def sex_for(series, name):
    s = SERIES[series][2]
    if s:
        return s
    n = name.lower()
    if "antlerless" in n or "cow" in n or "doe" in n:
        return "female"
    if "bull" in n or "spike" in n or "buck" in n:
        return "male"
    return None


def parse():
    out = {"state": "OR", "system": "pref75", "point_label": "preference points", "sources": [], "hunts": []}
    hunts = {}
    LOG.append("apps = first-choice applicants. by_pts drawn = drawn in the 75% preference-point phase only "
               "(random-phase draws are in hunt totals). Only a total quota (Tags Authorized) is published -> T.tags.")
    for year, series, url in FILES:
        sp, label, _ = SERIES[series]
        try:
            data = fetch(url)
            rows, bad = parse_file(data)
        except Exception as e:
            LOG.append(f"FAIL {year} {label} {url}: {e}")
            continue
        out["sources"].append({"year": year, "species": sp, "url": url,
                               "title": f"{year} {label} Preference Point Draw Report"})
        kept = 0
        for hid, h in rows:
            name = h["name"]
            if skip(hid, name):
                continue
            tags, rapps, rdrawn, nrapps, nrdrawn, tapps, tdrawn = h["head"][:7]
            yr = {}
            R, NR, T = {}, {}, {}
            if rapps is not None: R["apps"] = rapps
            if rdrawn is not None: R["drawn"] = rdrawn
            if nrapps is not None: NR["apps"] = nrapps
            if nrdrawn is not None: NR["drawn"] = nrdrawn
            if tags is not None: T["tags"] = tags
            if tapps is not None: T["apps"] = tapps
            if tdrawn is not None: T["drawn"] = tdrawn
            pts = {}
            for p in h["pts"]:
                pp, a, ra, rd, na, nd = p
                q = pts.setdefault(pp, [0, 0, 0, 0, 0])
                q[0] += a or 0; q[1] += ra or 0; q[2] += rd or 0; q[3] += na or 0; q[4] += nd or 0
            if pts:
                ks = sorted(pts, reverse=True)
                R["by_pts"] = [[k, pts[k][1], pts[k][2]] for k in ks if pts[k][1]]
                NR["by_pts"] = [[k, pts[k][3], pts[k][4]] for k in ks if pts[k][3]]
                T["by_pts"] = [[k, pts[k][0], pts[k][2] + pts[k][4]] for k in ks if pts[k][0]]
                for d, col in ((R, 2), (NR, 4)):
                    drew = [k for k in ks if pts[k][col] > 0]
                    if drew:
                        d["min_pts"] = min(drew)
                drew = [k for k in ks if pts[k][2] + pts[k][4] > 0]
                if drew:
                    T["min_pts"] = min(drew)
                for d in (R, NR, T):
                    if "by_pts" in d and not d["by_pts"]:
                        del d["by_pts"]
            if R: yr["R"] = R
            if NR: yr["NR"] = NR
            if T: yr["T"] = T
            key = hid
            if key not in hunts:
                e = {"id": hid, "species": sp, "units": units_for(name), "label": f"{hid} {name}",
                     "weapon": weapon(hid, name), "kind": "limited", "years": {}}
                s = sex_for(series, name)
                if s:
                    e["sex"] = s
                hunts[key] = e
            hunts[key]["years"][str(year)] = yr
            kept += 1
        LOG.append(f"{year} {label}: {url} -> {len(rows)} hunts parsed, {kept} kept")
        for b in bad:
            LOG.append(f"  unparsed row: {b}")
    out["hunts"] = sorted(hunts.values(), key=lambda h: (h["species"], h["id"]))
    for sp in "EDP":
        hs = [h for h in out["hunts"] if h["species"] == sp]
        unmatched = sorted({u for h in hs for u in h["units"] if u not in WMUS})
        LOG.append(f"species {sp}: {len(hs)} hunts; non-WMU unit names: {unmatched[:80]}")
    return out
