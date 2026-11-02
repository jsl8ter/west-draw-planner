"""Post-parse quality step, run by parse_all.py on every state (and runnable alone: postprocess.py [ST ...]).

1. bag: what the tag lets you kill, from the official hunt code / bag-limit text:
     antlered   mature male legal (bull, buck, antlered, MB, fork-antlered, horns longer than ears, brow-tined bull)
     either     either sex (any elk/deer/antelope) - mature male legal
     spike      spike-only (or spike-or-antlerless) - NOT a trophy hunt
     antlerless cow/doe/ewe only
     other      a different animal than the species group (e.g. white-tailed or black-tailed deer only on a mule deer list)
     unknown    no official bag found - never treated as a trophy hunt
   Sources: Colorado hunt code letter (M/F/E); New Mexico bag code (MB, ES, A, FAD...); Oregon bag limit from the
   regulation tables (data/draw/regs/OR.json, eregulations.com = ODFW's official regulations host); Montana permit
   descriptions (data/draw/regs/MT.json when present); other states the official hunt name in the draw report.
   h["bag_text"] keeps the official wording where we have it; h["sex"] is made consistent with bag.
2. New Mexico: 2022 belongs to the 2018-22 rule cycle; hunt codes were renumbered for 2023, so 2022 rows are dropped.
"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGS = os.path.join(ROOT, "data", "draw", "regs")

OTHER = re.compile(r"white[- ]?tail|black[- ]?tail|\bAny Wh\b", re.I)
SPIKE = re.compile(r"(?<!golden )\bspike\b", re.I)   # not the "Golden Spike" CWMU
EITHER = re.compile(r"either[- ]sex|\beither\b|antlerless or antlered|antlered or antlerless|\bany (elk|deer|antelope|pronghorn)\b|"
                    r"^one (elk|deer)\b(?! with)|\(ES\)", re.I)
ANTLERLESS = re.compile(r"antlerless|\bcows?\b|cow or calf|\bdoes?\b|doe or fawn|\bewes?\b|horns shorter|\bfemale\b|\(A\)\s*$|\bB license\b", re.I)
ANTLERED = re.compile(r"antlered|\bbulls?\b|\bbucks?\b|horns longer|\((MB|FAD|FAMD|FAWTD|APRE[^)]*)\)|brow[- ]tined|\d+ ?pt\+?", re.I)
SEX = {"antlered": "male", "spike": "male", "antlerless": "female", "either": "either"}


def classify(text, species):
    t = text or ""
    if not t.strip():
        return "unknown"
    if species == "D" and OTHER.search(t) and not re.search(r"mule", t, re.I):
        # "white-tailed buck ... or black-tailed deer", "Any white-tailed deer": not a mule deer tag
        return "other"
    if SPIKE.search(t):
        return "spike"
    if EITHER.search(t):
        return "either"
    if ANTLERLESS.search(t):
        return "antlerless"
    if ANTLERED.search(t):
        return "antlered"
    return "unknown"


def load_regs(st):
    p = os.path.join(REGS, f"{st}.json")
    return json.load(open(p)).get("hunts", {}) if os.path.exists(p) else {}


def bag_for(st, h, regs):
    sp, lab, hid = h["species"], h.get("label") or "", h["id"]
    if st == "CO":
        m = re.match(r"^[DEAC]-([MFE])-", hid)
        b = {"M": "antlered", "F": "antlerless", "E": "either"}.get(m.group(1)) if m else "unknown"
        return b, None
    if st == "OR":
        r = regs.get(hid)
        if r and r.get("bag"):
            return classify(r["bag"], sp), r["bag"]
        # hunts no longer in the current regulations: series rule only where it is unambiguous
        if re.match(r"^1\d\d", hid) and sp == "D": return "antlered", None   # 100-series = buck deer
        if re.match(r"^6\d\d", hid) and sp == "D": return "antlerless", None  # 600-series = antlerless deer
        return "unknown", None
    if st == "MT":
        r = regs.get(hid)
        if r and r.get("bag"):
            return classify(r["bag"], sp), r["bag"]
        if re.search(r"\b(Deer|Elk|Antelope) B\b", lab): return "antlerless", None
        if h.get("kind") == "general": return "either", None
        return "unknown", None
    if st == "NM":
        m = re.search(r"\(([A-Z/0-9]+)\)\s*$", lab)
        code = m.group(1) if m else ""
        b = {"MB": "antlered", "FAD": "antlered", "FAMD": "antlered", "FAWTD": "antlered", "ES": "either", "ESWTD": "either", "MB/A": "either", "A": "antlerless"}.get(code)
        if b is None and code.startswith("APRE"): b = "antlered"
        return b or classify(lab, sp), code or None
    if st == "WY" and re.match(r"^Region [A-Z]|General deer", lab.split(" - ", 1)[-1]):
        return "antlered", "General license (legal deer set by hunt area)"
    b = classify(lab, sp)
    if b == "unknown" and h.get("sex") in SEX.values():
        b = {"male": "antlered", "female": "antlerless", "either": "either"}[h["sex"]]
    return b, None


def merge_ut_api(d):
    """Utah 2026+: draw results from utahdraws.com JSON (data/draw/raw/UT/<year>_<type>.json, fetched by
    fetch_ut_api.py). Rows: ResidencyTypeID 1 resident / 2 nonresident; ParticipantCount = 1st-choice applicants,
    SuccessfulCount = drawn; max-point vs regular round split gives the bonus-pass cutoff."""
    import glob
    byid = {h["id"]: h for h in d["hunts"]}
    added, missing = 0, []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "draw", "raw", "UT", "20??_*.json"))):
        y = os.path.basename(f)[:4]
        try: data = (json.load(open(f)) or {}).get("Data") or []
        except Exception: continue
        for a in data:
            h = byid.get(a.get("HuntCode"))
            if h is None:
                if a.get("QuotaQuantity"): missing.append(a.get("HuntCode"))
                continue
            Y = {}
            for res, rid, q in (("R", 1, a.get("ResidentQuotaQuantity")), ("NR", 2, a.get("NonResidentQuotaQuantity"))):
                rows = [o for o in a.get("OddsList") or [] if o.get("ResidencyTypeID") == rid and not o.get("IsYouth")]
                if not rows: continue
                by = {}
                for o in rows:
                    p = int(o.get("Point") or 0); r = by.setdefault(p, [0, 0, 0])
                    r[0] += o.get("ParticipantCount") or 0; r[1] += o.get("SuccessfulCount") or 0; r[2] += o.get("SuccessfulByMaxPointRoundCount") or 0
                by_pts = [[p, v[0], v[1]] for p, v in sorted(by.items(), reverse=True) if v[0] or v[1]]
                mx = [p for p, v in by.items() if v[2] > 0]
                blk = {"apps": sum(v[0] for v in by.values()), "drawn": sum(v[1] for v in by.values()), "by_pts": by_pts}
                if q: blk["tags"] = q
                if mx: blk["min_pts"] = min(mx)
                Y[res] = blk
            if Y:
                Y["T"] = {"apps": sum(Y[r]["apps"] for r in ("R", "NR") if r in Y), "drawn": sum(Y[r]["drawn"] for r in ("R", "NR") if r in Y)}
                if a.get("QuotaQuantity"): Y["T"]["tags"] = a["QuotaQuantity"]
                h["years"][y] = Y; added += 1
    d.setdefault("notes", {})["ut_api"] = f"{added} hunt-years from utahdraws.com; not matched to a known hunt: {missing[:20]}"


def annotate(st, d):
    if st == "UT": merge_ut_api(d)
    regs = load_regs(st)
    from collections import Counter
    c = Counter()
    for h in d["hunts"]:
        b, txt = bag_for(st, h, regs)
        h["bag"] = b
        if txt: h["bag_text"] = txt
        else: h.pop("bag_text", None)
        if b in SEX: h["sex"] = SEX[b]
        c[(h["species"], b)] += 1
    if st == "NM":
        keep = []
        for h in d["hunts"]:
            if "2022" in h["years"] and len(h["years"]) > 1: h["years"].pop("2022")
            if set(h["years"]) == {"2022"}: continue   # old-cycle hunt code, not offered since
            keep.append(h)
        d["hunts"] = keep
    d.setdefault("notes", {})["bag"] = {f"{sp}:{b}": n for (sp, b), n in sorted(c.items())}
    return d


if __name__ == "__main__":
    for st in (sys.argv[1:] or "CO WY UT AZ NM NV OR ID MT".split()):
        p = os.path.join(ROOT, "data", "draw", f"{st}.json")
        d = annotate(st, json.load(open(p)))
        json.dump(d, open(p, "w"), separators=(",", ":"))
        print(st, d["notes"]["bag"])
