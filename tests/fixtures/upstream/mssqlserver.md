---
title: Microsoft SQL Server
addedAt: 2019-12-17
category: database
tags: microsoft
iconSlug: microsoftsqlserver
permalink: /mssqlserver
alternate_urls:
  - /mssql
  - /microsoftsqlserver
versionCommand: select @@version
releasePolicyLink: https://learn.microsoft.com/lifecycle/products/?terms=SQL%20Server
eoasColumn: true
eoesColumn: Extended Security Updates

customFields:
  - name: latestGdr
    display: api-only
    label: Latest General Distribution Release
  - name: latestGdrLink
    display: api-only
    label: Latest General Distribution Release link

identifiers:
  - cpe: cpe:/a:microsoft:sql_server
  - cpe: cpe:2.3:a:microsoft:sql_server

# releaseDate/support/eol/extendedSupport: https://learn.microsoft.com/lifecycle/products/?terms=SQL%20Server
# Overview over all versions: https://learn.microsoft.com/troubleshoot/sql/releases/download-and-install-latest-updates
releases:
  - releaseCycle: "17.0"
    codename: SQL25
    releaseLabel: "2025"
    releaseDate: 2025-11-18
    eoas: 2031-01-06
    eol: 2036-01-06
    latestGdr: "17.0.1145.4"
    latestGdrLink: https://support.microsoft.com/help/5128492
    latest: "17.0.5035.5 CU10"
    latestReleaseDate: 2026-10-22
    link: https://support.microsoft.com/help/5125471

  - releaseCycle: "16.0"
    codename: Dallas
    releaseLabel: "2022 '__CODENAME__'"
    releaseDate: 2022-11-16
    eoas: 2028-01-11
    eol: 2033-01-11
    latestGdr: "16.0.1210.3"
    latestGdrLink: https://support.microsoft.com/help/5128493
    latest: "16.0.4305.5 CU27+GDR"
    latestReleaseDate: 2026-10-13
    # CU27 link: https://support.microsoft.com/help/5104824
    link: https://support.microsoft.com/help/5126934 # GDR for CU27

  - releaseCycle: "13.0-sp3-acp"
    codename: SQL16
    releaseLabel: "2016 SP3 Azure Connect Pack"
    releaseDate: 2022-05-19
    eoas: 2026-07-14
    eol: 2026-07-14
    eoes: 2029-07-17
    latestGdr: "13.0.7095.1"
    latestGdrLink: https://support.microsoft.com/help/5102339
    latest: "13.0.7095.1 Azure Connect pack+GDR"
    latestReleaseDate: 2026-07-14
    # SP3 link: https://learn.microsoft.com/troubleshoot/sql/releases/sqlserver-2016/servicepack3
    # Azure Connect pack link: https://learn.microsoft.com/troubleshoot/sql/releases/sqlserver-2016/servicepack3-azureconnect
    link: https://support.microsoft.com/help/5102339 # GDR for Azure Connect pack

  - releaseCycle: "13.0-sp3"
    codename: SQL16
    releaseLabel: "2016 SP3"
    releaseDate: 2021-09-15
    eoas: 2026-07-14
    eol: 2026-07-14
    eoes: 2029-07-17
    latestGdr: "13.0.6500.1"
    latestGdrLink: https://support.microsoft.com/help/5102340
    latest: "13.0.6500.1 GDR"
    latestReleaseDate: 2026-07-14
    # SP3 link: https://learn.microsoft.com/troubleshoot/sql/releases/sqlserver-2016/servicepack3
    link: https://support.microsoft.com/help/5102340

---

Description text removed from this test copy.
