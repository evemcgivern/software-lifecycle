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
- https://marketplace.visualstudio.com/items?itemName=redhat.ansible (the Red Hat VS Code extension named Ansible; its versions read from the Marketplace gallery API)
- https://github.com/quasar/Quasar/releases/tag/v1.4.1 (Quasar 1.4.1, a remote administration tool that shares the Quasar framework's name)
- https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.5%2B11 (Temurin 21.0.5+11 release)
- https://github.com/jetty/jetty.project/releases/tag/jetty-9.4.56.v20240826 (Jetty 9.4.56.v20240826 release)
- https://cloud.google.com/kubernetes-engine/docs/release-notes (GKE version strings such as 1.30.5-gke.1014001)
- https://github.com/ibmruntimes/semeru21-binaries/releases/tag/jdk-21.0.5%2B11_openj9-0.48.0 (IBM Semeru Runtime 21.0.5+11 release)
- https://pypi.org/project/podman/ (the PyPI podman package (Python bindings for the Podman API) has a 5.4.0 release)
- https://pypi.org/project/redis/ (the PyPI redis client (also npm and RubyGems clients named redis) has a 5.0.1 release)
- https://pypi.org/project/elasticsearch/ (the PyPI elasticsearch client has a 7.17.9 release)
- https://pypi.org/project/neo4j/ (the PyPI neo4j driver has a 5.20.0 release)
- https://pypi.org/project/dapr/ (the PyPI dapr package (the Dapr Python SDK) has a 1.14.0 release)
- https://pypi.org/project/opensearch-py/ (the OpenSearch Python client opensearch-py has a 2.4.0 release)
- https://www.npmjs.com/package/bitbucket (the npm bitbucket package (an API client) has a 2.12.0 release)
- https://www.npmjs.com/package/cockroachdb (the npm cockroachdb package (a client) has a 1.0.3 release)
- https://pypi.org/project/containerd/ (the PyPI containerd package (a Python API client) has a 1.5.3 release)
- https://rubygems.org/gems/duckdb (the duckdb gem (Ruby bindings) has a 1.0.0.0 release)
- https://pypi.org/project/ffmpeg/ (the PyPI ffmpeg package (a wrapper) has a 1.2.1 release)
- https://pypi.org/project/foundationdb/ (the PyPI foundationdb package (Python bindings) has a 7.3.9 release)
- https://www.npmjs.com/package/gitlab (the npm gitlab package (an API client) has a 14.2.2 release)
- https://www.npmjs.com/package/gradle (the npm gradle package (unrelated to Gradle) has a 1.2.4 release)
- https://pypi.org/project/graylog/ (the PyPI graylog package has a 1.0.0 release)
- https://pypi.org/project/influxdb/ (the PyPI influxdb client has a 3.0.0 release)
- https://rubygems.org/gems/memcached (the memcached gem (a libmemcached client) has a 1.4.1 release)
- https://rubygems.org/gems/openssl (the openssl gem (Ruby's OpenSSL binding) has a 3.0.0 release)
- https://www.npmjs.com/package/sqlite (the npm sqlite package (a Node.js client) has a 3.0.6 release)
- https://www.npmjs.com/package/wireshark (the npm wireshark package has a 1.0.2 release)
- https://pypi.org/project/wordpress/ (the PyPI wordpress package (a REST API client) has a 1.2 release)
- https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint (the VS Code ESLint extension; release 3.0.34)
- https://marketplace.visualstudio.com/items?itemName=cweijan.vscode-mysql-client2 (a VS Code extension named MySQL; release 9.0.2)
- https://marketplace.visualstudio.com/items?itemName=cweijan.vscode-postgresql-client2 (a VS Code extension named PostgreSQL; release 9.0.2)
- https://marketplace.visualstudio.com/items?itemName=redhat.vscode-quarkus (the VS Code Quarkus extension; release 1.24.2026082508)
- https://marketplace.visualstudio.com/items?itemName=redhat.vscode-knative (the VS Code Knative extension; release 1.5.0)
- https://marketplace.visualstudio.com/items?itemName=vuetifyjs.vuetify-vscode (the VS Code Vuetify extension; release 1.0.2)
- https://marketplace.visualstudio.com/items?itemName=denoland.vscode-deno (the VS Code Deno extension; 1.x to 3.x releases)
- https://pypi.org/project/podman/5.4.0/ (the PyPI podman package, Python bindings for the Podman API)
- https://github.com/microsoft/winget-pkgs/blob/master/manifests/r/RedHat/Podman/5.8.3/RedHat.Podman.locale.en-US.yaml (winget gives Podman's publisher as Red Hat)
- Issue #17 rows (Microsoft edition names and OS release names; names and
  build numbers only, no dates), each page fetched on 2026-10-27:
  - https://endoflife.date/windows (Windows 7 SP1 6.1.7601, 8.1 6.3.9600,
    10 LTSB 2015 10.0.10240, the 10 21H2 IoT LTS row; (W) and (E) edition
    groups)
  - https://learn.microsoft.com/en-us/windows-server/get-started/kms-client-activation-keys
    (Windows 11, 10, 8.1, 7 and Server 2008 R2 edition names, IoT
    Enterprise LTSC 2021)
  - https://learn.microsoft.com/en-us/windows-server/get-started/upgrade-conversion-options
    (Windows Server evaluation editions)
  - https://learn.microsoft.com/en-us/security-updates/securitybulletins/2006/ms06-015
    (Windows Server 2003 and 2003 R2 edition names)
  - https://www.microsoft.com/en-us/software-download/windows11 (Windows 11
    Installation Assistant)
  - https://learn.microsoft.com/en-us/windows-server/administration/windows-server-update-services/get-started/windows-server-update-services-wsus
    (WSUS is a server role)
  - https://learn.microsoft.com/en-us/sql/database-engine/configure-windows/sql-server-express-localdb
    (LocalDB is a feature of SQL Server Express)
  - https://learn.microsoft.com/en-us/sql/reporting-services/install-windows/install-reporting-services
    (Reporting Services has its own installer)
  - https://learn.microsoft.com/en-us/sql/relational-databases/native-client/sql-server-native-client
    (Native Client is the ODBC and OLE DB drivers)
  - https://learn.microsoft.com/en-us/exchange/plan-and-deploy/post-installation-tasks/install-management-tools
    (Exchange management tools install on other computers)
  - https://learn.microsoft.com/en-us/officeupdates/sharepoint-updates
    (SharePoint 2013 builds 15.0; 2016, 2019, Subscription Edition 16.0)
  - https://learn.microsoft.com/en-us/office/ltsc/2024/overview (Office LTSC
    Professional Plus 2024, Office LTSC Standard 2024, Office LTSC Standard
    for Mac 2024; major version 16.0)
  - https://learn.microsoft.com/en-us/security-updates/securitybulletins/2013/ms13-026
    (Office for Mac 2011 updates are 14.x)
  - https://code.visualstudio.com/updates/v1_95 (Visual Studio Code 1.95.3)
  - https://learn.microsoft.com/en-us/visualstudio/releases/2019/system-requirements
    (Visual Studio Community, Professional and Enterprise 2019; Build Tools
    2019)
  - https://learn.microsoft.com/en-us/visualstudio/releases/2022/system-requirements
    (Visual Studio Community, Professional and Enterprise 2022)
  - https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-history
    (Visual Studio 2022 is 17.0 to 17.14)
  - https://learn.microsoft.com/en-us/previous-versions/visualstudio/mac/releasenotes/vs2019-mac-relnotes
    (Visual Studio 2019 for Mac 8.10.25)
  - https://dotnet.microsoft.com/en-us/download/dotnet-framework/net481
    (.NET Framework 4.8.1 Runtime)
  - https://www.freedesktop.org/software/systemd/man/latest/os-release.html
    (os-release NAME "Debian GNU/Linux")
  - https://support.apple.com/en-us/109033 (macOS names and numbers,
    Sierra 10.12 to Tahoe 26)
  - https://support.apple.com/en-us/102662 (the macOS installer is named
    "Install" plus the version name)
  - https://ubuntu.com/download/server (Ubuntu Server naming, "24.04.5
    LTS")
  - https://github.com/dotnet/core/blob/main/release-notes/2.0/releases.json
    (.NET Core SDK 2.1.4, 2.1.100 and 2.1.202 belong to the 2.0 release line)
  - https://packages.debian.org/bullseye/linux-image-amd64,
    https://packages.debian.org/bookworm/linux-image-amd64 and
    https://packages.debian.org/trixie/linux-image-amd64 (Debian kernel
    versions 5.10, 6.1 and 6.12)
  - https://endoflife.date/sles (SLES service packs: 15 SP5 is 15.5)
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
- Classification rows (columns `classification`, `expected_parent`): public
  names only, from the winget, Homebrew, Debian and Ubuntu catalogs above and
  the vendor naming pages above (VC++ redistributable, Office, Windows
  update and .NET runtime names). Labels come from two independent reviewers
  and are kept only where both agree. The parent cases in `parents/` are
  hand-designed from the same naming pages, with made-up names for
  vendor-neutral cases. The silver sample is drawn from the same public
  catalogs.
