# Demo estate

`software-inventory.csv` is a made-up inventory of 60 rows. Every product, publisher and owner is fictional.
`answer-key.json` lists, by item ID, what the tool should report for each planted case. The other files are sample override files.
`golden-sources.csv`, `exceptions.csv` and `tracking.csv` are the golden-source, risk-exception and change-reference files.
`support-records.csv` is a made-up support-records file; its references are fictional.
The demo runs against the synthetic data in `tests/fixtures/data`, not the live snapshots, so the output never changes with the date.
Run it from the repo root:

    python3 software_lifecycle.py check examples/software-inventory.csv --data tests/fixtures/data --as-of 2026-10-24 --golden examples/golden-sources.csv --exceptions examples/exceptions.csv --tracking examples/tracking.csv --support-records examples/support-records.csv --out /tmp/swlc-demo

To regenerate the inventory, answer key, tracking file and support-records file, run `python3 examples/generate.py`. A fixed seed gives the same bytes every time.
`tests/test_e2e.py` checks the run against the answer key.
