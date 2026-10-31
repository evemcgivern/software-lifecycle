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

from helpers import (EVIL, PARENT_HEADER, PARENT_ROWS, SCRIPT, make_data_dir,
                     write_inventory)
from swlc import report
from swlc.cli import build

AS_OF = date(2026, 10, 24)
KEV_LINE = ("The vendor and product appear in CISA KEV. This does not mean "
            "your version is affected.")
CLAIMS = ("Runs locally with no network by default; built to enterprise "
          "security practices; not independently assessed.")
CAVEAT = ("Matches rest on name and publisher only. Rows we could not tell "
          "apart are listed as unmatched. Check the source and cycle before "
          "relying on any row.")


class Base(unittest.TestCase):
    kev_date = "2026-10-22"
    inv_rows = None
    inv_header = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = make_data_dir(self.tmp.name, self.kev_date, "2026-10-20")
        self.inv = write_inventory(Path(self.tmp.name) / "inv.csv", self.inv_rows,
                                   self.inv_header)
        self.result, self.meta = build(self.inv, as_of=AS_OF, data=self.data)
        self.md = report.render_markdown(self.result, self.meta)

    def item(self, name, version=None):
        for it in self.result["items"]:
            if it["name"] == name and (version is None
                                       or it["version"] == version):
                return it
        raise KeyError(name)


class PartsBase(Base):
    inv_rows = PARENT_ROWS
    inv_header = PARENT_HEADER

    def section(self, heading):
        start = self.md.index(heading)
        end = self.md.index("\n## ", start + 1) if "\n## " in self.md[
            start + 1:] else self.md.index("```findings")
        return self.md[start:end]

    def block(self, name):
        it = self.item(name)
        start = self.md.index("(id `%s`)" % it["id"])
        end = self.md.index("\n- **", start) if "\n- **" in self.md[
            start:] else len(self.md)
        return self.md[start:end]


class ClassViewTests(PartsBase):
    def test_inherited_heading_and_label(self):
        self.assertEqual(report.INHERITED_HEADING,
                         "Parent's date (inherited, not this item's own)")
        self.assertIn(report.INHERITED_HEADING, report.CSV_COLUMNS)
        header = next(csv.reader(io.StringIO(
            report.render_csv(self.result))))
        self.assertIn(report.INHERITED_HEADING, header)
        part = self.block("Demo Addon")
        self.assertIn("  - Classification: bundle_member (basis: ", part)
        self.assertIn("  - %s: end of life " % report.INHERITED_HEADING, part)
        self.assertIn("per endoflife.date, state past end of life, from "
                      "parent Demo OS 1.0 (id `", part)
        self.assertNotIn("  - End of life:", part)
        sql = self.block("Example SQL")
        self.assertIn("  - End of life: ", sql)
        self.assertNotIn(report.INHERITED_HEADING, sql)
        self.assertIn("  - Classification: governable (basis: ", sql)

    def test_parent_without_a_date_and_absent_parent(self):
        self.assertIn("  - %s: parent has no date"
                      % report.INHERITED_HEADING, self.block("Evil Child"))
        gone = self.block("Gone Child")
        self.assertIn("  - Parent: demoos/2.0, not in this inventory. "
                      "No date shown.", gone)
        self.assertNotIn(report.INHERITED_HEADING, gone)

    def test_unmatched_section_leads_with_needs_review(self):
        sec = self.section("## Couldn't match")
        n = self.result["counts"]["unmatched_breakdown"]["needs_review"]
        self.assertEqual(n, 6)
        self.assertIn("## Couldn't match (11)\n\nNeeds review: 6. Parts with "
                      "a parent are listed in their own section.\n", sec)
        for name in ("Mystery Tool", "Lone Addon"):
            self.assertIn(self.item(name)["id"], sec)
        for name in ("Demo Addon", "Gone Child", "Evil Child"):
            self.assertNotIn(self.item(name)["id"], sec)
        parts = self.section("## Parts that could not be matched")
        self.assertIn("## Parts that could not be matched (5)", parts)
        for name in ("Demo Addon", "Gone Child", "Evil Child", "Script Child"):
            self.assertIn(self.item(name)["id"], parts)
        self.assertNotIn(self.item("Mystery Tool")["id"], parts)

    def test_parts_past_parent_section(self):
        sec = self.section("## Parts of a parent past or near end of life")
        self.assertIn("(2)", sec.split("\n")[0])
        self.assertEqual(self.result["counts"]["inherited_attention"], 2)
        self.assertIn(self.item("Demo Addon")["id"], sec)
        self.assertNotIn(self.item("Gone Child")["id"], sec)
        types = {f["type"] for f in json.loads(re.search(
            r"```findings\n(.*?)\n```", self.md, re.S).group(1))}
        self.assertEqual(types, {"past_eol", "ends_soon", "dates_disagree",
                                 "unmatched", "review_urgently"})
        self.assertNotIn(self.item("Demo Addon")["id"],
                         self.result["lists"]["past_eol"])

    def test_csv_appends_columns_in_order(self):
        cols = report.CSV_COLUMNS
        self.assertEqual(len(cols), 33)
        self.assertEqual(cols[:29], (
            "id", "name", "version", "publisher", "owners", "rows", "state",
            "reason", "product", "cycle", "eol_used", "eol_source",
            "eol_endoflife", "eol_export", "eol_export_raw", "support",
            "extended_support", "golden_applied", "golden_expired",
            "dates_disagree", "accepted_risk", "exception_expired",
            "decision_needed", "kev", "kev_stale", "change_ref",
            "problem_ref", "lists", "match_source"))
        self.assertEqual(cols[29:], ("classification", "parent_ref",
                                     report.INHERITED_HEADING,
                                     "Review reason"))
        rows = list(csv.DictReader(io.StringIO(
            report.render_csv(self.result))))
        by = {r["name"]: r for r in rows}
        part = by["Demo Addon"]
        self.assertEqual(part["classification"], "bundle_member")
        self.assertEqual(part["parent_ref"], "item:Demo OS 1.0")
        self.assertNotEqual(part[report.INHERITED_HEADING], "")
        self.assertEqual(by["Evil Child"][report.INHERITED_HEADING],
                         "parent has no date")
        self.assertEqual(by["Gone Child"]["parent_ref"], "product:demoos/2.0")
        self.assertEqual(by["Gone Child"][report.INHERITED_HEADING], "")
        self.assertEqual(by["Example SQL"]["parent_ref"], "")
        self.assertEqual(by["Mystery Tool"]["classification"], "unknown")

    def test_hostile_parent_cell_is_escaped(self):
        text = report.render_csv(self.result)
        for row in csv.reader(io.StringIO(text)):
            for cell in row:
                self.assertNotIn(cell[:1], ("=", "+", "@", "\t", "\r"), cell)
        by = {r["name"]: r for r in csv.DictReader(io.StringIO(text))}
        self.assertEqual(by["Evil Child"]["parent_ref"],
                         "item:'" + EVIL + " Suite")
        child = self.block("Script Child")
        self.assertNotIn("<script>", self.md)
        self.assertIn("Parent: &lt;script&gt;", child)
        self.assertNotIn(EVIL, self.md)
        self.assertNotIn(EVIL, child)


class MarkdownTests(Base):
    def test_section_order(self):
        heads = ["## Past end of life", "## Ends within the lookahead window",
                 "## Dates disagree", "## Couldn't match",
                 "## In CISA KEV, past or near end of life", "## Accepted risk", "## Ownerless",
                 "## Golden source overrides", "```findings"]
        pos = [self.md.index(h) for h in heads]
        self.assertEqual(pos, sorted(pos))

    def test_match_caveat_once_under_the_counts(self):
        lines = self.md.split("\n")
        self.assertEqual(lines.count(CAVEAT), 1)
        self.assertEqual(self.md.count(CAVEAT), 1)
        at = lines.index(CAVEAT)
        counts = [i for i, l in enumerate(lines) if l.startswith("Items: ")]
        first_section = min(i for i, l in enumerate(lines)
                            if l.startswith("## "))
        self.assertEqual(len(counts), 1)
        self.assertTrue(counts[0] < at < first_section)
        self.assertEqual(report.MATCH_CAVEAT, CAVEAT)

    def test_match_caveat_not_in_json_or_csv(self):
        self.assertNotIn(CAVEAT, report.render_json(self.result, self.meta))
        self.assertNotIn(CAVEAT, report.render_csv(self.result))

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
        sec = md.split("## In CISA KEV, past or near end of life")[1].split("## ")[0]
        self.assertIn("not current", sec)
        self.assertNotIn("None found", sec)


class JsonTests(Base):
    def test_canonical_and_meta(self):
        text = report.render_json(self.result, self.meta)
        obj = json.loads(text)
        self.assertEqual(obj["meta"]["tool_version"],
                         (Path(__file__).resolve().parents[1]
                          / "VERSION").read_text().strip())
        self.assertEqual(text, report.render_json(self.result, self.meta))
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(
            text, json.dumps(obj, sort_keys=True, indent=2) + "\n")


class MatchSourceTests(Base):
    def test_markdown_names_how_the_product_was_matched(self):
        self.assertIn("Product matched by a curated alias.", self.md)
        result = copy.deepcopy(self.result)
        for it in result["items"]:
            if it["match_source"] == "curated":
                it["match_source"] = "generated"
        md = report.render_markdown(result, self.meta)
        self.assertIn("Product matched by product title.", md)
        self.assertNotIn("Product matched by a curated alias.", md)

    def test_no_source_line_without_a_product(self):
        it = self.item("Mystery Tool")
        self.assertIsNone(it["match_source"])
        block = self.md[self.md.index("**Mystery Tool**"):]
        block = block[:block.index("\n- ")] if "\n- " in block else block
        self.assertNotIn("Product matched by", block)

    def test_csv_adds_match_source_as_the_last_column(self):
        rows = list(csv.reader(io.StringIO(report.render_csv(self.result))))
        self.assertEqual(rows[0][27:29], ["lists", "match_source"])
        col = rows[0].index("match_source")
        self.assertEqual({r[col] for r in rows[1:]}, {"curated", ""})


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

    def test_every_cell_is_quoted(self):
        result = copy.deepcopy(self.result)
        result["items"][0]["name"] = "a;=1+1"
        text = report.render_csv(result)
        self.assertIn('"a;=1+1"', text)
        for line in text.splitlines():
            self.assertTrue(line.startswith('"') and line.endswith('"'))
        self.assertEqual(self.rows(result)[1][1], "a;=1+1")

    def test_plain_cell_unchanged_and_rows_complete(self):
        rows = self.rows(self.result)
        self.assertEqual(len(rows) - 1, len(self.result["items"]))
        self.assertIn("Example SQL", [r[rows[0].index("name")]
                                      for r in rows[1:]])


if __name__ == "__main__":
    unittest.main()
