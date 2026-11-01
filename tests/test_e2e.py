"""End to end: the demo estate against its answer key.

The demo (examples/) runs against the synthetic data in fixtures/data, so
the output never changes with the calendar. Regenerate the expected report
with UPDATE_GOLDEN=1 after a deliberate change.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpers import run_main
from swlc.assess import LISTS
from swlc.report import CLAIMS_LINE, DECISION_TEXT, KEV_LINE, MATCH_CAVEAT

EXAMPLES = ROOT / "examples"
DATA = ROOT / "tests" / "fixtures" / "data"
EXPECTED = ROOT / "tests" / "fixtures" / "expected-report.json"
_SPEC = importlib.util.spec_from_file_location(
    "demo_generate", EXAMPLES / "generate.py")
generate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(generate)
AS_OF = "2026-10-24"
DEMO_FILES = ("software-inventory.csv", "answer-key.json", "tracking.csv",
              "support-records.csv", "sample-report.md")


def check_args(out: Path, *extra) -> list:
    return ["check", str(EXAMPLES / "software-inventory.csv"),
            "--data", str(DATA), "--as-of", AS_OF,
            "--golden", str(EXAMPLES / "golden-sources.csv"),
            "--exceptions", str(EXAMPLES / "exceptions.csv"),
            "--tracking", str(EXAMPLES / "tracking.csv"),
            "--support-records", str(EXAMPLES / "support-records.csv"),
            "--out", str(out), *extra]


def read_demo_rows() -> list:
    with open(EXAMPLES / "software-inventory.csv", encoding="utf-8",
              newline="") as fh:
        return list(csv.DictReader(fh))


class DemoBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "out"
        cls.code, cls.stdout, cls.stderr = run_main(check_args(cls.out))
        cls.key = json.loads(
            (EXAMPLES / "answer-key.json").read_text(encoding="utf-8"))
        cls.report_text = (cls.out / "report.json").read_text(
            encoding="utf-8")
        cls.report = json.loads(cls.report_text)
        cls.md = (cls.out / "report.md").read_text(encoding="utf-8")
        cls.csv_text = (cls.out / "report.csv").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class AnswerKeyTests(DemoBase):
    def test_run_succeeds(self):
        self.assertEqual(self.code, 0, self.stderr)

    def test_inventory_size(self):
        self.assertEqual(len(read_demo_rows()), 60)

    def test_every_list_equals_the_key(self):
        self.assertEqual(sorted(self.key["lists"]), sorted(LISTS))
        for name in LISTS:
            self.assertEqual(sorted(self.report["lists"][name]),
                             sorted(self.key["lists"][name]), name)

    def test_lists_are_ordered_by_the_key_counts(self):
        cases = self.key["cases"]

        def rank(gid):
            count = cases[gid]["install_count"]
            return (count is None, -(count or 0), gid)
        for name in LISTS:
            self.assertEqual(self.report["lists"][name],
                             sorted(self.key["lists"][name], key=rank), name)

    def test_install_counts_match_the_key(self):
        items = {it["id"]: it for it in self.report["items"]}
        for gid, case in self.key["cases"].items():
            self.assertEqual(items[gid]["install_count"],
                             case["install_count"], case["case"])
        self.assertEqual(self.report["counts"]["count_invalid_cells"],
                         self.key["counts"]["count_invalid_cells"])
        self.assertGreater(self.key["counts"]["count_invalid_cells"], 0)

    def test_every_planted_case(self):
        items = {it["id"]: it for it in self.report["items"]}
        self.assertGreaterEqual(len(self.key["cases"]), 24)
        for gid, case in self.key["cases"].items():
            with self.subTest(case=case["case"]):
                it = items[gid]
                self.assertEqual(it["name"], case["name"])
                self.assertEqual(it["version"], case["version"])
                self.assertEqual(it["state"], case["state"])
                self.assertEqual(it["reason"], case["reason"])
                self.assertEqual(it["dates_disagree"],
                                 case["dates_disagree"])
                self.assertEqual(it["decision_needed"],
                                 case["decision_needed"])
                self.assertEqual(
                    sorted(n for n in LISTS
                           if gid in self.report["lists"][n]),
                    sorted(case["lists"]))
                if "classification" in case:
                    self.assertEqual(it["classification"],
                                     case["classification"])
                    src = it["inherited_from"]
                    self.assertEqual(
                        items[src]["state"] if src else None,
                        case["inherited_state"])
                    block = it["inherited_lifecycle"]
                    self.assertEqual(block["state"] if block else None,
                                     case["inherited_state"])

    def test_parent_cases_planted(self):
        names = {c["case"] for c in self.key["cases"].values()}
        for need in ("part-parent-past-eol", "part-parent-absent",
                     "os-patch-one-os"):
            self.assertIn(need, names)
        self.assertEqual(self.report["counts"]["inherited_attention"],
                         self.key["counts"]["inherited_attention"])
        self.assertGreater(self.key["counts"]["inherited_attention"], 0)

    def test_names_to_review_case(self):
        ids = [gid for gid, c in self.key["cases"].items()
               if c["case"] == "names_to_review"]
        self.assertEqual(len(ids), 1)
        flagged = [it["id"] for it in self.report["items"]
                   if it["ambiguity"]]
        self.assertEqual(flagged, ids)
        self.assertEqual(self.report["counts"]["ambiguous_review"], 1)
        self.assertIn("## Names to review (1)", self.md)

    def test_support_records_match_the_key(self):
        key = self.key["support_records"]
        filler = key.pop("filler:lanternviewer")
        self.assertEqual(self.report["counts"]["support_records"],
                         self.key["counts"]["support_records"])
        for it in self.report["items"]:
            refs = sorted(e["record_ref"] for e in it["support_records"])
            if it["product"] == "lanternviewer" and it["cycle"]:
                want = filler
            else:
                want = key.get(it["id"], [])
            self.assertEqual(refs, want, it["id"])
        self.assertIn("## Support records", self.md)

    def test_case_names_are_unique(self):
        names = [c["case"] for c in self.key["cases"].values()]
        self.assertEqual(len(names), len(set(names)))


class GoldenReportTests(DemoBase):
    def test_whole_report_matches_committed_copy(self):
        if os.environ.get("UPDATE_GOLDEN"):
            EXPECTED.write_text(self.report_text, encoding="utf-8")
        self.assertEqual(self.report_text,
                         EXPECTED.read_text(encoding="utf-8"))


class MarkdownTests(DemoBase):
    def test_fixed_lines(self):
        self.assertIn(KEV_LINE, self.md)
        self.assertIn(CLAIMS_LINE, self.md)
        self.assertEqual(self.md.split("\n").count(MATCH_CAVEAT), 1)
        self.assertNotIn(MATCH_CAVEAT, self.report_text)
        self.assertNotIn(MATCH_CAVEAT, self.csv_text)

    def test_sample_report_is_this_run(self):
        # examples/sample-report.md is the demo's report.md, byte for byte,
        # plus the sample note under the title. Regenerate it with
        # python3 examples/generate.py.
        sample = (EXAMPLES / "sample-report.md").read_bytes()
        self.assertEqual(sample, generate.add_sample_note(
            self.md.encode("utf-8")))
        self.assertEqual(sample.count(generate.SAMPLE_NOTE), 1)
        # A real run's report.md never carries the note.
        self.assertNotIn("Sample note", self.md)

    def test_never_says_vulnerable(self):
        self.assertNotIn("vulnerable", self.md.lower())

    def test_decision_needed_names_roles(self):
        self.assertIn("**Decision needed:** " + DECISION_TEXT[
            "DIFFERENT_DATE"], self.md)
        self.assertIn("The ITAM lead settles", self.md)
        self.assertIn("an independent approver sign off", self.md)

    def test_one_findings_fence(self):
        self.assertEqual(self.md.count("```findings"), 1)
        self.assertEqual(self.md.count("```"), 2)

    def test_hostile_names_are_safe(self):
        self.assertNotIn("<script>", self.md)
        self.assertIn("&lt;script&gt;", self.md)
        self.assertIn("\\|", self.md)
        self.assertIn("\\`rm", self.md)
        names = {r["name"]: r for r in csv.DictReader(
            self.csv_text.splitlines(keepends=True))}
        self.assertIn("'=cmd|' /C calc'!A0", names)
        self.assertEqual(names["'=cmd|' /C calc'!A0"]["state"], "unmatched")


class CountsOnlyTests(unittest.TestCase):
    def test_no_inventory_text_reaches_the_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_main(
                check_args(Path(tmp) / "out", "--counts-only"))
        self.assertEqual(code, 0, err)
        self.assertIn("past_eol ", out)
        seen = out + err
        for row in read_demo_rows():
            for field in ("Software Name", "Publisher", "Owner"):
                if row[field]:
                    self.assertNotIn(row[field], seen, row[field])


class GeneratorTests(unittest.TestCase):
    def run_generate(self, dest: Path) -> None:
        subprocess.run([sys.executable, "-B", str(EXAMPLES / "generate.py"),
                        str(dest)], check=True, capture_output=True,
                       cwd=str(dest))

    def test_two_runs_are_byte_identical_and_match_committed(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "a", Path(tmp) / "b"
            first.mkdir()
            second.mkdir()
            self.run_generate(first)
            self.run_generate(second)
            for name in DEMO_FILES:
                data = (first / name).read_bytes()
                self.assertEqual(data, (second / name).read_bytes(), name)
                self.assertEqual(data, (EXAMPLES / name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
