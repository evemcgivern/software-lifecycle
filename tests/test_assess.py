import builtins
import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import make_data_dir
from swlc.assess import add_months, assess
from swlc.data import Data, load_data
from swlc.errors import InputError
from swlc.inputs import group_rows
from swlc.overrides import Exceptions, Golden

AS_OF = date(2026, 10, 24)
COLMAP = {"name": "name", "version": "version", "publisher": "publisher",
          "owner": "owner", "export_eol": "export_eol"}

# Synthetic product "alpha"; each cycle plants one case.
ALPHA = [
    {"cycle": "1", "eol": date(2026, 1, 15), "support": date(2025, 1, 15),
     "extended": None},
    {"cycle": "2", "eol": date(2027, 9, 24), "support": None,
     "extended": None},                                   # 11 months
    {"cycle": "3", "eol": date(2027, 11, 24), "support": None,
     "extended": None},                                   # 13 months
    {"cycle": "4", "eol": True, "support": False, "extended": None},
    {"cycle": "5", "eol": False, "support": True, "extended": None},
    {"cycle": "6", "eol": False, "support": date(2026, 1, 1),
     "extended": date(2029, 1, 1)},
    {"cycle": "7", "eol": date(2026, 10, 24), "support": None,
     "extended": None},                                   # == as_of
    {"cycle": "8", "eol": date(2027, 10, 24), "support": None,
     "extended": None},                                   # exactly 12 months
    {"cycle": "9", "eol": date(2027, 10, 25), "support": None,
     "extended": None},                                   # 12 months + 1 day
    {"cycle": "10", "eol": None, "support": None, "extended": None},
    # endoflife.date's live shape: support true = ongoing, false = ended.
    {"cycle": "11", "eol": False, "support": True, "extended": None},
    {"cycle": "12", "eol": date(2030, 1, 1), "support": False,
     "extended": None},
]
ALIASES = [{"key": "alpha app", "match": "exact", "product": "alpha",
            "version_from": "version"}]
KEV = [{"vendor": "alpha corp", "product": "alpha app",
        "date_added": date(2026, 9, 1), "cve": "CVE-2099-0002"}]
KEV_PUB = "Alpha Corp"  # rows default to another publisher, off KEV


def make_data(kev_current=True, warnings=None):
    return Data(release_id="data-2026.10.24.1",
                file_hashes={"kev.json": "b" * 64, "aliases.json": "a" * 64},
                aliases=copy.deepcopy(ALIASES),
                products={"alpha": copy.deepcopy(ALPHA)},
                kev=copy.deepcopy(KEV), kev_catalog_version="2026.10.22",
                kev_age_days=2, eol_age_days=4, kev_current=kev_current,
                warnings=list(warnings or []))


def row(version, name="Alpha App", publisher="Other Corp", owner="ops",
        export_eol=""):
    return {"name": name, "version": version, "publisher": publisher,
            "owner": owner, "export_eol": export_eol}


def golden_row(source, review_by=date(2027, 1, 1), manual=None,
               product="alpha"):
    return {"product": product, "source": source, "manual_eol": manual,
            "reason": "r", "set_by": "itam lead", "set_on": date(2026, 1, 1),
            "review_by": review_by}


def exception_row(expires_on, scope="", product="alpha"):
    return {"product": product, "scope": scope,
            "compensating_controls": "isolated", "risk_owner": "risk",
            "approver": "approver", "requested_by": "owner",
            "expires_on": expires_on, "reference": "RISK-1"}


def run(rows, golden=None, exceptions=None, tracking=None, previous=None,
        data=None, as_of=AS_OF, lookahead_months=12):
    return assess(group_rows(rows, COLMAP), data or make_data(),
                  golden or Golden(), exceptions or Exceptions(),
                  tracking or {}, as_of, lookahead_months=lookahead_months,
                  previous=previous)


def only(out):
    assert len(out["items"]) == 1, out["items"]
    return out["items"][0]


def on(out, item):
    return sorted(k for k, ids in out["lists"].items() if item["id"] in ids)


class MonthMath(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(add_months(date(2026, 10, 24), 12),
                         date(2027, 10, 24))

    def test_clamps_day(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2027, 8, 31), 6), date(2028, 2, 29))
        self.assertEqual(add_months(date(2026, 3, 31), -1), date(2026, 2, 28))

    def test_year_rollover(self):
        self.assertEqual(add_months(date(2026, 11, 15), 3), date(2027, 2, 15))


class States(unittest.TestCase):
    def test_eol_before_as_of_is_past(self):
        it = only(run([row("1")]))
        self.assertEqual(it["state"], "past_eol")
        self.assertEqual(it["eol_used"], "2026-01-15")
        self.assertEqual(it["eol_source"], "endoflife.date")
        self.assertIsNone(it["reason"])

    def test_eol_on_as_of_is_past(self):
        self.assertEqual(only(run([row("7")]))["state"], "past_eol")

    def test_eleven_months_ends_soon(self):
        out = run([row("2")])
        it = only(out)
        self.assertEqual(it["state"], "ends_soon")
        self.assertEqual(on(out, it), ["ends_soon"])

    def test_exactly_twelve_months_is_in_window(self):
        self.assertEqual(only(run([row("8")]))["state"], "ends_soon")

    def test_day_after_window_is_out(self):
        self.assertEqual(only(run([row("9")]))["state"], "supported")

    def test_thirteen_months_not_ends_soon(self):
        out = run([row("3")])
        self.assertEqual(only(out)["state"], "supported")
        self.assertEqual(out["lists"]["ends_soon"], [])

    def test_shorter_lookahead(self):
        out = run([row("2")], lookahead_months=6)
        self.assertEqual(only(out)["state"], "supported")
        self.assertEqual(out["lookahead_months"], 6)

    def test_zero_lookahead_has_no_window(self):
        self.assertEqual(only(run([row("2")], lookahead_months=0))["state"],
                         "supported")

    def test_bad_lookahead_raises(self):
        for bad in (-1, True, 1.5, "12", 601, 10 ** 9):
            with self.assertRaises(InputError):
                run([row("1")], lookahead_months=bad)

    def test_largest_lookahead_allowed(self):
        self.assertEqual(only(run([row("3")], lookahead_months=600))["state"],
                         "ends_soon")

    def test_eol_true_is_past_with_no_date(self):
        it = only(run([row("4")]))
        self.assertEqual(it["state"], "past_eol")
        self.assertIs(it["eol_used"], True)
        self.assertIs(it["eol_endoflife"], True)

    def test_eol_false_supported(self):
        it = only(run([row("5")]))
        self.assertEqual(it["state"], "supported")
        self.assertIs(it["eol_used"], False)

    def test_support_passed_is_mainstream_ended(self):
        it = only(run([row("6")]))
        self.assertEqual(it["state"], "mainstream_ended")
        self.assertEqual(it["support"], "2026-01-01")
        self.assertEqual(it["extended_support"], "2029-01-01")

    def test_past_eol_wins_over_support(self):
        self.assertEqual(only(run([row("1")]))["state"], "past_eol")

    def test_live_shape_support_true_is_supported(self):
        it = only(run([row("11")]))
        self.assertEqual(it["state"], "supported")
        self.assertIs(it["support"], True)

    def test_live_shape_support_false_is_mainstream_ended(self):
        it = only(run([row("12")]))
        self.assertEqual(it["state"], "mainstream_ended")
        self.assertIs(it["support"], False)

    def test_no_eol_field_is_supported(self):
        it = only(run([row("10")]))
        self.assertEqual(it["state"], "supported")
        self.assertIsNone(it["eol_used"])


class Unmatched(unittest.TestCase):
    def test_reason_codes(self):
        out = run([row("1", name="Nope Suite"), row("", owner="a"),
                   row("99", owner="b")])
        by = {it["version"] + "|" + it["name"]: it for it in out["items"]}
        self.assertEqual(by["1|Nope Suite"]["reason"], "NO_ALIAS")
        self.assertEqual(by["|Alpha App"]["reason"], "NO_VERSION")
        self.assertEqual(by["99|Alpha App"]["reason"], "NO_CYCLE")
        for it in out["items"]:
            self.assertEqual(it["state"], "unmatched")
            self.assertIsNone(it["eol_used"])
            self.assertIn(it["id"], out["lists"]["unmatched"])
        self.assertEqual(out["lists"]["past_eol"], [])

    def test_unmatched_ignores_golden(self):
        g = Golden({"nope suite": golden_row("manual",
                                             manual=date(2020, 1, 1),
                                             product="nope suite")})
        it = only(run([row("1", name="Nope Suite")], golden=g))
        self.assertEqual(it["state"], "unmatched")
        self.assertIsNone(it["golden_applied"])


class DatesDisagree(unittest.TestCase):
    def test_different_dates_disagree_and_use_endoflife(self):
        out = run([row("2", export_eol="2030-01-01")])
        it = only(out)
        self.assertEqual(on(out, it), ["dates_disagree", "ends_soon"])
        self.assertEqual(it["dates_disagree"], "DIFFERENT_DATE")
        self.assertEqual(it["eol_used"], "2027-09-24")
        self.assertEqual(it["eol_export"], "2030-01-01")
        self.assertEqual(it["eol_source"], "endoflife.date")

    def test_same_date_with_time_agrees(self):
        out = run([row("1", export_eol="2026-01-15 00:00:00")])
        self.assertEqual(out["lists"]["dates_disagree"], [])
        self.assertEqual(only(out)["eol_export"], "2026-01-15")

    def test_unreadable_export_date_is_decision_needed(self):
        out = run([row("1", export_eol="15/01/2026")])
        it = only(out)
        self.assertEqual(it["dates_disagree"], "EXPORT_DATE_UNREADABLE")
        self.assertIn("EXPORT_DATE_UNREADABLE", it["decision_needed"])
        self.assertIsNone(it["eol_export"])
        self.assertEqual(it["eol_export_raw"], "15/01/2026")
        self.assertEqual(it["eol_used"], "2026-01-15")

    def test_impossible_date_is_unreadable(self):
        it = only(run([row("1", export_eol="2026-02-30")]))
        self.assertEqual(it["dates_disagree"], "EXPORT_DATE_UNREADABLE")

    def test_export_date_but_no_endoflife_date(self):
        for version in ("5", "4", "10"):
            it = only(run([row(version, export_eol="2027-01-01")]))
            self.assertEqual(it["dates_disagree"], "NO_ENDOFLIFE_DATE",
                             version)

    def test_missing_endoflife_date_with_export_is_decision_needed(self):
        it = only(run([row("10", export_eol="2027-01-01")]))
        self.assertEqual(it["state"], "supported")
        self.assertIn("NO_ENDOFLIFE_DATE", it["decision_needed"])
        it = only(run([row("5", export_eol="2027-01-01")]))
        self.assertEqual(it["decision_needed"], [])

    def test_no_export_date_no_disagreement(self):
        it = only(run([row("1")]))
        self.assertIsNone(it["dates_disagree"])
        self.assertIsNone(it["eol_export"])


class GoldenSource(unittest.TestCase):
    def test_active_export_golden_decides_and_is_not_disagree(self):
        g = Golden({"alpha": golden_row("export")})
        out = run([row("1", export_eol="2027-09-01")], golden=g)
        it = only(out)
        self.assertEqual(it["eol_used"], "2027-09-01")
        self.assertEqual(it["eol_source"], "export")
        self.assertEqual(it["golden_applied"], "export")
        self.assertEqual(it["eol_endoflife"], "2026-01-15")
        self.assertEqual(it["state"], "ends_soon")
        self.assertEqual(it["state_endoflife"], "past_eol")
        self.assertEqual(on(out, it), ["ends_soon", "golden_overrides"])
        self.assertFalse(it["accepted_risk"])

    def test_active_manual_golden(self):
        g = Golden({"alpha": golden_row("manual", manual=date(2026, 3, 1))})
        it = only(run([row("3")], golden=g))
        self.assertEqual(it["eol_used"], "2026-03-01")
        self.assertEqual(it["eol_source"], "manual")
        self.assertEqual(it["state"], "past_eol")

    def test_active_endoflife_golden_keeps_past_eol(self):
        g = Golden({"alpha": golden_row("endoflife.date")})
        out = run([row("1", export_eol="2030-01-01")], golden=g)
        it = only(out)
        self.assertEqual(on(out, it), ["past_eol"])
        self.assertEqual(it["eol_source"], "endoflife.date")
        self.assertFalse(it["accepted_risk"])

    def test_golden_by_normalized_name(self):
        g = Golden({"alpha app": golden_row("manual", manual=date(2026, 3, 1),
                                            product="alpha app")})
        self.assertEqual(only(run([row("3")], golden=g))["eol_source"],
                         "manual")

    def test_golden_export_without_usable_date(self):
        g = Golden({"alpha": golden_row("export")})
        for export in ("", "garbage"):
            out = run([row("1", export_eol=export)], golden=g)
            it = only(out)
            self.assertEqual(it["eol_used"], "2026-01-15")
            self.assertEqual(it["eol_source"], "endoflife.date")
            self.assertIsNone(it["golden_applied"])
            self.assertEqual(it["dates_disagree"], "GOLDEN_EXPORT_UNUSABLE")
            self.assertIn("GOLDEN_EXPORT_UNUSABLE", it["decision_needed"])
            self.assertIn(it["id"], out["lists"]["past_eol"])

    def test_expired_golden_back_on_dates_disagree(self):
        g = Golden({"alpha": golden_row("export",
                                        review_by=date(2026, 10, 23))})
        out = run([row("1", export_eol="2027-09-01")], golden=g)
        it = only(out)
        self.assertTrue(it["golden_expired"])
        self.assertIsNone(it["golden_applied"])
        self.assertEqual(it["dates_disagree"], "GOLDEN_EXPIRED")
        self.assertIn("GOLDEN_EXPIRED", it["decision_needed"])
        self.assertEqual(it["eol_used"], "2026-01-15")
        self.assertEqual(on(out, it), ["dates_disagree", "past_eol"])

    def test_expired_golden_even_when_dates_agree(self):
        g = Golden({"alpha": golden_row("endoflife.date",
                                        review_by=date(2026, 1, 1))})
        it = only(run([row("1")], golden=g))
        self.assertEqual(it["dates_disagree"], "GOLDEN_EXPIRED")

    def test_review_by_today_still_active(self):
        g = Golden({"alpha": golden_row("export", review_by=AS_OF)})
        it = only(run([row("1", export_eol="2027-09-01")], golden=g))
        self.assertEqual(it["golden_applied"], "export")


class GoldenOverrides(unittest.TestCase):
    def test_golden_changing_state_is_listed(self):
        g = Golden({"alpha": golden_row("export")})
        out = run([row("1", export_eol="2030-01-01")], golden=g)
        it = only(out)
        self.assertEqual(it["state"], "mainstream_ended")  # support passed
        self.assertEqual(it["state_endoflife"], "past_eol")
        self.assertEqual(it["eol_endoflife"], "2026-01-15")
        self.assertEqual(it["eol_export"], "2030-01-01")
        self.assertEqual(out["lists"]["golden_overrides"], [it["id"]])
        self.assertEqual(out["counts"]["lists"]["golden_overrides"], 1)

    def test_without_golden_not_listed(self):
        out = run([row("1", export_eol="2030-01-01")])
        self.assertEqual(out["lists"]["golden_overrides"], [])
        self.assertEqual(only(out)["state_endoflife"], "past_eol")

    def test_unmatched_has_no_endoflife_state(self):
        out = run([row("1", name="Nope")])
        self.assertIsNone(only(out)["state_endoflife"])
        self.assertEqual(out["lists"]["golden_overrides"], [])


class ExportConflict(unittest.TestCase):
    ROWS = [row("1", export_eol="2030-01-01"),
            row("1", export_eol="2026-01-15"), row("1")]

    def test_conflict_is_decision_needed(self):
        out = run(self.ROWS)
        it = only(out)
        self.assertEqual(it["dates_disagree"], "EXPORT_DATES_CONFLICT")
        self.assertIn("EXPORT_DATES_CONFLICT", it["decision_needed"])
        self.assertIsNone(it["eol_export"])
        self.assertEqual(it["eol_used"], "2026-01-15")
        self.assertIn(it["id"], out["lists"]["dates_disagree"])

    def test_row_order_does_not_matter(self):
        g = Golden({"alpha": golden_row("export")})
        for golden in (None, g):
            self.assertEqual(run(self.ROWS, golden=golden),
                             run(list(reversed(self.ROWS)), golden=golden))

    def test_export_golden_refused(self):
        g = Golden({"alpha": golden_row("export")})
        it = only(run(self.ROWS, golden=g))
        self.assertIsNone(it["golden_applied"])
        self.assertEqual(it["eol_source"], "endoflife.date")
        self.assertEqual(it["eol_used"], "2026-01-15")
        self.assertEqual(it["dates_disagree"], "EXPORT_DATES_CONFLICT")

    def test_conflict_flagged_under_other_golden(self):
        g = Golden({"alpha": golden_row("manual", manual=date(2026, 3, 1))})
        it = only(run(self.ROWS, golden=g))
        self.assertEqual(it["golden_applied"], "manual")
        self.assertEqual(it["dates_disagree"], "EXPORT_DATES_CONFLICT")
        self.assertIn("EXPORT_DATES_CONFLICT", it["decision_needed"])

    def test_same_date_written_twice_is_not_a_conflict(self):
        it = only(run([row("1", export_eol="2026-01-15"),
                       row("1", export_eol="2026-01-15 00:00:00")]))
        self.assertIsNone(it["dates_disagree"])
        self.assertEqual(it["eol_export"], "2026-01-15")


class ExceptionsTests(unittest.TestCase):
    def test_active_exception_accepted_and_still_past(self):
        ex = Exceptions({("alpha", ""): exception_row(date(2027, 1, 1))})
        out = run([row("1")], exceptions=ex)
        it = only(out)
        self.assertTrue(it["accepted_risk"])
        self.assertEqual(on(out, it), ["accepted_risk", "past_eol"])

    def test_expires_on_today_is_active(self):
        ex = Exceptions({("alpha", ""): exception_row(AS_OF)})
        self.assertTrue(only(run([row("1")], exceptions=ex))["accepted_risk"])

    def test_expired_exception_is_decision_needed(self):
        ex = Exceptions({("alpha", ""): exception_row(date(2026, 10, 23))})
        out = run([row("1")], exceptions=ex)
        it = only(out)
        self.assertFalse(it["accepted_risk"])
        self.assertTrue(it["exception_expired"])
        self.assertIn("EXCEPTION_EXPIRED", it["decision_needed"])
        self.assertEqual(on(out, it), ["past_eol"])

    def test_scope_by_cycle(self):
        ex = Exceptions({("alpha", "1"): exception_row(date(2027, 1, 1),
                                                      scope="1")})
        out = run([row("1"), row("2")], exceptions=ex)
        by = {it["version"]: it for it in out["items"]}
        self.assertTrue(by["1"]["accepted_risk"])
        self.assertFalse(by["2"]["accepted_risk"])

    def test_scope_specific_wins_over_empty(self):
        ex = Exceptions({
            ("alpha", "1"): exception_row(date(2026, 1, 1), scope="1"),
            ("alpha", ""): exception_row(date(2027, 1, 1))})
        it = only(run([row("1")], exceptions=ex))
        self.assertFalse(it["accepted_risk"])
        self.assertTrue(it["exception_expired"])

    def test_exception_by_name_for_unmatched(self):
        ex = Exceptions({("nope suite", ""): exception_row(
            date(2027, 1, 1), product="nope suite")})
        out = run([row("1", name="Nope Suite")], exceptions=ex)
        it = only(out)
        self.assertTrue(it["accepted_risk"])
        self.assertEqual(on(out, it), ["accepted_risk", "unmatched"])


class Owners(unittest.TestCase):
    def test_no_owner_is_ownerless(self):
        out = run([row("1", owner=""), row("1", owner="")])
        it = only(out)
        self.assertEqual(it["owners"], [])
        self.assertIn(it["id"], out["lists"]["ownerless"])
        self.assertEqual(it["rows"], 2)

    def test_owners_unioned(self):
        out = run([row("1", owner="b team"), row("1", owner="a team"),
                   row("1", owner=""), row("1", owner="b team")])
        it = only(out)
        self.assertEqual(it["owners"], ["a team", "b team"])
        self.assertEqual(out["lists"]["ownerless"], [])


class Kev(unittest.TestCase):
    def test_overlay_only_for_past_or_ends_soon(self):
        out = run([row(v, owner=v, publisher=KEV_PUB)
                   for v in ("1", "2", "5", "6")])
        by = {it["version"]: it for it in out["items"]}
        self.assertTrue(by["1"]["kev"])
        self.assertTrue(by["2"]["kev"])
        self.assertIsNone(by["5"]["kev"])
        self.assertIsNone(by["6"]["kev"])
        self.assertEqual(out["lists"]["review_urgently"],
                         sorted([by["1"]["id"], by["2"]["id"]]))

    def test_publisher_must_match(self):
        out = run([row("1", publisher="Other Corp")])
        self.assertFalse(only(out)["kev"])
        self.assertEqual(out["lists"]["review_urgently"], [])

    def kev_alias_data(self, kev):
        data = make_data()
        data.aliases = [dict(ALIASES[0], kev=kev)]
        return data

    def test_alias_kev_pair_used(self):
        # Publisher and name would never match KEV exactly; the alias's
        # sourced pair does (normalized on both sides).
        data = self.kev_alias_data({"vendor": "ALPHA  Corp",
                                    "product": "Alpha App"})
        out = run([row("1", publisher="Somebody Else")], data=data)
        it = only(out)
        self.assertTrue(it["kev"])
        self.assertEqual(out["lists"]["review_urgently"], [it["id"]])

    def test_alias_kev_pair_wins_over_fallback(self):
        data = self.kev_alias_data({"vendor": "Nobody", "product": "Nothing"})
        it = only(run([row("1", publisher=KEV_PUB)], data=data))
        self.assertFalse(it["kev"])

    def test_unmatched_never_gets_overlay(self):
        out = run([row("99", publisher=KEV_PUB)])
        self.assertIsNone(only(out)["kev"])
        self.assertEqual(out["lists"]["review_urgently"], [])

    def test_kev_not_current_still_computed_and_flagged(self):
        out = run([row("1", publisher=KEV_PUB)],
                  data=make_data(kev_current=False))
        self.assertFalse(out["kev_current"])
        self.assertTrue(any("not current" in w for w in out["warnings"]))
        it = only(out)
        self.assertEqual(out["lists"]["review_urgently"], [it["id"]])
        self.assertTrue(it["kev_stale"])

    def test_kev_warning_not_doubled(self):
        w = "KEV snapshot is 9 days old; it is not current"
        out = run([row("1", publisher=KEV_PUB)],
                  data=make_data(kev_current=False, warnings=[w]))
        self.assertEqual(out["warnings"], [w])

    def test_kev_current_not_stale(self):
        out = run([row("1", publisher=KEV_PUB)])
        self.assertTrue(out["kev_current"])
        self.assertFalse(only(out)["kev_stale"])
        self.assertEqual(out["warnings"], [])


class Tracking(unittest.TestCase):
    def test_refs(self):
        groups = group_rows([row("1")], COLMAP)
        gid = next(iter(groups))
        out = run([row("1")], tracking={gid: {"change_ref": "CHG1",
                                              "problem_ref": ""}})
        it = only(out)
        self.assertEqual(it["change_ref"], "CHG1")
        self.assertIsNone(it["problem_ref"])


class Shape(unittest.TestCase):
    ROWS = [row("1"), row("2", owner=""), row("5"), row("1", name="Nope"),
            row("6", export_eol="2020-01-01")]

    def test_top_level(self):
        out = run(self.ROWS)
        self.assertEqual(sorted(out), sorted([
            "schema_version", "as_of", "lookahead_months", "data_release",
            "kev_current", "warnings", "items", "lists", "counts", "diff"]))
        self.assertEqual(out["schema_version"], 1)
        self.assertEqual(out["as_of"], "2026-10-24")
        self.assertEqual(out["data_release"]["id"], "data-2026.10.24.1")
        self.assertEqual(out["data_release"]["kev_catalog_version"],
                         "2026.10.22")
        self.assertEqual(sorted(out["lists"]), sorted([
            "past_eol", "ends_soon", "dates_disagree", "unmatched",
            "accepted_risk", "ownerless", "review_urgently",
            "golden_overrides"]))

    def test_sorted(self):
        out = run(self.ROWS)
        ids = [it["id"] for it in out["items"]]
        self.assertEqual(ids, sorted(ids))
        for ids in out["lists"].values():
            self.assertEqual(ids, sorted(ids))

    def test_counts(self):
        out = run(self.ROWS)
        c = out["counts"]
        self.assertEqual(c["items"], 5)
        self.assertEqual(c["rows"], 5)
        self.assertEqual(c["states"], {"supported": 1, "mainstream_ended": 1,
                                       "ends_soon": 1, "past_eol": 1,
                                       "unmatched": 1})
        self.assertEqual(c["lists"]["past_eol"], 1)
        self.assertEqual(c["lists"]["ownerless"], 1)
        self.assertEqual(c["lists"]["dates_disagree"], 1)
        self.assertEqual(c["lists"]["golden_overrides"], 0)

    def test_item_fields(self):
        it = run(self.ROWS)["items"][0]
        for key in ("id", "name", "version", "publisher", "owners", "state",
                    "reason", "eol_endoflife", "eol_export", "eol_used",
                    "eol_source", "support", "extended_support",
                    "golden_applied", "golden_expired", "accepted_risk", "kev",
                    "change_ref", "problem_ref"):
            self.assertIn(key, it)

    def test_deterministic_and_json_safe(self):
        a, b = run(self.ROWS), run(list(reversed(self.ROWS)))
        self.assertEqual(a, b)
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(run(self.ROWS), sort_keys=True))

    def test_inputs_not_mutated(self):
        data = make_data()
        groups = group_rows(self.ROWS, COLMAP)
        before = copy.deepcopy((groups, data.products, data.kev))
        assess(groups, data, Golden(), Exceptions(), {}, AS_OF)
        self.assertEqual(before, (groups, data.products, data.kev))

    def test_rejects_datetime_as_of(self):
        from datetime import datetime
        with self.assertRaises(ValueError):
            run([row("1")], as_of=datetime(2026, 10, 24, 12))


class Purity(unittest.TestCase):
    def test_no_open_or_print_while_running(self):
        def boom(*a, **k):
            raise AssertionError("assess must not do I/O")
        with mock.patch.object(builtins, "open", boom), \
                mock.patch.object(builtins, "print", boom), \
                mock.patch.object(builtins, "input", boom):
            out = run(Shape.ROWS, previous=run(Shape.ROWS))
        self.assertTrue(out["diff"]["available"])

    def test_source_has_no_clock_env_or_io(self):
        src = (Path(__file__).resolve().parents[1] / "swlc" /
               "assess.py").read_text(encoding="utf-8")
        for bad in ("open(", "print(", "today(", "now(", "import time",
                    "import os", "os.environ", "getenv", "sys.", "logging",
                    "Path("):
            self.assertNotIn(bad, src, bad)


class Diff(unittest.TestCase):
    def test_no_previous(self):
        d = run([row("1")])["diff"]
        self.assertEqual(d, {"available": False, "new": [], "resolved": [],
                             "changed_state": []})

    def test_against_previous(self):
        prev = run([row("1"), row("2", owner="x"), row("5", owner="y")])
        by = {it["version"]: it["id"] for it in prev["items"]}
        # "2" moved to past_eol by a later check date; "5" gone; "3" new.
        now = run([row("1"), row("2", owner="x"), row("3", owner="z")],
                  previous=prev, as_of=date(2027, 10, 1))
        new_id = [it["id"] for it in now["items"] if it["version"] == "3"]
        d = now["diff"]
        self.assertTrue(d["available"])
        self.assertEqual(d["new"], new_id)
        self.assertEqual(d["resolved"], [by["5"]])
        self.assertEqual(d["changed_state"], [
            {"id": by["2"], "from": "ends_soon", "to": "past_eol"}])

    def test_previous_through_json(self):
        prev = json.loads(json.dumps(run([row("1")])))
        d = run([row("1")], previous=prev)["diff"]
        self.assertEqual(d, {"available": True, "new": [], "resolved": [],
                             "changed_state": []})

    def test_unusable_previous(self):
        for bad in ({"schema_version": 2, "items": []}, {"items": "x"},
                    {"schema_version": True, "items": []},
                    {"schema_version": 1.0, "items": []},
                    {"schema_version": 1, "items": [{"no": "id"}]}, []):
            out = run([row("1")], previous=bad)
            self.assertFalse(out["diff"]["available"])
            self.assertTrue(any("previous" in w for w in out["warnings"]))


class WithFixtureData(unittest.TestCase):
    def test_loaded_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = load_data(make_data_dir(tmp, "2026-10-22", "2026-10-20"),
                             AS_OF)
        rows = [{"name": "Example SQL", "version": "15.0.2000",
                 "publisher": "Example Vendor", "owner": "dba",
                 "export_eol": ""},
                {"name": "Demo OS 2.0", "version": "", "publisher": "Demo",
                 "owner": "", "export_eol": ""}]
        out = assess(group_rows(rows, COLMAP), data, Golden(), Exceptions(),
                     {}, AS_OF)
        by = {it["name"]: it for it in out["items"]}
        sql = by["Example SQL"]
        self.assertEqual(sql["state"], "ends_soon")
        self.assertEqual(sql["eol_used"], "2026-12-31")
        self.assertEqual(sql["extended_support"], "2028-12-31")
        self.assertEqual(sql["product"], "examplesql")
        self.assertEqual(sql["cycle"], "15")
        self.assertEqual(out["lists"]["review_urgently"], [sql["id"]])
        self.assertEqual(by["Demo OS 2.0"]["state"], "supported")


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
FIXTURE_DATA = ROOT / "tests" / "fixtures" / "data"


def demo_and_parent_reports():
    from swlc import cli
    out = [cli.build(
        str(EXAMPLES / "software-inventory.csv"), as_of=AS_OF,
        data=str(FIXTURE_DATA),
        golden=str(EXAMPLES / "golden-sources.csv"),
        exceptions=str(EXAMPLES / "exceptions.csv"),
        tracking=str(EXAMPLES / "tracking.csv"))[0]]
    for path in sorted((ROOT / "tests" / "benchmark" / "parents").glob(
            "*.csv")):
        exp = json.loads(path.with_suffix(".expected.json").read_text())
        out.append(cli.build(str(path), as_of=date.fromisoformat(
            exp["as_of"]))[0])
    return out


class ClassCounts(unittest.TestCase):
    def test_breakdown_sums_to_unmatched(self):
        reports = demo_and_parent_reports()
        self.assertGreater(len(reports), 10)
        seen = set()
        for result in reports:
            counts = result["counts"]
            parts = counts["unmatched_breakdown"]
            self.assertEqual(set(parts), {"needs_review", "parts_with_parent",
                                          "parts_parent_absent"})
            self.assertEqual(sum(parts.values()), counts["lists"]["unmatched"])
            seen.update(k for k, v in parts.items() if v)
        self.assertEqual(seen, {"needs_review", "parts_with_parent",
                                "parts_parent_absent"})

    def test_breakdown_rules(self):
        result = demo_and_parent_reports()[0]
        by_id = {it["id"]: it for it in result["items"]}
        want = {"needs_review": 0, "parts_with_parent": 0,
                "parts_parent_absent": 0}
        for gid in result["lists"]["unmatched"]:
            it = by_id[gid]
            if it["classification"] in ("unknown", "governable"):
                want["needs_review"] += 1
            elif it["classification"] == "bundle_member" \
                    and it["inherited_from"]:
                want["parts_with_parent"] += 1
            else:
                want["parts_parent_absent"] += 1
        self.assertEqual(result["counts"]["unmatched_breakdown"], want)
        self.assertEqual(sum(1 for v in want.values() if v), 3)

    def test_classification_counts(self):
        for result in demo_and_parent_reports():
            counts = result["counts"]["classification"]
            self.assertEqual(list(counts), ["governable", "component",
                                            "bundle_member", "unknown"])
            self.assertEqual(sum(counts.values()), result["counts"]["items"])
            for name, n in counts.items():
                self.assertEqual(n, sum(1 for it in result["items"]
                                        if it["classification"] == name))
        from swlc import cli
        result = cli.build(str(ROOT / "tests" / "benchmark" / "parents"
                               / "one-os.csv"), as_of=AS_OF)[0]
        counts = result["counts"]["classification"]
        self.assertEqual(counts["governable"], 1)
        self.assertEqual(counts["bundle_member"], 2)
        self.assertEqual(counts["component"] + counts["unknown"], 0)


if __name__ == "__main__":
    unittest.main()
