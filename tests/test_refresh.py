import contextlib
import gzip
import hashlib
import http.server
import io
import json
import shutil
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import refresh_data as rd
from helpers import make_data_dir
from make_fixtures import COMMITTED, build
from swlc.data import verify_data

UPSTREAM = Path(__file__).resolve().parent / "fixtures" / "upstream"
SHA = "7cfb122846893f10ee819ab47b615eff261945d0"
OTHER_SHA = "1" * 40


def kev_obj(count, start=1, licence=rd.LICENCE_NOTE):
    entries = [{"cveID": "CVE-2099-%04d" % n, "vendorProject": "Vendor %d" % n,
                "product": "Product %d" % n, "dateAdded": "2026-09-01"}
               for n in range(start, start + count)]
    obj = {"catalogVersion": "2026.10.22", "dateReleased": "2026-10-22",
           "entries": entries}
    if licence is not None:
        obj["license"] = licence
    return obj


def cisa_feed(count=3):
    """A synthetic feed shaped like the live CISA file (extra fields kept)."""
    vulns = []
    for n in range(count, 0, -1):
        vulns.append({
            "cveID": "CVE-2099-%04d" % n, "vendorProject": "Example Corp",
            "product": "Gateway Server", "vulnerabilityName": "Long name",
            "dateAdded": "2026-10-%02d" % n,
            "shortDescription": "SECRET DESCRIPTION TEXT",
            "requiredAction": "Apply updates", "dueDate": "2026-11-12",
            "knownRansomwareCampaignUse": "Unknown", "notes": "a note",
            "cwes": ["CWE-20"]})
    feed = {"title": "CISA Catalog of Known Exploited Vulnerabilities",
            "catalogVersion": "2026.10.23",
            "dateReleased": "2026-10-23T19:30:18.9209Z",
            "count": count, "vulnerabilities": vulns}
    return json.dumps(feed).encode("utf-8")


def make_archive(sha=SHA, files=None, pax=True, extra=None):
    """A gzip tarball laid out like GitHub's archive of the upstream repo."""
    if files is None:
        files = {p.name: p.read_bytes() for p in sorted(UPSTREAM.glob("*.md"))}
    buf = io.BytesIO()
    headers = {"comment": sha} if pax else {}
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT,
                      pax_headers=headers) as tar:
        top = "endoflife.date-%s/" % sha
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(top + "products/" + name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        readme = b"# not a product\n"
        info = tarfile.TarInfo(top + "README.md")
        info.size = len(readme)
        tar.addfile(info, io.BytesIO(readme))
        if extra:
            extra(tar, top)
    return gzip.compress(buf.getvalue(), mtime=0)


def product(name):
    return rd.product_from_markdown((UPSTREAM / name).read_text("utf-8"))


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = rd.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class CanonicalTests(unittest.TestCase):
    def test_sorted_ascii_indented_with_trailing_newline(self):
        raw = rd.canonical({"b": "é", "a": [1, {"d": 1, "c": 2}]})
        self.assertTrue(raw.endswith(b"}\n"))
        self.assertEqual(json.loads(raw), {"b": "é",
                                           "a": [1, {"d": 1, "c": 2}]})
        self.assertIn(b"\\u00e9", raw)
        self.assertLess(raw.index(b'"a"'), raw.index(b'"b"'))
        self.assertIn(b'\n  "a": [', raw)

    def test_fixture_builder_reuses_it_and_stays_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(Path(tmp))
            for path in sorted(COMMITTED.rglob("*.json")):
                rel = path.relative_to(COMMITTED)
                self.assertEqual((Path(tmp) / rel).read_bytes(),
                                 path.read_bytes(), str(rel))


class CheckKevTests(unittest.TestCase):
    def test_one_entry_addition_passes(self):
        self.assertEqual(rd.check_kev(kev_obj(101), kev_obj(100)), [])

    def test_thirty_percent_drop_fails(self):
        fails = rd.check_kev(kev_obj(70), kev_obj(100))
        self.assertTrue(any("entry count" in f for f in fails), fails)

    def test_thirty_percent_rise_fails(self):
        fails = rd.check_kev(kev_obj(130), kev_obj(100))
        self.assertTrue(any("entry count" in f for f in fails), fails)

    def test_twenty_percent_is_the_edge(self):
        self.assertEqual(rd.check_kev(kev_obj(120), kev_obj(100)), [])

    def test_removed_entry_fails(self):
        new = kev_obj(100, start=2)  # CVE-2099-0001 gone, one added
        fails = rd.check_kev(new, kev_obj(100))
        self.assertTrue(any("removed" in f for f in fails), fails)
        self.assertFalse(any("CVE-2099-0001" in f for f in fails))

    def test_removed_entry_passes_with_flag(self):
        new = kev_obj(100, start=2)
        self.assertEqual(rd.check_kev(new, kev_obj(100), allow_removed=True),
                         [])

    def test_missing_licence_note_fails(self):
        fails = rd.check_kev(kev_obj(101, licence=None), kev_obj(100))
        self.assertTrue(any("licence" in f for f in fails), fails)
        fails = rd.check_kev(kev_obj(101, licence="unknown"), kev_obj(100))
        self.assertTrue(any("licence" in f for f in fails), fails)

    def test_bad_schema_fails(self):
        bad = kev_obj(101)
        del bad["entries"][3]["cveID"]
        fails = rd.check_kev(bad, kev_obj(100))
        self.assertTrue(any("schema" in f for f in fails), fails)
        self.assertTrue(rd.check_kev({"entries": "x"}, kev_obj(100)))
        self.assertTrue(rd.check_kev([], kev_obj(100)))

    def test_bad_previous_file_fails(self):
        fails = rd.check_kev(kev_obj(10), {"entries": []})
        self.assertTrue(any("previous" in f for f in fails), fails)

    def test_failures_never_echo_feed_text(self):
        bad = kev_obj(50, start=60)
        bad["entries"][0]["vendorProject"] = "<script>evil</script>"
        bad.pop("license")
        text = " ".join(rd.check_kev(bad, kev_obj(100)))
        self.assertNotIn("evil", text)
        self.assertNotIn("Vendor", text)


class KevContentGateTests(unittest.TestCase):
    """The review's attack inputs: each one used to publish."""

    def fails(self, new, old, **kw):
        out = rd.check_kev(new, old, **kw)
        self.assertTrue(out, "gate passed")
        return " ".join(out)

    def test_rewritten_entries_with_same_ids_fail(self):
        new = kev_obj(100)
        for entry in new["entries"]:
            entry.update(vendorProject="Nobody", product="Nothing",
                         dateAdded="2099-12-31")
        text = self.fails(new, kev_obj(100))
        self.assertIn("changed", text)
        self.assertIn("dateAdded", text)
        self.assertNotIn("Nobody", text)

    def test_a_few_renames_pass(self):
        new = kev_obj(100)
        for entry in new["entries"][:3]:
            entry["product"] = "Renamed"
        self.assertEqual(rd.check_kev(new, kev_obj(100)), [])
        new["entries"][3]["product"] = "Renamed"
        self.assertTrue(rd.check_kev(new, kev_obj(100)))

    def test_hostile_new_entries_fail(self):
        for field, value in (("cveID", "\u202e<script>x"),
                             ("cveID", "CVE-2026-\u0661\u0662\u0663\u0664"),
                             ("cveID", "CVE-2026-123"),
                             ("vendorProject", "V" * (5 * 1024 * 1024)),
                             ("vendorProject", "x" * 201),
                             ("product", "Gate\u200bway"),
                             ("product", "Gate\u202eway"),
                             ("product", "Gate\nway")):
            new = kev_obj(101)
            new["entries"][-1][field] = value
            text = self.fails(new, kev_obj(100))
            self.assertNotIn("script", text, field)
            self.assertLess(len(text), 1000, field)

    def test_real_feed_characters_pass(self):
        new = kev_obj(101)
        new["entries"][-1]["product"] = "Caf\u00e8 \u2013 Server\u202f2"
        self.assertEqual(rd.check_kev(new, kev_obj(100)), [])

    def test_bulk_additions_fail_without_override(self):
        old = kev_obj(1000)
        new = kev_obj(1200)  # 20% more: inside the count range
        text = self.fails(new, old)
        self.assertIn("added", text)
        self.assertEqual(rd.check_kev(new, old, allow_bulk=True), [])
        # Small baselines still allow a normal day of up to 50 additions.
        self.assertEqual(rd.check_kev(kev_obj(250), kev_obj(220)), [])

    def test_override_relaxes_only_volume_checks(self):
        new = kev_obj(101)
        new["entries"][-1]["cveID"] = "not-a-cve"
        self.assertTrue(rd.check_kev(new, kev_obj(100), allow_bulk=True))
        new = kev_obj(101)
        new["dateReleased"] = "2001-01-01"
        self.assertTrue(rd.check_kev(new, kev_obj(100), allow_bulk=True))

    def test_dates_and_versions_never_move_backwards(self):
        new = kev_obj(101)
        new["dateReleased"] = "2001-01-01"
        for entry in new["entries"]:
            entry["dateAdded"] = "2000-12-31"
        self.assertIn("dateReleased", self.fails(new, kev_obj(100)))
        new = kev_obj(101)
        new["catalogVersion"] = "2001.01.01"
        self.assertIn("catalogVersion", self.fails(new, kev_obj(100)))
        new = kev_obj(101)
        new["catalogVersion"] = "next"
        self.assertIn("catalogVersion", self.fails(new, kev_obj(100)))

    def test_entry_added_after_the_release_date_fails(self):
        new = kev_obj(101)
        new["entries"][-1]["dateAdded"] = "2026-10-23"
        self.assertIn("dateAdded", self.fails(new, kev_obj(100)))

    def test_duplicate_ids_fail(self):
        new = kev_obj(101)
        new["entries"][-1]["cveID"] = new["entries"][0]["cveID"]
        self.assertIn("twice", self.fails(new, kev_obj(100)))


class KevFeedTests(unittest.TestCase):
    def test_keeps_only_ids_names_and_dates(self):
        obj = rd.kev_from_feed(cisa_feed(3))
        self.assertEqual(obj["catalogVersion"], "2026.10.23")
        self.assertEqual(obj["dateReleased"], "2026-10-23")
        self.assertEqual(obj["license"], rd.LICENCE_NOTE)
        self.assertEqual(set(obj), {"catalogVersion", "dateReleased",
                                    "license", "entries"})
        self.assertEqual([e["cveID"] for e in obj["entries"]],
                         ["CVE-2099-0001", "CVE-2099-0002", "CVE-2099-0003"])
        for entry in obj["entries"]:
            self.assertEqual(set(entry), {"cveID", "vendorProject",
                                          "product", "dateAdded"})
        self.assertNotIn(b"SECRET", rd.canonical(obj))

    def test_count_mismatch_is_refused(self):
        feed = json.loads(cisa_feed(3))
        feed["count"] = 4
        with self.assertRaises(rd.RefreshError):
            rd.kev_from_feed(json.dumps(feed).encode())

    def test_duplicate_cve_is_refused(self):
        feed = json.loads(cisa_feed(2))
        feed["vulnerabilities"][1]["cveID"] = feed["vulnerabilities"][0]["cveID"]
        with self.assertRaises(rd.RefreshError):
            rd.kev_from_feed(json.dumps(feed).encode())

    def test_bad_feed_shapes_are_refused(self):
        for raw in (b"not json", b"[]", b'{"vulnerabilities": {}}',
                    json.dumps({"catalogVersion": "x", "count": 0,
                                "dateReleased": "yesterday",
                                "vulnerabilities": []}).encode()):
            with self.assertRaises(rd.RefreshError, msg=raw):
                rd.kev_from_feed(raw)

    def test_kev_command_is_byte_stable(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(rd, "fetch", return_value=cisa_feed(5)):
            outs = []
            for n in (1, 2):
                out = Path(tmp) / str(n)
                code, _, err = run_cli(["kev", "--out", str(out)])
                self.assertEqual(code, 0, err)
                outs.append((out / "kev.json").read_bytes())
            self.assertEqual(outs[0], outs[1])
            self.assertEqual(rd.fetch.call_args[0][0], rd.KEV_URL)


class FrontMatterTests(unittest.TestCase):
    def test_mssqlserver(self):
        pid, cycles = product("mssqlserver.md")
        self.assertEqual(pid, "mssqlserver")
        self.assertEqual([c["cycle"] for c in cycles],
                         ["17.0", "16.0", "13.0-sp3-acp", "13.0-sp3"])
        self.assertEqual(cycles[0], {
            "cycle": "17.0", "releaseDate": "2025-11-18",
            "support": "2031-01-06", "eol": "2036-01-06",
            # eoesColumn is set and this release has no eoes: false, as the
            # upstream v0 API writes it.
            "extendedSupport": False})
        self.assertEqual(cycles[2]["extendedSupport"], "2029-07-17")

    def test_checkmk_dash_at_column_zero(self):
        pid, cycles = product("checkmk.md")
        self.assertEqual(pid, "checkmk")
        self.assertEqual(cycles, [
            {"cycle": "2.5", "releaseDate": "2026-04-28", "eol": "2028-04-28"},
            {"cycle": "2.4", "releaseDate": "2025-05-06", "eol": "2027-11-06"},
        ])

    def test_rhel_ignores_release_keys_outside_releases(self):
        pid, cycles = product("rhel.md")
        self.assertEqual(pid, "rhel")
        self.assertEqual([c["cycle"] for c in cycles], ["10", "9", "8"])
        self.assertEqual(cycles[2], {
            "cycle": "8", "releaseDate": "2019-05-07", "support": "2024-05-31",
            "eol": "2029-05-31", "extendedSupport": "2033-05-31"})

    def test_openai_booleans_comments_and_nested_lists(self):
        pid, cycles = product("openai-api-models.md")
        self.assertEqual(pid, "openai-api-models")
        # eoas: false means active support has not ended, so support: true.
        self.assertEqual(cycles[0], {
            "cycle": "gpt-6.1-sol", "releaseDate": "2026-09-29",
            "support": True, "eol": False})
        self.assertEqual(len(cycles), 2)

    def test_eoas_true_means_support_ended(self):
        text = ("---\npermalink: /demo\nreleases:\n"
                "  - releaseCycle: \"1\"\n    eoas: true\n    eol: true\n"
                "    eoes: false\n---\n")
        self.assertEqual(rd.product_from_markdown(text)[1], [
            {"cycle": "1", "support": False, "eol": True,
             "extendedSupport": True}])

    def test_values_with_extra_spaces_and_single_quotes(self):
        text = ("---\npermalink: /demo\nreleases:\n"
                "  - releaseCycle: '9.4'\n    eol:  2026-03-17\n"
                "  - releaseCycle: moto-g87\n    eol: false # none yet\n---\n")
        self.assertEqual(rd.product_from_markdown(text)[1], [
            {"cycle": "9.4", "eol": "2026-03-17"},
            {"cycle": "moto-g87", "eol": False}])

    def test_unreadable_layouts_are_refused(self):
        head = "---\npermalink: /demo\nreleases:\n"
        bad = [
            head + "  - {releaseCycle: \"1\", eol: false}\n---\n",
            head + "  - releaseCycle: 1.10\n---\n",
            head + "  - releaseCycle: \"1\"\n    eol: *anchor\n---\n",
            head + "  - releaseCycle: \"1\"\n    eol: \"2026-01-01\"\n---\n",
            head + "  - releaseCycle: \"1\"\n    eol:\n      - 2026-01-01\n---\n",
            head + "  - releaseCycle: \"1\"\n    eol: |\n      x\n---\n",
            head + "  - releaseCycle: \"1\"\n   eol: false\n---\n",
            head + "  - releaseCycle: \"1\"\n    eol: false\n    eol: true\n---\n",
            head + "  - releaseCycle: \"1\"\n  - releaseCycle: \"1\"\n---\n",
            head + "  - releaseCycle: \"Bad Name\"\n---\n",
            head + "  - releaseCycle: \"a\\\"b\"\n---\n",
            head + "  - eol: false\n---\n",
            head + "  - releaseCycle: \"1\"\n    eol: 2026-02-30\n---\n",
            head + "\t- releaseCycle: \"1\"\n---\n",
            head + "  - releaseCycle: \"1\"\n",
            head.replace("\n", "\r\n") + "  - releaseCycle: \"1\"\r\n---\r\n",
            "---\nreleases:\n  - releaseCycle: \"1\"\n---\n",
            "---\npermalink: /Bad\nreleases:\n  - releaseCycle: \"1\"\n---\n",
            "---\npermalink: /demo\n---\n",
            head + "---\n",
            "title: no front matter\n",
            "﻿" + head + "  - releaseCycle: \"1\"\n---\n",
        ]
        for text in bad:
            with self.assertRaises(rd.RefreshError, msg=repr(text)):
                rd.product_from_markdown(text)

    def test_error_text_never_echoes_file_content(self):
        text = ("---\npermalink: /demo\nreleases:\n"
                "  - releaseCycle: \"1\"\n    eol: IGNORE-ALL-RULES\n---\n")
        with self.assertRaises(rd.RefreshError) as ctx:
            rd.product_from_markdown(text)
        self.assertNotIn("IGNORE", str(ctx.exception))


class ArchiveTests(unittest.TestCase):
    def test_reads_every_product_from_a_pinned_archive(self):
        products = rd.eol_from_archive(make_archive(), SHA)
        self.assertEqual(sorted(products), ["checkmk", "mssqlserver",
                                            "openai-api-models", "rhel"])

    def test_archive_for_another_commit_is_refused(self):
        with self.assertRaises(rd.RefreshError):
            rd.eol_from_archive(make_archive(sha=OTHER_SHA), SHA)
        with self.assertRaises(rd.RefreshError):
            rd.eol_from_archive(make_archive(pax=False), SHA)

    def test_links_and_bad_archives_are_refused(self):
        def add_link(tar, top):
            info = tarfile.TarInfo(top + "products/evil.md")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
        with self.assertRaises(rd.RefreshError):
            rd.eol_from_archive(make_archive(extra=add_link), SHA)
        with self.assertRaises(rd.RefreshError):
            rd.eol_from_archive(b"not a gzip file", SHA)
        with self.assertRaises(rd.RefreshError):
            rd.eol_from_archive(make_archive(files={}), SHA)

    def test_nested_files_are_ignored(self):
        def add_nested(tar, top):
            data = b"not front matter"
            info = tarfile.TarInfo(top + "products/sub/x.md")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        products = rd.eol_from_archive(make_archive(extra=add_nested), SHA)
        self.assertEqual(len(products), 4)

    def test_eol_command_writes_dates_only_and_is_byte_stable(self):
        archive = make_archive()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(rd, "fetch", return_value=archive):
            runs = []
            for n in (1, 2):
                out = Path(tmp) / str(n)
                code, _, err = run_cli(["eol", "--upstream-commit", SHA,
                                        "--out", str(out)])
                self.assertEqual(code, 0, err)
                runs.append({p.name: p.read_bytes()
                             for p in sorted(out.glob("*.json"))})
            self.assertEqual(runs[0], runs[1])
            self.assertEqual(rd.fetch.call_args[0][0],
                             rd.EOL_ARCHIVE_URL % SHA)
            allowed = {"cycle", "releaseDate", "eol", "support",
                       "extendedSupport"}
            for name, raw in runs[0].items():
                for cycle in json.loads(raw):
                    self.assertLessEqual(set(cycle), allowed, name)
                for word in (b"Description", b"title", b"Microsoft",
                             b"link", b"codename", b"latest", b"http"):
                    self.assertNotIn(word, raw, name)

    def test_eol_command_refuses_a_bad_sha_and_a_full_folder(self):
        code, _, _ = run_cli(["eol", "--upstream-commit", "main",
                              "--out", "x"])
        self.assertEqual(code, 2)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(rd, "fetch", return_value=make_archive()):
            (Path(tmp) / "old.json").write_text("[]")
            code, _, err = run_cli(["eol", "--upstream-commit", SHA,
                                    "--out", tmp])
            self.assertEqual(code, 1)
            self.assertIn("not empty", err)


class ManifestTests(unittest.TestCase):
    def _refreshed(self, tmp):
        """A data dir built the way the daily job builds one."""
        data = Path(tmp) / "data"
        (data / "eol").mkdir(parents=True)
        for name in ("aliases.json", "profiles.json"):
            shutil.copyfile(COMMITTED / name, data / name)
        (data / "kev.json").write_bytes(
            rd.canonical(rd.kev_from_feed(cisa_feed(4))))
        rd.write_eol(str(data / "eol"), rd.eol_from_archive(make_archive(), SHA))
        return data

    def test_refreshed_dir_passes_verify_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self._refreshed(tmp)
            code, _, err = run_cli([
                "manifest", "--dir", str(data), "--kev-date", "2026-10-23",
                "--eol-date", "2026-10-24", "--upstream-commit", SHA,
                "--kev-catalog-version", "2026.10.23",
                "--release-id", "data-2026.10.24.1"])
            self.assertEqual(code, 0, err)
            manifest = json.loads((data / "manifest.json").read_bytes())
            self.assertEqual(manifest["release_id"], "data-2026.10.24.1")
            self.assertEqual(manifest["upstream_commit"], SHA)
            self.assertEqual(manifest["min_tool_version"], rd.MIN_TOOL_VERSION)
            self.assertEqual(manifest["data_format"], 1)
            listed = set(manifest["files"])
            self.assertEqual(listed, {
                "aliases.json", "profiles.json", "kev.json",
                "eol/checkmk.json", "eol/mssqlserver.json",
                "eol/openai-api-models.json", "eol/rhel.json"})
            for name, meta in manifest["files"].items():
                raw = (data / name).read_bytes()
                self.assertEqual(meta["sha256"],
                                 hashlib.sha256(raw).hexdigest())
                self.assertEqual(meta["size"], len(raw))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(verify_data(str(data)), 0)

    def test_manifest_is_byte_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_dir(tmp, "2026-10-22", "2026-10-20")
            args = (data, "2026-10-22", "2026-10-20", "0" * 40,
                    "2026.10.22", "fixture-1")
            first = rd.build_manifest(*args)
            self.assertEqual(rd.build_manifest(*args), first)
            committed = (COMMITTED / "manifest.json").read_bytes()
            self.assertEqual(first, committed)

    def test_unexpected_or_missing_files_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(make_data_dir(tmp, "2026-10-22", "2026-10-20"))
            args = ("2026-10-22", "2026-10-20", SHA, "2026.10.22", "r-1")
            (data / "notes.txt").write_text("x")
            with self.assertRaises(rd.RefreshError):
                rd.build_manifest(str(data), *args)
            (data / "notes.txt").unlink()
            (data / "kev.json").unlink()
            with self.assertRaises(rd.RefreshError):
                rd.build_manifest(str(data), *args)

    def test_bad_flags_are_usage_errors(self):
        base = ["manifest", "--dir", "x", "--kev-date", "2026-10-23",
                "--eol-date", "2026-10-24", "--upstream-commit", SHA,
                "--kev-catalog-version", "2026.10.23", "--release-id", "r-1"]
        for flag, value in (("--kev-date", "2026-13-01"),
                            ("--upstream-commit", "abc"),
                            ("--kev-catalog-version", "2026 10;rm"),
                            ("--release-id", "../x")):
            argv = list(base)
            argv[argv.index(flag) + 1] = value
            code, _, _ = run_cli(argv)
            self.assertEqual(code, 2, flag)


class ZipTests(unittest.TestCase):
    def test_zip_is_byte_stable_sorted_and_dated_1980(self):
        import os
        import time
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(make_data_dir(tmp, "2026-10-22", "2026-10-20"))
            first = Path(tmp) / "a.zip"
            rd.write_zip(str(data), str(first))
            for path in data.rglob("*.json"):
                os.utime(path, (time.time() + 99999, time.time() + 99999))
            second = Path(tmp) / "b.zip"
            code, _, err = run_cli(["zip", "--dir", str(data),
                                    "--out", str(second)])
            self.assertEqual(code, 0, err)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as zf:
                names = zf.namelist()
                self.assertEqual(names, sorted(names))
                self.assertIn("manifest.json", names)
                self.assertIn("eol/demoos.json", names)
                for info in zf.infolist():
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
            unpacked = Path(tmp) / "unpacked"
            with zipfile.ZipFile(first) as zf:
                zf.extractall(unpacked)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(verify_data(str(unpacked)), 0)


class EolSummaryTests(unittest.TestCase):
    OLD = {
        "alpha": [{"cycle": "1", "eol": "2026-01-01", "support": True},
                  {"cycle": "2", "eol": "2027-01-01", "support": True}],
        "beta": [{"cycle": "5", "eol": False, "support": True}] * 1,
        "gamma": [{"cycle": "3", "eol": "2028-01-01", "support": False},
                  {"cycle": "4", "eol": "2029-01-01", "support": False},
                  {"cycle": "5", "eol": "2030-01-01", "support": False},
                  {"cycle": "6", "eol": "2031-01-01", "support": False},
                  {"cycle": "7", "eol": "2032-01-01", "support": False}],
    }

    def _copy(self):
        return json.loads(json.dumps(self.OLD))

    def test_unchanged_is_not_flagged(self):
        summary = rd.eol_change_summary(self._copy(), self._copy())
        self.assertFalse(summary["flagged"])
        self.assertEqual(summary["dates_changed"], 0)
        self.assertEqual(summary["dates_total"], 16)

    def test_vanished_product_is_flagged(self):
        new = self._copy()
        del new["beta"]
        summary = rd.eol_change_summary(new, self.OLD)
        self.assertTrue(summary["flagged"])
        self.assertEqual(summary["products_removed"], ["beta"])

    def test_one_change_in_sixteen_is_not_flagged(self):
        new = self._copy()
        new["alpha"][0]["eol"] = "2026-06-30"
        summary = rd.eol_change_summary(new, self.OLD)
        self.assertEqual(summary["dates_changed"], 1)
        self.assertFalse(summary["flagged"])

    def test_more_than_ten_percent_changed_is_flagged(self):
        new = self._copy()
        new["gamma"][0]["eol"] = "2028-06-30"
        new["gamma"][1]["support"] = "2027-01-01"
        summary = rd.eol_change_summary(new, self.OLD)
        self.assertEqual(summary["dates_changed"], 2)
        self.assertTrue(summary["flagged"])

    def test_added_products_and_cycles_are_counted(self):
        new = self._copy()
        new["delta"] = [{"cycle": "1", "eol": False}]
        new["alpha"].append({"cycle": "3", "eol": False})
        summary = rd.eol_change_summary(new, self.OLD)
        self.assertEqual(summary["products_added"], ["delta"])
        self.assertEqual(summary["cycles_added"], 1)
        self.assertFalse(summary["flagged"])

    def test_newly_added_date_fields_count_as_changed(self):
        new = self._copy()
        new["beta"][0]["extendedSupport"] = "2030-01-01"
        new["alpha"][0]["releaseDate"] = "2020-01-01"
        summary = rd.eol_change_summary(new, self.OLD)
        self.assertEqual(summary["dates_changed"], 2)
        self.assertEqual(summary["dates_total"], 18)
        self.assertEqual(summary["products_changed"], ["alpha", "beta"])
        self.assertTrue(summary["flagged"])

    def test_removed_cycle_counts_its_dates_as_changed(self):
        new = self._copy()
        new["gamma"].pop()
        summary = rd.eol_change_summary(new, self.OLD)
        self.assertEqual(summary["cycles_removed"], 1)
        self.assertEqual(summary["dates_changed"], 2)

    def test_cli_exit_codes_and_fixed_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / "old", Path(tmp) / "new"
            changed = self._copy()
            del changed["beta"]
            rd.write_eol(str(old), self.OLD)
            rd.write_eol(str(new), self._copy())
            code, out, _ = run_cli(["eol-summary", "--new", str(new),
                                    "--old", str(old)])
            self.assertEqual(code, 0, out)
            shutil.rmtree(new)
            rd.write_eol(str(new), changed)
            code, out, _ = run_cli(["eol-summary", "--new", str(new),
                                    "--old", str(old)])
            self.assertEqual(code, 1)
            self.assertIn("beta", out)
            self.assertIn("Flagged", out)


class CheckKevCliTests(unittest.TestCase):
    def _files(self, tmp, new, old):
        n, o = Path(tmp) / "new.json", Path(tmp) / "old.json"
        n.write_bytes(rd.canonical(new))
        o.write_bytes(rd.canonical(old))
        return str(n), str(o)

    def test_pass_and_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            n, o = self._files(tmp, kev_obj(101), kev_obj(100))
            code, out, _ = run_cli(["check-kev", "--new", n, "--old", o])
            self.assertEqual(code, 0)
            self.assertIn("1 added", out)
            n, o = self._files(tmp, kev_obj(60, start=50), kev_obj(100))
            code, out, err = run_cli(["check-kev", "--new", n, "--old", o])
            self.assertEqual(code, 1)
            self.assertIn("removed", err)
            self.assertNotIn("Vendor", out + err)
            code, _, _ = run_cli(["check-kev", "--new", n, "--old", o,
                                  "--allow-removed"])
            self.assertEqual(code, 1)  # the count gate still fails

    def test_added_digest_has_ids_vendor_and_product_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            n, o = self._files(tmp, kev_obj(102), kev_obj(100))
            digest = Path(tmp) / "digest.md"
            code, _, err = run_cli(["check-kev", "--new", n, "--old", o,
                                    "--digest", str(digest)])
            self.assertEqual(code, 0, err)
            text = digest.read_text("utf-8")
            self.assertIn("CVE-2099-0101", text)
            self.assertIn("Vendor 102", text)
            self.assertNotIn("CVE-2099-0100", text)

    def test_digest_escapes_markdown(self):
        new = kev_obj(101)
        new["entries"][-1]["product"] = "<img src=x> | [link](http://x)"
        with tempfile.TemporaryDirectory() as tmp:
            n, o = self._files(tmp, new, kev_obj(100))
            digest = Path(tmp) / "digest.md"
            run_cli(["check-kev", "--new", n, "--old", o,
                     "--digest", str(digest)])
            text = digest.read_text("utf-8")
            self.assertNotIn("<img", text)
            self.assertNotIn("](http", text)
            self.assertNotIn(" | [", text)

    def test_unreadable_files_fail_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            n = Path(tmp) / "new.json"
            n.write_text("{")
            code, _, err = run_cli(["check-kev", "--new", str(n),
                                    "--old", str(n)])
            self.assertEqual(code, 1)


# --- the fetch helper, against a server on 127.0.0.1 only ------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        _Handler.seen.append((self.path, self.headers.get("User-Agent")))
        if self.path == "/ok":
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/big":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"x" * 5000)
        elif self.path == "/biglength":
            self.send_response(200)
            self.send_header("Content-Length", "999999")
            self.end_headers()
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


class FetchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _Handler.seen.clear()

    def get(self, path, max_bytes=1000):
        return rd.fetch(self.base + path, max_bytes, timeout=5,
                        allow_loopback_http=True)

    def test_fetch_returns_body_and_names_the_tool(self):
        self.assertEqual(self.get("/ok"), b'{"ok": true}')
        self.assertEqual(_Handler.seen, [("/ok", rd.USER_AGENT)])
        self.assertIn("software-lifecycle", rd.USER_AGENT)

    def test_size_cap(self):
        with self.assertRaises(rd.RefreshError):
            self.get("/big")
        with self.assertRaises(rd.RefreshError):
            self.get("/biglength")

    def test_redirect_is_refused(self):
        with self.assertRaises(rd.RefreshError):
            self.get("/redirect")
        self.assertEqual([p for p, _ in _Handler.seen], ["/redirect"])

    def test_http_error_is_refused(self):
        with self.assertRaises(rd.RefreshError):
            self.get("/missing")

    def test_plain_http_needs_the_test_flag(self):
        with self.assertRaises(rd.RefreshError):
            rd.fetch(self.base + "/ok", 1000, timeout=5)
        self.assertEqual(_Handler.seen, [])

    def test_test_flag_only_opens_loopback(self):
        for url in ("http://example.com/ok", "http://localhost.example/ok",
                    "ftp://127.0.0.1/ok", "file:///etc/passwd"):
            with self.assertRaises(rd.RefreshError, msg=url):
                rd.fetch(url, 1000, timeout=5, allow_loopback_http=True)

    def test_https_only_by_default(self):
        for url in ("http://www.cisa.gov/x", "file:///etc/passwd",
                    "https://", "ftp://example.com/x"):
            with self.assertRaises(rd.RefreshError, msg=url):
                rd.fetch(url, 1000, timeout=5)


if __name__ == "__main__":
    unittest.main()
