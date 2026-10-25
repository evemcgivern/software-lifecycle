"""Draw a stratified sample of the silver catalog for hand labelling.

Not part of the suite and never imported by it. The silver file (public
rows from winget, Homebrew, Debian and Ubuntu) is not in the repository; its
path comes from the SWLC_SILVER environment variable. No network.

    SWLC_SILVER=/path/to/silver.csv python3 tests/sample_silver.py OUT.csv 150

OUT.csv gets the header of tests/benchmark/silver-sample.csv with the label
columns empty. The silver file needs the headings source, name, publisher
and version.
"""
from __future__ import annotations

import csv
import hashlib
import os
import random
import sys
from pathlib import Path

SOURCES = ("winget", "homebrew", "debian", "ubuntu")
HEADER = ["source", "name", "publisher", "version", "label", "label_b",
          "agreed", "heldout", "notes"]


def heldout(name: str, publisher: str, version: str) -> str:
    """The gold rule: the digest of name|publisher|version, divisible by 10."""
    key = "%s|%s|%s" % (name, publisher, version)
    return "1" if int(hashlib.sha256(key.encode("utf-8")).hexdigest(),
                      16) % 10 == 0 else "0"


def draw(silver_csv: Path, per_source: int, seed: int = 20261025) -> list:
    """Up to per_source distinct rows from each source, chosen by a seeded
    shuffle, so the same file and seed always give the same sample."""
    by_source = {s: {} for s in SOURCES}
    with open(silver_csv, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            source = (row.get("source") or "").strip().lower()
            if source not in by_source:
                continue
            key = (row.get("name") or "", row.get("publisher") or "",
                   row.get("version") or "")
            if key[0].strip():
                by_source[source].setdefault(key, None)
    rng = random.Random(seed)
    sample = []
    for source in SOURCES:
        keys = sorted(by_source[source])
        rng.shuffle(keys)
        for name, publisher, version in keys[:per_source]:
            sample.append({"source": source, "name": name,
                           "publisher": publisher, "version": version})
    return sample


def main(argv: list) -> int:
    path = os.environ.get("SWLC_SILVER")
    if not path or len(argv) != 3:
        print("usage: SWLC_SILVER=silver.csv python3 tests/sample_silver.py "
              "OUT.csv PER_SOURCE", file=sys.stderr)
        return 2
    rows = draw(Path(path), int(argv[2]))
    with open(argv[1], "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(HEADER)
        for r in rows:
            writer.writerow([r["source"], r["name"], r["publisher"],
                             r["version"], "", "", "",
                             heldout(r["name"], r["publisher"],
                                     r["version"]), ""])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
