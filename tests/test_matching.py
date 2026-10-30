import csv
import json
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swlc.errors import DataError  # noqa: E402
from swlc.inputs import OPTIONAL, REQUIRED, map_columns  # noqa: E402
from swlc.matching import (  # noqa: E402
    AMBIGUOUS, NO_ALIAS, NO_CYCLE, NO_VERSION, MatchResult, match_product)
from swlc.normalize import normalize_name  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"


def cycles(*labels):
    return [{"cycle": c} for c in labels]


def alias(key, product, match="exact", version_from="version", **extra):
    entry = {"key": key, "match": match, "product": product,
             "version_from": version_from}
    entry.update(extra)
    return entry


SQL_PRODUCTS = {"mssqlserver": cycles("2014", "2016", "2019")}


class BriefCaseTests(unittest.TestCase):
    def test_build_map_maps_sql_build_to_cycle(self):
        a = [alias("Microsoft SQL Server", "mssqlserver",
                   build_map={"13.0": "2016"})]
        r = match_product("Microsoft SQL Server", "13.0.5026", a, SQL_PRODUCTS)
        self.assertIsInstance(r, MatchResult)
        self.assertEqual((r.product, r.cycle, r.reason),
                         ("mssqlserver", {"cycle": "2016"}, None))

    def test_sql_build_without_build_map_is_no_cycle(self):
        a = [alias("Microsoft SQL Server", "mssqlserver")]
        r = match_product("Microsoft SQL Server", "13.0.5026", a, SQL_PRODUCTS)
        self.assertEqual((r.product, r.cycle, r.reason),
                         ("mssqlserver", None, NO_CYCLE))

    def test_version_11_never_matches_cycle_1(self):
        a = [alias("Node.js", "nodejs")]
        r = match_product("Node.js", "11", a, {"nodejs": cycles("1")})
        self.assertEqual(r.reason, NO_CYCLE)
        self.assertIsNone(r.cycle)

    def test_empty_version_is_no_version(self):
        a = [alias("Node.js", "nodejs")]
        for v in ("", "   ", "v"):
            r = match_product("Node.js", v, a, {"nodejs": cycles("18")})
            self.assertEqual((r.product, r.cycle, r.reason),
                             ("nodejs", None, NO_VERSION), repr(v))

    def test_unknown_name_is_no_alias(self):
        a = [alias("Node.js", "nodejs")]
        r = match_product("Totally Unknown App", "1.0", a,
                          {"nodejs": cycles("1")})
        self.assertEqual((r.product, r.cycle, r.reason), (None, None, NO_ALIAS))

    def test_name_hitting_two_products_is_ambiguous(self):
        a = [alias("acme", "acme-one", match="prefix"),
             alias("acme server", "acme-two", match="prefix")]
        products = {"acme-one": cycles("1"), "acme-two": cycles("1")}
        r = match_product("Acme Server 1", "1", a, products)
        self.assertEqual((r.product, r.cycle, r.reason), (None, None, AMBIGUOUS))

    def test_office_16_fitting_several_cycles_is_ambiguous(self):
        a = [alias("Microsoft Office", "office",
                   build_map={"16.0": ["2016", "2019", "2021"]})]
        products = {"office": cycles("2016", "2019", "2021")}
        r = match_product("Microsoft Office", "16.0.4266.1001", a, products)
        self.assertEqual((r.product, r.cycle, r.reason),
                         ("office", None, AMBIGUOUS))

    def test_java_1_8_build_maps_to_8(self):
        a = [alias("Java SE", "oracle-jdk",
                   build_map={"1.8": "8", "8": "8"})]
        products = {"oracle-jdk": cycles("1.4", "7", "8", "11")}
        for v in ("1.8.0_391", "8.0.3910.13"):
            r = match_product("Java SE (64-bit)", v, a, products)
            self.assertEqual((r.product, r.cycle, r.reason),
                             ("oracle-jdk", {"cycle": "8"}, None), v)


class RuleTests(unittest.TestCase):
    def test_build_map_is_strict(self):
        # With a build map, a version outside it never falls back to direct
        # matching: 13.0.5026 must not land on the 13.0 (RTM) cycle.
        a = [alias("Microsoft SQL Server", "mssqlserver",
                   build_map={"15.0": "15.0"})]
        products = {"mssqlserver": cycles("13.0", "13.0-sp2", "15.0")}
        r = match_product("Microsoft SQL Server", "13.0.5026", a, products)
        self.assertEqual(r.reason, NO_CYCLE)
        r = match_product("Microsoft SQL Server", "15.0.4430.1", a, products)
        self.assertEqual(r.cycle, {"cycle": "15.0"})

    def test_build_map_target_must_exist_exactly(self):
        a = [alias("X", "x", build_map={"2": "2.1"})]
        r = match_product("X", "2.5", a, {"x": cycles("2")})
        self.assertEqual(r.reason, NO_CYCLE)

    def test_build_map_longest_key_wins(self):
        a = [alias("Windows Server", "windows-server", match="prefix",
                   version_from="name", edition_words=["standard"],
                   build_map={"2012": "2012", "2012 r2": "2012-r2"})]
        products = {"windows-server": cycles("2012", "2012-r2", "2016")}
        r = match_product("Windows Server 2012 R2 Standard", "", a, products)
        self.assertEqual(r.cycle, {"cycle": "2012-r2"})
        r = match_product("Windows Server 2012 Standard", "", a, products)
        self.assertEqual(r.cycle, {"cycle": "2012"})
        r = match_product("Windows Server 2008 R2 Standard", "", a, products)
        self.assertIsNone(r.cycle)
        self.assertIn(r.reason, (NO_CYCLE, NO_ALIAS))

    def test_three_ten_is_not_three_one(self):
        a = [alias("python", "python", match="prefix", version_from="name")]
        products = {"python": cycles("3.1", "3.10", "3.11")}
        self.assertEqual(
            match_product("Python 3.10.11 (64-bit)", "", a, products).cycle,
            {"cycle": "3.10"})
        self.assertEqual(
            match_product("Python 3.1.5", "", a, products).cycle,
            {"cycle": "3.1"})
        self.assertEqual(
            match_product("Python 3.12.0", "", a, products).reason, NO_CYCLE)

    def test_version_from_name_ignores_version_column(self):
        a = [alias("python", "python", match="prefix", version_from="name")]
        products = {"python": cycles("3.11")}
        # "launcher" is not a version, so it is a tail word the strict
        # prefix rule rejects: no product (it was python, NO_CYCLE, before
        # the gold benchmark showed it as a wrong product).
        r = match_product("Python Launcher", "3.11.4150.0", a, products)
        self.assertEqual((r.product, r.reason), (None, NO_ALIAS))
        r = match_product("Python", "3.11.4", a, products)
        self.assertEqual(r.reason, NO_VERSION)

    def test_prefix_needs_whole_word_boundary(self):
        a = [alias("python", "python", match="prefix", version_from="name")]
        products = {"python": cycles("3.11")}
        for name in ("Pythonista 3.11", "pythonnet 3.11", "CPython 3.11"):
            self.assertEqual(match_product(name, "", a, products).reason,
                             NO_ALIAS, name)

    def test_exact_needs_whole_name(self):
        a = [alias("Node.js", "nodejs")]
        r = match_product("Node.js Tools", "18.1", a, {"nodejs": cycles("18")})
        self.assertEqual(r.reason, NO_ALIAS)

    def test_prefix_tail_rule(self):
        a = [alias("acme server", "acme", match="prefix", version_from="name",
                   edition_words=["standard", "edition"],
                   build_map={"2019": "15.0"})]
        products = {"acme": cycles("15.0")}
        # empty tail
        self.assertEqual(
            match_product("Acme Server 2019 (64-bit)", "", a, products).cycle,
            {"cycle": "15.0"})
        # edition words, and a bare "-" left by a dropped token
        self.assertEqual(
            match_product("Acme Server 2019 Standard Edition - en-us", "", a,
                          products).cycle, {"cycle": "15.0"})
        # any other word is not a guess
        for name in ("Acme Server 2019 CLR Types", "Acme Server 2019 for Mac",
                     "Acme Server 2019 Standard Native Client",
                     "Acme Server Update Services"):
            self.assertEqual(
                match_product(name, "", a, products),
                MatchResult(None, None, NO_ALIAS), name)

    def test_prefix_tail_rule_version_column(self):
        a = [alias("acme os", "acme", match="prefix",
                   edition_words=["pro"], build_map={"10.0.19045": "22h2"})]
        products = {"acme": cycles("22h2")}
        self.assertEqual(
            match_product("Acme OS", "10.0.19045.1", a, products).cycle,
            {"cycle": "22h2"})
        self.assertEqual(
            match_product("Acme OS Pro", "10.0.19045.1", a, products).cycle,
            {"cycle": "22h2"})
        self.assertEqual(
            match_product("Acme OS SDK", "10.0.19045.1", a, products).reason,
            NO_ALIAS)

    def test_numbered_words_take_one_whole_number(self):
        # Issue #20: "Cumulative Update 23" after the year in an Exchange
        # name. The numbered word must be followed by one whole number.
        a = [alias("acme server", "acme", match="prefix", version_from="name",
                   edition_words=["cumulative", "update"],
                   numbered_words=["update"], build_map={"2019": "2019"})]
        products = {"acme": cycles("2019")}
        for name in ("Acme Server 2019 Cumulative Update 23",
                     "Acme Server 2019 Update 23",
                     "Acme Server 2019 Cumulative Update 1",
                     "Acme Server 2019 Cumulative Update 999"):
            self.assertEqual(match_product(name, "", a, products).cycle,
                             {"cycle": "2019"}, name)
        for name in ("Acme Server 2019 Cumulative 23",
                     "Acme Server 2019 Update",
                     "Acme Server 2019 Cumulative Update",
                     "Acme Server 2019 Cumulative Update 23 Language Pack",
                     "Acme Server 2019 23 Cumulative Update",
                     "Acme Server 2019 Cumulative Update 14 14",
                     "Acme Server 2019 Cumulative Update 14b",
                     "Acme Server 2019 Cumulative Update Update 14",
                     "Acme Server 2019 Cumulative Update 14 Update 2",
                     "Acme Server 2019 Cumulative Update \u0662\u0663",
                     "Acme Server 2019 Cumulative Update 014",
                     "Acme Server 2019 Cumulative Update 0",
                     "Acme Server 2019 Cumulative Update 1000",
                     "Acme Server 2019 Cumulative Update " + "9" * 4000):
            self.assertEqual(match_product(name, "", a, products),
                             MatchResult(None, None, NO_ALIAS), name)

    def test_numbered_words_are_part_of_the_rule(self):
        # Two same-key entries that differ only in numbered_words are two
        # rules for one name: the row is not decided.
        base = dict(match="prefix", version_from="name",
                    edition_words=["cumulative", "update"],
                    build_map={"2019": "2019"})
        a = [alias("acme server", "acme", numbered_words=["update"], **base),
             alias("acme server", "acme", numbered_words=["release"],
                   **base)]
        r = match_product("Acme Server 2019", "", a,
                          {"acme": cycles("2019")})
        self.assertEqual((r.product, r.cycle, r.reason),
                         ("acme", None, AMBIGUOUS))

    def test_numbered_words_are_off_without_the_field(self):
        a = [alias("acme server", "acme", match="prefix", version_from="name",
                   edition_words=["cumulative", "update"],
                   build_map={"2019": "2019"})]
        products = {"acme": cycles("2019")}
        self.assertEqual(
            match_product("Acme Server 2019 Cumulative Update 23", "", a,
                          products).reason, NO_ALIAS)

    def test_prefix_without_edition_words_needs_empty_tail(self):
        a = [alias("python", "python", match="prefix", version_from="name")]
        products = {"python": cycles("3.11")}
        self.assertEqual(
            match_product("Python 3.11.4 Core Interpreter", "", a,
                          products).reason, NO_ALIAS)

    def test_exact_alias_unchanged_by_tail_rule(self):
        a = [alias("node.js", "nodejs", edition_words=[])]
        self.assertEqual(
            match_product("Node.js", "18.1", a, {"nodejs": cycles("18")})
            .cycle, {"cycle": "18"})

    def test_alias_key_is_literal_not_pattern(self):
        a = [alias("a.c", "x", match="prefix", version_from="name"),
             alias("(ab)+", "y")]
        products = {"x": cycles("1"), "y": cycles("1")}
        self.assertEqual(match_product("abc 1", "", a, products).reason,
                         NO_ALIAS)
        self.assertEqual(match_product("abab", "1", a, products).reason,
                         NO_ALIAS)
        self.assertEqual(match_product("a.c 1", "", a, products).cycle,
                         {"cycle": "1"})

    def test_normalization_on_both_sides(self):
        a = [alias("  MICROSOFT   SQL Server (64-bit) ", "mssqlserver",
                   build_map={"13.0": "2016"})]
        r = match_product("microsoft sql server x64", "13.0.1", a,
                          SQL_PRODUCTS)
        self.assertEqual(r.cycle, {"cycle": "2016"})

    def test_fixed_cycle(self):
        a = [alias("Acme Suite 2019", "acme", version_from="name",
                   cycle="2019")]
        r = match_product("Acme Suite 2019", "16.0", a,
                          {"acme": cycles("2016", "2019")})
        self.assertEqual(r.cycle, {"cycle": "2019"})
        r = match_product("Acme Suite 2019", "", a, {"acme": cycles("2016")})
        self.assertEqual(r.reason, NO_CYCLE)

    def test_exact_beats_prefix_for_same_product(self):
        a = [alias("ubuntu", "ubuntu", match="prefix", version_from="name",
                   edition_words=["lts"]),
             alias("ubuntu", "ubuntu", match="exact", version_from="version")]
        products = {"ubuntu": cycles("20.04", "22.04")}
        r = match_product("Ubuntu", "22.04.3 LTS", a, products)
        self.assertEqual(r.cycle, {"cycle": "22.04"})
        # The name says 20.04, the version column 22.04: not decided.
        r = match_product("Ubuntu 20.04.6 LTS", "22.04", a, products)
        self.assertEqual((r.product, r.cycle, r.reason),
                         ("ubuntu", None, NO_CYCLE))
        r = match_product("Ubuntu 20.04.6 LTS", "20.04.6", a, products)
        self.assertEqual(r.cycle, {"cycle": "20.04"})

    def test_longest_key_wins_for_same_product(self):
        a = [alias("acme", "acme", match="prefix", version_from="name"),
             alias("acme pro", "acme", match="prefix", version_from="name",
                   edition_words=["x"])]
        r = match_product("Acme Pro 2 x", "", a, {"acme": cycles("2")})
        self.assertEqual(r.cycle, {"cycle": "2"})

    def test_same_key_different_rules_is_ambiguous(self):
        a = [alias("acme", "acme", version_from="name"),
             alias("acme", "acme", version_from="version")]
        r = match_product("Acme", "2", a, {"acme": cycles("2")})
        self.assertEqual((r.product, r.reason), ("acme", AMBIGUOUS))

    def test_duplicate_alias_entries_are_not_ambiguous(self):
        a = [alias("acme", "acme"), alias("ACME", "acme")]
        r = match_product("Acme", "2", a, {"acme": cycles("2")})
        self.assertEqual(r.cycle, {"cycle": "2"})

    def test_tied_cycles_with_same_parts_are_deduped(self):
        a = [alias("acme", "acme")]
        products = {"acme": [{"cycle": "13.0", "eol": "2020-01-01"},
                             {"cycle": "13_0", "eol": "2020-01-01"},
                             {"cycle": "13.0", "eol": "2020-01-01"}]}
        r = match_product("Acme", "13.0.5", a, products)
        self.assertIsNone(r.reason)
        self.assertEqual(r.cycle["cycle"], "13.0")

    def test_build_map_keys_with_same_parts_deduped(self):
        a = [alias("acme", "acme", build_map={"1.8": "8", "1_8": "8"})]
        r = match_product("Acme", "1.8.0", a, {"acme": cycles("8")})
        self.assertEqual(r.cycle, {"cycle": "8"})

    def test_build_map_keys_same_parts_different_targets_ambiguous(self):
        a = [alias("acme", "acme", build_map={"1.8": "8", "1_8": "9"})]
        r = match_product("Acme", "1.8.0", a, {"acme": cycles("8", "9")})
        self.assertEqual(r.reason, AMBIGUOUS)

    def test_product_missing_from_snapshot_is_no_cycle(self):
        a = [alias("acme", "acme")]
        r = match_product("Acme", "1", a, {})
        self.assertEqual((r.product, r.reason), ("acme", NO_CYCLE))

    def test_returned_cycle_is_the_snapshot_dict(self):
        cyc = {"cycle": "18", "eol": "2025-04-30", "support": "2023-10-18"}
        r = match_product("Node.js", "18.17.0", [alias("node.js", "nodejs")],
                          {"nodejs": [cyc]})
        self.assertIs(r.cycle, cyc)

    def test_bad_alias_entry_is_data_error(self):
        products = {"x": cycles("1")}
        for bad in (alias("x", "x", match="regex"),
                    alias("x", "x", version_from="both"),
                    {"key": "x", "match": "exact", "version_from": "version"},
                    alias("x", "x", build_map=["1"]),
                    alias("x", "x", build_map={"1": 2}),
                    alias("x", "x", edition_words="standard"),
                    alias("x", "x", edition_words=[""]),
                    alias("x", "x", numbered_words="update"),
                    alias("x", "x", numbered_words=[]),
                    alias("x", "x", numbered_words=[" "]),
                    alias("x", "x", numbered_words=[3])):
            with self.assertRaises(DataError, msg=repr(bad)):
                match_product("x", "1", [bad], products)

    def test_bad_kev_shape_is_data_error(self):
        products = {"x": cycles("1")}
        for kev in ("Microsoft", ["Microsoft", "Windows"], {},
                    {"vendor": "Microsoft"},
                    {"vendor": "Microsoft", "product": ""},
                    {"vendor": " ", "product": "Windows"},
                    {"vendor": "Microsoft", "product": 1},
                    {"vendor": "M", "product": "W", "extra": "x"}):
            with self.assertRaises(DataError, msg=repr(kev)):
                match_product("x", "1", [alias("x", "x", kev=kev)], products)

    def test_bad_note_is_data_error(self):
        products = {"x": cycles("1")}
        for note in ("", "  ", 1, None, ["why"], {"why": "x"}):
            with self.assertRaises(DataError, msg=repr(note)):
                match_product("x", "1", [alias("x", "x", note=note)],
                              products)

    def test_note_string_accepted(self):
        r = match_product("x", "1", [alias("x", "x", note="kept because")],
                          {"x": cycles("1")})
        self.assertIsNone(r.reason)

    def test_match_carries_alias_kev(self):
        products = {"x": cycles("1")}
        kev = {"vendor": "Microsoft", "product": "Windows"}
        r = match_product("x", "1", [alias("x", "x", kev=kev)], products)
        self.assertEqual(r.kev, kev)
        self.assertIsNone(match_product("x", "1", [alias("x", "x")],
                                        products).kev)
        self.assertIsNone(match_product("x", "9", [alias("x", "x", kev=kev)],
                                        products).kev)

    def test_publisher_guard_needs_a_whole_word_run(self):
        products = {"nodejs": cycles("18", "20")}
        a = [alias("Node.js", "nodejs",
                   publisher=["node.js foundation", "openjs foundation"])]
        for pub, want in (("Node.js Foundation", "18"),
                          ("OpenJS Foundation", "18"),
                          ("The OpenJS Foundation, Inc.", "18"),
                          ("CollabFS", None), ("", None),
                          ("OpenJSFoundation", None),
                          ("Foundation OpenJS", None)):
            with self.subTest(pub=pub):
                r = match_product("Node.js", "18.19.0", a, products,
                                  publisher=pub)
                self.assertEqual(r.cycle["cycle"] if r.cycle else None, want)
                self.assertEqual(r.product, "nodejs" if want else None)
                if not want:
                    self.assertEqual(r.reason, NO_ALIAS)

    def test_publisher_guard_failing_is_no_hit(self):
        # A guarded alias that does not apply leaves the row to other
        # aliases (and to title matching), as if it were absent.
        products = {"a": cycles("1"), "b": cycles("1")}
        aliases = [alias("x", "a", publisher=["acme"]), alias("x", "b")]
        self.assertEqual(match_product("x", "1", aliases, products,
                                       publisher="Other").product, "b")
        self.assertEqual(match_product("x", "1", aliases, products,
                                       publisher="Acme").reason, AMBIGUOUS)

    def test_bad_publisher_guard_is_data_error(self):
        products = {"x": cycles("1")}
        for pubs in ([], "acme", [1], [""], ["  "], ["..."], None, {"a": 1}):
            with self.assertRaises(DataError, msg=repr(pubs)):
                match_product("x", "1", [alias("x", "x", publisher=pubs)],
                              products, publisher="acme")

    def test_year_version_for_a_name_reading_alias_is_another_product(self):
        products = {"python": cycles("3.12", "3.11", "2.7")}
        a = [alias("python", "python", match="prefix", version_from="name")]
        r = match_product("Python", "2023.22.1", a, products,
                          publisher="Microsoft Corporation")
        self.assertEqual((r.product, r.cycle, r.reason),
                         (None, None, NO_ALIAS))
        # Not a year, or the name carries the version: unchanged.
        self.assertEqual(match_product("Python", "1.0.1", a, products).reason,
                         NO_VERSION)
        self.assertEqual(match_product("Python", "", a, products).reason,
                         NO_VERSION)
        self.assertEqual(match_product("Python 3.12.1", "2023.22.1", a,
                                       products).product, "python")
        # A product whose cycles are years keeps the year.
        years = {"office": cycles("2019", "2021")}
        o = [alias("office", "office", match="prefix", version_from="name")]
        self.assertEqual(match_product("Office", "2021.1", o, years).product,
                         "office")


def _hits(name, key, mode):
    n, k = normalize_name(name), normalize_name(key)
    if not k:
        return False
    if mode == "exact":
        return n == k
    return n == k or n.startswith(k + " ")


class PropertyTests(unittest.TestCase):
    BASE = [
        alias("python", "python", match="prefix", version_from="name"),
        alias("node.js", "nodejs"),
        alias("microsoft sql server", "mssqlserver",
              build_map={"15.0": "15.0", "16.0": "16.0"}),
        alias("ubuntu", "ubuntu", match="prefix", version_from="name",
              edition_words=["lts"]),
        alias("java se", "oracle-jdk", build_map={"1.8": "8", "8": "8"}),
    ]
    PRODUCTS = {
        "python": cycles("3.1", "3.10", "3.11", "2.7"),
        "nodejs": cycles("1", "11", "18", "20"),
        "mssqlserver": cycles("13.0", "15.0", "16.0"),
        "ubuntu": cycles("20.04", "22.04"),
        "oracle-jdk": cycles("8", "11"),
        "other": cycles("1", "8", "15.0", "22.04"),
    }
    ROWS = [
        ("Python 3.10.11 (64-bit)", ""), ("Python 2.7.18", ""),
        ("Node.js", "18.17.0"), ("Node.js", "v20.10.0"),
        ("Microsoft SQL Server", "15.0.4430.1"),
        ("Ubuntu 22.04.3 LTS", ""), ("Java SE", "1.8.0_391"),
    ]

    def _key_variants(self, rng, name):
        n = normalize_name(name)
        words = n.split(" ")
        cut = rng.randint(1, max(1, len(n) - 1))
        choices = [
            n[:cut],                                  # mid-word truncation
            n + rng.choice(["x", "s", " pro", "1"]),  # longer than the name
            " ".join(words[:-1]) + "x" if len(words) > 1 else n + "z",
            "".join(rng.choice("abcdefghijklmnop .-") for _ in
                    range(rng.randint(1, 12))),
            rng.choice(["c", "my ", "the "]) + n,
            n.replace(" ", "", 1),
        ]
        return rng.choice(choices)

    def test_unrelated_alias_never_changes_a_match(self):
        rng = random.Random(1234)
        products = sorted(self.PRODUCTS) + ["brand-new"]
        baseline = {row: match_product(row[0], row[1], self.BASE,
                                       self.PRODUCTS) for row in self.ROWS}
        for row, res in baseline.items():
            self.assertIsNone(res.reason, row)
        checked = 0
        for _ in range(200):
            row = rng.choice(self.ROWS)
            key = self._key_variants(rng, row[0])
            mode = rng.choice(["exact", "prefix"])
            if _hits(row[0], key, mode):
                continue
            extra = alias(key, rng.choice(products), match=mode,
                          version_from=rng.choice(["name", "version"]))
            if rng.random() < 0.5:
                extra["build_map"] = {"1": "1"}
            aliases = list(self.BASE)
            aliases.insert(rng.randint(0, len(aliases)), extra)
            got = match_product(row[0], row[1], aliases, self.PRODUCTS)
            self.assertEqual(got, baseline[row], (row, extra))
            checked += 1
        self.assertGreaterEqual(checked, 150)


def _load(name):
    path = DATA / name
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    return text, doc


def _canonical(doc):
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# Cycle labels only (no dates), as published by endoflife.date on
# 2026-10-24 for the products the alias table names. Used to check that every
# alias target exists and to run the labelled corpus. Task 5 replaces this
# with the shipped snapshot.
EOL_CYCLE_LABELS = {
    "mssqlserver": ["17.0", "16.0", "13.0-sp3-acp", "13.0-sp3", "15.0",
                    "12.0-sp3", "13.0-sp2", "11.0-sp4", "14.0", "13.0-sp1",
                    "12.0-sp2", "13.0", "11.0-sp3", "12.0-sp1", "10.50-sp3",
                    "10.0-sp4", "11.0-sp2", "12.0", "11.0-sp1", "10.50-sp2",
                    "11.0", "10.00-sp3", "10.50-sp1", "9.0-sp4",
                    "10.00-sp2", "10.50-r2", "10.00-sp1", "9.00-sp3",
                    "10.00", "9.00-sp2", "9.0-sp1", "9.0", "8.0-sp4",
                    "7.0-sp4", "6.50-sp5a", "6.0-sp3"],
    "windows-server": ["2025", "23h2-ac", "2022", "20h2-sac", "2004-sac",
                       "1909-sac", "1903-sac", "1809-sac", "2019",
                       "1803-sac", "1709-sac", "2016", "2012-r2", "2012",
                       "2008-r2-sp1", "2008-sp2", "2003-sp2", "2003-sp1",
                       "2003", "2000"],
    "windows": ["11-26h2-e", "11-26h2-w", "11-26h1-e", "11-26h1-w",
                "11-25h2-e", "11-25h2-w", "11-24h2-iot-lts", "11-24h2-e-lts",
                "11-24h2-e", "11-24h2-w", "11-23h2-e", "11-23h2-w",
                "10-22h2", "11-22h2-e", "11-22h2-w", "10-21h2-iot-lts",
                "10-21h2-e-lts", "10-21h2-e", "10-21h2-w", "11-21h2-e",
                "11-21h2-w", "10-21h1", "10-20h2-e", "10-20h2-w", "10-2004",
                "10-1909-e", "10-1909-w", "10-1903", "10-1809-e-lts",
                "10-1809-e", "10-1809-w", "10-1803-e", "10-1803-w",
                "10-1709-e", "10-1709-w", "10-1703-e", "10-1703-w",
                "10-1607-e-lts", "10-1607-e", "10-1607-w", "10-1511",
                "10-1507-e-lts", "10-1507", "10-1507-iot", "8.1", "8",
                "7-sp1", "6-sp2", "5-sp3"],
    "office": ["2024", "2024-ltsc", "2021", "2019", "2016", "2013",
               "2011-for-mac", "2010", "2008-for-mac", "2007"],
    "python": ["3.15", "3.14", "3.13", "3.12", "3.11", "3.10", "3.9", "3.8",
               "3.7", "3.6", "3.5", "3.4", "3.3", "3.2", "2.7", "3.1", "3.0",
               "2.6"],
    "nodejs": [str(n) for n in range(26, 0, -1)],
    "ubuntu": ["26.10", "26.04", "25.10", "25.04", "24.10", "24.04", "23.10",
               "23.04", "22.10", "22.04", "21.10", "21.04", "20.10", "20.04",
               "19.10", "19.04", "18.10", "18.04", "17.10", "17.04", "16.10",
               "16.04", "15.10", "15.04", "14.10", "14.04", "13.10", "13.04",
               "12.10", "12.04", "11.10", "11.04", "10.10", "10.04", "9.10",
               "9.04", "8.10", "8.04", "7.10", "7.04", "6.10", "6.06",
               "5.10", "5.04", "4.10"],
    "oracle-jdk": ["27", "26", "25", "24", "23", "22", "21", "20", "19", "18",
                   "17", "16", "15", "14", "13", "12", "11", "10", "9", "8",
                   "7", "6", "5", "1.4", "1.3", "1.2", "1.1", "1.0"],
    "eclipse-temurin": ["27", "26", "25", "24", "23", "22", "21", "20", "19",
                        "18", "17", "11", "16", "8"],
    "windows-powershell": ["5.1", "5.0", "4.0", "3.0", "2.0", "1.0"],
    "mysql": ["26.7", "9.7", "9.6", "9.5", "9.4", "9.3", "9.2", "9.1", "9.0",
              "8.4", "8.3", "8.2", "8.1", "8.0", "5.7", "5.6", "5.5"],
    "bellsoft-liberica": ["27", "26", "25", "24", "23", "22", "21", "20",
                          "19", "18", "17", "16", "15", "14", "13", "12",
                          "11", "10", "8", "7", "6"],
    "msexchange": ["subscription", "2019", "2016", "2013", "2010", "2007",
                   "2003", "2000", "5.5", "5.0", "4.0"],
    "sharepoint": ["subscription", "2019", "2016", "2013", "2010", "2007"],
    "visual-studio": ["18.%d" % n for n in range(11, -1, -1)]
    + ["17.%d" % n for n in range(14, -1, -1)]
    + ["16.%d" % n for n in range(11, -1, -1)]
    + ["15.%d" % n for n in range(9, -1, -1)]
    + ["14.0", "12.0", "11.0", "10.0"],
    "dotnet": ["10", "9", "8", "7", "6", "5", "3.1", "3.0", "2.2", "2.1",
               "2.0", "1.1", "1.0"],
    "dotnetfx": ["4.8.1", "4.8", "4.7.2", "4.7.1", "4.7", "4.6.2", "4.6.1",
                 "4.6", "4.5.2", "4.5.1", "4.5", "4.0", "3.5-sp1"],
    "debian": ["13", "12", "11", "10", "9", "8", "7", "6", "5", "4", "3.1",
               "3.0", "2.2", "2.1", "2.0", "1.3", "1.2", "1.1"],
    "macos": ["27", "26", "15", "14", "13", "12", "11", "10.15", "10.14",
              "10.13", "10.12", "10.11", "10.10", "10.9", "10.8", "10.7",
              "10.6", "10.5", "10.4", "10.3", "10.2", "10.1", "10.0"],
    "powershell": ["7.6", "7.5", "7.4", "7.3", "7.2", "7.1", "7.0", "6.2",
                   "6.1", "6.0"],
    "rhel": ["10", "9", "8", "7", "6", "5", "4"],
    "rocky-linux": ["10", "9", "8"],
    "almalinux": ["10", "9", "8"],
    "oracle-linux": ["10", "9", "8", "7", "6"],
    "sles": ["16.0", "15.7", "15.6", "15.5", "15.4", "15.3", "15.2", "12.5",
             "15.1", "12.4", "15.0", "12.3", "12.2", "12.1", "11.4", "12.0",
             "11.3", "11.2", "10.4", "11.1", "10.3", "11.0", "10.2", "10.1",
             "10.0"],
}
EOL_PRODUCTS = {p: cycles(*labels) for p, labels in EOL_CYCLE_LABELS.items()}


# Corpus rows whose true cycle the shipped table cannot reach under the
# strict prefix rule (an update number or "8u" build in the name).
KNOWN_MISSES = [
    ("Eclipse Temurin JDK with Hotspot 8u392-b08 (x64)", "8.0.392.8",
     NO_CYCLE),
    ("Java 8 Update 391", "1.8.0_391", NO_ALIAS),
]


class AliasFileTests(unittest.TestCase):
    def setUp(self):
        self.text, self.doc = _load("aliases.json")

    def test_canonical_json(self):
        self.assertEqual(self.text, _canonical(self.doc))

    def test_schema(self):
        self.assertEqual(self.doc["format"], 1)
        entries = self.doc["aliases"]
        self.assertGreaterEqual(len(entries), 12)
        allowed = {"key", "match", "product", "version_from", "cycle",
                   "build_map", "column_map", "source", "edition_words",
                   "numbered_words", "kev", "note", "publisher"}
        for e in entries:
            self.assertLessEqual(set(e), allowed, e)
            self.assertIn(e["match"], ("exact", "prefix"))
            self.assertIn(e["version_from"], ("name", "version"))
            self.assertEqual(e["key"], normalize_name(e["key"]), e)
            self.assertTrue(e["source"].startswith("https://"), e)
            self.assertIn(e["product"], EOL_CYCLE_LABELS, e)
            for p in e.get("publisher", []):
                self.assertEqual(p, normalize_name(p), e)
            for w in e.get("edition_words", []):
                self.assertEqual(w, normalize_name(w), e)
                self.assertEqual(len(w.split()), 1, e)
            for w in e.get("numbered_words", []):
                self.assertEqual(w, normalize_name(w), e)
                self.assertEqual(len(w.split()), 1, e)

    def test_broad_windows_kev_pair_has_note(self):
        for e in self.doc["aliases"]:
            if e.get("kev") == {"vendor": "Microsoft", "product": "Windows"} \
                    and e["product"] == "windows-server":
                self.assertIn("note", e, e["key"])
                self.assertLessEqual(len(e["note"]), 200)

    def test_targets_exist_in_endoflife_cycles(self):
        for e in self.doc["aliases"]:
            labels = EOL_CYCLE_LABELS[e["product"]]
            targets = []
            if "cycle" in e:
                targets.append(e["cycle"])
            for field in ("build_map", "column_map"):
                for v in e.get(field, {}).values():
                    targets.extend(v if isinstance(v, list) else [v])
            for t in targets:
                self.assertIn(t, labels, e)

    def test_column_map_only_on_name_reading_build_map_aliases(self):
        for e in self.doc["aliases"]:
            if "column_map" in e:
                self.assertEqual(e["version_from"], "name", e["key"])
                self.assertIn("build_map", e, e["key"])

    def test_no_name_hits_two_products(self):
        # Every key, used as a product name, must hit only one product.
        entries = self.doc["aliases"]
        for e in entries:
            prods = {o["product"] for o in entries
                     if _hits(e["key"], o["key"], o["match"])}
            self.assertEqual(prods, {e["product"]}, e["key"])


class CorpusTests(unittest.TestCase):
    def test_corpus_has_zero_false_matches(self):
        _, doc = _load("aliases.json")
        with open(HERE / "corpus_versions.csv", newline="",
                  encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 40)
        false_matches, missed, hits = [], [], 0
        for row in rows:
            r = match_product(row["name"], row["version"], doc["aliases"],
                              EOL_PRODUCTS, publisher=row["publisher"])
            got = r.cycle["cycle"] if r.cycle else "NONE"
            want = row["expected_cycle"]
            self.assertTrue(row["source"].startswith("https://"), row)
            if want == "NONE":
                if got != "NONE":
                    false_matches.append((row["name"], row["version"], got))
                continue
            if got == "NONE":
                missed.append((row["name"], row["version"], r.reason))
            elif got != want or r.product != row["expected_product"]:
                false_matches.append((row["name"], row["version"], got))
            else:
                hits += 1
        self.assertEqual(false_matches, [])
        # Missed matches only count toward coverage. The known list keeps
        # any coverage change visible in review.
        self.assertEqual(sorted(missed), sorted(KNOWN_MISSES))
        self.assertGreater(hits, 0)


class ProfileFileTests(unittest.TestCase):
    def setUp(self):
        self.text, self.doc = _load("profiles.json")

    def test_canonical_json(self):
        self.assertEqual(self.text, _canonical(self.doc))

    def test_schema(self):
        self.assertEqual(self.doc["format"], 1)
        self.assertIs(self.doc["unverified"], True)
        profiles = self.doc["profiles"]
        self.assertEqual(set(profiles), {"flexera", "servicenow-mbs",
                                         "rapid7"})
        canon = set(REQUIRED) | set(OPTIONAL)
        for name, prof in profiles.items():
            self.assertEqual(prof["status"], "Unverified", name)
            self.assertTrue(prof["source"], name)
            for src in prof["source"]:
                self.assertTrue(src.startswith("https://"), name)
            self.assertLessEqual(set(prof["columns"]), canon, name)
            for aliases in prof["columns"].values():
                self.assertIsInstance(aliases, list)
                self.assertTrue(all(isinstance(a, str) and a
                                    for a in aliases))

    def test_each_alias_maps_to_one_field(self):
        for name, prof in self.doc["profiles"].items():
            cols = prof["columns"]
            for canon, aliases in cols.items():
                for a in aliases:
                    fill = [h for h in ("name", "version") if h != canon]
                    headers = [a] + fill
                    got = map_columns(headers, cols, None)
                    self.assertEqual(got[canon], a, (name, a))

    def test_profile_maps_its_own_full_header_set(self):
        for name, prof in self.doc["profiles"].items():
            headers = [aliases[0] for aliases in prof["columns"].values()]
            got = map_columns(headers, prof["columns"], None)
            self.assertEqual(set(got), set(prof["columns"]), name)

    def test_flexera_report_with_extended_support_column(self):
        # Flexera's installations report carries both "End of support" and
        # "End of extended support"; the second must not collide.
        cols = self.doc["profiles"]["flexera"]["columns"]
        headers = ["Application name", "Version", "Publisher", "Installed",
                   "End of life", "End of support", "End of extended support"]
        got = map_columns(headers, cols, None)
        self.assertEqual(got["export_support"], "End of support")
        self.assertEqual(got["count"], "Installed")

    def test_removing_a_profile_keeps_the_rest_loadable(self):
        doc = json.loads(self.text)
        del doc["profiles"]["rapid7"]
        reloaded = json.loads(_canonical(doc))
        self.assertEqual(set(reloaded["profiles"]),
                         {"flexera", "servicenow-mbs"})
        for prof in reloaded["profiles"].values():
            headers = [aliases[0] for aliases in prof["columns"].values()]
            map_columns(headers, prof["columns"], None)


if __name__ == "__main__":
    unittest.main()
