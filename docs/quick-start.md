# Quick start

One page, from an inventory export to a report you can read. Every flag is
in [usage.md](usage.md). The words in the report are in
[glossary.md](glossary.md).

## Before you start

**Windows is not a supported platform yet:** no one has run the tool on a
real Windows export. You can still try it there with the Windows steps
below.

1. **Open a command window.**
   - macOS: press Command and Space, type `Terminal`, press Return.
   - Windows: open the Start menu, type `PowerShell`, open
     "Windows PowerShell".
2. **Check Python.** Type this and press Return:
   - macOS and Linux: `python3 --version`
   - Windows: `py --version` (or `python --version`)

   It must print Python 3.9 or newer. If it does not, install Python from
   <https://www.python.org/downloads/> and open a new window.
3. **Put the files in place.** There is nothing to install. Download or
   clone the repo and put it next to your export, for example in your
   Documents folder:

       Documents/
         software-lifecycle/   the tool (holds software_lifecycle.py)
         inventory.csv         your export
         swlc-out/             the report (the tool makes this folder)

   Keep the export and the report outside the tool's folder. Real
   inventories are confidential, and so are the reports made from them.
   You do not need to make `swlc-out`: the check creates it.
4. **Go into the tool's folder.** Run every command from there.
   - macOS and Linux: `cd ~/Documents/software-lifecycle`
   - Windows: `cd $HOME\Documents\software-lifecycle`

The commands below start with `python3`. On Windows, type `py` (or
`python`) in its place, for example
`py software_lifecycle.py preflight ../inventory.csv`.

## Try the demo first

The demo inventory is made up and runs against synthetic test data, so it
gives the same report every time. This command writes the report into a
`swlc-demo` folder next to the tool's folder.

macOS and Linux:

    python3 software_lifecycle.py check examples/software-inventory.csv \
      --data tests/fixtures/data \
      --as-of 2026-10-24 \
      --golden examples/golden-sources.csv \
      --exceptions examples/exceptions.csv \
      --tracking examples/tracking.csv \
      --support-records examples/support-records.csv \
      --out ../swlc-demo

Windows PowerShell:

    py software_lifecycle.py check examples/software-inventory.csv `
      --data tests/fixtures/data `
      --as-of 2026-10-24 `
      --golden examples/golden-sources.csv `
      --exceptions examples/exceptions.csv `
      --tracking examples/tracking.csv `
      --support-records examples/support-records.csv `
      --out ../swlc-demo

Open `../swlc-demo/report.md`. It is the same as the committed
[sample report](../examples/sample-report.md), except for the sample's
note at the top. The Hostile Corp rows are planted tests of how the tool
handles unsafe text.

## 1. Get an export

Export your software inventory as a CSV file with a header row and save it
as `inventory.csv` next to the tool's folder (see the layout above). It
needs a name column and a version column; publisher, owner and count
columns help. The headings the tool accepts are in the
[README](../README.md), and export steps for some platforms are in
[platform-guide.md](platform-guide.md).

## 2. Run preflight first

    python3 software_lifecycle.py preflight ../inventory.csv

`preflight` reads the file and writes nothing. It prints your column
titles and numbers only, never a cell value. Read its output:

- **Columns** says which column it found for each field, or "not found".
- **What to fix** lists problems in plain words. Fix what it says in the
  export, or add a `--columns` file for headings it does not know (see
  [usage.md](usage.md)), then run `preflight` again.
- **Next command** is the `check` command to run.

## 3. Run the check

    python3 software_lifecycle.py check ../inventory.csv --out ../swlc-out

The tool creates `../swlc-out` if it is not there, writes `report.md`,
`report.json` and `report.csv` into it, and prints one line naming them.

## 4. Open the report

Open `../swlc-out/report.md` in any text editor or Markdown viewer. The
top says the checked-on date and the age of the data. Then come the lists:
past end of life, ends within the lookahead window, dates disagree,
couldn't match, names to review, in CISA KEV, accepted risk, ownerless
and golden source overrides. An item can be on more than one list. Each
term is explained in [glossary.md](glossary.md).

`report.csv` holds the same items as a table and opens in Excel, Numbers
or Google Sheets. Cells that a spreadsheet could read as a formula are
neutralized, so the spreadsheet does not run them.

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

The KEV snapshot the run used is more than 7 days older than the
checked-on date, or is dated more than a day after it. The "In CISA KEV"
list may then be out of date. The end-of-life dates come from their own
snapshot, with their own age shown at the top.

The data ships inside the tool's folder. Its dates are `kev_date` and
`eol_date` in `data/manifest.json`. What to do:

1. Get a newer copy of the tool (download it again, or `git pull`) and
   check `kev_date` in its `data/manifest.json`. If the date is newer, run
   the check again with that copy.
2. A data release published on its own can be used with `--data DIR`
   after you verify it; see "Data and release verification" in the
   [README](../README.md) and step 1 of [sop.md](sop.md).
3. `refresh_data.py` is the only file in the project that uses the
   network: it builds data releases and is run by the project's data
   workflows, so run it yourself only with your organisation's OK (see
   [SECURITY.md](../SECURITY.md)).

If no newer data is available, the KEV list may miss recent entries.

## Next

For a regular review, follow the quarterly procedure in [sop.md](sop.md)
and the one-page [checklist.md](checklist.md).
