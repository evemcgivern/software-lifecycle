---
title: Red Hat Enterprise Linux
addedAt: 2019-05-29
category: os
tags: red-hat linux-distribution
iconSlug: redhat
permalink: /rhel
alternate_urls:
  - /redhat
  - /redhatlinux
versionCommand: cat /etc/redhat-release
changelogTemplate: https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/__RELEASE_CYCLE__/html/__LATEST___release_notes/index
releasePolicyLink: https://access.redhat.com/support/policy/updates/errata
LTSLabel: "<abbr title='Extended Life Cycle Support'>ELS</abbr>"
eoasColumn: Full Support
eolColumn: Maintenance Support
eoesColumn: Extended Life Cycle Support

identifiers:
  - cpe: cpe:/o:redhat:enterprise_linux
  - cpe: cpe:2.3:o:redhat:enterprise_linux

auto:
  methods:
    - json_releases: "https://access.redhat.com/product-life-cycles/api/v1/products?name=Red%20Hat%20Enterprise%20Linux"
      selector: '$.data[0].versions[*]'
      fields:
        releaseCycle: '$.name'
        releaseDate: "$.phases[?(@.name == 'General availability')].date"
        eoas: "$.phases[?(@.name == 'Full support')].date"
        eol: "$.phases[?(@.name == 'Maintenance support')].date"
        eoes: "$.phases[?(@.name == 'Extended life cycle support (ELS) add-on')].date"

releases:
  - releaseCycle: "10"
    releaseDate: 2025-05-20
    eoas: 2030-05-31
    eol: 2035-05-31
    lts: 2035-05-31
    eoes: 2039-05-31
    latest: "10.2"
    latestReleaseDate: 2026-05-20

  - releaseCycle: "9"
    releaseDate: 2022-05-18
    eoas: 2027-05-31
    eol: 2032-05-31
    lts: 2032-05-31
    eoes: 2036-05-31
    latest: "9.8"
    latestReleaseDate: 2026-05-20

  - releaseCycle: "8"
    releaseDate: 2019-05-07
    eoas: 2024-05-31
    eol: 2029-05-31
    lts: 2029-05-31
    eoes: 2033-05-31
    latest: "8.10"
    latestReleaseDate: 2024-05-22

---

Description text removed from this test copy.
