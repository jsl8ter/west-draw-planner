"""Season dates per hunt -> h["season"] = {"y": 2026, "r": [[label, "MM-DD", "MM-DD"], ...], "src": "..."}

Sources (all official, already in the repo):
  CO  2026 big game brochure hunt-code tables (data/draw/probe/CO/brochure_tables_2026.txt); hunts without their
      own dates use the brochure's standard season dates for their season code (archery, muzzleloader, rifle 1-4)
  WY  2026 hunting season tables (data/draw/regs/WY_text.txt, rotated pages): archery + regular season by area/type
  UT  2026 hunt season from utahdraws.com (data/draw/raw/UT/2026_*.json)
  AZ  hunt dates in the draw report / regulations label; ID and NV: dates in the draw report label
  OR  2026 regulation tables "Open Season" (data/draw/regs/OR_tables.json)
  MT  2026 regulations permit lines (data/draw/regs/MT_text.txt); combos use the general season
  NM  hunt rules 19.31 NMAC (data/draw/regs/NM_text.txt) when present
"""
import json, os, re, glob
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
MD = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s*(\d{1,2})"


def md(m, d):
    return f"{MON[m[:3].lower()]:02d}-{int(d):02d}"


def ranges(text):
    """'Oct. 24–Nov. 1', 'Sep. 2–30', 'Aug. 15 - Aug. 23', 'Oct 24-Nov 29' -> [("10-24","11-01"), ...]"""
    out = []
    for m in re.finditer(MD + r"\s*[–\-—]\s*(?:" + MD + r"|(\d{1,2})\b)", text or ""):
        a = md(m.group(1), m.group(2))
        b = md(m.group(3), m.group(4)) if m.group(3) else md(m.group(1), m.group(5))
        out.append((a, b))
    return out


# ---------------- Colorado ----------------
CO_STD = {   # 2026 standard dates (brochure p.2), by species group and method / rifle season number
    "ED": {"A": ("09-02", "09-30"), "M": ("09-12", "09-20"), 1: ("10-14", "10-18"), 2: ("10-24", "11-01"), 3: ("11-07", "11-15"), 4: ("11-18", "11-22")},
    "P": {"A": ("08-15", "09-20"), "M": ("09-21", "09-29"), "R": ("10-03", "10-11")},
}
_co = None


def co_table():
    global _co
    if _co is not None: return _co
    _co = {}
    p = os.path.join(ROOT, "data", "draw", "probe", "CO", "brochure_tables_2026.txt")
    if not os.path.exists(p): return _co
    for line in open(p, encoding="utf-8", errors="replace"):
        cells = [c.strip().strip("'\"") for c in line.split(" | ")]
        for i, c in enumerate(cells):
            m = re.fullmatch(r"([DEA]-[MFE]-\d{3}-[A-Z0-9]{2}-[A-Z])", c)
            if not m: continue
            for j in range(i - 1, max(-1, i - 4), -1):
                r = ranges(cells[j].replace("\\n", " "))
                if r: _co.setdefault(m.group(1), r); break
    return _co


def season_co(h):
    m = re.match(r"^([DEA])-[MFE]-\d{3}-([A-Z0-9]{2})-([A-Z])$", h["id"])
    if not m: return None
    sp, sea, meth = m.groups()
    r = co_table().get(h["id"])
    lab = {"A": "Archery", "M": "Muzzleloader", "R": "Rifle", "X": "Season"}.get(meth, "Season")
    if r: return {"y": 2026, "r": [[lab, a, b] for a, b in r], "src": "CPW 2026 brochure"}
    if sp == "A":
        d = CO_STD["P"].get(meth)
    else:
        n = int(sea[1]) if sea[1].isdigit() else 0
        d = CO_STD["ED"].get(meth) if meth in "AM" else CO_STD["ED"].get(n)
        if meth == "R" and n: lab = f"Rifle {n}{['st','nd','rd','th'][min(n,4)-1]} season"
    return {"y": 2026, "r": [[lab, d[0], d[1]]], "src": "CPW 2026 standard season dates"} if d else None


# ---------------- Wyoming ----------------
_wy = None


def wy_table():
    global _wy
    if _wy is not None: return _wy
    _wy = {}
    p = os.path.join(ROOT, "data", "draw", "regs", "WY_text.txt")
    if not os.path.exists(p): return _wy
    D = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.? \d{1,2}"
    ROW = re.compile(rf"(?<![\d,])(\d{{1,3}}) (\d|Gen) ((?:{D} ){{2,4}})")
    sp = None
    for page in open(p, encoding="utf-8", errors="replace").read().split("\n===== "):
        if "[rotated" not in page: continue
        m = re.search(r"\b(ANTELOPE|DEER|ELK)\b", page)
        if not m: continue
        sp = {"ANTELOPE": "P", "DEER": "D", "ELK": "E"}[m.group(1)]
        for line in page.splitlines():
            for r in ROW.finditer(line):
                ds = re.findall(D, r.group(3))
                if r.group(2) == "Gen": continue
                k = f"{sp}-{int(r.group(1)):03d}-{r.group(2)}"
                parts = [md(*re.match(r"(\w+)\.? (\d+)", x).groups()) for x in ds]
                rr = [["Archery", parts[0], parts[1]], ["Regular", parts[2], parts[3]]] if len(parts) == 4 else [["Regular", parts[0], parts[1]]]
                _wy.setdefault(k, rr)
    return _wy


# ---------------- Utah ----------------
_ut = None


def ut_table():
    global _ut
    if _ut is not None: return _ut
    _ut = {}
    for f in glob.glob(os.path.join(ROOT, "data", "draw", "raw", "UT", "20??_*.json")):
        y = int(os.path.basename(f)[:4])
        try: data = json.load(open(f)).get("Data") or []
        except Exception: continue
        for a in data:
            rr = []
            for s in a.get("SeasonWeapons") or []:
                if s.get("UnCertainDateRange"): continue
                a1, b1 = (s.get("SeasonStartDate") or "")[5:10], (s.get("SeasonEndDate") or "")[5:10]
                if a1 and b1: rr.append([s.get("WeaponName") or "Season", a1, b1])
            if rr and (a.get("HuntCode") not in _ut or _ut[a["HuntCode"]]["y"] < y):
                _ut[a["HuntCode"]] = {"y": y, "r": rr, "src": "utahdraws.com"}
    return _ut


# ---------------- Oregon ----------------
_or = None


def or_table():
    global _or
    if _or is not None: return _or
    _or = {}
    p = os.path.join(ROOT, "data", "draw", "regs", "OR_tables.json")
    if not os.path.exists(p): return _or
    for page, tbls in json.load(open(p)).items():
        for t in tbls:
            hdr = None
            for r in t["rows"]:
                low = [c.lower() for c in r]
                if low and low[0].startswith("hunt"): hdr = low; continue
                if not hdr: continue
                m = re.match(r"^((?:[A-Z]{2}\d{3}|\d{3})[A-Z0-9-]*)\*?$", (r[0] if r else "").replace(" ", ""))
                if not m: continue
                row = dict(zip(hdr, r))
                rr = ranges(next((v for k, v in row.items() if "season" in k), ""))
                if rr: _or.setdefault(m.group(1), rr)
    return _or


# ---------------- Montana ----------------
_mt = None
MT_LAB = {"09-05": "Archery", "10-24": "General", "12-12": "Muzzleloader"}


def mt_table():
    global _mt
    if _mt is not None: return _mt
    _mt = {}
    p = os.path.join(ROOT, "data", "draw", "regs", "MT_text.txt")
    if not os.path.exists(p): return _mt
    for line in open(p, encoding="utf-8", errors="replace"):
        m = re.match(r"^(Elk|Deer|Antelope) (?:B )?(?:Permit|License|B License):\s*(\d{3}-\d{2})\b(.*)$", line.strip())
        if not m: continue
        sp = {"Elk": "E", "Deer": "D", "Antelope": "P"}[m.group(1)]
        rr = []
        for a, b in re.findall(r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.? \d{1,2})-((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.? \d{1,2})", m.group(3)):
            x, y = md(*re.match(r"(\w+)\.? (\d+)", a).groups()), md(*re.match(r"(\w+)\.? (\d+)", b).groups())
            rr.append([MT_LAB.get(x, "Season"), x, y])
        if rr: _mt.setdefault(f"{sp}:{m.group(2)}", rr)
    return _mt


# ---------------- New Mexico ----------------
_nm = None


def nm_table():
    """19.31 NMAC hunt tables: columns '2023-2024 hunt dates' ... '2026-2027 hunt dates', 'hunt code'. Uses the
    latest license-year column; a hunt opening Jan-Apr falls in the next calendar year."""
    global _nm
    if _nm is not None: return _nm
    _nm = {}
    p = os.path.join(ROOT, "data", "draw", "regs", "NM_tables.json")
    if not os.path.exists(p): return _nm
    for page, tbls in json.load(open(p)).items():
        for t in tbls:
            hdr = None
            for r in t["rows"]:
                low = [c.lower() for c in r]
                if any("hunt code" == c for c in low): hdr = low; continue
                if not hdr or len(r) < len(hdr): continue
                ci = hdr.index("hunt code")
                dcols = [(int(re.match(r"(\d{4})", c).group(1)), i) for i, c in enumerate(hdr) if re.match(r"\d{4}-\d{4} hunt dates", c)]
                if not dcols: continue
                y, di = max(dcols)
                code = r[ci].strip()
                rr = []
                for m in re.finditer(r"(\d{1,2})/(\d{1,2})(?:/\d{4})?\s*-\s*(\d{1,2})/(\d{1,2})", r[di]):
                    rr.append(["Season", f"{int(m.group(1)):02d}-{int(m.group(2)):02d}", f"{int(m.group(3)):02d}-{int(m.group(4)):02d}"])
                if rr and re.match(r"^(ELK|DER|ANT)-\d-\d{3}$", code):
                    yy = y + 1 if int(rr[0][1][:2]) <= 4 else y
                    _nm.setdefault(code, {"y": yy, "r": rr, "src": "19.31 NMAC hunt rules"})
    return _nm


def from_label(st, h):
    lab = h.get("label") or ""
    if st == "AZ":
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})-(\d{1,2})/(\d{1,2})/(\d{4})", lab)
        if m: return {"y": int(m.group(3)), "r": [["Season", f"{int(m.group(1)):02d}-{int(m.group(2)):02d}", f"{int(m.group(4)):02d}-{int(m.group(5)):02d}"]], "src": "AZGFD draw report"}
    if st == "ID":
        m = re.search(r"\((\d{1,2})/(\d{1,2})/(\d{2})-(\d{1,2})/(\d{1,2})/(\d{2})\)", lab)
        if m: return {"y": 2000 + int(m.group(3)), "r": [["Season", f"{int(m.group(1)):02d}-{int(m.group(2)):02d}", f"{int(m.group(4)):02d}-{int(m.group(5)):02d}"]], "src": "IDFG hunt planner"}
    if st == "NV":
        segs = re.findall(MD + r"(?:,\s*(\d{4}))?\s*-\s*" + MD + r"(?:,\s*(\d{4}))?", lab)
        if segs:
            y = next((int(s[2]) for s in segs if s[2]), max(int(x) for x in h["years"]))
            return {"y": y, "r": [["Season", md(s[0], s[1]), md(s[3], s[4])] for s in segs], "src": "NDOW draw results"}
    return None


def season_for(st, h):
    if st == "CO": return season_co(h)
    if st == "WY":
        r = wy_table().get(re.sub(r"-S$", "", h["id"]))
        return {"y": 2026, "r": r, "src": "WGFD 2026 regulations"} if r else None
    if st == "UT": return ut_table().get(h["id"])
    if st == "OR":
        r = or_table().get(h["id"])
        return {"y": 2026, "r": [["Season", a, b] for a, b in r], "src": "ODFW 2026 regulations"} if r else None
    if st == "MT":
        if h.get("kind") == "general":
            return {"y": 2026, "r": [["Archery", "09-05", "10-18"], ["General", "10-24", "11-29"]], "src": "FWP 2026 regulations"}
        r = mt_table().get(f"{h['species']}:{h['id']}")
        return {"y": 2026, "r": r, "src": "FWP 2026 regulations"} if r else None
    if st == "NM":
        return nm_table().get(re.sub(r" \(\d{4}\)$", "", h["id"]))
    return from_label(st, h)


def annotate(st, d):
    n = 0
    for h in d["hunts"]:
        s = season_for(st, h)
        if s: h["season"] = s; n += 1
        else: h.pop("season", None)
    d.setdefault("notes", {})["season"] = f"{n}/{len(d['hunts'])} hunts with season dates"
    return d
