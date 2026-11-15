# Vendor-evidence pilot: report

Checked 2026-11-15. Public vendor pages and two invented cases only. No
inventory was used. Nothing in `swlc/`, the report schema, KEV logic or
overrides changed.

Files here: `worksheet.csv` (13 cases), `cases.json` (search terms),
`find_evidence.py` (throwaway helper, standard library, read-only),
`results.json` (helper output). Vendor page copies are not stored; the
worksheet keeps the URL, section, table headings and the matching row.

## Go / no-go

**No-go on a runtime helper. Go on the worksheet, filled in by hand.**

The helper produced no wrong picks, but I tuned it after seeing the
results, there are 13 cases, and I did not measure a human. There is no
evidence yet that it saves time. The worksheet fields and the two rules
below are the part worth keeping.

## Results (13 cases: 11 public, 2 invented)

| Measure | Helper | Cheap-model lookup (Haiku, 10 cases) |
|---|---|---|
| Cases it proposed a row for | 7 | 8 |
| Wrong edition, release or tier | 0 (final), 2 (first run) | 0 |
| Wrong day (off by one) | 0, it prints the date as shown and flags the stamp | 4 (C01, C02, C04, C05) picked the table date over the announced date |
| Missing evidence left unresolved | 5 of 5 | 2 of 2 asked (C06, C07) |
| Over-cautious (unresolved when a row exists) | 1 (C08, same table appears twice) | 0 |

First helper run, before I changed it: it silently chose Home/Pro for a
Windows 11 item with no edition (C03), reused the Office Standard row for
Professional Plus (C06, my search term was too loose), and found nothing
for Python 3.12, Python 2.7 and Node.js 20 (my parser did not read their
table layouts). I fixed all five, so the final numbers are tuned to this
set and say little about new cases.

Time to a usable citation: **Not measured.** Nobody timed a human. The
helper searches a saved page in under 10 ms; saving the pages and
reading the result still takes a person. The Haiku fetches took 60 to 100
seconds per batch of five cases.

## What the cases show

1. **Edition decides the date (C01, C02, C03).** Windows 11 24H2 ends
   2026-10-13 for Home/Pro and 2027-10-12 for Enterprise/Education. With
   no edition in the inventory the answer is unresolved. A
   `golden-sources.csv` row has one date per product, so it cannot hold
   both. A row for `windows` would set the wrong date for one edition.
2. **Printed dates can be a day late (C01, C02, C04, C05).** Microsoft
   tables print `6:59:59 AM`, which is the end of the previous day in
   Pacific time. The bundled data matches the announced day. A model that
   copies the table gets a date one day off. The helper prints the stamp
   with a flag and leaves the day to a person.
3. **Normal and paid tiers sit in different columns (C04, C08).** The
   bundled `eol` for Windows Server 2022 is the extended date (2031-10-14),
   not the mainstream date (2026-10-13). A reviewer needs both on one line.
4. **Some evidence is not in the page text (C05 ESU, C07 RHEL 8).** Red
   Hat shows RHEL 8 dates in a chart. Microsoft's ESU page returned HTTP
   403 to `curl`; the 2027-10-12 ESU date came from a summarised fetch and
   is **Unverified**.
5. **Month-only sources (C08, C09).** Ubuntu and Python print the month.
   The bundled day (for example 2028-10-31) cannot be confirmed from the
   vendor page.

## The paper

arXiv 2608.06305 (READ) checks out on three of four claims in the
handoff: 51 questions on one financial report; READ beat tuned dense
retrieval by 23.5 points (p=0.017); BM25 is statistically
indistinguishable and costs about a third as much ($0.020 vs $0.058 per
question). **The fourth is wrong as worded.** The paper's own test
removing the outline tool scored higher (66.7% vs 58.8%, p=1.00). The
authors credit reading whole documents instead of top-k chunks, not
structure, and say they cannot claim the full tool set is best. They also
state: one document, one model, benchmark built by the system's authors.
The paper gives no support for a result on vendor lifecycle pages.

## If a human wants to continue

1. Time one reviewer on 5 of these cases by hand, then with
   `find_evidence.py`. Write the seconds in `worksheet.csv`.
2. Add `edition_scope` and `source_locator` columns to a copy of
   `golden-sources.csv` as a proposal. That changes a template, which is
   the maintainer's call, so it is not done here.
