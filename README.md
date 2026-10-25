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
