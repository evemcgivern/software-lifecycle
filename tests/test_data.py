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
    kev_match, load_data, validate_curation, validate_eol, validate_kev,
    validate_products, verify_data)
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
        demo = {"tidewatersuite", "brightlineeditor", "mapletonreports",
                "ironwoodscheduler", "northwindgateway", "quillbase",
                "harborviewcrm", "pineconearchive", "redwoodbackup",
                "copperfieldnotes", "lanternviewer"}
        self.assertEqual(set(d.file_hashes), {
            "aliases.json", "profiles.json", "kev.json", "products.json",
            "curation.json", "eol/examplesql.json", "eol/demoos.json"}
            | {"eol/%s.json" % name for name in demo})
        self.assertEqual(set(d.products), {"examplesql", "demoos"} | demo)
        self.assertEqual(set(d.catalog), set(d.products))
        self.assertEqual(d.catalog["demoos"]["title"], "Demo OS")
        self.assertEqual(d.curation, make_fixtures.CURATION)
        self.assertEqual(d.kev_catalog_version, "2026.10.22")
        self.assertEqual(d.kev_age_days, 1)
        self.assertEqual(d.eol_age_days, 1)
        self.assertTrue(d.kev_current)
        self.assertEqual(d.warnings, [])
        self.assertEqual(d.kev, [{
            "vendor": "example vendor", "product": "example sql",
            "date_added": date(2026, 9, 1), "cve": "CVE-2099-0001"}, {
            "vendor": "example corp", "product": "gateway server",
            "date_added": date(2026, 8, 15), "cve": "CVE-2099-0002"}])

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
        m["min_tool_version"] = "0.7.0"
        self.write_manifest(d, m)
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertIn("0.7.0", str(ctx.exception))

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
        skill = Path(__file__).resolve().parents[1]
        self.assertEqual(data.tool_version(),
                         (skill / "VERSION").read_text().strip())

    def test_unsupported_data_format(self):
        for value in (3, 0, True, False, "2", None, 2.0, 1.0, [2]):
            with self.subTest(value=value):
                d = make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                                  days_ago(1), days_ago(1))
                m = self.manifest(d)
                m["data_format"] = value
                self.write_manifest(d, m)
                with self.assertRaises(DataError):
                    load_data(d, AS_OF)

    def test_unknown_format_is_reported_before_file_names(self):
        # A future format may list files this tool has never heard of. An
        # old tool must say "data format not supported", not complain about
        # a file name.
        d = self.make()
        m = self.manifest(d)
        m["data_format"] = 3
        m["files"]["future-thing.json"] = {"sha256": "0" * 64, "size": 2}
        m["files"]["eol/Bad Name.json"] = {"sha256": "0" * 64, "size": 2}
        del m["files"]["products.json"]
        self.write_manifest(d, m)
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertEqual(
            str(ctx.exception),
            "manifest.json: data format is not supported by this tool")
        self.assertEqual(verify_data_quiet(d), 4)

    def test_format_1_loads_without_a_catalog(self):
        d = make_data_dir(self.tmp, days_ago(1), days_ago(1), data_format=1)
        self.assertFalse((Path(d) / "products.json").exists())
        self.assertFalse((Path(d) / "curation.json").exists())
        loaded = load_data(d, AS_OF)
        self.assertIsNone(loaded.catalog)
        self.assertIsNone(loaded.curation)
        self.assertEqual(loaded.warnings, [
            "This data release has no product catalog; "
            "generated matching is off."])
        self.assertEqual(set(loaded.file_hashes), {
            "aliases.json", "profiles.json", "kev.json"}
            | {"eol/%s.json" % p for p in loaded.products})
        self.assertEqual(verify_data_quiet(d), 0)

    def test_format_1_warning_comes_after_staleness_warnings(self):
        d = make_data_dir(self.tmp, days_ago(5), days_ago(1), data_format=1)
        warnings = load_data(d, AS_OF).warnings
        self.assertEqual(len(warnings), 2)
        self.assertEqual(warnings[-1], data.NO_CATALOG_WARNING)

    def test_format_2_has_no_catalog_warning(self):
        self.assertNotIn(data.NO_CATALOG_WARNING,
                         load_data(self.make(), AS_OF).warnings)

    def test_format_1_may_not_list_the_format_2_files(self):
        d = make_data_dir(self.tmp, days_ago(1), days_ago(1), data_format=1)
        for name in ("products.json", "curation.json"):
            with self.subTest(name=name):
                m = self.manifest(d)
                m["files"][name] = {"sha256": "0" * 64, "size": 2}
                self.write_manifest(d, m)
                with self.assertRaises(DataError):
                    load_data(d, AS_OF)
                del m["files"][name]
                self.write_manifest(d, m)

    def test_format_2_needs_both_new_files_listed(self):
        for name in ("products.json", "curation.json"):
            with self.subTest(name=name):
                d = make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                                  days_ago(1), days_ago(1))
                m = self.manifest(d)
                del m["files"][name]
                self.write_manifest(d, m)
                with self.assertRaises(DataError) as ctx:
                    load_data(d, AS_OF)
                self.assertEqual(
                    str(ctx.exception),
                    "manifest.json: files: %s is not listed" % name)

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
        real = Path(__file__).resolve().parents[1] / "data"
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


def products_obj(*records):
    return {"format": 1, "products": list(records)}


def record(pid="alpha", **over):
    rec = {"id": pid, "title": "Alpha", "category": "app",
           "vendors": [], "namespaces": []}
    rec.update(over)
    return rec


def curation_obj(**over):
    obj = {"format": 1, "publisher_aliases": {}, "single_word_allowlist": [],
           "exclusions": [], "generated_off": []}
    obj.update(over)
    return obj


GOOD_EXCLUSION = {"product": "alpha", "name": "alpha desktop",
                  "publisher": "", "reason": "client", "gold": "a|b|c"}
GOOD_ALLOW = {"product": "alpha", "reason": "vendor says so",
              "source": "https://example.com/a", "gold": "a|b|c"}


GOOD_CLASS_ROW = {"name": "alpha tool", "publisher": "alpha",
                  "class": "governable", "reason": "standalone app",
                  "source": "https://example.com/c", "gold": "a|b|c"}
GOOD_CLASS_PROD = {"class": "governable", "reason": "standalone runtime",
                   "source": "https://example.com/r"}
GOOD_PARENT = {"name_prefix": "alpha writer", "publisher": "alpha",
               "parent": "alpha", "reason": "sold in the suite",
               "source": "https://example.com/s", "gold": "a|b|c"}


def pa(*phrases, **over):
    """A publisher_aliases entry."""
    entry = {"phrases": list(phrases), "reason": "the vendor's own name",
             "source": "https://example.com/p"}
    entry.update(over)
    return entry


class ProductsSchemaTests(DataCase):
    def test_valid_catalog_returns_id_to_record(self):
        out = validate_products(products_obj(
            record("alpha", vendors=["a", "b"], namespaces=["x"]),
            record("beta", title="Beta")))
        self.assertEqual(list(out), ["alpha", "beta"])
        self.assertEqual(out["alpha"]["vendors"], ["a", "b"])
        self.assertEqual(validate_products(products_obj()), {})

    def test_bad_catalogs_are_refused(self):
        bad = [
            [], {"format": 1}, {"products": []},
            {"format": 2, "products": []}, {"format": True, "products": []},
            {"format": 1, "products": [], "extra": 1},
            {"format": 1, "products": {}},
            products_obj("x"),
            products_obj(record(extra=1)),
            products_obj({"id": "alpha", "title": "A", "category": "a"}),
            products_obj(record(id="Alpha")),
            products_obj(record(id="a b")),
            products_obj(record(id=5)),
            products_obj(record(title="")),
            products_obj(record(title=3)),
            products_obj(record(category=" ")),
            products_obj(record(vendors="a")),
            products_obj(record(vendors=["b", "a"])),
            products_obj(record(vendors=["a", "a"])),
            products_obj(record(vendors=[""])),
            products_obj(record(vendors=[3])),
            products_obj(record(vendors=[" a"])),
            products_obj(record(namespaces=["Upper"])),
            products_obj(record(namespaces=["b", "a"])),
            products_obj(record("b"), record("a")),
            products_obj(record("a"), record("a")),
        ]
        for obj in bad:
            with self.subTest(obj=obj):
                with self.assertRaises(DataError):
                    validate_products(obj)

    def test_errors_never_echo_values(self):
        for obj in (products_obj(record(id="SECRET", title="SECRET")),
                    products_obj(record(vendors=["SECRET", "SECRET"])),
                    products_obj(record(namespaces=["SECRET"] + ["A"]))):
            with self.assertRaises(DataError) as ctx:
                validate_products(obj)
            self.assertNotIn("SECRET", str(ctx.exception))

    def test_bad_catalog_fails_load_and_verify_naming_the_file(self):
        d = self.make()
        replace_file(d, "products.json", products_obj(record(id="Bad")))
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertTrue(str(ctx.exception).startswith("products.json: "))
        self.assertEqual(verify_data_quiet(d), 4)

    def test_catalog_is_read_from_the_verified_bytes(self):
        d = self.make()
        obj = json.loads(json.dumps(make_fixtures.PRODUCTS))
        for rec in obj["products"]:
            if rec["id"] == "examplesql":
                rec["title"] = "Changed"
        replace_file(d, "products.json", obj)
        self.assertEqual(
            load_data(d, AS_OF).catalog["examplesql"]["title"], "Changed")

    def test_text_fields_refuse_control_and_direction_characters(self):
        for bad in ("a\nb", "a\x1b[31mb", "a\u202eb", "a\u200bb",
                    "a\u2028b", "x" * 201, "", " "):
            for key in ("title", "category"):
                with self.subTest(key=key, bad=bad):
                    with self.assertRaises(DataError) as ctx:
                        validate_products(products_obj(record(**{key: bad})))
                    self.assertNotIn("\x1b", str(ctx.exception))
        validate_products(products_obj(record(title="x" * 200)))
        validate_products(products_obj(record(title="C++ Builder (2nd)")))

    def test_vendor_and_namespace_character_rules(self):
        validate_products(products_obj(record(
            vendors=["c++", "clam_anti-virus", "pivotal_software",
                     "ruby-lang"],
            namespaces=["a_b-c.d", "angular", "org.apache.tomcat"])))
        for key, bad in (("vendors", "Upper"), ("vendors", "a b"),
                         ("vendors", "a\nb"), ("vendors", "a/b"),
                         ("vendors", "-a"), ("vendors", "a\u202eb"),
                         ("namespaces", "a/b"), ("namespaces", "a b"),
                         ("namespaces", "a\nb"), ("namespaces", "a\u202eb"),
                         ("namespaces", "@angular"), ("namespaces", "a+b"),
                         ("namespaces", "-a")):
            with self.subTest(key=key, bad=bad):
                with self.assertRaises(DataError):
                    validate_products(products_obj(record(**{key: [bad]})))

    def test_vendor_and_namespace_tokens_are_at_most_100_characters(self):
        validate_products(products_obj(record(
            vendors=["v" * 100], namespaces=["n" * 100])))
        for key in ("vendors", "namespaces"):
            with self.subTest(key=key):
                with self.assertRaises(DataError):
                    validate_products(products_obj(record(
                        **{key: ["x" * 101]})))

    def test_catalog_must_match_the_eol_files(self):
        obj = json.loads(json.dumps(make_fixtures.PRODUCTS))
        extra = dict(obj["products"][0], id="zzz-no-eol-file")
        d = self.make()
        replace_file(d, "products.json",
                     dict(obj, products=obj["products"] + [extra]))
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertNotIn("zzz", str(ctx.exception))
        self.assertTrue(str(ctx.exception).startswith("products.json: "))
        self.assertEqual(verify_data_quiet(d), 4)
        d = make_data_dir(tempfile.mkdtemp(dir=self.tmp),
                          days_ago(1), days_ago(1))
        replace_file(d, "products.json",
                     dict(obj, products=obj["products"][1:]))
        with self.assertRaises(DataError):
            load_data(d, AS_OF)
        self.assertEqual(verify_data_quiet(d), 4)


class CurationSchemaTests(DataCase):
    def test_valid_curation_is_returned(self):
        obj = curation_obj(
            publisher_aliases={"alpha": pa("acme", "acme software"),
                               "beta": pa("b", gold="Beta|B Inc|1.0")},
            single_word_allowlist=[GOOD_ALLOW],
            exclusions=[GOOD_EXCLUSION, dict(GOOD_EXCLUSION, publisher="p")],
            generated_off=["alpha", "beta"])
        self.assertIs(validate_curation(obj), obj)
        self.assertIs(validate_curation(obj, ["alpha", "beta"]), obj)
        validate_curation(curation_obj(), [])

    def test_bad_curation_is_refused(self):
        bad = [
            [], {}, dict(curation_obj(), extra=1),
            {k: v for k, v in curation_obj().items() if k != "format"},
            curation_obj(format=2), curation_obj(format=True),
            curation_obj(publisher_aliases=[]),
            curation_obj(publisher_aliases={"Alpha": pa("a")}),
            curation_obj(publisher_aliases={"alpha": ["a"]}),
            curation_obj(publisher_aliases={"alpha": pa()}),
            curation_obj(publisher_aliases={"alpha": pa(phrases="a")}),
            curation_obj(publisher_aliases={"alpha": pa("b", "a")}),
            curation_obj(publisher_aliases={"alpha": pa("a", "a")}),
            curation_obj(publisher_aliases={"alpha": pa("Acme")}),
            curation_obj(publisher_aliases={"alpha": pa(" a")}),
            curation_obj(publisher_aliases={"alpha": pa("")}),
            curation_obj(publisher_aliases={"alpha": pa("...")}),
            curation_obj(publisher_aliases={"alpha": pa("a", "-")}),
            curation_obj(publisher_aliases={"alpha": pa("a", reason="")}),
            curation_obj(publisher_aliases={"alpha": pa("a", reason=5)}),
            curation_obj(publisher_aliases={"alpha": pa(
                "a", source="http://example.com/p")}),
            curation_obj(publisher_aliases={"alpha": pa("a", extra=1)}),
            curation_obj(publisher_aliases={"alpha": pa("a", gold="a|b")}),
            curation_obj(publisher_aliases={"alpha": pa("a", gold="")}),
            curation_obj(publisher_aliases={"alpha": pa("a", gold=5)}),
            curation_obj(publisher_aliases={"alpha": {
                "phrases": ["a"], "reason": "r"}}),
            curation_obj(publisher_aliases={"alpha": {
                "phrases": ["a"], "source": "https://example.com/p"}}),
            curation_obj(single_word_allowlist={}),
            curation_obj(single_word_allowlist=[GOOD_ALLOW, GOOD_ALLOW]),
            curation_obj(single_word_allowlist=[dict(GOOD_ALLOW, extra=1)]),
            curation_obj(single_word_allowlist=[
                {"product": "alpha", "reason": "r"}]),
            curation_obj(single_word_allowlist=[dict(GOOD_ALLOW, reason="")]),
            curation_obj(single_word_allowlist=[
                dict(GOOD_ALLOW, source="http://example.com/a")]),
            curation_obj(single_word_allowlist=[
                dict(GOOD_ALLOW, source="https://")]),
            curation_obj(single_word_allowlist=[
                dict(GOOD_ALLOW, source="https://a b")]),
            curation_obj(single_word_allowlist=[
                dict(GOOD_ALLOW, source="ftp://example.com")]),
            curation_obj(single_word_allowlist=[dict(GOOD_ALLOW, source=5)]),
            curation_obj(single_word_allowlist=[
                {k: v for k, v in GOOD_ALLOW.items() if k != "gold"}]),
            curation_obj(single_word_allowlist=[dict(GOOD_ALLOW, gold="a|b")]),
            curation_obj(single_word_allowlist=[dict(GOOD_ALLOW, gold="")]),
            curation_obj(exclusions={}),
            curation_obj(exclusions=["x"]),
            curation_obj(exclusions=[dict(GOOD_EXCLUSION, extra=1)]),
            curation_obj(exclusions=[
                {k: v for k, v in GOOD_EXCLUSION.items() if k != "gold"}]),
            curation_obj(exclusions=[dict(GOOD_EXCLUSION, name="")]),
            curation_obj(exclusions=[dict(GOOD_EXCLUSION, publisher="A")]),
            curation_obj(exclusions=[dict(GOOD_EXCLUSION, publisher="a b")]),
            curation_obj(exclusions=[dict(GOOD_EXCLUSION, publisher=None)]),
            curation_obj(exclusions=[dict(GOOD_EXCLUSION, reason="")]),
            curation_obj(exclusions=[dict(GOOD_EXCLUSION, gold="a|b")]),
            curation_obj(exclusions=[dict(GOOD_EXCLUSION, gold="a|b|c|d")]),
            curation_obj(exclusions=[dict(GOOD_EXCLUSION, gold="")]),
            curation_obj(exclusions=[GOOD_EXCLUSION, dict(GOOD_EXCLUSION)]),
            curation_obj(generated_off="alpha"),
            curation_obj(generated_off=["b", "a"]),
            curation_obj(generated_off=["a", "a"]),
            curation_obj(generated_off=["Alpha"]),
            curation_obj(generated_off=[5]),
        ]
        for obj in bad:
            with self.subTest(obj=obj):
                with self.assertRaises(DataError):
                    validate_curation(obj)

    def test_no_cycle_versions(self):
        good = {"prefixes": ["21.0.0", "21.3"], "reason": "old numbering",
                "source": "https://example.com/v"}
        obj = curation_obj(no_cycle_versions={"alpha": good})
        self.assertIs(validate_curation(obj, ["alpha"]), obj)
        validate_curation(curation_obj(no_cycle_versions={}))
        for entry in (
                [], dict(good, extra=1),
                {k: v for k, v in good.items() if k != "source"},
                dict(good, prefixes=[]), dict(good, prefixes="21.3"),
                dict(good, prefixes=["21.3", "21.0.0"]),
                dict(good, prefixes=["21.3", "21.3"]),
                dict(good, prefixes=["21.x"]), dict(good, prefixes=["21."]),
                dict(good, prefixes=[".21"]), dict(good, prefixes=[21]),
                dict(good, reason=""),
                dict(good, source="http://example.com/v")):
            with self.subTest(entry=entry):
                with self.assertRaises(DataError):
                    validate_curation(curation_obj(
                        no_cycle_versions={"alpha": entry}))
        for bad in ([], {"Alpha": good}):
            with self.assertRaises(DataError):
                validate_curation(curation_obj(no_cycle_versions=bad))
        with self.assertRaises(DataError):
            validate_curation(curation_obj(no_cycle_versions={"gone": good}),
                              ["alpha"])

    def test_curation_new_keys_optional(self):
        validate_curation(curation_obj())
        self.assertIs(validate_curation(make_fixtures.CURATION),
                      make_fixtures.CURATION)
        obj = curation_obj(classification_rows=[GOOD_CLASS_ROW],
                           classification_products={"alpha": GOOD_CLASS_PROD},
                           bundle_parents=[GOOD_PARENT])
        self.assertIs(validate_curation(obj, ["alpha"]), obj)
        validate_curation(curation_obj(classification_rows=[],
                                       classification_products={},
                                       bundle_parents=[]))

    def test_curation_rejects_bad_class(self):
        bad = [
            curation_obj(classification_rows=[dict(GOOD_CLASS_ROW,
                                                   **{"class": "app"})]),
            curation_obj(classification_rows=[dict(
                GOOD_CLASS_ROW, **{"class": "bundle_member"})]),
            curation_obj(classification_products={"alpha": dict(
                GOOD_CLASS_PROD, **{"class": "bundle_member"})}),
            curation_obj(classification_products={"alpha": dict(
                GOOD_CLASS_PROD, **{"class": None})}),
            curation_obj(classification_rows={}),
            curation_obj(classification_rows=[dict(GOOD_CLASS_ROW, extra=1)]),
            curation_obj(classification_rows=[dict(GOOD_CLASS_ROW,
                                                   name="Alpha  Tool")]),
            curation_obj(classification_rows=[dict(GOOD_CLASS_ROW,
                                                   publisher="a b")]),
            curation_obj(classification_rows=[dict(GOOD_CLASS_ROW,
                                                   source="http://x.org")]),
            curation_obj(classification_rows=[dict(GOOD_CLASS_ROW,
                                                   gold="a|b")]),
            curation_obj(classification_rows=[GOOD_CLASS_ROW,
                                              dict(GOOD_CLASS_ROW)]),
            curation_obj(classification_rows=[
                dict(GOOD_CLASS_ROW, name="zeta"), GOOD_CLASS_ROW]),
            curation_obj(classification_products=[]),
            curation_obj(classification_products={"alpha": dict(
                GOOD_CLASS_PROD, reason="")}),
            curation_obj(classification_products={"Alpha": GOOD_CLASS_PROD}),
        ]
        for obj in bad:
            with self.subTest(obj=obj):
                with self.assertRaises(DataError):
                    validate_curation(obj)

    def test_class_product_error_names_the_product(self):
        with self.assertRaises(DataError) as ctx:
            validate_curation(curation_obj(classification_products={
                "alpha": dict(GOOD_CLASS_PROD, **{"class": "bad"})}))
        self.assertIn("alpha", str(ctx.exception))

    def test_curation_rejects_bundle_parent_without_gold(self):
        bad = [
            {k: v for k, v in GOOD_PARENT.items() if k != "gold"},
            dict(GOOD_PARENT, gold=""), dict(GOOD_PARENT, gold="a|b"),
            dict(GOOD_PARENT, extra=1), dict(GOOD_PARENT, publisher=""),
            dict(GOOD_PARENT, publisher="Alpha"),
            dict(GOOD_PARENT, publisher="alpha corp"),
            dict(GOOD_PARENT, name_prefix=""),
            dict(GOOD_PARENT, name_prefix="Alpha Tool"),
            dict(GOOD_PARENT, name_prefix="alpha  tool"),
            dict(GOOD_PARENT, parent="Alpha"),
            dict(GOOD_PARENT, source="ftp://example.com"),
            dict(GOOD_PARENT, reason=""),
        ]
        for entry in bad:
            with self.subTest(entry=entry):
                with self.assertRaises(DataError):
                    validate_curation(curation_obj(bundle_parents=[entry]))
        for value in ({}, [GOOD_PARENT, dict(GOOD_PARENT)],
                      [dict(GOOD_PARENT, name_prefix="zeta"), GOOD_PARENT]):
            with self.assertRaises(DataError):
                validate_curation(curation_obj(bundle_parents=value))

    def test_curation_named_parents_must_exist(self):
        for obj in (
                curation_obj(bundle_parents=[dict(GOOD_PARENT,
                                                  parent="gone")]),
                curation_obj(classification_products={
                    "gone": GOOD_CLASS_PROD})):
            with self.subTest(obj=obj):
                validate_curation(obj)              # fine without ids
                with self.assertRaises(DataError):
                    validate_curation(obj, ["alpha"])

    def test_every_named_product_must_exist_when_ids_are_given(self):
        known = ["alpha"]
        for obj in (
                curation_obj(publisher_aliases={"gone": pa("a")}),
                curation_obj(single_word_allowlist=[
                    dict(GOOD_ALLOW, product="gone")]),
                curation_obj(exclusions=[
                    dict(GOOD_EXCLUSION, product="gone")]),
                curation_obj(generated_off=["gone"])):
            with self.subTest(obj=obj):
                validate_curation(obj)              # fine without ids
                with self.assertRaises(DataError) as ctx:
                    validate_curation(obj, known)
                self.assertNotIn("gone", str(ctx.exception))

    def test_errors_never_echo_values(self):
        for obj in (
                curation_obj(single_word_allowlist=[
                    dict(GOOD_ALLOW, source="http://SECRET.example")]),
                curation_obj(generated_off=["SECRET", "Alpha"]),
                curation_obj(exclusions=[dict(GOOD_EXCLUSION,
                                              gold="SECRET")])):
            with self.assertRaises(DataError) as ctx:
                validate_curation(obj)
            self.assertNotIn("SECRET", str(ctx.exception))

    def test_bad_curation_fails_load_and_verify_naming_the_file(self):
        d = self.make()
        replace_file(d, "curation.json", curation_obj(generated_off=["b", "a"]))
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertTrue(str(ctx.exception).startswith("curation.json: "))
        self.assertEqual(verify_data_quiet(d), 4)

    def test_https_urls_need_a_host_and_no_user_name(self):
        for url in ("https:///", "https://@", "https://@host/x",
                    "https://user@host/x", "https://user:pw@host/", "https://",
                    "https:///path", "https://-a.com", "https://a b.com",
                    "https://a.com/a b", "https://a.com\n", "http://a.com",
                    "https://a.com:99999999/", "https://.com"):
            with self.subTest(url=url):
                with self.assertRaises(DataError):
                    validate_curation(curation_obj(single_word_allowlist=[
                        dict(GOOD_ALLOW, source=url)]))
        for url in ("https://example.com", "https://example.com/a?b=c#d",
                    "https://example.com:8443/x", "https://a-b.example.org/"):
            with self.subTest(url=url):
                validate_curation(curation_obj(single_word_allowlist=[
                    dict(GOOD_ALLOW, source=url)]))

    def test_load_checks_curation_against_the_catalog(self):
        d = self.make()
        replace_file(d, "curation.json", curation_obj(generated_off=["gone"]))
        with self.assertRaises(DataError) as ctx:
            load_data(d, AS_OF)
        self.assertTrue(str(ctx.exception).startswith("curation.json: "))
        self.assertNotIn("gone", str(ctx.exception))
        self.assertEqual(verify_data_quiet(d), 4)
        replace_file(d, "curation.json", curation_obj(generated_off=["demoos"]))
        load_data(d, AS_OF)

    def test_curation_is_read_from_the_verified_bytes(self):
        d = self.make()
        obj = curation_obj(generated_off=["demoos"])
        replace_file(d, "curation.json", obj)
        self.assertEqual(load_data(d, AS_OF).curation, obj)


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
