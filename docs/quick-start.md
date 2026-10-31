# Quick start

One page, from an inventory export to a report you can read. Every flag is
in [usage.md](usage.md). The words in the report are in
[glossary.md](glossary.md).

## Before you start

You need Python 3.9 or newer. There is nothing to install: download or
clone the repo and run every command from the repo root (the folder that
holds `software_lifecycle.py`).

- **macOS and Linux:** type the commands as shown, starting with
  `python3`.
- **Windows:** Windows is not a supported platform yet: no one has run
  the tool on a real Windows export. To try it, type `py` (or `python`)
  in place of `python3`, for example
  `py software_lifecycle.py preflight inventory.csv`.

Use a short output folder next to the repo, such as `../swlc-out`, not a
folder inside it. Real inventories are confidential, and so are the
reports made from them.

## Try the demo first

The demo inventory is made up and runs against synthetic test data, so it
gives the same report every time:

    python3 software_lifecycle.py check examples/software-inventory.csv --data tests/fixtures/data --as-of 2026-10-24 --out ../swlc-demo

Open `../swlc-demo/report.md`. With the demo's four sample files added
(the full command is in [examples/README.md](../examples/README.md)) the
report is the same as the committed
[sample report](../examples/sample-report.md).

## 1. Get an export

Export your software inventory as a CSV file with a header row. It needs
a name column and a version column; publisher, owner and count columns
help. The headings the tool accepts are in the [README](../README.md),
and export steps for some platforms are in
[platform-guide.md](platform-guide.md).

## 2. Run preflight first

    python3 software_lifecycle.py preflight inventory.csv

`preflight` reads the file and writes nothing. It prints your column
titles and numbers only, never a cell value. Read its output:

- **Columns** says which column it found for each field, or "not found".
- **What to fix** lists problems in plain words. Fix what it says in the
  export, or add a `--columns` file for headings it does not know (see
  [usage.md](usage.md)), then run `preflight` again.
- **Next command** is the `check` command to run.

## 3. Run the check

    python3 software_lifecycle.py check inventory.csv --out ../swlc-out

The tool writes `report.md`, `report.json` and `report.csv` into
`../swlc-out` and prints one line naming them.

## 4. Open report.md

Open `../swlc-out/report.md` in any text editor or Markdown viewer. The
top says the checked-on date and the age of the data. Then come the lists:
past end of life, ends within the lookahead window, dates disagree,
couldn't match, names to review, in CISA KEV, accepted risk, ownerless
and golden source overrides. An item can be on more than one list. Each
term is explained in [glossary.md](glossary.md).

## 5. Names to review and couldn't match

- **Names to review** are not findings. The tool left each one unmatched
  on purpose because the row lacks evidence, usually a publisher. Add a
  publisher that names the vendor and run again, or record that it is a
  different product. See "Names to review" in [usage.md](usage.md).
- **Couldn't match** rows have no date from the tool. Check whether each
  name is a real product. To match it on your own copy, see "Extending the
  alias table" in [usage.md](usage.md). To ask for it in the bundled data,
  open the "Product the tool could not match" issue form with the product
  name, publisher and version format only, never inventory rows.

## 6. If the report says "KEV overlay is not current"

The KEV data the run used is more than 7 days older than the checked-on
date, so the "In CISA KEV" list may be out of date. The end-of-life dates
still come from their own snapshot, with their own age shown at the top.

The bundled data's dates are `kev_date` and `eol_date` in
`data/manifest.json`. To fix it, get a newer data release, verify it, and
point the check at it with `--data DIR`; the steps are in "Data and
release verification" in the [README](../README.md) and step 1 of
[sop.md](sop.md). `refresh_data.py` is the only file in the project that
uses the network: it builds data releases and is run by the project's data
workflows, so run it yourself only with your organisation's OK (see
[SECURITY.md](../SECURITY.md)).

## Next

For a regular review, follow the quarterly procedure in [sop.md](sop.md)
and the one-page [checklist.md](checklist.md).
