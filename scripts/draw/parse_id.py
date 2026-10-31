"""Idaho (IDFG) controlled hunt drawing odds -> data/draw/ID.json

Sources (Idaho Hunt Planner JSON endpoints behind the web pages):
 - Drawing odds:  https://idfg.idaho.gov/ifwis/huntplanner/api/1.1/odds/?biggame=<1 deer|2 elk|3 pronghorn>&yr=<Y>&draw=1
   per hunt number: PermitAvailable, ApplChoice1/SuccChoice1, ResApp/ResPermit, NonResApp/NonResPermit, PermitTotal.
 - Hunt list:     https://idfg.idaho.gov/ifwis/huntplanner/api/1.1/list/?start=..&end=..&game=..  (season, ornament,
   weapon method, area, open/close per hunt number) used for labels and to link hunts across years
   (Idaho renumbers controlled hunts every year).
"""
import re, time
import requests

LOG = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"}
API = "https://idfg.idaho.gov/ifwis/huntplanner/api/1.1/"
YEARS = list(range(2022, 2027))
GAMES = {"D": (1, "Deer"), "E": (2, "Elk"), "P": (3, "Pronghorn")}
S = requests.Session()
S.headers.update(UA)


def get_json(path, params):
    err = None
    for i in range(5):
        try:
            r = S.get(API + path, params=params, timeout=90,
                      headers={"Referer": "https://idfg.idaho.gov/ifwis/huntplanner/odds/"})
            if r.status_code in (429, 503):
                raise RuntimeError(f"HTTP {r.status_code}")
            r.raise_for_status()
            time.sleep(1.5)
            return r.json()
        except Exception as e:
            err = e
            time.sleep(10 * (i + 1))
    raise err


_LIST = {}


def hunt_list(year, game_id, game_name):
    """controlled hunts whose season overlaps Jul 1 Y .. Mar 31 Y+1, keyed by hunt number"""
    if year not in _LIST:
        _LIST[year] = _fetch_list(year)
        from collections import Counter
        LOG.append(f"hunt list {year}: {len(_LIST[year])} rows; games {dict(Counter(r.get('game') for r in _LIST[year]))}; "
                   f"seasons {dict(Counter(r.get('season') for r in _LIST[year]).most_common(12))}")
    return _pick(_LIST[year], year, game_name)


def _fetch_list(year):
    rows, off = [], 0
    while True:
        d = get_json("list/", {"start": f"{year}-7-1", "end": f"{year + 1}-3-31",
                               "limit": 100, "offset": off, "search": "Controlled"})
        rr = d.get("rows") or []
        rows += rr
        off += len(rr)
        if not rr or off >= int(d.get("total") or 0):
            break
    return rows


def _pick(rows, year, game_name):
    out = {}
    for r in rows:
        if game_name.lower() not in (r.get("game") or "").lower() or "controlled" not in (r.get("season") or "").lower():
            continue
        num = str(r.get("number") or "").strip()
        if not num:
            continue
        op = r.get("open") or ""
        m = re.match(r"(\d+)/(\d+)/(\d+)", op)
        oy = (2000 + int(m.group(3))) if m else None
        prev = out.get(num)
        # prefer the segment opening in the draw year (a number can recur in Jan-Mar for last year's hunt)
        if prev is None or (oy == year and prev["_oy"] != year):
            r["_oy"] = oy
            r["_om"] = (int(m.group(1)), int(m.group(2))) if m else (99, 99)
            out[num] = r
    return out


def units_of(area):
    out = []
    for part in re.split(r"[,&/;]|\band\b", area or ""):
        m = re.match(r"\s*(\d{1,2}[A-C]?)(?:-\d+)?[A-Z]?\s*$", part)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out or [area.strip()]


def weapon_of(method):
    m = (method or "").lower()
    if "archery" in m:
        return "archery"
    if "muzzle" in m:
        return "muzzleloader"
    if "any" in m:
        return "any"
    return "other"


def sex_of(orn):
    o = (orn or "").lower()
    if "either" in o:
        return "either"
    if "antlerless" in o or "doe" in o or "cow" in o:
        return "female"
    if "antlered" in o or "buck" in o or "bull" in o:
        return "male"
    return None


SKIP = re.compile(r"youth|landowner|disab|mentor|super hunt|depredation", re.I)


def parse():
    out = {"state": "ID", "system": "random", "point_label": "none (random draw)", "sources": [], "hunts": []}
    LOG.append("apps = 1st-choice applicants (ApplChoice1); R/NR apps = 1st-choice resident/nonresident applicants; "
               "R/NR drawn = permits awarded to residents/nonresidents in the 1st drawing (can include 2nd-choice "
               "draws: see SuccChoice2); T.drawn = PermitTotal. NR permit share is capped (max 10%) but not published "
               "per hunt -> NR.tags omitted. 2nd drawing (leftover permits) not included.")
    groups = {}   # link key -> hunt dict
    for sp, (gid, gname) in GAMES.items():
        for y in YEARS:
            try:
                odds = get_json("odds/", {"biggame": gid, "yr": y, "draw": 1})
            except Exception as e:
                LOG.append(f"FAIL odds {gname} {y}: {e}")
                continue
            rows = odds.get("rows") or []
            try:
                meta = hunt_list(y, gid, gname)
            except Exception as e:
                LOG.append(f"FAIL list {gname} {y}: {e}")
                meta = {}
            url = f"{API}odds/?biggame={gid}&yr={y}&draw=1"
            out["sources"].append({"year": y, "species": sp, "url": url, "title": f"{y} {gname} controlled hunt drawing odds (1st drawing)"})
            nometa, kept, skipped = [], 0, 0
            seen_keys = {}
            # order hunts within a key by opening date so that duplicate keys get stable ordinals
            def okey(r):
                m = meta.get(str(r.get("CHunt")))
                return (m["_om"] if m else (99, 99), int(r.get("CHunt") or 0))
            for r in sorted(rows, key=okey):
                if int(r.get("Draw") or 1) != 1:
                    continue
                num = str(r.get("CHunt"))
                area = (r.get("CHuntArea") or "").strip()
                m = meta.get(num)
                if m and SKIP.search(m.get("season") or ""):
                    skipped += 1
                    continue
                if m:
                    base = (sp, area, m.get("ornament"), m.get("method"), m.get("season"))
                else:
                    base = (sp, area, None, None, f"hunt {num}")
                    nometa.append(num)
                k = seen_keys.get(base, 0)
                seen_keys[base] = k + 1
                key = base + (k,)
                h = groups.get(key)
                if h is None:
                    h = {"id": num, "species": sp, "units": units_of(area), "kind": "limited", "years": {}}
                    groups[key] = h
                h["id"] = num  # latest year's hunt number (years processed in ascending order)
                if m:
                    h["label"] = f"Hunt {num} - Area {area} {gname} {m.get('season', '')} - {m.get('ornament', '')}, " \
                                 f"{m.get('method', '')} ({m.get('open')}-{m.get('close')})"
                    h["weapon"] = weapon_of(m.get("method"))
                    s = sex_of(m.get("ornament"))
                    if s:
                        h["sex"] = s
                else:
                    h.setdefault("label", f"Hunt {num} - Area {area} {gname}")
                tags = r.get("PermitAvailable")
                T = {"apps": int(r.get("ApplChoice1") or 0), "drawn": int(r.get("PermitTotal") or 0)}
                if tags is not None and int(tags) != 999999:
                    T["tags"] = int(tags)
                R = {"apps": int(r.get("ResApp") or 0), "drawn": int(r.get("ResPermit") or 0)}
                NR = {"apps": int(r.get("NonResApp") or 0), "drawn": int(r.get("NonResPermit") or 0)}
                h["years"][str(y)] = {"hunt": num, "R": R, "NR": NR, "T": T}
                kept += 1
            LOG.append(f"{y} {gname}: {url} -> {len(rows)} rows, {kept} kept, {skipped} youth/landowner/etc skipped, "
                       f"{len(meta)} hunts in list; no list metadata for {len(nometa)}: {nometa[:30]}")
    hunts = list(groups.values())
    for h in hunts:
        h.setdefault("weapon", "any")
    out["hunts"] = sorted(hunts, key=lambda h: (h["species"], int(re.sub(r"\D", "", h["id"]) or 0)))
    for sp in "EDP":
        hs = [h for h in out["hunts"] if h["species"] == sp]
        LOG.append(f"species {sp}: {len(hs)} hunts; multi-year {sum(1 for h in hs if len(h['years']) > 1)}")
    LOG.append("Hunts are linked across years by (area, ornament, weapon method, season type, order by opening date); "
               "each year object carries that year's hunt number in 'hunt'.")
    return out
