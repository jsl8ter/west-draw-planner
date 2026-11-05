"""Estimated trophy scores for UNRATED units -> data/trophy_est.json

Only where draw demand tracks the researched ratings well (Spearman >= 0.55 between a unit's demand and its
rating among rated units of the same state + species): the estimate is the median rating of the 5 rated units
with the closest demand (log of resident/total applicants per tag for antlered hunts). Elsewhere no estimate.
"""
import json, math, os, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = json.load(open(os.path.join(ROOT, "data", "trophy.json")))["units"]
MIN_RHO, K = 0.55, 5


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
    for k, i in enumerate(o): r[i] = k
    return r


def spear(a, b):
    ra, rb = rank(a), rank(b); n = len(a); ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0


out, log = {}, []
for st in "CO WY UT AZ NM NV OR ID MT".split():
    d = json.load(open(os.path.join(ROOT, "data", "draw", f"{st}.json")))
    for sp in "EDCP":
        dem = collections.defaultdict(list)
        for h in d["hunts"]:
            if h["species"] != sp or h.get("bag") != "antlered": continue
            Y = h["years"][max(h["years"])]; b = Y.get("R") or Y.get("T") or {}
            if not b.get("apps") or not (b.get("drawn") or b.get("tags")): continue
            for u in h["units"]: dem[str(u)].append(b["apps"] / max(1, b.get("drawn") or b.get("tags")))
        rated = [(math.log(max(v)), T[st][sp][u]["s"]) for u, v in dem.items() if T.get(st, {}).get(sp, {}).get(u)]
        if len(rated) < 8: continue
        rho = spear([x for x, _ in rated], [y for _, y in rated])
        if rho < MIN_RHO:
            log.append(f"{st} {sp}: no estimates (demand vs rating rho {rho:.2f})"); continue
        n = 0
        for u, v in dem.items():
            if T.get(st, {}).get(sp, {}).get(u): continue
            x = math.log(max(v))
            near = sorted(rated, key=lambda r: abs(r[0] - x))[:K]
            s = sorted(y for _, y in near)[len(near) // 2]
            out.setdefault(st, {}).setdefault(sp, {})[u] = {"s": s, "est": True,
                "why": f"Estimated: draw demand similar to {st} units rated {s}/5 (not researched)"}
            n += 1
        log.append(f"{st} {sp}: {n} estimated (rho {rho:.2f})")
json.dump({"generated": "from data/draw + data/trophy.json", "log": log, "units": out}, open(os.path.join(ROOT, "data", "trophy_est.json"), "w"), indent=0)
print("\n".join(log))
