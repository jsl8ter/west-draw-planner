"""Wyoming hunt-area limitations from the 2026 regulation text dump (sideways tables rotated by fetch_regs.py).
Rows look like '<area> <type> [<archery open> <close>] <open> <close> <quota> <limitations>' and two table
columns share a printed line. -> regs/WY.json hunts {"E-124-2": {"bag": "Antlered elk four (4) points or less ..."}}"""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
P = os.path.join(ROOT, "data", "draw", "regs")
D = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.? \d{1,2}"
ROW = re.compile(rf"(?<![\d,])(\d{{1,3}}) (\d|Gen) ((?:{D} ){{2,4}})(\d[\d,]*)?\s*")
SPX = {"ANTELOPE": "P", "DEER": "D", "ELK": "E"}
def extract():
    txt = open(os.path.join(P, "WY_text.txt")).read()
    out = {}
    for page in txt.split("\n===== "):
        if "[rotated" not in page: continue
        m = re.search(r"\b(ANTELOPE|DEER|ELK)\b", page)
        if not m: continue
        sp = SPX[m.group(1)]
        for line in page.splitlines():
            ms = list(ROW.finditer(line))
            for i, r in enumerate(ms):
                lim = line[r.end(): ms[i + 1].start() if i + 1 < len(ms) else len(line)].strip()
                area, typ = int(r.group(1)), r.group(2)
                if typ == "Gen" or not lim: continue
                k = f"{sp}-{area:03d}-{typ}"
                out.setdefault(k, {"bag": lim})
    return out
if __name__ == "__main__":
    d = json.load(open(os.path.join(P, "WY.json"))); d["hunts"] = extract()
    json.dump(d, open(os.path.join(P, "WY.json"), "w"), indent=1)
    print(len(d["hunts"]))
