# Themes XW-029 to XW-032

Each theme is a job the tool helps with. `crosswalk.csv` in this folder
lists the published standards that touch each one. It is a reference, not
a claim of compliance.

## How to read crosswalk.csv

Editions used: ISO/IEC 19770-1:2017; NIST SP 800-53 Rev 5; NIST CSF 2.0;
CIS Controls v8.1; ISO/IEC 27001:2022; COBIT 2019.

## What was checked, and against what

Page numbers are printed pages. The verdicts mean this:

- Partial: the text fits only part of the claim.
- Supported: the text fits the claim as written.
- Supported with limits: the text fits, but leaves out part of the claim.
- Partial, weak fit: the match is thin.
- Partial, related only: the control stays in the CSV as a related
  control, not as a fit.
- Read earlier, no per-cell verdict recorded: the control was read but no
  verdict was kept.

A cell can be Supported and still not be a direct requirement.

What was checked, column by column:

- `iso27001`: checked against ISO/IEC 27001:2022. Amendment 1 (2024) was
  not opened: Unverified.
- `iso19770_1`: checked against ISO/IEC 19770-1:2017. Amendment 1 (2024)
  was not opened: Unverified. The 19770-1 clauses read are the ones in
  the table below. Other 19770-1 clauses were not read.
- ISO/IEC 19770-2:2015 (SWID tags) was read for the elements
  SoftwareIdentity (8.5.1), Link (8.5.4), SoftwareMeta (8.6.11) and
  VersionScheme (8.6.13). None carries support-end data, so there is no
  19770-2 column. Pages 17 to 22 of 19770-2 were not read.
- `nist_csf2`: checked against the CSF 2.0 Core, NIST CSWP.29 (pp.16-21).
  NIST.CSWP.40 in the same folder is the NIST Privacy Framework draft, not
  the CSF, and is not cited.
- `nist_800_53`: checked against NIST SP 800-53 Rev 5 (PDF page is the
  printed page plus 27). Read: SA-22, CM-8, CM-2(2), CM-8(4), CM-3 (items
  c and e), PM-4, PM-5, RA-5, SI-5, PM-16, RA-7, RA-3, CA-5, AC-5, CA-6
  and CA-7.
- `cis_v8`: the cells 2.1, 2.2, 7.1 and 7.2 were checked against the CIS
  Controls v8.1 guide (June 2024). The v8 versus v8.1 title hedge is
  dropped for those four controls.
- `cobit2019`: checked against the COBIT 2019 Governance and Management
  Objectives volume (ISACA 2018). Every cell is Partial: no cited practice
  is a direct match. The 2018 text cites NIST 800-53 Rev 5 (Draft) and CIS
  v6.1. A newer COBIT 2019 publication date is Unverified. APO03, BAI03
  and the MEA objectives were not checked. Cells hold practice IDs where
  one fits, otherwise the objective.
- ITIL 4 cells hold practice names. ITIL 4 has no clause numbers.
- ISO/IEC 20000-1 cells hold clause numbers.

### Verdicts per control

| Source | ID and title | Page | Row | Verdict |
| --- | --- | --- | --- | --- |
| 27001 | A.5.9 Inventory of information and other associated assets | 11 | XW-029 | Partial |
| 27001 | A.5.9 | 11 | XW-032 | Supported |
| 27001 | A.8.8 Management of technical vulnerabilities | 16 | XW-029 | Partial |
| 27001 | A.8.8 | 16 | XW-030 | Supported |
| 27001 | A.5.7 Threat intelligence | 11 | XW-030 | Supported |
| 27001 | 6.1.3 Information security risk treatment | 4-5 | XW-031 | Supported with limits |
| 27001 | A.5.3 Segregation of duties | 11 | XW-031 | Supported |
| 27001 | A.8.32 Change management | 17 | XW-032 | Supported |
| 27001 | A.5.2 Information security roles and responsibilities | 11 | XW-032 | Supported (not per-item) |
| 19770-1 | 8.3 Core data management | 22 | XW-029, XW-030 | Partial |
| 19770-1 | 6.1.2 IT asset risk assessment | 15-16 | XW-029, XW-030 | Partial |
| 19770-1 | 6.2.4 item b | 18 | XW-029 | Partial |
| 19770-1 | Annex A, Table A.1, Retirement objective | 29 | XW-029 | Supported with limits (covers removing assets, not tracking end of life) |
| 19770-1 | 8.5 Security management | 23 | XW-030 | Partial, weak fit (nothing on vulnerabilities) |
| 19770-1 | 6.1.3 IT asset risk treatment | 16 | XW-031 | Supported |
| 19770-1 | 7.6.3 Audit trails of authorizations | 21 | XW-031, XW-032 | Supported |
| 19770-1 | 5.3 Organizational roles, responsibilities and authorities | 14 | XW-031 | Partial |
| 19770-1 | 7.6.2 Traceability of ownership and responsibility | 20 | XW-032 | Supported |
| 19770-1 | 7.6.5 Control of documented information | 21 | XW-032 | Partial |
| 19770-1 | 8.2 Management of change | 22 | XW-032 | Supported |
| 19770-1 | 9.1 Monitoring, measurement, analysis and evaluation | 24 | XW-032 | Partial |
| 19770-1 | 10.1 Nonconformity and corrective action | 26 | XW-032 | Partial |
| CSF 2.0 | ID.AM-02 | 18 | XW-029 | Supported |
| CSF 2.0 | ID.AM-02 | 18 | XW-032 | Partial |
| CSF 2.0 | ID.AM-08 | 18 | XW-029 | Supported |
| CSF 2.0 | PR.PS-02 | 20 | XW-029 | Supported (best fit) |
| CSF 2.0 | ID.RA-01 | 18 | XW-030 | Partial |
| CSF 2.0 | ID.RA-02 | 19 | XW-030 | Supported |
| CSF 2.0 | ID.RA-05 | 19 | XW-030 | Supported |
| CSF 2.0 | ID.RA-06 | 19 | XW-031 | Partial |
| CSF 2.0 | ID.RA-07 | 19 | XW-031 | Supported |
| CSF 2.0 | ID.RA-07 | 19 | XW-032 | Partial |
| CSF 2.0 | GV.RR-02 | 17 | XW-032 | Partial |
| 800-53 | RA-5 Vulnerability Monitoring and Scanning | 242-243 | XW-030 | Partial |
| 800-53 | SI-5 Security Alerts, Advisories, and Directives | 343-344 | XW-030 | Partial |
| 800-53 | RA-3 Risk Assessment | 240 | XW-030, XW-031 | Partial (does not cover risk acceptance) |
| 800-53 | RA-7 Risk Response | 246 | XW-031 | Partial |
| 800-53 | CA-6 Authorization | 89-90 | XW-031 | Partial (closest to independent approval, but it authorizes a system; expiry only as a re-authorization frequency) |
| 800-53 | CA-5 Plan of Action and Milestones | 88 | XW-031 | Partial, related only |
| 800-53 | AC-5 Separation of Duties | 36 | XW-031 | Partial, related only |
| 800-53 | CA-7 Continuous Monitoring | 90-91 | XW-032 | Partial, related only |
| 800-53 | SA-22 | 290 | XW-029, XW-031 | Read earlier, no per-cell verdict recorded |
| 800-53 | CM-8 | 107-108 | XW-029 | Read earlier, no per-cell verdict recorded |
| 800-53 | CM-8(4) | 109 | XW-032 | Read earlier, no per-cell verdict recorded |
| 800-53 | CM-3 | 98-99 | XW-032 | Read earlier, no per-cell verdict recorded |
| 800-53 | PM-4 | 205 | XW-032 | Read earlier, no per-cell verdict recorded |
| CIS v8.1 | 2.1, 2.2, 7.1, 7.2 | - | XW-029, XW-030, XW-031 | Read earlier, no per-cell verdict recorded |

Limits seen in the text:

- 27001 6.1.3 and 19770-1 6.1.3 have owners approve the plan and accept
  residual risk, but say nothing on expiry or an independent approver.
- The CSF text has nothing on per-item ownership or independent approval.
- RA-5 and SI-5 do not name a known-exploited list.
- RA-7 has no expiry or independent approval.
- CA-6 is the closest 800-53 control to independent approval, as
  co-authorizing officials, but it authorizes a system and sets
  re-authorization frequency, not an expiry.
- In 19770-1 7.6.3, authorizations can be time-limited.
- 19770-1 8.3 has no end-of-life idea.

Related only: CA-5, AC-5 and CA-7 stay in the CSV as related controls,
not as a fit. AC-5 names no requester-versus-approver rule.

Dropped: 27001 A.5.33, CSF GV.RM-02 and 800-53 PM-16 fit only weakly.
RA-3(3) (p.241) is a closer fit than PM-16 for threat context.

### What stays Unverified

- `itil4`: ITIL 4 Essentials (2nd ed., 2020, pp.126-179) is a secondary
  book, not the official practice guides. It names the seven practices.
  Its fit is Supported for IT asset management, service configuration
  management and change enablement. Its fit is Partial for supplier,
  information security, risk and problem management. The official
  practice guides for the seven practices were not available. The
  official Service Design practice guide is not one of the seven and does
  not speak to the claims (pp.1-8 read, pp.9-31 not read). A third-party
  ITIL materials folder is not cited. Best status: checked against a
  secondary summary.
- `iso20000_1`: the ISO/IEC 20000-1:2018 standard text was not available.
  A third-party template kit shows no clause numbers, so the cells stay
  leads.
- Amendment 1 (2024) to ISO/IEC 27001 and ISO/IEC 19770-1.
- The `unverified_columns` column lists, per row, the columns not checked
  against the standard text. Treat those as leads, not citations:
  - XW-029: `itil4`, `iso20000_1`
  - XW-030: `itil4`, `iso20000_1`
  - XW-031: `itil4`, `iso20000_1`
  - XW-032: `itil4`, `iso20000_1`

### CSDM notes

CSDM is not a column. Findings from the 3.0 white paper, the CSDM 5
document and a third-party explainer:

- Product models carry end-of-life details, and CSDM 5 adds life cycle
  stages (Operational, End of Life) on every configuration item.
- No operating system or edition attribute was found in the pages read.
- Discoverable installations are limited to one host.

### Other notes

- `verified` stays empty on any row that has an unverified column. Every
  row does today, because `itil4` and `iso20000_1` stay Unverified.
- Every mapping is a closest match, not a direct requirement.
- CSAM p.165 defines release and version by the digits around the decimal
  point. Do not use it for cycle logic.

## XW-029: End-of-life and end-of-support tracking for software

Know which installed software the vendor no longer supports, or soon will
not.

Implemented by the "Past end of life", "Ends within the lookahead window"
and "Couldn't match" lists, and by the golden-sources file, which records
which date is right for a product. The optional support-records file
shows the owner's own support records beside those dates, as a renewal
aid. It adds no list and changes no state.

COBIT 2019 (Partial): BAI09 is the main fit, BAI09.01 (p.209) and BAI09.03
(p.211). BAI10 (p.215) and APO10 (p.119) are weak: nothing on lifecycle or
end of support, so they are dropped. PM-5 is not cited: it is an inventory
of whole systems, not components (NIST p.206). SA-22 and CM-8 stay.
CIS 2.2 expects a monthly review of supported software (p.20); the SOP
sets a quarterly review (`sop.md`, Cadence). The difference is real.

## XW-030: Known-exploited vulnerability overlay on the software inventory

Mark old software whose vendor and product appear in CISA KEV, so a person
reviews it first. It is a reference for prioritization.

Implemented by the "In CISA KEV, past or near end of life" list. It
matches vendor and product only, never version, and says "needs review".
It does not say any version is affected.

COBIT 2019 (Partial): DSS05 (p.257) is primary, DSS05.07 (p.261). APO12 (p.131) is weak and secondary.

## XW-031: Risk acceptance with expiry and independent approval

When old software must stay, named people accept the risk and the
acceptance expires.

Implemented by `exceptions.csv` and the "Accepted risk" list. The file
needs a risk owner, an approver who is not the requester, an expiry date
and a reference. An expired exception shows up as `EXCEPTION_EXPIRED` in
`decision_needed`.

COBIT 2019 (Partial): APO12.02, APO12.04, APO12.05 (pp.132-133) fit best.
No COBIT counterpart was found for the independent-approver rule.

## XW-032: Ownership, evidence and change linkage for lifecycle findings

Every finding has an owner, a record of what was decided and a link to the
change that fixes it.

Implemented by the "Ownerless" list, the hashes and data release ID in
`report.json`, the `--previous` diff, and `tracking.csv`, which links an
item ID to a change reference and a problem reference.

COBIT 2019 (Partial): BAI06 (p.193), DSS03 (p.243) and BAI10 (p.215) are
reasonable; BAI09.01 act. 1 (p.209) is added. Item ownership at practice
level: Not found.
