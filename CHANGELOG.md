# Changelog

## Unreleased

- Data format 2: the data folder gains `products.json` (a product catalog
  generated from the endoflife.date product files: id, title, category,
  vendor and owner names) and `curation.json` (hand-kept maintainer
  decisions, empty for now). A format 1 folder still loads, with a warning
  that generated matching is off. The weekly job regenerates and
  summarises the catalog; the daily release ships both files. See
  `data/manifest.json` for the bundled release.
- Matching by product title: names that equal an endoflife.date product
  title now match, with vendor checks on one-word titles, and
  `curation.json` now holds hand-kept publisher aliases, a one-word
  allowlist, exclusions and a list of products left out. Each item in the
  report gains `match_source` (`curated` or `generated`).
- The first run after the upgrade shows a large `diff.changed_state`: rows
  that were unmatched now match.
- Golden-source and exception rows keyed by product id now reach newly
  matched rows. Check them once.
- `kev: false` means "no match under those rules". It does not mean the
  software is known safe.
- The data format is now 2. A format 1 data folder still loads, with a
  warning and generated matching off.
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
