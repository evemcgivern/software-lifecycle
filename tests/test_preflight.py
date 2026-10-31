"""The preflight command: profile fit, columns, counts, and no cell text."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import run_main, write_inventory
from swlc import cli, preflight

# Distinctive synthetic cell values; none may reach stdout or stderr.
SECRETS = ["Zqxv Quokkasoft Suite", "Plumbline Wrenwick", "77.31.9q",
           "Ovenbird Tallyho", "=HYPERLINK(\"zqxv\")", "Gondolfo Brisket"]
SECRET_ROWS = [
    [SECRETS[0], SECRETS[1], SECRETS[2], SECRETS[3]],
    [SECRETS[4], SECRETS[1], "", SECRETS[5]],
    ["n/a", "unknown", "1.0", SECRETS[3]],
]


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def inv(self, header, rows, name="inv.csv"):
        return write_inventory(self.root / name, rows, header)

    def pre(self, *argv):
        return run_main(["preflight", *argv])

    def pre_json(self, *argv):
        code, out, err = self.pre(*argv, "--json")
        return code, json.loads(out), err

    def assert_no_secrets(self, *texts):
        for text in texts:
            for secret in SECRETS + ["Quokkasoft", "Wrenwick", "Ovenbird",
                                     "Brisket", "HYPERLINK", "zqxv"]:
                self.assertNotIn(secret, text)


class ProfileTests(Base):
    def best(self, header):
        path = self.inv(header, [["a", "b", "1", "2"][:len(header)]])
        code, res, err = self.pre_json(path)
        self.assertEqual(code, 0, err)
        return res

    def test_each_profile_is_detected(self):
        cases = {
            "flexera": ["Application name", "Publisher", "Version",
                        "Installed"],
            "servicenow-mbs": ["display_name", "publisher", "version"],
            "rapid7": ["name", "vendor", "version"],
            "generic": ["Product", "Publisher", "Version"],
        }
        for expected, header in cases.items():
            with self.subTest(expected):
                res = self.best(header)
                self.assertEqual(res["profile"]["best"], expected)
                self.assertEqual(res["profile"]["used"], expected)
                self.assertTrue(res["profile"]["how"])

    def test_flexera_fit_finds_its_count_column(self):
        res = self.best(["Application name", "Publisher", "Version",
                         "Installed"])
        self.assertEqual(res["columns"]["count"], "Installed")
        self.assertIn("--profile flexera", res["next_command"])
        self.assertEqual(res["profile"]["status"], "Unverified")

    def test_explicit_profile_is_used_and_better_fit_named(self):
        path = self.inv(["name", "vendor", "version"], [["a", "b", "1"]])
        code, res, _ = self.pre_json(path, "--profile", "flexera")
        self.assertEqual(code, 0)
        self.assertEqual(res["profile"]["used"], "flexera")
        self.assertEqual(res["profile"]["best"], "rapid7")
        self.assertIn("OTHER_PROFILE", [f["code"] for f in res["fix"]])
        self.assertIn("--profile rapid7", res["next_command"])

    def test_unknown_profile_is_a_usage_error(self):
        path = self.inv(["Name", "Version"], [["a", "1"]])
        code, out, err = self.pre(path, "--profile", "nope")
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("unknown profile", err)

    def test_columns_file_adds_headings(self):
        path = self.inv(["Thing", "Rev"], [["a", "1"]])
        cols = self.root / "cols.json"
        cols.write_text(json.dumps({"name": ["Thing"], "version": ["Rev"]}))
        code, res, _ = self.pre_json(path, "--columns", str(cols))
        self.assertEqual(code, 0)
        self.assertEqual(res["columns"]["name"], "Thing")
        self.assertIn("--columns", res["next_command"])


class ColumnTests(Base):
    def test_missing_required_column_exits_3_and_says_so(self):
        path = self.inv(["Product", "Publisher"], [["a", "b"]])
        code, out, err = self.pre(path)
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("version: not found", out)
        self.assertIn("[must fix] No version column was found", out)
        self.assertIn("Next command, after the must-fix items", out)

    def test_missing_optional_columns_warn_and_exit_0(self):
        path = self.inv(["Product", "Version"], [["a", "1"]])
        code, res, _ = self.pre_json(path)
        self.assertEqual(code, 0)
        self.assertTrue(res["ok"])
        codes = {f["code"]: f["blocking"] for f in res["fix"]}
        self.assertEqual(codes, {"NO_PUBLISHER": False, "NO_COUNT": False,
                                 "NO_PARENT": False})
        self.assertIsNone(res["columns"]["publisher"])

    def test_counts_blank_placeholder_and_formula_cells(self):
        path = self.inv(["Product", "Publisher", "Version", "Owner"],
                        SECRET_ROWS)
        code, res, _ = self.pre_json(path)
        self.assertEqual(code, 0)
        self.assertEqual(res["file"]["rows"], 3)
        self.assertEqual(res["blank_cells"]["version"], 1)
        # n/a as a name is matched as written, so it is not counted.
        self.assertEqual(res["placeholder_cells"], {})
        self.assertEqual(res["formula_cells"], 1)
        self.assertEqual(res["other_columns"], {"owner": "Owner"})

    def test_placeholders_count_for_the_parent_column(self):
        path = self.inv(["Product", "Version", "Parent"],
                        [["n/a", "1", "n/a"], ["a", "1", "None"],
                         ["b", "1", "Suite"], ["c", "1", ""]])
        code, res, _ = self.pre_json(path)
        self.assertEqual(code, 0)
        self.assertEqual(res["placeholder_cells"], {"parent": 2})
        self.assertEqual(res["blank_cells"]["parent"], 1)
        self.assertIn("PLACEHOLDER", [f["code"] for f in res["fix"]])

    def test_control_characters_in_a_header_are_not_printed(self):
        path = self.inv(["\x1bName\x07", "Product", "Version"],
                        [["a", "b", "1"]])
        code, out, err = self.pre(path)
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("'?Name?'", err)
        code, out, err = self.pre(path, "--json")
        for text in (out, err):
            self.assertNotIn("\x1b", text)
            self.assertNotIn("\x07", text)
            self.assertNotIn("\\u001b", text)
        path = self.inv(["\x1bName", "Version"], [["a", "1"]], "ok.csv")
        code, res, err = self.pre_json(path)
        self.assertEqual(code, 0, err)
        self.assertEqual(res["columns"]["name"], "?Name")
        _, out, _ = self.pre(path)
        self.assertNotIn("\x1b", out)

    def test_duplicate_header_names_positions_only(self):
        path = self.root / "dup.csv"
        path.write_text("Product,product,Version\na,b,1\n", encoding="utf-8")
        code, out, err = self.pre(str(path))
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("duplicate column name at positions 1 and 2", err)
        self.assertNotIn("roduct", err)

    def test_header_conflict_is_bad_input(self):
        path = self.inv(["Name", "Product", "Version"], [["a", "b", "1"]])
        code, out, err = self.pre(path)
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("two columns map to field 'name'", err)


class FileTests(Base):
    def test_crlf_and_bom_are_noted(self):
        path = Path(self.inv(["Product", "Version"], [["a", "1"]]))
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
        code, res, _ = self.pre_json(str(path))
        self.assertEqual(code, 0)
        self.assertTrue(res["file"]["bom"])
        self.assertEqual(res["file"]["line_endings"], "CRLF")
        self.assertEqual(res["columns"]["name"], "Product")
        code, out, _ = self.pre(str(path))
        self.assertIn("UTF-8, with a byte order mark", out)
        self.assertIn("line endings: CRLF", out)

    def test_lf_file(self):
        path = self.root / "lf.csv"
        path.write_bytes(b"Product,Version\na,1\n")
        _, res, _ = self.pre_json(str(path))
        self.assertFalse(res["file"]["bom"])
        self.assertEqual(res["file"]["line_endings"], "LF")

    def test_empty_file_exits_3(self):
        path = self.root / "empty.csv"
        path.write_bytes(b"")
        code, out, err = self.pre(str(path))
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("input file is empty", err)
        self.assertEqual(out, "")

    def test_header_only_file_exits_3_with_report(self):
        path = self.root / "head.csv"
        path.write_bytes(b"Product,Version\n")
        code, res, _ = self.pre_json(str(path))
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertFalse(res["ok"])
        self.assertEqual(res["file"]["rows"], 0)
        self.assertEqual(res["fix"][0]["code"], "NO_ROWS")

    def test_missing_file_exits_3(self):
        code, out, err = self.pre(str(self.root / "nope.csv"))
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("cannot read input file", err)

    def test_directory_is_not_a_regular_file(self):
        code, out, err = self.pre(str(self.root))
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("input is not a regular file", err)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "no FIFOs on this platform")
    def test_fifo_is_refused_without_blocking(self):
        fifo = self.root / "pipe.csv"
        os.mkfifo(str(fifo))
        code, out, err = self.pre(str(fifo))
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("input is not a regular file", err)

    @unittest.skipUnless(os.path.exists("/dev/zero"), "no /dev/zero")
    def test_device_is_refused(self):
        code, out, err = self.pre("/dev/zero")
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("input is not a regular file", err)

    def test_oversize_file_exits_3(self):
        path = self.inv(["Product", "Version"], [["a", "1"]] * 20)
        with mock.patch("swlc.inputs.MAX_BYTES", 50):
            code, out, err = self.pre(path)
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("larger than 50 bytes", err)

    def test_row_cap_exits_3(self):
        path = self.inv(["Product", "Version"], [["a", "1"]] * 5)
        with mock.patch("swlc.inputs.MAX_ROWS", 3):
            code, out, err = self.pre(path)
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertIn("more than 3 data rows", err)

    def test_preflight_writes_nothing(self):
        path = self.inv(["Product", "Version"], [["a", "1"]])
        before = sorted(p.name for p in self.root.iterdir())
        self.pre(path)
        self.pre(path, "--json")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), before)


class OutputTests(Base):
    def test_json_shape(self):
        path = self.inv(["Product", "Publisher", "Version", "Owner"],
                        SECRET_ROWS)
        code, res, _ = self.pre_json(path)
        self.assertEqual(code, 0)
        self.assertEqual(set(res), {
            "preflight_version", "ok", "file", "limits", "profile",
            "columns", "other_columns", "blank_cells", "placeholder_cells",
            "formula_cells", "fix", "next_command"})
        self.assertEqual(set(res["file"]), {"readable", "encoding", "bom",
                                            "line_endings", "bytes", "rows"})
        self.assertEqual(set(res["limits"]),
                         {"max_rows", "max_bytes", "within"})
        self.assertEqual(set(res["profile"]),
                         {"best", "how", "used", "status", "scores"})
        self.assertEqual(list(res["columns"]), sorted(preflight.FIELDS))
        for item in res["fix"]:
            self.assertEqual(set(item), {"code", "blocking", "text"})
            self.assertEqual(item["text"], preflight.FIX_TEXT[item["code"]])

    def test_json_error_shape(self):
        path = self.root / "empty.csv"
        path.write_bytes(b"")
        code, res, err = self.pre_json(str(path))
        self.assertEqual(code, cli.EXIT_INPUT)
        self.assertEqual(res, {"preflight_version": 1, "ok": False,
                               "exit_code": 3,
                               "error": "input file is empty"})

    def test_output_is_deterministic(self):
        path = self.inv(["Product", "Publisher", "Version", "Owner"],
                        SECRET_ROWS)
        self.assertEqual(self.pre(path), self.pre(path))

    def test_next_command_is_the_check_command(self):
        path = self.inv(["Product", "Version"], [["a", "1"]])
        _, res, _ = self.pre_json(path)
        self.assertEqual(res["next_command"],
                         "python3 software_lifecycle.py check %s --out "
                         "../swlc-out" % path)

    def test_no_cell_value_on_success(self):
        path = self.inv(["Product", "Publisher", "Version", "Owner"],
                        SECRET_ROWS)
        for argv in ([path], [path, "--json"]):
            code, out, err = self.pre(*argv)
            self.assertEqual(code, 0, err)
            self.assert_no_secrets(out, err)

    def test_no_cell_value_on_error_paths(self):
        cases = []
        # Missing version column: blocking, exit 3.
        cases.append(self.inv(["Product", "Publisher"],
                              [r[:2] for r in SECRET_ROWS], "a.csv"))
        # Ragged row: malformed input.
        bad = self.root / "b.csv"
        bad.write_text("Product,Version\n%s,1,%s\n"
                       % (SECRETS[0], SECRETS[3]), encoding="utf-8")
        cases.append(str(bad))
        # Bad UTF-8 after a secret.
        enc = self.root / "c.csv"
        enc.write_bytes(("Product,Version\n%s,1\n" % SECRETS[5])
                        .encode("utf-8") + b"\xff\xfe,2\n")
        cases.append(str(enc))
        # Unbalanced quote.
        quote = self.root / "d.csv"
        quote.write_text('Product,Version\n"%s,1\n' % SECRETS[1],
                         encoding="utf-8")
        cases.append(str(quote))
        # No header row: the first data row has a repeated value.
        nohead = self.root / "e.csv"
        nohead.write_text("%s,%s\n1,2\n" % (SECRETS[0], SECRETS[0]),
                          encoding="utf-8")
        cases.append(str(nohead))
        dup = self.inv([SECRETS[3], SECRETS[3].upper(), "Version"],
                       [["a", "b", "1"]], "f.csv")
        cases.append(dup)
        for path in cases:
            for argv in ([path], [path, "--json"]):
                with self.subTest(path=Path(path).name, argv=argv):
                    code, out, err = self.pre(*argv)
                    self.assertEqual(code, cli.EXIT_INPUT)
                    self.assert_no_secrets(out, err)

    def test_banned_words_absent_from_output(self):
        path = self.inv(["Product"], [["a"]])
        _, out, _ = self.pre(path)
        text = out + " ".join(preflight.FIX_TEXT.values())
        for word in ("covered", "licensed", "shelfware", "compliant",
                     "audit-ready", "over-licensed", "percent", "%"):
            self.assertNotIn(word, text.lower())


if __name__ == "__main__":
    unittest.main()
