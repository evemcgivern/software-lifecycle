# Standard operating procedure: quarterly software lifecycle review

Each quarter, run the check to find software past or near end of life,
decide what to do about each item, and keep a record of the decisions.

Matching covers only the products endoflife.date lists. The report is not
a complete view of the inventory and not a licence position.

New to the tool? Start with [quick-start.md](quick-start.md). The words in
the report are explained in [glossary.md](glossary.md).

## Roles

The tool names roles. It never assigns people. Your organization decides
who holds each role.

- Asset owner: requests risk acceptance for an item.
- Risk owner: signs off on accepted risk.
- Independent approver: also signs off, and is not the person who
  requested the acceptance.
- ITAM lead: settles every "dates disagree" item.
- Contract owner: decides whether to renew or end each support record,
  using the dates in the contract.

## Cadence

- Review the whole run every quarter.
- Review the KEV overlay whenever it changes (a new data release).
- Evidence retention is your choice. The tool keeps no run history by
  default, so decide what you keep and for how long (step 12).

## Steps

### 1. Get the data

Check the bundled data's age. The report header lists the data release and
the snapshot dates.

If the report warns that the KEV snapshot is older than 3 days or the
end-of-life snapshot is older than 30 days, fetch a newer data release.
Verify it online with `gh attestation verify` (command in the
[README](../README.md)). Then run
`python3 software_lifecycle.py verify-data --data DIR`.

### 2. Export the inventory

Use [platform-guide.md](platform-guide.md) or your own source.

On a new export, run `python3 software_lifecycle.py preflight
inventory.csv`. It shows which columns the tool found and what to fix.

Real inventories are Confidential. Keep them on the machine that runs the
tool.

### 3. Run the check locally

Pass your override files and last quarter's report:

    python3 software_lifecycle.py check inventory.csv --golden golden-sources.csv --exceptions exceptions.csv --tracking tracking.csv --support-records support-records.csv --previous last-quarter/report.json --out ../swlc-this-quarter

If an AI agent runs it, use `--counts-only` and keep the output folder out
of the agent's reach. No model should read the full report. A desktop chat
app can use the optional counts-only server instead (see
[mcp-setup.md](mcp-setup.md)).

The counts are items and inventory rows. A row count is not an install
count or a machine count.

### 4. Read "Changes since the previous report"

This section shows what is new, gone or changed.

The first run after an upgrade that adds matching by product title shows a
long state-changed list (`diff.changed_state`). Items that were unmatched
now match, and golden-source and exception rows keyed by product id now
apply to them. Check those rows once.

A data folder in format 1 still loads, with a warning and generated
matching off, so its report matches by alias only.

### 5. Work "Past end of life" and "Ends within the lookahead window"

For each item, the owner chooses: replace, upgrade, retire, or request
risk acceptance (step 8).

If a support record is listed in your file, the item shows it ("A support
record is listed in your file: REF, KIND, ends on DATE (scope: ...)." or
"ended on DATE"). Use it to weigh paying for extended support against
migrating. The tool does not check that a record was paid for or is
current, and extended support may include only some fixes or editions.

Then read the "Support records" section. For each record that ends within
the window, the contract owner decides whether to renew it or let it end.
Notice and renewal dates come from the contract, not from the tool.

Check each record not matched to a dated item in this inventory. That
includes a product that is in the inventory without a decided cycle or
version, and discovery coverage is unknown, so the product may still be in
use.

After a data refresh, a record whose product ID was renamed or removed
stops the run. Fix the row's product ID.

**Decision needed:** the owner's choice for each item, and the contract
owner's renew-or-end choice for each support record.

### 6. Work "In CISA KEV, past or near end of life"

These items are past or near end of life, and their vendor and product
appear in CISA KEV. This does not mean your version is affected. A person
checks the version against the KEV entries and decides the priority.

`kev: false` means "no match under those rules", not "known safe".

**Decision needed:** whether each item is affected, and its priority.

### 7. Settle "Dates disagree"

The ITAM lead picks the right date for each item. If it will keep
recurring, record the choice as a row in `golden-sources.csv` with a
`review_by` date.

If two rows could apply to one item (one by product ID and one by name),
the product-ID row is used and the report warns "N item(s) matched two
golden-source rows; the product-id row was used." Remove the extra row.

**Decision needed:** the ITAM lead's choice of date and review-by date.

### 8. Handle accepted risk

The asset owner requests risk acceptance. The risk owner and an
independent approver sign off. Record it in `exceptions.csv` with
compensating controls, an expiry date and your record reference.

The tool rejects a file where the approver and the requester are the same
person. It does not confirm that anyone gave approval.

**Decision needed:** the risk owner's and approver's sign-off. Renew or
end any item flagged `EXCEPTION_EXPIRED`.

### 9. Handle "Couldn't match"

Check whether the name is a real product. If it is, open an
unmatched-product issue in the project's issue tracker with the public
product name, publisher and version format only. Never put inventory rows,
owner names or report text in a public issue.

Until it is matched, track the item by hand.

### 10. Assign owners to the "Ownerless" items

Give each item in the "Ownerless" list an owner.

### 11. Raise change requests

For each finding that needs action, open a change request in your own
system. Add a row to `tracking.csv`: the item ID, the change reference
and, if there is one, the problem reference. The next run shows those
references beside the item.

### 12. Keep evidence

Decide what to keep. A usual set:

- `report.json` (it holds the data release ID, file hashes and override
  file hashes)
- the override files
- the sign-off records from step 8

The reports contain inventory text, so store them as Confidential. Keep
the `report.json` for the next run's `--previous`.

### 13. Review the overrides

Check each `review_by` and `expires_on` date coming up. The tool lists
expired ones.

## Questions a governance council will ask

**Who proves the tool makes no network calls?** The tests in this repo.
`tests/test_no_network.py` runs the tool with network calls blocked
(`test_check_runs_with_network_calls_blocked`) and checks that no module
imports a network library
(`test_no_swlc_module_imports_a_network_library`). This is the project's
own test. It is not an independent assessment, and the tool has not been
independently assessed.

**What are the data terms?** The end-of-life data derives from the
endoflife.date repository (MIT, with attribution). The KEV data derives
from the CISA catalog (CC0 1.0). See THIRD-PARTY.md.

**Who owns the alias table and the golden sources?** Your team owns
`golden-sources.csv` and `exceptions.csv`. The maintainer owns the alias
table (the list that maps inventory names to products).

**What happens if the maintainer stops?** The tool is offline and uses
only the Python standard library, so it keeps working on the last data
release you hold. It warns when data goes stale: after 3 days for KEV and
30 days for the end-of-life snapshot. After 7 days it reports the KEV
overlay as "not current". New data and new aliases would stop arriving.

**How does a finding become a change request?** Through your change
process. The tool does not create tickets. You raise the change, then
record its reference in `tracking.csv` (step 11).

**Does it follow a standard?** `docs/crosswalk.csv` maps the themes to
published standards as a reference. The ITIL 4 and ISO/IEC 20000-1 cells
are not checked against the official text and are marked in
`unverified_columns`. See [themes.md](themes.md).

The KEV overlay is a reference for prioritization. It does not show
compliance with any standard. CISA's current binding directive for US
federal civilian agencies, BOD 26-04, superseded BOD 22-01 (source:
<https://www.cisa.gov/news-events/directives/bod-26-04-prioritizing-security-updates-based-risk>).
It is a reference only. It binds federal civilian agencies only. This tool
does not implement it or its deadlines.

**What is the support level?** Maintained as time allows, best effort, no
SLA. This is an experiment with a review date of 2027-01-31. On that date
the maintainer decides whether to keep it, archive it, or fold it into
another project.

## Maintainer: when the weekly data job fails

This part is for the project maintainer, not for a quarterly review.

The "endoflife.date weekly pull request" job runs the full test suite on
the new data before it opens a pull request. When a test fails, it opens
no pull request and opens or updates one issue labelled
`eol-weekly-failed`.

1. **Find the failing test.** Open the run linked from the issue. The
   step that failed is either `verify-data` (the data check) or the test
   suite. In the suite's output, find the failing test's name and
   message.
2. **Find the product.** Usually upstream renamed or removed a product
   that a gold row in `tests/benchmark/gold.csv` or an entry in
   `data/curation.json` names. A data check that stops with
   "curation.json: a product named here is not in the catalog" means a
   curation entry names a removed product. Compare the run's catalog
   summary with `data/products.json` on main to see which one.
3. **Fix it on main.**
   - A curation entry names a removed or renamed product: update or
     remove that entry in `data/curation.json` with its reason and
     source, rebuild the manifest (see "Extending the curation file" in
     [usage.md](usage.md)) and run the full suite.
   - A gold row or a floor no longer holds: open an issue that names the
     product and the test. Do not merge a workaround.
   - Never lower `tests/benchmark/floor.json` and never edit a gold row
     to make a test pass, unless the maintainer has recorded the decision
     and its reason in the commit and in `tests/benchmark/README.md`.
   - Example (issue #74): upstream added old cycles (LibreOffice 6.0,
     MySQL 4.0, Notepad++ 6.0, PHP 4.0), so gold rows that expected the
     product with cycle `none` (no cycle in the snapshot) now got a real
     cycle and scored hard wrong. The rows' premise was out of date, and
     the maintainer approved relabelling them. Main still has the old
     data, so the exact new cycle would fail there. The rows were set to
     an empty cycle (any cycle is fine), which is correct on both, and
     can be tightened to the exact cycle after the weekly data is merged.
4. **Run it again.** After the fix is on main, run "endoflife.date weekly
   pull request" by hand from the Actions tab, or wait for the next
   weekly run. Close the issue once a pull request opens.

The weekly job sets `SWLC_WEEKLY_JOB`. With it, the generated-row floor of
the benchmark is reported (in the test's skip message), not checked,
because an ordinary upstream rename changes generated rows. The hand and
catalog floor, hard wrong and soft wrong are checked in every run. Every
pull request and local run checks the generated floor too.
