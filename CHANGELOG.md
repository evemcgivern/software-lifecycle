# Changelog

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
