# Changelog

## Unreleased

- Data format 2: the data folder gains `products.json` (a product catalog
  generated from the endoflife.date product files: id, title, category,
  vendor and owner names) and `curation.json` (hand-kept maintainer
  decisions, empty for now). A format 1 folder still loads, with a warning
  that generated matching is off. The weekly job regenerates and
  summarises the catalog; the daily release ships both files. Matching
  behavior is unchanged. See `data/manifest.json` for the bundled release.
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
