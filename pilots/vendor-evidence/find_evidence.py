"""Pilot helper: keyword search over saved public vendor pages.

Read-only. Standard library only. Proposes candidate rows; never decides.
Usage: python3 -I find_evidence.py PAGES_DIR cases.json
"""
import json, re, sys, time
from pathlib import Path

DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}(?: \d{1,2}:\d{2}:\d{2} [AP]M)?|\d{4}-\d{2}-\d{2}|\b[A-Z][a-z]{2} \d{4}\b")

STOP = re.compile(r"^(Version |Windows |Ubuntu |Office |\d+\.\d+$|\d+\.x$)")

def cells(text):
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            out += [c.strip(" *[]") for c in line.split("|") if c.strip(" *[]")]
        elif line.strip(" |"):
            out.append(line.strip(" |"))
    return out

def search(page, row_re, header_re):
    cs = cells(page)
    hits = []
    for i, c in enumerate(cs):
        if re.search(row_re, c):
            row = [c]
            for d in cs[i + 1:i + 8]:
                if STOP.search(d):
                    break
                row.append(d)
            if not any(DATE.search(d) for d in row[1:]):
                continue
            heads = [h for h in cs[max(0, i - 12):i] if re.search(header_re, h)]
            hits.append({"row": row, "headers": heads[-4:]})
    return hits

def main(pages, cases):
    out = []
    for case in json.load(open(cases)):
        t0 = time.perf_counter()
        f = Path(pages) / case["page"]
        hits = search(f.read_text(errors="replace"), case["row_re"], case.get("header_re", "Date|Version|Branch|Release|End")) if f.exists() else []
        if case.get("edition_missing"):
            others = [h for p in case.get("other_pages", []) for h in search((Path(pages) / p).read_text(errors="replace"), case["row_re"], "Date|Version")]
            hits = hits + others
            verdict = "unresolved: edition missing; editions disagree" if len({h["row"][-1] for h in hits}) > 1 else "unresolved: edition missing"
        elif case.get("other_pages"):
            others = [h for p in case["other_pages"] for h in search((Path(pages) / p).read_text(errors="replace"), case["row_re"], "Date|Version")]
            hits = hits + others
            verdict = "unresolved: sources conflict" if len({h["row"][-1] for h in hits}) > 1 else None
        else:
            verdict = None
        flags = sorted({"stamp 6:59/7:59 AM: may be the end of the previous day in PT; confirm against the vendor announcement"
                        for h in hits for c in h["row"] if re.search(r"\b[67]:59:59 AM", c)})
        out.append({"case_id": case["case_id"], "page": case["page"], "n_hits": len(hits),
                    "hits": hits[:3], "flags": flags, "seconds": round(time.perf_counter() - t0, 3),
                    "verdict": verdict or ("unresolved: no row found" if not hits else
                               "unresolved: several rows" if len(hits) > 1 else "candidate: human verifies")})
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main(*sys.argv[1:3])
