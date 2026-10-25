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

## Licence

MIT. See LICENSE.
