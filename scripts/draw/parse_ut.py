# TEMP exploration
import io, re, requests, pdfplumber
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) west-draw-planner/1.0"}
def parse():
    r = requests.get("https://wildlife.utah.gov/odds", headers=UA, timeout=60)
    links = sorted(set(re.findall(r'href="([^"]*pdf/bg/202[3-6][^"]*)"', r.text)))
    LOG.append("ODDS LINKS:\n" + "\n".join(links))
    for u in ["https://wildlife.utah.gov/pdf/bg/2026/26_bg-odds.pdf", "https://wildlife.utah.gov/pdf/bg/2026/26_bg_odds.pdf",
              "https://wildlife.utah.gov/pdf/bg/2026/2026_bg-odds.pdf", "https://wildlife.utah.gov/pdf/bg/2026/26_deer_odds.pdf"]:
        try: LOG.append(f"HEAD {u} {requests.head(u, headers=UA, timeout=30).status_code}")
        except Exception as e: LOG.append(f"HEAD {u} {e}")
    for u in ["https://wildlife.utah.gov/pdf/bg/2025/25_bg-odds.pdf"]:
        data = requests.get(u, headers=UA, timeout=300).content
        out = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for i, p in enumerate(pdf.pages):
                t = p.extract_text() or ""
                ls = t.splitlines()
                out.append(f"{i+1}: " + " || ".join(ls[:2]))
                if len(ls) > 1 and not ls[1].startswith("Hunt:"):
                    out.append("FULL:\n" + t[:3000])
        LOG.append(u + "\n" + "\n".join(out))
    return {"state": "UT", "hunts": []}
