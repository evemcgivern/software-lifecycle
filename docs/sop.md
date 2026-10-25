# Standard operating procedure: quarterly software lifecycle review

Purpose: find software past or near end of life, decide what to do about
each item, and keep a record of the decisions.

## Roles

The tool names roles. It never assigns people. Your organization decides
who holds each role.

- **Asset owner**: requests risk acceptance for an item.
- **Risk owner**: signs off on accepted risk.
- **Independent approver**: signs off too, and is not the person who
  requested the acceptance.
- **ITAM lead**: settles every "dates disagree" item.

## Cadence

- Review the whole run every quarter.
- Review the KEV overlay whenever it changes (a new data release).
- Evidence retention is your choice. The tool keeps no run history by
  default. Decide below what you keep and for how long.

## Steps

1. **Get the data.** Check the bundled data's age: the report header lists the data release and the snapshot dates. If the report warns that
   the KEV snapshot is older than 3 days or the end-of-life snapshot is
   older than 30 days, fetch a newer data release and verify it online with
   `gh attestation verify` (command in the [README](../README.md)). Then
   run `python3 software_lifecycle.py verify-data --data DIR`.
2. **Export the inventory.** Use [platform-guide.md](platform-guide.md) or
   your own source. Real inventories are Confidential: keep them on the
   machine that runs the tool.
3. **Run the check locally.** Pass your override files and last quarter's
   report:

       python3 software_lifecycle.py check inventory.csv --golden golden-sources.csv --exceptions exceptions.csv --tracking tracking.csv --previous last-quarter/report.json --out ../swlc-this-quarter

   If an AI agent runs it, use `--counts-only` and keep the output folder
   out of the agent's reach. No model should read the full report.
4. **Read the "Changes since the previous report" section** to see what is
   new, gone or changed.
5. **Work "Past end of life" and "Ends within the lookahead window".** For
   each item, the owner chooses: replace, upgrade, retire, or request risk
   acceptance (step 8).
   **Decision needed:** the owner's choice for each item.
6. **Work "Review urgently".** These items are past or near end of life and
   their vendor and product appear in CISA KEV. This does not mean your
   version is affected. A person checks the version against the KEV entries
   and decides the priority.
   **Decision needed:** whether each item is affected, and its priority.
7. **Settle "Dates disagree".** The ITAM lead picks the right date for each
   item. If it will keep recurring, record the choice as a row in
   `golden-sources.csv` with a `review_by` date.
   **Decision needed:** the ITAM lead's choice of date and review-by date.
8. **Handle accepted risk.** The asset owner requests risk acceptance. The
   risk owner and an independent approver sign off. Record it in
   `exceptions.csv` with compensating controls, an expiry date and your
   record reference. The tool rejects a file where the approver and the
   requester are the same person. It does not confirm that anyone gave
   approval.
   **Decision needed:** the risk owner's and approver's sign-off. Renew or
   end any item flagged `EXCEPTION_EXPIRED`.
9. **Handle "Couldn't match".** Check whether the name is a real product.
   If it is, open an unmatched-product issue in the project's issue tracker
   with the public product name, publisher and version format only. Never
   put inventory rows, owner names or report text in a public issue. Until
   it is matched, track the item by hand.
10. **Assign owners to the "Ownerless" items.**
11. **Raise change requests.** For each finding that needs action, open a
    change request in your own system. Add a row to `tracking.csv`: the
    item ID, the change reference and, if there is one, the problem
    reference. The next run shows those references beside the item.
12. **Keep evidence.** Decide what to keep. A usual set:
    `report.json` (it holds the data release ID, file hashes and override
    file hashes), the three override files, and the sign-off records from
    step 8. The reports contain inventory text, so store them as
    Confidential. Keep the `report.json` for the next run's `--previous`.
13. **Review the overrides.** Check each `review_by` and `expires_on` date
    coming up. The tool lists expired ones.

## Questions a governance council will ask

**Who proves the tool makes no network calls?** The tests in this repo.
`tests/test_no_network.py` runs the tool with network calls blocked
(`test_check_runs_with_network_calls_blocked`) and checks that no module
imports a network library (`test_no_swlc_module_imports_a_network_library`).
This is the project's own test. It is not an independent assessment, and
the tool has not been independently assessed.

**What are the data terms?** The end-of-life data derives from the
endoflife.date repository (MIT, with attribution). The KEV data derives
from the CISA catalog (CC0 1.0). See THIRD-PARTY.md.

**Who owns the alias table and the golden sources?** Your team owns
`golden-sources.csv` and `exceptions.csv`. The maintainer owns the alias
table (the list that maps inventory names to products).

**What happens if the maintainer stops?** The tool is offline and uses only
the Python standard library, so it keeps working on the last data release
you hold. It warns when data goes stale: after 3 days for KEV and 30 days
for the end-of-life snapshot. After 7 days it reports the KEV overlay as
"not current". New data and new aliases would stop arriving.

**How does a finding become a change request?** Through your change
process. The tool does not create tickets. You raise the change, then
record its reference in `tracking.csv` (step 11).

**Does it follow a standard?** `docs/crosswalk.csv` maps the themes to
published standards as a reference. Some cells are secondary-sourced and
marked in `unverified_columns`. See [themes.md](themes.md). The KEV overlay
is a reference for prioritization. It does not show compliance with any
standard. CISA's current binding directive for US federal civilian agencies, BOD 26-04, superseded BOD 22-01. It is a reference only. It binds federal civilian agencies only. This tool does not implement it or its deadlines. Details are not reviewed here (Unverified).

**What is the support level?** Maintained as time allows, best effort, no
SLA. The repo is on the Experiment track with a review date of 2027-01-31.
