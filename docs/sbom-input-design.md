# Design note: read an SBOM as an inventory input (#19)

Status: deferred by the maintainer. No code. The reader is not built. See
"Decision" below for what to do instead and what would reopen it.

## Decision

Defer the SBOM reader. An ITAM expert review found that SBOMs mostly come
from in-house build pipelines and from vendors on request, and that they sit
with security teams, not ITAM. Checking each component for end of life is
security work, and those users already have tools for it. Only 19 of 489
catalog products publish an SBOM as a GitHub release asset, and none is a
commercial vendor product.

Do instead:

1. Curated bundle facts: "product X version Y bundles component Z", each with
   a vendor source URL, a gold row and a test. These follow the existing
   `bundle_parents` rules in `AGENTS.md`.
2. Full purls in the generated data (decision 1 below), so a reader can use
   them later.

Reopen the reader if security users are brought into scope and ask for it.
The expert's review is unverified practitioner judgment, not a sourced
finding. A source is needed before any claim from it goes into user docs.

## What the review added to this note

- **Distro packages.** Debian and Red Hat keep supporting a package after
  upstream end of life. Reducing a `deb` or `rpm` version to the upstream
  version would flag supported packages as past end of life. A reader must
  not do that, or must label those rows.
- **One SBOM, many machines.** An SBOM describes one build, not where it is
  installed. It cannot be joined to inventory rows or counts.
- **Age and origin.** The report should show who wrote the SBOM and when.
- **Noise.** In-house root components will mostly report "parent not in this
  inventory".
- **Reason code.** Add a reason code for "matched by identifier" and bump
  `schema_version`, so users can see how each row matched (decision 3).
- **Formats.** CycloneDX first is fine. Vendors tend to supply SPDX, so do
  not rule it out.

## What the data allows

Counted in the endoflife.date product files at commit `eda9a80` (489
products):

| Identifier | Products | Notes |
| --- | --- | --- |
| package URL (purl) | 210 | 997 purls in all |
| CPE | 292 | |
| both | 136 | |

Most purls name a distribution or a repackager, not the owner: `github` 176,
`rpm` 171, `docker` 151, `deb` 83, `maven` 77, `oci` 56, `apk` 56. `npm` has
31 and `pypi` only 5. An SBOM from a Python project will mostly find nothing.

Two things follow:

- `data/products.json` keeps only the CPE vendors and the owner part of a
  purl (`docs/usage.md`, "What `products.json` reads"). It does not keep a
  full purl. Matching by identifier needs the type, namespace and name per
  product, so it needs new generated data.
- A name alone is not an identifier. Eight purl names are shared by several
  products, among them `core`, `base`, `server` and `v2`. A match must use the
  whole purl: type, namespace and name.

The figures in the issue (200 of 485 and 286) are out of date. They are now
210 of 489 and 292.

## Proposed approach

Turn each SBOM component into an inventory row, then use the existing
matching, classification and report steps. No second pipeline.

1. **Read.** CycloneDX JSON (`components[]`, with `purl` and `cpe`) and SPDX
   JSON (`packages[]`, with `externalRefs` of type purl or cpe23Type). Python
   standard library `json` only. Same size and row limits as `inputs.py`.
   Start with CycloneDX alone if one format is enough.
2. **Match, in this order.**
   1. Whole purl equals a purl of one product.
   2. CPE vendor and product both equal a CPE of one product.
   3. Nothing else. A component with no identifier match is "Not found", never
      a name guess.
3. **Version.** Use the purl version. For `deb` and `rpm`, drop the epoch
   and the distribution revision first (`1:3.0.11-1~deb12u2` becomes
   `3.0.11`). If that does not pick exactly one cycle, the row is
   "Unverified".
4. **Parent.** The SBOM's root component (CycloneDX `metadata.component`,
   SPDX `DESCRIBES`) becomes an item. Every other component names it as
   its parent. This reuses the 0.2.0 part-with-a-parent report. A root with
   no matched product already reports "parent not in this inventory".

## Rows to write before building (synthetic only)

- The same package name under two types (`pkg:npm/core` and `pkg:github/org/core`)
  must not cross-match.
- A purl with a known type but an unknown namespace is not matched.
- `pkg:maven/org.apache.tomcat/tomcat@9.0.80` matches Tomcat 9.0.
- A `deb` version with an epoch resolves to one cycle.
- A component with no purl and no CPE is "Not found".
- An SBOM with duplicate bom-refs, a loop in its dependency list, or a size
  over the limit stops with a clear message.

## Decisions needed

1. **Data.** Add full purls to the generated data (a new field in
   `products.json`, or a new file). This changes a data source and the
   refresh, so it is yours to decide.
2. **Skip the one-word vendor check?** I recommend yes, for a whole-purl or
   whole-CPE match only: the namespace already confirms the vendor. Never for
   a name alone.
3. **Report.** A new reason code for "matched by identifier" bumps
   `schema_version` (`docs/report-schema.md`). The alternative is to reuse an
   existing code and give up that visibility.
4. **Formats.** CycloneDX first, or both at once?
5. **Where SBOMs come from.** Not known. Worth asking an ITAM practitioner
   before building, as the issue says.

## Out of scope

Deprecated or archived package flags, as the issue says. Network lookups.
SBOM generation.

## Privacy

An SBOM lists what an organization runs, so it is as confidential as an
inventory. The same rules apply: counts only, no reading the report files.
Tests and examples use synthetic SBOMs only.

## If approved

One pull request for the data change and one for the reader with its tests.
The benchmark floor (`tests/benchmark/floor.json`) is not lowered, and the
new rows go in with the change that earns them.
