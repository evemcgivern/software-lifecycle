import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_fixtures  # noqa: E402
from helpers import make_data_dir, replace_file  # noqa: E402
from swlc import data  # noqa: E402
from swlc.data import (  # noqa: E402
    kev_match, load_data, validate_eol, validate_kev, verify_data)
from swlc.errors import DataError  # noqa: E402
from swlc.matching import match_product  # noqa: E402

AS_OF = date(2026, 10, 24)
COMMITTED = make_fixtures.COMMITTED


def days_ago(n):
    return AS_OF - timedelta(days=n)


class DataCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def make(self, kev_days=1, eol_days=1):
        return make_data_dir(self.tmp, days_ago(kev_days), days_ago(eol_days))

    def manifest(self, d):
        return json.loads((Path(d) / "manifest.json").read_bytes())

    def write_manifest(self, d, obj):
        (Path(d) / "manifest.json").write_bytes(
            json.dumps(obj).encode("ascii"))


class LoadTests(DataCase):
    def test_valid_dir_loads(self):
        d = load_data(self.make(), AS_OF)
        self.assertEqual(d.release_id, "fixture-1")
        self.assertEqual(set(d.file_hashes), {
            "aliases.json", "profiles.json", "kev.json",
            "eol/examplesql.json", "eol/demoos.json"})
        self.assertEqual(set(d.products), {"examplesql", "demoos"})
        self.assertEqual(d.kev_catalog_version, "2026.10.22")
        self.assertEqual(d.kev_age_days, 1)
        self.assertEqual(d.eol_age_days, 1)
        self.assertTrue(d.kev_current)
        self.assertEqual(d.warnings, [])
        self.assertEqual(d.kev, [{
            "vendor": "example vendor", "product": "example sql",
            "date_added": date(2026, 9, 1), "cve": "CVE-2099-0001"}])

    def test_cycle_dates_and_flags_parse(self):
        d = load_data(self.make(), AS_OF)
        cycles = {c["cycle"]: c for c in d.products["examplesql"]}
        self.assertIs(cycles["14"]["eol"], True)
        self.assertIs(cycles["16"]["eol"], False)
        self.assertEqual(cycles["15"]["eol"], date(2026, 12, 31))
        self.assertEqual(cycles["15"]["support"], date(2024, 12, 31))
        self.assertEqual(cycles["15"]["extended"], date(2028, 12, 31))
        self.assertIsNone(cycles["14"]["extended"])

    def test_missing_dates_are_none(self):
        d = self.make()
        replace_file(d, "eol/demoos.json", [{"cycle": "3.0"}])
        c = load_data(d, AS_OF).products["demoos"][0]
        self.assertEqual(
            (c["eol"], c["support"], c["extended"]), (None, None, None))

    def test_fits_match_product(self):
        d = load_data(self.make(), AS_OF)
        r = match_product("Example SQL", "15.0.2", d.aliases, d.products)
        self.assertEqual((r.product, r.cycle["cycle"]), ("examplesql", "15"))
        r = match_product("Demo OS 2.0", "", d.aliases, d.products)
        self.assertEqual((r.product, r.cycle["cycle"]), ("demoos", "2.0"))

    def test_committed_fixture_loads(self):
        d = load_data(str(COMMITTED), AS_OF)
        self.assertEqual(d.release_id, "fixture-1")

    def test_committed_fixture_matches_regeneration(self):
        build_dir = Path(self.tmp) / "regen"
        make_fixtures.build(build_dir)
        old = sorted(p.relative_to(COMMITTED).as_posix()
                     for p in COMMITTED.rglob("*")
                     if p.is_file() and p.name not in data._IGNORED_NAMES)
        new = sorted(p.relative_to(build_dir).as_posix()
                     for p in build_dir.rglob("*") if p.is_file())
        self.assertEqual(old, new)
        for name in old:
            self.assertEqual((COMMITTED / name).read_bytes(),
                             (build_dir / name).read_bytes(), name)

    def test_committed_manifest_hashes_verify(self):
        manifest = json.loads((COMMITTED / "manifest.json").read_bytes())
        import hashlib
        for name, meta in manifest["files"].items():
            raw = (COMMITTED / name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"])
            self.assertEqual(len(raw), meta["size"])
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(verify_data(str(COMMITTED)), 0)


class ManifestTests(DataCase):
    def test_one_changed_byte_names_file_not_content(self):
        d = self.make()
        path = Path(d) / "kev.json"
        raw = bytearray(path.read_bytes())
        raw[raw.index(b"Example Vendor")] = ord("X")
        path.write_bytes(bytes(raw))
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        msg = str(ctx.exception)
        self.assertIn("kev.json", msg)
        self.assertNotIn("Xxample", msg)
        self.assertNotIn("Example", msg)

    def test_size_mismatch(self):
        d = self.make()
        with open(Path(d) / "aliases.json", "ab") as fh:
            fh.write(b" ")
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("aliases.json", str(ctx.exception))

    def test_missing_manifest(self):
        d = self.make()
        os.remove(Path(d) / "manifest.json")
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("manifest.json", str(ctx.exception))

    def test_missing_data_dir(self):
        with self.assertRaises(DataError):
            load_data(str(Path(self.tmp) / "nope"), AS_OF)

    def test_manifest_not_json(self):
        d = self.make()
        (Path(d) / "manifest.json").write_bytes(b"{not json")
        with self.assertRaises(DataError):
            load_data(d, AS_OF)

    def test_min_tool_version_above_current(self):
        d = self.make()
        m = self.manifest(d)
        m["min_tool_version"] = "0.2.0"
        self.write_manifest(d, m)
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("0.2.0", str(ctx.exception))

    def test_min_tool_version_compare_is_numeric(self):
        d = self.make()
        m = self.manifest(d)
        m["min_tool_version"] = "0.1.0"
        self.write_manifest(d, m)
        with mock.patch.object(data, "tool_version", lambda: "0.10.0"):
            load_data(d, AS_OF)
        m["min_tool_version"] = "0.10.0"
        self.write_manifest(d, m)
        with mock.patch.object(data, "tool_version", lambda: "0.9.0"):
            with self.assertRaises(DataError):
                load_data(d, AS_OF)

    def test_tool_version_read_from_version_file(self):
        skill = Path(__file__).resolve().parents[2]
        self.assertEqual(data.tool_version(),
                         (skill / "VERSION").read_text().strip())

    def test_unsupported_data_format(self):
        d = self.make()
        m = self.manifest(d)
        m["data_format"] = 2
        self.write_manifest(d, m)
        with self.assertRaises(DataError):
            load_data(d, AS_OF)

    def test_bad_manifest_fields(self):
        for key, value in (("release_id", ""), ("kev_date", "2026-13-40"),
                           ("eol_date", 5), ("files", []),
                           ("min_tool_version", "banana"),
                           ("kev_catalog_version", None)):
            with self.subTest(key=key):
                d = make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                                  days_ago(1), days_ago(1))
                m = self.manifest(d)
                m[key] = value
                self.write_manifest(d, m)
                with self.assertRaises(DataError):
                    load_data(d, AS_OF)

    def test_bad_file_entry(self):
        for entry in ({"sha256": "abc", "size": 1}, {"sha256": "0" * 64},
                      {"sha256": "0" * 64, "size": True}, "x"):
            with self.subTest(entry=entry):
                d = make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                                  days_ago(1), days_ago(1))
                m = self.manifest(d)
                m["files"]["kev.json"] = entry
                self.write_manifest(d, m)
                with self.assertRaises(DataError):
                    load_data(d, AS_OF)

    def test_unlisted_eol_file_rejected(self):
        d = self.make()
        (Path(d) / "eol" / "sneaky.json").write_bytes(b"[]")
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("sneaky.json", str(ctx.exception))

    def test_unlisted_top_level_and_nested_files_rejected(self):
        for rel in ("extra.json", "eol/sub/deep.json", "notes.txt"):
            with self.subTest(rel=rel):
                d = make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                                  days_ago(1), days_ago(1))
                path = Path(d) / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
                with self.assertRaises(DataError):
                    load_data(d, AS_OF)

    def test_listed_file_missing_on_disk(self):
        d = self.make()
        os.remove(Path(d) / "eol" / "demoos.json")
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("demoos.json", str(ctx.exception))

    def test_path_traversal_names_rejected(self):
        outside = Path(self.tmp) / "outside.json"
        outside.write_bytes(b"[]")
        for name in ("../outside.json", "eol/../../outside.json",
                     "/etc/passwd", "eol/a/b.json", "eol\\x.json",
                     "eol/.hidden.json", "other.json", "eol/x.txt"):
            with self.subTest(name=name):
                d = make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                                  days_ago(1), days_ago(1))
                m = self.manifest(d)
                m["files"][name] = {"sha256": "0" * 64, "size": 2}
                self.write_manifest(d, m)
                with self.assertRaises(DataError) as ctx:
                    load_data(d, AS_OF)
                self.assertNotIn("passwd", str(ctx.exception))

    def test_required_files_must_be_listed(self):
        for name in ("aliases.json", "profiles.json", "kev.json"):
            with self.subTest(name=name):
                d = make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                                  days_ago(1), days_ago(1))
                m = self.manifest(d)
                del m["files"][name]
                self.write_manifest(d, m)
                with self.assertRaises(DataError):
                    load_data(d, AS_OF)

    def test_symlink_rejected(self):
        d = self.make()
        target = Path(self.tmp) / "real.json"
        target.write_bytes((Path(d) / "eol" / "demoos.json").read_bytes())
        os.remove(Path(d) / "eol" / "demoos.json")
        os.symlink(target, Path(d) / "eol" / "demoos.json")
        with self.assertRaises(DataError):
            load_data(d, AS_OF)

    def test_verify_happens_before_parse(self):
        d = self.make()
        size = len((Path(d) / "kev.json").read_bytes())
        (Path(d) / "kev.json").write_bytes(b"{broken".ljust(size))
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("SHA-256", str(ctx.exception))

    def test_no_parse_when_manifest_fails(self):
        d = self.make()
        with open(Path(d) / "kev.json", "ab") as fh:
            fh.write(b" ")
        with mock.patch.object(data, "validate_kev") as vk, \
                mock.patch.object(data, "validate_eol") as ve:
            with self.assertRaises(DataError):
                load_data(d, AS_OF)
        vk.assert_not_called()
        ve.assert_not_called()


class StalenessTests(DataCase):
    def test_kev_3_days_no_warning(self):
        d = load_data(self.make(kev_days=3), AS_OF)
        self.assertEqual(d.warnings, [])
        self.assertTrue(d.kev_current)

    def test_kev_4_days_warns_still_current(self):
        d = load_data(self.make(kev_days=4), AS_OF)
        self.assertEqual(d.kev_age_days, 4)
        self.assertTrue(d.kev_current)
        self.assertEqual(len(d.warnings), 1)
        self.assertIn("KEV", d.warnings[0])
        self.assertIn("4", d.warnings[0])

    def test_kev_7_days_still_current(self):
        d = load_data(self.make(kev_days=7), AS_OF)
        self.assertTrue(d.kev_current)

    def test_kev_8_days_not_current(self):
        d = load_data(self.make(kev_days=8), AS_OF)
        self.assertFalse(d.kev_current)
        self.assertEqual(d.kev_age_days, 8)
        self.assertTrue(any("KEV" in w and "8" in w for w in d.warnings))

    def test_eol_30_days_no_warning(self):
        self.assertEqual(load_data(self.make(eol_days=30), AS_OF).warnings, [])

    def test_eol_31_days_warns(self):
        d = load_data(self.make(eol_days=31), AS_OF)
        self.assertEqual(d.eol_age_days, 31)
        self.assertEqual(len(d.warnings), 1)
        self.assertIn("31", d.warnings[0])
        self.assertTrue(d.kev_current)


class FutureDateTests(DataCase):
    def test_minus_one_day_tolerated(self):
        d = load_data(self.make(kev_days=-1, eol_days=-1), AS_OF)
        self.assertTrue(d.kev_current)
        self.assertEqual(d.warnings, [])

    def test_minus_two_and_thirty_not_current(self):
        for n in (-2, -30):
            with self.subTest(n=n):
                d = load_data(self.make_in(n, n), AS_OF)
                self.assertFalse(d.kev_current)
                self.assertTrue(any("KEV" in w and "future" in w
                                    for w in d.warnings))
                self.assertTrue(any("End-of-life" in w and "future" in w
                                    for w in d.warnings))

    def make_in(self, kev_days, eol_days):
        return make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                             days_ago(kev_days), days_ago(eol_days))


class ParseLimitTests(DataCase):
    def test_huge_min_tool_version_is_data_error(self):
        d = self.make()
        m = self.manifest(d)
        m["min_tool_version"] = "9" * 5000
        self.write_manifest(d, m)
        with self.assertRaises(DataError):
            load_data(d, AS_OF)

    def test_deeply_nested_manifest_is_data_error(self):
        d = self.make()
        (Path(d) / "manifest.json").write_bytes(b"[" * 200000)
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("manifest.json", str(ctx.exception))

    def test_deeply_nested_data_file_is_data_error(self):
        d = self.make()
        replace_file(d, "eol/demoos.json", b"[" * 200000)
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("demoos.json", str(ctx.exception))


class StrayFileTests(DataCase):
    def test_os_junk_files_ignored(self):
        d = self.make()
        for rel in (".DS_Store", "eol/.DS_Store", "Thumbs.db",
                    "eol/desktop.ini"):
            (Path(d) / rel).write_bytes(b"\x00junk")
        self.assertEqual(load_data(d, AS_OF).release_id, "fixture-1")
        self.assertEqual(verify_data_quiet(d), 0)

    def test_other_stray_file_still_fails(self):
        d = self.make()
        (Path(d) / ".DS_Store").write_bytes(b"x")
        (Path(d) / "notes.txt").write_bytes(b"x")
        with self.assertRaises(DataError):
            load_data(d, AS_OF)


class ProfilesAndAliasShapeTests(DataCase):
    def test_profiles_loaded_from_verified_bytes(self):
        d = load_data(self.make(), AS_OF)
        self.assertEqual(d.profiles["demo"]["columns"]["name"], ["Product"])

    def test_absent_profiles_key_is_empty(self):
        d = self.make()
        replace_file(d, "profiles.json", {"format": 1})
        self.assertEqual(load_data(d, AS_OF).profiles, {})

    def test_bad_profile_shapes(self):
        for obj in ([], {"profiles": []}, {"profiles": {"a": 1}},
                    {"profiles": {"a": {}}},
                    {"profiles": {"a": {"columns": {"name": "x"}}}},
                    {"profiles": {"a": {"columns": {"name": [1]}}}}):
            with self.subTest(obj=obj):
                d = make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                                  days_ago(1), days_ago(1))
                replace_file(d, "profiles.json", obj)
                with self.assertRaises(DataError) as ctx:
                    load_data(d, AS_OF)
                self.assertIn("profiles.json", str(ctx.exception))

    def test_real_profiles_and_aliases_pass(self):
        real = Path(__file__).resolve().parents[2] / "data"
        d = self.make()
        for name in ("aliases.json", "profiles.json"):
            replace_file(d, name, (real / name).read_bytes())
        self.assertTrue(load_data(d, AS_OF).profiles)

    def test_malformed_alias_entry_fails_load_and_verify(self):
        d = self.make()
        replace_file(d, "aliases.json", {"aliases": [{"key": "x"}]})
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("aliases.json", str(ctx.exception))
        self.assertEqual(verify_data_quiet(d), 4)


def verify_data_quiet(d):
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        return verify_data(d)


class SchemaTests(DataCase):
    def bad(self, name, content):
        d = self.make()
        replace_file(d, name, content)
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        return str(ctx.exception)

    def test_wrong_typed_eol_field(self):
        msg = self.bad("eol/demoos.json",
                       [{"cycle": "1.0", "eol": 20250630}])
        self.assertIn("demoos.json", msg)

    def test_bad_eol_shapes(self):
        for obj in ({}, [1], [{}], [{"cycle": ""}], [{"cycle": 1}],
                    [{"cycle": "1", "eol": "2025-02-30"}],
                    [{"cycle": "1", "eol": "25-01-01"}],
                    [{"cycle": "1", "support": "soon"}],
                    [{"cycle": "1", "extendedSupport": 5}]):
            with self.subTest(obj=obj):
                with self.assertRaises(DataError):
                    validate_eol(obj)

    def test_unknown_extra_keys_ignored(self):
        got = validate_eol([{"cycle": "1", "eol": False, "lts": True,
                             "link": "x"}])
        self.assertEqual(got[0]["cycle"], "1")
        validate_kev({"catalogVersion": "1", "dateReleased": "2026-01-01",
                      "extra": 1, "entries": []})

    def test_wrong_typed_kev_field(self):
        msg = self.bad("kev.json", {
            "catalogVersion": "1", "dateReleased": "2026-10-23",
            "entries": [{"cveID": "CVE-2099-1", "vendorProject": 5,
                         "product": "p", "dateAdded": "2026-01-01"}]})
        self.assertIn("kev.json", msg)

    def test_bad_kev_shapes(self):
        good = {"cveID": "C", "vendorProject": "v", "product": "p",
                "dateAdded": "2026-01-01"}
        base = {"catalogVersion": "1", "dateReleased": "2026-01-01"}
        for obj in ([], {**base}, {**base, "entries": {}},
                    {**base, "entries": [1]},
                    {**base, "entries": [{**good, "dateAdded": "x"}]},
                    {**base, "entries": [{**good, "cveID": ""}]},
                    {"catalogVersion": 1, "dateReleased": "2026-01-01",
                     "entries": []},
                    {"catalogVersion": "1", "dateReleased": "nope",
                     "entries": []}):
            with self.subTest(obj=obj):
                with self.assertRaises(DataError):
                    validate_kev(obj)

    def test_schema_error_never_echoes_values(self):
        with self.assertRaises(DataError) as ctx:
            validate_eol([{"cycle": "1", "eol": "SECRET-VALUE"}])
        self.assertNotIn("SECRET", str(ctx.exception))

    def test_aliases_must_be_object_with_list(self):
        for obj in ([], {"aliases": {}}, {"format": 1}):
            with self.subTest(obj=obj):
                self.bad("aliases.json", obj)

    def test_invalid_json_file(self):
        msg = self.bad("eol/demoos.json", b"{nope")
        self.assertIn("demoos.json", msg)

    def test_invalid_utf8_file(self):
        self.bad("eol/demoos.json", b"\xff\xfe[]")

    def test_bad_product_file_name_in_manifest_and_disk(self):
        d = self.make()
        (Path(d) / "eol" / "Bad Name.json").write_bytes(b"[]")
        m = self.manifest(d)
        m["files"]["eol/Bad Name.json"] = {"sha256": "0" * 64, "size": 2}
        self.write_manifest(d, m)
        with self.assertRaises(DataError):
            load_data(d, AS_OF)


class KevMatchTests(unittest.TestCase):
    KEV = [{"vendor": "example vendor", "product": "example sql",
            "date_added": date(2026, 9, 1), "cve": "CVE-2099-0001"}]

    def test_exact_normalized_match(self):
        self.assertTrue(kev_match(self.KEV, "Example  Vendor", "EXAMPLE SQL"))

    def test_both_sides_required(self):
        self.assertFalse(kev_match(self.KEV, "Example Vendor", "Other"))
        self.assertFalse(kev_match(self.KEV, "Other", "Example SQL"))

    def test_no_substring_match(self):
        self.assertFalse(kev_match(self.KEV, "Example Vendor", "Example"))
        self.assertFalse(kev_match(self.KEV, "Example", "Example SQL"))

    def test_empty_never_matches(self):
        kev = [{"vendor": "", "product": "", "date_added": date(2026, 1, 1)}]
        self.assertFalse(kev_match(kev, "", ""))
        self.assertFalse(kev_match([], "a", "b"))


class VerifyDataTests(DataCase):
    def test_ok_returns_zero(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(verify_data(self.make()), 0)
        self.assertIn("fixture-1", out.getvalue())

    def test_failure_returns_four_without_content(self):
        d = self.make()
        with open(Path(d) / "kev.json", "ab") as fh:
            fh.write(b"X")
        import contextlib
        import io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(verify_data(d), 4)
        self.assertIn("kev.json", err.getvalue())

    def test_schema_failure_returns_four(self):
        d = self.make()
        replace_file(d, "eol/demoos.json", [{"cycle": 1}])
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(verify_data(d), 4)

    def test_stale_data_still_verifies(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                verify_data(self.make(kev_days=400, eol_days=400)), 0)


if __name__ == "__main__":
    unittest.main()
