# Sources

## Fetched catalogs and data (whole-file downloads)

- https://api.github.com/repos/endoflife-date/endoflife.date/tarball/7cfb122846893f10ee819ab47b615eff261945d0 (via `gh api`; all 485 `products/*.md` parsed; MIT)
- https://cdn.winget.microsoft.com/cache/source.msix (winget community index; 186,552 manifests, 15,776 packages; repo github.com/microsoft/winget-pkgs is MIT)
- https://cdn.winget.microsoft.com/cache/source2.msix (v2 index; schema checked, not used)
- https://formulae.brew.sh/api/formula.json and https://formulae.brew.sh/api/cask.json
- https://formulae.brew.sh/api/analytics/install/365d.json and https://formulae.brew.sh/api/analytics/cask-install/365d.json
- https://deb.debian.org/debian/dists/bookworm/main/binary-amd64/Packages.xz
- http://archive.ubuntu.com/ubuntu/dists/noble/main/binary-amd64/Packages.xz
- http://archive.ubuntu.com/ubuntu/dists/noble/universe/binary-amd64/Packages.xz
- https://popcon.debian.org/by_inst.gz
- https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json (fetched; not used: no versions)
- https://repology.org/api (terms read: 1 request/s, bulk use discouraged, use the dump; Repology was not bulk-queried)

## Fetched vendor and project pages (name styles, build numbers)

- https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist (VC++ redistributable names and 14.x/12.0.40664/10.0.40219 versions)
- https://learn.microsoft.com/en-us/dotnet/framework/migration-guide/how-to-determine-which-versions-are-installed (.NET Framework versions; Programs and Features)
- https://learn.microsoft.com/en-us/dotnet/core/install/how-to-detect-installed-versions (.NET runtime and SDK naming)
- https://support.microsoft.com/servicing/sql/kb321185-download-and-install-latest-updates (SQL Server 2012-2025 = 11.0-17.0, RTM builds)
- https://learn.microsoft.com/en-us/windows/release-health/release-information (Windows 10 builds incl. LTSC 2019/2021, LTSB 2016)
- https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information (Windows 11 builds)
- https://learn.microsoft.com/en-us/microsoft-365-apps/deploy/install-different-office-visio-and-project-versions-on-the-same-computer (Office 2016-2024 and Microsoft 365 all 16.0)
- https://learn.microsoft.com/en-us/exchange/new-features/build-numbers-and-release-dates (Exchange 15.0/15.1/15.2 builds)
- https://www.java.com/en/download/help/version_manual.html ("Java 8 Update N" in Programs and Features)
- https://docs.python.org/3/using/windows.html (Python launcher, installer features: docs, pip, Tcl/Tk, test suite)
- https://www.postgresql.org/download/windows/ (EDB installer: server, pgAdmin, StackBuilder)
- https://packages.debian.org/bookworm/postgresql-15 (Debian package version and maintainer style)
- Repo files read (not fetched): data/aliases.json sources, tests/corpus_versions.csv sources.
- Not reached / not used: NVD CPE dictionary (API rate limit 5 requests per 30 s without a key; the 1.3M-entry dictionary needs hundreds of paged calls; skipped). npm top packages (skipped: not easy without a third-party list).

## Pages cited in row notes

- https://learn.microsoft.com/en-us/officeupdates/update-history-office-2019 (Office 2019 volume-licensed builds)
- https://learn.microsoft.com/en-us/windows/release-health/windows-server-release-info (Windows Server builds)
- https://support.microsoft.com/en-us/servicing/sql/kb321185-download-and-install-latest-updates (the same SQL Server build page as above)
- https://www.graalvm.org/release-calendar/ (GraalVM calendar-year and JDK-based version numbers)
- endoflife.date product pages: https://endoflife.date/android,
  https://endoflife.date/centos-stream, https://endoflife.date/cockroachdb,
  https://endoflife.date/commvault, https://endoflife.date/django,
  https://endoflife.date/docker-engine, https://endoflife.date/firefox,
  https://endoflife.date/ios, https://endoflife.date/ipados,
  https://endoflife.date/jquery, https://endoflife.date/nodejs,
  https://endoflife.date/nutanix-prism, https://endoflife.date/react,
  https://endoflife.date/ruby, https://endoflife.date/splunk,
  https://endoflife.date/spring-boot, https://endoflife.date/spring-framework,
  https://endoflife.date/tomcat and https://endoflife.date/windows-server

## Where each row came from

- Positive rows for a product and its cycles: the product's file at
  `https://github.com/endoflife-date/endoflife.date/blob/7cfb122846893f10ee819ab47b615eff261945d0/products/PRODUCT.md`, where PRODUCT is the `expected_product` id. Gold rows cover 447 of the 485
  product files.
- Hand-written rows (stratum `hand`): written from the vendor naming pages
  above (Programs and Features names, installer names, operating system
  release names, Debian and Red Hat package names, device-management rows).
  The traps are written by hand to look like a product and not be one.
- Catalog rows (stratum `catalog`): the exact name was found in one of the
  fetched catalogs (winget, Debian or Ubuntu packages, Homebrew). About 120
  of them matched the catalog only after dropping punctuation. 82 of them
  are constructed traps with invented versions (notes `trap=nocycle` and
  `trap=conflict`); see the README.
- Generated rows (stratum `generated`): built by program from the upstream
  title, the per-cycle latest version, a package name, a vendor plus title,
  or an architecture suffix. Generated traps use versions that fit no cycle,
  a name and a version that disagree, bare one-word names with no publisher,
  and Debian documentation packages.
- Rows added by hand (Jenkins lines, Office builds, Windows Server 2019,
  mixed-cycle products, device-management, framework and database rows) are
  written from `data/eol/` in this repository and the public page named in
  each row note. Their notes start with "hand-added".
- Rows that could not be settled are in `unsure.csv`, not in gold.
- No row comes from a real inventory.
