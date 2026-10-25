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
    build_index, split_tail, strip_arch, tokens)
from swlc.data import Data, load_data  # noqa: E402
from swlc.inputs import group_rows  # noqa: E402
from swlc.matching import (  # noqa: E402
    AMBIGUOUS, CURATED, GENERATED, NO_ALIAS, NO_CYCLE, NO_VERSION,
    MatchResult, match_product)
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
)}
CURATION = {
    "format": 1,
    "publisher_aliases": {"jsrun": ["openjs foundation"]},
    "single_word_allowlist": [
        {"product": "listed", "reason": "unambiguous in exports",
         "source": "https://example.com/listed"}],
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
    "widget-pro": ["1"], "dbms": ["7"],
}
PRODUCTS = {p: [{"cycle": c} for c in labels] for p, labels in CYCLES.items()}
INDEX = build_index(CATALOG, CURATION)


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
        # Another publisher that still confirms is not excluded... none here:
        # the only confirming phrase is the excluded one, so test the name.
        self.assertEqual(gen("Chatter 9.3", "", "Chatter").product,
                         "chatter")

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
        self.assertEqual(r.product, "foo-tool")

    def test_exclusion_names_are_cleaned(self):
        self.assertIsNone(gen("Foo Tool Helper", "2.1").product)
        self.assertEqual(INDEX.exclusions[("foo tool helper", "foo-tool")],
                         ((),))

    def test_exclusions_never_silence_curated_aliases(self):
        a = [alias("chatter", "chatter")]
        self.assertEqual(got(gen("Chatter", "9.3.0", "Chatter", a)),
                         ("chatter", "9.3", None, CURATED))


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

MAX_SECONDS_100K = 20.0   # measured 3.4 s (3.15) and 4.4 s (3.9) here


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
        start = time.perf_counter()
        n = 0
        for name, ver, pub in synthetic_rows(data.catalog, 100000):
            match_product(name, ver, data.aliases, data.products,
                          catalog_index=index, publisher=pub)
            n += 1
        elapsed = time.perf_counter() - start
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

    def test_every_title_matches_itself_or_needs_a_publisher(self):
        # Each multi-word title, as a row name with no publisher, finds its
        # own product (or nothing for generated_off); never another product.
        data = self.data
        index = data.matching_index()
        for pid, rec_ in sorted(data.catalog.items()):
            ids, _ = index.lookup(rec_["title"], "")
            self.assertIn(ids, ((pid,), ()), pid)
            if " " in normalize_name(rec_["title"]) and pid not in index.off:
                self.assertEqual(ids, (pid,), pid)


if __name__ == "__main__":
    unittest.main()
