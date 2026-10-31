"""The count column (issue #37): install_count, the order it sets, and
what it never changes. The count is a number from the user's file, not
discovered installs. All products and owners here are synthetic."""
from __future__ import annotations

import copy
import csv
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpers import run_main
from swlc import cli, report
from swlc.assess import LISTS
from swlc.inputs import MAX_COUNT_CELL, count_cell

DATA = ROOT / "tests" / "fixtures" / "data"
AS_OF = date(2026, 10, 24)
HEADER = ["Software Name", "Version", "Publisher", "Owner", "Install Count"]
# (name, version, publisher, owner, count cell). States per the fixture
# data on AS_OF.
ROWS = [
    ("Tidewater Suite", "4.2", "Example Corp", "Finance", "10"),   # past
    ("Tidewater Suite", "1.0", "Example Corp", "Finance", "500"),  # past
    ("Example SQL", "14", "Sample Systems Inc", "Infra", ""),      # past
    ("Redwood Backup", "1.0", "Sample Systems Inc", "Infra", "abc"),  # past
    ("Tidewater Suite", "5.0", "Example Corp", "Finance", "7"),    # soon
    ("Tidewater Suite", "5.0", "Example Corp", "Finance", "8"),    # soon
    ("Tidewater Suite", "2.0", "Example Corp", "Finance", "15"),   # soon
    ("Mystery Tool", "3.1", "Nobody Inc", "Desk", "40"),           # unmatched
    ("Brightline Editor", "9.0", "Fictional Software Ltd", "Desk",
     "40"),                                                        # unmatched
    ("Tidewater Suite", "6.0", "Example Corp", "", "3"),           # ownerless
]


def write_inventory(folder: Path, rows, header=HEADER, name="inv.csv"):
    path = folder / name
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return path


def without_count(rows):
    return [r[:4] for r in rows]


def check(path: Path, out: Path, *extra):
    return run_main(["check", str(path), "--data", str(DATA), "--as-of",
                     AS_OF.isoformat(), "--out", str(out), *extra])


def outputs(out: Path) -> dict:
    return {n: (out / n).read_text(encoding="utf-8")
            for n in ("report.json", "report.md", "report.csv")}


def rank(it):
    return (it["install_count"] is None, -(it["install_count"] or 0),
            it["id"])


class CountCellTests(unittest.TestCase):
    def test_whole_numbers_are_read(self):
        self.assertEqual(count_cell("0"), 0)
        self.assertEqual(count_cell("42"), 42)
        self.assertEqual(count_cell("007"), 7)
        self.assertEqual(count_cell(str(MAX_COUNT_CELL)), MAX_COUNT_CELL)
        self.assertEqual(count_cell("1,234"), 1234)
        self.assertEqual(count_cell("1,000,000,000"), MAX_COUNT_CELL)
        self.assertEqual(count_cell("12.0"), 12)
        self.assertEqual(count_cell("1,234.00"), 1234)
        self.assertEqual(count_cell("0.00"), 0)

    def test_everything_else_is_refused(self):
        for text in ("-5", "+5", "-1.0", "1.5", "1.234", "1.", ".0",
                     "1 000", "1 234", "12,34", "1234,567", "1,234.",
                     "1,234.5", ",123", "abc", "=1+1", "@SUM(A1)", "1e3",
                     "١٢", "١,٢٣٤",
                     str(MAX_COUNT_CELL + 1), "1,000,000,001",
                     "9" * 5000, "1" + ",000" * 2000):
            self.assertIsNone(count_cell(text), text)


class RankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        cls.with_path = write_inventory(folder, ROWS)
        cls.plain_path = write_inventory(folder, without_count(ROWS),
                                         HEADER[:4], "plain.csv")
        cls.result = cli.run(str(cls.with_path), data=str(DATA),
                             as_of=AS_OF)
        cls.plain = cli.run(str(cls.plain_path), data=str(DATA),
                            as_of=AS_OF)
        cls.by_name = {(it["name"], it["version"]): it
                       for it in cls.result["items"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def count(self, name, version):
        return self.by_name[(name, version)]["install_count"]

    def test_sum_over_rows_and_nulls(self):
        self.assertEqual(self.count("Tidewater Suite", "5.0"), 15)
        self.assertEqual(self.count("Tidewater Suite", "1.0"), 500)
        self.assertIsNone(self.count("Example SQL", "14"))       # blank
        self.assertIsNone(self.count("Redwood Backup", "1.0"))   # invalid
        self.assertEqual(self.result["counts"]["count_invalid_cells"], 1)

    def test_lists_ordered_largest_first_nulls_last(self):
        items = {it["id"]: it for it in self.result["items"]}
        past = [items[i] for i in self.result["lists"]["past_eol"]]
        self.assertEqual([it["install_count"] for it in past][:2],
                         [500, 10])
        self.assertEqual([it["install_count"] for it in past][2:],
                         [None, None])
        for name in LISTS:
            ids = self.result["lists"][name]
            self.assertEqual(ids, [it["id"] for it in
                                   sorted((items[i] for i in ids),
                                          key=rank)], name)
        self.assertEqual(self.result["items"],
                         sorted(self.result["items"], key=rank))

    def test_ties_keep_id_order(self):
        tied = [i for i in self.result["lists"]["unmatched"]]
        self.assertEqual(len(tied), 2)
        self.assertEqual(tied, sorted(tied))
        nulls = self.result["lists"]["past_eol"][2:]
        self.assertEqual(nulls, sorted(nulls))

    def test_count_changes_nothing_but_order(self):
        def strip(result):
            body = copy.deepcopy(result)
            for it in body["items"]:
                it.pop("install_count")
            body["counts"].pop("count_invalid_cells")
            body["items"].sort(key=lambda it: it["id"])
            body["lists"] = {k: sorted(v) for k, v in body["lists"].items()}
            body["meta"].pop("encoding")
            return body
        self.assertEqual(strip(self.result), strip(self.plain))

    def test_no_column_keeps_id_order_and_null_keys(self):
        ids = [it["id"] for it in self.plain["items"]]
        self.assertEqual(ids, sorted(ids))
        for name, members in self.plain["lists"].items():
            self.assertEqual(members, sorted(members), name)
        self.assertTrue(all(it["install_count"] is None
                            for it in self.plain["items"]))
        self.assertEqual(self.plain["counts"]["count_invalid_cells"], 0)


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_views(self, rows, header=HEADER, *extra, name="inv.csv"):
        path = write_inventory(self.folder, rows, header, name)
        out = self.folder / ("out-" + name)
        code, stdout, stderr = check(path, out, *extra)
        return code, stdout, stderr, outputs(out)

    def test_md_line_and_order_note(self):
        _c, _o, _e, files = self.run_views(ROWS)
        md = files["report.md"]
        self.assertIn("  - Count (from your file): 500\n", md)
        self.assertIn("  - Count (from your file): 15\n", md)
        self.assertEqual(md.count(report.COUNT_ORDER_LINE), 1)
        self.assertIn(report.COUNT_INVALID_LINE % 1, md)
        self.assertIn("not discovered installs", md)
        past = md.split("## Past end of life")[1].split("## ")[0]
        self.assertLess(past.index("Tidewater Suite** 1.0"),
                        past.index("Tidewater Suite** 4.2"))

    def test_csv_column(self):
        _c, _o, _e, files = self.run_views(ROWS)
        rows = list(csv.DictReader(io.StringIO(files["report.csv"])))
        self.assertEqual(list(rows[0]), list(report.CSV_COLUMNS))
        self.assertEqual(list(rows[0])[-1], "Count (from your file)")
        self.assertEqual(list(rows[0])[-2], report.SUPPORT_COLUMN)
        rep = json.loads(files["report.json"])
        self.assertEqual([r["id"] for r in rows],
                         [it["id"] for it in rep["items"]])
        for r, it in zip(rows, rep["items"]):
            want = it["install_count"]
            self.assertEqual(r[report.COUNT_COLUMN],
                             "" if want is None else str(want))

    def test_no_column_output_matches_blank_column(self):
        """No count column and an all-blank one give the same files, and
        report.md has no count text: the view without counts is the one
        from before counts were read."""
        plain = without_count(ROWS)
        blank = [r[:4] + ("",) for r in ROWS]
        _c, _o, _e, a = self.run_views(plain, HEADER[:4], name="a.csv")
        _c, _o, _e, b = self.run_views(blank, HEADER, name="b.csv")
        self.assertEqual(a["report.md"], b["report.md"])
        self.assertEqual(a["report.csv"], b["report.csv"])
        self.assertEqual(json.loads(a["report.json"])["items"],
                         json.loads(b["report.json"])["items"])
        self.assertNotIn("Count", a["report.md"])
        rep = json.loads(a["report.json"])
        # report.md rendered from the result with the count keys removed
        # is the same text: the count feature adds nothing without counts.
        meta = rep.pop("meta")
        old = copy.deepcopy(rep)
        for it in old["items"]:
            it.pop("install_count")
        old["counts"].pop("count_invalid_cells")
        self.assertEqual(report.render_markdown(old, meta),
                         report.render_markdown(rep, meta))
        for r in csv.DictReader(io.StringIO(a["report.csv"])):
            self.assertEqual(r[report.COUNT_COLUMN], "")

    def test_governable_only_keeps_count_order(self):
        header = HEADER + ["Parent"]
        rows = [r + ("",) for r in ROWS] + [
            ("Mystery Tool Plugin", "1.0", "Nobody Inc", "Desk",
             "900", "Mystery Tool")]
        _c, _o, _e, files = self.run_views(rows, header, "--governable-only")
        rep = json.loads(files["report.json"])
        parts = ("component", "bundle_member")
        shown = [it for it in rep["items"]
                 if it["classification"] not in parts]
        hidden = [it["name"] for it in rep["items"]
                  if it["classification"] in parts]
        self.assertEqual(hidden, ["Mystery Tool Plugin"])
        self.assertEqual(rep["items"], sorted(rep["items"], key=rank))
        csv_ids = [r["id"] for r in
                   csv.DictReader(io.StringIO(files["report.csv"]))]
        self.assertEqual(csv_ids, [it["id"] for it in shown])
        md = files["report.md"]
        self.assertNotIn("Count (from your file): 900", md)
        past = md.split("## Past end of life")[1].split("## ")[0]
        self.assertLess(past.index("Tidewater Suite** 1.0"),
                        past.index("Tidewater Suite** 4.2"))

    def test_fail_on_unaffected(self):
        flags = ("--fail-on", "past_eol,ends_soon,unmatched")
        with_c = self.run_views(ROWS, HEADER, *flags, name="c.csv")
        plain = self.run_views(without_count(ROWS), HEADER[:4], *flags,
                               name="d.csv")
        self.assertEqual(with_c[0], cli.EXIT_FINDINGS)
        self.assertEqual(with_c[0], plain[0])
        self.assertEqual(with_c[2], plain[2])
        zero = [r[:4] + ("0",) for r in ROWS]
        none = self.run_views(zero, HEADER, "--fail-on", "dates_disagree",
                              name="e.csv")
        self.assertEqual(none[0], cli.EXIT_OK)

    def test_counts_only_total_and_id_order(self):
        code, stdout, _e, _f = self.run_views(ROWS, HEADER, "--counts-only")
        self.assertEqual(code, 0)
        self.assertIn("count_total 623\n", stdout)
        for line in stdout.splitlines():
            name = line.split(" ", 1)[0]
            if name in LISTS and ": " in line:
                ids = line.split(": ", 1)[1].split()
                self.assertEqual(ids, sorted(ids), name)
        for row in ROWS:
            self.assertNotIn(row[0], stdout)
        _c, plain, _e, _f = self.run_views(without_count(ROWS), HEADER[:4],
                                           "--counts-only", name="p.csv")
        self.assertNotIn("count_total", plain)


if __name__ == "__main__":
    unittest.main()
