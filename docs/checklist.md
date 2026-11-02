# Run checklist

One page. The full procedure is in [sop.md](sop.md). The words in the
report are in [glossary.md](glossary.md).

## Before

- [ ] Data is recent: KEV snapshot 3 days old or less, end-of-life
      snapshot 30 days old or less (or you accept the warnings).
- [ ] `python3 software_lifecycle.py verify-data` passes.
- [ ] A newer data release, if you use one, passed `gh attestation verify`
      online.
- [ ] The inventory export is on the machine that runs the tool.
- [ ] You ran `python3 software_lifecycle.py preflight inventory.csv` on
      the export, and fixed what it lists under "What to fix".
- [ ] Heading check: the export has name and version columns the tool
      accepts (or you have a `--columns` file).
- [ ] Override files are current: `golden-sources.csv`, `exceptions.csv`,
      `tracking.csv`, `support-records.csv`.
- [ ] Last run's `report.json` is at hand for `--previous`.
- [ ] If an AI agent runs it: `--counts-only`, and the output folder is
      out of its reach.

## During

- [ ] The run exits with code 0 (or 10 if you used `--fail-on`).
- [ ] The report has no unexpected warnings.
- [ ] Each past-end-of-life and ends-soon item has a decision.
- [ ] A person checks each "In CISA KEV, past or near end of life" item
      against the KEV entries.
- [ ] The ITAM lead settles the dates-disagree items.
- [ ] Each accepted risk has a risk owner and an independent approver.
- [ ] You check the couldn't-match items. Only product names go to an
      unmatched-product issue.
- [ ] The contract owner makes a renew-or-end decision on each support
      record that ends within the window. You check records not matched to
      a dated item.

## After

- [ ] Change requests are raised and recorded in `tracking.csv`.
- [ ] Ownerless items have owners.
- [ ] Evidence is stored as Confidential, per your retention choice.
- [ ] You reviewed the dates in `golden-sources.csv` and `exceptions.csv`.
- [ ] The next review is booked (quarterly, or sooner if the KEV overlay
      changes).
