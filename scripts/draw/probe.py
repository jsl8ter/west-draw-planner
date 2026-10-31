"""Download report files and dump their structure so a parser can be written.

Usage: probe.py ST URL [URL ...]   (or ST alone to read URLs from scripts/draw/probe_ST.txt)
Writes data/draw/probe/ST/<n>.txt with: final URL, content type, size, and for PDFs the text of
the first 3 pages + last page + pdfplumber tables on page 1; for XLSX/XLS/CSV the sheet names and
first 40 rows of each sheet; for HTML the visible text (first 15k chars).
"""
import io, json, os, re, sys, urllib.request, csv
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) west-draw-planner/1.0"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.geturl(), r.headers.get("Content-Type", ""), r.headers.get("Content-Disposition", ""), r.read()

def dump(url):
    out = []
    final, ct, cd, data = get(url)
    out.append(f"URL: {url}\nFINAL: {final}\nTYPE: {ct}\nDISPOSITION: {cd}\nBYTES: {len(data)}\n")
    head = data[:8]
    if head.startswith(b"%PDF"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            n = len(pdf.pages); out.append(f"PDF PAGES: {n}\n")
            for i in sorted({0, 1, 2, n - 1}):
                if i < n:
                    out.append(f"\n----- PAGE {i+1} TEXT -----\n{(pdf.pages[i].extract_text() or '')[:6000]}")
            try:
                for t in pdf.pages[0].extract_tables()[:2]:
                    out.append("\n----- PAGE 1 TABLE -----\n" + "\n".join(" | ".join(str(c) for c in row) for row in t[:30]))
            except Exception as e:
                out.append(f"table error {e}")
    elif head.startswith(b"PK"):
        import openpyxl
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            for ws in wb.worksheets[:6]:
                out.append(f"\n----- SHEET {ws.title} (max_row={ws.max_row}, max_col={ws.max_column}) -----")
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    if i >= 40: break
                    out.append(" | ".join("" if c is None else str(c) for c in row))
        except Exception as e:
            out.append(f"zip/xlsx error: {e}")
    elif head.startswith(b"\xd0\xcf\x11\xe0"):
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        for sh in wb.sheets()[:6]:
            out.append(f"\n----- SHEET {sh.name} ({sh.nrows}x{sh.ncols}) -----")
            for r in range(min(40, sh.nrows)):
                out.append(" | ".join(str(c) for c in sh.row_values(r)))
    else:
        txt = data.decode("utf-8", "replace")
        if "<html" in txt[:2000].lower():
            txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", txt, flags=re.S | re.I)
            links = re.findall(r'href="([^"]+)"[^>]*>([^<]{0,120})<', txt)
            txt = re.sub(r"<[^>]+>", " ", txt); txt = re.sub(r"\s+", " ", txt)
            out.append("HTML TEXT:\n" + txt[:15000])
            out.append("\nLINKS:\n" + "\n".join(f"{t.strip()} | {h}" for h, t in links[:400]))
        else:
            out.append("TEXT/CSV:\n" + txt[:15000])
    return "\n".join(out)

def main():
    st = sys.argv[1]; urls = sys.argv[2:]
    if not urls:
        p = os.path.join(ROOT, "scripts", "draw", f"probe_{st}.txt")
        urls = [l.strip() for l in open(p) if l.strip() and not l.startswith("#")]
    d = os.path.join(ROOT, "data", "draw", "probe", st); os.makedirs(d, exist_ok=True)
    for i, u in enumerate(urls):
        try: txt = dump(u)
        except Exception as e: txt = f"URL: {u}\nERROR: {e}"
        open(os.path.join(d, f"{i:02d}.txt"), "w").write(txt)
        print(st, i, u[:90], "->", txt.splitlines()[1] if len(txt.splitlines())>1 else "", flush=True)

if __name__ == "__main__":
    main()
