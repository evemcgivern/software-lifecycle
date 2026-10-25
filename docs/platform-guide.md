# Platform guide: getting an inventory export

This page says where to find a software inventory export in three
platforms and which column headings the tool's profiles expect. Facts here
come only from pages fetched on 2026-10-24 (see Sources). Where no fetched
page says it, this page says "Not found". The vendor pages can change; check
them.

## How profiles work

A profile is a pre-filled list of extra column headings, nothing more. It
does not change how the tool matches products or dates. Use one with
`--profile flexera`, `--profile servicenow-mbs` or `--profile rapid7`.
The profile lists live in `data/profiles.json`. All three are marked
**Unverified**: no one has run them on a real export.

If a heading does not match, the tool stops and names the missing field.
Add your own headings with `--columns FILE` (see
`templates/columns.example.json`), or rename the column in the file. The
tool never guesses.

## Flexera

- Where to export: Not found. The Flexera documentation pages in the
  Sources section returned HTTP 403 (access refused) when fetched, so no
  Flexera page was read.
- Headings the profile expects, from `data/profiles.json` (maintainer's
  list, Unverified): name as `Application name` or `Application`;
  publisher as `Publisher`; version as `Version`; count as `Installed` or
  `Installations`; export_eol as `End of life`; export_support as
  `End of support`.
- Whether a Flexera export uses those headings: Not found.

## ServiceNow

The profile name `servicenow-mbs` is a label from the maintainer. Its
meaning is not documented here.

- Table: ServiceNow's Xanadu IT Asset Management documentation names the
  "Software Installation" table as `cmdb_sam_sw_install`.
- Fields on the Software Installation form, per that page: Display name,
  Discovery model, Publisher, Version, Edition Override, Prod id
  (deprecated, shows empty), Install location, Install date, Revision
  (deprecated, shows empty), Instance key, Installed on, Uninstall string,
  ISO serial number, Entitlement (deprecated, shows empty), Inferred suite,
  Omit from suites. The page does not list every field of the table.
- Export a list: the Xanadu documentation says to open the list, select and
  hold or right-click any column header, choose the CSV export option, and
  when the export finishes, click Download. In List v3 the export option is
  in the list title menu instead. Exports run in the background, so the
  data may differ from the list view if the table has session-dependent
  ACLs (access rules).
- Which column headings a list export of that table produces (labels such
  as `Display name`, or field names such as `display_name`): Not found.
- Headings the profile expects, from `data/profiles.json` (Unverified):
  name as `Display name` or `display_name`; publisher as `Publisher` or
  `publisher`; version as `Version` or `version`.
- The profile has no headings for owner, count or end-of-life dates. Add
  them with `--columns` if your export has them. Whether the table holds
  them: Not found.

## Rapid7

- Table: Rapid7's InsightVM reporting data model documentation describes
  the dimension `dim_software` ("all the software packages that have been
  enumerated"). Its columns are `software_id`, `vendor`, `family`, `name`,
  `version`, `software_class` and `cpe`. A related dimension,
  `dim_asset_software`, links assets to software through `software_id`.
  Only the first 100,000 characters of that page were read.
- Export: a reply in a Rapid7 community thread (May 2025, replier's role not
  shown) says to use the query builder, go to the Software tab, and export
  as CSV. A second reply says a warehouse query or the console can also do
  it but would be "time and resource consuming". This is community advice,
  not Rapid7 documentation. An official export procedure: Not found.
- Headings the profile expects, from `data/profiles.json` (Unverified):
  name as `name`; publisher as `vendor`; version as `version`.
- Whether the export carries owners, counts or end-of-life dates: Not found.
- End-of-life dates: the fetched part of the data model page gave no
  end-of-life dates for software. The maintainer reports that some Rapid7
  end-of-life dates are wrong. This is a maintainer report, not a sourced
  fact. This tool lets you choose the right date per product in
  `golden-sources.csv`.

## Sources

Fetched or attempted on 2026-10-24.

- Flexera, attempted, HTTP 403, not read:
  https://docs.flexera.com/flexera-one/it-assets/reports-introduction/reports-ootb/application-and-license-installations-report
- Flexera, attempted, HTTP 403, not read:
  https://docs.flexera.com/flexera-one/it-assets/app-applications/app-application-publisher/app-publisher-properties/installed-applications-page
- ServiceNow, "Software installation fields" (Xanadu), fetched 2026-10-24:
  https://www.servicenow.com/docs/r/w3Hg5id41C9xrkzqBsUMhA/IuFu7WtUjVe4xjLvvDqDXA
- ServiceNow, "Export data from a list" (Xanadu, updated 2024-08-01 per the
  page), fetched 2026-10-24:
  https://www.servicenow.com/docs/r/SbrhqYG7UKQCk7uYwvgVBA/i7sDpMe8BxnzsKw~YbJXxg
- Flexera's ServiceNow integration page, listed in `data/profiles.json` as a
  profile source for `servicenow-mbs`, attempted, HTTP 403, not read:
  https://docs.flexera.com/ServiceNowFlexeraIntegrationApp/ITVisibility/v507/helplibrary/ExportFromSNTables.htm
- Rapid7, "Understanding the reporting data model: dimensions", fetched
  2026-10-24 (first 100,000 of 113,951 characters read):
  https://docs.rapid7.com/insightvm/understanding-the-reporting-data-model-dimensions/
- Rapid7 community thread, fetched 2026-10-24:
  https://discuss.rapid7.com/t/how-to-export-a-list-of-all-installed-software-across-all-vms-for-compliance-eol-audits/51169
