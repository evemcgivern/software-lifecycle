"""Item classification: governable, component, bundle_member, unknown.

Uses the fixture data folder plus inline catalog records and curation dicts,
so these tests never depend on the bundled data's dates or contents.
"""
from __future__ import annotations

import dataclasses
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swlc import classify as C  # noqa: E402
from swlc.data import load_data  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
