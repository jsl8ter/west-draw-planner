"""Consistency checks over data/draw/*.json. python3 scripts/qa/anomalies.py [ST ...]"""
import json, sys, collections
STATES = sys.argv[1:] or "CO WY UT AZ NM NV OR ID MT".split()
for st in STATES:
    d = json.load(open(f"data/draw/{st}.json"))
    issues = collections.defaultdict(list)
    for h in d["hunts"]:
        ys = sorted(h["years"])
        tags_by_year = {}
        for y in ys:
            Y = h["years"][y]
            for res, b in Y.items():
                if not isinstance(b, dict): continue
                a, dr, tg = b.get("apps"), b.get("drawn"), b.get("tags")
                rows = b.get("by_pts") or []
                if a is not None and dr is not None and dr > a: issues["drawn>apps"].append(f"{h['id']} {y} {res} {dr}>{a}")
                if tg is not None and dr is not None and dr > tg * 1.05 + 1: issues["drawn>tags"].append(f"{h['id']} {y} {res} {dr}>{tg}")
                if rows:
                    sa = sum(r[1] for r in rows); sd = sum((r[2] or 0) for r in rows)
                    if any((r[2] or 0) > r[1] for r in rows): issues["row drawn>apps"].append(f"{h['id']} {y} {res}")
                    if a and abs(sa - a) > max(2, 0.1 * a): issues["by_pts apps != apps"].append(f"{h['id']} {y} {res} rows={sa} apps={a}")
                    if dr is not None and sd > dr + 1: issues["by_pts drawn > drawn"].append(f"{h['id']} {y} {res} rows={sd} drawn={dr}")
                    drew = [r[0] for r in rows if (r[2] or 0) > 0]
                    if b.get("min_pts") is not None and drew and min(drew) != b["min_pts"]:
                        issues["min_pts != lowest drawing row"].append(f"{h['id']} {y} {res} min={b['min_pts']} rows={min(drew)}")
                if res == "T" and tg: tags_by_year[y] = tg
            nr, t = Y.get("NR") or {}, Y.get("T") or {}
            if nr.get("tags") and t.get("tags") and nr["tags"] > t["tags"]: issues["NR tags > total"].append(f"{h['id']} {y}")
            if nr.get("apps") and t.get("apps") and nr["apps"] > t["apps"]: issues["NR apps > total apps"].append(f"{h['id']} {y} {nr['apps']}>{t['apps']}")
        tv = list(tags_by_year.values())
        if len(tv) >= 2 and max(tv) > 4 * max(1, min(tv)) and max(tv) - min(tv) > 10:
            issues["tags swing >4x (same hunt?)"].append(f"{h['id']} {tags_by_year} | {h['label'][:60]}")
        if not h.get("units"): issues["no units"].append(h["id"])
    print(f"\n=== {st} ({len(d['hunts'])} hunts)")
    for k, v in sorted(issues.items(), key=lambda x: -len(x[1])):
        print(f"  {k}: {len(v)}  e.g. {v[:3]}")
