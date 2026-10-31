"""New Mexico draw statistics from NMDGF "Big Game Drawing Odds Complete Report" workbooks.

Each workbook has one sheet: left block = pre-draw applicants (Hunt Total / Resident / Non-Resident /
Outfitter by choice), right block = post-draw successful applicants by choice for the same groups.
Columns shift slightly between years, so positions are located from the header row.
"""
import io, re, requests, openpyxl
from collections import Counter

LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SOURCES = [
    (2026, "https://wildlife.dgf.nm.gov/download/2026-big-game-drawing-odds-complete-report/?wpdmdl=56113", "2026 Big Game Drawing Odds Complete Report"),
    (2025, "https://wildlife.dgf.nm.gov/download/2025-drawing-odds-complete-report/?wpdmdl=52046", "2025 Drawing Odds Complete Report"),
    (2024, "https://wildlife.dgf.nm.gov/download/2024-drawing-odds-complete-report/?wpdmdl=48997", "2024 Drawing Odds Complete Report"),
    (2023, "https://wildlife.dgf.nm.gov/download/2023-big-game-draw-odds-complete-report/?wpdmdl=48734", "2023 Big Game Draw Odds Complete Report"),
    (2022, "https://wildlife.dgf.nm.gov/download/2022-big-game-draw-odds-complete-report/?wpdmdl=48730", "2022 Big Game Draw Odds Complete Report"),
]
CODE = re.compile(r"^(ELK|DER|ANT)-(\d)-(\d{3})$")
SPECIES = {"ELK": "E", "DER": "D", "ANT": "P"}
SKIP = re.compile(r"youth|landowner|auction|raffle|enhancement|private land only|ranch only", re.I)
DEBUG = Counter()


def s(v):
    return "" if v is None else str(v).strip()


def num(v):
    if v is None or s(v) == "": return 0
    try: return int(round(float(str(v).replace(",", ""))))
    except ValueError: return None


def layout(hdr):
    """Return column map from the 'Hunt Code | Unit/Description | ...' header row."""
    h = [s(c).lower() for c in hdr]
    hunt_cols = [i for i, c in enumerate(h) if c.startswith("hunt")]
    if len(hunt_cols) < 2: return None
    L, Rs = hunt_cols[0], hunt_cols[1]
    left = h[L:Rs]
    lic = next(i for i, c in enumerate(left) if c.startswith("lic")) + L
    bag = next((i + L for i, c in enumerate(left) if c.startswith("bag")), None)
    firsts = [i + L for i, c in enumerate(left) if c == "1st"]
    # left groups in order: hunt total, resident, nonresident, outfitter (first-choice col of each)
    rp = next(i for i, c in enumerate(h) if c == "r%")
    # right block: ... | HT(5) | R(1st..4th,T) | NR(5) | O(5) | R% NR% O% T%
    m = {"code": L, "desc": L + 1, "bag": bag, "lic": lic,
         "app_T": firsts[0], "app_R": firsts[1], "app_NR": firsts[2], "app_O": firsts[3],
         "dr_R": rp - 15, "dr_NR": rp - 10, "dr_O": rp - 5, "dr_T": rp - 20}
    for k in ("dr_R", "dr_NR", "dr_O"):
        assert h[m[k]] == "1st" and h[m[k] + 4] in ("t", "total"), (k, h[m[k]:m[k] + 5])
    return m


def weapon_of(desc):
    d = desc.lower()
    if re.search(r"\bbow\b|archery", d): return "archery"
    if "muzzleloader" in d: return "muzzleloader"
    return None


def sex_of(bag):
    b = bag.upper()
    if b.startswith("ES") or b in ("ES-BOW", "ESWTD"): return "either"
    if b.startswith("A") and not b.startswith("APRE"): return "female"
    if b.startswith(("MB", "APRE", "FAD", "FAWTD", "MM", "BB")): return "male"
    return None


def parse_book(year, url, title, hunts, sources):
    r = requests.get(url, headers=UA, timeout=180); r.raise_for_status()
    wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True, data_only=True)
    nrows = nh = 0
    bad = []
    for ws in wb.worksheets:
        m = None
        for row in ws.iter_rows(values_only=True):
            row = list(row)
            c0 = s(row[0]) if row else ""
            if c0.lower().startswith("hunt") and m is None:
                try: m = layout(row)
                except Exception as e: LOG.append(f"{year} header error {e}: {row[:12]}")
                continue
            if not CODE.match(c0) or m is None: continue
            nrows += 1
            sp3 = c0[:3]
            desc = s(row[m["desc"]]); bag = s(row[m["bag"]]) if m["bag"] is not None else ""
            DEBUG[(sp3, c0.split("-")[1], bag)] += 1
            if SKIP.search(desc): continue
            vals = {k: num(row[v]) for k, v in m.items() if k.startswith(("app", "dr", "lic"))}
            if None in vals.values():
                if len(bad) < 50: bad.append(f"{year} unparsed {row[:30]}")
                continue
            sp = SPECIES[sp3]
            if sp3 == "DER" and ("WTD" in bag.upper() or re.search(r"white-?tail|coues", desc, re.I)):
                sp = "C"
            units = re.findall(r"\b\d{1,2}[A-Z]?\b", re.sub(r"^units?\s*", "", desc.split(":")[0], flags=re.I))
            h = hunts.setdefault(c0, {"id": c0, "species": sp, "units": units, "label": desc + (f" ({bag})" if bag else ""),
                                      "kind": "limited", "years": {}})
            w = weapon_of(desc); x = sex_of(bag)
            if w: h["weapon"] = w
            if x: h["sex"] = x
            if "mobility" in desc.lower(): h["kind"] = "special"
            y = {"T": {"tags": vals["lic"], "apps": vals["app_T"], "drawn": vals["dr_T"]},
                 "R": {"apps": vals["app_R"], "drawn": vals["dr_R"]},
                 "NR": {"apps": vals["app_NR"], "drawn": vals["dr_NR"]},
                 "O": {"apps": vals["app_O"], "drawn": vals["dr_O"]}}
            h["years"][str(year)] = y
            nh += 1
    LOG.append(f"{year} {url} rows={nrows} hunts(E/D/C/P kept)={nh}")
    LOG.extend(bad)
    sources.append({"year": year, "species": "E,D,C,P", "url": url, "title": title})


def parse():
    hunts, sources = {}, []
    for year, url, title in SOURCES:
        try: parse_book(year, url, title, hunts, sources)
        except Exception as e: LOG.append(f"{year} FAILED {url}: {e!r}")
    LOG.append("apps = 1st-choice applicants; drawn = licenses drawn by 1st-choice applicants (report also has 2nd-4th choice).")
    LOG.append("NR = non-resident (unguided) pool only; outfitter-pool applicants/drawn are reported separately under key 'O' (nonresidents applying through an outfitter). T = hunt total incl. all pools.")
    LOG.append("Per-residency license quotas are not published in the odds report; only total Licenses (T.tags).")
    LOG.append("DEBUG species/digit/bag counts: " + "; ".join(f"{a}-{b} {c}:{n}" for (a, b, c), n in sorted(DEBUG.items())))
    out = sorted(hunts.values(), key=lambda h: h["id"])
    return {"state": "NM", "system": "random", "point_label": "none (pure random draw)", "sources": sources, "hunts": out}
