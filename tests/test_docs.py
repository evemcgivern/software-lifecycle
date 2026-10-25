"""Keep the docs, templates and crosswalk true to the code."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swlc import assess, cli, matching, overrides
from swlc.inputs import GENERIC_ALIASES, map_columns, read_rows
from swlc.report import CLAIMS_LINE, DECISION_TEXT, KEV_LINE

DOCS = ROOT / "docs"
TEMPLATES = ROOT / "templates"
README = ROOT / "README.md"
DEMO = ROOT / "examples" / "software-inventory.csv"
FIXTURE_DATA = ROOT / "tests" / "fixtures" / "data"

CROSSWALK_HEADER = [
    "id", "theme", "iso19770_1", "itil4", "iso20000_1", "cobit2019",
    "nist_800_53", "nist_csf2", "cis_v8", "iso27001", "summary", "verified",
    "unverified_columns"]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def doc_files() -> list:
    return [README] + sorted(DOCS.glob("*.md"))


def public_files() -> list:
    out = doc_files() + sorted(DOCS.glob("*.csv"))
    out += [p for p in sorted(TEMPLATES.iterdir()) if p.is_file()]
    return out


def sentences(body: str) -> list:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n\s*\n", body) if s.strip()]


class TemplateTests(unittest.TestCase):
    def test_override_templates_load_as_empty(self):
        p = TEMPLATES
        self.assertEqual(overrides.load_golden(str(p / "golden-sources.csv")).rows, {})
        self.assertEqual(
            overrides.load_exceptions(str(p / "exceptions.csv")).rows, {})
        self.assertEqual(overrides.load_tracking(str(p / "tracking.csv")), {})

    def test_override_template_columns_match_the_loader(self):
        for name, cols in (("golden-sources.csv", overrides._GOLDEN_COLS),
                           ("exceptions.csv", overrides._EXC_COLS),
                           ("tracking.csv", overrides._TRACK_COLS)):
            with open(TEMPLATES / name, newline="", encoding="utf-8") as fh:
                self.assertEqual(next(csv.reader(fh)), list(cols), name)
            self.assertEqual(cols[0], "schema_version")

    def test_inventory_template_maps(self):
        rows, headers = read_rows(str(TEMPLATES / "inventory-template.csv"),
                                  allow_empty=True)
        self.assertEqual(rows, [])
        found = map_columns(headers, None, None)
        self.assertEqual(sorted(found), sorted(GENERIC_ALIASES))

    def test_columns_example_is_accepted(self):
        obj = json.loads(text(TEMPLATES / "columns.example.json"))
        with tempfile.TemporaryDirectory() as tmp:
            cli._read_columns(str(TEMPLATES / "columns.example.json"))
        self.assertTrue(set(obj) <= set(GENERIC_ALIASES))


class CrosswalkTests(unittest.TestCase):
    def rows(self):
        with open(DOCS / "crosswalk.csv", newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            return header, [dict(zip(header, r)) for r in reader]

    def test_header_and_ids(self):
        header, rows = self.rows()
        self.assertEqual(header, CROSSWALK_HEADER)
        ids = [r["id"] for r in rows]
        self.assertEqual(ids, ["XW-029", "XW-030", "XW-031", "XW-032"])
        self.assertEqual(len(set(ids)), len(ids))

    def test_verified_rule(self):
        _, rows = self.rows()
        for r in rows:
            self.assertEqual(len(r), len(CROSSWALK_HEADER))
            if r["verified"].strip():
                self.assertEqual(r["unverified_columns"].strip(), "", r["id"])
            for col in r["unverified_columns"].split(";"):
                if col.strip():
                    self.assertIn(col.strip(), CROSSWALK_HEADER)

    def test_no_table_a1(self):
        self.assertNotIn("Table A.1", text(DOCS / "crosswalk.csv"))


class LinkTests(unittest.TestCase):
    def test_relative_links_resolve(self):
        link = re.compile(r"\]\(([^)\s]+)\)")
        for path in doc_files():
            for target in link.findall(text(path)):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue
                rel = target.split("#")[0]
                self.assertTrue((path.parent / rel).exists(),
                                "%s -> %s" % (path.name, target))


class FixedWordingTests(unittest.TestCase):
    def test_readme_lines(self):
        body = " ".join(text(README).split())
        self.assertEqual(body.count(CLAIMS_LINE), 1)
        self.assertEqual(body.count(KEV_LINE), 1)


def parser_flags() -> set:
    parser = cli._parser()
    flags = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                flags.add(name)
                for a in sub._actions:
                    flags.update(o for o in a.option_strings
                                 if o.startswith("--"))
    return flags


class UsageTests(unittest.TestCase):
    def test_every_flag_is_documented(self):
        body = text(DOCS / "usage.md")
        flags = parser_flags()
        self.assertIn("--counts-only", flags)
        for flag in flags:
            self.assertIn(flag, body)


def code_constants() -> set:
    out = set()
    for mod in (assess, matching):
        out |= {v for k, v in vars(mod).items()
                if isinstance(v, str) and k == v and k.isupper()}
    out |= set(DECISION_TEXT)
    return out


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = cli.run(str(DEMO), data=str(FIXTURE_DATA),
                             as_of=__import__("datetime").date(2026, 10, 24))
        cls.body = text(DOCS / "report-schema.md")

    def test_keys_documented(self):
        keys = set(self.report)
        for item in self.report["items"]:
            keys |= set(item)
        keys |= set(self.report["meta"])
        keys |= set(self.report["data_release"])
        keys |= set(self.report["counts"])
        keys |= set(self.report["diff"])
        self.assertIn("meta", keys)
        self.assertIn("decision_needed", keys)
        for key in keys:
            self.assertIn(key, self.body, key)

    def test_lists_documented(self):
        for name in assess.LISTS + assess.STATES:
            self.assertIn(name, self.body)

    def test_codes_documented(self):
        codes = code_constants()
        self.assertIn("DIFFERENT_DATE", codes)
        self.assertIn("NO_ALIAS", codes)
        for code in codes:
            self.assertIn(code, self.body, code)

    def test_override_columns_documented(self):
        for cols in (overrides._GOLDEN_COLS, overrides._EXC_COLS,
                     overrides._TRACK_COLS):
            for col in cols:
                self.assertIn(col, self.body, col)


BANNED = ["REDACTED", "REDACTED", "REDACTED", "REDACTED", "REDACTED",
          "REDACTED", "REDACTED", "job search", "portfolio", "resume",
          "/users/", "/applications/", "gmail"]


class BannedWordTests(unittest.TestCase):
    def test_banned_words(self):
        for path in public_files():
            low = text(path).lower()
            for word in BANNED:
                self.assertNotIn(word, low, "%s: %s" % (path.name, word))
            self.assertIsNone(re.search(r"\bREDACTED\b", low), path.name)
            self.assertIsNone(re.search(r"\bsigned\b", low), path.name)

    def test_bod_22_01_only_as_superseded(self):
        for path in public_files():
            for s in sentences(text(path)):
                if "BOD 22-01" in s:
                    self.assertIn("superseded", s, path.name)

    def test_vulnerable_only_in_never_sentence(self):
        for path in public_files():
            for s in sentences(text(path)):
                if "vulnerable" in s.lower():
                    self.assertIn("never", s.lower(), path.name)


class PlatformGuideTests(unittest.TestCase):
    def test_sources_section(self):
        body = text(DOCS / "platform-guide.md")
        self.assertIn("## Sources", body)
        sources = body.split("## Sources", 1)[1]
        for vendor in ("flexera", "servicenow", "rapid7"):
            self.assertRegex(sources.lower(), r"https://[^\s)]*%s" % vendor)

    def test_mbs_not_expanded(self):
        body = text(DOCS / "platform-guide.md").replace("servicenow-mbs", "")
        self.assertIsNone(re.search(r"\bmbs\b", body, re.I))


if __name__ == "__main__":
    unittest.main()
