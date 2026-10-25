import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swlc.errors import InputError
from swlc.overrides import (Exceptions, Golden, file_hash, load_exceptions,
                            load_golden, load_tracking)

GH = "schema_version,product,source,manual_eol,reason,set_by,set_on,review_by\n"
EH = ("schema_version,product,scope,compensating_controls,risk_owner,"
      "approver,requested_by,expires_on,reference\n")
TH = "schema_version,item_id,change_ref,problem_ref\n"


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, data, name="o.csv"):
        p = self.dir / name
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return str(p)


class GoldenTests(Base):
    def test_none_is_empty(self):
        g = load_golden(None)
        self.assertEqual(g.expired(date(2026, 1, 1)), [])
        self.assertIsNone(g.for_product("nginx", "nginx"))

    def test_manual_without_eol_raises(self):
        p = self.write(GH + "1,nginx,manual,,why,eve,2026-01-01,2027-01-01\n")
        with self.assertRaises(InputError):
            load_golden(p)

    def test_unknown_source_raises(self):
        p = self.write(GH + "1,nginx,guess,,,,,\n")
        with self.assertRaises(InputError):
            load_golden(p)

    def test_unknown_schema_version_plain_message(self):
        p = self.write(GH + "2,nginx,export,,,,,\n")
        with self.assertRaises(InputError) as cm:
            load_golden(p)
        self.assertIn("schema_version", str(cm.exception))
        self.assertNotIn("nginx", str(cm.exception))

    def test_missing_schema_version_column_raises(self):
        p = self.write("product,source\nnginx,export\n")
        with self.assertRaises(InputError):
            load_golden(p)

    def test_bad_date_names_row_not_text(self):
        p = self.write(GH + "1,nginx,manual,SECRETDATE,r,e,2026-01-01,\n")
        with self.assertRaises(InputError) as cm:
            load_golden(p)
        self.assertNotIn("SECRETDATE", str(cm.exception))
        self.assertNotIn("nginx", str(cm.exception))
        self.assertIn("manual_eol", str(cm.exception))
        for bad in ("2026-1-1", "20260101", "2026-02-30", "01/02/2026"):
            q = self.write(GH + "1,nginx,manual,%s,r,e,,\n" % bad)
            with self.assertRaises(InputError):
                load_golden(q)

    def test_expired_review_by_inclusive(self):
        p = self.write(GH + "1,nginx,manual,2026-12-31,r,eve,2026-01-01,2026-06-30\n")
        g = load_golden(p)
        row = g.for_product("nginx", "nginx")
        self.assertEqual(row["manual_eol"], date(2026, 12, 31))
        self.assertEqual(g.expired(date(2026, 6, 30)), [])
        self.assertFalse(g.is_expired(row, date(2026, 6, 30)))
        self.assertEqual(g.expired(date(2026, 7, 1)), [row])
        self.assertTrue(g.is_expired(row, date(2026, 7, 1)))

    def test_empty_review_by_never_expires(self):
        p = self.write(GH + "1,nginx,export,,,,,\n")
        self.assertEqual(load_golden(p).expired(date(2099, 1, 1)), [])

    def test_product_key_slug_vs_name(self):
        p = self.write(GH + "1,microsoft-office,export,,,,,\n"
                       "1,  Adobe  Reader (64-bit) ,endoflife.date,,,,,\n")
        g = load_golden(p)
        self.assertEqual(g.for_product("microsoft-office", "office")["source"],
                         "export")
        self.assertEqual(g.for_product("x", "adobe reader")["source"],
                         "endoflife.date")
        self.assertIsNone(g.for_product("adobe-reader", "other"))

    def test_duplicate_product_raises(self):
        p = self.write(GH + "1,Nginx,export,,,,,\n1,nginx,export,,,,,\n")
        with self.assertRaises(InputError):
            load_golden(p)

    def test_bom_file(self):
        p = self.write(b"\xef\xbb\xbf" + (GH + "1,nginx,export,,,,,\n").encode())
        self.assertIsNotNone(load_golden(p).for_product("nginx", "nginx"))

    def test_header_only_loads_empty_zero_byte_raises(self):
        self.assertEqual(load_golden(self.write(GH)).rows, {})
        self.assertEqual(load_exceptions(self.write(EH)).rows, {})
        self.assertEqual(load_tracking(self.write(TH)), {})
        for load in (load_golden, load_exceptions, load_tracking):
            with self.assertRaises(InputError):
                load(self.write(""))

    def test_header_only_missing_column_still_raises(self):
        with self.assertRaises(InputError):
            load_golden(self.write("schema_version,product\n"))

    def test_manual_eol_with_other_source_raises(self):
        p = self.write(GH + "1,nginx,export,2026-01-01,,,,\n")
        with self.assertRaises(InputError) as cm:
            load_golden(p)
        self.assertIn("manual_eol", str(cm.exception))
        self.assertIn("not counting the header", str(cm.exception))

    def test_bad_encoding_uses_reader_behavior(self):
        p = self.write(GH.encode() + b"1,caf\xe9,export,,,,,\n")
        with self.assertRaises(InputError) as cm:
            load_golden(p)
        self.assertIn("--encoding", str(cm.exception))


class ExceptionsTests(Base):
    ROW = "1,nginx,site-a,mfa,risk,boss,dev,2026-06-30,CHG1\n"

    def test_none_is_empty(self):
        self.assertFalse(load_exceptions(None).active("nginx", "x",
                                                      date(2026, 1, 1)))

    def test_active_inclusive_of_expiry_day(self):
        e = load_exceptions(self.write(EH + self.ROW))
        self.assertTrue(e.active("nginx", "site-a", date(2026, 6, 30)))
        self.assertFalse(e.active("nginx", "site-a", date(2026, 7, 1)))
        self.assertFalse(e.active("nginx", "site-b", date(2026, 6, 1)))
        self.assertFalse(e.active("other", "site-a", date(2026, 6, 1)))

    def test_find_returns_row(self):
        e = load_exceptions(self.write(EH + self.ROW))
        row = e.find("nginx", "SITE-A ")
        self.assertEqual(row["reference"], "CHG1")
        self.assertEqual(row["risk_owner"], "risk")
        self.assertEqual(row["approver"], "boss")
        self.assertEqual(row["expires_on"], date(2026, 6, 30))
        self.assertIsNone(e.find("nginx", "nope"))

    def test_lookup_by_normalized_name(self):
        e = load_exceptions(self.write(
            EH + "1,Adobe Reader,s,,r,a,b,2026-06-30,R\n"))
        self.assertTrue(e.active("adobe reader (64-bit)", "s", date(2026, 1, 1)))

    def test_approver_equals_requester_raises(self):
        p = self.write(EH + "1,nginx,s,,r,  Eve ,eve,2026-06-30,R\n")
        with self.assertRaises(InputError) as cm:
            load_exceptions(p)
        self.assertNotIn("Eve", str(cm.exception))

    def test_scope_plain_key(self):
        e = load_exceptions(self.write(
            EH + "1,nginx,x64,,r,a,b,2026-06-30,R\n"
            "1,nginx,x86,,r,a,b,2026-06-30,R\n"))
        self.assertTrue(e.active("nginx", "x64", date(2026, 1, 1)))
        self.assertTrue(e.active("nginx", "X86", date(2026, 1, 1)))
        self.assertFalse(e.active("nginx", "", date(2026, 1, 1)))

    def test_approver_comparison_key(self):
        for a, b in (("A  Smith", "a smith"), ("\uff21 Smith", "A Smith")):
            with self.assertRaises(InputError):
                load_exceptions(self.write(
                    EH + "1,nginx,s,,r,%s,%s,2026-06-30,R\n" % (a, b)))

    def test_required_fields(self):
        for col in range(3, 9):
            if col == 3:  # controls are not required
                continue
            cells = ["1", "nginx", "s", "c", "r", "a", "b", "2026-06-30", "R"]
            cells[col] = ""
            with self.assertRaises(InputError, msg=str(col)):
                load_exceptions(self.write(EH + ",".join(cells) + "\n"))

    def test_bad_date_no_echo(self):
        p = self.write(EH + "1,nginx,s,c,r,a,b,SECRETDATE,R\n")
        with self.assertRaises(InputError) as cm:
            load_exceptions(p)
        self.assertNotIn("SECRETDATE", str(cm.exception))

    def test_unknown_version_raises(self):
        with self.assertRaises(InputError):
            load_exceptions(self.write(EH + "3,nginx,s,c,r,a,b,2026-06-30,R\n"))

    def test_duplicate_product_scope_raises(self):
        with self.assertRaises(InputError):
            load_exceptions(self.write(EH + self.ROW + self.ROW))

    def test_same_product_different_scope_ok(self):
        e = load_exceptions(self.write(
            EH + self.ROW + "1,nginx,site-b,,r,a,b,2026-06-30,R\n"))
        self.assertTrue(e.active("nginx", "site-b", date(2026, 6, 1)))

    def test_type(self):
        self.assertIsInstance(load_exceptions(None), Exceptions)
        self.assertIsInstance(load_golden(None), Golden)


class TrackingTests(Base):
    def test_none_is_empty(self):
        self.assertEqual(load_tracking(None), {})

    def test_keyed_by_item_id(self):
        t = load_tracking(self.write(TH + "1,abc123,CHG1,PRB2\n1,def456,,\n"))
        self.assertEqual(t["abc123"], {"change_ref": "CHG1",
                                       "problem_ref": "PRB2"})
        self.assertEqual(t["def456"], {"change_ref": "", "problem_ref": ""})

    def test_duplicate_id_raises(self):
        with self.assertRaises(InputError):
            load_tracking(self.write(TH + "1,abc,C,P\n1,abc,C,P\n"))

    def test_empty_id_and_bad_version_raise(self):
        with self.assertRaises(InputError):
            load_tracking(self.write(TH + "1,,C,P\n"))
        with self.assertRaises(InputError):
            load_tracking(self.write(TH + "9,abc,C,P\n"))


class HashTests(Base):
    def test_absent_is_empty_string(self):
        self.assertEqual(file_hash(None), "")
        self.assertEqual(file_hash(str(self.dir / "missing.csv")), "")

    def test_known_value_and_changes(self):
        p = self.write(b"abc")
        self.assertEqual(
            file_hash(p),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        q = self.write(b"abd", name="q.csv")
        self.assertNotEqual(file_hash(p), file_hash(q))


if __name__ == "__main__":
    unittest.main()
