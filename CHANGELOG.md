# Changelog

## Unreleased

- Internet Explorer 11 rows now get the product `internet-explorer` with
  no cycle, date or state, and are listed under "Names to review" with the
  new review code `shared_support_lines` (issue #21). IE 11 follows the
  Windows it runs on, and its builds are shared by desktop, Server, LTSB
  and LTSC editions, so the generic cycle 11 (past end of life on
  2022-06-15 per Microsoft; the catalog lists 2022-06-14) is no longer
  used. A version that names its line (`11-ltsc`, `11-server`) keeps that
  line's cycle. Internet Explorer 9 and 10 are unchanged. A golden-source
  row is not applied to a flagged item (it has no cycle), and the report
  warns when one names such an item's product ("N item(s) have a
  golden-source row that was not applied: no cycle, see Names to
  review."). A `--previous` report of
  an unsupported version now gets a warning that names the version.
  The new hand-kept `curation.json` key `review_versions` lists the
  version prefixes. `report.json` `schema_version` is now 2; `--previous`
  still accepts a version 1 report. A tool from 0.6.0 or earlier refuses
  this `curation.json` with a data error.
- Fixed the crosswalk and themes against the framework text (issue #61).
  PM-5 is no longer cited for end of life. COBIT 2019 cells now name
  practice IDs, all Partial. CIS 2.1, 2.2, 7.1 and 7.2 and the NIST cells
  that were read are no longer hedged; the rest stay Unverified.
  `docs/usage.md` now agrees with the crosswalk on ISO/IEC 19770-1
  clause 8.3. Docs and tests only.
- Updated the crosswalk from the newly checked framework text (issue
  #64). The ISO/IEC 27001, ISO/IEC 19770-1, NIST CSF 2.0 and NIST SP
  800-53 cells are now checked against the standard text and no longer
  listed as Unverified. Dropped 27001 A.5.33, CSF GV.RM-02 and 800-53
  PM-16; added 27001 A.5.2, 19770-1 6.2.4, 8.5 and 10.1 and Annex A
  Retirement, and 800-53 CA-6 and RA-3. `itil4` and `iso20000_1` stay
  Unverified, with the reasons in `docs/themes.md`. Docs and tests only.

## 0.6.0 - 2026-11-01

- Added `swlc_mcp.py`, an optional local MCP server for desktop chat apps
  (part of issue #52). It offers two tools, `preflight` and
  `check_counts`, each taking only the path to a `.csv` file. It returns
  only fixed labels and numbers: no cell text, column titles or item IDs.
  It refuses a path whose file itself is a symlink (a symlinked parent
  folder is followed), folders, non-CSV paths and files over the tool's
  size limit. Each CSV gets its own report folder next to it,
  `swlc-out-<file name>`. `docs/mcp-setup.md` explains how to add it to
  the ChatGPT desktop app and, untested, to Claude Desktop, and what it
  does not protect. The README, usage, quick start, procedure, glossary,
  SECURITY.md and CONTRIBUTING.md point to it. The one-click Claude
  Desktop package is not built yet.
- `preflight` now ends with a second command line for an AI assistant:
  the same `check` command with `--counts-only`, which prints counts only
  (issue #54). `preflight --json` has one new optional key,
  `next_command_counts_only`. `next_command` and `preflight_version` (1)
  are unchanged.
- Added `docs/assistant-setup.md`: which AI assistants can run the tool,
  the privacy rule, and a copy-paste prompt for each kind of assistant. The
  README now opens with a "Start here" chooser. `AGENTS.md` gains rules for
  an agent asked to run the tool on an inventory, and `CLAUDE.md` imports
  it (issue #51).
- Docs and tests now describe the public repository (issue #47).
  SECURITY.md, CONTRIBUTING.md, the README and the quick start no longer
  say the repository is private or that scheduled workflows are paused.
  `docs/maintaining.md` has a go-public day checklist for the owner. The
  hashed banned-term scan now also covers `CHANGELOG.md`,
  `THIRD-PARTY.md`, `examples/` and `swlc/`.
- Refreshed the bundled CISA KEV snapshot (issue #48): catalog 2026.10.23
  to 2026.10.30, 1756 to 1766 entries (10 added, none removed). End-of-life
  data is unchanged.

- Ease-of-use fixes (issue #45). `preflight` now checks the owner column
  (a missing column puts every item on "Ownerless"; blank owner cells are
  named) and the export end-of-life date column (cells not in
  YYYY-MM-DD form, such as day-first dates, are counted, because they put
  items on "Dates disagree"). Its JSON gains `columns.owner`,
  `columns.export_eol` and `unreadable_date_cells`; owner and export_eol
  no longer appear under `other_columns`. Under "Next command" a line
  tells Windows users to type `py` instead of `python3`. An unmatched
  item whose product is known now reads "Product known; version not
  matched." in `report.md` instead of "Product matched by a curated
  alias."; `match_source` in `report.json` is unchanged and
  `schema_version` stays 1. `examples/sample-report.md` carries a note
  under its title that the Hostile Corp rows are planted tests of how the
  tool handles unsafe text; a real run's `report.md` has no such note.
  The demo writes to `../swlc-demo` in every doc.

## 0.5.0 - 2026-10-31

- Docs for report readers (issue #42): `docs/quick-start.md`, one page
  for macOS, Linux and Windows (preflight first, a short output folder,
  what "KEV overlay is not current" means); `docs/glossary.md`, plain
  meanings of the report's words; and `examples/sample-report.md`, the
  demo's real `report.md`, written by `examples/generate.py` and checked
  byte for byte by `tests/test_e2e.py`. `docs/checklist.md` uses the
  report heading "In CISA KEV, past or near end of life" and adds
  preflight and support records. `docs/sop.md` says matching covers only
  the products endoflife.date lists. The report format is unchanged.
- The inventory's `count` column now orders the findings (issue #37).
  Each item gets `install_count`, the sum of its rows' count cells: a
  count from your file, not discovered installs. A cell must be a whole
  number from 0 to 1000000000; comma groups of three (`1,234`) and a
  decimal part of zeros only (`12.0`) are read. Any other cell is ignored
  and counted in
  `counts.count_invalid_cells`. Each list in `report.json`, each section
  of `report.md` and the rows of `report.csv` go largest count first,
  then items with no count, then by item ID. `report.md` shows "Count
  (from your file): N" on items with a count; `report.csv` gains a last
  column "Count (from your file)", after "Support records (from your
  file)"; `--counts-only` prints `count_total N`. Without a count column
  the order and `report.md` are unchanged. A count never changes a
  state, a list's members, a class, an item ID or `--fail-on`.
  `schema_version` stays 1.
- Docs wording before publication (issue #36): the claims line is now
  "Runs locally with no network by default; not independently assessed."
  in the README, SECURITY.md and `report.md`. The BOD 26-04 sentence cites
  its cisa.gov page. The go-public checklist moved to
  `docs/maintaining.md`. The README says who the tool is for and when not
  to use it, and that the `count` column is read but not used to rank or
  filter findings. `docs/sop.md` step 5 makes renewing a support record
  the contract owner's decision, with dates from the contract. The
  ISO/IEC 19770-1 sentence in `docs/usage.md` no longer claims what the
  standard requires and marks its clause Not found / Unverified.

- New `preflight INVENTORY` command (issue #38): reads an export offline
  and says whether it is readable, its row count, which profile fits best
  and how, which name, publisher, version, count and parent columns were
  found, blank and placeholder cell counts, and what to fix, with the
  `check` command to run next. `--json` prints the same result. It prints
  column titles and numbers only, never a cell value, and writes nothing.
- Windows (issue #31): `.gitattributes` checks text files out with LF, so
  the bundled data matches `data/manifest.json` after a Windows clone. The
  informational `test-windows` job passes, with POSIX-only checks skipped.
  A test shows a CRLF inventory gives the same items as an LF one. README
  says Windows is not a supported platform yet.
- New optional `--support-records FILE` (issue #32): a hand-kept CSV of
  the support records you hold (your reference, an endoflife.date product
  ID, an optional cycle or version, a kind and an end date). `report.md`
  shows a line on past and near end-of-life items that have one and a
  "Support records" section; `report.csv` always has a new last column,
  empty without the flag, so "Review reason" is no longer last;
  `report.json` adds the item key `support_records` (always present, empty
  by default) and `counts.support_records`; `--counts-only` prints one
  count line, and `meta.override_hashes` gains the file's hash when the
  flag is used. The file holds at most 2,000 rows and 25 records per
  product. A lifecycle and renewal aid, not a licence or audit
  position. A record never changes a state, a list or `--fail-on`, and
  the tool does not check that it was paid for or is current.
  `schema_version` stays 1.
- `report.md` shows the KEV list under the heading "In CISA KEV, past or
  near end of life" instead of "Review urgently" (issue #29). "Urgently"
  set a priority the tool cannot back: the match is on vendor and
  product, never version. The JSON list key `review_urgently` and the
  `--fail-on` name keep their names; `schema_version` stays 1.
- `report.md` says its counts are inventory rows, not installs: the
  summary line reads "(inventory rows, not installs)" and each item's
  "Rows" label is now "Inventory rows". JSON keys are unchanged. Docs say
  the same in README, `docs/usage.md`, `docs/sop.md` and
  `docs/report-schema.md`.
- CI has an informational Windows test job (`test-windows`, Python 3.12,
  `continue-on-error`). It is not a required check and does not rename
  the five `test` checks.
- Docs say plainly that an item ID is an unsalted, truncated hash of
  publisher, name and version: it keeps names out of counts and findings,
  but a guessed product can be confirmed against it, so IDs need the same
  care as the inventory. README, `docs/usage.md`, `docs/report-schema.md`
  and `SECURITY.md`. A keyed ID option is still open in issue #26.
- Matching looks up only the aliases whose key starts with the name's
  first word, instead of testing every alias on every row (issue #23).
  The lookup is built once per loaded data folder. Results are
  unchanged. Matching 100,000 rows (best of 3) took 3.9 s before and
  1.3 s after on Python 3.15, and 4.6 s and 1.4 s on Python 3.9, with
  155 aliases. With 600 made-up aliases it stays at 1.4 s and 1.5 s.
  The test limit drops from 20 s to 10 s.

## 0.4.0 - 2026-10-30

- Names to review (issue #12): an unmatched row whose name is a one-word
  product title and no publisher, refused because nothing confirms the
  product (`title_needs_publisher`) or because the title is not on the
  version-in-name list (`title_not_on_list`), carries a new item key
  `ambiguity` with the code and a fixed reason. `counts.ambiguous_review`
  counts them. `report.md` lists them in a "Names to review" section,
  `report.csv` adds a trailing "Review reason" column, and
  `--counts-only` prints `ambiguous_review N`. They stay in the unmatched
  list, never feed `--fail-on`, and claim no product, cycle or date.
  Matching results are unchanged; `schema_version` stays 1.
- Microsoft edition names and OS release names (issue #17): 75 new
  aliases in `aliases.json` (94 in all, for 19 products). Windows 11 by
  edition (Home, Pro, Pro Education and Pro for Workstations map to the
  `-w` cycles, Education and Enterprise to the `-e` cycles), Windows 10
  Enterprise LTSB 2015 and 2016 and LTSC 2019 and 2021, Windows 7 and
  8.1, Windows Server 2003 and 2008 R2, SQL Server 2008 R2 service packs
  and "SQL Server <year>", Exchange Server, SharePoint Server, Office
  LTSC 2024, Office 2011 for Mac, Visual Studio 2019 and 2022 editions,
  named .NET runtime, SDK and ASP.NET Core forms, `.NET Framework
  Runtime` names, `Debian GNU/Linux`, Ubuntu Server, macOS release names
  and SUSE Linux Enterprise Server service packs. The two Windows Server
  aliases accept the edition word `evaluation`. Where the name and the
  version column both carry a version or a build the alias's map lists,
  they must agree, or the row gets the product with no cycle; a build
  the map does not list is ignored. Exchange,
  SharePoint, .NET Framework and macOS matches carry the CISA KEV vendor
  and product pair the catalog uses for them. Families with no source
  for the name, or a name that cannot pick a cycle, stay unmatched; see
  "Known limits of matching" in `docs/usage.md`. The data format stays 2
  and `schema_version` stays 1.
- Matching checks each alias entry once instead of on every row; results
  are unchanged. With 94 aliases the old check made matching about four
  times slower.
- The benchmark gains 56 hand rows for these aliases (traps, conflicts
  and a few positives). The hand and catalog floor rises from 482 to
  549 and the classification floor from 294 to 297. Two corpus rows for
  Windows 10 Enterprise LTSC 2019 and 2021 now expect the LTSC cycles.
- Held OS and Microsoft names (issue #20): 61 new aliases (155 in all,
  for 24 products). `PowerShell 7-x64` (PowerShell 7.0 to 7.6 only), Red
  Hat Enterprise Linux 7 Server names, RHEL 8.0 to 8.10 (Ootpa) and 9.0
  to 9.8 (Plow), Rocky Linux 8.4 to 8.10 (Green Obsidian) and 9.0 to 9.7
  (Blue Onyx), `AlmaLinux` and AlmaLinux 8.3 to 10.2 by codename, and
  `Oracle Linux Server`. Each name form has two public sources. A
  release name with a codename matches only as an exact name whose
  number and codename are one pair on the vendor's list, and the version
  column must be that release. All of them need the vendor in the
  publisher; rows with a blank publisher stay unmatched.
- New optional alias field `numbered_words`: a word that must be
  followed by one whole number. The Exchange Server alias uses it, so
  "Microsoft Exchange Server 2019 Cumulative Update 14" matches 2019; the
  update number is not checked against the build. The data format stays
  2 and `schema_version` stays 1.
- Internet Explorer 11 stays as it was (issue #21).
- The benchmark gains 257 hand rows for these names. The hand and
  catalog floor rises from 549 to 751 and the classification floor from
  297 to 299. Matching 100,000 rows (best of 3) took 4.6 s on main and
  6.3 s with 155 aliases on Python 3.15, and 5.2 s and 8.2 s on Python
  3.9; the test limit is 20 s. Each alias is checked against every row,
  so the headroom shrinks as aliases are added.

## 0.3.0 - 2026-10-26

- Matching by product title splits a wider version token off a name:
  digit-led build or distro parts after `.`, `-` or `+`, a few named build
  tags (`hf`, `eks`, `gke`, `I001`, `.v20211001`) and a glued `patchN`
  (`Eclipse Jetty 9.3.30.v20211001`, `Amazon EKS 1.27-eks-53`,
  `Eclipse Temurin 20.0.2+9`). Other words (`8.0-router`) and pre-release
  or milestone suffixes (`2.1-beta`, `-rc1`, `-M1`, `.CR1`, `-ea`) are not
  split.
- Version-in-name rule: a row with no publisher whose name is a coined
  one-word title plus a version (`Kibana 8.15.3`) matches when the version
  decides exactly one cycle. Ordinary words, common names, names another
  product shares (Go, Flux, Salt, Quasar, Rocket.Chat) and titles shared
  with a same-named PyPI, npm or RubyGems client (redis, podman,
  elasticsearch) or VS Code or JetBrains extension (ESLint, MySQL,
  PostgreSQL) are left out; a Kubernetes `-gke.` or `-eks-` build is not
  upstream Kubernetes; a row with a publisher still needs the
  vendor check, and exclusions still win. See "How names are matched" in
  `docs/usage.md`.
- `curation.json` gains publisher names for 31 one-word titles (30 new
  entries and one added phrase), each with a source, and an exclusion that
  keeps Google's Google Go app from matching Go. A `publisher_aliases`
  entry may carry an optional `gold` key naming the benchmark row it
  protects; the data format is unchanged.
- The benchmark gains 83 hand rows for these rules: 70 traps that must
  stay unmatched and 13 positives. Correct rows rise from 1,163 (of 1,798
  rows that should match) to 1,333 (of 1,811): hand and catalog 450 to
  482, generated 713 to 851. Wrong matches: none found on the benchmark;
  unknown in general. The rate on a real estate is unknown.

## 0.2.0 - 2026-10-25

- Item classification: every item gets a `classification` (`governable`,
  `component`, `bundle_member` or `unknown`) with `classification_basis`,
  and parts get `parent_ref`, `inherited_from` and `inherited_lifecycle`.
  `counts` gains `classification`, `unmatched_breakdown` and
  `inherited_attention`. `curation.json` gains `classification_rows`,
  `classification_products` and `bundle_parents`. A part shows its
  parent's date, labelled as the parent's.
- The inventory gains an optional parent column (`Parent`, `Parent
  Software`, `Suite`, `Bundle`). Placeholder cells such as `n/a` count as
  blank.
- `--governable-only` leaves components and bundle members out of
  `report.md` and `report.csv`. `report.json` is unchanged and `unknown`
  items are never hidden. `--fail-on` is unchanged and never reads
  inherited dates.
- Known limits are in `docs/usage.md`, "Known limits".
- The benchmark gains a labelled silver sample of public catalog rows,
  scored per source with the floor `silver_correct_min`. See
  `tests/benchmark/README.md`.

- Data format 2: the data folder gains `products.json` (a product catalog
  generated from the endoflife.date product files: id, title, category,
  vendor and owner names) and `curation.json` (hand-kept maintainer
  decisions: publisher aliases for 42 products, 13 one-word allowlist
  entries, 2 exclusions, 2 products left out of title matching and older
  version numbering for 2 products). A format 1 folder still loads, with a warning
  that generated matching is off. The weekly job regenerates and
  summarises the catalog; the daily release ships both files. See
  `data/manifest.json` for the bundled release.
- Matching by product title: names that equal an endoflife.date product
  title now match, with vendor checks on one-word titles, and
  `curation.json` now holds hand-kept publisher aliases, a one-word
  allowlist, exclusions and a list of products left out. Each item in the
  report gains `match_source`: `curated`, `generated`, or `null` when
  no product is known.
- `report.md` gains a fixed notice line under the summary counts.
- The first run after the upgrade shows a large `diff.changed_state`: rows
  that were unmatched now match.
- Golden-source and exception rows keyed by product id now reach newly
  matched rows. Check them once.
- `kev: false` means "no match under those rules". It does not mean the
  software is known safe.
- Moved into its own repository from the agent-skills kit.
- `check` command: reads an inventory CSV, matches it to bundled
  endoflife.date data, and writes `report.json`, `report.md` and
  `report.csv`.
- KEV needs-review overlay, golden-sources, exceptions and tracking
  override files, `--previous` diff, `--fail-on`, `--counts-only`.
- `verify-data` command and a bundled data release (see `data/manifest.json`).
- Profiles `flexera`, `servicenow-mbs` and `rapid7` (Unverified).
- Demo estate in `examples/`.
- Documentation: README, `docs/usage.md`, `docs/report-schema.md`,
  `docs/sop.md`, `docs/checklist.md`, `docs/platform-guide.md`,
  `docs/themes.md` and `docs/crosswalk.csv`.
- Templates in `templates/`.
- SECURITY.md updated, CONTRIBUTING.md, AGENTS.md and CLAUDE.md added,
  with pull request and issue templates and CODEOWNERS in `.github/`.
- Tests that keep the docs, templates and crosswalk true to the code
  (`tests/test_docs.py`).
