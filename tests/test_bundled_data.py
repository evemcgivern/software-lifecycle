"""Checks on the committed data/ folder. Reads files only, never the network.

Dates come from the manifest itself, so these tests do not start failing
because the bundled data aged.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from helpers import run_main, write_inventory  # noqa: E402
from swlc.data import (  # noqa: E402
    load_data, validate_curation, validate_products)
from swlc.matching import match_product  # noqa: E402

# SWLC_DATA_DIR lets a test point this module at a scratch copy of data/.
DATA = Path(os.environ.get("SWLC_DATA_DIR") or ROOT / "data")
RELEASE_ID = re.compile(
    r"bundled-[0-9]{4}\.[0-9]{2}\.[0-9]{2}|main-eol-[0-9]{4}-[0-9]{2}-[0-9]{2}")
CYCLE_KEYS = {"cycle", "releaseDate", "eol", "support", "extendedSupport"}


def read(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


MANIFEST = read("manifest.json")
AS_OF = date.fromisoformat(MANIFEST["kev_date"])


def cycle_labels(product):
    return [c["cycle"] for c in read("eol/%s.json" % product)]


class BundledDataTests(unittest.TestCase):
    def test_loads_as_of_manifest_date(self):
        data = load_data(str(DATA), as_of=AS_OF)
        self.assertTrue(data.products)
        self.assertTrue(data.kev)

    def test_alias_products_and_cycles_exist(self):
        for entry in read("aliases.json")["aliases"]:
            who = "alias %r -> product %r" % (entry["key"], entry["product"])
            path = DATA / "eol" / ("%s.json" % entry["product"])
            self.assertTrue(path.is_file(), who + ": product not in data/eol")
            labels = set(cycle_labels(entry["product"]))
            targets = []
            if "cycle" in entry:
                targets.append(entry["cycle"])
            for value in entry.get("build_map", {}).values():
                targets.extend(value if isinstance(value, list) else [value])
            for target in targets:
                self.assertIn(target, labels, who + ": cycle not in product")

    def test_alias_kev_pairs_exist_in_kev(self):
        kev = read("kev.json")["entries"]
        pairs = {(e["vendorProject"], e["product"]) for e in kev}
        for entry in read("aliases.json")["aliases"]:
            if "kev" in entry:
                pair = (entry["kev"]["vendor"], entry["kev"]["product"])
                self.assertIn(pair, pairs, "alias %r: kev pair not in kev.json"
                              % entry["key"])

    def test_no_description_text_in_eol_files(self):
        files = sorted((DATA / "eol").glob("*.json"))
        self.assertTrue(files)
        for path in files:
            for cyc in json.loads(path.read_text(encoding="utf-8")):
                self.assertLessEqual(set(cyc), CYCLE_KEYS, path.name)

    def test_manifest_names_the_upstream_commit(self):
        self.assertRegex(MANIFEST["upstream_commit"], r"[0-9a-f]{40}")
        self.assertRegex(MANIFEST["upstream_commit"], r"^[0-9a-f]{40}$")
        self.assertTrue(RELEASE_ID.fullmatch(MANIFEST["release_id"]),
                        "release_id must be bundled-YYYY.MM.DD or "
                        "main-eol-YYYY-MM-DD")


class BundledCatalogTests(unittest.TestCase):
    def setUp(self):
        self.data = load_data(str(DATA), as_of=AS_OF)

    def test_manifest_is_format_2_and_lists_the_new_files(self):
        self.assertEqual(MANIFEST["data_format"], 2)
        self.assertEqual(MANIFEST["min_tool_version"], "0.1.0")
        self.assertIn("products.json", MANIFEST["files"])
        self.assertIn("curation.json", MANIFEST["files"])
        self.assertNotIn(
            "This data release has no product catalog; "
            "generated matching is off.", self.data.warnings)

    def test_catalog_has_one_record_per_eol_product(self):
        self.assertEqual(set(self.data.catalog), set(self.data.products))
        self.assertEqual(
            [p["id"] for p in read("products.json")["products"]],
            sorted(self.data.products))

    def test_catalog_files_are_canonical_json(self):
        import refresh_data
        for name in ("products.json", "curation.json"):
            raw = (DATA / name).read_bytes()
            self.assertEqual(raw, refresh_data.canonical(json.loads(raw)),
                             name)

    def test_catalog_holds_only_the_five_keys(self):
        for rec in self.data.catalog.values():
            self.assertEqual(set(rec), {"id", "title", "category", "vendors",
                                        "namespaces"})
        self.assertTrue(any(r["vendors"] for r in self.data.catalog.values()))
        self.assertTrue(
            any(r["namespaces"] for r in self.data.catalog.values()))

    def test_curation_names_only_products_in_the_data(self):
        # Trivially true while curation.json is empty; it fails as soon as
        # a weekly update removes a product that curation still names.
        validate_products(read("products.json"))
        validate_curation(self.data.curation, set(self.data.catalog))
        validate_curation(read("curation.json"), set(self.data.products))


def gold_rows():
    import csv
    path = ROOT / "tests" / "benchmark" / "gold.csv"
    with open(path, encoding="utf-8", newline="") as fh:
        return {"%s|%s|%s" % (r["name"], r["publisher"], r["version"]): r
                for r in csv.DictReader(fh)}


class BundledClassificationCuration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.curation = read("curation.json")
        cls.gold = gold_rows()

    def test_bundle_parents_exist_in_eol(self):
        parents = self.curation.get("bundle_parents", [])
        self.assertTrue(parents)
        for entry in parents:
            with self.subTest(prefix=entry["name_prefix"]):
                path = DATA / "eol" / ("%s.json" % entry["parent"])
                self.assertTrue(path.is_file(), "parent not in data/eol")
                row = self.gold.get(entry["gold"])
                self.assertIsNotNone(row, "entry cites no gold row")
                self.assertEqual(row["classification"], "bundle_member")
                self.assertEqual(row["heldout"], "0")
                m = re.fullmatch(r"product:([^/\s]+)/(\S+)",
                                 row["expected_parent"])
                self.assertIsNotNone(m, row["expected_parent"])
                self.assertEqual(m.group(1), entry["parent"])
                self.assertIn(m.group(2), cycle_labels(entry["parent"]))

    def test_classification_rows_cite_gold(self):
        for entry in self.curation.get("classification_rows", []):
            with self.subTest(name=entry["name"]):
                row = self.gold.get(entry["gold"])
                self.assertIsNotNone(row, "entry cites no gold row")
                self.assertEqual(row["classification"], entry["class"])
                self.assertEqual(row["heldout"], "0")

    def test_dotnet_and_nodejs_are_standalone_runtimes(self):
        products = self.curation.get("classification_products", {})
        for pid in ("dotnet", "nodejs"):
            self.assertEqual(products.get(pid, {}).get("class"),
                             "governable", pid)


class BundledCurationRows(unittest.TestCase):
    """Rows the maintainer's curation decisions settle on the bundled data."""
    @classmethod
    def setUpClass(cls):
        cls.data = load_data(str(DATA), AS_OF)

    def product(self, name, publisher, version):
        return match_product(name, version, self.data.aliases,
                             self.data.products,
                             catalog_index=self.data.matching_index(),
                             publisher=publisher).product

    def test_red_hat_ansible_extension_rows_stay_unmatched(self):
        # The VS Code extension redhat.ansible is named Ansible by Red Hat.
        for pub, ver in (("Red Hat", "2.10.130"), ("Red Hat", "2.9.118"),
                         ("Red Hat", "26.8.2"), ("Red Hat, Inc.", "2.16.2")):
            with self.subTest(pub=pub, ver=ver):
                self.assertIsNone(self.product("Ansible", pub, ver))

    def test_podman_needs_a_podman_publisher(self):
        # podman on PyPI (no publisher) is the API bindings, not Podman.
        for ver in ("5.4.0", "4.9.0"):
            with self.subTest(ver=ver):
                self.assertIsNone(self.product("podman", "", ver))
        for pub in ("Red Hat", "Podman Project"):
            with self.subTest(pub=pub):
                self.assertEqual(self.product("Podman", pub, "6.1.4"),
                                 "podman")


class BundledSmokeTest(unittest.TestCase):
    def test_check_with_real_products(self):
        # Ended versions stay ended, so these facts do not change.
        rows = [["Python 3.8", "", "Python Software Foundation", "a", ""],
                ["Ubuntu 18.04 LTS", "", "Canonical", "b", ""],
                ["Node.js", "12", "OpenJS Foundation", "c", ""]]
        header = ["Product", "Version", "Publisher", "Owner", "End of life"]
        with tempfile.TemporaryDirectory() as tmp:
            inv = write_inventory(Path(tmp) / "inv.csv", rows, header)
            out = Path(tmp) / "out"
            code, _, err = run_main(
                ["check", inv, "--data", str(DATA), "--as-of",
                 AS_OF.isoformat(), "--out", str(out)])
            self.assertEqual(code, 0, err)
            report = json.loads((out / "report.json").read_text("utf-8"))
        states = {i["name"]: i["state"] for i in report["items"]}
        self.assertEqual(states["Python 3.8"], "past_eol")
        self.assertEqual(states["Ubuntu 18.04 LTS"], "past_eol")
        self.assertEqual(states["Node.js"], "past_eol")
        self.assertEqual(report["lists"]["unmatched"], [])


if __name__ == "__main__":
    unittest.main()
