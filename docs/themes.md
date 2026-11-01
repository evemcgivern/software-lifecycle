# Themes XW-029 to XW-032

Each theme is a job the tool helps with. `crosswalk.csv` in this folder
lists published standards that touch each one. It is a reference, not a
claim of compliance.

## How to read crosswalk.csv

Editions used: ISO/IEC 19770-1:2017; NIST SP 800-53 Rev 5; NIST CSF 2.0;
CIS Controls v8.1; ISO/IEC 27001:2022.

- ISO/IEC 19770-1 cells hold clause numbers, checked against the contents
  page of a public preview. Clause 8.3 (core data management, p.22) was
  read in the standard itself.
- ITIL 4 cells hold practice names. ITIL 4 has no clause numbers.
- The CIS cells (2.1, 2.2, 7.1, 7.2) were checked against the CIS Controls
  v8.1 guide (June 2024) text, and the NIST 800-53 cells SA-22, CM-8,
  CM-8(4), CM-3 and PM-4 against NIST SP 800-53 Rev 5. The v8 versus
  v8.1 title hedge is dropped for those four CIS controls.
- cobit2019 cells were checked against the COBIT 2019 Governance and
  Management Objectives volume (ISACA 2018). Every cell is Partial: no
  cited practice is a direct match. The 2018 text cites NIST 800-53
  Rev 5 (Draft) and CIS v6.1, and a newer COBIT 2019 publication date is
  Unverified. APO03, BAI03 and the MEA objectives were not checked. Cells
  hold practice IDs; page numbers below are printed pages.
- The `unverified_columns` column lists, per row, the columns not checked
  against the standard text. Treat those as leads, not citations:
  - XW-029: `itil4`, `iso20000_1`, `nist_csf2`, `iso27001`
  - XW-030: `itil4`, `iso20000_1`, `nist_800_53` (RA-5, SI-5, PM-16),
    `nist_csf2`, `iso27001`
  - XW-031: `itil4`, `iso20000_1`, `nist_800_53` (RA-7, CA-5, AC-5),
    `nist_csf2`, `iso27001`
  - XW-032: `itil4`, `iso20000_1`, `nist_800_53` (CA-7), `nist_csf2`,
    `iso27001`
  Also Unverified: the ISO/IEC 19770-2 platform elements (SWID), CSDM, and
  the clause numbers of ITIL and ISO/IEC 20000-1.
- `verified` stays empty on any row that has an unverified column. Every
  row does today.
- Every mapping is a closest match, not a direct requirement.
- CSAM p.165 defines release and version by the digits around the decimal
  point. Do not use it for cycle logic.

## XW-029: End-of-life and end-of-support tracking for software

Know which installed software the vendor no longer supports, or soon will
not. Implemented by the "Past end of life", "Ends within the lookahead
window" and "Couldn't match" lists, and by the golden-sources file, which
records which date is right for a product. The optional support-records
file shows the owner's own support records beside those dates, as a
renewal aid; it adds no list and changes no state.

COBIT 2019 (Partial): BAI09 is the main fit, BAI09.01 (p.209) and BAI09.03
(p.211). BAI10 (p.215) and APO10 (p.119) are weak: nothing on lifecycle or
end of support, so they are dropped. PM-5 is not cited: it is an inventory
of whole systems, not components (NIST p.206). SA-22 and CM-8 stay.
CIS 2.2 expects a monthly review of supported software (p.20); the SOP
sets a quarterly review (`sop.md`, Cadence). The difference is real.

## XW-030: Known-exploited vulnerability overlay on the software inventory

Mark old software whose vendor and product appear in CISA KEV, so a person
reviews it first. It is a reference for prioritization. Implemented by the
"In CISA KEV, past or near end of life" list. It matches vendor and product only, never version,
and says "needs review". It does not say any version is affected.

COBIT 2019 (Partial): DSS05 (p.257) is primary, DSS05.07 (p.261) and
DSS05.01 act. 5. APO12 (p.131) is weak and secondary.

## XW-031: Risk acceptance with expiry and independent approval

When old software must stay, the risk is accepted by named people and
expires. Implemented by `exceptions.csv` and the "Accepted risk" list. The
file needs a risk owner, an approver who is not the requester, an expiry
date and a reference. An expired exception shows up as `EXCEPTION_EXPIRED`
in `decision_needed`.

COBIT 2019 (Partial): APO12.02, APO12.04, APO12.05 (pp.132-133) fit best.
No COBIT counterpart was found for the independent-approver rule.

## XW-032: Ownership, evidence and change linkage for lifecycle findings

Every finding has an owner, a record of what was decided and a link to the
change that fixes it. Implemented by the "Ownerless" list, the hashes and
data release ID in `report.json`, the `--previous` diff, and `tracking.csv`,
which links an item ID to a change reference and a problem reference.

COBIT 2019 (Partial): BAI06 (p.193), DSS03 (p.243) and BAI10 (p.215) are
reasonable; BAI09.01 act. 1 (p.209) is added. Item ownership at practice
level: Not found.
