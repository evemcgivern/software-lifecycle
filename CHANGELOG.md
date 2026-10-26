# Changelog

## Unreleased

- Matching by product title splits a wider version token off a name: a
  build, distro or hotfix suffix after `.`, `-` or `+`, or a glued
  `patchN` (`Eclipse Jetty 9.3.30.v20211001`, `Amazon EKS 1.27-eks-53`,
  `Eclipse Temurin 20.0.2+9`). A pre-release suffix (`2.1-beta`, `-rc1`)
  is still not split.
- Version-in-name rule: a row with no publisher whose name is a coined
  one-word title plus a version (`nginx 1.24.0`) matches when the version
  decides exactly one cycle. Ordinary words, common names and names
  another product shares (Go, Flux, Salt, Quasar, Rocket.Chat) are left
  out, a row with a publisher still needs the vendor check, and
  exclusions still win. See "How names are matched" in `docs/usage.md`.
- `curation.json` gains publisher names for 32 one-word titles (31 new
  entries and one added phrase), each with a source. A `publisher_aliases`
  entry may carry an optional `gold` key naming the benchmark row it
  protects; the data format is unchanged.
- The benchmark gains 44 hand rows for these rules: 31 traps that must
  stay unmatched and 13 positives. Correct rows rise from 1,163 (of 1,798
  rows that should match) to 1,351 (of 1,811): hand and catalog 450 to
  484, generated 713 to 867, with no wrong match. That is the benchmark
  only; the rate on a real estate is unknown.

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
