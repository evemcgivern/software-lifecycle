"""The gold benchmark: how the current matcher does on tests/benchmark/gold.csv.

One inventory is built from every gold row and run once through the same
function the command line uses, against the bundled data. Each item is mapped
back to its gold row by item id. Rules:

* wrong must be zero on every stratum (a wrong match is a bug in the rule);
* correct hand + catalog rows must not fall below tests/benchmark/floor.json.
  Raising the floor is a deliberate hand edit in the commit that earns it.
  Never lower it.

Print the numbers with `SWLC_BENCH_REPORT=1` or `-v`.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swlc import cli
from swlc.inputs import item_id
from test_docs import BANNED, BANNED_DIGESTS, hashed_terms

BENCH = ROOT / "tests" / "benchmark"
GOLD = BENCH / "gold.csv"
FLOOR = BENCH / "floor.json"
EOL_DIR = ROOT / "data" / "eol"
HEADER = ["name", "publisher", "version", "expected_product",
          "expected_cycle", "notes", "stratum", "heldout"]
STRATA = ("hand", "catalog", "generated")
OUTCOMES = ("correct", "wrong", "missed", "right-none")


# Gold rows the current matcher gets wrong. Each is a defect in an existing
# alias in data/aliases.json, found by this benchmark. They are marked
# expectedFailure below, never removed from gold. When a rule fixes one, its
# test reports an unexpected success: delete the entry in that commit.
# Key: (name, publisher, version). Value: the alias and the cause.
KNOWN_WRONG = {
    ("Python 3.11.7 (64-bit)", "Python Software Foundation", "3.12.1150.0"):
        "alias 'python' (prefix, version from name) ignores a version "
        "column that disagrees with the name",
    ("Python 3.15.1", "Python Software Foundation", "2.6.9"):
        "alias 'python' (prefix, version from name) ignores a version "
        "column that disagrees with the name",
    ("Microsoft Office Professional Plus 2019", "Microsoft Corporation",
     "16.0.10399"):
        "alias 'microsoft office professional plus' (prefix, build map by "
        "name year) trusts the year in the name over the shared 16.0 build",
    ("Python Launcher", "Python Software Foundation", "3.12.1150.0"):
        "alias 'python' (prefix, no edition words) names the product for a "
        "component row; no cycle, state unmatched",
    ("Python", "Python Software Foundation", "1.0.1"):
        "alias 'python' (prefix) names the product from a bare name; no "
        "cycle, state unmatched",
    ("Python 10.0.0", "Python Software Foundation", "10.0.0"):
        "alias 'python' (prefix) names the product for a version past the "
        "snapshot; no cycle, state unmatched",
    ("Windows Server", "Microsoft Corporation", "10.0.17763"):
        "alias 'windows server' (prefix, build map by name year) names the "
        "product from a bare name; no cycle, state unmatched",
    ("Microsoft SQL Server 2005", "Microsoft Corporation", "9.00.5000.00"):
        "alias 'microsoft sql server' (prefix, build map) names the product "
        "for a year outside the snapshot; no cycle, state unmatched",
    ("Ubuntu", "Canonical", "3.0.1"):
        "alias 'ubuntu' (exact, version from version) names the product for "
        "a version outside the snapshot; no cycle, state unmatched",
    ("Microsoft Windows Server Core", "", "2025"):
        "alias 'microsoft windows server' (prefix) names windows-server for "
        "a Server Core row whose product is windows-server-core; no cycle, "
        "state unmatched",
}


def read_gold() -> list:
    with open(GOLD, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def row_key(row: dict) -> tuple:
    return (row["name"], row["publisher"], row["version"])


def outcome(row: dict, item: dict) -> str:
    """Score one item against its gold row."""
    want, cycle = row["expected_product"], row["expected_cycle"]
    got = item["product"]
    if want == "NONE":
        return "right-none" if got is None else "wrong"
    if got is None:
        return "missed"
    if got != want:
        return "wrong"
    if not cycle:
        return "correct"
    if item["cycle"] is None:
        return "missed"
    return "correct" if item["cycle"] == cycle else "wrong"


def run_gold(rows: list) -> list:
    """Run every gold row through the real pipeline once.

    Returns [(row, outcome, item)] in gold order.
    """
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(
        encoding="utf-8"))
    as_of = date.fromisoformat(manifest["eol_date"])
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "gold-inventory.csv"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Software Name", "Publisher", "Version"])
            for r in rows:
                writer.writerow([r["name"], r["publisher"], r["version"]])
        result, _meta = cli.build(str(path), as_of=as_of)
    items = {it["id"]: it for it in result["items"]}
    seen = {}
    out = []
    for r in rows:
        gid = item_id(r["publisher"], r["name"], r["version"])
        want = (r["expected_product"], r["expected_cycle"])
        if gid in seen and seen[gid] != want:
            raise AssertionError("gold rows with one item id disagree: %s"
                                 % r["name"])
        seen[gid] = want
        out.append((r, outcome(r, items[gid]), items[gid]))
    return out


def tally(results: list) -> dict:
    """{group: Counter of outcomes}; groups are strata, 'heldout',
    'hand+catalog' and 'all'."""
    table = defaultdict(Counter)
    for row, res, _item in results:
        table[row["stratum"]][res] += 1
        table["all"][res] += 1
        if row["stratum"] != "generated":
            table["hand+catalog"][res] += 1
        if row["heldout"] == "1":
            table["heldout"][res] += 1
    return table


def report_table(results: list) -> str:
    """A plain table of the numbers, for commit messages and reports."""
    table = tally(results)
    head = "%-13s %7s %8s %7s %7s %10s" % (
        "group", "rows", "correct", "wrong", "missed", "right-none")
    lines = [head]
    for group in STRATA + ("hand+catalog", "heldout", "all"):
        c = table[group]
        lines.append("%-13s %7d %8d %7d %7d %10d" % (
            group, sum(c.values()), c["correct"], c["wrong"], c["missed"],
            c["right-none"]))
    return "\n".join(lines)


def wants_report() -> bool:
    return bool(os.environ.get("SWLC_BENCH_REPORT")) or "-v" in sys.argv \
        or "--verbose" in sys.argv


_CACHE: dict = {}


def results() -> list:
    if "r" not in _CACHE:
        _CACHE["r"] = run_gold(read_gold())
    return _CACHE["r"]


class BenchmarkRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = results()
        cls.table = tally(cls.results)
        if wants_report():
            print("\n" + report_table(cls.results), file=sys.stderr)

    def test_every_gold_row_was_scored(self):
        self.assertEqual(len(self.results), len(read_gold()))

    def test_no_wrong_matches_on_any_stratum(self):
        for stratum in STRATA:
            with self.subTest(stratum=stratum):
                wrong = ["%s | %s | %s -> %s %s (want %s %s)" % (
                    r["name"], r["publisher"], r["version"], it["product"],
                    it["cycle"], r["expected_product"], r["expected_cycle"])
                    for r, res, it in self.results
                    if res == "wrong" and r["stratum"] == stratum
                    and row_key(r) not in KNOWN_WRONG]
                self.assertEqual(wrong, [], "%d wrong:\n%s" % (
                    len(wrong), "\n".join(wrong[:40])))

    def test_hand_and_catalog_correct_not_below_floor(self):
        floor = json.loads(FLOOR.read_text(encoding="utf-8"))
        got = self.table["hand+catalog"]["correct"]
        self.assertGreaterEqual(
            got, floor["hand_catalog_correct_min"],
            "hand+catalog correct fell below the floor; fix the rule, "
            "never lower floor.json")


def _known_wrong_test(key, cause):
    @unittest.expectedFailure
    def test(self):
        for r, res, _it in self.results:
            if row_key(r) == key:
                self.assertNotEqual(res, "wrong", cause)
                return
        self.fail("known-wrong row is not in gold: %s" % (key,))
    return test


for _n, (_key, _cause) in enumerate(sorted(KNOWN_WRONG.items())):
    setattr(BenchmarkRunTests, "test_known_wrong_%02d" % _n,
            _known_wrong_test(_key, _cause))


def eol_cycles(product: str):
    path = EOL_DIR / (product + ".json")
    if not path.is_file():
        return None
    return {c["cycle"] for c in json.loads(path.read_text(encoding="utf-8"))}


class GoldFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_gold()

    def test_header(self):
        with open(GOLD, encoding="utf-8", newline="") as fh:
            self.assertEqual(next(csv.reader(fh)), HEADER)

    def test_floor_file_shape(self):
        floor = json.loads(FLOOR.read_text(encoding="utf-8"))
        self.assertEqual(sorted(floor), ["hand_catalog_correct_min", "note"])
        self.assertIsInstance(floor["hand_catalog_correct_min"], int)
        self.assertGreater(floor["hand_catalog_correct_min"], 0)

    def test_strata_and_heldout_values(self):
        for r in self.rows:
            self.assertIn(r["stratum"], STRATA, r["name"])
            self.assertIn(r["heldout"], ("0", "1"), r["name"])

    def test_heldout_rule(self):
        for r in self.rows:
            key = "%s|%s|%s" % (r["name"], r["publisher"], r["version"])
            digit = int(hashlib.sha256(key.encode("utf-8")).hexdigest(),
                        16) % 10
            want = "1" if r["stratum"] != "generated" and digit == 0 else "0"
            self.assertEqual(r["heldout"], want, key)

    def test_no_conflicting_duplicates(self):
        seen = {}
        for r in self.rows:
            key = (r["name"], r["publisher"], r["version"])
            want = (r["expected_product"], r["expected_cycle"])
            self.assertEqual(seen.setdefault(key, want), want, key)

    def test_expected_ids_and_cycles_exist_in_the_data(self):
        for r in self.rows:
            product, cycle = r["expected_product"], r["expected_cycle"]
            if product == "NONE":
                self.assertEqual(cycle, "", r["name"])
                continue
            cycles = eol_cycles(product)
            self.assertIsNotNone(cycles, "%s: no data/eol/%s.json"
                                 % (r["name"], product))
            if cycle:
                self.assertIn(cycle, cycles, "%s: %s" % (r["name"], product))

    def test_every_row_has_a_name_and_a_note(self):
        for r in self.rows:
            self.assertTrue(r["name"].strip())
            self.assertTrue(r["notes"].strip(), r["name"])

    def test_known_judgment_rows_are_present(self):
        want = {("Microsoft Office Professional Plus 2019", "16.0.10399",
                 "NONE"),
                ("Windows Server 2019 Standard", "10.0.17763",
                 "windows-server")}
        have = {(r["name"], r["version"], r["expected_product"])
                for r in self.rows}
        self.assertLessEqual(want, have)
        self.assertGreaterEqual(
            sum(1 for r in self.rows if r["expected_product"] == "jenkins"),
            5)


def benchmark_files() -> list:
    return sorted(p for p in BENCH.iterdir() if p.is_file()
                  and p.suffix in (".csv", ".md", ".json"))


class BenchmarkFileHygieneTests(unittest.TestCase):
    NEUTRAL = ["resume", "job search", "portfolio", "/users/",
               "/applications/", "gmail"]

    def test_files_exist(self):
        names = {p.name for p in benchmark_files()}
        for need in ("gold.csv", "floor.json", "README.md", "SOURCES.md"):
            self.assertIn(need, names)

    def test_neutral_banned_list(self):
        for path in benchmark_files():
            low = path.read_text(encoding="utf-8").lower()
            for word in self.NEUTRAL:
                self.assertNotIn(word, low, "%s: %s" % (path.name, word))
            for word in BANNED:
                self.assertNotIn(word, low, "%s: %s" % (path.name, word))

    def test_hashed_banned_terms(self):
        for path in benchmark_files():
            low = path.read_text(encoding="utf-8").lower()
            hit = hashed_terms(low) & BANNED_DIGESTS
            self.assertFalse(hit, "%s: banned term, digest %s"
                             % (path.name, sorted(hit)))

    def test_no_email_addresses(self):
        pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        for path in benchmark_files():
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(pattern.search(text), path.name)
            self.assertNotIn("@", text, path.name)


if __name__ == "__main__":
    unittest.main()
