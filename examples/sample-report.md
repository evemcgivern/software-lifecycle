# Software lifecycle report

Sample note: the Hostile Corp rows (a script tag, a spreadsheet formula and a shell command) are planted tests of how the tool handles unsafe text.

Checked on: 2026-10-24. Lookahead: 12 months.
Tool version: 0.5.0. Data release: fixture-1.
End-of-life dates: per endoflife.date, snapshot 2026-10-20 (4 days old).
KEV: CISA KEV catalog 2026.10.22, snapshot 2026-10-22 (2 days old).

Runs locally with no network by default; not independently assessed.

This report shows end-of-life dates from your data and the snapshots above. It does not say whether any version is affected by a flaw. It contains text from your inventory; keep it as private as the inventory.

Warning: 1 parts whose parent is not in this inventory

Items: 50 (rows: 60; inventory rows, not installs). past end of life 8; ends within the lookahead window 5; dates disagree 4; couldn't match 11; in CISA KEV, past or near end of life 2; accepted risk 1; ownerless 1; golden source overrides 1; names to review 1.

Matches rest on name and publisher only. Rows we could not tell apart are listed as unmatched. Check the source and cycle before relying on any row.

Items in each section are ordered by the count from your file, largest first, then items with no count. The count is the sum of your file's count column, not discovered installs.

Count cells ignored: 1. A count cell is used only when it is a whole number from 0 to 1000000000.

## Past end of life (8)

- **Quillbase Database** 12.0.6024.0, publisher Placeholder Labs (id `34f37eea99c2`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Infrastructure. Inventory rows: 1
  - Count (from your file): 388
  - End of life: 2024-07-09 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2019-07-09 per endoflife.date, snapshot 2026-10-20
- **Demo OS 1.0** 1.0, publisher Fictional Software Ltd (id `faa0f833f626`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Infrastructure, Support Desk. Inventory rows: 2
  - Count (from your file): 383
  - End of life: 2025-06-30 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2024-06-30 per endoflife.date, snapshot 2026-10-20
  - Accepted risk per your exceptions file. The tool lists it and does not confirm the sign-off.
  - Change reference: CHG-1001
  - Problem reference: PRB-2001
- **Tidewater Suite** 1.0, publisher Example Corp (id `153057dabd68`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 372
  - End of life: 2026-10-24 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2025-10-24 per endoflife.date, snapshot 2026-10-20
- **Harborview CRM** 5.1, publisher Fictional Software Ltd (id `5095e8b556dd`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Marketing Ops. Inventory rows: 1
  - Count (from your file): 314
  - End of life: 2026-06-30 per your export; golden source per your file
  - Other date, shown beside the one used: 2028-01-01 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: ongoing per endoflife.date, snapshot 2026-10-20
- **Tidewater Suite** 4.2, publisher Example Corp (id `8e099c3b6863`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 302
  - End of life: 2026-03-01 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2025-03-01 per endoflife.date, snapshot 2026-10-20
  - A support record is listed in your file: SR-1001, extended support, ends on 2027-06-30 (scope: 4).
  - The tool does not check that this record is current.
  - Change reference: CHG-1002
- **Example SQL** 14, publisher Sample Systems Inc (id `0a668be21645`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 91
  - End of life: reached (no date given) per endoflife.date, snapshot 2026-10-20
  - Mainstream support: ended per endoflife.date, snapshot 2026-10-20
  - A support record is listed in your file: SR-1002, extended support, ended on 2026-06-30 (scope: 14).
  - The tool does not check that this record is current.
- **Northwind Gateway** 4.1, publisher Northwind Software (id `c3756f7f9c32`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 45
  - End of life: 2025-12-31 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2024-12-31 per endoflife.date, snapshot 2026-10-20
  - A support record is listed in your file: SR-1004, vendor support, ends on 2029-01-31 (scope: any cycle of this product).
  - The tool does not check that this record is current.
  - KEV: The vendor and product appear in CISA KEV. This does not mean your version is affected. Needs review.
- **Redwood Backup** 1.0, publisher Sample Systems Inc (id `55be4cfcc848`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Infrastructure. Inventory rows: 1
  - End of life: 2025-01-31 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2024-01-31 per endoflife.date, snapshot 2026-10-20
  - **Decision needed:** The risk exception has expired. The asset owner requests risk acceptance again; the risk owner and an independent approver sign off. The tool names roles and never assigns people.

## Ends within the lookahead window (5)

- **Example SQL** 15, publisher Example Vendor (id `a3f0e99e87b4`)
  - State: ends within the lookahead window
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 263
  - End of life: 2026-12-31 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2024-12-31 per endoflife.date, snapshot 2026-10-20
  - Extended support: 2028-12-31 per endoflife.date, snapshot 2026-10-20
  - KEV: The vendor and product appear in CISA KEV. This does not mean your version is affected. Needs review.
- **Pinecone Archive** 2.0, publisher Placeholder Labs (id `17559088ded2`)
  - State: ends within the lookahead window
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Records Office. Inventory rows: 1
  - Count (from your file): 258
  - End of life: 2027-02-28 per endoflife.date, snapshot 2026-10-20
  - Other date: 2027-05-31 per your export
  - Mainstream support: 2025-12-31 per endoflife.date, snapshot 2026-10-20
  - Dates disagree: GOLDEN_EXPIRED
  - **Decision needed:** The golden source's review-by date has passed, so the item is back on the dates-disagree list. The ITAM lead settles the date and renews or ends the golden source.
- **Tidewater Suite** 2.0, publisher Example Corp (id `3dbe716847ae`)
  - State: ends within the lookahead window
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 158
  - End of life: 2027-10-24 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2026-01-01 per endoflife.date, snapshot 2026-10-20
- **Tidewater Suite** 5.0, publisher Example Corp (id `ffc50ca894b4`)
  - State: ends within the lookahead window
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 39
  - End of life: 2027-03-15 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2026-03-15 per endoflife.date, snapshot 2026-10-20
  - A support record is listed in your file: SR-1003, vendor support, ends on 2028-03-31 (scope: 5.0).
  - The tool does not check that this record is current.
- **Tidewater Suite** 5.1, publisher Example Corp (id `769398c5545d`)
  - State: ends within the lookahead window
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 10
  - End of life: 2027-03-15 per endoflife.date, snapshot 2026-10-20
  - Other date: 2027-04-30 per your export
  - Mainstream support: 2026-03-15 per endoflife.date, snapshot 2026-10-20
  - Dates disagree: DIFFERENT_DATE
  - **Decision needed:** The export date and the endoflife.date date differ. The ITAM lead settles which date to use. Nothing here is auto-resolved.

## Dates disagree (4)

- **Ironwood Scheduler** 2.0, publisher Placeholder Labs (id `800d6329e8a3`)
  - State: supported
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Facilities. Inventory rows: 2
  - Count (from your file): 664
  - End of life: 2028-05-31 per endoflife.date, snapshot 2026-10-20
  - Other date: unreadable text: 2028-05-31; 2028-06-30 per your export
  - Mainstream support: ongoing per endoflife.date, snapshot 2026-10-20
  - Dates disagree: EXPORT_DATES_CONFLICT
  - **Decision needed:** Rows for this item carry different export dates. The ITAM lead settles the date.
- **Pinecone Archive** 2.0, publisher Placeholder Labs (id `17559088ded2`)
  - State: ends within the lookahead window
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Records Office. Inventory rows: 1
  - Count (from your file): 258
  - End of life: 2027-02-28 per endoflife.date, snapshot 2026-10-20
  - Other date: 2027-05-31 per your export
  - Mainstream support: 2025-12-31 per endoflife.date, snapshot 2026-10-20
  - Dates disagree: GOLDEN_EXPIRED
  - **Decision needed:** The golden source's review-by date has passed, so the item is back on the dates-disagree list. The ITAM lead settles the date and renews or ends the golden source.
- **Mapleton Reports** 3.1, publisher Fictional Software Ltd (id `321fceafbdce`)
  - State: supported
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Records Office. Inventory rows: 1
  - Count (from your file): 99
  - End of life: no date given per endoflife.date, snapshot 2026-10-20
  - Other date: 2028-06-30 per your export
  - Mainstream support: ongoing per endoflife.date, snapshot 2026-10-20
  - Dates disagree: NO_ENDOFLIFE_DATE
  - **Decision needed:** endoflife.date has no date to compare with the export date. The ITAM lead settles which date to use.
- **Tidewater Suite** 5.1, publisher Example Corp (id `769398c5545d`)
  - State: ends within the lookahead window
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 10
  - End of life: 2027-03-15 per endoflife.date, snapshot 2026-10-20
  - Other date: 2027-04-30 per your export
  - Mainstream support: 2026-03-15 per endoflife.date, snapshot 2026-10-20
  - Dates disagree: DIFFERENT_DATE
  - **Decision needed:** The export date and the endoflife.date date differ. The ITAM lead settles which date to use. Nothing here is auto-resolved.

## Couldn't match (11)

Needs review: 8. Parts with a parent are listed in their own section.
Names to review: 1 of these were left unmatched on purpose; see "Names to review" below.

- **Brightline Editor** 9.0, publisher Fictional Software Ltd (id `bbccc7b93adf`)
  - State: could not be matched
  - Classification: governable (basis: category_governable)
  - Product known; version not matched.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 381
  - **Unverified:** product known (brightlineeditor), but no cycle was matched. Reason NO_CYCLE: no cycle matches this version, or the version in the name disagrees with it. No end-of-life date is claimed.
- **Brightline Editor** , publisher Fictional Software Ltd (id `b3e080c410cc`)
  - State: could not be matched
  - Classification: unknown (basis: category_governable, version_shape)
  - Product known; version not matched.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 336
  - **Unverified:** product known (brightlineeditor), but no cycle was matched. Reason NO_VERSION: no version given. No end-of-life date is claimed.
- **&lt;script&gt;alert\(1\)&lt;/script&gt;** 1, publisher Hostile Corp (id `7ba2dda739a2`)
  - State: could not be matched
  - Classification: unknown (basis: no_signal)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 299
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.
- **Orbit Client** 2, publisher Fictional Software Ltd (id `f3d465853a7a`)
  - State: could not be matched
  - Classification: unknown (basis: no_signal)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 287
  - **Unverified:** no known product was matched. Reason AMBIGUOUS: the name fits more than one product. No end-of-life date is claimed.
- **=cmd\|&#x27; /C calc&#x27;\!A0** 9, publisher Hostile Corp (id `f08603b790e5`)
  - State: could not be matched
  - Classification: unknown (basis: no_signal)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 250
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.
- **Util \| \`rm -rf\` tool** 2, publisher Hostile Corp (id `61053426d57d`)
  - State: could not be matched
  - Classification: unknown (basis: no_signal)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 137
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.
- **Quillbase** 2019 (id `cc1211feace1`)
  - State: could not be matched
  - Classification: unknown (basis: no_signal)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 131
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.
- **Mystery Tool** 3.1, publisher Nobody Inc (id `1261552c85af`)
  - State: could not be matched
  - Classification: unknown (basis: no_signal)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 32
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.

## Names to review (1)

Unmatched on purpose, not a finding. Each name looks like a catalog product, but there is not enough evidence to match it, so no product, cycle, date or state is claimed. To settle one, add a publisher that names the vendor, ask for a curated alias, or record that it is a different product. These items are also counted under "Couldn't match".

- **Quillbase** 2019 (id `cc1211feace1`)
  - Review: The name is a product title, but the row has no publisher to confirm the product.

## Parts that could not be matched (3)

- **Harborview CRM Mail Connector** 5.1.2, publisher Fictional Software Ltd (id `52f7be6ebed6`)
  - State: could not be matched
  - Classification: bundle_member (basis: no_signal, parent_column)
  - Parent's date (inherited, not this item's own): end of life 2026-06-30 per endoflife.date, state past end of life, from parent Harborview CRM (id `5095e8b556dd`)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 189
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.
- **Fieldnote Sync Agent** 1.2, publisher Placeholder Labs (id `0879b8a5b037`)
  - State: could not be matched
  - Classification: bundle_member (basis: no_signal, parent_column, parent_absent)
  - Parent: demoos/2.0, not in this inventory. No date shown.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 172
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.
- **Security Update for Demo OS 1.0 \(KB5000001\)** 1, publisher Acme Corp (id `86cd3cda695f`)
  - State: could not be matched
  - Classification: bundle_member (basis: name_os_part, os_parent)
  - Parent's date (inherited, not this item's own): end of life 2025-06-30 per endoflife.date, state past end of life, from parent Demo OS 1.0 (id `faa0f833f626`)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 147
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.

## Parts of a parent past or near end of life (2)

- **Harborview CRM Mail Connector** 5.1.2, publisher Fictional Software Ltd (id `52f7be6ebed6`)
  - State: could not be matched
  - Classification: bundle_member (basis: no_signal, parent_column)
  - Parent's date (inherited, not this item's own): end of life 2026-06-30 per endoflife.date, state past end of life, from parent Harborview CRM (id `5095e8b556dd`)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 189
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.
- **Security Update for Demo OS 1.0 \(KB5000001\)** 1, publisher Acme Corp (id `86cd3cda695f`)
  - State: could not be matched
  - Classification: bundle_member (basis: name_os_part, os_parent)
  - Parent's date (inherited, not this item's own): end of life 2025-06-30 per endoflife.date, state past end of life, from parent Demo OS 1.0 (id `faa0f833f626`)
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 147
  - **Unverified:** no known product was matched. Reason NO_ALIAS: no alias entry or product title fits this name. No end-of-life date is claimed.

## In CISA KEV, past or near end of life (2)

Needs review, not a finding that any version is affected. KEV is checked only for matched items that are past end of life or end within the window.

- **Example SQL** 15, publisher Example Vendor (id `a3f0e99e87b4`)
  - State: ends within the lookahead window
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 263
  - End of life: 2026-12-31 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2024-12-31 per endoflife.date, snapshot 2026-10-20
  - Extended support: 2028-12-31 per endoflife.date, snapshot 2026-10-20
  - KEV: The vendor and product appear in CISA KEV. This does not mean your version is affected. Needs review.
- **Northwind Gateway** 4.1, publisher Northwind Software (id `c3756f7f9c32`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Finance Systems. Inventory rows: 1
  - Count (from your file): 45
  - End of life: 2025-12-31 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2024-12-31 per endoflife.date, snapshot 2026-10-20
  - KEV: The vendor and product appear in CISA KEV. This does not mean your version is affected. Needs review.

## Accepted risk (1)

- **Demo OS 1.0** 1.0, publisher Fictional Software Ltd (id `faa0f833f626`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Infrastructure, Support Desk. Inventory rows: 2
  - Count (from your file): 383
  - End of life: 2025-06-30 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2024-06-30 per endoflife.date, snapshot 2026-10-20
  - Accepted risk per your exceptions file. The tool lists it and does not confirm the sign-off.
  - Change reference: CHG-1001
  - Problem reference: PRB-2001

## Ownerless (1)

- **Tidewater Suite** 6.0, publisher Example Corp (id `865a640f2016`)
  - State: supported
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: none listed. This item cannot be actioned until an owner is named. Inventory rows: 1
  - Count (from your file): 82
  - End of life: 2031-01-01 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: 2029-01-01 per endoflife.date, snapshot 2026-10-20

## Golden source overrides (1)

- **Harborview CRM** 5.1, publisher Fictional Software Ltd (id `5095e8b556dd`)
  - State: past end of life
  - Classification: governable (basis: category_governable)
  - Product matched by a curated alias.
  - Owners: Marketing Ops. Inventory rows: 1
  - Count (from your file): 314
  - End of life: 2026-06-30 per your export; golden source per your file
  - Other date, shown beside the one used: 2028-01-01 per endoflife.date, snapshot 2026-10-20
  - Mainstream support: ongoing per endoflife.date, snapshot 2026-10-20

## Support records

From your support-records file, shown beside the vendor's dates. A record never changes an item's state, never puts an item on a list and never affects --fail-on. The tool does not check that a record was paid for or is current. Discovery coverage is unknown: software missing from this inventory may still be in use. Extended support may include only some fixes or editions. Record references are confidential; keep this report as private as the file.

Listed: records that fit at least one dated item (an item with a product and cycle). Not matched to a dated item: records that fit none; this includes a product that appears in this inventory without a decided cycle or version. Listed and not matched add up to the records in the file. Ending within the lookahead window counts records from either group that end after the checked-on date and by the end of the window, so the counts overlap.

Listed against dated items in this inventory: 5. Ending within the lookahead window: 2. Not matched to a dated item in this inventory: 2.

Ending within the lookahead window (2):

- SR-1005, product copperfieldnotes, scope 9, extended support, ends on 2027-01-31.
- SR-1001, product tidewatersuite, scope 4, extended support, ends on 2027-06-30.

Not matched to a dated item in this inventory (2):

- SR-1005, product copperfieldnotes, scope 9, extended support, ends on 2027-01-31.
- SR-1006, product brightlineeditor, scope 9.0, vendor support, ends on 2028-12-31.

```findings
[{"type": "past_eol", "id": "34f37eea99c2"},
 {"type": "past_eol", "id": "faa0f833f626"},
 {"type": "past_eol", "id": "153057dabd68"},
 {"type": "past_eol", "id": "5095e8b556dd"},
 {"type": "past_eol", "id": "8e099c3b6863"},
 {"type": "past_eol", "id": "0a668be21645"},
 {"type": "past_eol", "id": "c3756f7f9c32"},
 {"type": "past_eol", "id": "55be4cfcc848"},
 {"type": "ends_soon", "id": "a3f0e99e87b4"},
 {"type": "ends_soon", "id": "17559088ded2"},
 {"type": "ends_soon", "id": "3dbe716847ae"},
 {"type": "ends_soon", "id": "ffc50ca894b4"},
 {"type": "ends_soon", "id": "769398c5545d"},
 {"type": "dates_disagree", "id": "800d6329e8a3"},
 {"type": "dates_disagree", "id": "17559088ded2"},
 {"type": "dates_disagree", "id": "321fceafbdce"},
 {"type": "dates_disagree", "id": "769398c5545d"},
 {"type": "unmatched", "id": "bbccc7b93adf"},
 {"type": "unmatched", "id": "b3e080c410cc"},
 {"type": "unmatched", "id": "7ba2dda739a2"},
 {"type": "unmatched", "id": "f3d465853a7a"},
 {"type": "unmatched", "id": "f08603b790e5"},
 {"type": "unmatched", "id": "52f7be6ebed6"},
 {"type": "unmatched", "id": "0879b8a5b037"},
 {"type": "unmatched", "id": "86cd3cda695f"},
 {"type": "unmatched", "id": "61053426d57d"},
 {"type": "unmatched", "id": "cc1211feace1"},
 {"type": "unmatched", "id": "1261552c85af"},
 {"type": "review_urgently", "id": "a3f0e99e87b4"},
 {"type": "review_urgently", "id": "c3756f7f9c32"}]
```
