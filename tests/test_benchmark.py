"""The gold benchmark: how the current matcher does on tests/benchmark/gold.csv.

One inventory is built from every gold row and run once through the same
function the command line uses, against the bundled data. Each item is mapped
back to its gold row by item id. Rules:

* hard wrong (a wrong cycle) must be zero except the listed KNOWN_WRONG rows
  (each stores the exact wrong answer; any change makes its test fail);
  soft wrong (a wrong product, no cycle) may not exceed soft_wrong_max;
* correct hand + catalog rows, and correct generated rows, must not fall
  below tests/benchmark/floor.json. Raising the floor is a deliberate hand
  edit in the commit that earns it. Never lower it.

Print the numbers with `SWLC_BENCH_REPORT=1` or `-v`.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swlc import assess, cli
from swlc.inputs import item_id
from swlc.normalize import normalize_name
from test_docs import BANNED, BANNED_DIGESTS, hashed_terms

BENCH = ROOT / "tests" / "benchmark"
GOLD = BENCH / "gold.csv"
FLOOR = BENCH / "floor.json"
EOL_DIR = ROOT / "data" / "eol"
HEADER = ["name", "publisher", "version", "expected_product",
          "expected_cycle", "notes", "stratum", "heldout", "classification",
          "expected_parent"]
CLASSES = ("governable", "component", "bundle_member", "unknown")
PARENTS = BENCH / "parents"
SILVER_SAMPLE = BENCH / "silver-sample.csv"
SILVER_HEADER = ["source", "name", "publisher", "version", "label",
                 "label_b", "agreed", "heldout", "notes"]
# Rows present before the classification columns were added: the first
# ORIGINAL_ROWS rows of gold.csv, identified by a digest of their keys. A
# pinned digest, not `git show main:tests/benchmark/gold.csv`: once this work
# merges, main itself holds the new rows, and a git call may be missing in CI.
ORIGINAL_ROWS = 2197
ORIGINAL_KEYS_SHA256 = "9681fc48293f431b94805cf30bf82a03704016b9cef4bf463a8660840d237245"
STRATA = ("hand", "catalog", "generated")
OUTCOMES = ("correct", "hard-wrong", "soft-wrong", "missed", "right-none")


# HARD WRONG rows the current matcher gets wrong (a cycle, so a lifecycle
# claim, that is wrong). Each is a defect found by this benchmark, marked
# expectedFailure below and never removed from gold. When a rule fixes one,
# or changes its answer to anything else, its test reports an unexpected
# success: update or delete the entry in that commit.
# Key: (name, publisher, version). Value: (cause, (product, cycle) it gives).
KNOWN_WRONG: dict = {}


def read_gold() -> list:
    with open(GOLD, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def row_key(row: dict) -> tuple:
    return (row["name"], row["publisher"], row["version"])


def read_parent_cases() -> list:
    """[(inventory csv path, expected dict)] for every parent case.

    A case is <case>.csv (headings Software Name, Publisher, Version, Parent)
    plus <case>.expected.json, in tests/benchmark/parents/.
    """
    cases = []
    for path in sorted(PARENTS.glob("*.csv")):
        expected = path.with_name(path.stem + ".expected.json")
        cases.append((path, json.loads(expected.read_text(encoding="utf-8"))))
    return cases


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
    lines.append(classification_table(results))
    return "\n".join(lines)


# --- classification scoring -------------------------------------------------
# Only gold rows with a non-empty classification are scored. Held-out rows
# are scored too, and reported apart.

def parent_text(item: dict):
    """The predicted parent as gold writes it ("product:office/2019")."""
    ref = item.get("parent_ref")
    return None if ref is None else "%s:%s" % (ref["kind"], ref["value"])


def classified(results: list) -> list:
    return [(r, it) for r, _res, it in results if r["classification"]]


def class_correct(row: dict, item: dict) -> bool:
    if item["classification"] != row["classification"]:
        return False
    want = row["expected_parent"]
    if want and want != "none":
        return parent_text(item) == want
    return True


def wrong_parent(row: dict, item: dict) -> bool:
    got, want = parent_text(item), row["expected_parent"]
    if want == "none":
        return got is not None
    return bool(want) and got is not None and got != want


def precision(pairs: list, cls: str):
    """(right, predicted) for one predicted class."""
    predicted = [(r, it) for r, it in pairs if it["classification"] == cls]
    right = sum(1 for r, it in predicted if r["classification"] == cls)
    return right, len(predicted)


def classification_table(results: list) -> str:
    lines = ["classification (gold rows with a class):",
             "%-13s %6s %8s %s" % ("group", "rows", "correct",
                                   "precision by predicted class")]
    pairs = classified(results)
    for group, keep in (("tuning", "0"), ("heldout", "1"), ("all", None)):
        sub = [(r, it) for r, it in pairs
               if keep is None or r["heldout"] == keep]
        prec = []
        for cls in CLASSES:
            right, n = precision(sub, cls)
            prec.append("%s %d/%d" % (cls, right, n))
        lines.append("%-13s %6d %8d %s" % (
            group, len(sub), sum(class_correct(r, it) for r, it in sub),
            ", ".join(prec)))
    wrong = [(r, it) for r, it in pairs if not class_correct(r, it)]
    lines.append("classification disagreements (%d):" % len(wrong))
    for r, it in wrong:
        lines.append("  %s | %s | %s: gold %s %s, got %s %s %s" % (
            r["name"], r["publisher"], r["version"], r["classification"],
            r["expected_parent"] or "-", it["classification"],
            parent_text(it) or "-", ",".join(it["classification_basis"])))
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

    # Generated rows are built from the catalog, which the weekly job
    # changes (an upstream retitle or removal), so this floor gates pull
    # requests and local runs only. In the weekly job (SWLC_WEEKLY_JOB) and
    # its simulation (SWLC_GATE_SIM) the count is reported instead.
    def test_generated_correct_not_below_floor(self):
        floor = json.loads(FLOOR.read_text(encoding="utf-8"))
        got = self.table["generated"]["correct"]
        if os.environ.get("SWLC_WEEKLY_JOB") or os.environ.get("SWLC_GATE_SIM"):
            self.skipTest("weekly job: generated correct %d, floor %d; "
                          "reported, not gating"
                          % (got, floor["generated_correct_min"]))
        self.assertGreaterEqual(
            got, floor["generated_correct_min"],
            "generated correct fell below the floor; fix the rule, "
            "never lower floor.json")


class ClassificationBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pairs = classified(results())
        cls.floor = json.loads(FLOOR.read_text(encoding="utf-8"))

    def test_rows_are_scored(self):
        self.assertGreaterEqual(len(self.pairs), 160)

    def test_no_governable_scored_as_part(self):
        bad = ["%s | %s | %s -> %s" % (r["name"], r["publisher"],
                                       r["version"], it["classification"])
               for r, it in self.pairs if r["classification"] == "governable"
               and it["classification"] in ("component", "bundle_member")]
        self.assertLessEqual(len(bad), self.floor["governable_as_part_max"],
                             "\n".join(bad))

    def test_no_wrong_parent(self):
        bad = ["%s | %s | %s -> %s (want %s)" % (
            r["name"], r["publisher"], r["version"], parent_text(it),
            r["expected_parent"]) for r, it in self.pairs
            if wrong_parent(r, it)]
        self.assertLessEqual(len(bad), self.floor["wrong_parent_max"],
                             "\n".join(bad))

    def test_part_precision_on_gold(self):
        for cls in ("component", "bundle_member"):
            with self.subTest(cls=cls):
                right, n = precision(self.pairs, cls)
                self.assertGreater(n, 0)
                self.assertGreaterEqual(right / n, 0.98,
                                        "%s precision %d/%d" % (cls, right, n))

    def test_classification_correct_not_below_floor(self):
        got = sum(class_correct(r, it) for r, it in self.pairs)
        self.assertGreaterEqual(
            got, self.floor["classification_correct_min"],
            "classification correct fell below the floor; fix the rule, "
            "never lower floor.json")

    def test_wrong_parent_scoring(self):
        item = {"parent_ref": {"kind": "product", "value": "office/2019",
                               "basis": "curated_parent"}}
        row = {"expected_parent": "product:office/2019"}
        self.assertFalse(wrong_parent(row, item))
        self.assertTrue(wrong_parent(dict(row, expected_parent=
                                          "product:office/2016"), item))
        self.assertTrue(wrong_parent(dict(row, expected_parent="none"),
                                     item))
        self.assertFalse(wrong_parent(dict(row, expected_parent=""), item))
        self.assertFalse(wrong_parent(row, {"parent_ref": None}))


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

    def test_classification_values(self):
        for r in self.rows:
            self.assertIn(r["classification"], ("",) + CLASSES, r["name"])

    def test_at_least_40_rows_per_class(self):
        counts = Counter(r["classification"] for r in self.rows)
        for cls in CLASSES:
            with self.subTest(cls=cls):
                self.assertGreaterEqual(counts[cls], 40, cls)

    def test_expected_parent_shape(self):
        for r in self.rows:
            value = r["expected_parent"]
            if not value:
                continue
            self.assertIn(r["classification"], ("bundle_member",)
                          if value != "none" else CLASSES, r["name"])
            if value == "none":
                continue
            match = re.fullmatch(r"product:([^/\s]+)/(\S+)", value)
            self.assertIsNotNone(match, "%s: %s" % (r["name"], value))
            cycles = eol_cycles(match.group(1))
            self.assertIsNotNone(cycles, "%s: %s" % (r["name"], value))
            self.assertIn(match.group(2), cycles, "%s: %s"
                          % (r["name"], value))

    def test_existing_rows_unchanged(self):
        old = self.rows[:ORIGINAL_ROWS]
        keys = "\n".join("%s|%s|%s" % row_key(r) for r in old)
        self.assertEqual(hashlib.sha256(keys.encode("utf-8")).hexdigest(),
                         ORIGINAL_KEYS_SHA256)
        for r in old:
            self.assertEqual(r["classification"], "", r["name"])
            self.assertEqual(r["expected_parent"], "", r["name"])

    def test_required_traps_present(self):
        def rows_named(name):
            return [r for r in self.rows
                    if r["name"] == name and r["classification"]]

        def has(name, ok, **extra):
            hits = [r for r in rows_named(name) if ok(r)
                    and all(r[k] == v for k, v in extra.items())]
            self.assertTrue(hits, "no row %r passing" % name)
        has("Runtime", lambda r: r["classification"] == "unknown")
        has("Android SDK Manager",
            lambda r: r["classification"] != "component")
        has("Driver Booster", lambda r: r["classification"] != "component")
        has("libreoffice", lambda r: r["classification"] == "governable")
        has("Microsoft Outlook 2019",
            lambda r: r["classification"] == "bundle_member"
            and r["expected_parent"] == "product:office/2019")
        has("Microsoft Outlook",
            lambda r: r["classification"] == "unknown"
            and r["version"].startswith("16.0."))
        temurin = [r for r in self.rows if "Temurin" in r["name"]
                   and r["classification"] == "governable"]
        self.assertTrue(temurin, "no standalone Temurin JDK row")
        vcpp = [r for r in self.rows if "Visual C++ 2015-2022 Redistributable"
                in r["name"] and r["classification"] == "component"]
        self.assertTrue(vcpp, "no VC++ redistributable component row")
        intel = [r for r in self.rows if r["name"].startswith("Intel")
                 and "Graphics" in r["name"]
                 and r["classification"] == "component"]
        self.assertTrue(intel, "no Intel graphics driver component row")
        kb = [r for r in self.rows if re.search(r"\(KB\d+\)", r["name"])
              and r["classification"] == "component"]
        self.assertTrue(kb, "no KB update component row")

    def test_silver_sample_header(self):
        with open(SILVER_SAMPLE, encoding="utf-8", newline="") as fh:
            self.assertEqual(next(csv.reader(fh)), SILVER_HEADER)

    def test_floor_file_shape(self):
        floor = json.loads(FLOOR.read_text(encoding="utf-8"))
        self.assertEqual(sorted(floor), ["classification_correct_min",
                                         "generated_correct_min",
                                         "governable_as_part_max",
                                         "hand_catalog_correct_min", "note",
                                         "soft_wrong_max",
                                         "wrong_parent_max"])
        self.assertEqual(floor["governable_as_part_max"], 0)
        self.assertEqual(floor["wrong_parent_max"], 0)
        self.assertIsInstance(floor["generated_correct_min"], int)
        self.assertGreater(floor["generated_correct_min"], 0)
        self.assertIsInstance(floor["soft_wrong_max"], int)
        self.assertIn("none", {r["expected_cycle"] for r in self.rows})
        self.assertIsInstance(floor["hand_catalog_correct_min"], int)
        self.assertGreater(floor["hand_catalog_correct_min"], 0)
        self.assertIsInstance(floor["classification_correct_min"], int)
        self.assertGreater(floor["classification_correct_min"], 0)

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

    def test_readme_heldout_count(self):
        count = sum(r["heldout"] == "1" for r in self.rows)
        text = " ".join((BENCH / "README.md").read_text("utf-8").split())
        self.assertIn("That is %d rows." % count, text)

    def test_every_note_url_is_in_sources(self):
        sources = (BENCH / "SOURCES.md").read_text("utf-8")
        for r in self.rows:
            for url in re.findall(r"https?://[^\s,;)]+", r["notes"]):
                self.assertIn(url.rstrip("."), sources, r["name"])

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

    def test_unsure_rows_do_not_near_duplicate_gold(self):
        """Compare normalized names (leading vendor prefix dropped) and
        versions, so a pair like 'Microsoft X 2022' and 'X 2022' is caught."""
        def key(name, publisher, version):
            norm = normalize_name(name)
            if norm.startswith("microsoft "):
                norm = norm[len("microsoft "):]
            return (norm, normalize_name(publisher), normalize_name(version))
        with open(BENCH / "unsure.csv", encoding="utf-8", newline="") as fh:
            unsure = list(csv.DictReader(fh))
        have = {key(r["name"], r["publisher"], r["version"])
                for r in self.rows}
        for u in unsure:
            self.assertNotIn(key(u["name"], u["publisher"], u["version"]),
                             have, u["name"])

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


class ShuffleTests(unittest.TestCase):
    def test_results_do_not_depend_on_row_order(self):
        rows = read_gold()
        base = {it["id"]: it for _r, _o, it in results()}
        shuffled = list(rows)
        random.Random(20261025).shuffle(shuffled)
        again = {it["id"]: it for _r, _o, it in run_gold(shuffled)}
        self.assertEqual(again, base)


class CurationCitesGoldTests(unittest.TestCase):
    def test_each_exclusion_cites_a_gold_row_that_is_not_held_out(self):
        curation = json.loads((ROOT / "data" / "curation.json").read_text(
            encoding="utf-8"))
        rows = {"%s|%s|%s" % row_key(r): r for r in read_gold()}
        for item in curation["exclusions"]:
            with self.subTest(gold=item["gold"]):
                row = rows.get(item["gold"])
                self.assertIsNotNone(row, "exclusion cites no gold row")
                self.assertEqual(row["heldout"], "0")
                self.assertEqual(row["expected_product"], "NONE")

    def test_each_allowlist_entry_cites_a_gold_row_of_its_product(self):
        curation = json.loads((ROOT / "data" / "curation.json").read_text(
            encoding="utf-8"))
        rows = {"%s|%s|%s" % row_key(r): r for r in read_gold()}
        for item in curation["single_word_allowlist"]:
            with self.subTest(gold=item["gold"]):
                row = rows.get(item["gold"])
                self.assertIsNotNone(row, "allowlist entry cites no gold row")
                self.assertEqual(row["heldout"], "0")
                self.assertEqual(row["expected_product"], item["product"])


class ParentCaseFileTests(unittest.TestCase):
    NEEDED = ("one-os", "two-os", "no-os", "column-item", "column-product",
              "column-absent", "column-duplicate-name",
              "column-names-a-part", "group-two-parents", "runtime-in-app",
              "parent-past-eol", "parent-no-cycle")
    HEADINGS = ["Software Name", "Publisher", "Version", "Parent"]

    def test_cases_present(self):
        have = {p.stem for p, _e in read_parent_cases()}
        for name in self.NEEDED:
            self.assertIn(name, have)

    def test_every_csv_has_an_expected_file(self):
        for path in PARENTS.glob("*.csv"):
            self.assertTrue(path.with_name(path.stem + ".expected.json")
                            .is_file(), path.name)
        for path in PARENTS.glob("*.expected.json"):
            self.assertTrue(path.with_name(
                path.name[:-len(".expected.json")] + ".csv").is_file(),
                path.name)

    def test_expected_files_parse(self):
        manifest = json.loads((ROOT / "data" / "manifest.json").read_text(
            encoding="utf-8"))
        for path, exp in read_parent_cases():
            with self.subTest(case=path.stem):
                with open(path, encoding="utf-8", newline="") as fh:
                    reader = csv.DictReader(fh)
                    self.assertEqual(reader.fieldnames, self.HEADINGS)
                    keys = {"%s|%s|%s" % (r["Software Name"], r["Publisher"],
                                          r["Version"]) for r in reader}
                self.assertEqual(sorted(exp), ["as_of", "data", "items",
                                               "warnings_contain"])
                # The weekly job and its simulation change the data date;
                # the cases then keep the date they were written for.
                if not (os.environ.get("SWLC_WEEKLY_JOB")
                        or os.environ.get("SWLC_GATE_SIM")):
                    self.assertEqual(exp["as_of"], manifest["eol_date"])
                date.fromisoformat(exp["as_of"])
                self.assertEqual(exp["data"], "bundled")
                self.assertIsInstance(exp["warnings_contain"], list)
                self.assertEqual(set(exp["items"]), keys)
                for key, want in exp["items"].items():
                    self.assertEqual(sorted(want), [
                        "classification", "inherited_from",
                        "inherited_state", "parent_ref"], key)
                    self.assertIn(want["classification"], CLASSES, key)
                    ref = want["parent_ref"]
                    if ref is not None:
                        self.assertEqual(sorted(ref), ["kind", "value"], key)
                        self.assertIn(ref["kind"], ("item", "product", "os"))
                    src = want["inherited_from"]
                    if src is not None:
                        self.assertIn(src, keys, key)
                        self.assertIsNotNone(ref, key)
                        self.assertIn(want["inherited_state"],
                                      assess.STATES, key)
                    else:
                        self.assertIsNone(want["inherited_state"], key)


def benchmark_files() -> list:
    return sorted(p for p in BENCH.rglob("*") if p.is_file()
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
