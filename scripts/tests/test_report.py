import copy
import csv
import io
import json
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import EVIL, make_data_dir, write_inventory
from swlc import report
from swlc.cli import build

AS_OF = date(2026, 10, 24)
KEV_LINE = ("The vendor and product appear in CISA KEV. This does not mean "
            "your version is affected.")
CLAIMS = ("Runs locally with no network by default; built to enterprise "
          "security practices; not independently assessed.")


class Base(unittest.TestCase):
    kev_date = "2026-10-22"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = make_data_dir(self.tmp.name, self.kev_date, "2026-10-20")
        self.inv = write_inventory(Path(self.tmp.name) / "inv.csv")
        self.result, self.meta = build(self.inv, as_of=AS_OF, data=self.data)
        self.md = report.render_markdown(self.result, self.meta)

    def item(self, name, version=None):
        for it in self.result["items"]:
            if it["name"] == name and (version is None
                                       or it["version"] == version):
                return it
        raise KeyError(name)


class MarkdownTests(Base):
    def test_section_order(self):
        heads = ["## Past end of life", "## Ends within the lookahead window",
                 "## Dates disagree", "## Couldn't match",
                 "## Review urgently", "## Accepted risk", "## Ownerless",
                 "## Golden source overrides", "```findings"]
        pos = [self.md.index(h) for h in heads]
        self.assertEqual(pos, sorted(pos))

    def test_fixed_wording(self):
        self.assertIn(KEV_LINE, self.md)
        self.assertIn(CLAIMS, self.md)
        self.assertNotIn("vulnerable", self.md.lower())

    def test_dates_show_source_and_snapshot(self):
        self.assertIn("per endoflife.date, snapshot 2026-10-20", self.md)

    def test_no_wall_clock_time(self):
        self.assertIsNone(re.search(r"\b\d{1,2}:\d{2}", self.md))

    def test_script_name_is_escaped(self):
        self.assertNotIn("<script>", self.md)
        self.assertIn("&lt;script&gt;", self.md)

    def test_markdown_specials_are_escaped(self):
        self.assertNotIn(EVIL, self.md)
        self.assertIn("\\[", report._disp("[x](http://e)"))
        self.assertNotIn("](", report._disp("[x](http://e)"))

    def test_display_is_truncated(self):
        shown = report._disp("a" * 1000)
        self.assertEqual(shown, "a" * report.MAX_DISPLAY + "...")

    def test_control_and_bidi_characters_removed(self):
        shown = report._disp("a\nb\r\x00c‮d")
        self.assertEqual(shown, "a b c" + "d")

    def test_unmatched_marked_unverified_with_reason(self):
        self.assertIn("**Unverified:**", self.md)
        self.assertIn("NO_ALIAS", self.md)

    def test_decision_needed_names_roles(self):
        self.assertIn("**Decision needed:**", self.md)
        self.assertIn("ITAM lead settles", self.md)

    def test_expired_exception_roles(self):
        text = report._decision_lines(
            {"dates_disagree": None, "decision_needed": ["EXCEPTION_EXPIRED"]})
        joined = "\n".join(text)
        self.assertIn("**Decision needed:**", joined)
        self.assertIn("asset owner requests risk acceptance", joined)
        self.assertIn("risk owner and an independent approver sign off",
                      joined)

    def test_every_decision_code_renders_a_line(self):
        for code in ("DIFFERENT_DATE", "NO_ENDOFLIFE_DATE",
                     "EXPORT_DATE_UNREADABLE", "EXPORT_DATES_CONFLICT",
                     "GOLDEN_EXPIRED", "GOLDEN_EXPORT_UNUSABLE",
                     "EXCEPTION_EXPIRED"):
            lines = report._decision_lines(
                {"dates_disagree": None, "decision_needed": [code]})
            self.assertEqual(len(lines), 1, code)
            self.assertTrue(lines[0].startswith("**Decision needed:**"))

    def test_findings_block(self):
        m = re.search(r"```findings\n(.*?)\n```", self.md, re.S)
        found = json.loads(m.group(1))
        self.assertTrue(self.md.rstrip().endswith("```"))
        types = {f["type"] for f in found}
        self.assertEqual(types, {"past_eol", "ends_soon", "dates_disagree",
                                 "unmatched", "review_urgently"})
        for f in found:
            self.assertEqual(set(f), {"type", "id"})
            self.assertIn(f["id"], self.result["lists"][f["type"]])
        self.assertEqual(
            len(found), sum(len(self.result["lists"][t]) for t in types))

    def test_current_kev_has_no_stale_notice(self):
        self.assertNotIn("KEV overlay is not current.", self.md)

    def test_golden_item_prints_both_dates(self):
        golden = Path(self.tmp.name) / "golden.csv"
        golden.write_text(
            "schema_version,product,source,manual_eol,reason,set_by,set_on,"
            "review_by\n1,examplesql,manual,2030-01-01,test,me,2026-01-01,"
            "2027-01-01\n", encoding="utf-8")
        result, meta = build(self.inv, as_of=AS_OF, data=self.data,
                             golden=str(golden))
        md = report.render_markdown(result, meta)
        self.assertIn("golden source per your file", md)
        self.assertIn("2030-01-01", md)
        self.assertIn("2026-12-31 per endoflife.date, snapshot 2026-10-20", md)
        self.assertIn("## Golden source overrides", md)

    def test_profile_unverified_in_header(self):
        result, meta = build(self.inv, as_of=AS_OF, data=self.data,
                             profile="demo")
        head = report.render_markdown(result, meta).split("## ")[0]
        self.assertIn("Profile: demo", head)
        self.assertIn("**Unverified:**", head)

    def test_generic_profile_has_no_profile_warning(self):
        head = self.md.split("## ")[0]
        self.assertNotIn("Profile:", head)

    def test_deterministic(self):
        again = report.render_markdown(copy.deepcopy(self.result), self.meta)
        self.assertEqual(again, self.md)


class StaleKevTests(Base):
    kev_date = "2026-10-16"  # 8 days before AS_OF

    def test_kev_overlay_not_current_with_age(self):
        self.assertIn("KEV overlay is not current.", self.md)
        self.assertIn("8 days", self.md)
        self.assertFalse(self.result["kev_current"])

    def test_empty_review_list_does_not_claim_none(self):
        result = copy.deepcopy(self.result)
        result["lists"]["review_urgently"] = []
        for it in result["items"]:
            it["kev"] = None
        md = report.render_markdown(result, self.meta)
        sec = md.split("## Review urgently")[1].split("## ")[0]
        self.assertIn("not current", sec)
        self.assertNotIn("None found", sec)


class JsonTests(Base):
    def test_canonical_and_meta(self):
        text = report.render_json(self.result, self.meta)
        obj = json.loads(text)
        self.assertEqual(obj["meta"]["tool_version"],
                         (Path(__file__).resolve().parents[2]
                          / "VERSION").read_text().strip())
        self.assertEqual(text, report.render_json(self.result, self.meta))
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(
            text, json.dumps(obj, sort_keys=True, indent=2) + "\n")


class CsvTests(Base):
    def rows(self, result):
        return list(csv.reader(io.StringIO(report.render_csv(result))))

    def test_evil_name_neutralized(self):
        rows = self.rows(self.result)
        names = [r[rows[0].index("name")] for r in rows[1:]]
        self.assertIn("'" + EVIL, names)
        self.assertNotIn(EVIL, names)

    def test_each_leading_character(self):
        for lead in ("=", "+", "-", "@", "\t", "\r"):
            result = copy.deepcopy(self.result)
            result["items"][0]["name"] = lead + "x"
            rows = self.rows(result)
            got = rows[1][rows[0].index("name")]
            self.assertEqual(got, "'" + lead + "x", repr(lead))

    def test_other_text_columns_neutralized(self):
        result = copy.deepcopy(self.result)
        result["items"][0]["publisher"] = "=1+1"
        result["items"][0]["owners"] = ["@bob", "carol"]
        rows = self.rows(result)
        self.assertEqual(rows[1][rows[0].index("publisher")], "'=1+1")
        self.assertTrue(rows[1][rows[0].index("owners")].startswith("'@bob"))

    def test_plain_cell_unchanged_and_rows_complete(self):
        rows = self.rows(self.result)
        self.assertEqual(len(rows) - 1, len(self.result["items"]))
        self.assertIn("Example SQL", [r[rows[0].index("name")]
                                      for r in rows[1:]])


if __name__ == "__main__":
    unittest.main()
