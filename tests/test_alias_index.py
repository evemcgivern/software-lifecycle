"""The alias table index (issue #23) against the full scan it replaces.

_full_scan is the alias loop of swlc/matching.py at 0.4.0, kept here so
the indexed lookup is compared with it on every name the suite knows."""
import copy
import csv
import json
import pickle
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from swlc.data import load_data  # noqa: E402
from swlc.matching import (  # noqa: E402
    AliasTable, _alias_hits, _check_once, _curated, _hits, _norm_key,
    _publisher_ok)
from swlc.normalize import normalize_name  # noqa: E402
from test_catalog_match import synthetic_rows  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def _full_scan(norm, aliases, publisher):
    """(hits, blocked) by testing every entry, as 0.4.0 did."""
    hits = []
    blocked = set()
    for pos, entry in enumerate(aliases, 1):
        _check_once(entry, pos)
        key = _norm_key(entry["key"])
        if not _hits(norm, key, entry["match"]):
            continue
        if _publisher_ok(entry, publisher):
            hits.append((key, entry))
        else:
            blocked.add(entry["product"])
    return hits, frozenset(blocked)


def _load(folder):
    manifest = json.loads((folder / "manifest.json").read_text(
        encoding="utf-8"))
    return load_data(str(folder), date.fromisoformat(manifest["eol_date"]))


def _csv_rows(path, name="name", publisher="publisher"):
    with open(path, encoding="utf-8", newline="") as fh:
        return [(r[name], r.get(publisher) or "") for r in csv.DictReader(fh)]


def _variants(key):
    """Names near an alias key: the key itself, longer and shorter forms,
    case, punctuation and the dropped arch tokens."""
    words = key.split()
    out = [key, key.upper(), key.lower(), key.title(), " %s " % key,
           key + " 2019", key + " 10.0.1", key + " x64", key + " (64-bit)",
           key + " en-US", key + " pro", key + ".", key + "-", key + "x",
           "the " + key, key[:-1], key.replace(" ", ""),
           key.replace(" ", "  "), key.replace(" ", "-")]
    if len(words) > 1:
        out += [" ".join(words[:-1]), " ".join(words[1:]), words[0],
                words[0] + " " + words[-1]]
    return out


class IndexMatchesFullScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = _load(ROOT / "data")
        cls.fixture = _load(HERE / "fixtures" / "data")

    def _names(self, data):
        names = set()
        for entry in data.aliases:
            for name in _variants(entry["key"]):
                names.add((name, ""))
        bench = HERE / "benchmark"
        for path in (bench / "gold.csv", bench / "silver-sample.csv",
                     bench / "unsure.csv", HERE / "corpus_versions.csv"):
            names.update(_csv_rows(path))
        names.update(_csv_rows(ROOT / "examples" / "software-inventory.csv",
                               "Software Name", "Publisher"))
        if data.catalog:
            # The timing test's names. Their random publishers are left
            # out: "" and every phrase cover both sides of each guard.
            names.update((n, "") for n, _v, _p in
                         synthetic_rows(data.catalog, 100000))
        return names

    def _compare(self, data):
        table = data.aliases
        self.assertIsInstance(table, AliasTable)
        plain = list(table)
        # Every publisher phrase at once, so guarded aliases hit, and none,
        # so they are blocked.
        every = " ".join(p for e in plain for p in e.get("publisher") or ())
        names = self._names(data)
        cases = {(normalize_name(n), pub) for n, p in names
                 for pub in (p, "", every)}
        found = blocked = 0
        for norm, pub in sorted(cases):
            want = _full_scan(norm, plain, pub)
            got = _alias_hits(norm, table, pub)
            self.assertEqual(
                ([(k, id(e)) for k, e in got[0]], got[1]),
                ([(k, id(e)) for k, e in want[0]], want[1]),
                (norm, pub))
            found += bool(want[0])
            blocked += bool(want[1])
        return len(cases), found, blocked

    def test_bundled_data_every_name(self):
        count, found, blocked = self._compare(self.data)
        self.assertGreater(count, 1000)
        self.assertGreater(found, 1000)
        self.assertGreater(blocked, 50)

    def test_fixture_data_every_name(self):
        count, found, _blocked = self._compare(self.fixture)
        self.assertGreater(found, 10)

    def test_keys_that_need_normalizing(self):
        # The bundled keys are already normalized; these are not: case,
        # spacing, a dropped arch token, a full-width letter, a key that
        # normalizes to nothing.
        forms = (str.upper, lambda k: "  %s\t" % k.replace(" ", "  "),
                 lambda k: "x64 " + k, lambda k: k + " (64-bit)",
                 lambda k: "Ａ" + k, lambda k: "x86")
        entries = [dict(e, key=form(e["key"])) for e in self.data.aliases
                   for form in forms]
        table = AliasTable(entries)
        names = {n for e in self.data.aliases for n in _variants(e["key"])}
        names |= {"a" + n for n in names} | {"", "x86"}
        for name in sorted(names):
            norm = normalize_name(name)
            got = _alias_hits(norm, table, "")
            want = _full_scan(norm, entries, "")
            self.assertEqual(
                ([(k, id(e)) for k, e in got[0]], got[1]),
                ([(k, id(e)) for k, e in want[0]], want[1]), name)

    def test_whole_result_equals_a_plain_list(self):
        data = self.data
        plain = list(data.aliases)
        for name, publisher in sorted(self._names(data))[::23]:
            for version in ("", "10.0.19045", "2019", "8.10"):
                self.assertEqual(
                    _curated(name, version, data.aliases, data.products,
                             publisher),
                    _curated(name, version, plain, data.products,
                             publisher), (name, version, publisher))


class IndexBelongsToOneTableTests(unittest.TestCase):
    def test_two_data_folders_never_share_groups(self):
        bundled = _load(ROOT / "data")
        fixture = _load(HERE / "fixtures" / "data")
        for data in (bundled, fixture):
            for entry in data.aliases:
                for _key, cand in data.aliases.candidates(
                        normalize_name(entry["key"])):
                    self.assertTrue(any(cand is e for e in data.aliases))
        self.assertIsNot(bundled.aliases._groups, fixture.aliases._groups)
        # A fixture name looked up in the bundled table, and back.
        name = normalize_name(fixture.aliases[0]["key"])
        self.assertEqual(_alias_hits(name, bundled.aliases, ""),
                         _full_scan(name, list(bundled.aliases), ""))
        self.assertEqual(_alias_hits(name, fixture.aliases, ""),
                         _full_scan(name, list(fixture.aliases), ""))

    def test_a_change_to_the_table_rebuilds_the_groups(self):
        def entry(key, product):
            return {"key": key, "product": product, "match": "prefix",
                    "version_from": "name"}
        new = entry("Foo Tool Pro 2", "new")
        changes = {
            "__init__": lambda t: t.__init__([new]),
            "__setitem__": lambda t: t.__setitem__(0, new),
            "__delitem__": lambda t: t.__delitem__(0),
            "__iadd__": lambda t: t.__iadd__([new]),
            "__imul__": lambda t: t.__imul__(2),
            "append": lambda t: t.append(new),
            "extend": lambda t: t.extend([new]),
            "insert": lambda t: t.insert(0, new),
            "pop": lambda t: t.pop(0),
            "remove": lambda t: t.remove(t[0]),
            "clear": lambda t: t.clear(),
            "sort": lambda t: t.sort(key=lambda e: e["product"]),
            "reverse": lambda t: t.reverse(),
        }
        norm = "foo tool pro 2"
        for name, change in changes.items():
            table = AliasTable([entry("Foo Tool", "foo"),
                                entry("Foo Tool Pro", "bar"),
                                entry("Foo", "baz"), entry("Zed", "zed")])
            table.candidates(norm)
            before = list(table)
            change(table)
            self.assertNotEqual(list(table), before, name)
            self.assertIsNone(table._groups, name)
            self.assertEqual(_alias_hits(norm, table, ""),
                             _full_scan(norm, list(table), ""), name)

    def test_init_again_rebuilds_the_groups(self):
        table = AliasTable([{"key": "Foo", "product": "foo",
                             "match": "exact", "version_from": "name"}])
        self.assertEqual(len(table.candidates("foo")), 1)
        table.__init__([{"key": "Bar", "product": "bar", "match": "exact",
                         "version_from": "name"}])
        self.assertEqual(table.candidates("foo"), [])
        self.assertEqual([e["product"] for _k, e in table.candidates("bar")],
                         ["bar"])

    def test_copies_are_plain_lists(self):
        table = AliasTable([{"key": "Foo", "product": "foo",
                             "match": "exact", "version_from": "name"}])
        table.candidates("foo")
        for other in (copy.copy(table), copy.deepcopy(table),
                      pickle.loads(pickle.dumps(table))):
            self.assertIs(type(other), list)
            self.assertEqual(other, table)

    def test_malformed_entry_fails_the_same_way(self):
        good = {"key": "Foo", "product": "foo", "match": "exact",
                "version_from": "name"}
        bad = dict(good, match="fuzzy")
        errors = []
        for aliases in ([good, bad], AliasTable([good, bad])):
            with self.assertRaises(Exception) as ctx:
                _curated("Foo", "", aliases, {})
            errors.append((type(ctx.exception), str(ctx.exception)))
        self.assertEqual(errors[0], errors[1])
        self.assertIn("alias entry 2", errors[0][1])


if __name__ == "__main__":
    unittest.main()
