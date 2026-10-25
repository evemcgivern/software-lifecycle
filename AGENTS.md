# AGENTS.md

This repo is `software-lifecycle`: an offline, standard-library Python tool
that finds software past or near end of life in an inventory export. It
adds a CISA KEV "needs review" flag. Experiment status, maintained as time
allows.

## Commands

No install step. Run from the repo root.

- Tests: `python3 -B -m unittest discover -s tests`
- One module: `python3 -B -m unittest discover -s tests -p 'test_x.py'`
  (do not use `tests.test_x` or `-t`).
- Demo: `python3 software_lifecycle.py check examples/software-inventory.csv --data tests/fixtures/data --as-of 2026-10-24 --golden examples/golden-sources.csv --exceptions examples/exceptions.csv --tracking examples/tracking.csv --out /tmp/swlc-demo`
- Verify data: `python3 software_lifecycle.py verify-data`
- On any real inventory: add `--counts-only --out DIR` and never read the
  report files.

## Layout

- `software_lifecycle.py`: entry point.
- `swlc/cli.py`: flags, exit codes, `run()`.
- `swlc/inputs.py`: CSV reading, column aliases, item IDs.
- `swlc/matching.py`: names to product and cycle.
- `swlc/normalize.py`: name and version cleanup.
- `swlc/assess.py`: states, lists, codes, the report dict.
- `swlc/overrides.py`: golden-sources, exceptions, tracking loaders.
- `swlc/data.py`: loads and checks bundled data.
- `swlc/report.py`: JSON, Markdown and CSV output.
- `swlc/safeio.py`: safe file writing.
- `swlc/errors.py`: error types.
- `refresh_data.py`: the only networked file. Builds data releases.
- `data/`: generated data, except `aliases.json` and `profiles.json`,
  which are hand-kept by the maintainer.
- `examples/`: the synthetic demo estate.
- `docs/`: usage, report schema, procedure, checklist, platform guide,
  themes, crosswalk.
- `templates/`: blank input and override files.
- `tests/`: the suite. `tests/fixtures/` is generated.
- `.github/workflows/`: `ci.yml`, `kev-daily.yml`, `eol-weekly.yml`.

## Hard rules

- Never put real inventory data into prompts, repo files, issues or
  commits. Use synthetic data only.
- `data/aliases.json` and `data/profiles.json` are maintainer-owned,
  hand-kept files. Profiles are pre-filled column alias lists, unverified
  against real exports. Edits need a source URL and tests. Each alias needs
  a source URL, a positive corpus row and a negative corpus row. Edition
  words come only from the vendor's own edition list. See "Ground rules" in
  `CONTRIBUTING.md`.
- Never hand-edit any other generated file in `data/`, `tests/fixtures/data` or
  `tests/fixtures/expected-report.json`. Regenerate the first with
  `tests/make_fixtures.py` and the second with `UPDATE_GOLDEN=1` (see
  `tests/test_e2e.py`).
- Never add dependencies. Standard library only, Python 3.9 floor.
- Never add network use under `swlc/`.
- Never write the word "vulnerable" except in sentences that say the tool
  never says it. Never call a release "signed".
- Keep the claims line and the KEV line exact.
- Workflows: pin every `uses:` to a full commit SHA, put no `${{ }}`
  inside `run:` blocks, use least-privilege `permissions`, and never use
  `pull_request_target`.
- Schema promise: within a `schema_version`, keys are never removed,
  renamed or changed in meaning. Adding a state, list, reason code or
  decision code bumps `schema_version`. See `docs/report-schema.md`.

## Git rules

- Branch name `type/NNNN-name`, where NNNN is the issue number.
- One concern per commit. Subject `type(scope): summary`, lowercase, 50
  characters or fewer.
- Never push to main. Open a pull request.
- Never force-push, never rewrite shared history, never skip hooks.
- If a hook, a test, a guard or branch protection blocks you, stop and ask
  in the issue. Do not work around it.

## Tests that guard the docs and the weekly job

- `tests/test_docs.py` checks docs against the code: flag tables, report
  keys, templates, links, fixed wording, banned terms.
- `tests/test_weekly_gate.py` copies the tree, applies the weekly job's
  manifest step with later dates, and runs the whole suite. A test that
  depends on the bundled data's dates fails it. Use fixture data or the
  manifest's own dates.

## Decisions that belong to the maintainer

Ask before changing: the wording of claims, the report schema, data
sources, the review date, or the experiment status.

## Design intent

Read `docs/usage.md`, `docs/report-schema.md` and `docs/sop.md`. When
unsure, ask in the issue.
