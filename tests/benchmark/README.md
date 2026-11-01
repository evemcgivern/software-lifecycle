# The gold benchmark

`gold.csv` is a list of made-up and public software names, each with the
answer the matcher should give. `tests/test_benchmark.py` runs the real
pipeline over every row against the bundled `data/` and scores it. Later
changes to the matcher are measured against this file.

No row comes from a real inventory. Never add one.

## Columns

| column | meaning |
| --- | --- |
| `name`, `publisher`, `version` | what an inventory export would hold |
| `expected_product` | an endoflife.date product id that exists in `data/eol/`, or `NONE` (not this product, or too ambiguous to name one) |
| `expected_cycle` | a cycle of that product; the word `none` (the product is right, but no cycle can be decided from the row); or empty (any cycle is fine, and always empty for `NONE`) |
| `notes` | why the row is here; every row has one |
| `stratum` | `hand`, `catalog` or `generated` (below) |
| `heldout` | `1` or `0` (below) |
| `classification` | empty (the row is not scored for classification), or `governable`, `component`, `bundle_member` or `unknown`, as defined in `docs/usage.md` |
| `expected_parent` | empty (no link is expected), `product:<id>/<cycle>` (the parent product and cycle, on `bundle_member` rows only), or `none` (no parent link may exist) |

### Classification columns

Rows that were in the file before the classification columns existed have both
columns empty and are not scored for classification. New rows carry a
`classification`. Each label is kept only where two independent reviewers who
did not see each other's labels agree; rows they disagree on go to
`unsure.csv` with a note. A person spot-checks a tenth of the kept rows. The
rows are public names only (winget, Homebrew, Debian and Ubuntu package names
and vendor product pages, cited in `SOURCES.md`). `expected_parent` is
`product:<id>/<cycle>` only where the name and version fit one cycle of one
product by themselves, for example `Microsoft Outlook 2019` is
`product:office/2019`. A row with a parent signal missing from its own name
(a runtime that might ship inside an app) is `unknown` or `governable`, not
`bundle_member`.

### Parent cases

`parents/` holds small inventories for the parent link, one pair of files per
case: `<case>.csv` (headings `Software Name,Publisher,Version,Parent`) and
`<case>.expected.json`. The JSON has `as_of` (the bundled `eol_date`),
`data` (`bundled`), `items` and `warnings_contain`. `items` maps
`name|publisher|version` to the expected `classification`, `parent_ref`
(`{"kind", "value"}` or null; `value` is the parent row key for `item` and
`os`, and `<product>/<cycle>` for `product`), `inherited_from` (the parent row
key, or null) and `inherited_state` (the parent row's state, or null).
`warnings_contain` lists text that must appear in the report warnings. The
cases are hand-designed tests of the parent rules, not gold rows.

### Silver sample

`silver-sample.csv` holds 2,391 public rows from the silver catalog (winget,
Homebrew, Debian, Ubuntu; 172,522 rows, built outside the repository and not
committed) with two independent labels, to measure classification rates per
source. Columns: `source`, `name`, `publisher`, `version`, `label` and
`label_b` (a class from each labeller), `agreed` (`1` if the labels match,
else `0`), `heldout` (the gold rule) and `notes`. `tests/sample_silver.py`
holds the held-out rule and a plain draw; the suite never imports it.

How the sample was made, plainly:

- It was drawn after the rule change that stopped a trailing Runtime or SDK
  from marking a component. Rows the tool labelled `component` were drawn
  per source (600 each for Debian and Ubuntu, all of them for Homebrew and
  winget), plus rows the tool labelled `governable`.
- The labellers are two AI models, not people: Sonnet wrote `label` and
  Haiku wrote `label_b`, each reading the rows itself, blind to the other
  and to the tool's answer. An earlier attempt that labelled rows with a
  script was thrown away. 59 rows have `agreed` = `0`; the person running
  the work read that list. The labels are left as the models gave them.
- 13 Homebrew rows were dropped because their names hold an at sign
  (versioned formulae), which no benchmark file may contain. No row hit the
  banned-term scan.
- A spot-check read 117 agreed rows (5%, a seeded shuffle) and found none
  plainly wrong; two (`liblouis-bin`, `libpurple-bin`, tool packages of a
  library) are arguable.
- After the sample was drawn, the `-dev` and `lib*` tool rules changed (a
  `*-dev` name needs a `lib` part or a digit; `lib*-cli`, `-tools` and the
  like are not libraries). Debian and Ubuntu Go and tool packages that the
  tool labelled `component` at drawing time are now `unknown`, so those two
  sources have fewer than 600 `component` rows and no rate is claimed for
  them.

The rates below hold for this catalog sample only. They say nothing about
any real estate, where the mix of rows is unknown. They are not coverage
figures.

### Silver sample rates

One row per source; rates are never pooled. The worst error is a row the
tool labels `component` while either labeller says `governable`, over all
rows the tool labels `component` (agreed or not, held-out rows included).
Precision is agreed `component` labels over agreed rows the tool labels
`component`. A rate is claimed only where at least 600 rows the tool labels
`component` stand behind it; the claim is a worst-error rate under 0.5% and
a precision of at least 98%. `bundle_member` is counted only: the sample has
almost none.

| source | tool says component | worst errors | worst-error rate | component precision | held-out worst / n |
| --- | --- | --- | --- | --- | --- |
| winget | 187 | 2 | not claimed (n under 600) | not claimed (178 of 180 agreed) | 0 / 19 |
| homebrew | 629 | 0 | 0.00% (0 of 629) | 100% (623 of 623) | 0 / 68 |
| debian | 557 | 1 | not claimed (n under 600) | not claimed (554 of 554 agreed) | 0 / 64 |
| ubuntu | 556 | 0 | not claimed (n under 600) | not claimed (553 of 553 agreed) | 0 / 71 |

`silver_correct_min` in `floor.json` is the count of agreed rows where the
tool's class equals the label.

### Product, no cycle

`expected_cycle` = `none` is for a row whose name clearly names the product
but whose version cannot pick a cycle. Rule applied when relabeling:

- the version fits no cycle in the snapshot (too old, too new);
- the name and the version column disagree and the name clearly names the
  product (for example `Python 3.15.1` with version `2.6.9`);
- the build is shared by several cycles (Office build `16.0`, Windows
  Server 2003 build 5.2.3790, a bare `Windows Server` with build 17763);
- the name is a year that several point releases share (Azure DevOps
  Server 2022).

A build that does decide the cycle is decided: SQL Server service-pack builds
(`10.50.6000.34` is `10.50-sp3`, `9.00.5000.00` is `9.0-sp4`) and Windows
Server 2008 R2 build 6.1.7601 (`2008-r2-sp1`). A row stays `NONE` when the
right answer is truly "not this product" (components, look-alikes, devices,
absent products, bare generic words) or the name fits several products.

## Strata

Each row gets the first rule that fits:

1. `hand`: written by hand. The hand-written positives, the hand-written
   traps (absent products, components, look-alikes, devices, bare generic
   names, vendor clashes, ambiguous builds, Mac rows, name and version
   conflicts, versions with no cycle), and the rows added by hand later.
2. `catalog`: not hand-written, and the name was seen in a fetched public
   catalog (winget, Debian or Ubuntu packages, Homebrew). Most catalog rows
   carry a plausible real version for that package (a test checks that a
   number in a package name agrees with the version). 78 do not: they are
   constructed traps that pair a catalog name with an invented version, to
   test that no cycle is guessed. 60 have notes starting `trap=nocycle` (a
   version that fits no cycle, such as `SQLite 10.0.0`), and 18 start
   `trap=conflict` (the name and the version column disagree, such as
   `MySQL 26.7.0` with version `5.5.63`). 37 of the 78 carry the invented
   version in the name itself, so that name is not the catalog's. All 78
   expect the product with no cycle, and 69 of them are scored correct and
   count toward the hand and catalog floor. The other 278 catalog rows (226
   expecting a cycle, 4 expecting any cycle, 48 expecting `NONE`) carry no
   invented-version trap; the 4 were `trap=nocycle` rows until upstream
   added their cycles (issue #74, under "Judgment calls built into gold").
3. `generated`: everything else. Built by program from upstream titles and
   per-cycle latest versions, or generated traps.

Counts (product with a cycle or any cycle, product with no cycle, `NONE`):

| stratum | cycle | none | NONE | total |
| --- | --- | --- | --- | --- |
| hand | 642 | 92 | 944 | 1678 |
| catalog | 230 | 78 | 48 | 356 |
| generated | 828 | 193 | 29 | 1050 |
| all | 1700 | 363 | 1021 | 3084 |

The research set marked 610 rows as seen in a catalog. About 254 of those are
also hand-written, so they count as `hand` and `catalog` holds 356.

## Held-out rows

`heldout` is `1` when the SHA-256 of `name|publisher|version`, read as a
number, is divisible by 10, for `hand` and `catalog` rows. `generated` rows
are always `0`. That is 199 rows. Do not use held-out rows when writing
exclusions, aliases or rules. The test reports them separately.

## What the test checks

- Outcome per row: `correct`; `hard-wrong` (the item carries a cycle, so a
  lifecycle claim, that is wrong for the row, or any cycle where gold says
  `NONE` or `none`); `soft-wrong` (a product but no cycle, so state
  unmatched, and the product is wrong or gold says `NONE`: no date claim,
  but it names a wrong product in the report); `missed` (gold has a
  product, the matcher gave none, or no cycle where gold names one); and
  `right-none`. For `none` rows the right product with no cycle is correct.
- A wrong match is a bug in the rule. Hard wrong must be zero. Soft wrong
  may only go down: it may not exceed `soft_wrong_max` in `floor.json`
  (target 0; lowering it is a deliberate hand edit). Known hard-wrong rows
  are listed in `KNOWN_WRONG` in `tests/test_benchmark.py`, each with its
  cause and the exact wrong answer it gives today, and run as expected
  failures. A listed row that stops being wrong, or changes to a different
  answer, fails its test until the entry is updated; a new hard-wrong row
  fails too.
- The count of `correct` rows in `hand` plus `catalog` must be at least
  `hand_catalog_correct_min` in `floor.json`. Raise it by hand in the commit
  that earns the gain. Never lower it.
- The count of `correct` rows in `generated` must be at least
  `generated_correct_min` in `floor.json`. The same rule: raise it by hand
  in the commit that earns the gain, never lower it. This check gates every
  pull request and local run. The weekly data job sets `SWLC_WEEKLY_JOB`
  and only reports it, because an upstream rename changes generated rows
  (see "Maintainer: when the weekly data job fails" in `docs/sop.md`).
- Classification scoring. A gold row with a `classification` is correct when
  the predicted class matches and, for a named parent, the parent product and
  cycle match. The count must be at least `classification_correct_min`.
  `governable_as_part_max` caps rows whose gold class is `governable` but
  that the tool calls `component` or `bundle_member` (target 0). Component
  and bundle member precision on the gold rows must stay at 0.98 or above.
  `wrong_parent_max` caps rows that get a parent link the gold row does not
  expect, including any link where `expected_parent` is `none` (target 0).
- Parent cases. Every item in `parents/` must match its expected file; the
  count must be at least `parent_cases_correct_min`. These are
  hand-designed tests of the parent rules, not a rate for any real estate.
- Floor lowerings: the floor is lowered only by a decision the maintainer
  records here, with the rows it loses.
  - 2026-10-25, removing the `red hat` publisher alias for `ansible`. The
    Red Hat VS Code extension named Ansible matched Ansible through it.
    `hand_catalog_correct_min` 421 to 418 and `generated_correct_min` 723
    to 718. Rows lost (now missed): `Ansible|Red Hat|9.1.0` (hand),
    `Ansible|Red Hat|14.5.0` and `Ansible|Red Hat|1.0.1` (catalog),
    `Ansible 7.7.0|Red Hat|7.7.0`, `Red Hat Ansible|Red Hat|7.7.0`,
    `Ansible (x64)|Red Hat|14.5.0`, `Ansible 21.0.0|Red Hat|21.0.0` and
    `Ansible 14.5.0|Red Hat|2.9.27` (generated).
  - 2026-10-25, excluding Moodle by name and publisher. The Moodle mobile
    app and the Moodle LMS share the name `Moodle` and the publisher
    `Moodle Pty Ltd`, so LMS rows could be the app. `hand_catalog_correct_min`
    418 to 417 and `generated_correct_min` 718 to 713. Rows lost (now
    missed): `Moodle|Moodle Pty Ltd|4.1.7` (hand), `Moodle|Moodle Pty Ltd|5.3.0`,
    `Moodle 4.2.11|Moodle Pty Ltd|4.2.11`, `Moodle|Moodle Pty Ltd|2.0.1`,
    `Moodle 12.0.0|Moodle Pty Ltd|12.0.0` and
    `Moodle 5.3.0|Moodle Pty Ltd|3.8.9` (generated).
  - 2026-10-26, issue #11 review, with the owner's approval. The
    `mastodon ggmbh` publisher alias was dropped, because Mastodon gGmbH
    also publishes the Mastodon mobile app, whose 2.x versions fit a
    server cycle. nginx, CKEditor, JHipster, jQuery, Magento, Matomo,
    Mautic, Oniguruma and PrivateBin left the version-in-name list,
    because a same-named PyPI, npm or RubyGems package from someone else
    has versions that fit a cycle. `hand_catalog_correct_min` 484 to 482
    and `generated_correct_min` 867 to 857. Rows lost (now missed):
    `nginx 1.24.0||1.24.0` and `Matomo 5.1.2||5.1.2` (hand),
    `Mastodon|Mastodon gGmbH|4.7.3`, `Mastodon 3.5.19|Mastodon gGmbH|3.5.19`,
    `CKEditor 4.25.2||4.25.2`, `JHipster 4.14.5||4.14.5`,
    `jQuery 2.2.4||2.2.4`, `Magento 2.1.18||2.1.18`,
    `Matomo 3.14.1||3.14.1`, `Mautic 4.2.2||4.2.2`,
    `Oniguruma 5.9.6||5.9.6` and `PrivateBin 1.4.0||1.4.0` (generated).
  - 2026-10-26, issue #11 second review, with the owner's approval.
    ESLint, MySQL, PostgreSQL, Quarkus, Knative, Vuetify, Deno, AngularJS
    and YouTrack left the version-in-name list, because a VS Code or
    JetBrains extension with the same name has versions that fit a cycle
    (`ESLint 3.0.34` is the VS Code ESLint extension). Kubernetes no
    longer takes a `-gke.` or `-eks-` build (no gold row changed).
    `generated_correct_min` 857 to 851; `hand_catalog_correct_min`
    unchanged. Rows lost (now missed, all generated):
    `AngularJS 1.4.14||1.4.14`, `ESLint 5.16.0||5.16.0`,
    `Knative 1.4.0||1.4.0`, `Quarkus 3.10.2||3.10.2`,
    `Vuetify 2.7.2||2.7.2` and `YouTrack 2022.2.65377||2022.2.65377`.
- Every product id and cycle exists in `data/eol/`. No two rows share an
  item id (names are normalized as the tool does). Rows in `unsure.csv` are
  not in gold.
- The benchmark files pass the banned-term scan and hold no email address.

See the numbers with `SWLC_BENCH_REPORT=1 python3 -B -m unittest discover -s tests -p 'test_benchmark.py'`.

## Add a row

1. Write a synthetic or public-catalog name. Never copy from an inventory.
2. Pick the stratum: `hand` if you wrote it, `catalog` if you saw the exact
   name in a public catalog, never `generated` by hand.
3. Compute `heldout` from the rule above (the test checks it).
4. Use `NONE` with an empty cycle for "not this product". Use a product id
   from `data/eol/` with a cycle from that file, or with `none`.
5. Put the reason and the source in `notes`.
6. If you are unsure of the answer, or the answer is defensible either way,
   leave the row out and list it in `unsure.csv` with a note. Borderline
   rows do not belong in a zero-wrong benchmark.
7. Never change a row so that a rule passes. A wrong match is a bug in the
   rule: hard wrong must be zero, soft wrong may only go down.

## Judgment calls built into gold

- A bare common word with no publisher (Salt, Go, Harbor, Express) is not a
  match. With the vendor's publisher it is. The same holds with a version in
  the name (`Go 1.21.5`, `Salt 3006.5` with no publisher): the
  version-in-name rule matches only coined one-word titles (`Kibana
  8.15.3`), never ordinary words, common names or names another product
  shares (`Quasar 1.4.1` is also a remote administration tool, Rocket.Chat
  has a desktop app). Exclusions still win (`Moodle 4.4.0` with no
  publisher is `NONE`).
- Clients, drivers, SDKs, add-ins and language packs are not the product.
  An agent or command-line row counts as the product only if it ships with
  the server at the same version and support dates (istioctl, Puppet Agent,
  Salt Minion, Keycloak Admin CLI count; MySQL
  Shell and Router, Elastic and Grafana agents, Python Launcher do not).
  SQLite and OpenSSL libraries count. The .NET runtime, desktop runtime,
  ASP.NET Core and SDK count as .NET.
- Debian and Ubuntu builds of upstream software (nginx, postgresql-15,
  docker.io) are the upstream product. Debian OpenJDK is `NONE`, because the
  snapshot only has vendor builds. A bare OpenJDK name with no publisher is
  `NONE`, including `java-1.6.0-openjdk`. A bare `graalvm` package is `NONE`
  (Community or Oracle).
- Java 8 runtime ("Java 8 Update 391") is `oracle-jdk` 8.
- Office 2019 with build 10399 is `office` 2019 (a 2019 volume-licensed
  build). Office with the shared build `16.0` is `office` with cycle `none`.
- Rows whose answer is defensible either way or rests on an unverified fact
  (Harbor with the VMware publisher, Elastic Agent, `Microsoft .NET` 4.8,
  .NET Framework 4.8.1 with build 4.8.09032, Oracle Solaris 11.4 with an
  unconfirmed build, Splunk UniversalForwarder, Windows 11 LTSC 2024 with
  build 26100.1742, Windows Server Core 2022 by build, Azure DevOps Server
  2022 by build) are in `unsure.csv`, not gold. A test compares normalized
  names (leading "Microsoft " dropped), publishers and versions so a
  near-duplicate cannot sit in both files.
- Rows added by hand with mixed-granularity cycles (Jenkins, Tomcat, Docker
  Engine and others) have notes that start with "hand-added".
- Issue #17 added 56 hand rows for the Microsoft edition and OS
  release-name aliases (notes start "hand-added (issue #17)"): 46 traps
  (look-alikes, tools, language packs, Mac editions, a name and a build
  that disagree, a build no cycle claims, kernel versions in an OS row,
  .NET Core SDK 2.1 builds that ship the 2.0 runtime), 9 positives and 1
  probe. Every
  row with a public page cites it; the language-pack rows use made-up
  names. Three are held out. The hand and
  catalog floor rose from 482 to 549 and the classification floor from
  294 to 297 in the same change. Windows 11 Enterprise LTSC 2024 with build
  26100.2314 is in gold as a row that must stay unmatched by the
  Enterprise aliases; the build 26100.1742 row stays in `unsure.csv`.
- Issue #20 added 257 hand rows for PowerShell 7, Red Hat Enterprise
  Linux, Rocky Linux, AlmaLinux and Oracle Linux release names and
  Exchange "Cumulative Update N" names (notes start "hand-added (issue
  #20)"): 176 expect a cycle, 32 the product with no cycle (a name and a
  version column that disagree, an empty or out-of-map version) and 49
  `NONE` (a codename that belongs to another release, modules, tools,
  documentation and release packages, language packs, update packages).
  15 of the rows that expect a cycle stay missed on purpose: names with
  a blank publisher, the `release` file form, the version-in-name
  PowerShell MSI form, the winget name `PowerShell`, RHEL 10, Rocky 10
  and Rocky 9.8. 32 are held out. Rows whose answer is defensible either
  way were left out: a real name with a made-up publisher, a real name
  with an extra word, previews, betas and RHEL variants. Internet
  Explorer rows wait for issue #21. The hand and catalog floor rose from
  549 to 751 and the classification floor from 297 to 299 in the same
  change.
- Issue #74, the maintainer's decision (2026-11-01): four catalog
  `trap=nocycle` rows, `LibreOffice|The Document Foundation|6.0.1`,
  `MySQL|Oracle Corporation|4.0.1`, `Notepad++|Notepad++ Team|6.0.1` and
  `PHP|The PHP Group|4.0.1`, were relabelled from cycle `none` to an
  empty cycle (the product, any cycle). The data changed, not the rule:
  upstream endoflife.date (commit 38b1896e) added the old cycles
  LibreOffice 6.0, MySQL 4.0, Notepad++ 6.0 and PHP 4.0, so these
  versions now fit a real cycle and the weekly job scored them hard
  wrong (hand and catalog 754 against the floor of 758). The exact new
  cycle would fail on the bundled data, which lacks those cycles; an
  empty cycle is correct on both. Once the weekly data is merged, each
  row can be tightened to its exact cycle. The hand and catalog count
  stays 758; no floor changed.

Sources are in `SOURCES.md`.
