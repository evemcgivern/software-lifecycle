"""Checks on the committed data/ folder. Reads files only, never the network.

Dates come from the manifest itself, so these tests do not start failing
because the bundled data aged.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from helpers import run_main, write_inventory  # noqa: E402
from swlc.data import load_data  # noqa: E402

DATA = ROOT / "data"
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
        self.assertTrue(MANIFEST["release_id"].startswith("bundled-"))


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
