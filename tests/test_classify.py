"""Item classification: governable, component, bundle_member, unknown.

Uses the fixture data folder plus inline catalog records and curation dicts,
so these tests never depend on the bundled data's dates or contents.
"""
from __future__ import annotations

import csv
import dataclasses
import json
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swlc import assess as A  # noqa: E402
from swlc import classify as C  # noqa: E402
from swlc.data import load_data  # noqa: E402
from swlc.inputs import group_rows, item_id, map_columns, read_rows  # noqa
from swlc.overrides import Exceptions, Golden  # noqa: E402

FIXTURE_DATA = ROOT / "tests" / "fixtures" / "data"

EXTRA = {
    # id: (title, category, cycles)
    "libreoffice": ("LibreOffice", "app", ["7.4", "7.5"]),
    "eclipse-temurin": ("Eclipse Temurin", "lang", ["11", "21"]),
    "dotnet": ("Microsoft .NET", "framework", ["6", "8"]),
    "office": ("Microsoft Office", "app", ["2016", "2019", "2021"]),
    "pixel": ("Google Pixel", "device", ["8"]),
}
SOURCE = "https://example.com/vendor-page"


def make_data(**curation):
    base = load_data(str(FIXTURE_DATA), as_of=date(2026, 10, 24))
    catalog = dict(base.catalog)
    products = dict(base.products)
    for pid, (title, category, cycles) in EXTRA.items():
        catalog[pid] = {"id": pid, "title": title, "category": category,
                        "vendors": [], "namespaces": []}
        products[pid] = [{"cycle": c, "eol": False, "support": True,
                          "extended": None} for c in cycles]
    cur = dict(base.curation)
    cur.update(curation)
    return dataclasses.replace(base, catalog=catalog, products=products,
                               curation=cur)


def item(name, version="", product=None, publisher=""):
    return {"id": "000000000000", "name": name, "version": version,
            "publisher": publisher, "product": product, "cycle": None}


def run(data, name, version="", product=None, publisher=""):
    return C.classify(item(name, version, product, publisher), publisher,
                      data)


OUTLOOK = {"name_prefix": "microsoft outlook", "publisher": "microsoft",
           "parent": "office", "reason": "sold in the suite",
           "source": SOURCE,
           "gold": "Microsoft Outlook 2019|Microsoft Corporation|1"}


class PartKindTests(unittest.TestCase):
    def test_part_words_only_fire_as_last_word(self):
        self.assertIsNone(C.part_kind("Runtime"))
        self.assertIsNone(C.part_kind("Android SDK Manager"))
        self.assertIsNone(C.part_kind("Driver Booster"))
        self.assertEqual(C.part_kind("Intel Graphics Driver"), "os_part")
        self.assertEqual(C.part_kind("Microsoft Windows Desktop Runtime"),
                         "part")

    def test_os_part_patterns(self):
        for name in ("Security Update for Windows (KB5031356)",
                     "Hotfix for Office", "Language Pack"):
            with self.subTest(name=name):
                self.assertEqual(C.part_kind(name), "os_part")

    def test_trailing_version_and_arch_are_ignored(self):
        self.assertEqual(C.part_kind(
            "Microsoft Visual C++ 2015-2022 Redistributable (x64) - "
            "14.36.32532"), "part")
        self.assertEqual(C.part_kind("Contoso Toolkit SDK 3.1"), "part")

    def test_tuned_patterns(self):
        for name, kind in (
                ("Microsoft ODBC Driver 18 for SQL Server", "os_part"),
                ("Samsung USB Driver for Mobile Phones", "os_part"),
                ("Microsoft Teams Meeting Add-in for Microsoft Office",
                 "part"),
                ("VP9 Video Extensions", "part"),
                ("fonts-liberation", "part"), ("font-fira-code", "part"),
                ("ttf-mscorefonts-installer", "part"),
                ("Lucerne Publishing Add-in Manager", None),
                ("Contoso Device Driver Manager", None),
                ("Library", None), ("Font Manager", None)):
            with self.subTest(name=name):
                self.assertEqual(C.part_kind(name), kind)

    def test_part_words_inside_an_app_name_do_not_fire(self):
        for name in ("Redistributable Packages Helper",
                     "Fabrikam Language Pack Studio",
                     "Margie's Travel Hotfix Utility", "Plugin",
                     "Extension", "Java Runtime Helper"):
            with self.subTest(name=name):
                self.assertIsNone(C.part_kind(name))


class ClassifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = make_data()

    def test_lib_prefix_skips_a_catalog_title(self):
        self.assertEqual(run(self.data, "libreoffice", "4:7.4.7-1",
                             "libreoffice").cls, "governable")
        self.assertEqual(run(self.data, "libreoffice-writer",
                             "4:7.4.7-1").cls, "unknown")
        self.assertEqual(run(self.data, "libssl3", "3.0.14-1").cls,
                         "component")
        self.assertEqual(run(self.data, "zlib1g-dev", "1:1.2.13").cls,
                         "component")

    def test_redistributable_is_component(self):
        got = run(self.data, "Microsoft Visual C++ 2015-2022 "
                  "Redistributable (x64)", "14.36.32532.0")
        self.assertEqual(got.cls, "component")
        self.assertIn("name_part", got.basis)
        self.assertIsNone(got.parent_ref)

    def test_os_part_is_component_without_a_parent(self):
        got = run(self.data, "Security Update for Windows (KB5031356)", "1")
        self.assertEqual((got.cls, got.basis), ("component",
                                                ("name_os_part",)))

    def test_standalone_runtime_is_governable(self):
        got = run(self.data, "Eclipse Temurin JDK with Hotspot 21.0.3+9 "
                  "(x64)", "21.0.3.9", "eclipse-temurin")
        self.assertEqual(got.cls, "governable")
        self.assertEqual(list(got.basis),
                         ["category_governable", "standalone_by_default"])
        data = make_data(classification_products={"dotnet": {
            "class": "governable", "reason": "standalone runtime",
            "source": SOURCE}})
        got = run(data, "Microsoft .NET Runtime - 8.0.7 (x64)", "8.0.7",
                  "dotnet")
        self.assertEqual(got.cls, "governable")
        self.assertEqual(list(got.basis),
                         ["product_override", "standalone_by_default"])
        # Without the product override, a trailing "Runtime" is a part.
        got = run(self.data, "Microsoft .NET Runtime - 8.0.7 (x64)", "8.0.7",
                  "dotnet")
        self.assertEqual(got.cls, "component")

    def test_framework_and_device_are_unknown(self):
        got = run(self.data, "Microsoft .NET", "8.0.7", "dotnet")
        self.assertEqual((got.cls, got.basis),
                         ("unknown", ("category_unknown",)))
        got = run(self.data, "Pixel 8", "14", "pixel")
        self.assertEqual((got.cls, got.basis),
                         ("unknown", ("device_category",)))

    def test_unmatched_with_no_signal_is_unknown(self):
        for name in ("Mystery Tool", "Runtime", "Driver Booster",
                     "Android SDK Manager", "Contoso Orders Server"):
            with self.subTest(name=name):
                got = run(self.data, name, "1.0")
                self.assertEqual(got.cls, "unknown")
                self.assertNotEqual(got.cls, "governable")
        self.assertEqual(run(self.data, "Mystery Tool", "1.0").basis,
                         ("no_signal",))

    def test_version_shape_breaks_a_tie_toward_unknown(self):
        got = run(self.data, "Example SQL", "", "examplesql")
        self.assertEqual(got.cls, "unknown")
        self.assertEqual(list(got.basis),
                         ["category_governable", "version_shape"])
        self.assertEqual(run(self.data, "Example SQL 16", "",
                             "examplesql").cls, "governable")

    def test_row_override_wins(self):
        row = {"name": "microsoft windows desktop runtime",
               "publisher": "microsoft", "class": "governable",
               "reason": "standalone runtime", "source": SOURCE,
               "gold": "a|b|c"}
        data = make_data(classification_rows=[row])
        got = run(data, "Microsoft Windows Desktop Runtime - 8.0.7 (x64)",
                  "8.0.7.33815", publisher="Microsoft Corporation")
        self.assertEqual(got.cls, "governable")
        self.assertEqual(got.basis[0], "row_override")
        self.assertIn("name_part", got.basis)
        # The publisher only confirms the curated entry.
        got = run(data, "Microsoft Windows Desktop Runtime - 8.0.7 (x64)",
                  "8.0.7.33815", publisher="Contoso Ltd")
        self.assertEqual(got.cls, "component")

    def test_suite_member_needs_one_cycle(self):
        data = make_data(bundle_parents=[OUTLOOK])
        got = run(data, "Microsoft Outlook 2019", "16.0.10396.20017",
                  publisher="Microsoft Corporation")
        self.assertEqual(got.cls, "bundle_member")
        self.assertEqual(got.parent_ref, {"kind": "product",
                                          "value": "office/2019",
                                          "basis": "curated_parent"})
        self.assertEqual(got.basis[0], "curated_parent")
        got = run(data, "Microsoft Outlook", "16.0.17928",
                  publisher="Microsoft Corporation")
        self.assertEqual(got.cls, "unknown")
        self.assertIn("suite_no_fit", got.basis)
        self.assertIsNone(got.parent_ref)
        # Whole leading words only.
        got = run(data, "Microsoft Outlookish 2019", "1",
                  publisher="Microsoft Corporation")
        self.assertNotEqual(got.cls, "bundle_member")

    def test_publisher_alone_never_decides(self):
        data = make_data(bundle_parents=[OUTLOOK])
        for name, version, product in (
                ("Example SQL", "16", "examplesql"),
                ("Mystery Tool", "1.0", None),
                ("Contoso Graphics Driver", "2.0", None),
                ("Microsoft Outlook 2019", "16.0", None)):
            with self.subTest(name=name):
                a = run(data, name, version, product, "Contoso Ltd")
                b = run(data, name, version, product, "Fabrikam Inc")
                self.assertEqual(a, b)
        # A curated entry needs its publisher word; without it, no link.
        got = run(data, "Microsoft Outlook 2019", "16.0", None,
                  "Contoso Ltd")
        self.assertEqual(got.cls, "unknown")

    def test_component_outranks_governable(self):
        got = run(self.data, "Example SQL Plugin", "16", "examplesql")
        self.assertEqual(got.cls, "component")
        self.assertEqual(list(got.basis),
                         ["name_part", "category_governable"])

    def test_product_override_classes(self):
        data = make_data(classification_products={"examplesql": {
            "class": "unknown", "reason": "r", "source": SOURCE}})
        got = run(data, "Example SQL", "16", "examplesql")
        self.assertEqual((got.cls, got.basis[0]),
                         ("unknown", "product_override"))


SUITE = [dict(OUTLOOK, name_prefix="microsoft " + app)
         for app in ("access", "excel", "word")]
DOTNET = [{"name_prefix": prefix, "publisher": "microsoft",
           "parent": "dotnet", "reason": "part of a .NET bundle",
           "source": SOURCE, "gold": "a|b|c"}
          for prefix in ("microsoft .net host",
                         "microsoft .net host fx resolver")]
PATCH = [{"name_prefix": prefix, "publisher": "microsoft",
          "parent": parent, "reason": "patches that release",
          "source": SOURCE, "gold": "a|b|c"}
         for prefix, parent in (("cumulative update for windows", "demoos"),
                                ("microsoft office proofing tools",
                                 "office"))]
MS = "Microsoft Corporation"


class SuiteTailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = make_data(bundle_parents=sorted(
            SUITE + DOTNET + PATCH, key=lambda e: e["name_prefix"]))

    def test_link_needs_a_tail_of_version_words(self):
        for name in ("Microsoft Excel 2016", "Microsoft Excel 2016 (x64)",
                     "Microsoft Excel - 2016"):
            with self.subTest(name=name):
                got = run(self.data, name, "16.0.4266.1001", publisher=MS)
                self.assertEqual(got.cls, "bundle_member")
                self.assertEqual(got.parent_ref["value"], "office/2016")

    def test_other_words_in_the_tail_give_no_link(self):
        for name in ("Microsoft Excel 2016 Viewer",
                     "Microsoft Word Mobile 2019",
                     "Microsoft Access 2016 Runtime",
                     "Microsoft Access Runtime 2016"):
            with self.subTest(name=name):
                got = run(self.data, name, "16.0.4266.1001", publisher=MS)
                self.assertEqual(got.cls, "unknown")
                self.assertIn("suite_no_fit", got.basis)
                self.assertIsNone(got.parent_ref)

    def test_the_longest_prefix_wins(self):
        got = run(self.data, "Microsoft .NET Host FX Resolver - 8.0.7 (x64)",
                  "8.0.7.33815", publisher=MS)
        self.assertEqual((got.cls, got.parent_ref["value"]),
                         ("bundle_member", "dotnet/8"))

    def test_allowed_patch_and_language_tails(self):
        data = make_data(bundle_parents=[dict(
            PATCH[0], parent="windows")])
        catalog = dict(data.catalog, windows={
            "id": "windows", "title": "Microsoft Windows", "category": "os",
            "vendors": [], "namespaces": []})
        products = dict(data.products, windows=[
            {"cycle": c, "eol": False, "support": True, "extended": None}
            for c in ("10-22h2", "11-24h2-w")])
        data = dataclasses.replace(data, catalog=catalog, products=products)
        got = run(data, "Cumulative Update for Windows 10 Version 22H2 for "
                  "x64-based Systems (KB5039211)", "1", publisher=MS)
        self.assertEqual(got.parent_ref["value"], "windows/10-22h2")
        got = run(self.data, "Microsoft Office Proofing Tools 2019 - English",
                  "16.0.10396.20017", publisher=MS)
        self.assertEqual(got.parent_ref["value"], "office/2019")
        got = run(data, "Cumulative Update for Windows 10 Version 22H2 for "
                  "x64-based Systems Preview (KB5039211)", "1", publisher=MS)
        self.assertEqual(got.cls, "unknown")


class SpeedTests(unittest.TestCase):
    def test_lib_rows_do_not_rescan_the_catalog(self):
        data = make_data()
        catalog = dict(data.catalog)
        for n in range(500):
            pid = "product%03d" % n
            catalog[pid] = {"id": pid, "title": "Product %03d Server" % n,
                            "category": "app", "vendors": [],
                            "namespaces": []}
        data = dataclasses.replace(data, catalog=catalog)
        start = time.perf_counter()
        for n in range(20000):
            C.classify(item("libthing%d" % n, "1.0"), "", data)
        self.assertLess(time.perf_counter() - start, 2.0)


class ApplyTests(unittest.TestCase):
    def test_apply_sets_every_key(self):
        data = make_data()
        items = [item("libssl3", "3.0"), item("Example SQL", "16",
                                               "examplesql")]
        C.apply_classification(items, {}, data)
        for it in items:
            self.assertEqual(
                {k: it[k] for k in ("classification", "classification_basis",
                                    "parent_ref", "inherited_from",
                                    "inherited_lifecycle")}.keys(),
                {"classification", "classification_basis", "parent_ref",
                 "inherited_from", "inherited_lifecycle"})
            self.assertIn(it["classification"], C.CLASSES)
            self.assertIsInstance(it["classification_basis"], list)
            self.assertIsNone(it["inherited_from"])
            self.assertIsNone(it["inherited_lifecycle"])
        self.assertEqual([it["classification"] for it in items],
                         ["component", "governable"])

    def test_no_curation_still_classifies(self):
        data = dataclasses.replace(make_data(), curation=None)
        self.assertEqual(run(data, "libssl3", "3.0").cls, "component")


ACME = "Acme Corp"
OS_PATCH = ("Security Update for Demo OS (KB5031356)", ACME, "1")


def check(rows, data=None, parent=True):
    """Assess (name, publisher, version[, parent]) rows; return the report
    dict and {(name, version): item}."""
    data = data or make_data()
    heads = ["Software Name", "Publisher", "Version"] + (
        ["Parent"] if parent else [])
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "inv.csv"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(heads)
            for r in rows:
                r = list(r) + [""] * (4 - len(r))
                writer.writerow(r[:len(heads)])
        found, headers = read_rows(str(path))
    groups = group_rows(found, map_columns(headers, None, None))
    report = A.assess(groups, data, Golden(), Exceptions(), {},
                      date(2026, 10, 24))
    return report, {(it["name"], it["version"]): it
                    for it in report["items"]}


def ident(name, publisher, version):
    return item_id(publisher, name, version)


DOTNET_ROW = {"name": "microsoft .net runtime", "publisher": "microsoft",
              "class": "governable", "reason": "standalone runtime",
              "source": SOURCE, "gold": "a|b|c"}


class ParentTests(unittest.TestCase):
    def test_os_part_links_only_to_the_one_os_item(self):
        os_id = ident("Demo OS 2.0", ACME, "2.0")
        _r, items = check([("Demo OS 2.0", ACME, "2.0"), OS_PATCH])
        part = items[(OS_PATCH[0], "1")]
        self.assertEqual(part["classification"], "bundle_member")
        self.assertEqual(part["parent_ref"],
                         {"kind": "os", "value": os_id, "basis": C.OS_PARENT})
        self.assertEqual(part["inherited_from"], os_id)
        self.assertIn(C.OS_PARENT, part["classification_basis"])
        self.assertEqual(part["inherited_lifecycle"]["state"], "supported")

        _r, items = check([("Demo OS 1.0", ACME, "1.0"),
                           ("Demo OS 2.0", ACME, "2.0"), OS_PATCH])
        part = items[(OS_PATCH[0], "1")]
        self.assertEqual(part["classification"], "component")
        self.assertIsNone(part["parent_ref"])
        self.assertIsNone(part["inherited_from"])

        _r, items = check([OS_PATCH, ("Example SQL", "Example Vendor", "16")])
        part = items[(OS_PATCH[0], "1")]
        self.assertEqual(part["classification"], "component")
        self.assertIsNone(part["parent_ref"])
        self.assertIsNone(part["inherited_from"])

    def test_os_part_version_token_must_agree(self):
        patch = ("Update for Demo OS 1.0 (KB5000001)", ACME, "1")
        _r, items = check([("Demo OS 1.0", ACME, "1.0"),
                           ("Demo OS 2.0", ACME, "2.0"), patch])
        part = items[(patch[0], "1")]
        self.assertEqual(part["classification"], "bundle_member")
        self.assertEqual(part["inherited_from"],
                         ident("Demo OS 1.0", ACME, "1.0"))
        _r, items = check([("Demo OS 2.0", ACME, "2.0"), patch])
        self.assertEqual(items[(patch[0], "1")]["classification"],
                         "component")

    def test_os_part_needs_the_os_publisher(self):
        patch = ("Security Update for Demo OS (KB5031356)", "Nobody Inc", "1")
        _r, items = check([("Demo OS 2.0", ACME, "2.0"), patch])
        self.assertEqual(items[(patch[0], "1")]["classification"],
                         "component")

    def test_parent_column_links_by_exact_name(self):
        viewer = ("Contoso Suite Viewer", "Contoso Ltd", "1.0")
        part = ("Contoso Charts", "Contoso Ltd", "1.0", "Contoso Suite")
        _r, items = check([viewer, part])
        got = items[("Contoso Charts", "1.0")]
        self.assertIsNone(got["parent_ref"])
        self.assertIsNone(got["inherited_from"])
        self.assertEqual(got["classification"], "unknown")

        suite = ("Contoso Suite", "Contoso Ltd", "1.0")
        _r, items = check([viewer, suite, part])
        got = items[("Contoso Charts", "1.0")]
        suite_id = ident(*suite)
        self.assertEqual(got["classification"], "bundle_member")
        self.assertEqual(got["parent_ref"], {"kind": "item",
                                             "value": suite_id,
                                             "basis": C.PARENT_COLUMN})
        self.assertEqual(got["inherited_from"], suite_id)
        self.assertIn(C.PARENT_COLUMN, got["classification_basis"])
        # an unmatched parent: the link is shown, the date is not
        self.assertIsNone(got["inherited_lifecycle"])
        self.assertIn(C.PARENT_NO_DATE, got["classification_basis"])

    def test_duplicate_parent_names_give_no_link(self):
        _r, items = check([
            ("Example SQL", "Example Vendor", "15"),
            ("Example SQL", "Example Vendor", "16"),
            ("Contoso Connector", "Contoso Ltd", "2.0", "Example SQL")])
        got = items[("Contoso Connector", "2.0")]
        self.assertEqual(got["classification"], "unknown")
        self.assertIn(C.PARENT_AMBIGUOUS, got["classification_basis"])
        self.assertIsNone(got["parent_ref"])
        self.assertIsNone(got["inherited_from"])
        self.assertIsNone(got["inherited_lifecycle"])

    def test_ambiguous_parent_keeps_a_name_signal(self):
        # D2: a part with its own name signal stays component, no link.
        _r, items = check([
            ("Example SQL", "Example Vendor", "15"),
            ("Example SQL", "Example Vendor", "16"),
            ("Example SQL Language Pack", "Example Vendor", "16",
             "Example SQL")])
        got = items[("Example SQL Language Pack", "16")]
        self.assertEqual(got["classification"], "component")
        self.assertIn(C.PARENT_AMBIGUOUS, got["classification_basis"])
        self.assertIsNone(got["parent_ref"])

    def test_parent_that_is_a_part_gets_no_inherited_block(self):
        # One hop only. The parent case fixture column-names-a-part fixes
        # inherited_from as null when the parent is itself a part.
        agent = ("Example SQL Agent", "Example Vendor", "16", "Example SQL")
        pack = ("Agent Report Pack", "Example Vendor", "16",
                "Example SQL Agent")
        _r, items = check([("Example SQL", "Example Vendor", "16"), agent,
                           pack])
        mid = items[("Example SQL Agent", "16")]
        self.assertEqual(mid["classification"], "bundle_member")
        self.assertEqual(mid["inherited_lifecycle"]["state"], "supported")
        got = items[("Agent Report Pack", "16")]
        self.assertEqual(got["classification"], "bundle_member")
        self.assertEqual(got["parent_ref"]["value"], ident(*agent[:3]))
        self.assertIsNone(got["inherited_from"])
        self.assertIsNone(got["inherited_lifecycle"])
        self.assertIn(C.PARENT_IS_PART, got["classification_basis"])

    def test_group_with_two_parent_values_is_unknown(self):
        _r, items = check([
            ("Example SQL", "Example Vendor", "16"),
            ("Demo OS 2.0", ACME, "2.0"),
            ("Contoso Widget", "Contoso Ltd", "1.0", "Example SQL"),
            ("Contoso Widget", "Contoso Ltd", "1.0", "Demo OS 2.0")])
        got = items[("Contoso Widget", "1.0")]
        self.assertEqual(got["classification"], "unknown")
        self.assertIn(C.PARENT_AMBIGUOUS, got["classification_basis"])
        self.assertIsNone(got["parent_ref"])
        self.assertIsNone(got["inherited_from"])

    def test_runtime_in_app_is_bundle_member(self):
        data = make_data(classification_rows=[DOTNET_ROW])
        app = ("Example SQL", "Example Vendor", "16")
        inside = ("Microsoft .NET Runtime - 8.0.10 (x64)",
                  "Microsoft Corporation", "8.0.10.34104", "Example SQL")
        alone = ("Microsoft .NET Runtime - 6.0.25 (x64)",
                 "Microsoft Corporation", "6.0.25.33121")
        _r, items = check([app, inside, alone], data)
        got = items[(inside[0], inside[2])]
        self.assertEqual(got["classification"], "bundle_member")
        self.assertIn(C.ROW_OVERRIDE, got["classification_basis"])
        self.assertIn(C.PARENT_COLUMN, got["classification_basis"])
        self.assertEqual(got["inherited_from"], ident(*app))
        self.assertEqual(items[(alone[0], alone[2])]["classification"],
                         "governable")

    def test_parent_column_never_beats_a_component_or_unknown_row(self):
        for cls in ("component", "unknown"):
            with self.subTest(cls=cls):
                data = make_data(classification_rows=[
                    dict(DOTNET_ROW, **{"class": cls})])
                inside = ("Microsoft .NET Runtime - 8.0.10 (x64)",
                          "Microsoft Corporation", "8.0.10.34104",
                          "Example SQL")
                _r, items = check([("Example SQL", "Example Vendor", "16"),
                                   inside], data)
                got = items[(inside[0], inside[2])]
                self.assertEqual(got["classification"], cls)
                self.assertIsNone(got["parent_ref"])
                self.assertIsNone(got["inherited_from"])
                self.assertIsNone(got["inherited_lifecycle"])

    def test_parent_column_beats_a_curated_suite_link(self):
        data = make_data(bundle_parents=[OUTLOOK])
        _r, items = check([
            ("Contoso Mail Suite", "Contoso Ltd", "3.0"),
            ("Microsoft Outlook 2019", "Microsoft Corporation", "16.0",
             "Contoso Mail Suite")], data)
        got = items[("Microsoft Outlook 2019", "16.0")]
        self.assertEqual(got["parent_ref"]["kind"], "item")
        self.assertEqual(got["inherited_from"],
                         ident("Contoso Mail Suite", "Contoso Ltd", "3.0"))

    def test_curated_suite_link_inherits_from_the_one_item(self):
        data = make_data(bundle_parents=[OUTLOOK])
        office = ("Microsoft Office Professional Plus 2019",
                  "Microsoft Corporation", "16.0.10399")
        part = ("Microsoft Outlook 2019", "Microsoft Corporation", "16.0")
        office_item = dict(item(office[0], office[2], "office",
                                office[1]), id=ident(*office),
                           cycle="2019", state="supported", eol_used=False,
                           support=True, extended_support=None)
        office_item["classification"] = "governable"
        part_item = dict(item(part[0], part[2], None, part[1]),
                         id=ident(*part), state="unmatched", eol_used=None,
                         support=None, extended_support=None)
        items = [office_item, part_item]
        C.apply_classification(items, {}, data)
        self.assertEqual(part_item["parent_ref"]["value"], "office/2019")
        self.assertEqual(part_item["inherited_from"], ident(*office))
        self.assertEqual(part_item["inherited_lifecycle"]["cycle"], "2019")

    def test_parent_absent_warning_and_no_date(self):
        report, items = check([("Contoso Agent", "Contoso Ltd", "1.0",
                                "Demo OS 2.0")])
        got = items[("Contoso Agent", "1.0")]
        self.assertEqual(got["classification"], "bundle_member")
        self.assertEqual(got["parent_ref"], {"kind": "product",
                                             "value": "demoos/2.0",
                                             "basis": C.PARENT_COLUMN})
        self.assertIsNone(got["inherited_from"])
        self.assertIsNone(got["inherited_lifecycle"])
        self.assertIn(C.PARENT_ABSENT, got["classification_basis"])
        self.assertNotEqual(got["state"], "supported")
        self.assertIn(A.PARENTS_ABSENT % 1, report["warnings"])
        self.assertEqual(A.PARENTS_ABSENT % 1,
                         "1 parts whose parent is not in this inventory")

    def test_no_warning_when_every_parent_is_present(self):
        report, _items = check([("Demo OS 2.0", ACME, "2.0"), OS_PATCH])
        self.assertFalse(any("not in this inventory" in w
                             for w in report["warnings"]))

    def test_parent_no_cycle_labels_no_date(self):
        _r, items = check([
            ("Example SQL", "Example Vendor", ""),
            ("Contoso Agent", "Contoso Ltd", "1.0", "Example SQL")])
        got = items[("Contoso Agent", "1.0")]
        self.assertEqual(got["classification"], "bundle_member")
        self.assertEqual(got["inherited_from"],
                         ident("Example SQL", "Example Vendor", ""))
        self.assertIsNone(got["inherited_lifecycle"])
        self.assertIn(C.PARENT_NO_DATE, got["classification_basis"])

    def test_inherited_block_never_touches_own_fields(self):
        rows = [("Tidewater Suite", "Example Corp", "4.2"),
                ("Example SQL", "Example Vendor", "15", "Tidewater Suite")]
        _r, plain = check(rows, parent=False)
        _r, linked = check(rows)
        own, got = plain[("Example SQL", "15")], linked[("Example SQL", "15")]
        for key in ("eol_used", "eol_endoflife", "state", "support",
                    "extended_support", "product", "cycle"):
            self.assertEqual(got[key], own[key], key)
        self.assertEqual(own["state"], "ends_soon")
        block = got["inherited_lifecycle"]
        parent = linked[("Tidewater Suite", "4.2")]
        self.assertEqual(block, {
            "parent_id": parent["id"], "product": "tidewatersuite",
            "cycle": "4", "eol": parent["eol_used"],
            "support": parent["support"],
            "extended_support": parent["extended_support"],
            "state": "past_eol", "label": C.INHERITED_LABEL})
        self.assertEqual(C.INHERITED_LABEL, "inherited from parent")

    def test_inherited_attention_and_not_past_eol(self):
        report, items = check([
            ("Example SQL", "Sample Systems Inc", "14"),
            ("Contoso Widget", "Contoso Ltd", "1.0", "Example SQL")])
        got = items[("Contoso Widget", "1.0")]
        self.assertEqual(got["inherited_lifecycle"]["state"], "past_eol")
        self.assertEqual(report["counts"]["inherited_attention"], 1)
        self.assertNotIn(got["id"], report["lists"]["past_eol"])
        self.assertNotIn(got["id"], report["lists"]["ends_soon"])
        self.assertIn(got["id"], report["lists"]["unmatched"])
        self.assertNotIn("lists_inherited", json.dumps(report))
        self.assertEqual(sorted(report["lists"]), sorted(A.LISTS))
        self.assertEqual(C.inherited_states,
                         ("past_eol", "ends_soon", "mainstream_ended"))

    def test_no_parent_column_means_no_column_links(self):
        report, items = check([("Example SQL", "Example Vendor", "16"),
                               ("Contoso Widget", "Contoso Ltd", "1.0")],
                              parent=False)
        self.assertEqual(report["counts"]["inherited_attention"], 0)
        self.assertIsNone(items[("Contoso Widget", "1.0")]["parent_ref"])


if __name__ == "__main__":
    unittest.main()
