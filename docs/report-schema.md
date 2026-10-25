# Report schema (version 1)

`report.json` is the full result. `report.md` and `report.csv` are views of
it. This page lists every key and code in schema version 1. A test in this
repo fails if a key in a real run is missing from this page.

`report.md` also prints one fixed line, once, under the summary counts:
"Matches rest on name and publisher only. Rows we could not tell apart are
listed as unmatched. Check the source and cycle before relying on any
row." It is not a key and is not in `report.json` or `report.csv`.

The file is UTF-8 JSON with sorted keys. It contains text from your
inventory, so keep it as private as the inventory.

## Top-level keys

| Key | Meaning |
|---|---|
| `schema_version` | The number 1. |
| `as_of` | The date checked, `YYYY-MM-DD`. |
| `lookahead_months` | The window in months (default 12). |
| `data_release` | Which data was used. See below. |
| `kev_current` | `true` if the KEV snapshot is no more than 7 days old (and not dated in the future by more than a day). When `false`, the KEV overlay may be out of date. |
| `warnings` | A list of plain-text warnings, for example a stale snapshot. |
| `items` | One entry per distinct publisher, name and version. See below. |
| `lists` | Item IDs for each list. See below. |
| `counts` | Counts of items, rows, states and lists. |
| `diff` | Changes since the report given with `--previous`. |
| `meta` | The tool version, data hashes, override file hashes, profile and encoding. |

### data_release

| Key | Meaning |
|---|---|
| `id` | The data release ID. |
| `file_hashes` | SHA-256 of each data file. |
| `kev_catalog_version` | The KEV catalog version in the data. |
| `kev_age_days` | Days from the KEV snapshot to `as_of`. Can be negative. |
| `eol_age_days` | Days from the end-of-life snapshot to `as_of`. |

### counts

| Key | Meaning |
|---|---|
| `items` | Number of items. |
| `rows` | Number of inventory rows. |
| `states` | Count of items in each state. |
| `lists` | Count of item IDs in each list. |

### meta

| Key | Meaning |
|---|---|
| `tool_version` | The tool's version. |
| `data_release` | The release ID and `file_hashes`. |
| `override_hashes` | SHA-256 of the `golden`, `exceptions` and `tracking` files; empty text when a file was not given. |
| `profile` | `name`, and `status` (`Unverified` for a profile; `null` for `generic`). |
| `encoding` | The inventory encoding (`utf-8` unless `--encoding` was used). |

### meta.data_release

| Key | Meaning |
|---|---|
| `id` | The data release ID. |
| `file_hashes` | SHA-256 of each data file. |

### meta.override_hashes

| Key | Meaning |
|---|---|
| `golden` | SHA-256 of the golden-sources file; empty text if not given. |
| `exceptions` | SHA-256 of the exceptions file; empty text if not given. |
| `tracking` | SHA-256 of the tracking file; empty text if not given. |

### meta.profile

| Key | Meaning |
|---|---|
| `name` | The profile name; `generic` by default. |
| `status` | `Unverified` for a profile; `null` for `generic`. |

## Items

Rows with the same normalized publisher, name and version make one item.
"Normalized" means lowercased, with extra spaces removed and a few fixed
tokens dropped (`(64-bit)`, `(32-bit)`, `x64`, `x86`, `en-us`).
`id` is 12 hex characters made from those three values, stable across runs.

| Field | Meaning |
|---|---|
| `id` | The stable item ID. |
| `name`, `version`, `publisher` | As in the inventory. |
| `owners` | Sorted list of distinct owners. |
| `rows` | How many inventory rows made this item. |
| `product` | The endoflife.date product. `null` only when no product matched (`NO_ALIAS`, or `AMBIGUOUS` across products). Set when the product is known but no cycle matched (`NO_VERSION`, `NO_CYCLE`, or `AMBIGUOUS` between cycles). |
| `match_source` | How the product was found: `curated` (an alias in `aliases.json`), `generated` (the name equals the product's title in `products.json`, under the rules in `docs/usage.md`), or `null` when `product` is `null`. Set also when the product is known but no cycle matched (the item then stays `unmatched` with `product` set and `cycle` `null`). With a format 1 data folder it is `curated` or `null`. |
| `cycle` | The matched cycle label, or `null`. |
| `state` | One of the states below. |
| `state_endoflife` | The state using only the endoflife.date date. `null` if unmatched. |
| `reason` | A reason code when `state` is `unmatched`; otherwise `null`. |
| `eol_endoflife` | The endoflife.date end-of-life value. |
| `eol_export` | The export's end-of-life date, if it was readable. |
| `eol_export_raw` | The export's end-of-life text as given. |
| `eol_used` | The end-of-life value the tool used. |
| `eol_source` | Where `eol_used` came from: `endoflife.date`, `export` or `manual`. |
| `support` | The mainstream support value from endoflife.date. |
| `extended_support` | The extended support value from endoflife.date. |
| `golden_applied` | `export`, `manual`, `endoflife.date` or `null`: which source a golden-sources row chose. |
| `golden_expired` | `true` if a golden-sources row exists and its `review_by` date has passed. |
| `dates_disagree` | A `dates_disagree` code, or `null`. |
| `accepted_risk` | `true` if an exceptions row matches and has not expired. |
| `exception_expired` | `true` if an exceptions row matches and has expired. |
| `decision_needed` | Sorted list of codes for a person to settle. |
| `kev` | `true` if the vendor and product appear in KEV; `false` if checked and not found; `null` if not checked. |
| `kev_stale` | `true` when KEV was checked (`kev` is not `null`) and the KEV data was not current. |
| `change_ref` | From the tracking file, or `null`. |
| `problem_ref` | From the tracking file, or `null`. |

Date fields (`eol_endoflife`, `eol_export`, `eol_used`, `support`,
`extended_support`) hold `YYYY-MM-DD` text, `null` for none, or `true` or
`false` where endoflife.date gives a flag instead of a date. For
`eol_endoflife` and `eol_used`, `true` means end of life reached with no
date given, and `false` means none announced. For `support` and
`extended_support`, `false` means the support has ended and `true` means
it is ongoing.

KEV is checked only for matched items whose state is `past_eol` or
`ends_soon`. It matches on vendor and product, never on version. The
report prints: The vendor and product appear in CISA KEV. This does not
mean your version is affected. The tool never says "vulnerable".

### States

| State | Meaning |
|---|---|
| `supported` | Not ended and not inside the window. |
| `mainstream_ended` | Mainstream support has ended; end of life has not. |
| `ends_soon` | End of life falls inside the lookahead window. |
| `past_eol` | End of life has passed. |
| `unmatched` | No product and cycle found. No date is claimed. |

### Reason codes (unmatched items)

| Code | Meaning |
|---|---|
| `NO_ALIAS` | No alias entry and no product title fits this name, or the name has extra words after an alias that the strict tail-word rule rejects. |
| `NO_CYCLE` | The product is known, but no cycle matches this version, or the version in the name and the version column disagree (they would pick different cycles), so the row is not decided. `product` and `match_source` are still set; `cycle` is `null`. |
| `NO_VERSION` | No version was given. |
| `AMBIGUOUS` | The name matches more than one product (aliases, product titles, or an alias and a title), or more than one cycle fits this version. |

### dates_disagree codes

| Code | Meaning |
|---|---|
| `DIFFERENT_DATE` | The export date and the endoflife.date date differ. |
| `NO_ENDOFLIFE_DATE` | The export has a date; endoflife.date has none to compare. |
| `EXPORT_DATE_UNREADABLE` | The export date is not an ISO date. |
| `EXPORT_DATES_CONFLICT` | Rows for the item carry different export dates. |
| `GOLDEN_EXPIRED` | The golden source's `review_by` date has passed. |
| `GOLDEN_EXPORT_UNUSABLE` | The golden source says use the export date, but the export has no usable date. |

### decision_needed codes

`decision_needed` can hold these codes. The ITAM lead settles the date
codes. For `EXCEPTION_EXPIRED`, the asset owner requests risk acceptance
again, and the risk owner and an independent approver sign off.

| Code | When |
|---|---|
| `NO_ENDOFLIFE_DATE` | Only when `eol_endoflife` is `null` and the export has a date. When endoflife.date gives a `true` or `false` flag instead, the item shows `NO_ENDOFLIFE_DATE` in `dates_disagree` with no decision code. It can appear in `decision_needed` while `dates_disagree` is `null`, when an active golden source applies. |
| `EXPORT_DATE_UNREADABLE` | When it appears in `dates_disagree` (see that table). |
| `EXPORT_DATES_CONFLICT` | When it appears in `dates_disagree` (see that table), and also when an active golden source applies. |
| `GOLDEN_EXPIRED` | When it appears in `dates_disagree` (see that table). |
| `GOLDEN_EXPORT_UNUSABLE` | When it appears in `dates_disagree` (see that table). |
| `EXCEPTION_EXPIRED` | An exceptions row matches the item and its `expires_on` date has passed. |

`DIFFERENT_DATE` appears in `dates_disagree` but not in `decision_needed`.
The Markdown report still prints a "Decision needed" line for it.

## Lists

`lists` maps each name to a sorted list of item IDs.

| List | Item is on it when |
|---|---|
| `past_eol` | `state` is `past_eol`. |
| `ends_soon` | `state` is `ends_soon`. |
| `dates_disagree` | `dates_disagree` is set. |
| `unmatched` | `state` is `unmatched`. |
| `accepted_risk` | `accepted_risk` is `true`. |
| `ownerless` | `owners` is empty. |
| `review_urgently` | `kev` is `true`. |
| `golden_overrides` | `state_endoflife` differs from `state`. |

## diff

| Key | Meaning |
|---|---|
| `available` | `true` if `--previous` was a usable report of schema version 1. If not, the report adds a warning and the lists below are empty. |
| `new` | Item IDs not in the previous report. |
| `resolved` | Item IDs in the previous report and not in this one. |
| `changed_state` | Entries with `id`, `from` and `to`. |

### diff.changed_state

Each entry in `changed_state` has these keys. The first run after the data
changes from format 1 to format 2 lists many items here: rows that were
`unmatched` now match by product title.

| Key | Meaning |
|---|---|
| `id` | The item ID. |
| `from` | The state in the previous report. |
| `to` | The state in this report. |

## Override file columns (schema_version 1)

All three files are CSV with a header row. The first column is
`schema_version` and every row must hold `1`. Every column listed below
must appear in the header, even the optional ones; a missing one stops the
run with "missing required column(s)". Header names are matched
without regard to case, and extra columns are ignored. Cells are trimmed.
A file with only the header is a valid empty file. A bad value stops the
run with exit code 3 and an error that names the data row number and the
column, never the cell text.

Dates in these files are ISO dates, `YYYY-MM-DD`, and must be real dates.
`review_by` and `expires_on` hold through that day: the item is expired
the day after.

### golden-sources.csv

Says which end-of-life date is right for a product.

| Column | Rule |
|---|---|
| `schema_version` | `1`. |
| `product` | Required. An endoflife.date product ID, or a product name. One row per product. If an item matches both a product-ID row (for example `nodejs`) and a name row (for example `node.js`), the product-ID row is used and the report adds this warning: "N item(s) matched two golden-source rows; the product-id row was used." |
| `source` | Required. `export`, `endoflife.date` or `manual`. |
| `manual_eol` | A date. Required when `source` is `manual`; not allowed otherwise. |
| `reason` | Why. Free text. |
| `set_by` | Who chose it. Free text. |
| `set_on` | Optional date. |
| `review_by` | Optional date. After it, the item returns to `dates_disagree` as `GOLDEN_EXPIRED`. |

### exceptions.csv

Accepted risk. The tool lists it and does not confirm the sign-off.

| Column | Rule |
|---|---|
| `schema_version` | `1`. |
| `product` | Required. A product ID or name. |
| `scope` | Optional. A cycle label or version. Empty means any. One row per product and scope. |
| `compensating_controls` | Free text. The tool does not require it; your process should. |
| `risk_owner` | Required. |
| `approver` | Required. Must differ from `requested_by` (compared without regard to case or spacing), or the file is rejected. |
| `requested_by` | Required. |
| `expires_on` | Required date. |
| `reference` | Required. Your ticket or record reference. |

### tracking.csv

Links a finding to your change and problem records.

| Column | Rule |
|---|---|
| `schema_version` | `1`. |
| `item_id` | Required. The 12-character item ID. Each ID once. |
| `change_ref` | Your change record reference. May be empty. |
| `problem_ref` | Your problem record reference. May be empty. |

## Stability

Within a `schema_version`, keys are never removed or renamed and never
change meaning or type. New keys may be added; consumers must ignore keys
they do not know. Adding a state, a list name, a reason code or a decision
code bumps `schema_version`. The keyword arguments of `swlc.cli.run` follow
the same rule. The tool only reads a `--previous` report of its own schema
version.

## Calling it from Python

`swlc.cli.run` returns the same dictionary that `report.json` holds. Run
from the repo root, or put the repo on `sys.path`.

    from datetime import date
    from swlc.cli import run

    report = run("inventory.csv", as_of=date(2026, 10, 24))
    print(report["lists"]["past_eol"])

Options are keyword arguments: `as_of` (required), `data`,
`lookahead_months`, `profile`, `columns`, `golden`, `exceptions`,
`tracking`, `previous` and `encoding`. They match the command-line flags.
It raises:

- `InputError` (in `swlc.errors`) when the inventory, a columns file, an
  override file or the `previous` report cannot be read or is not valid,
  and when `lookahead_months` is not a whole number from 0 to 600. The
  command line exits with 3.
- `DataError` (in `swlc.errors`) when a data check fails, or when two
  different items share one ID. The command line exits with 4.
- `UsageError` (in `swlc.cli`) for an unknown `profile` or a date out of
  range. The command line exits with 2.
- `TypeError` if `as_of` is a `datetime` instead of a `date`. Pass a
  `date`.
