# software-lifecycle

`software_lifecycle.py` reads a software inventory export and lists what is
past end of life or close to it. It also marks items whose vendor and
product appear in the CISA Known Exploited Vulnerabilities (KEV) catalog, so
a person can review them first.

Runs locally with no network by default; built to enterprise security
practices; not independently assessed.

It needs Python 3.9 or newer and nothing else. It uses only the standard
library.

## Quick start

Run these from the repo root.

1. Try the demo. The demo inventory is made up and runs against synthetic
   data, so the output never changes with the date:

       python3 software_lifecycle.py check examples/software-inventory.csv --data tests/fixtures/data --as-of 2026-10-24 --golden examples/golden-sources.csv --exceptions examples/exceptions.csv --tracking examples/tracking.csv --out /tmp/swlc-demo

2. Open `/tmp/swlc-demo/report.md`. `report.json` and `report.csv` are in
   the same folder.
3. Run your own inventory against the bundled real data:

       python3 software_lifecycle.py check YOUR-INVENTORY.csv --out out

   Real inventories are confidential. Read "Privacy and security" below
   first. Running the demo inventory against the bundled data lists every
   item as "couldn't match", because the demo names are made up.

All commands and flags are in [docs/usage.md](docs/usage.md).

## What you get

The report has these lists. An item can be on more than one.

- Past end of life.
- Ends within the lookahead window (12 months unless you change it).
- Dates disagree: the export's own date and the endoflife.date date differ,
  or a golden source needs a decision.
- Couldn't match: the name and version did not map to a known product and
  cycle. The tool claims no date for these.
- Review urgently: the item is past or near end of life and its vendor and
  product appear in CISA KEV. The wording is "needs review". KEV matches
  vendor and product only, never version. The tool never says "vulnerable".
  The report prints this line: The vendor and product appear in CISA KEV. This does not mean your version is affected.
- Accepted risk: listed in your exceptions file.
- Ownerless: no owner in the export.
- Golden overrides: a golden source changed the date used.

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

If a required heading is missing, the tool stops and names the field. If
two columns map to one field, it stops too. `--columns FILE` adds your own
headings; see `templates/columns.example.json`. A blank layout is in
`templates/inventory-template.csv`.

Export dates must be ISO dates (`2026-01-15`, optionally with a time).
Day-first and month-first dates are never read; they go to "dates
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
- `--counts-only` prints counts and item IDs only. The inventory text does
  not reach the agent. Honest limit: the report files are still written to
  `--out`, and nothing technical stops an agent from reading them. Tell the
  agent not to, and keep the output folder out of its reach.
- No model should read the full report. Chat mode, where a model reads the
  CSV itself, is for synthetic or non-sensitive inventories only.
- The default keeps no run history. Keeping evidence is your choice. See
  [docs/sop.md](docs/sop.md).
- The tool prints roles (asset owner, risk owner, approver, ITAM lead). It
  never assigns people.
- Details of the supply chain are in `SECURITY.md`. Report problems there,
  privately.

CISA's current binding directive for US federal civilian agencies, BOD 26-04 (which superseded BOD 22-01), is a reference; it binds federal civilian agencies only; this tool does not implement it or its deadlines; details not reviewed here (Unverified).

## Data and release verification

The bundled data is release `bundled-2026.10.24`: end-of-life dates from
the endoflife.date product files at upstream commit
`7cfb122846893f10ee819ab47b615eff261945d0` (snapshot dated 2026-10-24), and
the CISA Known Exploited Vulnerabilities catalog version 2026.10.23
(released 2026-10-23).

- `data/eol/*.json` derive from endoflife.date product files (MIT).
  Product descriptions are not included. See THIRD-PARTY.md for the
  attribution and licence text.
- `data/kev.json` derives from the CISA Known Exploited Vulnerabilities
  catalog (CC0 1.0), https://www.cisa.gov/known-exploited-vulnerabilities-catalog.

Staleness rules: a KEV snapshot older than 3 days gives a warning, and
older than 7 days the KEV overlay is reported as "not current". An
end-of-life snapshot older than 30 days gives a warning.

The bundled data is a snapshot. The scheduled refreshes (KEV daily,
end-of-life weekly) publish newer data releases. Point `--data` at any
directory that holds a verified data release to use one.

The tool checks a SHA-256 manifest every time it loads data
(`verify-data` runs only that check). That catches a damaged data folder.
It does not prove who made the files. The tool never claims to verify
attestations offline. Each data release carries a GitHub artifact
attestation. Check it online before you use a release:

    gh attestation verify data.zip --repo evemcgivern/software-lifecycle --signer-workflow evemcgivern/software-lifecycle/.github/workflows/kev-daily.yml --source-ref refs/heads/main

## How it can be wrong

- Build numbers versus cycles: a product whose version is a build number
  may map to the wrong cycle or none. Check the cycle shown in the report.
- Names must match strictly. A name with extra words after the product name
  often lands in "couldn't match". That is safer than a wrong guess.
- SQL Server 2016 and older are unmatched in this version, because
  endoflife.date lists service-pack cycles for them.
- Java 8 names that carry an update number are unmatched.
- KEV matches vendor and product only, never version. A match means "needs
  review", not "your version is affected".
- `windows-server` uses the broad Windows KEV pair, because CISA files
  Windows Server flaws under the product Windows. Every Windows entry
  matches.
- The profiles are Unverified until run on a real export.
- Data is a snapshot and can be out of date.
- The tests ran locally on Python 3.9.25 for the 3.9 floor.

## Maintaining

This repo is on the workspace "Experiment" track. Review date: 2027-01-31,
when the choice is keep maintaining, archive, or fold it back into a kit.
Maintained as time allows, best effort, no SLA, not independently assessed.

- GitHub turns off scheduled workflows in a public repository after
  60 days with no repository activity. Tags and releases may not count as
  activity, so the daily data releases alone may not keep the schedules
  on. If the daily or weekly job stops, turn it back on in the Actions tab
  or push a commit.
- The CI test matrix runs on `ubuntu-24.04`, pinned so the Python 3.9 leg
  keeps working. Python 3.9 is past end of life upstream; drop it from the
  matrix when that runner image stops offering it.
- Before the first data release, create the `data-release` environment
  with main as its only deployment branch (see SECURITY.md).

Run the tests from the repo root:

    python3 -B -m unittest discover -s tests

## Contributing

If a product lands in "couldn't match", open the "Product the tool could not
match" issue form. Give the public product name, the publisher and the
version format. Names only: never paste inventory rows, owner names or
reports into a public issue.

The crosswalk to standards is in `docs/crosswalk.csv`; how to read it is in
[docs/themes.md](docs/themes.md).

## Licence

MIT. See LICENSE. Third-party material: THIRD-PARTY.md.
