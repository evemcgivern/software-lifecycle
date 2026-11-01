"""Rows the matcher refused on purpose (issue #12): the review codes from
swlc/catalog_match.py ("Refusals for review") and swlc/matching.py
(match_noted).

The fixtures are the fictional products of tests/test_catalog_match.py.
Matching results never change: match_noted always returns the MatchResult
match_product gives.
"""
import copy
import json
import sys
import time
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swlc import assess as assess_mod  # noqa: E402
from swlc.assess import AMBIGUITY_REASONS, assess  # noqa: E402
from swlc.catalog_match import (  # noqa: E402
    SHARED_SUPPORT_LINES, TITLE_NEEDS_PUBLISHER, TITLE_NOT_ON_LIST,
    build_index)
from swlc.data import Data  # noqa: E402
from swlc.inputs import group_rows  # noqa: E402
from swlc.matching import NO_ALIAS, match_noted, match_product  # noqa: E402
from swlc.overrides import Exceptions, Golden  # noqa: E402
from test_catalog_match import (  # noqa: E402
    CATALOG, CURATION, CYCLES, INDEX, MAX_SECONDS_100K, PRODUCTS, alias,
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

    def test_publisher_that_does_not_confirm_has_no_code(self):
        # A publisher that does not confirm the product is often another
        # product: no code, so no one is invited to add an alias for it.
        self.assertIsNone(noted("Lexicon", "1.0", "Acme Corp"))
        # "Promo Group" is not exactly the one-word title vendor "promo".
        self.assertIsNone(noted("Promo", "3.5", "Promo Group"))
        # Same answer whether the version is in the name or the column.
        self.assertIsNone(noted("Lexicon 1.0", "", "Acme Corp"))

    def test_version_that_fits_no_cycle_has_no_code(self):
        for version in ("99.9", "banana", "9.9.9"):
            with self.subTest(version=version):
                self.assertIsNone(noted("Plainword", version))
                self.assertIsNone(noted("Lexicon", version))

    def test_empty_version_keeps_the_code(self):
        for version in ("", "  "):
            with self.subTest(version=version):
                self.assertEqual(noted("Plainword", version),
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


# --- the report: item key and count ----------------------------------------

AS_OF = date(2026, 10, 24)
COLMAP = {"name": "name", "version": "version", "publisher": "publisher",
          "owner": "owner", "parent": "parent"}
# (name, version, publisher, parent) -> expected ambiguity code
ROWS = {
    ("Plainword", "1", "", ""): TITLE_NEEDS_PUBLISHER,
    ("Lexicon 1.0", "", "", ""): TITLE_NOT_ON_LIST,
    ("Chatter", "9.3", "Chatter Inc.", ""): None,       # exclusion
    ("Tabby Tablet", "8", "", ""): None,                # device
    ("Lexicon 9.9", "", "", ""): None,                  # no such cycle
    ("Foo Tool", "2.1.4", "", ""): None,                # matched, past EOL
    ("Plainword", "1.0", "", "Foo Tool"): None,         # a bundle part
    ("Lexicon", "1.0", "Acme", ""): None,               # has a publisher
    ("Lexicon", "99.9", "", ""): None,                  # version fits none
    ("Nothing", "1", "", ""): None,                     # no title hit
}


def report_data():
    """Every fixture product, every cycle past end of life."""
    products = {pid: [{"cycle": c, "eol": date(2020, 1, 1),
                       "support": False, "extended": None}
                      for c in labels] for pid, labels in CYCLES.items()}
    return Data(release_id="r", file_hashes={}, aliases=[],
                products=products, kev=[], kev_catalog_version="1",
                kev_age_days=1, eol_age_days=1,
                catalog=copy.deepcopy(CATALOG),
                curation=copy.deepcopy(CURATION))


def run_rows(rows=ROWS, data=None):
    dicts = [{"name": n, "version": v, "publisher": p, "owner": "ops",
              "parent": parent} for n, v, p, parent in rows]
    return assess(group_rows(dicts, COLMAP), data or report_data(),
                  Golden(), Exceptions(), {}, AS_OF)


def by_row(out):
    return {(it["name"], it["version"], it["publisher"]): it
            for it in out["items"]}


class ReportKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = run_rows()
        cls.items = by_row(cls.out)

    def test_key_on_every_item(self):
        self.assertEqual(len(self.out["items"]), len(ROWS))
        for it in self.out["items"]:
            self.assertIn("ambiguity", it)

    def test_codes_per_row(self):
        for (name, version, pub, _parent), code in ROWS.items():
            with self.subTest(name=name, pub=pub):
                got = self.items[(name, version, pub)]["ambiguity"]
                if code is None:
                    self.assertIsNone(got)
                else:
                    self.assertEqual(got, {"code": code,
                                           "reason": AMBIGUITY_REASONS[code]})

    def test_part_is_never_ambiguous(self):
        part = self.items[("Plainword", "1.0", "")]
        self.assertEqual(part["classification"], "bundle_member")
        self.assertIsNone(part["ambiguity"])
        # The same row with no parent is reviewed.
        alone = by_row(run_rows([("Plainword", "1.0", "", "")]))
        self.assertEqual(alone[("Plainword", "1.0", "")]["ambiguity"][
            "code"], TITLE_NEEDS_PUBLISHER)

    def test_ambiguous_items_claim_nothing(self):
        for it in self.out["items"]:
            if not it["ambiguity"]:
                continue
            self.assertIn(it["classification"], ("unknown", "governable"))
            self.assertEqual(it["state"], "unmatched")
            self.assertEqual(it["reason"], NO_ALIAS)
            for key in ("product", "cycle", "match_source", "eol_used",
                        "eol_endoflife", "support", "extended_support",
                        "state_endoflife", "kev"):
                self.assertIsNone(it[key], key)

    def test_each_code_string_has_its_own_reason(self):
        # Pinned literals: swapping the code strings or the texts fails.
        self.assertEqual(TITLE_NEEDS_PUBLISHER, "title_needs_publisher")
        self.assertEqual(TITLE_NOT_ON_LIST, "title_not_on_list")
        self.assertEqual(SHARED_SUPPORT_LINES, "shared_support_lines")
        self.assertEqual(AMBIGUITY_REASONS, {
            "title_needs_publisher": (
                "The name is a product title, but the row has no publisher "
                "to confirm the product."),
            "title_not_on_list": (
                "The name is a product title and a version, but that title "
                "is not on the reviewed list for rows with no publisher."),
            "shared_support_lines": (
                "The name and version fit more than one support line "
                "(desktop, Server, LTSB or LTSC); the row does not say "
                "which Windows it runs on."),
        })
        for text in AMBIGUITY_REASONS.values():
            for claim in ("cycle", "date", "end of life", "supported"):
                self.assertNotIn(claim, text.lower())

    def test_reason_is_fixed_text(self):
        for code, text in AMBIGUITY_REASONS.items():
            self.assertNotIn("\n", text)
            for name, _v, _p, _parent in ROWS:
                self.assertNotIn(name, text)
        self.assertEqual(set(AMBIGUITY_REASONS),
                         {TITLE_NEEDS_PUBLISHER, TITLE_NOT_ON_LIST,
                          SHARED_SUPPORT_LINES})

    def test_count_and_breakdown(self):
        counts = self.out["counts"]
        self.assertEqual(counts["ambiguous_review"], 2)
        self.assertEqual(sum(counts["unmatched_breakdown"].values()),
                         counts["lists"]["unmatched"])
        ambiguous = {it["id"] for it in self.out["items"]
                     if it["ambiguity"]}
        self.assertLessEqual(ambiguous, set(self.out["lists"]["unmatched"]))

    def test_never_on_a_finding_list(self):
        ambiguous = {it["id"] for it in self.out["items"]
                     if it["ambiguity"]}
        self.assertTrue(self.out["lists"]["past_eol"])
        for name, ids in self.out["lists"].items():
            if name in ("unmatched", "ownerless"):
                continue
            with self.subTest(name=name):
                self.assertFalse(ambiguous & set(ids))
        self.assertEqual(set(self.out["lists"]), set(assess_mod.LISTS))

    def test_no_new_state_list_or_schema(self):
        self.assertEqual(self.out["schema_version"], 2)
        self.assertEqual(set(self.out["counts"]["states"]),
                         set(assess_mod.STATES))


class GoldUnchangedTests(unittest.TestCase):
    """The whole gold benchmark gives the same items with the review hook
    as with the hook ignored (match_product), apart from the new key."""

    def test_gold_items_unchanged(self):
        import test_benchmark
        rows = test_benchmark.read_gold()
        noted = test_benchmark.results()
        original = assess_mod.match_noted

        def ignored(*args, **kwargs):
            return match_product(*args, **kwargs), None

        assess_mod.match_noted = ignored
        try:
            plain = test_benchmark.run_gold(rows)
        finally:
            assess_mod.match_noted = original
        self.assertEqual(len(noted), len(plain))
        flagged = 0
        for (_r, res_a, a), (_r2, res_b, b) in zip(noted, plain):
            self.assertEqual(res_a, res_b)
            self.assertIsNone(b["ambiguity"])
            flagged += bool(a["ambiguity"])
            if a["ambiguity"]:
                self.assertEqual(a["state"], "unmatched")
                self.assertIsNone(a["cycle"])
                if a["ambiguity"]["code"] == SHARED_SUPPORT_LINES:
                    self.assertEqual(a["product"], "internet-explorer")
                else:
                    self.assertIsNone(a["product"])
            a, b = dict(a), dict(b)
            a.pop("ambiguity")
            b.pop("ambiguity")
            self.assertEqual(a, b, a["name"])
        self.assertGreater(flagged, 0)


# --- the views: report.md, report.csv, --counts-only, --fail-on ------------

# Bundled data: Redmine with no publisher, and Caddy and Bun (titles not on
# the version-in-name list) with a version in the name.
VIEW_ROWS = (
    ("Redmine", "", "5.1.2"),         # title_needs_publisher
    ("Caddy 2.7.6", "", ""),          # title_not_on_list
    ("Bun 1.1.0", "", ""),            # title_not_on_list
    ("Synthetic Thing", "", "1.0"),   # no title hit
)
VIEW_DATE = "2026-10-24"


class ViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import csv
        import io
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from swlc import cli
        cls.cli = cli
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        cls.inv = tmp / "inventory.csv"
        with open(cls.inv, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Software Name", "Publisher", "Version",
                             "Owner"])
            for name, pub, ver in VIEW_ROWS:
                writer.writerow([name, pub, ver, "ops"])

        def run(*flags, out="out"):
            buf, err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                code = cli.main(["check", str(cls.inv), "--as-of", VIEW_DATE,
                                 "--out", str(tmp / out), *flags])
            return code, buf.getvalue(), tmp / out

        cls.check = staticmethod(run)
        _code, _text, out = run()
        cls.report = json.loads((out / "report.json").read_text("utf-8"))
        cls.md = (out / "report.md").read_text("utf-8")
        cls.csv = list(csv.DictReader(io.StringIO(
            (out / "report.csv").read_text("utf-8"))))
        cls.amb = [it for it in cls.report["items"] if it["ambiguity"]]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def section(self, md, heading):
        start = md.index("\n## %s (" % heading)
        end = md.index("\n## ", start + 1)
        return md[start:end]

    def test_bundled_rows_get_the_codes(self):
        codes = {it["name"]: (it["ambiguity"] or {}).get("code")
                 for it in self.report["items"]}
        self.assertEqual(codes, {
            "Redmine": TITLE_NEEDS_PUBLISHER, "Caddy 2.7.6": TITLE_NOT_ON_LIST,
            "Bun 1.1.0": TITLE_NOT_ON_LIST, "Synthetic Thing": None})
        self.assertEqual(self.report["counts"]["ambiguous_review"], 3)

    def test_markdown_section_lists_them_without_claims(self):
        sec = self.section(self.md, "Names to review")
        self.assertIn("## Names to review (3)", sec)
        self.assertIn("not a finding", sec)
        for it in self.amb:
            self.assertIn("(id `%s`)" % it["id"], sec)
            self.assertIn("Review: " + it["ambiguity"]["reason"], sec)
        self.assertNotIn("Synthetic Thing", sec)
        for claim in ("State:", "End of life", "Mainstream support",
                      "Product matched", "past end of life", "redmine/",
                      "Classification:", VIEW_DATE):
            self.assertNotIn(claim, sec)

    def test_markdown_lead_gives_the_three_ways_to_settle(self):
        sec = self.section(self.md, "Names to review")
        self.assertIn("add a publisher that names the vendor, ask for a "
                      "curated alias, or record that it is a different "
                      "product", sec)

    def test_review_line_has_no_double_space_without_a_version(self):
        from swlc.report import _review_block
        it = {"id": "0123456789ab", "name": "Redmine", "version": "",
              "publisher": "", "ambiguity": {"code": TITLE_NEEDS_PUBLISHER,
                                             "reason": "r"}}
        self.assertEqual(_review_block(it)[0],
                         "- **Redmine** (id `0123456789ab`)")
        it["version"] = "5.1.2"
        self.assertEqual(_review_block(it)[0],
                         "- **Redmine** 5.1.2 (id `0123456789ab`)")

    def test_markdown_pointer_and_summary_count(self):
        unmatched = self.section(self.md, "Couldn't match")
        self.assertIn("Names to review: 3 of these were left unmatched on "
                      "purpose", unmatched)
        summary = [line for line in self.md.split("\n")
                   if line.startswith("Items: ")]
        self.assertEqual(len(summary), 1)
        self.assertIn("couldn't match 4;", summary[0])
        self.assertTrue(summary[0].endswith("names to review 3."))

    def test_findings_block_unchanged(self):
        block = self.md.split("```findings\n", 1)[1].split("```", 1)[0]
        types = {f["type"] for f in json.loads(block)}
        self.assertEqual(types, {"unmatched"})

    def test_csv_column(self):
        reasons = {row["name"]: row["Review reason"] for row in self.csv}
        self.assertEqual(reasons["Synthetic Thing"], "")
        for it in self.amb:
            self.assertEqual(reasons[it["name"]], it["ambiguity"]["reason"])
        self.assertEqual(list(self.csv[0])[-3:], [
            "Review reason", "Support records (from your file)",
            "Count (from your file)"])

    def test_counts_only_line_has_no_names(self):
        code, text, _out = self.check("--counts-only", out="counts")
        self.assertEqual(code, 0)
        lines = text.split("\n")
        self.assertIn("ambiguous_review 3", lines)
        at = lines.index("ambiguous_review 3")
        self.assertTrue(lines[at - 1].startswith("classification "))
        for name, pub, _ver in VIEW_ROWS:
            self.assertNotIn(name.split()[0], text)

    def test_governable_only_keeps_them(self):
        _code, _text, out = self.check("--governable-only", out="gov")
        md = (out / "report.md").read_text("utf-8")
        sec = self.section(md, "Names to review")
        csv_text = (out / "report.csv").read_text("utf-8")
        for it in self.amb:
            self.assertEqual(it["classification"], "unknown")
            self.assertIn("(id `%s`)" % it["id"], sec)
            self.assertIn(it["id"], csv_text)

    def test_fail_on_is_unaffected(self):
        code, _text, _out = self.check(
            "--fail-on", "past_eol,ends_soon,review_urgently,dates_disagree",
            out="fail1")
        self.assertEqual(code, 0)
        # They are still unmatched rows, so the unmatched list fires.
        code, _text, _out = self.check("--fail-on", "unmatched", out="fail2")
        self.assertEqual(code, self.cli.EXIT_FINDINGS)
        for name in ("past_eol", "ends_soon", "review_urgently",
                     "dates_disagree"):
            self.assertEqual(self.report["lists"][name], [])


# --- shared_support_lines (issue #21): bundled data, review_versions -------

IE_ROWS = (
    # (name, publisher, version, review code, cycle)
    ("Internet Explorer 11", "Microsoft Corporation", "11.0.9600.19596",
     SHARED_SUPPORT_LINES, None),
    ("Internet Explorer 11", "Microsoft Corporation", "11.0.14393.0",
     SHARED_SUPPORT_LINES, None),
    ("Internet Explorer", "Microsoft Corporation", "11.0.17763.0",
     SHARED_SUPPORT_LINES, None),
    ("Internet Explorer", "", "11.0.19041.1", SHARED_SUPPORT_LINES, None),
    ("Internet Explorer 11", "Microsoft Corporation", "",
     SHARED_SUPPORT_LINES, None),
    # The name says 11 and the version says 10: the name version counts.
    ("Internet Explorer 11", "Microsoft Corporation", "10.0.9200.16384",
     SHARED_SUPPORT_LINES, None),
    # A version that names its support line keeps that line's cycle.
    ("Internet Explorer", "Microsoft Corporation", "11-ltsc", None,
     "11-ltsc"),
    ("Internet Explorer", "Microsoft Corporation", "11-server", None,
     "11-server"),
    ("Internet Explorer 10", "Microsoft Corporation", "10.0.9200.16384",
     None, "10"),
    ("Internet Explorer 9", "Microsoft Corporation", "9.0.8112.16421",
     None, "9"),
)


class SharedSupportLinesTests(unittest.TestCase):
    """An Internet Explorer 11 row keeps its product, gets no cycle, date
    or state, and is listed under "Names to review"."""

    @classmethod
    def setUpClass(cls):
        import csv
        import io
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from swlc import cli
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        inv = tmp / "inventory.csv"
        with open(inv, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Software Name", "Publisher", "Version",
                             "Owner"])
            for name, pub, ver, _code, _cycle in IE_ROWS:
                writer.writerow([name, pub, ver, "ops"])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            cli.main(["check", str(inv), "--as-of", VIEW_DATE, "--out",
                      str(tmp / "out")])
        out = tmp / "out"
        cls.report = json.loads((out / "report.json").read_text("utf-8"))
        cls.md = (out / "report.md").read_text("utf-8")
        cls.csv = list(csv.DictReader(io.StringIO(
            (out / "report.csv").read_text("utf-8"))))
        cls.items = {(it["name"], it["publisher"], it["version"]): it
                     for it in cls.report["items"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_codes_and_cycles(self):
        for name, pub, ver, code, cycle in IE_ROWS:
            with self.subTest(name=name, ver=ver):
                it = self.items[(name, pub, ver)]
                self.assertEqual(it["product"], "internet-explorer")
                self.assertEqual(it["cycle"], cycle)
                self.assertEqual((it["ambiguity"] or {}).get("code"), code)
        self.assertEqual(self.report["counts"]["ambiguous_review"], 6)
        self.assertEqual(self.report["schema_version"], 2)

    def test_no_date_or_state_from_cycle_11(self):
        for it in self.report["items"]:
            if not it["ambiguity"]:
                continue
            self.assertEqual(it["state"], "unmatched")
            self.assertIn(it["id"], self.report["lists"]["unmatched"])
            self.assertNotIn(it["id"], self.report["lists"]["past_eol"])
            for key in ("cycle", "eol_used", "eol_endoflife", "support",
                        "extended_support", "state_endoflife", "kev"):
                self.assertIsNone(it[key], key)
            self.assertNotEqual(it["eol_used"], "2022-06-14")

    def test_markdown_lists_the_product_and_the_reason(self):
        start = self.md.index("\n## Names to review (")
        sec = self.md[start:self.md.index("\n## ", start + 1)]
        self.assertIn("## Names to review (6)", sec)
        self.assertIn("  - Product: internet-explorer (no cycle)", sec)
        self.assertIn("Review: " + AMBIGUITY_REASONS[SHARED_SUPPORT_LINES],
                      sec)
        for claim in ("2022-06-14", "State:", "past end of life"):
            self.assertNotIn(claim, sec)

    def test_named_lines_never_carry_the_review_text(self):
        from swlc.report import REVIEW_COLUMN
        text = AMBIGUITY_REASONS[SHARED_SUPPORT_LINES]
        for ver in ("11-ltsc", "11-server"):
            with self.subTest(ver=ver):
                it = self.items[("Internet Explorer", "Microsoft Corporation",
                                 ver)]
                self.assertIsNone(it["ambiguity"])
                self.assertEqual(it["eol_endoflife"], "2031-10-14")
                self.assertNotIn(it["id"], self.md.split(
                    "\n## Names to review (", 1)[1].split("\n## ", 1)[0])
                rows = [r for r in self.csv if r["version"] == ver]
                self.assertEqual(len(rows), 1)
                self.assertNotEqual(rows[0][REVIEW_COLUMN], text)
                self.assertEqual(rows[0]["cycle"], ver)

    def test_golden_source_is_not_applied_and_a_warning_says_so(self):
        from swlc.data import load_data
        data = load_data(str(ROOT / "data"), date.fromisoformat(VIEW_DATE))
        golden = Golden({"internet-explorer": {
            "product": "internet-explorer", "source": "manual",
            "manual_eol": date(2031, 10, 14), "reason": "r",
            "set_by": "lead", "set_on": date(2026, 1, 1),
            "review_by": date(2027, 1, 1)}})
        rows = [{"name": n, "version": v, "publisher": p, "owner": "ops",
                 "parent": ""}
                for n, p, v in (("Internet Explorer 11",
                                 "Microsoft Corporation", "11.0.9600.19596"),
                                ("Internet Explorer", "Microsoft Corporation",
                                 "11-server"))]
        out = assess(group_rows(rows, COLMAP), data, golden, Exceptions(),
                     {}, date.fromisoformat(VIEW_DATE))
        items = {it["version"]: it for it in out["items"]}
        flagged = items["11.0.9600.19596"]
        self.assertEqual(flagged["ambiguity"]["code"], SHARED_SUPPORT_LINES)
        self.assertIsNone(flagged["golden_applied"])
        self.assertIsNone(flagged["eol_used"])
        self.assertNotIn(flagged["id"], out["lists"]["golden_overrides"])
        self.assertIn(assess_mod.GOLDEN_NOT_APPLIED % 1, out["warnings"])
        # The row that names its line still takes the golden source.
        self.assertEqual(items["11-server"]["golden_applied"], "manual")
        # No golden row, no warning.
        out = assess(group_rows(rows, COLMAP), data, Golden(), Exceptions(),
                     {}, date.fromisoformat(VIEW_DATE))
        self.assertFalse(any("golden-source row" in w
                             for w in out["warnings"]))

    def test_golden_warning_is_whole_in_report_md(self):
        import io
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from swlc import cli
        from swlc.report import MAX_DISPLAY
        self.assertLessEqual(len(assess_mod.GOLDEN_NOT_APPLIED % 999999),
                             MAX_DISPLAY)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            inv = tmp / "inventory.csv"
            inv.write_text("Software Name,Publisher,Version,Owner\n"
                           "Internet Explorer 11,Microsoft Corporation,"
                           "11.0.9600.19596,ops\n", encoding="utf-8")
            gold = tmp / "golden.csv"
            gold.write_text(
                "schema_version,product,source,manual_eol,reason,set_by,"
                "set_on,review_by\n1,internet-explorer,manual,2031-10-14,"
                "Server line,lead,2026-01-01,2027-01-01\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()), \
                    redirect_stderr(io.StringIO()):
                cli.main(["check", str(inv), "--as-of", VIEW_DATE,
                          "--golden", str(gold), "--out", str(tmp / "out")])
            md = (tmp / "out" / "report.md").read_text("utf-8")
        lines = [line for line in md.split("\n")
                 if line.startswith("Warning: 1 item")]
        self.assertEqual(len(lines), 1, md)
        self.assertTrue(lines[0].endswith(
            "not applied: no cycle, see Names to review."), lines[0])
        self.assertNotIn("...", lines[0])

    def test_csv_review_column(self):
        from swlc.report import REVIEW_COLUMN
        reasons = [row[REVIEW_COLUMN] for row in self.csv
                   if row[REVIEW_COLUMN]]
        self.assertEqual(reasons,
                         [AMBIGUITY_REASONS[SHARED_SUPPORT_LINES]] * 6)



if __name__ == "__main__":
    unittest.main()
