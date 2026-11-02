"""Colorado (CPW) elk / deer / pronghorn primary draw statistics.

Source: CPW "Primary Draw Recap" (Post Draw Report) PDFs, one per species and year, linked as
"<year> Draw Recap Report" on the CPW elk / deer / pronghorn statistics pages and hosted on cpw.widen.net
(the share page links to the PDF via /content/<id>/original/<name>.pdf?...download=true).

Each hunt code has a block:
  * Total Quota, # Drawn (total, balance, adult res, adult nonres, youth res, youth nonres, LPP unrestricted,
    LPP restricted), general first-choice applicants,
  * "Drawn Out At" per column (preference points of the last level drawn in the preference pass),
  * a table by preference point level of first-choice pre-draw applicants and post-draw successful,
    per column, followed by Total Choice 1..4 lines.
Output per hunt/year:
  T.tags = Total Quota; T.drawn = # Drawn (all choices, incl. landowner LPP); T.apps = general 1st-choice apps
  R / NR: apps = 1st-choice applicants (adult + youth), drawn = 1st-choice successful (adult + youth),
          by_pts = [points, 1st-choice applicants, 1st-choice successful] (adult + youth),
          min_pts = adult "Drawn Out At" preference points (when the hunt drew out in the preference pass on
          choice 1; when it is "Choice N" every 1st-choice applicant drew and min_pts = lowest level drawn).
  R/NR quotas are not fixed before the draw (CPW prints "Determined by Draw"), so only T.tags is given.
"""
import io, os, re, sys, time, tempfile, concurrent.futures as cf
import requests, pdfplumber

LOG = []
DIAG = []
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) west-draw-planner/1.0"}
PAGES = {
    "E": "https://cpw.state.co.us/activities/hunting/big-game/hunting-elk/elk-statistics",
    "D": "https://cpw.state.co.us/activities/hunting/big-game/hunting-deer/deer-statistics",
    "P": "https://cpw.state.co.us/activities/hunting/big-game/hunting-pronghorn/pronghorn-statistics",
}
SPLETTER = {"E": "E", "D": "D", "A": "P"}
NYEARS = int(os.environ.get("CO_YEARS", "5"))
ONLY = []  # debug subset of (year, species); empty = all
BUDGET = float(os.environ.get("CO_BUDGET_MIN", "48")) * 60
CODE = re.compile(r"^([EDA])([EMF])(\d{3})([A-Z]\d)([A-Z])$")
COLS = ["RA", "NA", "RY", "NY", "LU", "LR"]
SEASONS = {"O1": "1st season", "O2": "2nd season", "O3": "3rd season", "O4": "4th season"}
METHOD = {"R": "rifle", "A": "archery", "M": "muzzleloader"}
SEX = {"M": "male", "F": "female", "E": "either"}
SPNAME = {"E": "elk", "D": "deer", "A": "pronghorn"}


def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=300, **kw)
    r.raise_for_status()
    return r


def find_reports():
    out = []
    for sp, page in PAGES.items():
        try:
            txt = get(page).text
        except Exception as e:
            LOG.append(f"page error {page}: {e}"); continue
        for href, label in re.findall(r'href="([^"]+)"[^>]*>\s*([^<]{0,80}?)\s*<', txt):
            m = re.match(r"(20\d\d) Draw Recap Report$", label.strip())
            if m:
                out.append((int(m.group(1)), sp, href))
    LOG.append(f"recap links found: {sorted((y, s) for y, s, _ in out)}")
    return out


def pdf_url(share):
    if share.lower().split("?")[0].endswith(".pdf"):
        return share
    txt = get(share).text
    m = re.search(r'(/content/[^"\s]+?download=true)', txt)
    if not m:
        m = re.search(r'(https://[^"\s]+\.pdf[^"\s]*)', txt)
        if not m:
            raise RuntimeError("no pdf link on share page")
        return m.group(1).replace("&amp;", "&")
    return "https://cpw.widen.net" + m.group(1).replace("&amp;", "&")


def _line(words, top, tol=3.5):
    return sorted([w for w in words if abs(w["top"] - top) <= tol], key=lambda w: w["x0"])


def drawn_out(page):
    """Map column -> text of the 'Drawn Out At' cell, using word x positions."""
    words = page.extract_words()
    dtop = None
    for w in words:
        if w["text"] == "Drawn":
            ln = _line(words, w["top"])
            j = ln.index(w)
            if j + 2 < len(ln) and ln[j + 1]["text"] == "Out" and ln[j + 2]["text"] == "At":
                dtop = w["top"]; dx = ln[j + 2]["x1"]; break
    if dtop is None:
        if len(DIAG) < 8:
            DIAG.append("drawn_out: label not found")
        return {}
    cands = [w for w in words if w["text"] == "Restricted" and w["top"] < dtop - 2]
    if not cands:
        if len(DIAG) < 8:
            DIAG.append("drawn_out: no header above")
        return {}
    last = max(cands, key=lambda w: w["top"])
    ln = _line(words, last["top"])
    j = ln.index(last)
    seq = ln[j - 5:j + 1] if j >= 5 else []
    if [w["text"] for w in seq] != ["Res", "NonRes", "Res", "NonRes", "Unrestricted", "Restricted"]:
        if len(DIAG) < 8:
            DIAG.append("drawn_out: header " + " ".join(w["text"] for w in ln))
        return {}
    htop = last["top"]
    centers = [(w["x0"] + w["x1"]) / 2 for w in seq]
    ends = [w["top"] for w in words if w["text"] == "#" and w["top"] > dtop + 2]
    end = min(ends) if ends else dtop + 30
    cells = {c: [] for c in COLS}
    for w in words:
        if not (htop + 3 < w["top"] < end - 2):
            continue
        if w["x1"] <= dx + 1:
            continue
        xc = (w["x0"] + w["x1"]) / 2
        k = min(range(6), key=lambda j: abs(centers[j] - xc))
        cells[COLS[k]].append((round(w["top"]), w["x0"], w["text"]))
    out = {c: " ".join(x[2] for x in sorted(v)) for c, v in cells.items()}
    return out


def work(args):
    path, start, stop = args
    res = []
    with pdfplumber.open(path) as pdf:
        for k in range(start, stop):
            p = pdf.pages[k]
            txt = p.extract_text() or ""
            do = drawn_out(p) if "Drawn Out At" in txt else {}
            res.append((k, txt, do))
            if hasattr(p, "close"):
                p.close()
    return res, DIAG[:]


def tok(x):
    return 0 if x == "-" else int(x)


def parse_pages(pages, year, sp, bad):
    hunts = {}
    cur = None
    for k, txt, do in pages:
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        for idx, ln in enumerate(lines):
            toks = ln.split()
            if toks and all(re.fullmatch(r"[A-Z]{2}\d{3,5}[A-Z0-9]{1,4}", x) for x in toks):
                if not CODE.match(toks[0]):
                    cur = None  # statewide / summary block
                    continue
                ln = toks[0]
                cur = hunts.setdefault(ln, {"code": ln, "rows": [], "do": {}, "tot": None, "quota": None,
                                            "drawn8": None, "apps": None, "c1": None,
                                            "also": [x for x in toks[1:] if CODE.match(x)]})
                if do and not cur["do"]:
                    cur["do"] = do
                continue
            if cur is None:
                continue
            m = re.match(r"^(\d+) LPP Restricted", ln)
            if m:
                if cur["quota"] is None:
                    cur["quota"] = int(m.group(1))
                else:
                    cur["dup"] = cur.get("dup", 0) + 1
                    if len(DIAG) < 4:
                        DIAG.append(f"{year} {sp} second quota block under {cur['code']} page {k+1}: " + " / ".join(lines[:14]))
                continue
            if cur.get("closed"):
                continue
            m = re.search(r"Total Choice 1 (\d+) (\d+)", ln)
            if m and cur["apps"] is None and not re.match(r"^Total Choice 1 (\S+ ){6}Total Choice 1", ln):
                cur["apps"] = int(m.group(1))
                # 2023/2024 layout: post-draw numbers on the same line
                tail = re.findall(r"\d+", ln[m.end():])
                if len(tail) >= 8 and cur["drawn8"] is None:
                    cur["drawn8"] = [int(x) for x in tail[-8:]]
                continue
            if cur["drawn8"] is None and cur["quota"] is not None:
                if re.fullmatch(r"(\d+ ){7}\d+", ln):
                    cur["drawn8"] = [int(x) for x in ln.split()]
                    continue
            m = re.match(r"^Total Choice 1 ((?:[\d-]+ ){6})Total Choice 1 ((?:[\d-]+ ?){6})$", ln)
            if m:
                if cur["c1"] is None:
                    cur["c1"] = ([tok(x) for x in m.group(1).split()], [tok(x) for x in m.group(2).split()])
                cur["closed"] = True
                continue
            t = ln.split()
            if all(re.fullmatch(r"\d+|-", x) for x in t) and len(t) in (14, 16):
                if len(t) == 16:
                    if t[0] == "1" and t[8] == "1":
                        t = t[1:8] + t[9:]
                    else:
                        bad.append(f"{cur['code']}: {ln}"); continue
                if t[0] == t[7] and t[0] != "-":
                    cur["rows"].append((int(t[0]), [tok(x) for x in t[1:7]], [tok(x) for x in t[8:14]]))
                else:
                    bad.append(f"{cur['code']}: {ln}")
    return hunts


def pts_of(cell):
    m = re.match(r"^(\d+) Pref Points\b", cell or "")
    return int(m.group(1)) if m else None


def build(h, bad):
    out = {}
    if h["quota"] is not None:
        out["T"] = {"tags": h["quota"]}
    if h["drawn8"]:
        d = h["drawn8"]
        out.setdefault("T", {})["drawn"] = d[0]
    if h["apps"] is not None:
        out.setdefault("T", {})["apps"] = h["apps"]
    rows = {}
    for pts, pre, post in h["rows"]:
        if pts in rows:  # duplicated line across a page break
            continue
        rows[pts] = (pre, post)
    for res, (a, y), dcol in (("R", (0, 2), 2), ("NR", (1, 3), 3)):
        by = [[p, pre[a] + pre[y], post[a] + post[y]] for p, (pre, post) in sorted(rows.items(), reverse=True)]
        by = [r for r in by if r[1] or r[2]]
        o = {}
        if h["c1"]:
            o["apps"] = h["c1"][0][a] + h["c1"][0][y]
            o["drawn"] = h["c1"][1][a] + h["c1"][1][y]
        elif rows:
            o["apps"] = sum(r[1] for r in by); o["drawn"] = sum(r[2] for r in by)
        if by:
            o["by_pts"] = by
            if "apps" in o and sum(r[1] for r in by) != o["apps"]:
                bad.append(f"{h['code']} {res}: by_pts apps {sum(r[1] for r in by)} != total {o['apps']}")
        cell = (h["do"] or {}).get("RA" if res == "R" else "NA", "")
        mp = pts_of(cell)
        if mp is not None:
            o["min_pts"] = mp
        elif cell.startswith("Choice") and by:
            drew = [r[0] for r in by if r[2] > 0]
            if drew:
                o["min_pts"] = min(drew)
        if o.get("apps") or o.get("drawn"):
            out[res] = o
    return out


def dash(code):
    m = CODE.match(code)
    return "-".join(m.groups())


def label(code):
    m = CODE.match(code)
    s, sex, gmu, season, meth = m.groups()
    return f"GMU {int(gmu)} {SPNAME[s]} {SEX[sex]} - {METHOD.get(meth, meth)} {SEASONS.get(season, season)}"


BROCHURE_DUMP = True


def _dump_brochure():
    url = "https://cpw.widen.net/s/5wvx7rggrd/colorado-big-game-hunting-brochure"
    data = get(url).content
    if not data.startswith(b"%PDF"):
        url = pdf_url(url); data = get(url).content
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    d = os.path.join(root, "data", "draw", "probe", "CO"); os.makedirs(d, exist_ok=True)
    out = [f"URL {url} bytes {len(data)}"]
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, pg in enumerate(pdf.pages):
            t = pg.extract_text() or ""
            out.append(f"\n===== PAGE {i+1} =====\n{t}")
            if i in (31, 45):
                for tb in pg.extract_tables()[:3]:
                    out.append("--- TABLE ---\n" + "\n".join(" | ".join(str(c) for c in r) for r in tb[:25]))
    open(os.path.join(d, "brochure_2026.txt"), "w").write("\n".join(out))
    raise RuntimeError("brochure dump only")


def parse():
    if BROCHURE_DUMP:
        _dump_brochure()
    t0 = time.time()
    reps = find_reports()
    by_sp = {}
    for y, sp, href in reps:
        by_sp.setdefault(sp, []).append((y, href))
    jobs = []
    for sp, lst in by_sp.items():
        for y, href in sorted(set(lst), reverse=True)[:NYEARS]:
            if not ONLY or (y, sp) in ONLY:
                jobs.append((y, sp, href))
    jobs.sort(key=lambda j: (-j[0], j[1]))  # newest first so a time cut drops the oldest
    hunts, sources, bad_all = {}, [], []
    ncpu = max(2, os.cpu_count() or 2)
    for y, sp, href in jobs:
        if time.time() - t0 > BUDGET:
            LOG.append(f"time budget reached, skipping {y} {sp}"); continue
        try:
            url = pdf_url(href)
            data = get(url).content
        except Exception as e:
            LOG.append(f"download error {y} {sp} {href}: {e}"); continue
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(data); tmp.close()
        with pdfplumber.open(tmp.name) as pdf:
            n = len(pdf.pages)
            title = " ".join((pdf.pages[0].extract_text() or "").split("\n")[0:8])
        ttl = re.search(r"(20\d\d) Primary (\w+) Post Draw Report", title)
        if ttl and int(ttl.group(1)) != y:
            LOG.append(f"note: {href} labelled {y} but titled {ttl.group(1)}")
        step = 40
        chunks = [(tmp.name, s, min(n, s + step)) for s in range(0, n, step)]
        pages = []
        import importlib
        fn = importlib.import_module(__name__).work  # picklable reference
        with cf.ProcessPoolExecutor(ncpu) as ex:
            for r, dg in ex.map(fn, chunks):
                pages.extend(r)
                for x in dg:
                    if x not in DIAG and len(DIAG) < 12:
                        DIAG.append(x)
        os.unlink(tmp.name)
        pages.sort()
        bad = []
        hs = parse_pages(pages, y, sp, bad)
        nh = 0
        for code, h in hs.items():
            s = SPLETTER[code[0]]
            if s != sp:
                bad.append(f"{code}: species letter does not match report {sp}")
                continue
            yd = build(h, bad)
            if not yd:
                continue
            m = CODE.match(code)
            hid = dash(code)
            H = hunts.setdefault(hid, {"id": hid, "species": sp, "units": [str(int(m.group(3)))],
                                       "label": label(code), "weapon": METHOD.get(m.group(5), "other"),
                                       "sex": SEX[m.group(2)], "kind": "limited", "years": {}})
            if h.get("also"):
                if "shared" not in H["label"]:
                    H["label"] += " (quota shared with " + ", ".join(dash(x) for x in h["also"]) + ")"
                for x in h["also"]:
                    u = str(int(CODE.match(x).group(3)))
                    if u not in H["units"]:
                        H["units"].append(u)
            H["years"][str(y)] = yd
            nh += 1
        sources.append({"year": y, "species": sp, "url": url, "title": f"{y} Primary {SPNAME['A' if sp=='P' else sp]} Post Draw Report (draw recap)"})
        LOG.append(f"{url} | {y} {sp} | pages {n} hunts {nh} unparsed {len(bad)} | {time.time()-t0:.0f}s")
        bad_all += [f"  {y} {sp} {b}" for b in bad]
    LOG.extend(DIAG)
    LOG.append(f"unparsed/mismatch rows total {len(bad_all)} (first 50):")
    LOG.extend(bad_all[:50])
    out = sorted(hunts.values(), key=lambda h: h["id"])
    LOG.append(f"hunts: E {sum(h['species']=='E' for h in out)} D {sum(h['species']=='D' for h in out)} P {sum(h['species']=='P' for h in out)}")
    LOG.append("apps = 1st-choice applicants (adult + youth); T.drawn = all licenses drawn incl. landowner and later choices.")
    return {"state": "CO", "system": "pref", "point_label": "preference points",
            "sources": sorted(sources, key=lambda s: (s["year"], s["species"])), "hunts": out}
