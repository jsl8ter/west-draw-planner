"""Download official hunt-unit boundaries from state ArcGIS services into data/*.geojson.

Runs on GitHub Actions (open internet). Writes data/report.json describing what loaded,
which URL worked, the unit field, and sample unit values, plus data/discovery.json with
ArcGIS Online search hits for sources we still need.
"""
import json, os, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data")
UA = {"User-Agent": "west-draw-planner/1.0 (github.com/jsl8ter/west-draw-planner)"}


def get_json(url, params=None, timeout=90):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"service error: {data['error'].get('message')}")
    return data


def resolve_item(item_id):
    j = get_json(f"https://www.arcgis.com/sharing/rest/content/items/{item_id}", {"f": "json"})
    u = j.get("url")
    if not u:
        raise RuntimeError("item has no url")
    if u.rstrip("/").endswith(("FeatureServer", "MapServer")):
        u = u.rstrip("/") + "/0"
    return u


def esri_to_features(j):
    out = []
    for f in j.get("features", []):
        g = f.get("geometry") or {}
        if "rings" in g:
            out.append({"type": "Feature", "properties": f.get("attributes") or {},
                        "geometry": {"type": "Polygon", "coordinates": g["rings"]}})
    return out


def query_all(base, where):
    last = None
    for fmt in ("geojson", "json"):
        try:
            feats, off = [], 0
            for _ in range(40):
                params = {"where": where, "outFields": "*", "returnGeometry": "true", "outSR": "4326",
                          "f": fmt, "geometryPrecision": "5", "maxAllowableOffset": "0.0015",
                          "resultOffset": str(off), "resultRecordCount": "1000"}
                j = get_json(base + "/query", params)
                fs = j.get("features", []) if fmt == "geojson" else esri_to_features(j)
                feats.extend(fs)
                more = j.get("exceededTransferLimit") or (j.get("properties") or {}).get("exceededTransferLimit")
                if not more or not fs:
                    break
                off += len(fs)
            if feats:
                return feats, fmt
            last = RuntimeError(f"{fmt}: no features")
        except Exception as e:  # noqa: BLE001
            last = e
    raise last or RuntimeError("no features")


def round_coords(c, nd=4):
    if isinstance(c, (int, float)):
        return round(c, nd)
    return [round_coords(x, nd) for x in c]


def pick_field(props, wanted):
    keys = list(props.keys())
    for w in wanted:
        for k in keys:
            if k.lower() == w.lower():
                return k
    for k in keys:
        if any(s in k.lower() for s in ("unit", "district", "gmu", "hunt", "area", "name")):
            return k
    return keys[0] if keys else None


def fetch_layer(cfg):
    rep = {"id": cfg["id"], "ok": False, "tried": []}
    urls = list(cfg.get("urls", []))
    for item in cfg.get("items", []):
        try:
            urls.append(resolve_item(item))
        except Exception as e:  # noqa: BLE001
            rep["tried"].append({"item": item, "error": str(e)[:200]})
    for u in urls:
        try:
            meta = {}
            try:
                meta = get_json(u, {"f": "json"})
            except Exception:  # noqa: BLE001
                pass
            feats, fmt = query_all(u, cfg.get("where", "1=1"))
            minf = (cfg.get("statewide_check") or {}).get("min_features", 0)
            if len(feats) < minf:
                raise RuntimeError(f"only {len(feats)} features (< {minf}), not statewide")
            field = pick_field(feats[0].get("properties") or {}, cfg.get("fields", []))
            out = []
            for f in feats:
                p = f.get("properties") or {}
                g = f.get("geometry")
                if not g:
                    continue
                v = p.get(field)
                out.append({"type": "Feature", "properties": {"unit": "" if v is None else str(v).strip()},
                            "geometry": {"type": g["type"], "coordinates": round_coords(g["coordinates"])}})
            fc = {"type": "FeatureCollection", "features": out}
            path = os.path.join(OUT, f"{cfg['id']}.geojson")
            with open(path, "w") as fh:
                json.dump(fc, fh, separators=(",", ":"))
            vals = sorted({f["properties"]["unit"] for f in out})
            rep.update({"ok": True, "url": u, "format": fmt, "field": field, "count": len(out),
                        "layer_name": meta.get("name"), "fields": [x.get("name") for x in meta.get("fields", [])][:40],
                        "bytes": os.path.getsize(path), "values": vals[:400]})
            rep["tried"].append({"url": u, "ok": True})
            return rep
        except Exception as e:  # noqa: BLE001
            rep["tried"].append({"url": u, "error": str(e)[:300]})
    return rep


def discover(queries):
    hits = {}
    for q in queries:
        try:
            j = get_json("https://www.arcgis.com/sharing/rest/search",
                         {"q": f'{q} type:"Feature Service" OR {q} type:"Map Service"', "num": "25", "f": "json"})
            hits[q] = [{"title": r.get("title"), "owner": r.get("owner"), "type": r.get("type"),
                        "url": r.get("url"), "id": r.get("id"), "modified": r.get("modified")}
                       for r in j.get("results", [])]
        except Exception as e:  # noqa: BLE001
            hits[q] = [{"error": str(e)[:200]}]
    return hits


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = json.load(open(os.path.join(ROOT, "scripts", "sources.json")))
    only = set(sys.argv[1:])
    report = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "layers": []}
    old = {}
    rp = os.path.join(OUT, "report.json")
    if only and os.path.exists(rp):
        old = {l["id"]: l for l in json.load(open(rp)).get("layers", [])}
    for layer in cfg["layers"]:
        if only and layer["id"] not in only:
            if layer["id"] in old:
                report["layers"].append(old[layer["id"]])
            continue
        r = fetch_layer(layer)
        print(f"{r['id']}: {'OK ' + str(r.get('count')) + ' via ' + r.get('url', '') if r['ok'] else 'FAILED'}", flush=True)
        report["layers"].append(r)
    with open(rp, "w") as fh:
        json.dump(report, fh, indent=1)
    with open(os.path.join(OUT, "discovery.json"), "w") as fh:
        json.dump(discover(cfg.get("discover", [])), fh, indent=1)


if __name__ == "__main__":
    main()
