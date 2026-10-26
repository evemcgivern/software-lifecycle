"""Rows the matcher refused on purpose (issue #12): the review codes from
swlc/catalog_match.py ("Refusals for review") and swlc/matching.py
(match_noted).

The fixtures are the fictional products of tests/test_catalog_match.py.
Matching results never change: match_noted always returns the MatchResult
match_product gives.
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swlc.catalog_match import (  # noqa: E402
    TITLE_NEEDS_PUBLISHER, TITLE_NOT_ON_LIST, build_index)
from swlc.matching import match_noted, match_product  # noqa: E402
from test_catalog_match import (  # noqa: E402
    CATALOG, CURATION, INDEX, MAX_SECONDS_100K, PRODUCTS, alias,
    synthetic_rows)

ROOT = Path(__file__).resolve().parents[1]
# plainword and sunny are on the version-in-name list here; lexicon is not.
LISTED = build_index(CATALOG, CURATION, version_names=(
    "plainword", "chatter", "gizmo", "foo-tool", "sunny"))


def noted(name, version="", publisher="", index=LISTED, aliases=()):
    """The review code, after checking the match result is unchanged."""
    result, code = match_noted(name, version, list(aliases), PRODUCTS,
                               catalog_index=index, publisher=publisher)
    plain = match_product(name, version, list(aliases), PRODUCTS,
                          catalog_index=index, publisher=publisher)
    assert result == plain, (name, result, plain)
    return code


class TitleNeedsPublisherTests(unittest.TestCase):
    def test_one_word_title_with_no_publisher(self):
        for name, version in (("Plainword", "1"), ("Plainword", ""),
                              ("PLAINWORD (x64)", "1"), ("Lexicon", "1.0"),
                              ("BIND", "9.18.1")):
            with self.subTest(name=name):
                self.assertEqual(noted(name, version), TITLE_NEEDS_PUBLISHER)

    def test_publisher_that_does_not_confirm(self):
        self.assertEqual(noted("Lexicon", "1.0", "Acme Corp"),
                         TITLE_NEEDS_PUBLISHER)
        # "Promo Group" is not exactly the one-word title vendor "promo".
        self.assertEqual(noted("Promo", "3.5", "Promo Group"),
                         TITLE_NEEDS_PUBLISHER)

    def test_matched_rows_have_no_code(self):
        for name, version, pub in (("Listed", "4", ""),
                                   ("Sunny", "1.0", "Sun Microsystems"),
                                   ("Foo Tool", "2.1", ""),
                                   ("Lexicon", "1.0", "Lexicon")):
            with self.subTest(name=name):
                self.assertIsNone(noted(name, version, pub))

    def test_exclusion_device_and_generated_off_have_no_code(self):
        # Chatter is named by an exclusion: no code with or without the
        # excluded publisher.
        self.assertIsNone(noted("Chatter", "9.3", "Chatter Inc."))
        self.assertIsNone(noted("Chatter", "9.3"))
        self.assertIsNone(noted("Gizmo Phone", "8"))       # generated_off
        self.assertIsNone(noted("Tabby Tablet", "8"))      # device
        # A two-word title with an exclusion on a longer form.
        self.assertIsNone(noted("Foo Tool Helper (x64)", "2.1"))

    def test_curated_decisions_have_no_code(self):
        # An alias that hits decides the row.
        self.assertIsNone(noted("Plainword", "9", aliases=[
            alias("plainword", "plainword")]))
        # An alias whose publisher guard failed blocks its product.
        self.assertIsNone(noted("Plainword", "1", aliases=[
            alias("plainword", "plainword", publisher=["Plain Co"])]))

    def test_names_with_no_title_hit_have_no_code(self):
        for name in ("Nothing", "Plainword Helper", "Synthetic App 00001"):
            with self.subTest(name=name):
                self.assertIsNone(noted(name, "1"))

    def test_without_a_catalog_there_is_no_code(self):
        self.assertIsNone(noted("Plainword", "1", index=None))


class TitleNotOnListTests(unittest.TestCase):
    def test_unlisted_title_and_version_with_no_publisher(self):
        self.assertEqual(noted("Lexicon 1.0"), TITLE_NOT_ON_LIST)
        self.assertEqual(noted("Lexicon 1.0", "1.0"), TITLE_NOT_ON_LIST)
        self.assertEqual(noted("Lexicon 1.0 (x64)"), TITLE_NOT_ON_LIST)
        # With an empty list every one-word title is unlisted.
        self.assertEqual(noted("Plainword 1.2", index=INDEX),
                         TITLE_NOT_ON_LIST)

    def test_version_or_cycle_mismatch_has_no_code(self):
        self.assertIsNone(noted("Lexicon 9.9"))            # no such cycle
        self.assertIsNone(noted("Lexicon 1.0", "9.9"))     # column disagrees
        self.assertIsNone(noted("Plainword 9.9"))          # listed, no cycle

    def test_listed_title_matches_and_has_no_code(self):
        self.assertIsNone(noted("Plainword 1.2"))
        r, _code = match_noted("Plainword 1.2", "", [], PRODUCTS,
                               catalog_index=LISTED)
        self.assertEqual(r.product, "plainword")

    def test_a_publisher_means_no_code(self):
        self.assertIsNone(noted("Lexicon 1.0", "1.0", "Acme Corp"))

    def test_exclusion_and_other_words_have_no_code(self):
        index = build_index(CATALOG, CURATION, version_names=())
        self.assertIsNone(noted("Chatter 9.3", index=index))
        self.assertIsNone(noted("Chatter 9.3.0", "9.3.0", index=index))
        for name in ("Lexicon Pro 1.0", "Lexicon 1.0 Pro", "Lexicon 1.0-beta",
                     "Gizmo 8"):
            with self.subTest(name=name):
                self.assertIsNone(noted(name))

    def test_confirming_publisher_matches_with_no_code(self):
        # Step c drops a confirming vendor word, and the row matches.
        self.assertIsNone(noted("Lexicon Lexicon 1.0", "", "Lexicon"))


class LookupNotedTests(unittest.TestCase):
    def test_first_two_values_equal_lookup(self):
        fits = (lambda p, t: True)
        for name, pub in (("Plainword", ""), ("Lexicon 1.0", ""),
                          ("Chatter", "Chatter Inc."), ("Foo Tool 2.1", ""),
                          ("Nothing", ""), ("x " * 70, "")):
            for f in (None, fits):
                with self.subTest(name=name, fits=f):
                    full = LISTED.lookup_noted(name, pub, f)
                    self.assertEqual(full[:2], LISTED.lookup(name, pub, f))

    def test_code_names_the_refused_products(self):
        self.assertEqual(LISTED.lookup_noted("Plainword"),
                         ((), {}, (TITLE_NEEDS_PUBLISHER, ("plainword",))))
        self.assertEqual(
            LISTED.lookup_noted("Lexicon 1.0", "", lambda p, t: True),
            ((), {}, (TITLE_NOT_ON_LIST, ("lexicon",))))


class NotedSpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        from datetime import date
        from swlc.data import load_data
        manifest = json.loads((ROOT / "data" / "manifest.json").read_text(
            encoding="utf-8"))
        cls.data = load_data(str(ROOT / "data"),
                             date.fromisoformat(manifest["eol_date"]))

    def test_100000_rows_within_the_bound(self):
        data = self.data
        index = data.matching_index()
        start = time.perf_counter()
        n = 0
        for name, ver, pub in synthetic_rows(data.catalog, 100000):
            match_noted(name, ver, data.aliases, data.products,
                        catalog_index=index, publisher=pub)
            n += 1
        elapsed = time.perf_counter() - start
        self.assertEqual(n, 100000)
        self.assertLess(elapsed, MAX_SECONDS_100K,
                        "100,000 rows took %.1f s" % elapsed)

    def test_same_result_as_match_product_on_synthetic_rows(self):
        data = self.data
        index = data.matching_index()
        for name, ver, pub in synthetic_rows(data.catalog, 5000, seed=7):
            self.assertEqual(
                match_noted(name, ver, data.aliases, data.products,
                            catalog_index=index, publisher=pub)[0],
                match_product(name, ver, data.aliases, data.products,
                              catalog_index=index, publisher=pub), name)


if __name__ == "__main__":
    unittest.main()
