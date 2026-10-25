"""Tests for the release-review fixes: help text, report wording, golden
clash warning and plural days."""
import csv
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpers import make_data_dir
from swlc import cli
from swlc.report import render_markdown

# Tests that read the bundled data take their date from its own manifest,
# so a newer data release cannot break them.
_MANIFEST = json.loads(
    (ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
AS_OF = max(date.fromisoformat(_MANIFEST["kev_date"]),
            date.fromisoformat(_MANIFEST["eol_date"]))


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
                      "version, or the version in the name disagrees with "
                      "it.", md)
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
        # Exact dates in a fixture data folder: KEV 1 day old, end of life
        # 2 days old, as of 2026-10-24; and a second run with 0 days.
        rows = [["Example SQL", "14", "Example Vendor", "a"]]
        for kev, eol, want in (
                ("2026-10-23", "2026-10-22", ["(1 day old)", "(2 days old)"]),
                ("2026-10-24", "2026-10-24", ["(0 days old)"])):
            with tempfile.TemporaryDirectory() as tmp:
                data = make_data_dir(tmp, kev, eol)
                inv = write_csv(Path(tmp) / "inv.csv",
                                ["name", "version", "publisher", "owner"],
                                rows)
                result, meta = cli.build(inv, as_of=date(2026, 10, 24),
                                         data=data)
            md = render_markdown(result, meta)
            for text in want:
                self.assertIn(text, md)
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
