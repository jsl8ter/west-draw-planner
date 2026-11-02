"""Montana permit bag limits from the regulation text dump (data/draw/regs/MT_text.txt) -> MT.json hunts
keyed "<species>:<code>", e.g. "E:262-45": {"bag": "Brow-tined Bull Elk", "limits": "Only valid on private land."}"""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
P = os.path.join(ROOT, "data", "draw", "regs")
SP = {"Elk": "E", "Deer": "D", "Antelope": "P"}
LINE = re.compile(r"^(Elk|Deer|Antelope) (?:B )?(Permit|License|B License):\s*(\d{3}-\d{2})\s+(.+?)\s+(?:April|June?|March|May|Jan|Feb|July?|Aug|Sept?|Oct|Nov|Dec)\.? ?\d")
def extract():
    lines = open(os.path.join(P, "MT_text.txt")).read().splitlines()
    out = {}
    for i, l in enumerate(lines):
        m = LINE.match(l.strip())
        if not m: continue
        sp, kind, code, desc = SP[m.group(1)], m.group(2), m.group(3), m.group(4).strip()
        if "B License" in kind or l.startswith(m.group(1) + " B "): desc = desc if re.search(r"antlerless|doe|cow|fawn|calf", desc, re.I) else desc + " (B license)"
        tail = " ".join(x.strip() for x in lines[i + 1:i + 3] if not LINE.match(x.strip()))
        lim = []
        for pat in (r"[^.]*private land[^.]*\.", r"[^.]*must be used with[^.]*\.", r"[^.]*[Oo]nly valid[^.]*\."):
            mm = re.search(pat, l[m.end():] + " " + tail)
            if mm: lim.append(mm.group(0).strip())
        k = f"{sp}:{code}"
        if k not in out: out[k] = {"bag": desc, "limits": " ".join(dict.fromkeys(lim))[:200]}
    return out
if __name__ == "__main__":
    d = json.load(open(os.path.join(P, "MT.json")))
    d["hunts"] = extract()
    json.dump(d, open(os.path.join(P, "MT.json"), "w"), indent=1)
    from collections import Counter
    print(len(d["hunts"]), Counter(v["bag"] for v in d["hunts"].values()).most_common(25))
