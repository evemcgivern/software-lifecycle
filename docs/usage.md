# Usage

There are two commands: `check` and `verify-data`. Run them from the repo
root with `python3 software_lifecycle.py`. Python 3.9 or newer.

## check

    python3 software_lifecycle.py check INVENTORY [flags]

`INVENTORY` is a CSV export with a header row. The layout is in the
[README](../README.md). Without `--out` the Markdown report prints to the
screen. With `--out DIR` the tool writes `report.json`, `report.md` and
`report.csv` into `DIR` and prints one line naming them.

| Flag | What it does | Example |
|---|---|---|
| `--data DIR` | Use this data directory instead of the bundled `data/`. | `--data tests/fixtures/data` |
| `--as-of YYYY-MM-DD` | Check as of this date. Default is today. This is the only place the tool reads the clock. | `--as-of 2026-10-24` |
| `--lookahead-months N` | Months ahead to count as "ends within the lookahead window". Default 12. From 0 to 600. | `--lookahead-months 6` |
| `--profile NAME` | Add a profile's extra column headings: `flexera`, `servicenow-mbs` or `rapid7`. Default `generic`. All three are Unverified. | `--profile rapid7` |
| `--columns FILE` | JSON file that adds column headings. See `templates/columns.example.json`. | `--columns my-columns.json` |
| `--golden FILE` | Golden-sources CSV. | `--golden golden-sources.csv` |
| `--exceptions FILE` | Exceptions CSV (accepted risk). | `--exceptions exceptions.csv` |
| `--tracking FILE` | Tracking CSV (change and problem references). | `--tracking tracking.csv` |
| `--previous REPORT.json` | An earlier `report.json`. The new report then shows what is new, gone or changed. | `--previous last-quarter/report.json` |
| `--out DIR` | Folder for the three report files. It must be a folder, not the input file. The tool will not write through a symbolic link. | `--out out` |
| `--counts-only` | Print counts and item IDs only. Needs `--out`. | `--counts-only --out out` |
| `--fail-on LIST` | Exit with code 10 if any named list has items. Names: `past_eol`, `ends_soon`, `review_urgently`, `dates_disagree`, `unmatched`. Comma separated. | `--fail-on past_eol,review_urgently` |
| `--encoding NAME` | Text encoding of the inventory if it is not UTF-8. | `--encoding cp1252` |
| `-h`, `--help` | Show help. | `--help` |

The override files (`--golden`, `--exceptions`, `--tracking`) are optional.
A file with only its header row is a valid empty file. Their columns are in
[report-schema.md](report-schema.md).

Full example, the demo:

    python3 software_lifecycle.py check examples/software-inventory.csv --data tests/fixtures/data --as-of 2026-10-24 --golden examples/golden-sources.csv --exceptions examples/exceptions.csv --tracking examples/tracking.csv --out /tmp/swlc-demo

## verify-data

    python3 software_lifecycle.py verify-data [--data DIR]

Checks the data directory against its SHA-256 manifest and checks the
file formats. It does not check dates for staleness. It does not verify
attestations; the tool never does that offline. Use `gh attestation
verify` online (see the README).

    python3 software_lifecycle.py verify-data
    python3 software_lifecycle.py verify-data --data tests/fixtures/data

On success it prints "Data check passed" with the release and file count.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | The tool ran. |
| 2 | Usage error: a bad flag, value or combination. |
| 3 | Bad input: the inventory, an override file, a columns file or the output location could not be used. |
| 4 | A data check failed. |
| 10 | Findings are present in a list named by `--fail-on`. Only returned with `--fail-on`. |
| 70 | Unexpected error. The tool prints only the error type. |

## Counts-only mode

    python3 software_lifecycle.py check INVENTORY --counts-only --out out

It prints:

- the checked-on date and whether the KEV data is current;
- the number of items and rows, and the count in each state;
- each list with its count and the item IDs.

It prints no names, versions, publishers or owners. In this mode an error
message also leaves out file content; it says to rerun locally without
`--counts-only`.

An item ID is a 12-character code made from the publisher, name and
version. It is the same on every run for the same item.

## Running it with an AI agent safely

Real inventories are Confidential.

1. Run the tool yourself, or let an agent run it with `--counts-only`.
2. Send the agent the item IDs and counts. Look up the names yourself in
   `report.md` or `report.csv`.
3. Be plain about the limit: `--counts-only` still writes the full report
   to `--out`. Nothing technical stops an agent from reading that folder.
   Write the output outside the agent's working folder, and tell the agent
   not to open it.
4. No model should read the full report.
5. Chat mode, where a model reads the CSV itself, is for synthetic or
   non-sensitive inventories only.

From Python, `swlc.cli.run(...)` returns the same data as `report.json`.
See [report-schema.md](report-schema.md).
