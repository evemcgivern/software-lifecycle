"""Tests for the release-review fixes: help text, report wording, golden
clash warning and plural days."""
import csv
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swlc import cli
from swlc.report import render_markdown

AS_OF = date(2026, 10, 24)


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return str(path)


def markdown_for(rows, **options):
    with tempfile.TemporaryDirectory() as tmp:
        inv = write_csv(Path(tmp) / "inv.csv",
                        ["name", "version", "publisher", "owner"], rows)
        result, meta = cli.build(inv, as_of=AS_OF, **options)
    return render_markdown(result, meta)


class HelpTests(unittest.TestCase):
    def test_every_flag_and_command_has_help(self):
        import argparse
        parser = cli._parser()
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for choice in action._choices_actions:
                    self.assertTrue(choice.help, choice.dest)
                for sub in action.choices.values():
                    for a in sub._actions:
                        self.assertTrue((a.help or "").strip(), a.dest)


class ReportWordingTests(unittest.TestCase):
    def test_unmatched_lines_follow_the_reason(self):
        md = markdown_for([
            ["Microsoft SQL Server 2016", "13.0.5026.0", "Microsoft", "a"],
            ["Zzz Unknown Tool", "1.0", "Nobody", "b"]])
        self.assertIn("product known (mssqlserver), but no cycle was "
                      "matched. Reason NO_CYCLE: no cycle matches this "
                      "version.", md)
        self.assertIn("no known product was matched. Reason NO_ALIAS",
                      md)
        self.assertNotIn("not matched to a known product", md)

    def test_ownerless_item_says_what_to_do(self):
        md = markdown_for([["Zzz Unknown Tool", "1.0", "Nobody", ""],
                           ["Other Tool", "2", "Nobody", "carol"]])
        self.assertIn("Owners: none listed. This item cannot be actioned "
                      "until an owner is named. Rows: 1", md)
        self.assertIn("Owners: carol. Rows: 1", md)

    def test_one_day_is_singular(self):
        md = markdown_for([["Zzz Unknown Tool", "1.0", "Nobody", "a"]])
        self.assertIn("(1 day old)", md)
        self.assertIn("(0 days old)", md)
        self.assertNotIn("1 days", md)


class GoldenClashTests(unittest.TestCase):
    HEADER = ["schema_version", "product", "source", "manual_eol", "reason",
              "set_by", "set_on", "review_by"]

    def run_with(self, golden_rows):
        with tempfile.TemporaryDirectory() as tmp:
            inv = write_csv(Path(tmp) / "inv.csv",
                            ["name", "version", "publisher", "owner"],
                            [["Node.js", "12", "OpenJS Foundation", "a"]])
            golden = write_csv(Path(tmp) / "g.csv", self.HEADER, golden_rows)
            return cli.run(inv, as_of=AS_OF, golden=golden)

    def test_two_rows_warn_and_product_id_row_wins(self):
        report = self.run_with([
            ["1", "nodejs", "manual", "2030-01-01", "r", "x", "", ""],
            ["1", "node.js", "manual", "2031-01-01", "r", "x", "", ""]])
        self.assertIn("1 item(s) matched two golden-source rows; the "
                      "product-id row was used.", report["warnings"])
        item = report["items"][0]
        self.assertEqual(item["eol_used"], "2030-01-01")

    def test_one_row_does_not_warn(self):
        report = self.run_with([
            ["1", "nodejs", "manual", "2030-01-01", "r", "x", "", ""]])
        self.assertFalse([w for w in report["warnings"]
                          if "golden-source" in w])


if __name__ == "__main__":
    unittest.main()
