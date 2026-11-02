"""Run each state's parser (scripts/draw/parse_<st>.py, function parse() -> dict) and write data/draw/<ST>.json.
Usage: parse_all.py [ST ...]"""
import importlib.util, json, os, sys, time, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
def run(st):
    p = os.path.join(HERE, f"parse_{st.lower()}.py")
    if not os.path.exists(p): print(st, "no parser"); return
    spec = importlib.util.spec_from_file_location(f"parse_{st.lower()}", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    log_p = os.path.join(ROOT, "data", "draw", f"{st}.log.txt")
    try:
        d = m.parse()
        import postprocess; d = postprocess.annotate(st, d)
        d["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        json.dump(d, open(os.path.join(ROOT, "data", "draw", f"{st}.json"), "w"), separators=(",", ":"))
        n = len(d.get("hunts", [])); yrs = sorted({y for h in d.get("hunts", []) for y in h.get("years", {})})
        msg = f"{st}: OK {n} hunts, years {yrs}"
        if hasattr(m, "LOG"): msg += "\n" + "\n".join(m.LOG[-300:])
    except Exception:
        msg = f"{st}: FAILED\n" + traceback.format_exc()
    open(log_p, "w").write(msg); print(msg[:3000], flush=True)
for st in (sys.argv[1:] or ["CO","WY","UT","AZ","NM","NV","OR","ID","MT"]): run(st)
