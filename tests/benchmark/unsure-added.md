# Rows left out on purpose

The 14 rows in the research set that could not be decided were never
imported. The rows below were considered for the added Jenkins and Windows
Server cases and also left out, because the snapshot does not settle them.

## Jenkins

`data/eol/jenkins.json` has cycle `2` (the weekly line, not end of life)
and cycles such as `2.426` and `2.555` (long-term support lines). Gold
includes only versions that name a line: `2.426.3` is a patch release of
line `2.426`.

- `Jenkins 2.430` (a weekly release between the lines `2.426` and `2.440`):
  cycle `2` is defensible as the weekly line, but the snapshot gives no rule
  for which cycle owns a weekly build. Not added.
- `Jenkins 2.571` (newer than the newest listed line `2.568`): same
  question. Not added.

## Windows Server

`Windows Server 2019 Standard` with build `10.0.17763` is in gold with cycle
`2019`. The name decides, because build 17763 is shared with the cycle
`1809-sac`. A row with the bare name `Windows Server` and that build is a
trap in gold (expected NONE).
