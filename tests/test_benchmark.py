"""The gold benchmark: how the current matcher does on tests/benchmark/gold.csv.

One inventory is built from every gold row and run once through the same
function the command line uses, against the bundled data. Each item is mapped
back to its gold row by item id. Rules:

* hard wrong (a wrong cycle) must be zero except the listed KNOWN_WRONG rows
  (each stores the exact wrong answer; any change makes its test fail);
  soft wrong (a wrong product, no cycle) may not exceed soft_wrong_max;
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
OUTCOMES = ("correct", "hard-wrong", "soft-wrong", "missed", "right-none")


# HARD WRONG rows the current matcher gets wrong (a cycle, so a lifecycle
# claim, that is wrong). Each is a defect found by this benchmark, marked
# expectedFailure below and never removed from gold. When a rule fixes one,
# or changes its answer to anything else, its test reports an unexpected
# success: update or delete the entry in that commit.
# Key: (name, publisher, version). Value: (cause, (product, cycle) it gives).
KNOWN_WRONG = {
    ("Python 3.11.7 (64-bit)", "Python Software Foundation", "3.12.1150.0"):
        ("alias 'python' (prefix, version from name) ignores a version "
         "column that disagrees with the name; gold is python, no cycle",
         ("python", "3.11")),
    ("Python 3.15.1", "Python Software Foundation", "2.6.9"):
        ("alias 'python' (prefix, version from name) ignores a version "
         "column that disagrees with the name; gold is python, no cycle",
         ("python", "3.15")),
}


def read_gold() -> list:
    with open(GOLD, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def row_key(row: dict) -> tuple:
    return (row["name"], row["publisher"], row["version"])


def outcome(row: dict, item: dict) -> str:
    """Score one item against its gold row.

    expected_cycle: a cycle label; empty (any cycle is fine, none is used for
    expected NONE rows); or the word none (the product is right but no cycle
    can be decided from the row).
    Hard wrong: the item carries a cycle (a lifecycle claim) that is wrong.
    Soft wrong: product set, no cycle, and the product is wrong or the row
    expects NONE.
    """
    want, cycle = row["expected_product"], row["expected_cycle"]
    got = item["product"]
    wrong = "hard-wrong" if item["cycle"] is not None else "soft-wrong"
    if want == "NONE":
        return "right-none" if got is None else wrong
    if got is None:
        return "missed"
    if got != want:
        return wrong
    if cycle == "none":
        return "correct" if item["cycle"] is None else "hard-wrong"
    if not cycle:
        return "correct"
    if item["cycle"] is None:
        return "missed"
    return "correct" if item["cycle"] == cycle else "hard-wrong"


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
    head = "%-13s %7s %8s %5s %5s %7s %10s" % (
        "group", "rows", "correct", "hard", "soft", "missed", "right-none")
    lines = [head]
    for group in STRATA + ("hand+catalog", "heldout", "all"):
        c = table[group]
        lines.append("%-13s %7d %8d %5d %5d %7d %10d" % (
            group, sum(c.values()), c["correct"], c["hard-wrong"],
            c["soft-wrong"], c["missed"], c["right-none"]))
    soft = [r for r, res, _i in results if res == "soft-wrong"]
    lines.append("soft-wrong rows (%d):" % len(soft))
    for r in soft:
        lines.append("  %s | %s | %s" % (r["name"], r["publisher"],
                                         r["version"]))
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

    def test_no_new_hard_wrong_matches_on_any_stratum(self):
        for stratum in STRATA:
            with self.subTest(stratum=stratum):
                wrong = ["%s | %s | %s -> %s %s (want %s %s)" % (
                    r["name"], r["publisher"], r["version"], it["product"],
                    it["cycle"], r["expected_product"], r["expected_cycle"])
                    for r, res, it in self.results
                    if res == "hard-wrong" and r["stratum"] == stratum
                    and row_key(r) not in KNOWN_WRONG]
                self.assertEqual(wrong, [], "%d hard wrong:\n%s" % (
                    len(wrong), "\n".join(wrong[:40])))

    def test_soft_wrong_not_above_ceiling(self):
        floor = json.loads(FLOOR.read_text(encoding="utf-8"))
        soft = [r["name"] for r, res, _i in self.results
                if res == "soft-wrong"]
        self.assertLessEqual(
            len(soft), floor["soft_wrong_max"],
            "soft wrong rose above soft_wrong_max: %s" % soft)

    def test_hand_and_catalog_correct_not_below_floor(self):
        floor = json.loads(FLOOR.read_text(encoding="utf-8"))
        got = self.table["hand+catalog"]["correct"]
        self.assertGreaterEqual(
            got, floor["hand_catalog_correct_min"],
            "hand+catalog correct fell below the floor; fix the rule, "
            "never lower floor.json")


def _known_wrong_test(key, cause, stored):
    @unittest.expectedFailure
    def test(self):
        for r, res, it in self.results:
            if row_key(r) == key:
                still = res == "hard-wrong" and \
                    (it["product"], it["cycle"]) == stored
                self.assertFalse(still, cause)
                return
        self.fail("known-wrong row is not in gold: %s" % (key,))
    return test


def _slug(key) -> str:
    return re.sub(r"[^a-z0-9]+", "_", " ".join(key).lower()).strip("_")


for _key, (_cause, _stored) in KNOWN_WRONG.items():
    setattr(BenchmarkRunTests, "test_known_wrong_" + _slug(_key),
            _known_wrong_test(_key, _cause, _stored))


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
        self.assertEqual(sorted(floor), ["hand_catalog_correct_min", "note",
                                         "soft_wrong_max"])
        self.assertIsInstance(floor["soft_wrong_max"], int)
        self.assertIn("none", {r["expected_cycle"] for r in self.rows})
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
            gid = item_id(r["publisher"], r["name"], r["version"])
            want = (r["expected_product"], r["expected_cycle"])
            self.assertNotIn(gid, seen, "duplicate row: %s" % r["name"])
            seen[gid] = want

    def test_expected_ids_and_cycles_exist_in_the_data(self):
        for r in self.rows:
            product, cycle = r["expected_product"], r["expected_cycle"]
            if product == "NONE":
                self.assertEqual(cycle, "", r["name"])
                continue
            cycles = eol_cycles(product)
            self.assertIsNotNone(cycles, "%s: no data/eol/%s.json"
                                 % (r["name"], product))
            if cycle and cycle != "none":
                self.assertIn(cycle, cycles, "%s: %s" % (r["name"], product))

    def test_unsure_rows_stay_out_of_gold(self):
        with open(BENCH / "unsure.csv", encoding="utf-8", newline="") as fh:
            unsure = list(csv.DictReader(fh))
        self.assertTrue(unsure)
        have = {item_id(r["publisher"], r["name"], r["version"])
                for r in self.rows}
        for u in unsure:
            self.assertNotIn(item_id(u["publisher"], u["name"], u["version"]),
                             have, u["name"])
            self.assertTrue(u["notes"].strip(), u["name"])

    def test_package_names_and_versions_agree(self):
        """A catalog or generated package row must carry a plausible real
        version: a number in the package name must match the version."""
        allow = {"pgadmin4", "log4j"}   # reviewed: names, not versions
        for r in self.rows:
            if r["stratum"] == "hand" or "auto=package" not in r["notes"] \
                    or r["expected_product"] == "NONE" or r["name"] in allow:
                continue
            toks = re.findall(
                r"(?<![A-Za-z0-9])\d+(?:\.\d+)*(?![A-Za-z0-9])"
                r"|(?<=[A-Za-z])\d+(?:\.\d+)*", r["name"])
            if not toks:
                continue
            ver = re.sub(r"^\d+:", "", r["version"]).replace("-", ".")
            vp = ver.split(".")
            ok = any(vp[:len(t.split("."))] == t.split(".") or
                     t.split(".")[:len(vp)] == vp for t in toks)
            self.assertTrue(ok or r["expected_cycle"] == "none",
                            "%s / %s" % (r["name"], r["version"]))

    def test_every_row_has_a_name_and_a_note(self):
        for r in self.rows:
            self.assertTrue(r["name"].strip())
            self.assertTrue(r["notes"].strip(), r["name"])

    def test_known_judgment_rows_are_present(self):
        want = {("Microsoft Office Professional Plus 2019", "16.0.10399",
                 "office", "2019"),
                ("Microsoft Office Professional Plus", "16.0", "office",
                 "none"),
                ("Windows Server 2019 Standard", "10.0.17763",
                 "windows-server", "2019")}
        have = {(r["name"], r["version"], r["expected_product"],
                 r["expected_cycle"]) for r in self.rows}
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
        for need in ("gold.csv", "floor.json", "README.md", "SOURCES.md",
                     "unsure.csv"):
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
