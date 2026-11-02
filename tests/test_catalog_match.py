"""Generated matching (rule C): swlc/catalog_match.py and its use in
swlc/matching.py and swlc/assess.py.

Every product here is a fictional fixture written for these tests, in the
products.json and curation.json shapes. Nothing comes from data/.
"""
import copy
import random
import sys
import time
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import make_data_dir  # noqa: E402
from swlc.assess import assess  # noqa: E402
from swlc.catalog_match import (  # noqa: E402
    SHARED_SUPPORT_LINES, build_index, split_tail, strip_arch, tokens)
from swlc.data import Data, load_data  # noqa: E402
from swlc.inputs import group_rows  # noqa: E402
from swlc.matching import (  # noqa: E402
    AMBIGUOUS, CURATED, GENERATED, NO_ALIAS, NO_CYCLE, NO_VERSION,
    MatchResult, match_noted, match_product)
from swlc.normalize import normalize_name  # noqa: E402
from swlc.overrides import Exceptions, Golden  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def rec(pid, title, vendors=(), namespaces=(), category="app"):
    return {"id": pid, "title": title, "category": category,
            "vendors": sorted(vendors), "namespaces": sorted(namespaces)}


CATALOG = {r["id"]: r for r in (
    rec("bind", "BIND", vendors=["isc"]),
    rec("bind-9", "BIND 9", vendors=["isc"]),
    rec("firefox", "Firefox", vendors=["mozilla"]),
    rec("foo-tool", "Foo Tool"),
    rec("webserver", "Webserver", vendors=["apache"]),
    rec("idserver", "Idserver", vendors=["red_hat"]),
    rec("scanner", "Scanner", vendors=["clam_anti-virus"]),
    rec("sunny", "Sunny", vendors=["sun"]),
    rec("catalina", "Catalina", namespaces=["org.apache.tomcat"]),
    rec("vaulty", "Vaulty", namespaces=["hashicorp"]),
    rec("jsrun", "Jsrun", vendors=["jsrun"]),
    rec("plainword", "Plainword"),
    rec("listed", "Listed"),
    rec("gizmo", "Gizmo Phone", category="device"),
    rec("chatter", "Chatter", vendors=["chatter"]),
    rec("alpha-beta", "Alpha Beta"),
    rec("beta-2", "Beta 2", vendors=["alpha"]),
    rec("gadget-suite", "Gadget Suite"),
    rec("widget-pro", "Widget Pro"),
    rec("dbms", "Northwind DBMS"),
    rec("tabby", "Tabby Tablet", category="device"),
    rec("promo", "Promo", vendors=["promo"]),
    rec("frame-work", "Frame Work"),
    rec("weekly", "Weekly Builder"),
    rec("lexicon", "Lexicon", vendors=["lexicon"]),
)}
CURATION = {
    "format": 1,
    "publisher_aliases": {"jsrun": {
        "phrases": ["openjs foundation"], "reason": "the project's steward",
        "source": "https://example.com/jsrun"}},
    "single_word_allowlist": [
        {"product": "listed", "reason": "unambiguous in exports",
         "source": "https://example.com/listed",
         "gold": "Listed|x|1"}],
    "exclusions": [
        {"product": "chatter", "name": "chatter", "publisher": "chatter",
         "reason": "desktop client with the server's name",
         "gold": "Chatter|Chatter Inc.|5.6.0"},
        {"product": "foo-tool", "name": "foo tool helper (x64)",
         "publisher": "", "reason": "helper, not the product",
         "gold": "Foo Tool Helper|x|1"}],
    "generated_off": ["gizmo"],
}
CYCLES = {
    "bind": ["9", "8"], "bind-9": ["9.18", "9.20"], "firefox": ["115", "128"],
    "foo-tool": ["2.1", "2.2", "3.0"], "webserver": ["2.4"],
    "idserver": ["23.0"], "scanner": ["1.0"], "sunny": ["1"],
    "catalina": ["9.0"], "vaulty": ["1.17"], "jsrun": ["20"],
    "plainword": ["1"], "listed": ["4"], "gizmo": ["8"], "chatter": ["9.3"],
    "alpha-beta": ["2"], "beta-2": ["2"], "gadget-suite": ["1"],
    "widget-pro": ["1"], "dbms": ["7"], "tabby": ["8"], "promo": ["3.5"],
    "frame-work": ["4.6", "4.6.1", "4.6.2", "4.8", "4.8.1"],
    "weekly": ["2", "2.426", "2.440"], "lexicon": ["1"],
}
PRODUCTS = {p: [{"cycle": c} for c in labels] for p, labels in CYCLES.items()}
# The version-in-name rule is off here (no ids); VersionInNameTests turns
# it on for fixture products.
INDEX = build_index(CATALOG, CURATION, version_names=())


def gen(name, version="", publisher="", aliases=()):
    return match_product(name, version, list(aliases), PRODUCTS,
                         catalog_index=INDEX, publisher=publisher)


def got(r):
    return (r.product, r.cycle["cycle"] if r.cycle else None, r.reason,
            r.source)


def alias(key, product, match="exact", version_from="version", **extra):
    entry = {"key": key, "match": match, "product": product,
             "version_from": version_from}
    entry.update(extra)
    return entry


class CandidateOrderTests(unittest.TestCase):
    def test_a_whole_name_equals_a_title(self):
        self.assertEqual(got(gen("Foo Tool", "2.1.4")),
                         ("foo-tool", "2.1", None, GENERATED))
        self.assertEqual(got(gen("FOO  tool", "3.0")),
                         ("foo-tool", "3.0", None, GENERATED))

    def test_a_whole_title_wins_over_a_split(self):
        # "BIND 9" is a whole title; "bind" + tail 9 would be another one.
        self.assertEqual(got(gen("BIND 9", "9.18.28", "ISC")),
                         ("bind-9", "9.18", None, GENERATED))

    def test_b_architecture_and_locale_groups(self):
        for name in ("Foo Tool (x64)", "Foo Tool (x86)", "Foo Tool (64-bit)",
                     "Foo Tool (32-bit)", "Foo Tool x64", "Foo Tool (en-US)",
                     "Foo Tool (x64 en-US)", "Foo Tool [x64]",
                     "Foo Tool (arm64)", "Foo Tool (aarch64)",
                     "Foo Tool amd64", "Foo Tool (de-DE)", "Foo Tool en_us",
                     "Foo Tool (x64, en-US)"):
            with self.subTest(name=name):
                self.assertEqual(got(gen(name, "2.2.0")),
                                 ("foo-tool", "2.2", None, GENERATED))

    def test_b_keeps_other_groups_and_inner_words(self):
        for name in ("Foo Tool (Beta)", "Foo Tool (x64 Beta)",
                     "Foo amd64 Tool", "Foo Tool Helper"):
            with self.subTest(name=name):
                self.assertEqual(got(gen(name, "2.2.0")),
                                 (None, None, NO_ALIAS, None))

    def test_strip_arch_and_split_tail_helpers(self):
        self.assertEqual(strip_arch("foo (x64 en-us)"), "foo")
        self.assertEqual(strip_arch("foo [x86] bar"), "foo bar")
        self.assertEqual(strip_arch("x64"), "x64")
        self.assertEqual(split_tail("foo 2.1"), ("foo", "2.1"))
        self.assertEqual(split_tail("foo v2"), ("foo", "v2"))
        self.assertEqual(split_tail("foo 2.1a"), ("foo", "2.1a"))
        self.assertIsNone(split_tail("foo 8u392"))
        self.assertIsNone(split_tail("foo 2.1-beta"))
        self.assertIsNone(split_tail("2.1"))

    def test_split_tail_wider_version_shapes(self):
        # Build, distro and hotfix suffixes after ".", "-" or "+", and a
        # glued "patchN", stay part of the version token.
        for tail in ("9.3.30.v20211001", "1.27-eks-53", "7.7.2-hf",
                     "2018.3.2patch20", "17.0.20.0.21+8", "20.0.2+9",
                     "1.26.15-gke.1469001", "3.62.0-01", "11.0.25.0.9-3"):
            with self.subTest(tail=tail):
                self.assertEqual(split_tail("foo " + tail), ("foo", tail))
        # A pre-release suffix stops the token: the name is not split.
        for tail in ("2.1-beta", "2.1-beta2", "2.0-rc1", "2.0.rc", "1.0-dev",
                     "1.0-devel", "3.1-alpha", "4.0-preview",
                     "1.2+snapshot", "5.0-nightly", "6.0-canary", "1.0-pre"):
            with self.subTest(tail=tail):
                self.assertIsNone(split_tail("foo " + tail))
        # Milestone and candidate markers, glued or not.
        for tail in ("11.0.0-m1", "2.1.0.m2", "3.0.0.cr1", "3.0.0-cr",
                     "8.0-milestone-1", "17.0.1-ea", "1.0-b1", "1.0rc1",
                     "1.0-alpha1", "2.0.0.rc2"):
            with self.subTest(tail=tail):
                self.assertIsNone(split_tail("foo " + tail))
        # A word after "-" or "." that is not a named build tag ends the
        # token: a component or edition word is never read as a build.
        for tail in ("8.0-router", "10.4.1-agent", "1.24.0-plus",
                     "8.15-plugin", "128.0.3-esr", "2.0-release",
                     "1.2-server", "3.1.0.final"):
            with self.subTest(tail=tail):
                self.assertIsNone(split_tail("foo " + tail))
        # Digit-led distro parts and the named tags still split.
        # Architecture names are not installer build tags.
        for tail in ("1.0-i686", "1.0-i386", "2.4.1.i586", "1.0-i486"):
            with self.subTest(tail=tail):
                self.assertIsNone(split_tail("foo " + tail))
        for tail in ("4.0r9", "2.6.8-i001", "2.5.9-i601",
                     "20.10.0-1nodesource1", "3.1-1ubuntu1"):
            with self.subTest(tail=tail):
                self.assertEqual(split_tail("foo " + tail), ("foo", tail))
        for word in ("8u392", "v", "patch20", "2.1-", "+8", "2.1_3"):
            with self.subTest(word=word):
                self.assertIsNone(split_tail("foo " + word))

    def test_d_wider_version_token_matches_an_exact_title(self):
        self.assertEqual(got(gen("Foo Tool 2.1.4-hf")),
                         ("foo-tool", "2.1", None, GENERATED))
        self.assertEqual(got(gen("Foo Tool 3.0.2+8", "3.0.2+8")),
                         ("foo-tool", "3.0", None, GENERATED))
        self.assertEqual(got(gen("Foo Tool 2.2.0.v20211001")),
                         ("foo-tool", "2.2", None, GENERATED))
        # The head must still equal a title exactly.
        self.assertEqual(got(gen("Foo Tools 2.1.4-hf")),
                         (None, None, NO_ALIAS, None))
        self.assertEqual(got(gen("Foo Tool 2.1-beta")),
                         (None, None, NO_ALIAS, None))

    def test_c_leading_vendor_word_dropped_only_when_publisher_has_it(self):
        self.assertEqual(got(gen("Mozilla Firefox", "128.0", "Mozilla")),
                         ("firefox", "128", None, GENERATED))
        self.assertEqual(
            got(gen("Mozilla Firefox (x64 en-US)", "115.9.1",
                    "Mozilla Corporation")),
            ("firefox", "115", None, GENERATED))
        # No publisher, or another publisher: the word stays.
        self.assertEqual(got(gen("Mozilla Firefox", "128.0")),
                         (None, None, NO_ALIAS, None))
        self.assertEqual(got(gen("Mozilla Firefox", "128.0", "Acme")),
                         (None, None, NO_ALIAS, None))
        # A leading word that is not this product's vendor is not dropped.
        self.assertEqual(got(gen("Acme Firefox", "128.0", "Acme")),
                         (None, None, NO_ALIAS, None))

    def test_d_tail_version_used_when_the_column_is_empty(self):
        self.assertEqual(got(gen("Foo Tool 2.1")),
                         ("foo-tool", "2.1", None, GENERATED))
        self.assertEqual(got(gen("Foo Tool v3.0", "  ")),
                         ("foo-tool", "3.0", None, GENERATED))
        self.assertEqual(got(gen("Mozilla Firefox 128", "", "Mozilla")),
                         ("firefox", "128", None, GENERATED))

    def test_d_tail_and_column_agree(self):
        self.assertEqual(got(gen("Foo Tool 2.1", "2.1.5")),
                         ("foo-tool", "2.1", None, GENERATED))

    def test_d_tail_and_column_disagree_is_undecided(self):
        self.assertEqual(got(gen("Foo Tool 2.1", "3.0.1")),
                         ("foo-tool", None, NO_CYCLE, GENERATED))
        # Both pick a cycle, but not the same one: 2.2 against 2.1.
        self.assertEqual(got(gen("Foo Tool 2.2", "2.1.9")),
                         ("foo-tool", None, NO_CYCLE, GENERATED))

    def test_d_update_style_token_is_not_split(self):
        self.assertEqual(got(gen("Foo Tool 8u392", "8.0.392")),
                         (None, None, NO_ALIAS, None))

    def test_two_products_found_after_level_one_is_ambiguous(self):
        # "beta 2" after dropping the vendor word, "alpha beta" + tail 2.
        self.assertEqual(got(gen("Alpha Beta 2", "", "Alpha")),
                         (None, None, AMBIGUOUS, None))
        self.assertEqual(got(gen("Alpha Beta 2", "")),
                         ("alpha-beta", "2", None, GENERATED))

    def test_lookup_returns_sorted_ids(self):
        ids, tails = INDEX.lookup("Alpha Beta 2", "Alpha")
        self.assertEqual(ids, ("alpha-beta", "beta-2"))
        self.assertEqual(tails, {"alpha-beta": "2", "beta-2": None})

    def test_version_handling(self):
        self.assertEqual(got(gen("Foo Tool")),
                         ("foo-tool", None, NO_VERSION, GENERATED))
        self.assertEqual(got(gen("Foo Tool", "9.9")),
                         ("foo-tool", None, NO_CYCLE, GENERATED))
        # Part boundaries: 2.10 is not 2.1.
        self.assertEqual(got(gen("Foo Tool", "2.10")),
                         ("foo-tool", None, NO_CYCLE, GENERATED))

    def test_slug_and_id_forms_never_match(self):
        for name in ("foo-tool", "footool", "foo_tool", "foo"):
            with self.subTest(name=name):
                self.assertEqual(gen(name, "2.1").product, None)


class VendorTokenTests(unittest.TestCase):
    def confirmed(self, name, publisher, version):
        return gen(name, version, publisher).product

    def test_single_vendor_token(self):
        self.assertEqual(self.confirmed(
            "Webserver", "The Apache Software Foundation", "2.4.1"),
            "webserver")
        for pub in ("ApacheFriends", "apachefriends.org", "Apaches Ltd", ""):
            with self.subTest(pub=pub):
                self.assertIsNone(self.confirmed("Webserver", pub, "2.4.1"))

    def test_multi_token_vendor_is_a_whole_phrase(self):
        self.assertEqual(self.confirmed("Idserver", "Red Hat, Inc.", "23.0"),
                         "idserver")
        for pub in ("Red Gate Software", "RedHat", "Hat Red", "Red"):
            with self.subTest(pub=pub):
                self.assertIsNone(self.confirmed("Idserver", pub, "23.0"))
        self.assertEqual(self.confirmed("Scanner", "Clam Anti-Virus", "1.0"),
                         "scanner")
        self.assertIsNone(self.confirmed("Scanner", "Clam", "1.0"))

    def test_no_fragments_or_prefixes(self):
        self.assertEqual(self.confirmed("Sunny", "Sun Microsystems", "1"),
                         "sunny")
        for pub in ("Sunbird", "sunsoft", "Sundance Labs"):
            with self.subTest(pub=pub):
                self.assertIsNone(self.confirmed("Sunny", pub, "1"))

    def test_namespaces_are_whole_tokens(self):
        self.assertEqual(self.confirmed("Vaulty", "HashiCorp", "1.17.6"),
                         "vaulty")
        # A dotted maven group id never equals one publisher token.
        for pub in ("org.apache.tomcat", "Apache Tomcat", "org"):
            with self.subTest(pub=pub):
                self.assertIsNone(self.confirmed("Catalina", pub, "9.0.1"))

    def test_curated_publisher_alias_phrase(self):
        self.assertEqual(self.confirmed("Jsrun", "OpenJS Foundation", "20.1"),
                         "jsrun")
        self.assertIsNone(self.confirmed("Jsrun", "OpenJS", "20.1"))
        self.assertIsNone(self.confirmed("Jsrun", "Foundation OpenJS", "20.1"))

    def test_tokens_helper(self):
        self.assertEqual(tokens("Red Hat, Inc."), ("red", "hat", "inc"))
        self.assertEqual(tokens("Clam Anti-Virus"), ("clam", "anti", "virus"))
        self.assertEqual(tokens(""), ())

    def test_index_phrases(self):
        self.assertEqual(INDEX.phrases["idserver"], (("red", "hat"),))
        self.assertEqual(INDEX.phrases["scanner"],
                         (("clam", "anti", "virus"),))
        self.assertEqual(INDEX.phrases["catalina"], (("org.apache.tomcat",),))
        self.assertEqual(INDEX.phrases["jsrun"],
                         (("jsrun",), ("openjs", "foundation")))


class OneWordAndCurationTests(unittest.TestCase):
    def test_one_word_title_needs_publisher_confirmation(self):
        self.assertIsNone(gen("Plainword", "1.0").product)
        self.assertIsNone(gen("Plainword", "1.0", "Plainword Inc").product)
        self.assertIsNone(gen("Firefox", "128.0").product)
        self.assertEqual(gen("Firefox", "128.0", "Mozilla").product,
                         "firefox")

    def test_one_word_title_refused_does_not_fall_through_to_a_split(self):
        # "bind" alone is a one-word title, unconfirmed: no match at all.
        self.assertEqual(got(gen("BIND", "9.18")),
                         (None, None, NO_ALIAS, None))

    def test_allowlisted_one_word_title(self):
        self.assertEqual(got(gen("Listed", "4.1")),
                         ("listed", "4", None, GENERATED))
        self.assertEqual(gen("Listed", "4.1", "Anyone At All").product,
                         "listed")

    def test_multi_word_title_needs_no_publisher(self):
        self.assertEqual(gen("Northwind DBMS", "7.2").product, "dbms")
        self.assertEqual(gen("Northwind DBMS", "7.2", "Someone").product,
                         "dbms")

    def test_generated_off(self):
        self.assertIsNone(gen("Gizmo Phone", "8").product)
        self.assertIsNone(gen("Gizmo Phone 8").product)

    def test_exclusion_needs_name_and_publisher_token(self):
        self.assertIsNone(gen("Chatter", "9.3.0", "Chatter, Inc.").product)
        self.assertIsNone(gen("Chatter (x64)", "9.3.0", "Chatter").product)

    def test_exclusion_is_compared_with_every_candidate_form(self):
        # A version in the name, a repeated vendor word, arch groups: each
        # candidate form is compared, not only the whole name.
        for name, ver in (("Chatter 9.3", ""), ("Chatter 9.3.0", "9.3.0"),
                          ("Chatter 9", "9.3.0"), ("Chatter Chatter", "9.3"),
                          ("Chatter 9.3.0 (x64)", "9.3.0"),
                          ("Chatter Chatter 9.3", "")):
            with self.subTest(name=name):
                self.assertIsNone(gen(name, ver, "Chatter, Inc.").product)

    def test_exclusion_with_empty_publisher_blocks_any_publisher(self):
        index = build_index(CATALOG, dict(CURATION, exclusions=[
            {"product": "foo-tool", "name": "Foo Tool", "publisher": "",
             "reason": "r", "gold": "a|b|c"}]))
        for pub in ("", "Acme"):
            r = match_product("Foo Tool", "2.1", [], PRODUCTS,
                              catalog_index=index, publisher=pub)
            self.assertIsNone(r.product, pub)
        r = match_product("Foo Tool 2.1", "", [], PRODUCTS,
                          catalog_index=index)
        self.assertIsNone(r.product)
        r = match_product("Foo Tool Pro", "2.1", [], PRODUCTS,
                          catalog_index=index)
        self.assertIsNone(r.product)

    def test_exclusion_names_are_cleaned(self):
        self.assertIsNone(gen("Foo Tool Helper", "2.1").product)
        self.assertEqual(INDEX.exclusions["foo tool helper"],
                         (("foo-tool", ()),))

    def test_exclusions_never_silence_curated_aliases(self):
        a = [alias("chatter", "chatter")]
        self.assertEqual(got(gen("Chatter", "9.3.0", "Chatter", a)),
                         ("chatter", "9.3", None, CURATED))


class VersionInNameTests(unittest.TestCase):
    """A one-word title plus a version token, on a row with no publisher
    (swlc/catalog_match.py, "Version-in-name rule")."""
    INDEX = build_index(CATALOG, CURATION, version_names=(
        "plainword", "chatter", "gizmo", "foo-tool", "sunny"))

    def m(self, name, version="", publisher=""):
        return got(match_product(name, version, [], PRODUCTS,
                                 catalog_index=self.INDEX,
                                 publisher=publisher))

    def test_listed_title_with_a_version_that_fits_matches(self):
        want = ("plainword", "1", None, GENERATED)
        self.assertEqual(self.m("Plainword 1.2"), want)
        self.assertEqual(self.m("Plainword 1.2", "1.2.3"), want)
        self.assertEqual(self.m("Plainword 1.2 (x64)", "1.2"), want)
        self.assertEqual(self.m("PLAINWORD v1.2"), want)
        self.assertEqual(self.m("Plainword 1.2.0-hf"), want)

    def test_the_version_must_decide_one_cycle(self):
        for name, version in (("Plainword 9.9", ""), ("Plainword 9.9", "9.9"),
                              ("Plainword 1.2", "2.0"),
                              ("Plainword 2.0", "1.2")):
            with self.subTest(name=name, version=version):
                self.assertEqual(self.m(name, version),
                                 (None, None, NO_ALIAS, None))

    def test_a_publisher_still_needs_the_vendor_check(self):
        for pub in ("Acme", "Plainword Inc"):
            with self.subTest(pub=pub):
                self.assertEqual(self.m("Plainword 1.2", "1.2", pub),
                                 (None, None, NO_ALIAS, None))
        # A confirming publisher matches as before, without the rule.
        self.assertEqual(self.m("Sunny 1.0", "1.0", "Sun Microsystems"),
                         ("sunny", "1", None, GENERATED))

    def test_bare_name_and_other_words_are_not_touched(self):
        for name in ("Plainword", "Plainword Pro 1.2", "Plainword 1.2 Pro",
                     "Plainword 1.2-beta", "Plainword 8u1"):
            with self.subTest(name=name):
                self.assertEqual(self.m(name, "1.2"),
                                 (None, None, NO_ALIAS, None))

    def test_unlisted_title_is_not_matched(self):
        self.assertEqual(self.m("Lexicon 1.0", "1.0"),
                         (None, None, NO_ALIAS, None))
        self.assertEqual(got(gen("Plainword 1.2")),
                         (None, None, NO_ALIAS, None))

    def test_exclusions_devices_and_generated_off_keep_winning(self):
        self.assertNotIn("chatter", self.INDEX.version_names)
        self.assertNotIn("gizmo", self.INDEX.version_names)
        self.assertEqual(self.m("Chatter 9.3.0", "9.3.0"),
                         (None, None, NO_ALIAS, None))
        self.assertEqual(self.m("Chatter 9.3"),
                         (None, None, NO_ALIAS, None))

    def test_only_one_word_titles_are_listed(self):
        # foo-tool is a two-word title: it needs no rule and is dropped.
        self.assertEqual(self.INDEX.version_names,
                         frozenset(("plainword", "sunny")))

    def test_lookup_without_fits_leaves_the_rule_off(self):
        self.assertEqual(self.INDEX.lookup("Plainword 1.2"), ((), {}))
        self.assertEqual(
            self.INDEX.lookup("Plainword 1.2", "", lambda p, t: True),
            (("plainword",), {"plainword": "1.2"}))


class PrecedenceTests(unittest.TestCase):
    def test_curated_match_wins_and_is_marked_curated(self):
        a = [alias("foo tool", "foo-tool")]
        self.assertEqual(got(gen("Foo Tool", "2.1.4", aliases=a)),
                         ("foo-tool", "2.1", None, CURATED))

    def test_curated_no_cycle_or_no_version_stops_generation(self):
        a = [alias("foo tool", "foo-tool", cycle="9.9")]
        self.assertEqual(got(gen("Foo Tool", "2.1", aliases=a)),
                         ("foo-tool", None, NO_CYCLE, CURATED))
        a = [alias("foo tool", "foo-tool")]
        self.assertEqual(got(gen("Foo Tool", "", aliases=a)),
                         ("foo-tool", None, NO_VERSION, CURATED))

    def test_rejected_curated_tail_does_not_fall_through(self):
        # "widget" + tail "pro" is rejected by the strict tail rule; the
        # title "Widget Pro" must not then decide the row.
        a = [alias("widget", "gadget-suite", match="prefix")]
        self.assertEqual(got(gen("Widget Pro", "1.0", aliases=a)),
                         (None, None, NO_ALIAS, None))
        self.assertEqual(got(gen("Widget Pro", "1.0")),
                         ("widget-pro", "1", None, GENERATED))

    def test_curated_ambiguity_stops_generation(self):
        a = [alias("widget", "gadget-suite", match="prefix"),
             alias("widget pro", "dbms", match="prefix")]
        self.assertEqual(got(gen("Widget Pro", "1.0", aliases=a)),
                         (None, None, AMBIGUOUS, None))

    def test_curated_x_and_generated_y_is_ambiguous(self):
        a = [alias("gadget suite", "widget-pro")]
        self.assertEqual(got(gen("Gadget Suite", "1.0", aliases=a)),
                         (None, None, AMBIGUOUS, None))
        # Also when the curated alias found the product but no cycle.
        a = [alias("gadget suite", "widget-pro", cycle="7")]
        self.assertEqual(got(gen("Gadget Suite", "1.0", aliases=a)),
                         (None, None, AMBIGUOUS, None))

    def test_without_an_index_generated_matching_is_off(self):
        self.assertEqual(
            match_product("Foo Tool", "2.1", [], PRODUCTS),
            MatchResult(None, None, NO_ALIAS))
        a = [alias("foo tool", "foo-tool")]
        self.assertEqual(
            match_product("Foo Tool", "2.1", a, PRODUCTS),
            MatchResult("foo-tool", {"cycle": "2.1"}, None, source=CURATED))


class CuratedCrossCheckTests(unittest.TestCase):
    PY = [alias("python", "python", match="prefix", version_from="name")]
    PY_CYCLES = {"python": [{"cycle": c} for c in
                            ("3.15", "3.12", "3.11", "2.7", "2.6")]}

    def py(self, name, version):
        return got(match_product(name, version, self.PY, self.PY_CYCLES))

    def test_name_and_column_disagree_is_undecided(self):
        self.assertEqual(self.py("Python 3.11.7 (64-bit)", "3.12.1150.0"),
                         ("python", None, NO_CYCLE, CURATED))
        self.assertEqual(self.py("Python 3.15.1", "2.6.9"),
                         ("python", None, NO_CYCLE, CURATED))
        self.assertEqual(self.py("Python 3.15.1", "1.0.1"),
                         ("python", None, NO_CYCLE, CURATED))

    def test_same_cycle_from_both_is_decided(self):
        # The python.org installer writes 3.12.1 as 3.12.1150.0.
        self.assertEqual(self.py("Python 3.12.1 (64-bit)", "3.12.1150.0"),
                         ("python", "3.12", None, CURATED))
        self.assertEqual(self.py("Python 3.12.1", ""),
                         ("python", "3.12", None, CURATED))

    def test_launcher_word_is_not_a_version(self):
        self.assertEqual(self.py("Python Launcher", "3.12.1150.0"),
                         (None, None, NO_ALIAS, None))

    def test_build_map_alias_cross_check(self):
        a = [alias("microsoft sql server", "mssqlserver", match="prefix",
                   version_from="name",
                   build_map={"2019": "15.0", "2022": "16.0"})]
        products = {"mssqlserver": [{"cycle": "15.0"}, {"cycle": "16.0"}]}

        def m(name, version):
            return got(match_product(name, version, a, products))
        self.assertEqual(m("Microsoft SQL Server 2019", "15.0.2000.5"),
                         ("mssqlserver", "15.0", None, CURATED))
        self.assertEqual(m("Microsoft SQL Server 2019", ""),
                         ("mssqlserver", "15.0", None, CURATED))
        self.assertEqual(m("Microsoft SQL Server 2019", "16.0.1000.6"),
                         ("mssqlserver", None, NO_CYCLE, CURATED))
        self.assertEqual(m("Microsoft SQL Server 2019", "2022"),
                         ("mssqlserver", None, NO_CYCLE, CURATED))

    def test_column_map_catches_a_build_from_another_year(self):
        a = [alias("windows server", "windows-server", match="prefix",
                   version_from="name", edition_words=["standard"],
                   build_map={"2019": "2019", "2022": "2022"},
                   column_map={"10.0.17763": ["2019", "1809-sac"],
                               "10.0.20348": "2022"})]
        products = {"windows-server": [{"cycle": c} for c in
                                       ("2019", "2022", "1809-sac")]}

        def m(name, version):
            return got(match_product(name, version, a, products))
        self.assertEqual(m("Windows Server 2022 Standard", "10.0.17763.6532"),
                         ("windows-server", None, NO_CYCLE, CURATED))
        self.assertEqual(m("Windows Server 2019 Standard", "10.0.17763.6532"),
                         ("windows-server", "2019", None, CURATED))
        self.assertEqual(m("Windows Server 2022 Standard", "10.0.20348.2849"),
                         ("windows-server", "2022", None, CURATED))
        # A build the column_map does not list is not checked.
        self.assertEqual(m("Windows Server 2022 Standard", "10.0.99999"),
                         ("windows-server", "2022", None, CURATED))

    def test_bad_column_map_is_a_data_error(self):
        from swlc.errors import DataError
        for bad in ({}, [], {"1": []}, {"1": ""}, {"1": [1]}, {"": "1"},
                    {" ": "1"}):
            a = [alias("x", "x", version_from="name", build_map={"1": "1"},
                       column_map=bad)]
            with self.subTest(bad=bad):
                with self.assertRaises(DataError):
                    match_product("x 1", "1", a, {"x": [{"cycle": "1"}]})
        # Without build_map, or on an alias reading the version column,
        # a column_map would be ignored: refused instead.
        for extra in ({"version_from": "name"},
                      {"version_from": "version", "build_map": {"1": "1"}}):
            a = [dict(alias("x", "x", column_map={"1": "1"}), **extra)]
            with self.subTest(extra=extra):
                with self.assertRaises(DataError):
                    match_product("x 1", "1", a, {"x": [{"cycle": "1"}]})
        # build_map keys are checked the same way.
        a = [alias("x", "x", build_map={"": "1"})]
        with self.assertRaises(DataError):
            match_product("x", "1", a, {"x": [{"cycle": "1"}]})

    def test_year_name_with_build_column_still_decides(self):
        # Windows Server cycles are years and the column is a build: the
        # column reads as neither a map key nor a label, so it takes no part.
        a = [alias("windows server", "windows-server", match="prefix",
                   version_from="name", edition_words=["standard"],
                   build_map={"2019": "2019"})]
        products = {"windows-server": [{"cycle": "2019"}]}
        self.assertEqual(
            got(match_product("Windows Server 2019 Standard", "10.0.17763",
                              a, products)),
            ("windows-server", "2019", None, CURATED))


class DeterminismTests(unittest.TestCase):
    NAMES = ["Foo Tool 2.1", "Mozilla Firefox", "Alpha Beta 2", "BIND 9",
             "Webserver", "Listed", "Chatter", "Northwind DBMS (x64)"]

    def test_index_does_not_depend_on_catalog_order(self):
        ids = list(CATALOG)
        rng = random.Random(7)
        for _ in range(5):
            rng.shuffle(ids)
            shuffled = {i: copy.deepcopy(CATALOG[i]) for i in ids}
            other = build_index(shuffled, copy.deepcopy(CURATION))
            for field in ("titles", "phrases", "leads", "exclusions"):
                self.assertEqual(dict(getattr(other, field)),
                                 dict(getattr(INDEX, field)), field)
            for name in self.NAMES:
                for pub in ("", "Mozilla", "Alpha", "Apache", "Chatter"):
                    self.assertEqual(other.lookup(name, pub),
                                     INDEX.lookup(name, pub))

    def test_index_is_read_only(self):
        with self.assertRaises(TypeError):
            INDEX.titles["x"] = ("y",)
        with self.assertRaises(AttributeError):
            INDEX.allow.add("x")
        with self.assertRaises(Exception):
            INDEX.off = frozenset()

    def test_same_answer_twice(self):
        for name in self.NAMES:
            for ver in ("", "2.1", "9.18.1", "128.0"):
                self.assertEqual(gen(name, ver, "Mozilla"),
                                 gen(name, ver, "Mozilla"))


class FixRoundTests(unittest.TestCase):
    """Rules added after the adversarial review."""

    def test_device_products_never_match_by_title(self):
        self.assertIsNone(gen("Tabby Tablet", "8").product)
        self.assertIsNone(gen("Tabby Tablet 8", "", "Tabby").product)
        self.assertIn("tabby", INDEX.devices)
        # A curated alias may still name a device on purpose.
        a = [alias("tabby tablet", "tabby")]
        self.assertEqual(gen("Tabby Tablet", "8", aliases=a).product,
                         "tabby")

    def test_self_title_vendor_needs_the_bare_publisher(self):
        for pub in ("Promo", "Promo Inc.", "The Promo Foundation",
                    "PROMO GmbH", "Promo Software Ltd", "promo project"):
            with self.subTest(pub=pub):
                self.assertEqual(gen("Promo", "3.5.1", pub).product, "promo")
        for pub in ("Promo Group Inc.", "Bot Framework Promo", "Promo Labs",
                    "The Promo Authors", "Promo Promo"):
            with self.subTest(pub=pub):
                self.assertIsNone(gen("Promo", "3.5.1", pub).product)

    def test_publisher_alias_adds_a_publisher_the_self_title_rule_refuses(self):
        index = build_index(CATALOG, dict(CURATION, publisher_aliases={
            "promo": {"phrases": ["promo labs"], "reason": "r",
                      "source": "https://example.com/p"}}))
        for pub, want in (("Promo Labs", "promo"), ("Promo Labs, Inc.", "promo"),
                          ("The Promo Labs Team", "promo"),
                          ("Promo Group Inc.", None), ("Labs Promo", None)):
            with self.subTest(pub=pub):
                r = match_product("Promo", "3.5.1", [], PRODUCTS,
                                  catalog_index=index, publisher=pub)
                self.assertEqual(r.product, want)

    def test_self_title_rule_also_governs_the_leading_word_drop(self):
        self.assertEqual(gen("Promo Promo", "3.5", "Promo Inc").product,
                         "promo")
        self.assertIsNone(gen("Promo Promo", "3.5", "Promo Group").product)

    def test_other_vendor_words_keep_the_run_rule(self):
        # Mozilla is not Firefox's own title: any run of it confirms.
        self.assertEqual(gen("Firefox", "128.1", "Mozilla Labs").product,
                         "firefox")

    def test_mixed_granularity_guard(self):
        def m(name, ver):
            return got(gen(name, ver))
        # 4.6 has children 4.6.1 and 4.6.2: an unknown next part is not 4.6.
        self.assertEqual(m("Frame Work", "4.6.01590"),
                         ("frame-work", None, NO_CYCLE, GENERATED))
        self.assertEqual(m("Frame Work", "4.8.09032"),
                         ("frame-work", None, NO_CYCLE, GENERATED))
        # A version that names a child, or stops at the cycle, is decided.
        self.assertEqual(m("Frame Work", "4.6.2.1"),
                         ("frame-work", "4.6.2", None, GENERATED))
        self.assertEqual(m("Frame Work", "4.6"),
                         ("frame-work", "4.6", None, GENERATED))
        self.assertEqual(m("Frame Work", "4.8.1"),
                         ("frame-work", "4.8.1", None, GENERATED))
        # A child cycle with no children of its own keeps today's rule.
        self.assertEqual(m("Weekly Builder", "2.426.3"),
                         ("weekly", "2.426", None, GENERATED))
        # 450 is a plain release number, not a build: cycle 2.
        self.assertEqual(m("Weekly Builder", "2.450"),
                         ("weekly", "2", None, GENERATED))
        self.assertEqual(m("Weekly Builder", "2"),
                         ("weekly", "2", None, GENERATED))
        # Childless cycles are unchanged.
        self.assertEqual(m("Foo Tool", "2.1.1150.0"),
                         ("foo-tool", "2.1", None, GENERATED))

    def test_guard_refuses_only_build_shaped_extra_parts(self):
        def m(ver):
            return got(gen("Frame Work", ver))[1:3]
        # Build-shaped: zero-padded (more than one character), more than
        # three digits, or not all digits.
        for ver in ("4.6.01590", "4.6.00079", "4.6.01", "4.8.4084.0",
                    "4.8.03761", "4.6.3a", "4.6.1590", "4.6.x"):
            with self.subTest(ver=ver):
                self.assertEqual(m(ver), (None, NO_CYCLE))
        # A plain number of three digits or fewer, no leading zero.
        for ver, cyc in (("4.6.0", "4.6"), ("4.6.3", "4.6"),
                         ("4.6.999", "4.6"), ("4.8.0.1", "4.8"),
                         ("4.6.2", "4.6.2"), ("4.6.1.7", "4.6.1")):
            with self.subTest(ver=ver):
                self.assertEqual(m(ver), (cyc, None))

    def test_mixed_granularity_guard_for_curated_aliases(self):
        a = [alias("frame work", "frame-work")]
        self.assertEqual(got(gen("Frame Work", "4.6.01590", aliases=a)),
                         ("frame-work", None, NO_CYCLE, CURATED))
        self.assertEqual(got(gen("Frame Work", "4.6.1.5", aliases=a)),
                         ("frame-work", "4.6.1", None, CURATED))

    def test_locale_strip_needs_a_real_locale_tag(self):
        self.assertEqual(strip_arch("foo go-to"), "foo go-to")
        self.assertEqual(strip_arch("foo (go-to)"), "foo (go-to)")
        self.assertEqual(strip_arch("foo zz-yy"), "foo zz-yy")
        for tag in ("en-us", "en_gb", "de-ch", "pt-br", "zh_tw", "ar-sa"):
            with self.subTest(tag=tag):
                self.assertEqual(strip_arch("foo " + tag), "foo")
                self.assertEqual(strip_arch("foo (x64 %s)" % tag), "foo")
        self.assertIsNone(gen("Foo Tool go-to", "2.1").product)

    def test_any_language_region_pair_is_a_locale(self):
        tags = ("es-AR fy-NL ga-IE gu-IN hi-IN hy-AM ne-NP nn-NO pa-IN "
                "es-CL en-ZA en-CA pt-PT sv-SE nb-NO zh-CN zh-TW cs-CZ "
                "he-IL th-TH ms-MY").split()
        self.assertEqual(len(tags), 20 + 1)
        for tag in tags:
            for form in (tag, tag.replace("-", "_")):
                with self.subTest(tag=form):
                    norm = normalize_name("Foo Tool (%s)" % form)
                    self.assertEqual(strip_arch(norm), "foo tool")
                    self.assertEqual(strip_arch("foo tool " + form.lower()),
                                     "foo tool")
        self.assertEqual(got(gen("Foo Tool (es-AR)", "2.2.0")),
                         ("foo-tool", "2.2", None, GENERATED))

    def test_words_of_locale_shape_that_are_not_pairs_stay(self):
        # First part not a language, or second part not a region.
        for word in ("go-to", "up-to", "on-off", "zz-us", "en-zz", "en-usa",
                     "e-us", "en-u", "en--us"):
            with self.subTest(word=word):
                self.assertEqual(strip_arch("foo " + word), "foo " + word)
                self.assertEqual(strip_arch("foo (%s)" % word),
                                 "foo (%s)" % word)

    def test_locale_sets_are_constant_strings(self):
        from swlc import catalog_match as cm
        self.assertEqual(len(cm._LANGS), 183)
        self.assertEqual(len(cm._REGIONS), 249)
        self.assertTrue(all(len(c) == 2 and c.islower() and c.isalpha()
                            for c in cm._LANGS | cm._REGIONS))

    def test_long_names_are_never_matched_by_title(self):
        name = "Foo Tool " + " ".join(["x"] * 70)
        self.assertEqual(INDEX.lookup(name, ""), ((), {}))
        self.assertEqual(INDEX.lookup("Foo " * 31 + "Tool", ""), ((), {}))

    def test_max_lead_is_the_longest_phrase(self):
        self.assertEqual(INDEX.max_lead, 3)   # clam anti virus


class NoCycleVersionTests(unittest.TestCase):
    """no_cycle_versions: an older numbering whose numbers overlap the
    product's cycles (calendar 21.3.1 against cycle 21)."""
    CAT = {"vm-ce": rec("vm-ce", "Vm Community Edition")}
    CYC = {"vm-ce": [{"cycle": c} for c in ("17", "21", "22", "25")]}
    CUR = {"format": 1, "publisher_aliases": {}, "single_word_allowlist": [],
           "exclusions": [], "generated_off": [],
           "no_cycle_versions": {"vm-ce": {
               "prefixes": ["21.0.0", "21.3", "22.0.0", "22.3"],
               "reason": "calendar numbering", "source": "https://example.com/v"}}}

    def m(self, name, version="", cur=None):
        index = build_index(self.CAT, self.CUR if cur is None else cur)
        return got(match_product(name, version, [], self.CYC,
                                 catalog_index=index))

    def test_old_numbering_gets_no_cycle(self):
        for name, ver in (("Vm Community Edition", "22.3.3"),
                          ("Vm Community Edition 21.3.1", "21.3.1"),
                          ("Vm Community Edition 22.0.0.2", ""),
                          ("Vm Community Edition 21.3.1", ""),
                          ("Vm Community Edition", "21.0.0")):
            with self.subTest(name=name, ver=ver):
                self.assertEqual(self.m(name, ver),
                                 ("vm-ce", None, NO_CYCLE, GENERATED))

    def test_new_numbering_keeps_its_cycle(self):
        for name, ver, cyc in (("Vm Community Edition", "21.0.2", "21"),
                               ("Vm Community Edition 22.0.1", "", "22"),
                               ("Vm Community Edition", "22", "22"),
                               ("Vm Community Edition", "25.4.4.1.1", "25"),
                               ("Vm Community Edition", "17.0.9", "17")):
            with self.subTest(name=name, ver=ver):
                self.assertEqual(self.m(name, ver),
                                 ("vm-ce", cyc, None, GENERATED))

    def test_a_name_in_old_numbering_is_checked_too(self):
        self.assertEqual(self.m("Vm Community Edition 21.3.1", "21.0.2"),
                         ("vm-ce", None, NO_CYCLE, GENERATED))

    def test_without_the_entry_the_cycle_is_picked(self):
        cur = dict(self.CUR)
        del cur["no_cycle_versions"]
        self.assertEqual(self.m("Vm Community Edition", "22.3.3", cur),
                         ("vm-ce", "22", None, GENERATED))

    def test_index_holds_part_tuples(self):
        index = build_index(self.CAT, self.CUR)
        self.assertEqual(index.no_cycle["vm-ce"],
                         (("21", "0", "0"), ("21", "3"), ("22", "0", "0"),
                          ("22", "3")))


class ReviewVersionTests(unittest.TestCase):
    """review_versions (issue #21): a version that fits several support
    lines keeps the product, gets no cycle and the entry's review code."""
    CAT = {"glassview": rec("glassview", "Glassview Browser")}
    CYC = {"glassview": [{"cycle": c} for c in
                         ("11", "11-server", "11-ltsc", "10", "9")]}
    CUR = {"format": 1, "publisher_aliases": {}, "single_word_allowlist": [],
           "exclusions": [], "generated_off": [],
           "review_versions": {"glassview": {
               "prefixes": ["11"], "code": SHARED_SUPPORT_LINES,
               "reason": "several support lines", "gold": "a|b|c",
               "source": "https://example.com/v"}}}

    def m(self, name, version="", cur=None, aliases=()):
        index = build_index(self.CAT, self.CUR if cur is None else cur)
        result, code = match_noted(name, version, list(aliases), self.CYC,
                                   catalog_index=index)
        plain = match_product(name, version, list(aliases), self.CYC,
                              catalog_index=index)
        self.assertEqual(result, plain)
        return got(result), code

    def test_listed_version_keeps_the_product_with_no_cycle(self):
        want = (("glassview", None, NO_CYCLE, GENERATED),
                SHARED_SUPPORT_LINES)
        for name, ver in (("Glassview Browser", "11.0.9600.1"),
                          ("Glassview Browser", "11"),
                          ("Glassview Browser 11", ""),
                          ("Glassview Browser 11", "11.0.17763.0"),
                          ("Glassview Browser 11", "10.0.9200.1")):
            with self.subTest(name=name, ver=ver):
                self.assertEqual(self.m(name, ver), want)

    def test_other_versions_are_unchanged(self):
        for name, ver, cyc in (("Glassview Browser", "10.0.9200.1", "10"),
                               ("Glassview Browser 10", "", "10"),
                               ("Glassview Browser 9", "9.0.8112.1", "9")):
            with self.subTest(name=name, ver=ver):
                self.assertEqual(self.m(name, ver),
                                 (("glassview", cyc, None, GENERATED), None))

    def test_a_version_that_names_its_line_keeps_that_cycle(self):
        for ver in ("11-server", "11-ltsc", "11-LTSC"):
            with self.subTest(ver=ver):
                cyc = ver.lower()
                self.assertEqual(self.m("Glassview Browser", ver),
                                 (("glassview", cyc, None, GENERATED), None))
        # The name says 11, the version names a line: no cycle (as before
        # review_versions) and no review code, whose text would be false.
        self.assertEqual(self.m("Glassview Browser 11", "11-ltsc"),
                         (("glassview", None, NO_CYCLE, GENERATED), None))

    def test_without_the_entry_the_generic_cycle_is_picked(self):
        cur = dict(self.CUR)
        del cur["review_versions"]
        self.assertEqual(self.m("Glassview Browser", "11.0.9600.1", cur),
                         (("glassview", "11", None, GENERATED), None))

    def test_curated_alias_still_wins(self):
        aliases = [alias("glassview browser", "glassview")]
        self.assertEqual(self.m("Glassview Browser", "11.0.9600.1",
                                aliases=aliases),
                         (("glassview", "11", None, CURATED), None))

    def test_index_holds_part_tuples_and_the_code(self):
        index = build_index(self.CAT, self.CUR)
        self.assertEqual(index.review["glassview"],
                         ((("11",),), SHARED_SUPPORT_LINES))


# --- assess: match_source, overrides on generated rows, format 1 -----------

AS_OF = date(2026, 10, 24)
COLMAP = {"name": "name", "version": "version", "publisher": "publisher",
          "owner": "owner"}
CYCLE_DATA = {
    "foo-tool": [{"cycle": "2.1", "eol": date(2025, 1, 1), "support": False,
                  "extended": None},
                 {"cycle": "3.0", "eol": date(2030, 1, 1), "support": True,
                  "extended": None}],
    "firefox": [{"cycle": "128", "eol": date(2030, 1, 1), "support": True,
                 "extended": None}],
}


def data_with(catalog=True, aliases=()):
    return Data(release_id="r", file_hashes={}, aliases=list(aliases),
                products=copy.deepcopy(CYCLE_DATA), kev=[],
                kev_catalog_version="1", kev_age_days=1, eol_age_days=1,
                catalog={k: CATALOG[k] for k in CYCLE_DATA}
                if catalog else None,
                curation=copy.deepcopy(CURATION) if catalog else None)


def assess_rows(rows, data, golden=None, exceptions=None):
    rows = [{"name": n, "version": v, "publisher": p, "owner": "ops"}
            for n, v, p in rows]
    return assess(group_rows(rows, COLMAP), data, golden or Golden(),
                  exceptions or Exceptions(), {}, AS_OF)


def by_name(out):
    return {it["name"]: it for it in out["items"]}


class AssessTests(unittest.TestCase):
    ROWS = [("Foo Tool", "2.1.4", ""), ("Foo Tool", "9.9", ""),
            ("Mozilla Firefox", "128.1", "Mozilla"), ("Nothing", "1", ""),
            ("Firefox", "128.1", "")]

    def test_match_source_for_each_path(self):
        a = [alias("mozilla firefox", "firefox")]
        out = assess_rows(self.ROWS, data_with(aliases=a))
        items = {(it["name"], it["version"]): it for it in out["items"]}
        self.assertEqual(items[("Foo Tool", "2.1.4")]["match_source"],
                         "generated")
        self.assertEqual(items[("Foo Tool", "2.1.4")]["state"], "past_eol")
        # Product known, no cycle: the source of the product match.
        self.assertEqual(items[("Foo Tool", "9.9")]["match_source"],
                         "generated")
        self.assertEqual(items[("Foo Tool", "9.9")]["reason"], NO_CYCLE)
        self.assertEqual(items[("Mozilla Firefox", "128.1")]["match_source"],
                         "curated")
        self.assertIsNone(items[("Nothing", "1")]["match_source"])
        self.assertIsNone(items[("Firefox", "128.1")]["match_source"])

    def test_index_is_built_once_and_reused(self):
        data = data_with()
        first = data.matching_index()
        self.assertIs(data.matching_index(), first)
        assess_rows(self.ROWS, data)
        self.assertIs(data.matching_index(), first)

    def test_format_one_data_keeps_the_old_behaviour(self):
        data = data_with(catalog=False)
        self.assertIsNone(data.matching_index())
        out = assess_rows(self.ROWS, data)
        for it in out["items"]:
            self.assertIsNone(it["product"], it["name"])
            self.assertIsNone(it["match_source"])
            self.assertEqual(it["reason"], NO_ALIAS)

    def test_golden_and_exceptions_reach_generated_rows(self):
        golden = Golden({"foo-tool": {
            "product": "foo-tool", "source": "manual",
            "manual_eol": date(2031, 1, 1), "reason": "r", "set_by": "lead",
            "set_on": date(2026, 1, 1), "review_by": date(2027, 1, 1)}})
        exceptions = Exceptions({("foo-tool", ""): {
            "product": "foo-tool", "scope": "",
            "compensating_controls": "isolated", "risk_owner": "risk",
            "approver": "approver", "requested_by": "owner",
            "expires_on": date(2027, 1, 1), "reference": "RISK-1"}})
        out = assess_rows([("Foo Tool", "2.1.4", "")], data_with(),
                          golden, exceptions)
        it = out["items"][0]
        self.assertEqual(it["match_source"], "generated")
        self.assertEqual(it["golden_applied"], "manual")
        self.assertEqual(it["eol_used"], "2031-01-01")
        self.assertTrue(it["accepted_risk"])
        self.assertIn(it["id"], out["lists"]["golden_overrides"])
        # The same row before generated matching: unmatched, no override.
        old = assess_rows([("Foo Tool", "2.1.4", "")],
                          data_with(catalog=False), golden, exceptions)
        self.assertEqual(old["items"][0]["state"], "unmatched")
        self.assertIsNone(old["items"][0]["golden_applied"])

    def test_format_one_folder_loads_with_generated_matching_off(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = make_data_dir(tmp, "2026-10-22", "2026-10-20", data_format=1)
            data = load_data(d, AS_OF)
        self.assertIsNone(data.catalog)
        self.assertIsNone(data.matching_index())


# --- the bundled data: speed -----------------------------------------------

# Measured best of 3 with the alias index (issue #23): 1.3 s (3.15) and
# 1.4 s (3.9) with 155 aliases, 1.3 s and 1.5 s with 300, 1.4 s and 1.5 s
# with 600. The full scan took 3.9 s and 4.6 s with 155 on the same run.
MAX_SECONDS_100K = 10.0


def synthetic_rows(catalog: dict, count: int, seed: int = 11):
    """Made-up inventory rows: real titles with versions, arch suffixes,
    vendor words and noise, plus names that match nothing."""
    rng = random.Random(seed)
    titles = [catalog[p]["title"] for p in sorted(catalog)]
    vendors = sorted({v for p in catalog.values() for v in p["vendors"]})
    words = ["Agent", "Client", "Helper", "Pro", "Tools", "Runtime", "SDK"]
    for i in range(count):
        kind = i % 5
        title = rng.choice(titles)
        ver = "%d.%d.%d" % (rng.randint(0, 30), rng.randint(0, 20),
                            rng.randint(0, 99))
        pub = rng.choice(vendors + [""]).replace("_", " ")
        if kind == 0:
            yield title, ver, pub
        elif kind == 1:
            yield "%s %s (x64 en-US)" % (title, ver), "", pub
        elif kind == 2:
            yield "%s %s" % (pub, title), ver, pub
        elif kind == 3:
            yield "%s %s" % (title, rng.choice(words)), ver, pub
        else:
            yield "Synthetic App %05d" % i, ver, "Nobody %d" % (i % 97)


class BundledSpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        manifest = json.loads((ROOT / "data" / "manifest.json").read_text(
            encoding="utf-8"))
        cls.data = load_data(str(ROOT / "data"),
                             date.fromisoformat(manifest["eol_date"]))

    def test_100000_rows_within_the_bound(self):
        data = self.data
        index = data.matching_index()
        start = time.process_time()
        n = 0
        for name, ver, pub in synthetic_rows(data.catalog, 100000):
            match_product(name, ver, data.aliases, data.products,
                          catalog_index=index, publisher=pub)
            n += 1
        elapsed = time.process_time() - start
        self.assertEqual(n, 100000)
        self.assertLess(elapsed, MAX_SECONDS_100K,
                        "100,000 rows took %.1f s" % elapsed)

    def test_same_results_on_two_runs(self):
        data = self.data
        rows = list(synthetic_rows(data.catalog, 3000, seed=5))

        def run():
            return [match_product(n, v, data.aliases, data.products,
                                  catalog_index=data.matching_index(),
                                  publisher=p) for n, v, p in rows]
        first = run()
        self.assertEqual(first, run())
        self.assertTrue(any(r.source == GENERATED for r in first))

    def test_finer_cycle_guard_on_real_rows(self):
        data = self.data
        index = data.matching_index()
        cases = (
            ("Apache Log4j", "The Apache Software Foundation", "2.17.1", "2"),
            ("Apache Log4j", "The Apache Software Foundation", "2.17.2", "2"),
            ("Apache Log4j", "The Apache Software Foundation", "2.20.0", "2"),
            ("Apache Log4j", "The Apache Software Foundation", "2.23.1", "2"),
            ("Apache Log4j", "The Apache Software Foundation", "2.12.4",
             "2.12"),
            ("Amazon RDS for MySQL", "Amazon Web Services", "8.0.35", "8.0"),
            # Curated review_versions (issue #21): IE 11 fits several
            # support lines, so the product is kept with no cycle.
            ("Internet Explorer", "Microsoft Corporation",
             "11.0.9600.20000", None),
            ("Mule Runtime", "MuleSoft", "4.9.0", "4.9"),
            ("Android OS", "Google", "12.0.0", "12"),
            ("Jenkins", "Jenkins project", "2.587", "2"),
            ("Jenkins", "Jenkins project", "2.430", "2"),
            ("Jenkins", "Jenkins project", "2.440.3", "2.440"),
        )
        for name, pub, ver, want in cases:
            with self.subTest(name=name, ver=ver):
                r = match_product(name, ver, data.aliases, data.products,
                                  catalog_index=index, publisher=pub)
                self.assertEqual((r.product is not None, r.cycle and
                                  r.cycle["cycle"]), (True, want))
        for ver in ("4.6.01590", "4.7.03062", "4.8.09032", "4.5.51209",
                    "4.7.02558", "4.6.01055", "4.8.03761", "4.8.4084.0",
                    "4.6.00079", "4.6.01"):
            with self.subTest(ver=ver):
                r = match_product("Microsoft .NET Framework", ver,
                                  data.aliases, data.products,
                                  catalog_index=index,
                                  publisher="Microsoft Corporation")
                self.assertEqual((r.product, r.cycle, r.reason),
                                 ("dotnetfx", None, NO_CYCLE))

    def test_device_rows_do_not_match(self):
        data = self.data
        for name, pub, ver in (
                ("Apple iPhone", "Apple", "17.5.1"),
                ("Apple iPhone", "", "13.7"),
                ("Google Pixel", "Google", "11"),
                ("Raspberry Pi", "Raspberry Pi Ltd", "5.15.84"),
                ("Amazon Kindle", "Amazon", "2.9.1.71006"),
                ("Samsung Galaxy Tab", "Samsung", "14"),
                ("Samsung Galaxy Watch", "Samsung", "5.0")):
            with self.subTest(name=name, ver=ver):
                r = match_product(name, ver, data.aliases, data.products,
                                  catalog_index=data.matching_index(),
                                  publisher=pub)
                self.assertIsNone(r.product)

    def test_same_name_rows_from_other_publishers_do_not_match(self):
        data = self.data
        for name, pub, ver in (
                ("Node.js", "CollabFS", "1.0.1"),
                ("Node.js", "Visual Studio Code extension", "0.3.1"),
                ("Ubuntu", "Google Fonts", "0.83"),
                ("Ubuntu", "Google Fonts", "22.04"),
                ("Ubuntu", "", "latest"),
                ("Python", "Microsoft Corporation", "2023.22.1"),
                ("Prometheus", "Prometheus Group Inc.", "3.5.0"),
                ("Composer", "Bot Framework Composer", "2.1.2"),
                ("Nextcloud 3.11.0", "Nextcloud GmbH", "3.11.0"),
                ("ClamAV", "ClamWin Pty Ltd", "0.103.2"),
                ("Harbor", "", "2.15.4"),
                ("Kotlin", "", "1.9.22")):
            with self.subTest(name=name, pub=pub, ver=ver):
                r = match_product(name, ver, data.aliases, data.products,
                                  catalog_index=data.matching_index(),
                                  publisher=pub)
                self.assertIsNone(r.product)
        for name, pub, ver, want in (
                ("Node.js", "Node.js Foundation", "20.10.0", "20"),
                ("Node.js", "OpenJS Foundation", "18.19.0", "18"),
                ("Ubuntu", "Canonical Group Limited", "22.04", "22.04"),
                ("Ubuntu 22.04 LTS", "Canonical", "", "22.04"),
                ("Python 3.12.1 (64-bit)", "Python Software Foundation",
                 "3.12.1150.0", "3.12"),
                ("Grafana", "Grafana Labs", "10.2.3", "10.2"),
                ("Prometheus", "The Prometheus Authors", "2.53.1", "2.53"),
                ("Valkey", "", "9.1.2", "9.1"),
                ("OpenTofu", "The Linux Foundation", "1.13.1", "1.13"),
                ("Harbor", "CNCF", "2.15.4", "2.15"),
                ("Kotlin", "JetBrains", "1.9.22", "1.9"),
                ("Windows PowerShell", "Microsoft Corporation",
                 "5.1.19041.4648", "5.1"),
                ("MySQL Server 8.4", "Oracle Corporation", "8.4.9", "8.4"),
                ("Liberica JDK 17 (64-bit)", "BellSoft", "17.0.9.11", "17")):
            with self.subTest(name=name, pub=pub, ver=ver):
                r = match_product(name, ver, data.aliases, data.products,
                                  catalog_index=data.matching_index(),
                                  publisher=pub)
                self.assertEqual(r.cycle and r.cycle["cycle"], want)

    def test_hostile_long_names_are_fast(self):
        data = self.data
        index = data.matching_index()
        words = ("a " * 32768)[:65536]
        lts = ("Ubuntu " + "LTS " * 16384)[:65536]
        pub = ("Apache " * 9363)[:65536]
        for name, publisher in ((words, ""), (lts, ""), (words, pub),
                                (lts, pub)):
            start = time.perf_counter()
            r = match_product(name, "22.04", data.aliases, data.products,
                              catalog_index=index, publisher=publisher)
            elapsed = time.perf_counter() - start
            self.assertLess(elapsed, 1.0, "%.2f s" % elapsed)
            self.assertNotEqual(r.source, GENERATED)

    def test_every_title_matches_itself_or_needs_a_publisher(self):
        # Each multi-word title, as a row name with no publisher, finds its
        # own product (or nothing for generated_off); never another product.
        data = self.data
        index = data.matching_index()
        for pid, rec_ in sorted(data.catalog.items()):
            ids, _ = index.lookup(rec_["title"], "")
            self.assertIn(ids, ((pid,), ()), pid)
            if " " in normalize_name(rec_["title"]) and pid not in index.off \
                    and pid not in index.devices \
                    and not index._excluded({normalize_name(
                        rec_["title"])}, ()):
                self.assertEqual(ids, (pid,), pid)


class GuardedAliasTests(unittest.TestCase):
    """A failed publisher guard blocks that alias's product everywhere."""

    @classmethod
    def setUpClass(cls):
        import json
        manifest = json.loads((ROOT / "data" / "manifest.json").read_text(
            encoding="utf-8"))
        cls.data = load_data(str(ROOT / "data"),
                             date.fromisoformat(manifest["eol_date"]))

    def run_row(self, name, publisher, version):
        d = self.data
        return match_product(name, version, d.aliases, d.products,
                             catalog_index=d.matching_index(),
                             publisher=publisher)

    def test_failed_guard_gives_no_guarded_product(self):
        rows = (("Node.js", "nodejs", "1.0.1"),
                ("Node.js", "Node.js", "1.0.1"),
                ("Node.js", "nodejs", "0.12.0"),
                ("Node.js", "", "20.1.0"),
                ("Ubuntu", "Google Fonts", "22.04"),
                ("Ubuntu", "", "latest"),
                ("Ubuntu", "Ubuntu Font Team", "22.04"))
        for row in rows:
            with self.subTest(row=row):
                self.assertIsNone(self.run_row(*row).product)

    def test_passing_guard_still_matches(self):
        for pub in ("Node.js Foundation", "OpenJS Foundation"):
            r = self.run_row("Node.js", pub, "22.1.0")
            self.assertEqual(r.product, "nodejs", pub)
        self.assertEqual(self.run_row("Ubuntu", "Canonical", "24.04").product,
                         "ubuntu")

    def test_other_products_still_match_when_a_guard_fails(self):
        products = {"a": [{"cycle": "1"}], "b": [{"cycle": "1"}]}
        aliases = [{"key": "foo bar", "match": "exact", "product": "a",
                    "version_from": "version", "publisher": ["acme"]}]
        index = build_index(
            {"b": {"title": "Foo Bar", "vendors": [], "namespaces": []}}, {})
        r = match_product("foo bar", "1", aliases, products, catalog_index=index,
                          publisher="Other")
        self.assertEqual(r.product, "b")
        index_a = build_index(
            {"a": {"title": "Foo Bar", "vendors": [], "namespaces": []}}, {})
        r = match_product("foo bar", "1", aliases, products, catalog_index=index_a,
                          publisher="Other")
        self.assertIsNone(r.product)


if __name__ == "__main__":
    unittest.main()
