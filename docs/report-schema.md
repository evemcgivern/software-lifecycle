# Report schema (version 1)

`report.json` is the full result. `report.md` and `report.csv` are views of
it. This page lists every key and code in schema version 1. A test in this
repo fails if a key in a real run is missing from this page.

`report.md` also prints one fixed line, once, under the summary counts:
"Matches rest on name and publisher only. Rows we could not tell apart are
listed as unmatched. Check the source and cycle before relying on any
row." It is not a key and is not in `report.json` or `report.csv`.

`report.md` also has a "Names to review" section and `report.csv` a
"Review reason" column, both made from the item key `ambiguity`
(see below).

With `--support-records`, `report.md` adds a support-record line to items
in "Past end of life" and "Ends within the lookahead window" and a
"Support records" section, and `report.csv` a last column "Support
records (from your file)", made from the item key `support_records` (see
below). `--counts-only` prints `support_records listed=N ending_soon=M
not_matched=K`. report.md and report.csv show at most 10 records per item,
then "and N more in report.json"; `report.json` keeps them all. The tool does not check that a record was paid for or
is current. Record references are confidential, like item IDs.

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
| `rows` | Number of inventory rows. This is rows in the export, not installs or machines. |
| `states` | Count of items in each state. |
| `lists` | Count of item IDs in each list. |
| `classification` | Count of items in each class. See `counts.classification`. |
| `unmatched_breakdown` | The unmatched total split three ways. See `counts.unmatched_breakdown`. |
| `ambiguous_review` | Number of items whose `ambiguity` is not `null`: unmatched rows the matcher refused on purpose, for a person to review. They stay in `lists.unmatched` and in `unmatched_breakdown`; a count only, not a list. See `ambiguity` below. |
| `support_records` | Counts from the support-records file. See `counts.support_records`. Zeros when no file is given. A count only: a record never changes a state, a list or `--fail-on`. |
| `inherited_attention` | Number of parts whose parent is `past_eol`, `ends_soon` or `mainstream_ended` (the `state` in `inherited_lifecycle`). A count only: a part never enters `past_eol` or `ends_soon` through its parent, and `--fail-on` never reads inherited dates. |

### counts.classification

| Key | Meaning |
|---|---|
| `governable` | Items classed `governable`. |
| `component` | Items classed `component`. |
| `bundle_member` | Items classed `bundle_member`. A part's parent is counted once, under its own class (normally `governable`). |
| `unknown` | Items classed `unknown`. |

The four numbers add up to `counts.items`.

### counts.unmatched_breakdown

| Key | Meaning |
|---|---|
| `needs_review` | Unmatched items whose class is `unknown` or `governable`. |
| `parts_with_parent` | Unmatched `bundle_member` items with `inherited_from` set. |
| `parts_parent_absent` | Every other unmatched part: a `component`, or a `bundle_member` whose parent is not in this inventory. |

The three numbers add up to `counts.lists.unmatched`. `lists.unmatched` itself
is unchanged. `report.md` leads its "Couldn't match" section with the
`needs_review` number and lists the other unmatched items in "Parts that could
not be matched". The warning "N parts whose parent is not in this inventory"
(`parent_absent` in `classification_basis`) appears in `warnings`.

### counts.support_records

| Key | Meaning |
|---|---|
| `listed` | Records that fit at least one dated item (an item with a `product` and `cycle`) in this inventory. |
| `ending_soon` | Records whose `ends_on` is after `as_of` and on or before the end of the lookahead window, whether or not they fit an item. A date on or before `as_of` has ended, the same rule as an item's state. |
| `not_matched` | Records that fit no dated item: not matched to a dated item in this inventory. This includes a product that appears in the inventory without a decided cycle or version (an unmatched row). `listed` and `not_matched` add up to the records in the file. |

The counts overlap: `ending_soon` counts records from both `listed` and
`not_matched`, so one record can be in `ending_soon` and in one of the
other two.

### meta

| Key | Meaning |
|---|---|
| `tool_version` | The tool's version. |
| `data_release` | The release ID and `file_hashes`. |
| `override_hashes` | SHA-256 of the `golden`, `exceptions` and `tracking` files; empty text when a file was not given. With `--support-records`, also `support_records`. |
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
| `support_records` | SHA-256 of the support-records file. Present only when `--support-records` is given, so a report made without it is unchanged. |

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
It is an unsalted hash: a guessed publisher, name and version can be
confirmed against it, so treat IDs with the same care as the inventory.

| Field | Meaning |
|---|---|
| `id` | The stable item ID. |
| `name`, `version`, `publisher` | As in the inventory. |
| `owners` | Sorted list of distinct owners. |
| `rows` | How many inventory rows made this item. This is not an install or machine count. |
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
| `classification` | What kind of item this is: `governable`, `component`, `bundle_member` or `unknown`. See "What kind of item this is" in `docs/usage.md`. |
| `classification_basis` | List of the signal codes that fired, in rule order. See the `classification_basis` codes below. |
| `parent_ref` | The named parent of a `bundle_member`, or `null`. See `parent_ref` below. |
| `inherited_from` | The parent item's ID when the parent is in the same inventory; otherwise `null`. |
| `inherited_lifecycle` | The parent's dates, shown against a part and labelled as the parent's, or `null`. See `inherited_lifecycle` below. The item's own date fields never change. |
| `support_records` | Always present: a list, empty by default, of the support records from `--support-records` that fit this item, sorted by `ends_on` then `record_ref`. See `support_records` below. Only matched items (with a `cycle`) get records. It changes no other key. |
| `ambiguity` | `null`, or an object with `code` and `reason` when the matcher refused this unmatched row on purpose: the name looks like a catalog product, but there is not enough evidence. See `ambiguity` below. Never set on a matched item or on a part (`component` or `bundle_member`). |

### parent_ref

| Key | Meaning |
|---|---|
| `kind` | `item` (another row named in the inventory's Parent column), `os` (the one OS item an OS part fits) or `product` (a product and cycle, from the Parent column or a curated parent). |
| `value` | The parent item's ID for `item` and `os`; `<product>/<cycle>` (or `<product>` when no cycle is known) for `product`. |
| `basis` | The signal code that named it: `parent_column`, `os_parent` or `curated_parent`. |

A `product` parent passes its dates only when exactly one item in the
inventory has that product and cycle. Otherwise the parent counts as not
in the inventory: `inherited_from` is `null`, the basis lists
`parent_absent`, and the report warns "N parts whose parent is not in this
inventory".

### inherited_lifecycle

Present when `inherited_from` names a parent that has a cycle. One hop
only: a part whose parent is itself a part gets none.

| Key | Meaning |
|---|---|
| `parent_id` | The parent item's ID. |
| `product` | The parent's product ID. |
| `cycle` | The parent's cycle. |
| `eol` | The parent's `eol_used`. |
| `support` | The parent's `support`. |
| `extended_support` | The parent's `extended_support`. |
| `state` | The parent's `state`, in the item state words. |
| `label` | Always "inherited from parent". |

### support_records

A record fits an item when the item has a `cycle`, its `product` is the
record's `product`, and the record's `scope` is empty or equal to the
item's `cycle` or `version` (compared without regard to case or spacing).
A record never changes `state`, never puts an item on a list, and
`--fail-on` never reads it. Record references are confidential.

| Key | Meaning |
|---|---|
| `record_ref` | Your reference, as in the file. |
| `kind` | The kind, as in the file, for example `extended support`. |
| `scope` | The scope from the file, or `null` for any cycle of the product. |
| `ends_on` | The record's end date, `YYYY-MM-DD`. |
| `owner_role` | The role from the file, or `null`. |

### ambiguity

Set only on an unmatched item with no product, whose class is `unknown`
or `governable`. It changes nothing else: the item keeps `state`
`unmatched`, its `reason` (`NO_ALIAS`), `product` `null` and no date. It
never puts the item on another list, and `--fail-on` never reads it.
Unmatched on purpose, not a finding. To settle one, a person adds a
publisher that names the vendor, asks the maintainer for a curated alias,
or records that it is a different product; the tool never promotes such
a row to a match.

| Key | Meaning |
|---|---|
| `code` | One of the `ambiguity` codes below. |
| `reason` | A fixed one-line English text for the code. It holds no text from the inventory. |

### ambiguity codes

| Code | When |
|---|---|
| `title_needs_publisher` | The cleaned name is exactly a one-word product title, the publisher is empty, and the match was refused only because no publisher confirms the product. When the version column is not empty, it must decide one cycle of that product; an empty version keeps the code. Reason: "The name is a product title, but the row has no publisher to confirm the product." |
| `title_not_on_list` | The name is a one-word product title followed by a version, the publisher is empty, the version would decide one cycle, and the product is not on the reviewed list for rows with no publisher (the version-in-name rule in "How names are matched", `docs/usage.md`). Reason: "The name is a product title and a version, but that title is not on the reviewed list for rows with no publisher." |

No code is set for a row with a publisher (a publisher that does not
confirm the product is often a different product, such as an editor
extension or a mobile app), a row refused by a curated exclusion (or for
any product an exclusion names), a device or `generated_off` product, a
version that is given but decides no single cycle, a name that hits no product title, or
a row a curated alias decided. A row gets at most one code: the
title check runs before the version split, so if both could apply,
`title_needs_publisher` is used.

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

### classification_basis codes

The first confident signal decides `classification`; every signal that fired
is listed. Publisher only confirms a curated entry and never decides a class.

| Code | When |
|---|---|
| `row_override` | A curated `classification_rows` entry names this row (a maintainer decision). |
| `curated_parent` | A curated `bundle_parents` entry names the parent, and the name's year or version (else the version column) fits exactly one cycle of it. |
| `suite_no_fit` | A curated `bundle_parents` entry matched, but the version fits no cycle or more than one; the item is `unknown`. |
| `name_part` | The name ends like a part: Redistributable, Visual C++ 20xx, font, codec, extension, plugin or add-in, or a one-word lowercase `lib*` library (not one ending in a tool word such as `-cli`), a `*-dev` package with a `lib` part or a digit, or a font package. |
| `name_os_part` | The name looks like an OS part: a KB number, a leading "Update for" or "Security Update for", Hotfix, Language Pack, or Driver after another word. |
| `product_override` | A curated `classification_products` entry sets the class for the matched product. |
| `category_governable` | The matched product's category is `server-app`, `app`, `os`, `database`, `lang` or `service`. |
| `standalone_by_default` | The product is a standalone runtime (category `lang`, or curated as governable). A last word Runtime or SDK is never a part signal on its own. |
| `device_category` | The matched product is a device; the item is `unknown`. |
| `category_unknown` | The matched product's category is `framework` or `standard`; the item is `unknown`. |
| `no_signal` | No product matched and no other signal fired; the item is `unknown`. |
| `version_shape` | The item would be governable, but it has no version in the column or the name; the item is `unknown`. |
| `parent_column` | The inventory's Parent column names the parent: one other row with the same normalized name (and, when both rows have a publisher, a publisher word in common), or else a product. A blank cell, or a placeholder such as N/A, None, null, unknown, TBD, -, Not Applicable, Not Available or No Parent (any case), is no parent signal. The item is a `bundle_member`. It overrides `governable`, also from a curated row, but never a curated row of class `component` or `unknown`. |
| `os_parent` | An OS part (see `name_os_part`) names an OS in its own name (the OS title, or the title without its vendor word) and fits exactly one OS item in the inventory, by publisher and, when the name carries a version, by cycle. Another row that looks like the same OS (an OS item, or an unmatched row whose name holds the title, from a publisher the OS confirms) counts as a second fit. The item is a `bundle_member`. With none or two or more fits, no link and the class is unchanged. |
| `parent_ambiguous` | The Parent column holds two different values for the item, or its value names two or more rows. No link; the item is `unknown`, or stays `component` when its own name says so. |
| `parent_not_found` | The Parent column value names no row and no product. No link; the item is `unknown`, or stays `component` when its own name says so. |
| `parent_is_self` | The Parent column names the row itself (its own name, or its name without a trailing version), or names the row's own product ("Microsoft Office" on an Office row). No link; the class is unchanged. |
| `parent_cycle` | Two rows name each other in the Parent column. No link for either; the classes are unchanged. |
| `parent_is_part` | The named parent is itself a `component` or `bundle_member`. The link and `inherited_from` stay; `inherited_lifecycle` is `null` (one hop only). |
| `parent_absent` | The parent is a product, and not exactly one item in the inventory has that product and cycle. No dates are shown. |
| `parent_no_date` | The parent item is unmatched or has no cycle. The link stays; `inherited_lifecycle` is `null` (the parent has no date). |

## Lists

`lists` maps each name to a sorted list of item IDs.

The list `review_urgently` keeps its old name for stability: renaming a key
would change the schema. `report.md` shows it under the heading "In CISA KEV,
past or near end of life".

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

All four files are CSV with a header row. The first column is
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

### support-records.csv

Support records you hold, shown beside the vendor's dates. A lifecycle
and renewal aid, not a licence or audit position. There is no quantity,
licence metric, cost or vendor column.

| Column | Rule |
|---|---|
| `schema_version` | `1`. |
| `record_ref` | Required. Your own reference (contract, purchase order or ticket), up to 64 characters. Each one once (compared without regard to case or spacing). |
| `product` | Required. An endoflife.date product ID in the loaded data, exactly. Product names are not matched; an unknown ID stops the run. |
| `scope` | Optional. A cycle label or version, up to 64 characters. Empty means any cycle of the product. |
| `kind` | Required. A short label, up to 40 characters, for example `extended support`. |
| `ends_on` | Required date. |
| `owner_role` | Optional. A role, not a person, up to 80 characters. |

At most 2,000 data rows and at most 25 records per product; a larger file
stops the run with an error that names the row and the limit. When a data
refresh renames or removes a product ID, a file that still names the old
ID stops the run (exit code 3, naming the data row): change the row to
the new ID or delete it.

## Stability

Within a `schema_version`, keys are never removed or renamed and never
change meaning or type. New keys may be added; consumers must ignore keys
they do not know. Adding a state, a list name, a reason code or a decision
code bumps `schema_version`. The item key `ambiguity` and
`counts.ambiguous_review` were added within schema version 1 as new keys;
they add no state, list, reason code or decision code. The item key
`support_records`, `counts.support_records`,
`meta.override_hashes.support_records` (only with the flag) and the
`support_records` keyword of `swlc.cli.run` were added the same way: optional keys only, no
new state, list, reason code or decision code. A report with them and a
report without them read each other with `--previous`. The `ambiguity`
codes follow the reason-code rule: adding one bumps `schema_version`.
The keyword arguments of `swlc.cli.run` follow
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
`tracking`, `support_records`, `previous` and `encoding`. They match the command-line flags.
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
