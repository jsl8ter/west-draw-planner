"""Montana (FWP) drawing statistics -> data/draw/MT.json

Source: myfwp.mt.gov/fwpPub/drawingStatistics (report repository, one list per animal).
 - "Drawing Statistics Report" PDFs (ALS30401): per license/permit (LPT) quota and landowner / regular
   resident / nonresident 1st-2nd-3rd choice applicants and successes.
 - "Detailed Bonus Point Drawing Statistics" PDFs: per LPT, residency and bonus points: applications, successes.
 - "NR Combination Preference Point Statistics" PDFs: general NR Big Game/Elk Combo and Deer Combo.
"""
import io, re, time
import requests, pdfplumber

LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
BASE = "https://myfwp.mt.gov/fwpPub/"
LISTS = {"28561": "Antelope", "28562": "Elk", "28566": "Deer", "94776": "NR Combination"}
YEARS = range(2022, 2027)
S = requests.Session()
S.headers.update(UA)

# item description -> (species, sex, kind label)
ITEMS = {"ELK PERMIT": ("E", None), "ELK B": ("E", "female"), "DEER PERMIT": ("D", "male"),
         "DEER B": ("D", "female"), "ANTELOPE": ("P", None), "ANTELOPE B": ("P", "female")}


def get(url, data=None):
    for i in range(4):
        try:
            r = S.post(url, data=data, timeout=120) if data else S.get(url, timeout=120)
            r.raise_for_status()
            return r
        except Exception as e:
            err = e
            time.sleep(5 * (i + 1))
    raise err


def report_list():
    get(BASE + "drawingStatistics")
    out = []
    for oid, animal in LISTS.items():
        r = get(BASE + "repositoryList_input.action", {"repositoryObjectId": oid})
        for m in re.finditer(r'href="([^"]*getRepositoryFile\?objectID=(\d+))"[^>]*>([^<]*)<', r.text):
            title = re.sub(r"\s+\d+(\.\d+)?\s*KB\s*$", "", m.group(3).strip())
            out.append((m.group(1).replace("&amp;", "&"), title, animal))
        time.sleep(1)
    return out


def classify(title):
    """-> (year, kind, item) kind in stats|bonus|combo"""
    m = re.match(r"(\d{4})\s+(.*)$", title)
    if not m:
        return None
    y, rest = int(m.group(1)), m.group(2)
    if y not in YEARS:
        return None
    low = rest.lower()
    if "combo" in low or "combination" in low:
        if "through" in low:
            return None
        return (y, "combo", None)
    if "bonus" in low:
        return (y, "bonus", None)  # item comes from each row
    if "drawing statistics" in low:
        for pat, item in ((r"^elk permit", "ELK PERMIT"), (r"^elk b\b", "ELK B"), (r"^deer permit", "DEER PERMIT"),
                          (r"^deer b\b", "DEER B"), (r"^antelope b\b", "ANTELOPE B"),
                          (r"^antelope (900|archery)", "ANTELOPE"), (r"^antelope drawing", "ANTELOPE")):
            if re.search(pat, low):
                return (y, "stats", item)
    return None


def _cell(c):
    if c is None:
        return ""
    if isinstance(c, float):
        return str(int(c)) if c == int(c) else str(c)
    return str(c).strip()


def pdf_lines(data, ytol=3):
    """Text lines from a PDF, XLS or XLSX report (spreadsheet rows are joined with spaces, leading
    numeric cells such as usage dates / item type codes dropped)."""
    if data[:4] == b"%PDF":
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for p in pdf.pages:
                for line in (p.extract_text(y_tolerance=ytol) or "").splitlines():
                    yield line.strip()
        return
    rows = []
    if data[:4] == b"\xd0\xcf\x11\xe0":
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        for sh in wb.sheets():
            for r in range(sh.nrows):
                rows.append(sh.row_values(r))
    elif data[:2] == b"PK":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows.extend(ws.iter_rows(values_only=True))
    for row in rows:
        cells = [_cell(c) for c in row]
        cells = [c for c in cells if c != ""]
        if cells and re.fullmatch(r"[\d.]+", cells[0]) and any(re.search(r"[A-Za-z]", c) for c in cells):
            while cells and re.fullmatch(r"[\d.]+", cells[0]):
                cells.pop(0)
        yield " ".join(cells)


NUM = r"(?:UNL|\d+)"  # 99999 also means unlimited
STAT_RE = re.compile(r"^(\d{3}-\d{2})\b(.*?)\s((?:%s\s+){22}%s)$" % (NUM, NUM))


def n(v):
    return None if v in ("UNL", "99999") else int(v)


def parse_stats(data, item):
    """ALS30401 layout after district: Quota | LO: R-QTA R-apps1 R-succ1 NR-QTA NR-apps1 NR-succ1 |
    Regular: R-QTA R-apps1 2 3 R-succ1 2 3 | NR-QTA NR-apps1 2 3 NR-succ1 2 3 | TotalSucc Surplus"""
    rows, bad = {}, []
    for line in pdf_lines(data):
        m = STAT_RE.match(line)
        if not m:
            if re.match(r"^\d{3}-\d{2}\b", line) and len(bad) < 50:
                bad.append(line)
            continue
        code, note, nums = m.group(1), m.group(2).strip(), m.group(3).split()
        v = [n(x) for x in nums]
        rows[code] = {"note": note, "quota": v[0], "lo_r": (v[2], v[3]), "lo_nr": (v[5], v[6]),
                      "r_qta": v[7], "r": (v[8], v[11]), "nr_qta": v[14], "nr": (v[15], v[18]),
                      "total_succ": v[21]}
    return rows, bad


BON_RE = re.compile(r"^([A-Z][A-Z0-9 \-]*?)\s+(\d{3}-\d{2})\b(.*?)\s(RESIDENT LANDOWNER|NONRESIDENT LANDOWNER|"
                    r"RESIDENT|NONRESIDENT)\s+(?:(\d+)\s+)?(\d+)\s+(\d+)\s+[\d.]+$")


BON2_RE = re.compile(r"^([A-Z][A-Z0-9 \-]*?)\s+(\d{3}-\d{2})\s+(.*?[a-z].*?)\s+(?:(\d+)\s+)?(\d+)\s+(\d+)\s+[\d.]+$")
RESIDENCIES = ["NONRESIDENT LANDOWNER", "RESIDENT LANDOWNER", "NONRESIDENT", "RESIDENT"]


def _subseq(needle, hay):
    it = iter(hay)
    return all(ch in it for ch in needle)


def untangle(line):
    """Rows where a wrapped note was printed over the residency column, e.g.
    'ELK PERMIT 270-45 (FirsRt ECShIDoiEcNe TOnly) 1 481 481 100' = '(First Choice Only)' + 'RESIDENT'.
    The residency is the longest candidate that is an in-order subsequence of the capital letters."""
    m = BON2_RE.match(line)
    if not m:
        return None
    caps = re.sub(r"[^A-Z]", "", m.group(3))
    for r in RESIDENCIES:
        if _subseq(r.replace(" ", ""), caps):
            return m.group(1), m.group(2), r, m.group(4), m.group(5), m.group(6)
    return None


def parse_bonus(data):
    """Rows keyed (item, code, residency, raw points). Some PDFs overlap a wrapped note with the residency
    column (interleaved text); a second pass with a tight y tolerance recovers most of those rows."""
    rows, bad = {}, {}
    passes = [3, 1] if data[:4] == b"%PDF" else [3]
    for ytol in passes:
        for line in pdf_lines(data, ytol):
            m = BON_RE.match(line)
            g = (m.group(1), m.group(2), m.group(4), m.group(5), m.group(6), m.group(7)) if m else untangle(line)
            if not g:
                if re.search(r"\d{3}-\d{2}", line) and " TOTAL " not in line and "TOTAL " not in line[:20]:
                    bad.setdefault(ytol, []).append(line)
                continue
            item = re.sub(r"\s+-\s+ARCHERY ONLY$", "", g[0].strip())
            item = re.sub(r"\s+LICENSE$", "", item)
            key = (item, g[1], g[2], g[3])
            if key not in rows:
                rows[key] = (int(g[4]), int(g[5]))
    out = {}
    for (item, code, res, pts), (apps, succ) in rows.items():
        # some years print the 0-point group with a blank points cell -> counted as 0 points
        q = out.setdefault((item, code), {}).setdefault(res, {}).setdefault(int(pts or 0), [0, 0])
        q[0] += apps; q[1] += succ
    # report lines still unmatched after all passes (first pass list, filtered to codes never parsed)
    got = {(k[0], k[1]) for k in rows}
    left = [l for l in bad.get(3, []) if not any(c == re.search(r"\d{3}-\d{2}", l).group(0) for _, c in got)
            or re.search(r"[a-z][A-Z]", l)]
    return out, left[:50], len(rows)


def parse_combo(data, url):
    """Text like:
    General Big Game/Elk Combo Primary Drawing Stats / 2026 Regular (Total apps 29,892)
    2.2 – 3 PP 100% Draw (5,377 apps) / 2 PP 75.77% Draw (9,609 apps, 7,281 successful)"""
    res = {}
    sec, year, pool = None, None, None
    for line in pdf_lines(data):
        l = line.replace(",", "")
        low = l.lower()
        if "deer combo" in low:
            sec = "D"; year = None; continue
        if "big game" in low or "elk combo" in low:
            sec = "E"; year = None; continue
        m = re.match(r"^(\d{4})\b(.*)", l)
        if m and not re.search(r"\d\s*PP\b", l, re.I):
            year = int(m.group(1)); pool = "landowner" if "landowner" in low else "regular"
            if pool == "regular" and sec:
                t = re.search(r"total apps\s*(\d+)", low)
                res.setdefault((sec, year), {"rows": []})
                if t:
                    res[(sec, year)]["apps"] = int(t.group(1))
            continue
        l2 = re.sub(r"\s+", " ", l.replace("–", "-"))
        m = re.match(r"^([\d.]+)\s*(?:-\s*([\d.]+))?\s*PP\s*([\d.]+)\s*%\s*(?:Draw)?\s*\(\s*(\d+)\s*apps?"
                     r"\s*(?:/?\s*(\d+)\s*(?:successful|combos ?available|available))?", l2, re.I)
        if m and sec and year and pool == "regular":
            lo, hi, pct, apps = float(m.group(1)), m.group(2), float(m.group(3)), int(m.group(4))
            hi = float(hi) if hi else lo
            lo, hi = min(lo, hi), max(lo, hi)
            if m.group(5):
                succ = int(m.group(5))
            elif pct in (100.0, 0.0):
                succ = apps if pct == 100.0 else 0
            else:
                succ = None
            res[(sec, year)]["rows"].append((lo, hi, apps, succ, line))
    return res


def bucket(points_dict):
    ks = sorted(points_dict, reverse=True)
    return [[k, points_dict[k][0], points_dict[k][1]] for k in ks if points_dict[k][0]]


def parse():
    out = {"state": "MT", "system": "bonus_sq", "point_label": "bonus points", "sources": [], "hunts": []}
    LOG.append("Permits/licenses: apps/drawn = REGULAR-pool 1st choice (landowner-preference pool excluded from R/NR, "
               "included in T). NR.tags = nonresident cap (QTA) in the regular pool; T.tags = total quota. "
               "by_pts from Detailed Bonus Point reports (1st choice, landowner rows excluded; blank points cell = 0). UNL/99999 quotas omitted.")
    reps = report_list()
    LOG.append(f"repository: {len(reps)} reports listed")
    stats, bonus, combos = [], [], []
    for url, title, animal in reps:
        c = classify(title)
        if not c:
            continue
        y, kind, item = c
        (stats if kind == "stats" else bonus if kind == "bonus" else combos).append((y, item, url, title))
    hunts = {}

    def hunt(item, code, note):
        sp, sex = ITEMS[item]
        key = (sp, item, code)
        if key not in hunts:
            low = note.lower()
            e = {"id": code, "species": sp, "units": [code.split("-")[0]], "label": f"{item.title()} {code} {note}".strip(),
                 "weapon": "archery" if "archery" in low else "any", "kind": "limited", "years": {}}
            if sex:
                e["sex"] = sex
            hunts[key] = e
        return hunts[key]

    # bonus first: index by (year, item, code)
    bon = {}
    for y, _, url, title in sorted(bonus):
        try:
            d, bad, cnt = parse_bonus(get(url).content)
        except Exception as e:
            LOG.append(f"FAIL bonus {y} {title} {url}: {e}"); continue
        for (item, code), v in d.items():
            bon[(y, item, code)] = v
        LOG.append(f"{y} {title}: {url} -> {cnt} rows, {len(d)} LPTs")
        for b in bad[:20]:
            LOG.append(f"  unparsed: {b}")
        time.sleep(1)
    for y, item, url, title in sorted(stats):
        try:
            rows, bad = parse_stats(get(url).content, item)
        except Exception as e:
            LOG.append(f"FAIL stats {y} {title} {url}: {e}"); continue
        out["sources"].append({"year": y, "species": ITEMS[item][0], "url": url, "title": title})
        for code, r in rows.items():
            h = hunt(item, code, r["note"])
            R = {"apps": r["r"][0], "drawn": r["r"][1]}
            NR = {"apps": r["nr"][0], "drawn": r["nr"][1]}
            T = {"apps": r["r"][0] + r["nr"][0] + (r["lo_r"][0] or 0) + (r["lo_nr"][0] or 0),
                 "drawn": r["r"][1] + r["nr"][1] + (r["lo_r"][1] or 0) + (r["lo_nr"][1] or 0)}
            if r["quota"] is not None:
                T["tags"] = r["quota"]
            if r["nr_qta"] is not None:
                NR["tags"] = r["nr_qta"]
            b = bon.get((y, item, code))
            if b:
                if b.get("RESIDENT"): R["by_pts"] = bucket(b["RESIDENT"])
                if b.get("NONRESIDENT"): NR["by_pts"] = bucket(b["NONRESIDENT"])
            h["years"][str(y)] = {"R": R, "NR": NR, "T": T}
        LOG.append(f"{y} {title}: {url} -> {len(rows)} LPTs")
        for b in bad[:30]:
            LOG.append(f"  unparsed: {b}")
        time.sleep(1)
    # general NR combos (preference points)
    combo_data = {}
    for y, _, url, title in sorted(combos):
        try:
            d = parse_combo(get(url).content, url)
        except Exception as e:
            LOG.append(f"FAIL combo {y} {title} {url}: {e}"); continue
        LOG.append(f"{y} {title}: {url} -> {sorted(d)}")
        out["sources"].append({"year": y, "species": "E", "url": url, "title": title})
        for k, v in d.items():
            if v["rows"] and (k not in combo_data or k[1] == y):
                combo_data[k] = v
        time.sleep(1)
    for sp, cid, label in (("E", "NR-BGC", "Nonresident Big Game / Elk Combination (general)"),
                           ("D", "NR-DC", "Nonresident Deer Combination (general)")):
        e = {"id": cid, "species": sp, "units": ["General"], "label": label, "weapon": "any", "kind": "general",
             "years": {}}
        for (s2, y), v in sorted(combo_data.items()):
            if s2 != sp or y not in YEARS:
                continue
            rows = []
            for lo, hi, apps, succ, line in v["rows"]:
                if succ is None:
                    LOG.append(f"  combo row without success count: {line}"); continue
                rows.append([int(hi), apps, succ])  # point range lo-hi recorded at int(hi)
            rows.sort(key=lambda r: -r[0])
            NR = {"apps": v.get("apps", sum(r[1] for r in rows)), "drawn": sum(r[2] for r in rows), "by_pts": rows}
            pref = [r[0] for r in rows if r[2] > 0 and r[0] > 0]
            if pref:
                NR["min_pts"] = min(pref)
            e["years"][str(y)] = {"NR": NR}
        if e["years"]:
            hunts[(sp, cid, cid)] = e
    LOG.append("General combos: system is preference points; point ranges (party averages, e.g. '2.2-3 PP') are "
               "recorded at the integer upper bound; min_pts ignores the 0-point random pool.")
    out["hunts"] = sorted(hunts.values(), key=lambda h: (h["species"], h["id"]))
    for sp in "EDP":
        LOG.append(f"species {sp}: {sum(1 for h in out['hunts'] if h['species'] == sp)} hunts")
    return out
