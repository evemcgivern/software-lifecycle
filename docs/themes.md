# Themes XW-029 to XW-032

Each theme is a job the tool helps with. `crosswalk.csv` in this folder
lists published standards that touch each one. It is a reference, not a
claim of compliance.

## How to read crosswalk.csv

Editions used: ISO/IEC 19770-1:2017; NIST SP 800-53 Rev 5; NIST CSF 2.0;
CIS Controls v8.1; ISO/IEC 27001:2022.

- ISO/IEC 19770-1 cells hold clause numbers, checked against the contents
  page of a public preview.
- ITIL 4 cells hold practice names. ITIL 4 has no clause numbers.
- NIST 800-53, CSF 2.0 and CIS cells were checked against the publishers'
  own lists, or against third-party summaries of the standard, not the
  standard text itself. The CIS control titles are the same
  in v8 and v8.1; that rests on matching titles, not on CIS's change log.
- The `unverified_columns` column lists the columns whose numbers came only
  from third-party summaries of the standard, not the standard text itself: here `iso20000_1`, `cobit2019` and `iso27001`.
  Treat those as leads to check, not as citations.
- `verified` stays empty on any row that has an unverified column. Every
  row does today.
- Every mapping is a closest match, not a direct requirement.

## XW-029: End-of-life and end-of-support tracking for software

Know which installed software the vendor no longer supports, or soon will
not. Implemented by the "Past end of life", "Ends within the lookahead
window" and "Couldn't match" lists, and by the golden-sources file, which
records which date is right for a product. The optional support-records
file shows the owner's own support records beside those dates, as a
renewal aid; it adds no list and changes no state.

## XW-030: Known-exploited vulnerability overlay on the software inventory

Mark old software whose vendor and product appear in CISA KEV, so a person
reviews it first. It is a reference for prioritization. Implemented by the
"In CISA KEV, past or near end of life" list. It matches vendor and product only, never version,
and says "needs review". It does not say any version is affected.

## XW-031: Risk acceptance with expiry and independent approval

When old software must stay, the risk is accepted by named people and
expires. Implemented by `exceptions.csv` and the "Accepted risk" list. The
file needs a risk owner, an approver who is not the requester, an expiry
date and a reference. An expired exception shows up as `EXCEPTION_EXPIRED`
in `decision_needed`.

## XW-032: Ownership, evidence and change linkage for lifecycle findings

Every finding has an owner, a record of what was decided and a link to the
change that fixes it. Implemented by the "Ownerless" list, the hashes and
data release ID in `report.json`, the `--previous` diff, and `tracking.csv`,
which links an item ID to a change reference and a problem reference.
