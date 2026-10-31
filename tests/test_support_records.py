"""Support records (issue #32): the loader, how records fit items, and the
report views. A record is shown beside the dates and changes nothing else.
All references, products and owners here are synthetic."""
from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpers import run_main
from swlc import cli, report
from swlc.errors import InputError
from swlc.support import COLUMNS, MAX_KIND, MAX_REF, load_support_records

DATA = ROOT / "tests" / "fixtures" / "data"
EXAMPLES = ROOT / "examples"
AS_OF = date(2026, 10, 24)
HEADER = ",".join(COLUMNS) + "\n"
PRODUCTS = {"tidewatersuite", "brightlineeditor", "examplesql"}
SECRET = "SECRETXYZ"

INVENTORY = [
    ("Tidewater Suite", "4.2", "Example Corp"),   # past_eol, cycle 4
    ("Tidewater Suite", "5.0", "Example Corp"),   # ends_soon, cycle 5
    ("Tidewater Suite", "5.1", "Example Corp"),   # ends_soon, cycle 5
    ("Tidewater Suite", "6.1", "Example Corp"),   # supported, cycle 6
    ("Brightline Editor", "9.0", "Fictional Software Ltd"),  # NO_CYCLE
    ("Mystery Tool", "3.1", "Nobody Inc"),        # NO_ALIAS
]
RECORDS = [
    # ref, product, scope, kind, ends_on, owner_role
    ("SR-ALL", "tidewatersuite", "", "vendor support", "2028-01-31",
     "Application owner"),
    ("SR-C5", "tidewatersuite", "5", "extended support", "2027-03-01", ""),
    ("SR-V51", "tidewatersuite", "5.1", "extended support", "2026-01-31",
     "ITAM lead"),
    ("SR-C4", "tidewatersuite", "4", "extended support", "2027-06-30",
     "Platform lead"),
    ("SR-NONE", "tidewatersuite", "99", "a|b support", "2027-02-28", ""),
    ("SR-BL", "brightlineeditor", "", "vendor support", "2029-01-31", ""),
    ("=HYPERLINK(1)", "tidewatersuite", "6.1", "vendor support",
     "2027-12-01", ""),
]
BANNED_WORDS = ("covered", "licensed", "unlicensed", "shelfware",
                "compliant", "non-compliant", "audit-ready", "over-licensed")


def csv_text(rows) -> str:
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, data, name="sr.csv") -> str:
        path = self.dir / name
        path.write_bytes(data if isinstance(data, bytes)
                         else data.encode("utf-8"))
        return str(path)

    def inventory(self, rows=INVENTORY) -> str:
        return self.write(csv_text([("name", "version", "publisher",
                                     "owner")] +
                                   [r + ("Team A",) for r in rows]),
                          "inv.csv")

    def records_file(self, records=RECORDS, name="sr.csv") -> str:
        return self.write(HEADER + csv_text(
            [("1",) + tuple(r) for r in records]), name)

    def assert_quiet_error(self, data, *words):
        """InputError naming the given words, with no cell text in it."""
        with self.assertRaises(InputError) as cm:
            load_support_records(self.write(data), PRODUCTS)
        text = str(cm.exception)
        self.assertNotIn(SECRET, text)
        self.assertNotIn("tidewater", text)
        for word in words:
            self.assertIn(word, text)
        return text


def row(**kw) -> str:
    base = {"schema_version": "1", "record_ref": "SR-" + SECRET,
            "product": "tidewatersuite", "scope": "", "kind": "support " +
            SECRET, "ends_on": "2027-01-31", "owner_role": SECRET}
    base.update(kw)
    return csv_text([[base[c] for c in COLUMNS]])


class LoaderTests(Base):
    def test_none_is_none(self):
        self.assertIsNone(load_support_records(None, PRODUCTS))

    def test_valid_file(self):
        got = load_support_records(self.records_file(), PRODUCTS)
        self.assertEqual(len(got), len(RECORDS))
        self.assertEqual([r["ends_on"] for r in got],
                         sorted(r["ends_on"] for r in got))
        first = got[0]
        self.assertEqual(first["record_ref"], "SR-V51")
        self.assertEqual(first["ends_on"], date(2026, 1, 31))
        self.assertEqual(first["owner_role"], "ITAM lead")
        self.assertIsNone([r for r in got if r["record_ref"] == "SR-C5"][0][
            "owner_role"])

    def test_header_only_is_empty(self):
        self.assertEqual(load_support_records(self.write(HEADER), PRODUCTS),
                         [])

    def test_empty_file_raises(self):
        with self.assertRaises(InputError):
            load_support_records(self.write(b""), PRODUCTS)

    def test_each_column_missing(self):
        for col in COLUMNS:
            with self.subTest(col=col):
                cols = [c for c in COLUMNS if c != col]
                data = ",".join(cols) + "\n" + ",".join(
                    "1" if c == "schema_version" else SECRET
                    for c in cols) + "\n"
                self.assert_quiet_error(data, "missing required", col)

    def test_each_required_value_empty(self):
        for col in ("record_ref", "product", "kind", "ends_on"):
            with self.subTest(col=col):
                self.assert_quiet_error(HEADER + row(**{col: ""}),
                                        col, "data row 1")

    def test_optional_values_may_be_empty(self):
        got = load_support_records(
            self.write(HEADER + row(scope="", owner_role="")), PRODUCTS)
        self.assertEqual(got[0]["scope"], "")
        self.assertIsNone(got[0]["owner_role"])

    def test_duplicate_record_ref(self):
        data = HEADER + row() + row(record_ref=" sr-" + SECRET.lower())
        self.assert_quiet_error(data, "data row 2", "record_ref")

    def test_unknown_product_id(self):
        for value in ("nosuchproduct", "Tidewater Suite", "TIDEWATERSUITE"):
            with self.subTest(value=value):
                data = HEADER + row() + row(record_ref="SR-2",
                                            product=value)
                text = self.assert_quiet_error(data, "data row 2",
                                               "product")
                self.assertNotIn(value, text)

    def test_bad_dates(self):
        for value in ("31/01/2027", "2027-02-30", "2027-1-31", SECRET):
            with self.subTest(value=value):
                text = self.assert_quiet_error(HEADER + row(ends_on=value),
                                               "ends_on", "data row 1")
                self.assertNotIn(value, text)

    def test_schema_version(self):
        self.assert_quiet_error(HEADER + row(schema_version="2"),
                                "schema_version")

    def test_extra_columns_are_ignored(self):
        data = (HEADER.strip() + ",quantity,cost\n"
                + row().strip() + ",500,999\n")
        got = load_support_records(self.write(data), PRODUCTS)
        self.assertEqual(sorted(got[0]), ["ends_on", "kind", "owner_role",
                                          "product", "record_ref", "scope"])

    def test_crlf_and_bom(self):
        data = ("﻿" + HEADER + row()).replace("\n", "\r\n")
        got = load_support_records(self.write(data.encode("utf-8")),
                                   PRODUCTS)
        self.assertEqual(got[0]["record_ref"], "SR-" + SECRET)
        self.assertEqual(got[0]["owner_role"], SECRET)

    def test_header_case_is_ignored(self):
        got = load_support_records(self.write(HEADER.upper() + row()),
                                   PRODUCTS)
        self.assertEqual(len(got), 1)

    def test_length_limits(self):
        for col, limit in (("record_ref", MAX_REF), ("kind", MAX_KIND),
                           ("scope", 64), ("owner_role", 80)):
            with self.subTest(col=col):
                ok = load_support_records(self.write(
                    HEADER + row(**{col: "x" * limit})), PRODUCTS)
                self.assertEqual(len(ok), 1)
                self.assert_quiet_error(
                    HEADER + row(**{col: SECRET + "x" * limit}), col,
                    "longer than %d" % limit)

    def test_huge_field(self):
        self.assert_quiet_error(HEADER + row(kind=SECRET * 10000),
                                "longer than")

    def test_formula_characters_are_kept_as_text(self):
        data = HEADER + row(record_ref="=SUM(1)", kind="@cmd",
                            owner_role="+x")
        got = load_support_records(self.write(data), PRODUCTS)
        self.assertEqual((got[0]["record_ref"], got[0]["kind"]),
                         ("=SUM(1)", "@cmd"))

    def test_not_utf8(self):
        data = (HEADER + row(kind="caf\xe9 " + SECRET)).encode("latin-1")
        self.assert_quiet_error(data, "not valid utf-8")

    def test_malformed_csv(self):
        self.assert_quiet_error(HEADER + '1,"SR-%s,x\n' % SECRET)


class FitTests(Base):
    """Which items get which records (product and scope rules)."""

    @classmethod
    def setUpClass(cls):
        cls._ctmp = tempfile.TemporaryDirectory()
        base = Base()
        base.dir = Path(cls._ctmp.name)
        cls.inv = base.inventory()
        cls.sr = base.records_file()
        cls.report = cli.run(cls.inv, data=str(DATA), as_of=AS_OF,
                             support_records=cls.sr)
        cls.plain = cli.run(cls.inv, data=str(DATA), as_of=AS_OF)
        cls.items = {(it["name"], it["version"]): it
                     for it in cls.report["items"]}

    @classmethod
    def tearDownClass(cls):
        cls._ctmp.cleanup()

    def refs(self, name, version):
        return [e["record_ref"]
                for e in self.items[(name, version)]["support_records"]]

    def test_states_are_as_planted(self):
        states = {k: it["state"] for k, it in self.items.items()}
        self.assertEqual(states[("Tidewater Suite", "4.2")], "past_eol")
        self.assertEqual(states[("Tidewater Suite", "5.0")], "ends_soon")
        self.assertEqual(states[("Tidewater Suite", "6.1")], "supported")
        self.assertEqual(states[("Brightline Editor", "9.0")], "unmatched")
        self.assertEqual(
            self.items[("Brightline Editor", "9.0")]["product"],
            "brightlineeditor")

    def test_product_only_fits_every_matched_cycle(self):
        for version in ("4.2", "5.0", "5.1", "6.1"):
            self.assertIn("SR-ALL", self.refs("Tidewater Suite", version))

    def test_scope_cycle_label(self):
        self.assertIn("SR-C5", self.refs("Tidewater Suite", "5.0"))
        self.assertIn("SR-C5", self.refs("Tidewater Suite", "5.1"))
        self.assertNotIn("SR-C5", self.refs("Tidewater Suite", "4.2"))
        self.assertEqual(self.refs("Tidewater Suite", "4.2"),
                         ["SR-C4", "SR-ALL"])

    def test_scope_version(self):
        self.assertIn("SR-V51", self.refs("Tidewater Suite", "5.1"))
        self.assertNotIn("SR-V51", self.refs("Tidewater Suite", "5.0"))

    def test_multiple_records_sorted_by_date_then_ref(self):
        self.assertEqual(self.refs("Tidewater Suite", "5.1"),
                         ["SR-V51", "SR-C5", "SR-ALL"])
        entry = self.items[("Tidewater Suite", "5.1")]["support_records"][0]
        self.assertEqual(entry, {"record_ref": "SR-V51",
                                 "kind": "extended support",
                                 "ends_on": "2026-01-31",
                                 "owner_role": "ITAM lead"})

    def test_unmatched_items_never_get_a_record(self):
        for it in self.report["items"]:
            if it["state"] == "unmatched":
                self.assertEqual(it["support_records"], [], it["name"])

    def test_counts(self):
        self.assertEqual(self.report["counts"]["support_records"],
                         {"listed": 5, "ending_soon": 3,
                          "nothing_found": 2})

    def test_window_edges_are_inclusive(self):
        recs = [("SR-TODAY", "tidewatersuite", "", "k", "2026-10-24", ""),
                ("SR-END", "tidewatersuite", "", "k", "2027-10-24", ""),
                ("SR-AFTER", "tidewatersuite", "", "k", "2027-10-25", ""),
                ("SR-BEFORE", "tidewatersuite", "", "k", "2026-10-23", "")]
        r = cli.run(self.inv, data=str(DATA), as_of=AS_OF,
                    support_records=self.records_file(recs, "edge.csv"))
        self.assertEqual(r["counts"]["support_records"]["ending_soon"], 2)
        r6 = cli.run(self.inv, data=str(DATA), as_of=AS_OF,
                     lookahead_months=13,
                     support_records=self.records_file(recs, "edge.csv"))
        self.assertEqual(r6["counts"]["support_records"]["ending_soon"], 3)

    def test_nothing_else_changes(self):
        stripped = copy.deepcopy(self.report)
        for it in stripped["items"]:
            del it["support_records"]
        del stripped["counts"]["support_records"]
        plain = copy.deepcopy(self.plain)
        for it in plain["items"]:
            self.assertEqual(it.pop("support_records"), [])
        self.assertEqual(plain["counts"].pop("support_records"),
                         {"listed": 0, "ending_soon": 0, "nothing_found": 0})
        self.assertEqual(stripped, plain)

    def test_key_present_on_every_item_without_a_file(self):
        self.assertTrue(all(it["support_records"] == []
                            for it in self.plain["items"]))


class DemoViews(Base):
    """The demo run with and without the support-records file."""

    def run_demo(self, name, *extra, records=True):
        out = self.dir / name
        argv = ["check", str(EXAMPLES / "software-inventory.csv"),
                "--data", str(DATA), "--as-of", "2026-10-24",
                "--golden", str(EXAMPLES / "golden-sources.csv"),
                "--exceptions", str(EXAMPLES / "exceptions.csv"),
                "--tracking", str(EXAMPLES / "tracking.csv"),
                "--out", str(out), *extra]
        if records:
            argv += ["--support-records",
                     str(EXAMPLES / "support-records.csv")]
        code, stdout, stderr = run_main(argv)
        return code, stdout, stderr, out

    def files(self, out):
        return {n: (out / n).read_text(encoding="utf-8")
                for n in cli.OUTPUT_FILES}

    def section(self, md, heading):
        start = md.index("\n## %s" % heading)
        end = md.find("\n## ", start + 4)
        fence = md.find("\n```findings", start)
        end = min(e for e in (end, fence) if e > 0)
        return md[start:end]

    def test_note_lines_only_in_past_and_ends_soon(self):
        _c, _o, _e, out = self.run_demo("a")
        md = self.files(out)["report.md"]
        rep = json.loads(self.files(out)["report.json"])
        items = {it["id"]: it for it in rep["items"]}
        lines = [l for l in md.split("\n")
                 if "A support record is listed in your file" in l]
        want = []
        for name in report.SUPPORT_SECTIONS:
            for gid in rep["lists"][name]:
                want += items[gid]["support_records"]
        self.assertEqual(len(lines), len(want))
        self.assertGreater(len(lines), 0)
        for name, heading, _f in report.SECTIONS:
            sec = self.section(md, heading)
            has = "A support record is listed in your file" in sec
            if name not in report.SUPPORT_SECTIONS:
                self.assertFalse(has, heading)
        self.assertIn("  - A support record is listed in your file: SR-1002, "
                      "extended support, ended on 2026-06-30.", md)
        self.assertIn("  - A support record is listed in your file: SR-1001, "
                      "extended support, ends on 2027-06-30.", md)
        # A supported item's record is in the CSV and JSON, not in report.md.
        self.assertNotIn("SR-1007", md)

    def test_section(self):
        _c, _o, _e, out = self.run_demo("b")
        md = self.files(out)["report.md"]
        sec = self.section(md, report.SUPPORT_HEADING)
        self.assertIn(report.SUPPORT_LEAD, sec)
        for line in ("The tool does not check that a record was paid for "
                     "or is current.", "Discovery coverage is unknown",
                     "Extended support may cover only some fixes or "
                     "editions.", "Record references are confidential"):
            self.assertIn(line, sec)
        self.assertIn("Listed against items in this inventory: 5. Ending "
                      "within the lookahead window: 2. Nothing found in "
                      "this inventory: 2.", sec)
        soon = sec.split("Ending within the lookahead window (2):")[1]
        soon = soon.split("Nothing found")[0]
        self.assertEqual(re.findall(r"SR-\d+", soon), ["SR-1005", "SR-1001"])
        none = sec.split("Nothing found in this inventory (2):")[1]
        self.assertEqual(re.findall(r"SR-\d+", none), ["SR-1005", "SR-1006"])
        self.assertIn("- SR-1006, product brightlineeditor, vendor support, "
                      "ends on 2028-12-31.", none)
        for name in ("Tidewater", "Copperfield", "Brightline", "Finance"):
            self.assertNotIn(name, sec)
        self.assertLess(md.index("## Golden source overrides"),
                        md.index("## Support records"))

    def test_section_absent_without_file_and_none_when_empty(self):
        _c, _o, _e, out = self.run_demo("c", records=False)
        md = self.files(out)["report.md"]
        self.assertNotIn("## Support records", md)
        self.assertNotIn("support record", md.lower())
        self.assertIn("Support records (from your file)",
                      self.files(out)["report.csv"].split("\n")[0])
        empty = self.write(HEADER, "empty.csv")
        code, _o, err, out = self.run_demo("d", "--support-records", empty,
                                           records=False)
        self.assertEqual(code, 0, err)
        sec = self.section(self.files(out)["report.md"], "Support records")
        self.assertEqual(sec.count("None."), 2)

    def test_csv_column(self):
        _c, _o, _e, out = self.run_demo("e")
        rows = list(csv.DictReader(io.StringIO(
            self.files(out)["report.csv"])))
        self.assertEqual(list(rows[0])[-1], report.SUPPORT_COLUMN)
        self.assertEqual(list(rows[0])[:-1], list(report.CSV_COLUMNS[:-1]))
        cells = {r["id"]: r[report.SUPPORT_COLUMN] for r in rows}
        rep = json.loads(self.files(out)["report.json"])
        for it in rep["items"]:
            self.assertEqual(bool(cells[it["id"]]),
                             bool(it["support_records"]), it["id"])
        lantern = [c for gid, c in cells.items() if "SR-1007" in c]
        self.assertTrue(lantern)
        self.assertEqual(lantern[0], "SR-1007, vendor support, ends on "
                         "2027-12-31, owner role Desktop lead")

    def test_csv_and_md_guard_record_text(self):
        inv = self.inventory()
        sr = self.records_file()
        code, _o, err = run_main(["check", inv, "--data", str(DATA),
                                  "--as-of", "2026-10-24", "--out",
                                  str(self.dir / "g"), "--support-records",
                                  sr])
        self.assertEqual(code, 0, err)
        rows = list(csv.DictReader(io.StringIO(
            (self.dir / "g" / "report.csv").read_text("utf-8"))))
        cell = [r for r in rows if r["version"] == "6.1"][0][
            report.SUPPORT_COLUMN]
        self.assertTrue(cell.startswith("'=HYPERLINK(1)"), cell)
        md = (self.dir / "g" / "report.md").read_text("utf-8")
        self.assertIn("a\\|b support", md)
        self.assertNotIn("a|b support", md)

    def test_counts_only_line_has_no_record_text(self):
        code, stdout, stderr, _out = self.run_demo("f", "--counts-only")
        self.assertEqual(code, 0, stderr)
        lines = stdout.split("\n")
        self.assertIn("support_records listed=5 ending_soon=2 "
                      "nothing_found=2", lines)
        at = lines.index("support_records listed=5 ending_soon=2 "
                         "nothing_found=2")
        self.assertTrue(lines[at - 1].startswith("ambiguous_review "))
        with open(EXAMPLES / "support-records.csv", encoding="utf-8",
                  newline="") as fh:
            for rec in csv.DictReader(fh):
                for col in ("record_ref", "product", "scope", "kind",
                            "ends_on", "owner_role"):
                    if len(rec[col]) > 2:
                        self.assertNotIn(rec[col], stdout + stderr, col)
        self.assertNotIn("SR-", stdout)

    def test_counts_only_line_without_a_file(self):
        _c, stdout, _e, _o = self.run_demo("g2", "--counts-only",
                                           records=False)
        self.assertIn("support_records listed=0 ending_soon=0 "
                      "nothing_found=0\n", stdout)

    def test_counts_only_error_leaves_out_file_content(self):
        bad = self.write(HEADER + row(product="no" + SECRET), "bad.csv")
        code, stdout, stderr, _o = self.run_demo(
            "h", "--counts-only", "--support-records", bad, records=False)
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn(cli.QUIET_TEXT, stderr)
        self.assertNotIn(SECRET, stdout + stderr)
        code, _o, stderr, _out = self.run_demo(
            "i", "--support-records", bad, records=False)
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("data row 1", stderr)
        self.assertNotIn(SECRET, stderr)

    def test_governable_only_leaves_json_identical(self):
        _c, _o, _e, a = self.run_demo("j")
        _c, _o, _e, b = self.run_demo("k", "--governable-only")
        self.assertEqual(self.files(a)["report.json"],
                         self.files(b)["report.json"])
        self.assertIn("## Support records", self.files(b)["report.md"])

    def test_fail_on_is_unaffected(self):
        for name in cli.FAIL_ON_NAMES:
            with self.subTest(name=name):
                with_rec = self.run_demo("w" + name, "--fail-on", name)
                without = self.run_demo("o" + name, "--fail-on", name,
                                        records=False)
                self.assertEqual(with_rec[0], without[0])
                self.assertEqual(with_rec[2], without[2])
                a = json.loads((with_rec[3] / "report.json").read_text())
                b = json.loads((without[3] / "report.json").read_text())
                self.assertEqual(a["lists"], b["lists"])
                self.assertEqual(
                    {k: v for k, v in a["counts"].items()
                     if k != "support_records"},
                    {k: v for k, v in b["counts"].items()
                     if k != "support_records"})

    def test_previous_diff_both_ways(self):
        _c, _o, _e, new = self.run_demo("p1")
        old_report = json.loads(self.files(new)["report.json"])
        for it in old_report["items"]:
            del it["support_records"]
        del old_report["counts"]["support_records"]
        old = self.write(json.dumps(old_report), "old.json")
        code, _o, err, out = self.run_demo("p2", "--previous", old)
        self.assertEqual(code, 0, err)
        diff = json.loads(self.files(out)["report.json"])["diff"]
        self.assertEqual(diff, {"available": True, "new": [],
                                "resolved": [], "changed_state": []})
        code, _o, err, out = self.run_demo(
            "p3", "--previous", str(new / "report.json"), records=False)
        self.assertEqual(code, 0, err)
        diff = json.loads(self.files(out)["report.json"])["diff"]
        self.assertTrue(diff["available"])
        self.assertEqual(diff["changed_state"], [])

    def test_banned_words_absent(self):
        _c, _o, _e, out = self.run_demo("z")
        texts = dict(self.files(out))
        texts["swlc/support.py"] = (ROOT / "swlc" / "support.py").read_text(
            encoding="utf-8")
        texts["swlc/report.py"] = (ROOT / "swlc" / "report.py").read_text(
            encoding="utf-8")
        for rel in ("README.md", "SECURITY.md", "CHANGELOG.md",
                    "docs/usage.md", "docs/report-schema.md", "docs/sop.md",
                    "docs/themes.md", "examples/support-records.csv",
                    "examples/README.md", "templates/support-records.csv"):
            body = (ROOT / rel).read_text(encoding="utf-8")
            # The one place the words may appear: the never-use list.
            body = re.sub(r"Words the tool never uses about a record:[^.]*\.",
                          "", " ".join(body.split()))
            texts[rel] = body
        pattern = re.compile(r"(?<![\w-])(%s)(?![\w-])" % "|".join(
            re.escape(w) for w in BANNED_WORDS), re.I)
        for name, body in texts.items():
            self.assertIsNone(pattern.search(body), name)
        self.assertIn("Words the tool never uses about a record:",
                      " ".join((ROOT / "docs" / "usage.md").read_text(
                          encoding="utf-8").split()))

    def test_the_scan_catches_a_planted_word(self):
        pattern = re.compile(r"(?<![\w-])(%s)(?![\w-])" % "|".join(
            re.escape(w) for w in BANNED_WORDS), re.I)
        for word in BANNED_WORDS:
            self.assertTrue(pattern.search("This item is %s." % word), word)


if __name__ == "__main__":
    unittest.main()
