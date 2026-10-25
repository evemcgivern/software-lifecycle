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
| `--governable-only` | Leave components and bundle members out of `report.md` and `report.csv`. Prints "N items hidden: M components, K bundle members". `report.json` and `--fail-on` are unchanged, and `unknown` items are never hidden. Default off. | `--governable-only --out ../swlc-out` |
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
   publisher, unless it has a `publisher` list: then it applies only when
   the row's publisher holds one of those phrases as whole words (the
   `node.js` alias needs the Node.js Foundation or the OpenJS Foundation,
   the `ubuntu` aliases need Canonical), and otherwise it does not hit at
   all. When an alias reads the version from the name, the name carries no
   version and the column is a calendar version such as `2023.22.1` while
   the product's cycles are not years (the Python extension for VS Code
   against Python 3.x), the row is another product: no match. When an
   alias reads the version from the name and the version column is not
   empty, the column is checked:
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
   tool drops architecture and locale groups such as `(x64 en-US)` or
   `[x64]` (a locale is any ISO language-region pair, such as `es-AR`; a word
   like `go-to` is not one), drops a leading vendor word when the publisher carries that
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
   - When the vendor word is the product's own title (vendor `prometheus`
     for Prometheus), the publisher must be that word alone, apart from
     words such as Inc, Ltd, GmbH, Foundation, Project, Team or The. So
     `Prometheus Group Inc.` does not confirm Prometheus, and `Grafana Labs`
     confirms Grafana only through its curated publisher alias. Known limit: a different
     product from a same-name vendor still confirms unless an exclusion
     stops it (the Moodle app from Moodle Pty Ltd is excluded).
   - Products whose catalog category is `device`, and products on
     `generated_off`, are never matched by title.
   - An exclusion stops one product for a name: it applies when its name
     equals any form of the row's name (whole, without architecture groups,
     without the vendor word, or with the version split off) and, when it
     gives one, its publisher word is in the publisher.
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

## Known limits of matching

These are known and not fixed. The tool leaves the row unmatched or says
so; it does not hide them.

- A curated alias matches by name, whatever the publisher, unless it has a
  `publisher` list. Only some aliases have one (`node.js`, `ubuntu`).
- Two products with the same name from the same vendor cannot be told
  apart. The Moodle mobile app and the Moodle LMS are an example: both are
  left unmatched, by an exclusion.
- A Jenkins weekly build whose number equals a long-term-support baseline
  (for example `2.426`) maps to that baseline's cycle. A weekly build that
  is not a baseline maps to cycle `2`.
- A cycle is left open (`NO_CYCLE`, product known) when a version's extra
  part looks like a build number, for example `.NET Framework` `4.6.01590`.
- Software with no lifecycle policy (git, curl, vim) is not in the data and
  never matches.
- Ansible rows from Red Hat stay unmatched. The catalog vendor is
  `redhat`, one word, and the Red Hat VS Code extension named Ansible
  shares the name and publisher, so no publisher alias adds Red Hat.
- A bare `podman` row with no publisher stays unmatched: the PyPI `podman`
  package (the API bindings) and the Homebrew `podman` formula look the
  same to the matcher. Podman matches when the publisher is Red Hat or the
  Podman project.
- The VS Code extensions for Julia and Deno share vendor words with the
  Julia and Deno products, so an extension row can be read as the product.

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
an object of `phrases`, a sorted list of lowercase vendor phrases, `reason`
and `source`), `single_word_allowlist` (a list of `product`, `reason`,
`source` and `gold`, the gold benchmark row it was checked on, as
`name|publisher|version`), where each `source` is an https URL,
`exclusions` (a list of `product`, `name`, `publisher`, `reason` and `gold`;
`publisher` is one lowercase word, or empty to apply whatever the
publisher)
`generated_off` (a sorted list of product ids) and, optionally,
`no_cycle_versions` (a product id to an object of `prefixes`, a sorted list
of version prefixes such as `21.3`, `reason` and `source`). Three more keys
are optional and set what kind of item a row is: `classification_rows` (a
sorted list of `name`, a normalized name, `publisher`, one lowercase word or
empty, `class`, `reason`, `source` and `gold`), `classification_products` (a
product id to an object of `class`, `reason` and `source`) and
`bundle_parents` (a sorted list of `name_prefix`, lowercase leading words,
`publisher`, one lowercase word that must appear in the publisher, `parent`,
a product id, `reason`, `source` and `gold`). A `class` here is
`governable`, `component` or `unknown`. The tool refuses a file
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

Most products match by their endoflife.date title (see the README). Use
an alias for a name the title does not cover. To add one, edit a copy of
the data folder. Do not edit `data/` in place.

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
   `product`), `note`, `edition_words` and `publisher` (a non-empty list of
   lowercase publisher phrases; the alias then applies only when the row's
   publisher holds one of them as whole words). `source` is a link to where you
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

## Extending the curation file

`curation.json` holds the maintainer's decisions about generated matching.
Edit it in a copy of the data folder, like the alias table, and rebuild the
manifest (steps 3 to 5 above). The tool refuses a file that breaks the
rules in "The data folder".

- A publisher alias adds vendor names for one product, so a one-word or
  short title can be confirmed by the row's publisher. Give `phrases`
  (lowercase), a `reason` and an https `source`.
- A one-word allowlist entry lets a one-word title match with no vendor.
  Give the `product`, a `reason`, a `source` and a `gold` row
  (`name|publisher|version`) that shows it is right.
- An exclusion stops one product for one name, optionally for one
  publisher word. Give the `product`, `name`, `publisher`, `reason` and a
  `gold` row.
- `generated_off` lists products that never match by title.
- `no_cycle_versions` names version prefixes from an older numbering that
  overlaps a product's cycles. GraalVM numbered releases by year until 2023
  (21.3.1), and its cycles are the later JDK-based releases (21.0.2). A
  title match whose version, in the column or in the name, starts with a
  listed prefix gets the product with no cycle. Give the `prefixes`, a
  `reason` and a `source`. Curated aliases are not affected.

For the bundled file, the rules in `CONTRIBUTING.md` also apply: every
entry cites its evidence and the benchmark must not get worse.

## What kind of item this is

An inventory row can be an application someone owns, a piece of something
else, or a member of a bundle. Each row gets one of four classes. These are
policy lines. ISO/IEC 19770-1 requires an inventory and lifecycle control but
does not define "component", "bundle" or "governable". ISO/IEC 19770-2 (SWID)
has parent and child links; its clause references are Unverified until
checked.

- `governable`: a standalone application, server, database, OS, browser,
  security agent or directly used developer tool, plus standalone runtimes
  (JDK, .NET, Node.js, Python).
- `component`: a library, redistributable, driver, language pack, OS patch,
  font, codec, extension, plugin, `lib*` or `-dev` package, with no known
  parent.
- `bundle_member`: a part with a named parent (a suite member, a runtime
  inside an app, a driver pack, an OS patch of the OS item).
- `unknown`: the tool cannot tell. This is a valid answer and the default.
  Never default to governable.

The first confident hit wins, and all the evidence is recorded. The order of
evidence is:

1. a curated row override (a maintainer decision);
2. bundle: an inventory parent column, a curated parent link, or a vendor
   suite pattern whose version fits one cycle of the parent;
3. component: a strong name pattern or a curated entry;
4. governable: the row matches an endoflife.date product whose category is
   app, server, OS, database or similar, and no component or bundle signal
   fired;
5. otherwise `unknown`. Products in the `device` category are `unknown`.

Component outranks governable when both fire. Publisher alone never decides.
Version shape only ever breaks a tie toward `unknown`.

A curated parent links a row only when every word after the curated name is
a year or version word, so "Microsoft Excel 2016" links to Office 2016 but
"Microsoft Excel 2016 Viewer" does not. A row that matches a curated parent,
including a curated OS-patch name, but fits no single cycle is `unknown`
(`suite_no_fit`), not `component`. A last word Runtime or SDK is not a part
signal by itself, because standalone runtimes and SDKs (.NET, Vulkan,
Google Cloud) end that way. Such a name gets its class from the other rules:
a curated row, the matched product's category, or `unknown`. Known parts
named that way, such as the WebView2 Runtime, are curated as components.

### The Parent column

An inventory can name a row's parent in a `Parent` column (also `Parent
Software`, `Suite` or `Bundle`). The column is optional. A blank cell, or a
placeholder cell (`n/a`, `na`, `none`, `null`, `nil`, `unknown`, `tbd`, `-`,
`--`, `n.a.`, `n.a`, `not applicable`, `not available`, `no parent`), counts
as no parent. Cells are compared without regard to case or spacing, so
"SQL Server" and "sql server" are one parent.

- The column beats a `governable` result, including a governable curated row
  override, because a runtime named in a Parent column is not standalone. It
  never beats a curated row override of class `component` or `unknown`.
- A name that matches one other row from the same publisher (when both rows
  have one, they must share a publisher word) links to it (kind `item`). A
  name that matches no row but matches a product links to that product
  (kind `product`). A name that matches two rows, whatever their publishers,
  or a row with two different Parent values, gives no link and the
  class `unknown` (or `component`, when the row's own name says so).
- A name that matches no row and no product gives no link
  (`parent_not_found`). A row that names itself or its own product family
  ("Microsoft Office" on an Office row, "Eclipse Temurin" on a Temurin row;
  `parent_is_self`), or two rows that name each other (`parent_cycle`), keep
  their class and get no link.
- A parent that is itself a part is linked, but no dates are inherited
  (one hop only).
- A parent that is a product and cycle passes its dates on only when exactly
  one inventory row has that product and cycle.
- A Parent cell that names a product with no cycle keeps the cycle a curated
  suite link already found ("Microsoft Excel 2016" stays with Office 2016).
  Without one, a year in the part's name must agree with the parent row's
  cycle; a part never takes another version's dates.

A linked part shows its parent's end-of-life date under the heading
"Parent's date (inherited, not this item's own)". The date is the parent's.
A part never enters `past_eol` or `ends_soon` through it, and `--fail-on`
never reads it. `counts.inherited_attention` counts the parts whose parent
needs attention. When a part's parent is not in the inventory, the report
warns "N parts whose parent is not in this inventory".

`--governable-only` is a view for `report.md` and `report.csv` only.
`report.json` is the same with and without it, the closing findings block
stays complete, and `unknown` items are never hidden.

### Known limits

- A runtime or SDK that ships inside an app, with no Parent column and no
  curated entry, is `unknown` (or `governable` when its product's category
  says so), not `component`.
- A curated OS-patch prefix that fits no cycle of the OS gives `unknown`,
  not a link.
- A one-word daemon named `lib*`, such as libvirt, is treated as a component.
  Other one-word lowercase `lib*` daemons and apps, such as libreswan and
  librespot, are treated as components too.
  A `lib*` name ending in a tool word (`-cli`, `-server`, `-daemon`, `-rest`,
  `-tools`, `-viewer`, `-manager`, `-gui`) is not, and a `*-dev` name counts
  only when a part of it starts with `lib` or it holds a digit.
- The list of Parent placeholders is closed. A cell such as "Not Known" is
  read as a parent name and gives `parent_not_found`.
- The rates on a real estate are unknown. The benchmark measures
  classification on a gold sample, not on any inventory.

## Counts-only mode

    python3 software_lifecycle.py check INVENTORY --counts-only --out ../swlc-out

It prints:

- the checked-on date and whether the KEV data is current;
- the number of items and rows, and the count in each state;
- the count of items in each class (`classification bundle_member=K component=M governable=G unknown=U`);
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
