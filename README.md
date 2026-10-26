# software-lifecycle

`software_lifecycle.py` reads a software inventory export and lists what is
past end of life or close to it. It also adds a KEV overlay: an extra
flag that marks items whose vendor and product appear in CISA's list of
known exploited vulnerabilities (the KEV catalog), so a person can review
them first.

Runs locally with no network by default; built to enterprise security
practices; not independently assessed.

It needs Python 3.9 or newer and nothing else. It uses only the standard
library.

## Install

There is nothing to install. Clone the repo or download a release, then run
the commands below from the repo root with `python3 software_lifecycle.py`.

## Quick start

Run these from the repo root.

1. Try the demo. The demo inventory is made up and runs against synthetic
   data, so the output never changes with the date:

       python3 software_lifecycle.py check examples/software-inventory.csv --data tests/fixtures/data --as-of 2026-10-24 --golden examples/golden-sources.csv --exceptions examples/exceptions.csv --tracking examples/tracking.csv --out /tmp/swlc-demo

2. Open `/tmp/swlc-demo/report.md`. `report.json` and `report.csv` are in
   the same folder.
3. Run your own inventory against the bundled real data:

       python3 software_lifecycle.py check YOUR-INVENTORY.csv --out ../swlc-out

   Real inventories are confidential. Read "Privacy and security" below
   first. Running the demo inventory against the bundled data lists every
   item as "couldn't match", because the demo names are made up.

All commands and flags are in [docs/usage.md](docs/usage.md).

## What you get

The report has these lists. An item can be on more than one.

- Past end of life.
- Ends within the lookahead window (12 months unless you change it).
- Dates disagree: the export's own date and the endoflife.date date differ,
  or a golden source has expired, or a golden source says to use the export
  date and the export has no usable one (`GOLDEN_EXPORT_UNUSABLE`).
- Couldn't match: the name and version did not map to a known product and
  cycle. The tool claims no date for these.
- Review urgently: the item is past or near end of life and its vendor and
  product appear in CISA KEV. The wording is "needs review". KEV matches
  vendor and product only, never version. The tool never says "vulnerable".
  The report prints this line: The vendor and product appear in CISA KEV. This does not mean your version is affected.
- Accepted risk: listed in your exceptions file.
- Ownerless: no owner in the export.
- Golden overrides: items whose state changed because a golden source
  chose a different date. A golden source that changes the date but not the
  state is not listed.

The report files are `report.json`, `report.md` and `report.csv`. Their
fields are in [docs/report-schema.md](docs/report-schema.md).

## Your input file

The file is a CSV with a header row. Two columns are required. The tool
matches headings after ignoring case, punctuation and spacing, and it never
guesses.

| Field | Headings it accepts |
|---|---|
| name (required) | name, software name, software, product, product name, display name, application, application name, app name, title |
| version (required) | version, software version, product version, display version, app version, release, build |
| publisher | publisher, vendor, manufacturer, software publisher, software vendor, company |
| owner | owner, assigned to, business owner, technical owner, application owner, managed by, contact, owned by |
| count | count, install count, installs, installations, installed count, number of installs, quantity, qty, instances, device count |
| export_eol | export eol, end of life, eol, eol date, end of life date, end of life eol |
| export_support | export support, end of support, eos, end of support date, support end date, support end |
| parent | parent, parent software, suite, bundle |

The `parent` column is optional. It names the row's parent software, such
as the suite a part belongs to. A blank or placeholder cell (`n/a`, `none`)
means no parent. See "The Parent column" in [docs/usage.md](docs/usage.md).

The `count` and `export_support` headings are accepted but not used in
this version: the tool reads them and does nothing with them. `rows` in the
report counts inventory rows, not installs.

If a required heading is missing, the tool stops and names the field. If
two columns map to one field, it stops too. `--columns FILE` adds your own
headings; see `templates/columns.example.json`. A blank layout is in
`templates/inventory-template.csv`.

Export dates must be ISO dates (`2026-01-15`, optionally with a time).
Day-first and month-first dates are never read. For a matched item with no
active golden source, an unreadable export date puts the item on "dates
disagree".

### Profiles

`--profile` picks a pre-filled list of extra headings for an export source.
The profiles `flexera`, `servicenow-mbs` and `rapid7` are read from
`data/profiles.json`. All three are marked **Unverified**: no one has run
them on a real export yet. The report says so when you use one. See
[docs/platform-guide.md](docs/platform-guide.md).

## Override files

You own these files. The tool never changes them.

- `golden-sources.csv` says which date is right for a product (the
  endoflife.date date, the export's date, or a manual date) and when to
  review that choice.
- `exceptions.csv` records accepted risk: compensating controls, a risk
  owner, an approver who is not the requester, an expiry date and a
  reference.
- `tracking.csv` links a finding's item ID to a change reference and a
  problem reference.

Blank copies are in `templates/`. The column rules are in
[docs/report-schema.md](docs/report-schema.md). The quarterly process is in
[docs/sop.md](docs/sop.md).

## Privacy and security

The claims line at the top of this file is the whole claim. Nothing here
goes beyond it.

- Real inventories are Confidential. Run them only through the local
  script, or through an AI agent in `--counts-only` mode.
- In `--counts-only` mode the tool prints only counts, item IDs, the
  checked-on date and the `kev_current` flag; the full report is written to
  a file. An agent can still read that file:
  nothing technical stops it. Tell the agent not to, and keep the output
  folder out of its reach.
- No model should read the full report. Letting an AI read the CSV
  directly is not a mode of the tool. Do it only with synthetic or
  non-sensitive inventories.
- The default keeps no run history. Keeping evidence is your choice. See
  [docs/sop.md](docs/sop.md).
- The tool prints roles (asset owner, risk owner, approver, ITAM lead). It
  never assigns people.
- Details of the supply chain are in [SECURITY.md](SECURITY.md). See it for
  how to report a security problem.

CISA's current binding directive for US federal civilian agencies, BOD 26-04, superseded BOD 22-01. It is a reference only. It binds federal civilian agencies only. This tool does not implement it or its deadlines. Details are not reviewed here (Unverified).

## Data and release verification

The bundled data holds end-of-life dates from the endoflife.date product
files and the CISA Known Exploited Vulnerabilities catalog. Its release ID,
upstream commit, snapshot dates and catalog version are in
`data/manifest.json`. Read them there; they change when a new data release
is merged.

- `data/eol/*.json` derive from endoflife.date product files (MIT).
  Product descriptions are not included. See THIRD-PARTY.md for the
  attribution and licence text.
- `data/products.json` derives from the same endoflife.date product files:
  product id, title, category, CPE vendor names and package owner names
  only. `data/curation.json` is a hand-kept file of maintainer decisions.
  See "The data folder" in [docs/usage.md](docs/usage.md).
- `data/kev.json` derives from the CISA Known Exploited Vulnerabilities
  catalog (CC0 1.0), https://www.cisa.gov/known-exploited-vulnerabilities-catalog.

Staleness rules: a KEV snapshot older than 3 days gives a warning, and
older than 7 days the KEV overlay is reported as "not current". An
end-of-life snapshot older than 30 days gives a warning.

The bundled data is a snapshot. KEV data releases are published daily.
The weekly end-of-life job opens a pull request, and the next daily release
carries the dates once it is merged. Point `--data` at any
directory that holds a verified data release to use one.

The tool checks a SHA-256 manifest every time it loads data
(`verify-data` runs only that check). That catches a damaged data folder.
It does not prove who made the files. The tool never claims to verify
attestations offline. The first data release was attested on 2026-10-25,
while the repository was public. The daily release workflow is disabled
while the repository is private, and GitHub attestations on a private
repository need GitHub Enterprise Cloud. When a release carries a GitHub
artifact attestation, check it online before you use the release:

    gh attestation verify data.zip --repo evemcgivern/software-lifecycle --signer-workflow evemcgivern/software-lifecycle/.github/workflows/kev-daily.yml --source-ref refs/heads/main

## How it can be wrong

- Coverage is partial. In the data release bundled when this was written
  (the weekly job can change the counts), the tool can match 454 of the 485
  products in `data/eol/`. Most are matched by the product's title from endoflife.date
  (`data/products.json`). `data/aliases.json` adds 19 aliases for
  11 products (mssqlserver, windows-server, windows, office,
  python, nodejs, ubuntu, eclipse-temurin, windows-powershell, mysql,
  bellsoft-liberica). `data/curation.json` adds hand-kept vendor names for
  73 products and a short list of one-word product names. A further list
  of coined one-word titles matches a row with no publisher when the name
  carries a version that decides the cycle (`nginx 1.24.0`). The other 31
  products are devices, products left out on purpose, or one-word titles
  with no vendor to check, and never match.
- That is a count of products, not a hit rate. On the project's own
  benchmark (the 1,673 hand-written and catalog rows in
  `tests/benchmark/gold.csv`), 790 rows should match a product. 484 of them
  are scored correct: 384 with the right cycle, and 100 rightly with the
  product and no cycle. Of the 676 rows that need a cycle, 384 get one. The other 883 rows are
  traps that should stay unmatched, and all 883 do. It is a benchmark, not a
  real estate. The rate on a real estate is unknown.
- No wrong lifecycle claim was found on the benchmark. That is not proof for
  other inventories: unknown in general.
- Software with no lifecycle policy, for example git, curl and vim, is
  outside the data and will never match. Long "couldn't match" lists will
  remain. That is safer than a wrong guess. A golden source does not apply
  to an unmatched item.
- To add your own aliases, see "Extending the alias table" in
  [docs/usage.md](docs/usage.md). The maintainer extends the bundled data
  from "couldn't match" reports; the issue form takes names only.
- Build numbers versus cycles: a product whose version is a build number
  may map to the wrong cycle or none. Check the cycle shown in the report.
- Names must match strictly. A name with extra words after the product name
  often lands in "couldn't match". That is safer than a wrong guess.
- SQL Server 2016 and older are unmatched in this version, because
  endoflife.date lists service-pack cycles for them.
- Java 8 names that carry an update number are unmatched.
- KEV matches vendor and product only, never version. A match means "needs
  review", not "your version is affected".
- KEV is checked through the alias table's vendor and product pairs for
  matched products. For a product matched by name but without such a pair,
  the tool compares the publisher and the full inventory name (version
  included) with KEV, exactly. So `kev: false` means "no match under those
  rules". It does not mean the software is known safe.
- `windows-server` and the Windows 10 client aliases use the broad
  Microsoft and Windows KEV pair, because CISA files Windows flaws under
  the product Windows. Every Windows entry matches.
- Windows 10 names with extra words, such as "Windows 10 Enterprise 22H2",
  land on NO_ALIAS. Windows 11 has no alias and is unmatched.
- The profiles are Unverified until run on a real export.
- Data is a snapshot and can be out of date.
- CI runs the tests on Python 3.9 to 3.13. The tool was tested on macOS
  and Linux. Windows is untested; the quick-start paths and the `python3`
  command assume Unix.

## Maintaining

This is an experiment with a review date of 2027-01-31; on that date the
maintainer decides whether to keep it, archive it, or fold it into another
project. Maintained as time allows, best effort, no SLA, not independently assessed.

- GitHub turns off scheduled workflows in a public repository after
  60 days with no repository activity. Tags and releases may not count as
  activity, so the daily data releases alone may not keep the schedules
  on. If the daily or weekly job stops, turn it back on in the Actions tab
  or push a commit.
- The CI test matrix runs on `ubuntu-24.04`, pinned so the Python 3.9 leg
  keeps working. Python 3.9 is past end of life upstream; drop it from the
  matrix when that runner image stops offering it.

Already set up (as of 2026-10-25):

- The `data-release` environment exists, limited to main.
- The label `alias-request` exists. The "Product the tool could not match"
  issue form applies it.
- The label `eol-weekly-failed` is used by the weekly job's failure report
  (one issue, opened or updated when the weekly update stops). Create it
  once by hand; the job also creates it if it is missing.

The repository is currently private. When it goes public again:

- Turn private vulnerability reporting on again (it was on while the
  repository was public on 2026-10-25). SECURITY.md and the issue-template
  link send reporters there, and no email address is given.
- Re-enable the daily KEV and weekly end-of-life workflows.
- Check that "Allow GitHub Actions to create and approve pull requests" is
  on in the Actions settings. The weekly end-of-life job opens its pull
  request with the job token.
- Re-run the dry runs.

Run the tests from the repo root:

    python3 -B -m unittest discover -s tests

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full rules, and
[SECURITY.md](SECURITY.md) for how to report a security problem. Agents
read [AGENTS.md](AGENTS.md).

If a product lands in "couldn't match", open the "Product the tool could not
match" issue form. Give the public product name, the publisher and the
version format. Names only: never paste inventory rows, owner names or
reports into a public issue.

The crosswalk to standards is in `docs/crosswalk.csv`; how to read it is in
[docs/themes.md](docs/themes.md).

## Licence

MIT. See LICENSE. Third-party material: THIRD-PARTY.md.
