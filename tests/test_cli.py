import hashlib
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import (FIXTURE_NAMES, FIXTURE_ROWS, make_data_dir, run_main,
                     write_inventory)
from swlc import cli

AS_OF = "2026-10-24"


class CliBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = make_data_dir(self.root, "2026-10-22", "2026-10-20")
        self.inv = write_inventory(self.root / "inv.csv")
        self.out = self.root / "out"

    def check(self, *extra, inv=None):
        return run_main(["check", inv or self.inv, "--data", self.data,
                         "--as-of", AS_OF, *extra])


class CheckTests(CliBase):
    def test_stdout_markdown_without_out(self):
        code, out, err = self.check()
        self.assertEqual(code, 0, err)
        self.assertIn("## Past end of life", out)
        self.assertIn("```findings", out)

    def test_out_writes_three_files_and_no_markdown_on_stdout(self):
        code, out, err = self.check("--out", str(self.out))
        self.assertEqual(code, 0, err)
        self.assertNotIn("## Past end of life", out)
        for name in ("report.json", "report.md", "report.csv"):
            path = self.out / name
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_two_runs_byte_identical(self):
        self.check("--out", str(self.root / "a"))
        self.check("--out", str(self.root / "b"))
        for name in ("report.json", "report.md", "report.csv"):
            self.assertEqual((self.root / "a" / name).read_bytes(),
                             (self.root / "b" / name).read_bytes())

    def test_run_equals_report_json(self):
        self.check("--out", str(self.out))
        parsed = json.loads((self.out / "report.json").read_text())
        got = cli.run(self.inv, as_of=date(2026, 10, 24), data=self.data)
        self.assertEqual(got, parsed)

    def test_override_hash_in_json(self):
        golden = self.root / "golden.csv"
        golden.write_text(
            "schema_version,product,source,manual_eol,reason,set_by,set_on,"
            "review_by\n1,examplesql,export,,test,me,2026-01-01,2027-01-01\n",
            encoding="utf-8")
        self.check("--golden", str(golden), "--out", str(self.out))
        obj = json.loads((self.out / "report.json").read_text())
        want = hashlib.sha256(golden.read_bytes()).hexdigest()
        self.assertEqual(obj["meta"]["override_hashes"]["golden"], want)
        self.assertEqual(obj["meta"]["override_hashes"]["exceptions"], "")

    def test_meta_data_release(self):
        self.check("--out", str(self.out))
        obj = json.loads((self.out / "report.json").read_text())
        self.assertEqual(obj["meta"]["data_release"]["id"], "fixture-1")
        self.assertIn("kev.json", obj["meta"]["data_release"]["file_hashes"])
        self.assertEqual(obj["meta"]["profile"]["name"], "generic")

    def test_previous_gives_diff(self):
        self.check("--out", str(self.out))
        code, _, err = self.check("--previous", str(self.out / "report.json"),
                                  "--out", str(self.root / "two"))
        self.assertEqual(code, 0, err)
        obj = json.loads((self.root / "two" / "report.json").read_text())
        self.assertTrue(obj["diff"]["available"])

    def test_bad_previous_exits_3(self):
        bad = self.root / "prev.json"
        for text in ("not json", '{"a": NaN}', '{"a": 1, "a": 2}'):
            bad.write_text(text)
            code, _, _ = self.check("--previous", str(bad))
            self.assertEqual(code, 3, text)

    def test_columns_file(self):
        inv = write_inventory(self.root / "odd.csv", [["Example SQL", "16"]],
                              header=["Thing", "Ver"])
        cols = self.root / "cols.json"
        cols.write_text('{"name": ["Thing"], "version": ["Ver"]}')
        code, _, err = self.check("--columns", str(cols), inv=inv)
        self.assertEqual(code, 0, err)
        code, _, _ = self.check(inv=inv)
        self.assertEqual(code, 3)

    def test_bad_columns_file_exits_3(self):
        cols = self.root / "cols.json"
        for text in ('[]', '{"nope": ["x"]}', '{"name": "x"}', "{bad"):
            cols.write_text(text)
            code, _, _ = self.check("--columns", str(cols))
            self.assertEqual(code, 3, text)

    def test_profile(self):
        code, _, err = self.check("--profile", "demo")
        self.assertEqual(code, 0, err)
        code, _, err = self.check("--profile", "nope")
        self.assertEqual(code, 2)
        self.assertIn("demo", err)
        self.assertIn("generic", err)

    def test_lookahead_out_of_range_is_usage(self):
        self.assertEqual(self.check("--lookahead-months", "-1")[0], 2)
        self.assertEqual(self.check("--lookahead-months", "9999")[0], 2)
        self.assertEqual(self.check("--lookahead-months", "0")[0], 0)

    def test_bad_as_of_is_usage(self):
        code, _, _ = run_main(["check", self.inv, "--data", self.data,
                               "--as-of", "2026-13-40"])
        self.assertEqual(code, 2)

    def test_clock_default_used_only_in_main(self):
        code, out, err = run_main(["check", self.inv, "--data", self.data])
        self.assertEqual(code, 0, err)
        self.assertIn("Checked on: %s" % date.today().isoformat(), out)


class FailureTests(CliBase):
    def test_bad_csv_exits_3(self):
        inv = write_inventory(self.root / "bad.csv", [["x"]], header=["Foo"])
        code, out, err = self.check(inv=inv)
        self.assertEqual(code, 3)
        self.assertNotIn("Traceback", err)

    def test_missing_input_exits_3(self):
        self.assertEqual(self.check(inv=str(self.root / "none.csv"))[0], 3)

    def test_corrupted_data_exits_4(self):
        path = Path(self.data) / "kev.json"
        raw = bytearray(path.read_bytes())
        raw[-3] ^= 0x01
        path.write_bytes(bytes(raw))
        code, _, err = self.check()
        self.assertEqual(code, 4)
        self.assertNotIn("Traceback", err)

    def test_default_data_is_the_bundled_release(self):
        code, _, err = run_main(["check", self.inv, "--as-of", AS_OF])
        self.assertEqual(code, 0, err)

    def test_unexpected_error_prints_only_class_name(self):
        with mock.patch.object(cli, "assess",
                               side_effect=RuntimeError("SECRET row text")):
            code, out, err = self.check()
        self.assertEqual(code, 70)
        self.assertEqual(err.strip(), "RuntimeError")
        self.assertNotIn("SECRET", out + err)

    def test_usage_errors(self):
        self.assertEqual(run_main([])[0], 2)
        self.assertEqual(run_main(["frobnicate"])[0], 2)
        self.assertEqual(self.check("--counts-only")[0], 2)


class FailOnTests(CliBase):
    def test_default_never_fails_on_findings(self):
        self.assertEqual(self.check()[0], 0)

    def test_fail_on_past_eol_exits_10(self):
        code, _, _ = self.check("--fail-on", "past_eol")
        self.assertEqual(code, 10)

    def test_fail_on_several_and_unknown(self):
        self.assertEqual(self.check("--fail-on", "ends_soon,unmatched")[0], 10)
        self.assertEqual(self.check("--fail-on", "past_eol,bogus")[0], 2)
        self.assertEqual(self.check("--fail-on", "")[0], 2)

    def test_empty_list_exits_0(self):
        inv = write_inventory(self.root / "ok.csv",
                              [["Example SQL", "16", "Other Publisher",
                                "zed", ""]])
        self.assertEqual(self.check("--fail-on",
                                    "past_eol,ends_soon,review_urgently,"
                                    "dates_disagree,unmatched", inv=inv)[0], 0)

    def test_fail_on_still_writes_output(self):
        code, _, _ = self.check("--fail-on", "past_eol", "--out",
                                str(self.out))
        self.assertEqual(code, 10)
        self.assertTrue((self.out / "report.md").is_file())


class OutputSafetyTests(CliBase):
    def test_out_equal_to_input_exits_2_and_input_unchanged(self):
        before = Path(self.inv).read_bytes()
        code, _, _ = self.check("--out", self.inv)
        self.assertEqual(code, 2)
        self.assertEqual(Path(self.inv).read_bytes(), before)

    def test_input_inside_out_dir_is_refused_before_any_write(self):
        self.out.mkdir()
        inv = write_inventory(self.out / "report.csv")
        before = Path(inv).read_bytes()
        code, _, _ = self.check("--out", str(self.out), inv=inv)
        self.assertEqual(code, 3)
        self.assertEqual(Path(inv).read_bytes(), before)
        self.assertFalse((self.out / "report.json").exists())

    def test_symlinked_report_refused(self):
        self.out.mkdir()
        target = self.root / "victim.txt"
        target.write_text("keep")
        os.symlink(target, self.out / "report.md")
        code, _, _ = self.check("--out", str(self.out))
        self.assertEqual(code, 3)
        self.assertEqual(target.read_text(), "keep")
        self.assertFalse((self.out / "report.json").exists())

    def test_symlinked_out_dir_refused(self):
        real = self.root / "real"
        real.mkdir()
        os.symlink(real, self.out)
        self.assertEqual(self.check("--out", str(self.out))[0], 3)
        self.assertEqual(list(real.iterdir()), [])

    def test_out_that_is_a_file_is_usage(self):
        other = self.root / "afile"
        other.write_text("x")
        self.assertEqual(self.check("--out", str(other))[0], 2)

    def test_no_output_dir_created_on_failure(self):
        inv = write_inventory(self.root / "bad.csv", [["x"]], header=["Foo"])
        self.check("--out", str(self.out), inv=inv)
        self.assertFalse(self.out.exists())


class CountsOnlyTests(CliBase):
    def test_stdout_has_counts_and_ids_only(self):
        code, out, err = self.check("--counts-only", "--out", str(self.out))
        self.assertEqual(code, 0, err)
        for name in FIXTURE_NAMES:
            self.assertNotIn(name.lower(), out.lower())
        for row in FIXTURE_ROWS:
            for cell in (row[0], row[2], row[3]):  # name, publisher, owner
                if cell:
                    self.assertNotIn(cell, out)
        obj = json.loads((self.out / "report.json").read_text())
        for gid in obj["lists"]["past_eol"]:
            self.assertIn(gid, out)
        self.assertIn("items 7", out)
        self.assertTrue((self.out / "report.md").is_file())

    def test_counts_only_with_fail_on_keeps_stdout_clean(self):
        code, out, err = self.check("--counts-only", "--fail-on", "past_eol",
                                    "--out", str(self.out))
        self.assertEqual(code, 10)
        for name in FIXTURE_NAMES:
            self.assertNotIn(name.lower(), (out + err).lower())


class VerifyDataTests(CliBase):
    def test_good_dir(self):
        code, out, _ = run_main(["verify-data", "--data", self.data])
        self.assertEqual(code, 0)
        self.assertIn("passed", out)

    def test_changed_byte(self):
        path = Path(self.data) / "aliases.json"
        raw = bytearray(path.read_bytes())
        raw[5] ^= 0x01
        path.write_bytes(bytes(raw))
        self.assertEqual(run_main(["verify-data", "--data", self.data])[0], 4)

    def test_bundled_default_verifies(self):
        self.assertEqual(run_main(["verify-data"])[0], 0)


SECRETS = ("SecretVendor Inc", "alice.secret@corp.example", "TopSecretCell")


class FixRound1Tests(CliBase):
    def quiet(self, inv, *extra):
        return self.check("--counts-only", "--out", str(self.out), *extra,
                          inv=inv)

    def assert_no_leak(self, out, err):
        for text in (*FIXTURE_NAMES, *SECRETS):
            self.assertNotIn(text.lower(), (out + err).lower())

    def test_headerless_csv_leaks_nothing_in_counts_only(self):
        inv = self.root / "nohdr.csv"
        inv.write_text("Example SQL,14,SecretVendor Inc,"
                       "alice.secret@corp.example\nDemo OS 1.0,1.0,Acme "
                       "Software,carol\n", encoding="utf-8")
        code, out, err = self.quiet(str(inv))
        self.assertEqual(code, 3)
        self.assert_no_leak(out, err)
        self.assertIn("--counts-only", err)

    def test_secret_header_cell_leaks_nothing_in_counts_only(self):
        inv = write_inventory(self.root / "h.csv", [["x", "1"]],
                              header=["TopSecretCell", "Version"])
        code, out, err = self.quiet(inv)
        self.assertEqual(code, 3)
        self.assert_no_leak(out, err)

    def test_ambiguous_and_duplicate_columns_leak_nothing(self):
        cols = self.root / "c.json"
        cols.write_text('{"name": ["TopSecretCell"], '
                        '"version": ["TopSecretCell"]}')
        inv = write_inventory(self.root / "h.csv", [["x", "1"]],
                              header=["TopSecretCell", "Other"])
        code, out, err = self.quiet(inv, "--columns", str(cols))
        self.assertEqual(code, 3)
        self.assert_no_leak(out, err)
        inv2 = write_inventory(self.root / "d.csv", [["x", "1", "2"]],
                               header=["Product", "TopSecretCell", "Name"])
        code, out, err = self.quiet(inv2)
        self.assertEqual(code, 3)
        self.assert_no_leak(out, err)

    def test_data_error_in_counts_only_is_fixed_text(self):
        (Path(self.data) / "kev.json").write_bytes(b"{}")
        code, out, err = self.quiet(self.inv)
        self.assertEqual(code, 4)
        self.assertIn("--counts-only", err)

    def test_without_flag_header_echo_is_kept(self):
        inv = write_inventory(self.root / "h.csv", [["x", "1"]],
                              header=["TopSecretCell", "Other"])
        code, _, err = self.check(inv=inv)
        self.assertEqual(code, 3)
        self.assertIn("TopSecretCell", err)

    def test_previous_with_hostile_ids_is_ignored_and_not_rendered(self):
        self.check("--out", str(self.root / "one"))
        prev = json.loads((self.root / "one" / "report.json").read_text())
        evil = ("\n## Fake heading\n**Decision needed:** fake\n"
                "```findings\n[]\n```<script>")
        prev["items"][0]["id"] = evil
        pj = self.root / "prev.json"
        pj.write_text(json.dumps(prev))
        code, out, _ = self.check("--previous", str(pj))
        self.assertEqual(code, 0)
        for bad in ("Fake heading", "<script>", "fake"):
            self.assertNotIn(bad, out)
        self.assertEqual(out.count("```findings"), 1)
        self.assertIn("previous run could not be read", out)
        prev["items"][0]["id"] = "0" * 12
        prev["items"][0]["state"] = "<b>x</b>"
        pj.write_text(json.dumps(prev))
        code, out, _ = self.check("--previous", str(pj))
        self.assertIn("previous run could not be read", out)

    def test_previous_valid_ids_still_diff(self):
        self.check("--out", str(self.root / "one"))
        code, out, _ = self.check(
            "--previous", str(self.root / "one" / "report.json"))
        self.assertIn("## Changes since the previous report", out)

    def test_unwritable_out_dir_exits_3_without_path(self):
        locked = self.root / "locked"
        locked.mkdir()
        os.chmod(locked, 0o500)
        self.addCleanup(os.chmod, locked, 0o700)
        if os.access(locked, os.W_OK):
            self.skipTest("running with permission to write anywhere")
        code, out, err = self.check("--out", str(locked / "sub"))
        self.assertEqual(code, 3)
        self.assertIn("cannot write output (EACCES)", err)
        self.assertNotIn(str(locked), err)
        code, out, err = self.check("--out", str(locked))
        self.assertEqual(code, 3)
        self.assertNotIn(str(locked), err)

    def test_oserror_from_write_exits_3(self):
        with mock.patch.object(cli, "write_text",
                               side_effect=OSError(28, "No space")):
            code, _, err = self.check("--out", str(self.out))
        self.assertEqual(code, 3)
        self.assertEqual(err.strip(), "Input error: cannot write output "
                         "(ENOSPC)")

    def test_as_of_range_and_overflow(self):
        for value in ("9999-12-31", "1989-12-31", "2201-01-01"):
            code, _, _ = run_main(["check", self.inv, "--data", self.data,
                                   "--as-of", value])
            self.assertEqual(code, 2, value)
        code, _, _ = run_main(["check", self.inv, "--data", self.data,
                               "--as-of", "2200-12-31",
                               "--lookahead-months", "600"])
        self.assertNotEqual(code, 70)

    def test_date_overflow_inside_build_is_usage(self):
        with self.assertRaises(cli.UsageError):
            cli.build(self.inv, as_of=date(9999, 12, 31), data=self.data)

    def test_as_of_must_be_plain_iso(self):
        for value in ("20261024", "2026-W43-6", "2026-10-24T00", " 2026-10-24",
                      "2026-1-4"):
            code, _, _ = run_main(["check", self.inv, "--data", self.data,
                                   "--as-of", value])
            self.assertEqual(code, 2, value)

    def test_fail_on_duplicates_accepted(self):
        self.assertEqual(self.check("--fail-on", "past_eol,past_eol")[0], 10)


if __name__ == "__main__":
    unittest.main()
