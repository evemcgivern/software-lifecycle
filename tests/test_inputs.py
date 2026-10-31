import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swlc import inputs, safeio
from swlc.errors import DataError, InputError
from swlc.inputs import group_rows, item_id, map_columns, read_rows


class TempCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, data, name="in.csv"):
        p = self.dir / name
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return str(p)


class ReadRowsTests(TempCase):
    def test_allow_empty_header_only(self):
        p = self.write("Name,Version\n")
        self.assertEqual(read_rows(p, allow_empty=True), ([], ["Name", "Version"]))
        with self.assertRaises(InputError):
            read_rows(p)
        with self.assertRaises(InputError):
            read_rows(self.write(""), allow_empty=True)

    def test_reads_rows_and_headers(self):
        p = self.write("Name,Version\nAlpha,1.0\nBeta,2\n")
        rows, headers = read_rows(p)
        self.assertEqual(headers, ["Name", "Version"])
        self.assertEqual(rows, [{"Name": "Alpha", "Version": "1.0"},
                                {"Name": "Beta", "Version": "2"}])

    def test_bom_reads_clean(self):
        p = self.write(b"\xef\xbb\xbfName,Version\nAlpha,1.0\n")
        rows, headers = read_rows(p)
        self.assertEqual(headers, ["Name", "Version"])
        self.assertEqual(rows[0]["Name"], "Alpha")

    def test_windows_1252_byte_needs_encoding_flag(self):
        p = self.write(b"Name,Version\nCaf\xe9,1\n")
        with self.assertRaises(InputError) as cm:
            read_rows(p)
        self.assertIn("--encoding", str(cm.exception))
        self.assertIn("line 2", str(cm.exception))

    def test_explicit_encoding_decodes(self):
        p = self.write(b"Name,Version\nCaf\xe9,1\n")
        rows, _ = read_rows(p, encoding="cp1252")
        self.assertEqual(rows[0]["Name"], "Café")

    def test_unknown_encoding_is_input_error(self):
        p = self.write("Name,Version\nA,1\n")
        with self.assertRaises(InputError):
            read_rows(p, encoding="no-such-codec")

    def test_header_only_raises(self):
        with self.assertRaises(InputError):
            read_rows(self.write("Name,Version\n"))

    def test_empty_file_raises(self):
        with self.assertRaises(InputError):
            read_rows(self.write(b""))

    def test_duplicate_header_raises(self):
        with self.assertRaises(InputError) as cm:
            read_rows(self.write("Name,Version,name\nA,1,B\n"))
        self.assertIn("duplicate", str(cm.exception).lower())

    def test_nul_byte_raises_with_line(self):
        with self.assertRaises(InputError) as cm:
            read_rows(self.write(b"Name,Version\nSECRETNUL\x00pha,1\n"))
        self.assertIn("line 2", str(cm.exception))
        self.assertNotIn("SECRETNUL", str(cm.exception))

    def test_oversize_field_names_line_not_text(self):
        secret = "SECRETTEXT" + "x" * 70_000
        p = self.write("Name,Version\nok,1\n%s,2\n" % secret)
        with self.assertRaises(InputError) as cm:
            read_rows(p)
        msg = str(cm.exception)
        self.assertIn("line 3", msg)
        self.assertNotIn("SECRETTEXT", msg)

    def test_custom_max_field(self):
        with self.assertRaises(InputError):
            read_rows(self.write("Name,Version\nabcdef,1\n"), max_field=5)

    def test_row_cap(self):
        p = self.write("Name,Version\nA,1\nB,2\nC,3\n")
        with self.assertRaises(InputError) as cm:
            read_rows(p, max_rows=2)
        self.assertIn("line 4", str(cm.exception))
        rows, _ = read_rows(p, max_rows=3)
        self.assertEqual(len(rows), 3)

    def test_too_many_fields_raises_without_text(self):
        with self.assertRaises(InputError) as cm:
            read_rows(self.write("Name,Version\nA,1,LEAKME\n"))
        self.assertIn("line 2", str(cm.exception))
        self.assertNotIn("LEAKME", str(cm.exception))

    def test_short_row_padded_and_blank_lines_skipped(self):
        rows, _ = read_rows(self.write("Name,Version\nA\n\nB,2\n"))
        self.assertEqual(rows, [{"Name": "A", "Version": ""},
                                {"Name": "B", "Version": "2"}])

    def test_utf16_needs_and_honors_encoding(self):
        p = self.write("Name,Version\nA,1\n".encode("utf-16"))
        rows, headers = read_rows(p, encoding="utf-16")
        self.assertEqual(headers, ["Name", "Version"])
        self.assertEqual(rows, [{"Name": "A", "Version": "1"}])
        with self.assertRaises(InputError) as cm:
            read_rows(p)
        self.assertIn("--encoding", str(cm.exception))

    def test_utf16_without_bom_nul_message_mentions_encoding(self):
        p = self.write("Name,Version\nA,1\n".encode("utf-16-le"))
        with self.assertRaises(InputError) as cm:
            read_rows(p)
        self.assertIn("--encoding", str(cm.exception))
        self.assertIn("line", str(cm.exception))

    def test_nul_with_explicit_encoding_still_rejected(self):
        with self.assertRaises(InputError) as cm:
            read_rows(self.write(b"Name,Version\nA\x00,1\n"), encoding="utf-8")
        self.assertIn("line 2", str(cm.exception))

    def test_huge_header_cell_message_bounded(self):
        big = "H" * 70_000
        for body in ("%s,%s\nA,1\n" % (big, big),):
            with self.assertRaises(InputError) as cm:
                read_rows(self.write(body))
            self.assertLess(len(str(cm.exception)), 400)
        with self.assertRaises(InputError) as cm:
            map_columns([big, "Other"], None, None)
        self.assertLess(len(str(cm.exception)), 400)

    def test_duplicate_header_gives_positions(self):
        with self.assertRaises(InputError) as cm:
            read_rows(self.write("Name,Version,name\nA,1,B\n"))
        self.assertIn("positions 1 and 3", str(cm.exception))

    def test_decode_error_has_no_chained_cause(self):
        with self.assertRaises(InputError) as cm:
            read_rows(self.write(b"Name,Version\nCaf\xe9,1\n"))
        self.assertIsNone(cm.exception.__cause__)
        self.assertTrue(cm.exception.__suppress_context__)
        with self.assertRaises(InputError) as cm:
            read_rows(self.write("Name,Version\nA,1\n"), encoding="no-such-codec")
        self.assertIsNone(cm.exception.__cause__)
        self.assertTrue(cm.exception.__suppress_context__)

    def test_byte_cap(self):
        p = self.write("Name,Version\nA,1\n")
        size = os.path.getsize(p)
        with self.assertRaises(InputError) as cm:
            read_rows(p, max_bytes=size - 1)
        self.assertNotIn("A,1", str(cm.exception))
        rows, _ = read_rows(p, max_bytes=size)
        self.assertEqual(len(rows), 1)

    def test_missing_file_is_input_error(self):
        with self.assertRaises(InputError):
            read_rows(str(self.dir / "nope.csv"))


class StrictCsvTests(TempCase):
    def test_unclosed_quote_is_refused_without_cell_text(self):
        p = self.write('Name,Version\n"SecretCell,1\n')
        with self.assertRaises(InputError) as ctx:
            read_rows(p)
        self.assertIn("malformed CSV", str(ctx.exception))
        self.assertNotIn("Secret", str(ctx.exception))

    def test_stray_quote_inside_field_is_refused(self):
        p = self.write('Name,Version\n"a"b,1\n')
        with self.assertRaises(InputError):
            read_rows(p)


class MapColumnsTests(unittest.TestCase):
    def test_missing_version_names_field(self):
        with self.assertRaises(InputError) as cm:
            map_columns(["Name", "Owner"], None, None)
        self.assertIn("version", str(cm.exception))
        self.assertIn("Owner", str(cm.exception))

    def test_generic_alias_software_name(self):
        m = map_columns(["Software Name", "Version"], None, None)
        self.assertEqual(m["name"], "Software Name")
        self.assertEqual(m["version"], "Version")

    def test_common_export_headings(self):
        m = map_columns(["Display Name", "Product Version", "Vendor",
                         "Assigned To", "Install Count", "End of Life"],
                        None, None)
        self.assertEqual(m, {"name": "Display Name", "version": "Product Version",
                             "publisher": "Vendor", "owner": "Assigned To",
                             "count": "Install Count", "export_eol": "End of Life"})

    def test_case_and_punctuation_insensitive(self):
        m = map_columns(["  PRODUCT_NAME ", "version"], None, None)
        self.assertEqual(m["name"], "  PRODUCT_NAME ")

    def test_two_headers_one_field_rejected(self):
        with self.assertRaises(InputError) as cm:
            map_columns(["Software Name", "Product", "Version"], None, None)
        self.assertIn("name", str(cm.exception))

    def test_profile_and_extra_aliases(self):
        prof = {"name": ["Application"], "version": ["Build"]}
        m = map_columns(["Application", "Build", "Team"], prof, {"owner": ["Team"]})
        self.assertEqual(m["name"], "Application")
        self.assertEqual(m["version"], "Build")
        self.assertEqual(m["owner"], "Team")

    def test_unknown_headers_ignored(self):
        m = map_columns(["Name", "Version", "Colour"], None, None)
        self.assertEqual(set(m), {"name", "version"})

    def test_parent_aliases_map(self):
        for heading in ("Parent", "Parent Software", "Suite", "Bundle"):
            with self.subTest(heading=heading):
                m = map_columns(["Name", "Version", heading], None, None)
                self.assertEqual(m["parent"], heading)
        self.assertIn("parent", inputs.OPTIONAL)


class ItemIdTests(unittest.TestCase):
    def test_stable_and_12_hex(self):
        a = item_id("Acme", "Widget", "1.0")
        self.assertEqual(a, item_id("Acme", "Widget", "1.0"))
        self.assertEqual(len(a), 12)
        int(a, 16)

    def test_normalizes_inputs(self):
        self.assertEqual(item_id("ACME", "Widget  (64-bit)", "1.0"),
                         item_id("acme", "widget", "1.0"))

    def test_differs_by_field(self):
        self.assertNotEqual(item_id("a", "b", "c"), item_id("a", "bc", ""))

    def test_new_alias_does_not_change_id(self):
        before = item_id("Acme", "Widget", "1.0")
        map_columns(["Name", "Version"], None, {"name": ["Brand New Heading"]})
        self.assertEqual(before, item_id("Acme", "Widget", "1.0"))


class GroupRowsTests(unittest.TestCase):
    cm = {"name": "N", "version": "V", "publisher": "P", "owner": "O",
          "export_eol": "E"}

    def test_groups_on_normalized_key(self):
        rows = [
            {"N": "Widget", "V": "1.0", "P": "Acme", "O": "zed", "E": ""},
            {"N": "WIDGET (64-bit)", "V": "1.0", "P": "acme", "O": "amy", "E": "2027-01-01"},
            {"N": "Widget", "V": "2.0", "P": "Acme", "O": "", "E": ""},
        ]
        g = group_rows(rows, self.cm)
        self.assertEqual(len(g), 2)
        gid = item_id("Acme", "Widget", "1.0")
        self.assertEqual(g[gid]["id"], gid)
        self.assertEqual(g[gid]["rows"], 2)
        self.assertEqual(g[gid]["owners"], ["amy", "zed"])
        self.assertEqual(g[gid]["export_eols"], ["2027-01-01"])

    def test_export_dates_sorted_distinct_any_order(self):
        rows = [
            {"N": "W", "V": "1", "P": "A", "O": "", "E": "2027-05-01"},
            {"N": "W", "V": "1", "P": "A", "O": "", "E": "2026-01-01"},
            {"N": "W", "V": "1", "P": "A", "O": "", "E": ""},
            {"N": "W", "V": "1", "P": "A", "O": "", "E": "2027-05-01"},
        ]
        for order in (rows, list(reversed(rows))):
            (grp,) = group_rows(order, self.cm).values()
            self.assertEqual(grp["export_eols"], ["2026-01-01", "2027-05-01"])

    def test_optional_columns_absent(self):
        g = group_rows([{"N": "W", "V": "1"}], {"name": "N", "version": "V"})
        (grp,) = g.values()
        self.assertEqual(grp["owners"], [])
        self.assertEqual(grp["export_eols"], [])

    def test_group_collects_distinct_parents(self):
        cm = {"name": "N", "version": "V", "parent": "S"}
        rows = [{"N": "W", "V": "1", "S": "Suite B"},
                {"N": "W", "V": "1", "S": " Suite A "},
                {"N": "W", "V": "1", "S": ""},
                {"N": "W", "V": "1", "S": "Suite B"},
                {"N": "X", "V": "1", "S": ""}]
        g = group_rows(rows, cm)
        self.assertEqual(g[item_id("", "W", "1")]["parents"],
                         ["Suite A", "Suite B"])
        self.assertEqual(g[item_id("", "X", "1")]["parents"], [])
        (grp,) = group_rows([{"N": "W", "V": "1"}],
                            {"name": "N", "version": "V"}).values()
        self.assertEqual(grp["parents"], [])

    def test_id_collision_raises_data_error(self):
        rows = [{"N": "ZQXONE", "V": "1"}, {"N": "ZQXTWO", "V": "1"}]
        original = inputs.item_id
        inputs.item_id = lambda p, n, v: "000000000000"
        try:
            with self.assertRaises(DataError) as cm:
                group_rows(rows, {"name": "N", "version": "V"})
        finally:
            inputs.item_id = original
        self.assertNotIn("ZQX", str(cm.exception))


class WriteTextTests(TempCase):
    @unittest.skipIf(sys.platform == "win32", "Windows has no POSIX file modes")
    def test_writes_with_mode_600(self):
        out = str(self.dir / "out.txt")
        safeio.write_text(out, "hello")
        self.assertEqual(Path(out).read_text(), "hello")
        self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o600)

    def test_overwrites_existing_regular_file(self):
        out = str(self.dir / "out.txt")
        Path(out).write_text("old")
        safeio.write_text(out, "new")
        self.assertEqual(Path(out).read_text(), "new")
        if sys.platform != "win32":  # no POSIX file modes on Windows
            self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o600)

    def test_refuses_input_path(self):
        p = self.write("Name,Version\nA,1\n")
        with self.assertRaises(InputError):
            safeio.write_text(p, "x", input_path=p)
        self.assertIn("Name", Path(p).read_text())

    def test_refuses_input_path_via_other_spelling(self):
        p = self.write("keep")
        alias = str(self.dir / "." / "in.csv")
        with self.assertRaises(InputError):
            safeio.write_text(alias, "x", input_path=p)
        self.assertEqual(Path(p).read_text(), "keep")

    def test_refuses_symlink_target(self):
        real = self.dir / "real.txt"
        real.write_text("keep")
        link = self.dir / "link.txt"
        os.symlink(real, link)
        with self.assertRaises(InputError):
            safeio.write_text(str(link), "x")
        self.assertEqual(real.read_text(), "keep")

    def test_no_temp_file_left_behind_on_refusal(self):
        real = self.dir / "real.txt"
        real.write_text("keep")
        link = self.dir / "link.txt"
        os.symlink(real, link)
        try:
            safeio.write_text(str(link), "x")
        except InputError:
            pass
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()),
                         ["link.txt", "real.txt"])


if __name__ == "__main__":
    unittest.main()
