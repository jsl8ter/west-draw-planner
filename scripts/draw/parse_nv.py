"""Nevada (NDOW) big game draw statistics.

Source: NDOW "Bonus Point and Application Choice Trends" PDFs (one per hunt type and year, sometimes split by
residency), found through the ndow.org WordPress media API. Each PDF has one block per hunt (residency x unit
group x season) with Quota, and by bonus point level the successful and total applicants for choices 1-5.

Output per hunt/year/residency:
  tags   = Quota printed for that residency block
  apps   = total 1st-choice applicants
  drawn  = successful applicants over all 5 choices (= tags issued in the main draw)
  by_pts = [points, 1st-choice applicants, 1st-choice successful]
Columns are assigned by x-position against the header row because empty cells are blank in the PDF.
"""
import io, re, json, collections
import requests, pdfplumber

LOG = []
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) west-draw-planner/1.0"}
YEARS = range(2021, 2027)
MEDIA = "https://www.ndow.org/wp-json/wp/v2/media"
SPECIES = [("Mule-Deer", "D"), ("Elk", "E"), ("Antelope", "P")]
SKIP_FILE = re.compile(r"Junior|Depredation|Youth|Landowner", re.I)
SKIP_TITLE = re.compile(r"Junior|Depredation|Youth|Landowner|Heritage|Silver State|Dream Tag|PIW", re.I)
MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=180, **kw)
    r.raise_for_status()
    return r


def find_files():
    urls = set()
    for term in ["Application Trend", "Bonus Point and Application"]:
        for page in range(1, 8):
            try:
                r = requests.get(MEDIA, headers=UA, timeout=60, params={
                    "search": term, "per_page": 100, "page": page, "_fields": "source_url"})
            except Exception as e:
                LOG.append(f"media api error {term} p{page}: {e}"); break
            if r.status_code != 200:
                break
            items = r.json()
            if not items:
                break
            for it in items:
                urls.add(it["source_url"])
            if len(items) < 100:
                break
    LOG.append(f"media api: {len(urls)} trend files found")
    best = {}
    for u in urls:
        name = u.rsplit("/", 1)[-1]
        sp = next((c for p, c in SPECIES if name.startswith(p + "-")), None)
        if not sp or SKIP_FILE.search(name):
            continue
        m = re.search(r"Trend-(?:([A-Za-z]+)-)?(20\d\d)", name)
        if not m:
            LOG.append(f"skip (no year): {u}"); continue
        year = int(m.group(2))
        if year not in YEARS:
            continue
        typ = name.split("-Bonus-Point")[0]
        typ = typ.replace("Muzzleloader", "Muzzle")
        res = (m.group(1) or "").lower()[:3]
        up = re.search(r"/uploads/(\d{4})/(\d\d)/", u)
        upk = (up.group(1) + up.group(2)) if up else ""
        k = (typ, res, year)
        if k not in best or upk > best[k][0]:
            best[k] = (upk, u)
    files = sorted(((k[2], k[0], v[1]) for k, v in best.items()), reverse=True)
    return files


def sp_of(title):
    t = title.lower()
    if "elk" in t: return "E"
    if "deer" in t: return "D"
    if "antelope" in t or "pronghorn" in t: return "P"
    return None


def lines_of(page):
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    rows = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if rows and abs(rows[-1][0] - w["top"]) <= 3:
            rows[-1][1].append(w)
        else:
            rows.append([w["top"], [w]])
    out = []
    for top, ws in rows:
        ws.sort(key=lambda w: w["x0"])
        out.append(ws)
    return out


def expand_units(s):
    units = []
    for part in re.split(r",", s):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d{3})\s*-\s*(\d{3})", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b and b - a < 30:
                units += [f"{i:03d}" for i in range(a, b + 1)]
                continue
        m = re.fullmatch(r"\d{1,3}", part)
        if m:
            units.append(f"{int(part):03d}"); continue
        units.append(part)
    return units


def to_int(s):
    s = s.replace(",", "")
    return int(s) if re.fullmatch(r"\d+", s) else None


def parse_pdf(data, url, year, bad):
    blocks = []
    cur = None
    cols = None  # list of (name, xcenter)
    title_prev = None
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            for ws in lines_of(page):
                texts = [w["text"] for w in ws]
                line = " ".join(texts)
                if line.startswith("Units:"):
                    cur = {"title": title_prev or "", "units_raw": line[6:].strip(), "rows": {}, "total": None}
                    blocks.append(cur)
                    continue
                if cur is not None and line.startswith("Season:"):
                    cur["season"] = line[7:].strip(); continue
                if cur is not None and line.startswith("Weapon"):
                    cur["weapon"] = line[6:].strip(" :"); continue
                if cur is not None and line.startswith("Quota"):
                    q = re.search(r"(\d[\d,]*)", line)
                    cur["quota"] = to_int(q.group(1)) if q else None; continue
                if line.startswith("Bonus Points") and "1st" in texts:
                    cols = []
                    seen = collections.Counter()
                    for w in ws[2:]:
                        t = w["text"]
                        if t in ("1st", "2nd", "3rd", "4th", "5th"):
                            seen[t] += 1
                            cols.append((("S" if seen[t] == 1 else "A") + t[0], (w["x0"] + w["x1"]) / 2))
                        elif t.lower().startswith("applicant"):
                            cols.append(("U", (w["x0"] + w["x1"]) / 2))
                    continue
                if cur is not None and cols and (to_int(texts[0]) is not None or texts[0] == "Total") and len(ws) >= 2:
                    vals = {}
                    ok = True
                    for w in ws[1:]:
                        v = to_int(w["text"])
                        if v is None:
                            ok = False; break
                        xc = (w["x0"] + w["x1"]) / 2
                        name = min(cols, key=lambda c: abs(c[1] - xc))[0]
                        if name in vals:
                            ok = False; break
                        vals[name] = v
                    if not ok:
                        if len(bad) < 50: bad.append(f"{year} {url.rsplit('/',1)[-1]}: {line}")
                        continue
                    if texts[0] == "Total":
                        cur["total"] = vals
                    else:
                        cur["rows"][to_int(texts[0])] = vals
                    continue
                # remember a possible block title (line right before "Units:")
                title_prev = line
    return blocks


def season_start(s, year):
    m = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2})", s or "")
    if not m or m.group(1) not in MONTHS:
        return "99-99"
    return f"{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"


def weapon_of(w, title):
    t = f"{w} {title}".lower()
    if "archery" in t: return "archery"
    if "muzzle" in t: return "muzzleloader"
    if "any legal" in t or "alw" in t: return "any"
    return "other"


def sex_of(title):
    t = title.lower()
    if "antlerless" in t or "shorter" in t or "ewe" in t: return "female"
    if "antlered" in t or "spike" in t or "longer" in t or "bull" in t: return "male"
    return "either"


def parse():
    files = find_files()
    sources, raw = [], []
    bad = []
    for year, typ, url in files:
        try:
            data = get(url).content
            blocks = parse_pdf(data, url, year, bad)
        except Exception as e:
            LOG.append(f"ERROR {url}: {e}"); continue
        n_ok = 0
        for b in blocks:
            title = b["title"]
            m = re.match(r"(Res|Resident|NonRes|Non-Res|Nonresident|NR)\b\s*(.*)", title, re.I)
            if not m:
                if len(bad) < 50: bad.append(f"{year} no residency in title '{title}' {url.rsplit('/',1)[-1]}")
                continue
            res = "R" if m.group(1).lower() in ("res", "resident") else "NR"
            name = m.group(2).strip()
            sp = sp_of(name)
            if not sp or SKIP_TITLE.search(name):
                continue
            if b.get("total") is None or b.get("quota") is None:
                if len(bad) < 50: bad.append(f"{year} incomplete block {title} {b['units_raw']} {url.rsplit('/',1)[-1]}")
                continue
            b.update(year=year, res=res, name=name, sp=sp, url=url)
            raw.append(b); n_ok += 1
        sp_codes = sorted({b["sp"] for b in raw if b["url"] == url})
        sources.append({"year": year, "species": ",".join(sp_codes) or "?", "url": url,
                        "title": f"{year} Bonus Point and Application Choice Trends - {typ.replace('-', ' ')}"})
        LOG.append(f"{url}: {len(blocks)} blocks, {n_ok} kept")

    # group into hunts: key (sp, name, weapon, units) -> per year sorted seasons
    groups = collections.defaultdict(lambda: collections.defaultdict(set))
    for b in raw:
        b["units"] = expand_units(b["units_raw"])
        b["weapon_k"] = weapon_of(b.get("weapon", ""), b["name"])
        b["start"] = season_start(b.get("season"), b["year"])
        gk = (b["sp"], b["name"], b["weapon_k"], tuple(b["units"]))
        groups[gk][b["year"]].add(b["start"])
    hunts = {}
    for b in raw:
        gk = (b["sp"], b["name"], b["weapon_k"], tuple(b["units"]))
        starts = sorted(groups[gk][b["year"]])
        idx = starts.index(b["start"]) + 1
        typecode = re.sub(r"[^A-Za-z]+", "", b["name"].replace("Mule Deer", "").replace("Elk", "").replace("Antelope", ""))
        hid = f"{b['sp']}-{typecode}-{b['weapon_k'][:3].upper()}-{'.'.join(b['units'])}" + (f"-S{idx}" if max(len(s) for s in groups[gk].values()) > 1 else "")
        h = hunts.get(hid)
        if h is None:
            kind = "special" if "guided" in b["name"].lower() else "limited"
            h = hunts[hid] = {"id": hid, "species": b["sp"], "units": b["units"], "label": "", "weapon": b["weapon_k"],
                              "sex": sex_of(b["name"]), "kind": kind, "years": {}, "_ly": 0}
        if b["year"] >= h["_ly"]:
            h["_ly"] = b["year"]
            h["label"] = f"{b['name']} - {b.get('weapon','')} - Units {b['units_raw']} - {b.get('season','')}".strip()
        tot = b["total"]
        drawn = sum(tot.get("S" + c, 0) for c in "12345")
        by = [[p, v.get("A1", 0), v.get("S1", 0)] for p, v in sorted(b["rows"].items(), reverse=True)]
        by = [r for r in by if r[1] or r[2]]
        rec = {"tags": b["quota"], "apps": tot.get("A1", 0), "drawn": drawn, "by_pts": by}
        if sum(r[1] for r in by) != rec["apps"] and len(bad) < 50:
            bad.append(f"{b['year']} {hid} {b['res']}: by_pts apps sum {sum(r[1] for r in by)} != total {rec['apps']}")
        if sum(r[2] for r in by) != tot.get("S1", 0) and len(bad) < 50:
            bad.append(f"{b['year']} {hid} {b['res']}: by_pts drawn sum {sum(r[2] for r in by)} != total S1 {tot.get('S1', 0)}")
        y = h["years"].setdefault(str(b["year"]), {})
        if b["res"] in y:
            if len(bad) < 50: bad.append(f"duplicate {b['year']} {hid} {b['res']} (kept first)")
            continue
        y[b["res"]] = rec
    for h in hunts.values():
        h.pop("_ly")
        for y in h["years"].values():
            parts = [y[r] for r in ("R", "NR") if r in y]
            y["T"] = {"tags": sum(p["tags"] for p in parts), "apps": sum(p["apps"] for p in parts),
                      "drawn": sum(p["drawn"] for p in parts)}
    LOG.append("NOTE: apps = 1st-choice applicants; drawn = successful over all 5 choices; by_pts drawn = 1st-choice successful")
    LOG.append("NOTE: hunts are NDOW unit-group x season blocks (no hunt numbers in source); id = species-type-weapon-units[-season#]")
    cnt = collections.Counter(h["species"] for h in hunts.values())
    LOG.append(f"hunts per species: {dict(cnt)}")
    LOG.extend("UNPARSED " + x for x in bad[:50])
    return {"state": "NV", "system": "bonus_sq", "point_label": "bonus points", "sources": sources,
            "hunts": sorted(hunts.values(), key=lambda h: h["id"])}
