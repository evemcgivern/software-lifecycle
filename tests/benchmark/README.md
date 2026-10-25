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
2. `catalog`: not hand-written, and the exact name was seen in a fetched
   public catalog (winget, Debian or Ubuntu packages, Homebrew). A catalog
   row must carry a plausible real version for that package (a test checks
   that a number in a package name agrees with the version).
3. `generated`: everything else. Built by program from upstream titles and
   per-cycle latest versions, or generated traps.

Counts (product with a cycle, product with no cycle, `NONE`):

| stratum | cycle | none | NONE | total |
| --- | --- | --- | --- | --- |
| hand | 363 | 19 | 372 | 754 |
| catalog | 226 | 82 | 48 | 356 |
| generated | 830 | 191 | 29 | 1050 |
| all | 1419 | 292 | 449 | 2160 |

The research set marked 610 rows as seen in a catalog. About 254 of those are
also hand-written, so they count as `hand` and `catalog` holds 356.

## Held-out rows

`heldout` is `1` when the SHA-256 of `name|publisher|version`, read as a
number, is divisible by 10, for `hand` and `catalog` rows. `generated` rows
are always `0`. That is 105 rows. Do not use held-out rows when writing
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
  match. With the vendor's publisher it is.
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

Sources are in `SOURCES.md`.
