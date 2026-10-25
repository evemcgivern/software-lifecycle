# Run checklist

One page. The full procedure is in [sop.md](sop.md).

## Before

- [ ] Data is recent: KEV snapshot 3 days old or less; end-of-life snapshot
      30 days old or less (or you accept the warnings).
- [ ] `python3 software_lifecycle.py verify-data` passes.
- [ ] A newer data release, if used, passed `gh attestation verify` online.
- [ ] The inventory export is on the machine that runs the tool.
- [ ] Heading check: the export has name and version columns the tool
      accepts (or you have a `--columns` file).
- [ ] Override files are current: `golden-sources.csv`, `exceptions.csv`,
      `tracking.csv`.
- [ ] Last run's `report.json` is at hand for `--previous`.
- [ ] If an AI agent runs it: `--counts-only`, and the output folder is out
      of its reach.

## During

- [ ] The run exits with code 0 (or 10 if you used `--fail-on`).
- [ ] No unexpected warnings in the report.
- [ ] Past end of life and ends-soon items each have a decision.
- [ ] Review-urgently items are checked by a person against the KEV entries.
- [ ] Dates-disagree items are settled by the ITAM lead.
- [ ] Accepted risk has a risk owner and an independent approver.
- [ ] Couldn't-match items are checked; product names (only) go to an
      unmatched-product issue.

## After

- [ ] Change requests are raised and recorded in `tracking.csv`.
- [ ] Ownerless items have owners.
- [ ] Evidence is stored as Confidential, per your retention choice.
- [ ] `golden-sources.csv` and `exceptions.csv` dates are reviewed.
- [ ] The next review is booked (quarterly; sooner if the KEV overlay
      changes).
