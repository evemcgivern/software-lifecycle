# software-lifecycle

An offline, standard-library Python tool that finds software past end of
life in an inventory export. It also adds a CISA KEV needs-review overlay.

Runs locally with no network by default; built to enterprise security
practices; not independently assessed.

## Status

Experiment (workspace track). Review date: 2027-01-31. Maintained as
time allows. Not independently assessed.

## Run the tests

From the repo root:

    python3 -B -m unittest discover -s tests

## Usage

The full usage docs are coming. For now, run
`python3 software_lifecycle.py --help`.

## Data

The bundled data is release `bundled-2026.10.24`: end-of-life dates from
the endoflife.date product files at upstream commit
`7cfb122846893f10ee819ab47b615eff261945d0` (snapshot dated 2026-10-24), and the CISA Known
Exploited Vulnerabilities catalog version 2026.10.23 (released
2026-10-23).

- `data/eol/*.json` derive from endoflife.date product files (MIT).
  Product descriptions are not included. See THIRD-PARTY.md for the
  attribution and licence text.
- `data/kev.json` derives from the CISA Known Exploited Vulnerabilities
  catalog (CC0 1.0), https://www.cisa.gov/known-exploited-vulnerabilities-catalog.

Staleness rules: a KEV snapshot older than 3 days gives a warning, and
older than 7 days the KEV overlay is reported as "not current". An
end-of-life snapshot older than 30 days gives a warning.

The bundled data is a snapshot. The daily refresh publishes newer data
releases. Point `--data` at any directory that holds a verified data
release to use one.

## Real inventories

Run real inventories locally. Do not give the full report to a model to
read.

## Maintaining

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

## Licence

MIT. See LICENSE.
