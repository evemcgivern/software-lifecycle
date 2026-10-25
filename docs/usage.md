# Usage

There are two commands: `check` and `verify-data`. Run them from the repo
root with `python3 software_lifecycle.py`. Python 3.9 or newer.

## check

    python3 software_lifecycle.py check INVENTORY [flags]

`INVENTORY` is a CSV export with a header row. The layout is in the
[README](../README.md). The KEV overlay is the extra flag that marks items
whose vendor and product appear in CISA's list of known exploited
vulnerabilities. Without `--out` the Markdown report prints to the
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
| `--out DIR` | Folder for the three report files. It must be a folder, not the input file; if it is a file or the input file, the tool exits with code 2. The tool will not write through a symbolic link (exit 3). Keep it outside the repo and outside an agent's reach. | `--out ../swlc-out` |
| `--counts-only` | Print counts and item IDs only. Needs `--out`. | `--counts-only --out ../swlc-out` |
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
| 2 | Usage error: a bad flag, value or combination, including an `--out` that is a file or is the input file. |
| 3 | Bad input: the inventory, an override file, a columns file or the output could not be written (for example, through a symbolic link). |
| 4 | A data check failed. |
| 10 | Findings are present in a list named by `--fail-on`. Only returned with `--fail-on`. |
| 70 | Unexpected error. The tool prints only the error type. |

## How KEV is checked

KEV is checked only for matched items that are past end of life or end
within the window. The check uses the alias table's vendor and product pair
for the matched product. If the alias has no pair, the tool compares the
publisher and the full inventory name (version included) with KEV, exactly.
`kev: false` therefore means "no match under those rules", not "known
safe". The `windows-server` and Windows 10 client aliases use the broad
Microsoft and Windows pair, so every Windows entry in KEV matches them.

## Extending the alias table

The bundled `data/aliases.json` covers few products (see the README). To
add one, edit a copy of the data folder. Do not edit `data/` in place.

1. Copy the folder: `cp -R data ../my-data`.
2. Add an entry to the `aliases` list in `../my-data/aliases.json`. This one
   maps the name "nginx" to the endoflife.date product `nginx`, which
   exists in `data/eol/`:

       {
         "key": "nginx",
         "match": "exact",
         "product": "nginx",
         "version_from": "version",
         "source": "https://nginx.org/"
       }

   `key` is the name as the export shows it (compared after the
   normalizing in [report-schema.md](report-schema.md)). `match` is `exact`
   or `prefix`. `product` is the file name in `data/eol/` without `.json`.
   `version_from` is `version` (read the version column) or `name` (read
   the version from the end of the name). Optional fields: `cycle` (a fixed
   cycle label), `build_map`, `kev` (an object with `vendor` and
   `product`), `note` and `edition_words`. `source` is a link to where you
   confirmed the mapping.
3. Rebuild the manifest. Copy the dates, catalog version and upstream commit
   from `data/manifest.json` into the placeholders:

       python3 refresh_data.py manifest --dir ../my-data --kev-date KEV_DATE --kev-catalog-version KEV_CATALOG_VERSION --eol-date EOL_DATE --upstream-commit UPSTREAM_COMMIT --release-id my-copy-1

4. Check it: `python3 software_lifecycle.py verify-data --data ../my-data`.
5. Run with it: `python3 software_lifecycle.py check INVENTORY --data ../my-data --out ../swlc-out`.

Golden sources do not apply to unmatched items. Add the alias first, and
then a golden source if you need one. If you want the bundled table to
cover a product, open the "Product the tool could not match" issue form
with names only.

## Counts-only mode

    python3 software_lifecycle.py check INVENTORY --counts-only --out ../swlc-out

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
5. Letting an AI read the CSV directly is not a mode of the tool. Do it
   only with synthetic or non-sensitive inventories.

From Python, `swlc.cli.run(...)` returns the same data as `report.json`.
See [report-schema.md](report-schema.md).
