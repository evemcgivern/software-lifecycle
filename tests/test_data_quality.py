"""The data-quality counts: figures about the rows read (issue #107)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import swlc_mcp
from helpers import run_main
from swlc import report

DATA = ROOT / "tests" / "fixtures" / "data"
HEADER = "Software Name,Version,Owner,Device\n"
# 5 rows. Matched: the three Demo OS rows. Blank owner: rows 3 and 5.
# No version number: "latest" and the blank. Identical repeat: row 2.
ROWS = ("Demo OS 2.0,2.0,ZzOwner,a\n"
        "Demo OS 2.0,2.0,ZzOwner,a\n"
        "Demo OS 2.0,2.0,,b\n"
        "ZzSecretApp,latest,ZzOwner,c\n"
        "ZzOtherApp,,,d\n")
WANT = {"matched_rows": 3, "blank_owner_rows": 2,
        "no_version_number_rows": 2, "identical_repeat_rows": 1}
LINE = ("data_quality matched_rows=3 blank_owner_rows=2 "
        "no_version_number_rows=2 identical_repeat_rows=1")


class DataQuality(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def check(self, text, *extra):
        inventory = self.root / "inv.csv"
        inventory.write_text(text, encoding="utf-8")
        out = self.root / "out"
        code, stdout, stderr = run_main(
            ["check", str(inventory), "--data", str(DATA),
             "--as-of", "2026-10-24", "--out", str(out), *extra])
        self.assertEqual(code, 0, stderr)
        return stdout, out

    def counts(self, text):
        _, out = self.check(text)
        return json.loads(
            (out / "report.json").read_text("utf-8"))["counts"]

    def test_figures_for_a_known_inventory(self):
        counts = self.counts(HEADER + ROWS)
        self.assertEqual(counts["rows"], 5)
        self.assertEqual(counts["data_quality"], WANT)

    def test_rows_that_differ_in_any_column_are_not_repeats(self):
        counts = self.counts(HEADER + "Demo OS 2.0,2.0,ZzOwner,a\n"
                             "Demo OS 2.0,2.0,ZzOwner,b\n")
        self.assertEqual(counts["data_quality"]["identical_repeat_rows"], 0)

    def test_no_owner_column_makes_every_row_blank_owner(self):
        counts = self.counts("Software Name,Version\nDemo OS 2.0,2.0\n"
                             "ZzSecretApp,1\n")
        self.assertEqual(counts["data_quality"]["blank_owner_rows"], 2)

    def test_report_md_shows_counts_beside_shares(self):
        _, out = self.check(HEADER + ROWS)
        md = (out / "report.md").read_text("utf-8")
        for line in (
                "- Matched: 3 of 5 (60%)",
                "- Blank owner cell: 2 of 5 (40%)",
                "- Version cell blank or without a digit: 2 of 5 (40%)",
                "- Identical to an earlier row: 1 of 5 (20%)"):
            self.assertIn(line + "\n", md)
        self.assertEqual(md.count(report.QUALITY_NOTE), 1)

    def test_shares_never_round_to_all_or_none(self):
        self.assertEqual(report._share(0, 1000), "0%")
        self.assertEqual(report._share(1, 1000), "under 1%")
        self.assertEqual(report._share(999, 1000), "99%")
        self.assertEqual(report._share(1000, 1000), "100%")

    def test_counts_only_line_has_numbers_only(self):
        stdout, _ = self.check(HEADER + ROWS, "--counts-only")
        self.assertIn(LINE, stdout.splitlines())
        for word in ("ZzOwner", "ZzSecretApp", "latest"):
            self.assertNotIn(word, stdout)

    def test_desktop_server_keeps_the_line(self):
        stdout, _ = self.check(HEADER + ROWS, "--counts-only")
        self.assertIn(LINE, swlc_mcp.counts_lines(stdout))
        self.assertEqual(swlc_mcp.counts_lines(LINE + " ZzSecretApp"), [])


if __name__ == "__main__":
    unittest.main()
