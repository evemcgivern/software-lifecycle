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

## How names are matched

Each item's name is matched in two steps. `match_source` in the report says
which one found the product.

1. **Curated aliases** (`aliases.json`). An alias that hits the name decides
   the item, even when it then finds no cycle or its strict tail-word rule
   rejects the name. A curated alias matches by name regardless of
   publisher. When an alias reads the version from the name and the version
   column is not empty, the column is checked:
   - an alias without a `build_map`: the name's version and the column must
     pick the same cycle (or, when either picks none, be equal on their
     shared leading parts);
   - an alias with a `build_map` (names that carry a year, such as Windows
     Server 2019): the column is checked only when its leading parts are a
     key of the alias's `column_map` (builds to the cycles they can be, for
     example `10.0.17763` is 2019 or 1809), a key of the `build_map`, or a
     cycle label. Then the year in the name must be one of the cycles the
     column can be. A column that is none of these, such as a Windows
     Server 2012 build, which the `column_map` does not list, is not
     checked.

   If the check fails, the item is not decided (`NO_CYCLE`, product known).
2. **Product titles** (`products.json`), only when no alias hits. The name
   must equal a product's title after normalizing. Before comparing, the
   tool drops architecture and real locale groups such as `(x64 en-US)` or
   `[x64]`, drops a leading vendor word when the publisher carries that
   vendor (`Mozilla Firefox` with publisher Mozilla), and splits a trailing
   version number off the name (`Foo 2.1`). A whole title wins over a split
   one. The version column is used; when it is empty, the version from the
   name is used; when both exist and pick different cycles, the item is not
   decided. A name of more than 64 words is never matched by title.
   - A one-word title matches only when the publisher names the product's
     vendor as whole words, or when the product is on the one-word
     allowlist in `curation.json`. `The Apache Software Foundation`
     confirms the vendor `apache`; `ApacheFriends` does not. A vendor
     written as one word, such as `redhat`, is not confirmed by
     `Red Hat, Inc.`.
   - Products whose catalog category is `device`, and products on
     `generated_off`, are never matched by title.
   - An exclusion stops one product for a name: it applies when its name
     equals the row's whole name or the name without architecture groups
     and, when it gives one, its publisher word is in the publisher.
   - No slugs, fragments or fuzzy scores are used.

When a version has more parts than the chosen cycle and that cycle has finer
cycles in the same product (4.6 has 4.6.1 and 4.6.2), the next part is
checked. If it names one of the finer cycles, that cycle is used. If it
names none and is shaped like a build (not all digits, more than three
digits, or a zero-padded number such as `01`), the item is not decided
(`NO_CYCLE`). So `.NET Framework` with the registry build `4.6.01590` gets
no cycle rather than the wrong one. A plain number of three digits or fewer
with no leading zero is read as a patch of the chosen cycle: Log4j `2.17.1`
is cycle 2 and Jenkins `2.587` is cycle 2. A cycle with no finer cycles is
unchanged (`3.12.1150.0` is Python 3.12).

A name that fits two products, by alias, by title or one of each, is
`AMBIGUOUS` and stays unmatched. A data folder without `products.json`
(format 1) matches by alias only.

## How KEV is checked

KEV is checked only for matched items that are past end of life or end
within the window. The check uses the alias table's vendor and product pair
for the matched product. If the alias has no pair, or the product was
matched by title, the tool compares the
publisher and the full inventory name (version included) with KEV, exactly.
`kev: false` therefore means "no match under those rules", not "known
safe". The `windows-server` and Windows 10 client aliases use the broad
Microsoft and Windows pair, so every Windows entry in KEV matches them.

## The data folder

A data folder holds these files. `data/manifest.json` lists every one with
its SHA-256 and size, and the tool checks them on every load.

| File | Made by | Holds |
|---|---|---|
| `aliases.json` | the maintainer, by hand | Names that map to a product. |
| `profiles.json` | the maintainer, by hand | Pre-filled column alias lists. |
| `curation.json` | the maintainer, by hand | Publisher aliases, a one-word allowlist, exclusions and a list of products left out of generated matching. Each list entry carries a reason or a source URL. |
| `products.json` | `refresh_data.py` | One record per endoflife.date product: `id`, `title`, `category`, `vendors` and `namespaces`. |
| `kev.json` | `refresh_data.py` | The CISA KEV catalog. |
| `eol/*.json` | `refresh_data.py` | Release cycles and end-of-life dates, one file per product. |

Never edit a generated file by hand. The weekly job regenerates
`products.json` and `eol/*.json` from the same endoflife.date commit.

`products.json` reads only these upstream fields: `permalink` (the id),
`title`, `category` and the `identifiers` list. From `identifiers` it keeps
the vendor part of each `cpe` entry (both the `cpe:/a:vendor:product` and
`cpe:2.3:a:vendor:product` forms) as `vendors`, and the owner part of each
`purl` entry as `namespaces`, lower-cased and checked to hold only letters,
digits, `_`, `.` and `-`. Five purl types give a namespace: `github` and
`composer` (the first namespace segment), `npm` (the scope, without the
`@`), `golang` (the owner, and only for modules on github.com) and `maven`
(the whole group id). Every other purl type gives none: `deb`, `rpm`,
`apk`, `alpm`, `docker`, `oci`, `brew`, `scoop`, `chocolatey`, `winget`,
`nuget`, `pypi`, `gem`, `cargo`, `hex`, `generic` and `swid`, because their
namespaces name a distribution, a tap or a repackager, not an owner. Other
identifier kinds are skipped. A value with unexpected characters stops the
refresh. The file holds no descriptions, slugs, alternate URLs, page text
or dates.

`curation.json` has the keys `format`, `publisher_aliases` (a product id to
a sorted list of lowercase vendor phrases), `single_word_allowlist` (a list
of `product`, `reason` and `source`, where `source` is an https URL),
`exclusions` (a list of `product`, `name`, `publisher`, `reason` and `gold`)
and `generated_off` (a sorted list of product ids). The tool refuses a file
with an unknown key, a wrong type, a duplicate or an unsorted list where
sorting is promised.

### Data format

`data_format` in the manifest is 2. A format 2 folder must list both
`products.json` and `curation.json`; the tool loads both or stops with a
data error that names the file. A format 1 folder, which has neither, still
loads as before. The report then carries this warning and the product
catalog is absent: "This data release has no product catalog; generated
matching is off." A tool that does not know a data format stops with "data
format is not supported by this tool" before it looks at any file name. In a
format 2 folder every product in `products.json` must have an `eol/` file
and the other way round, and `curation.json` may name only products in
`products.json`; otherwise the load stops with a data error that names the
file and echoes no value.

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
   cycle label), `build_map`, `column_map` (for an alias that reads the
   version from the name: version-column builds to the cycles they can be,
   used only to check the name), `kev` (an object with `vendor` and
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
