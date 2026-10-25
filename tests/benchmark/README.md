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
| `expected_product` | an endoflife.date product id that exists in `data/eol/`, or `NONE` |
| `expected_cycle` | a cycle of that product, or empty when any cycle (or none) is fine; empty for `NONE` |
| `notes` | why the row is here; every row has one |
| `stratum` | `hand`, `catalog` or `generated` (below) |
| `heldout` | `1` or `0` (below) |

## Strata

Each row gets the first rule that fits:

1. `hand`: written by hand. The 331 hand-written positives, the hand-written
   traps (absent products, components, look-alikes, devices, bare generic
   names, vendor clashes, ambiguous builds, Mac rows, name and version
   conflicts, versions with no cycle), and the rows added in this commit.
2. `catalog`: not hand-written, and the exact name was seen in a fetched
   public catalog (winget, Debian or Ubuntu packages, Homebrew).
3. `generated`: everything else. Built by program from upstream titles and
   per-cycle latest versions, or generated traps.

Counts (positives with a product, rows expecting `NONE`):

| stratum | positives | NONE | total |
| --- | --- | --- | --- |
| hand | 348 | 392 | 740 |
| catalog | 228 | 128 | 356 |
| generated | 832 | 218 | 1050 |
| all | 1408 | 738 | 2146 |

The research set marked 610 rows as seen in a catalog. 254 of those are also
hand-written, so they count as `hand` here and `catalog` holds 356.

## Held-out rows

`heldout` is `1` when the SHA-256 of `name|publisher|version`, read as a
number, is divisible by 10, for `hand` and `catalog` rows. `generated` rows
are always `0`. That is 104 rows. Do not use held-out rows when writing
exclusions, aliases or rules. The test reports them separately.

## What the test checks

- Outcome per row: `correct`, `wrong` (a product or cycle that contradicts
  gold, or any product where gold says `NONE`), `missed` (gold has a
  product, the matcher gave none, or no cycle where gold names one) and
  `right-none`.
- `wrong` must be zero on every stratum. Known exceptions are listed in
  `KNOWN_WRONG` in `tests/test_benchmark.py`, each with its alias and cause,
  and run as expected failures.
- The count of `correct` rows in `hand` plus `catalog` must be at least
  `floor.json`. Raise it by hand in the commit that earns the gain. Never
  lower it.
- Every product id and cycle exists in `data/eol/`.
- The benchmark files pass the banned-term scan and hold no email address.

See the numbers with `SWLC_BENCH_REPORT=1 python3 -B -m unittest discover -s tests -p 'test_benchmark.py'`.

## Add a row

1. Write a synthetic or public-catalog name. Never copy from an inventory.
2. Pick the stratum: `hand` if you wrote it, `catalog` if you saw the exact
   name in a public catalog, never `generated` by hand.
3. Compute `heldout` from the rule above (the test checks it).
4. Use `NONE` with an empty cycle for a trap. Otherwise use an id from
   `data/eol/` and, when the cycle matters, a cycle from that file.
5. Put the reason and the source in `notes`.
6. If you are unsure of the answer, leave the row out and list it in
   `unsure-added.md`.
7. Never change a row so that a rule passes. A wrong match is a bug in the
   rule.

## Judgment calls built into gold

- A bare common word with no publisher (Salt, Go, Harbor, Express) is not a
  match. With the vendor's publisher it is.
- Clients, drivers, SDKs, add-ins and language packs are not the product.
  The agent and command-line rows of a server product count as the product.
  SQLite and OpenSSL libraries count. The .NET runtime, desktop runtime,
  ASP.NET Core and SDK count as .NET.
- Debian and Ubuntu builds of upstream software (nginx, postgresql-15,
  docker.io) are the upstream product. Debian OpenJDK is `NONE`, because the
  snapshot only has vendor builds.
- Java 8 runtime ("Java 8 Update 391") is `oracle-jdk` 8.
- Office 2019 with build 16.0 is `NONE`: 16.0 is shared by several Office
  cycles, so the version cannot decide.
- `Microsoft .NET Framework 4.8.1` with build 4.8.09032 comes from community
  knowledge. Its note says Unverified.
- Rows added by hand with mixed-granularity cycles (Jenkins, Tomcat, Docker
  Engine and others) have notes that start with "hand-added".

Sources are in `SOURCES.md`.
