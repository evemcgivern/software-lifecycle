"""Pure assessment core: groups plus data in, one JSON-ready dict out.

No file access, no printing, no clock, no environment reads. The same
inputs always give an identical dict. Items carry fixed codes only; the
human wording is the report's job.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime

from .classify import (CLASSES, PARENT_ABSENT, apply_classification,
                       inherited_states)
from .data import Data, kev_match
from .errors import InputError
from .matching import match_product
from .normalize import normalize_name
from .overrides import Exceptions, Golden

SCHEMA_VERSION = 1
STATES = ("supported", "mainstream_ended", "ends_soon", "past_eol",
          "unmatched")
LISTS = ("past_eol", "ends_soon", "dates_disagree", "unmatched",
         "accepted_risk", "ownerless", "review_urgently", "golden_overrides")
MAX_LOOKAHEAD_MONTHS = 600
_ID = re.compile(r"[0-9a-f]{12}")

# dates_disagree codes (also used in decision_needed)
DIFFERENT_DATE = "DIFFERENT_DATE"
NO_ENDOFLIFE_DATE = "NO_ENDOFLIFE_DATE"
EXPORT_DATE_UNREADABLE = "EXPORT_DATE_UNREADABLE"
EXPORT_DATES_CONFLICT = "EXPORT_DATES_CONFLICT"
GOLDEN_EXPIRED = "GOLDEN_EXPIRED"
GOLDEN_EXPORT_UNUSABLE = "GOLDEN_EXPORT_UNUSABLE"
EXCEPTION_EXPIRED = "EXCEPTION_EXPIRED"

KEV_NOT_CURRENT = ("KEV snapshot is not current; the KEV overlay may be "
                   "out of date")
GOLDEN_CLASH = ("%d item(s) matched two golden-source rows; the product-id "
                "row was used.")
PREVIOUS_UNUSABLE = "previous run could not be read; no diff"
PARENTS_ABSENT = "%d parts whose parent is not in this inventory"

# ISO date, optionally followed by a time ("2026-01-15 00:00:00",
# "2026-01-15T00:00:00Z"). Day-first or month-first forms are never read.
_EXPORT_DATE = re.compile(
    r"([0-9]{4}-[0-9]{2}-[0-9]{2})"
    r"(?:[ T][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?Z?)?\Z")


def add_months(d: date, months: int) -> date:
    """Calendar month arithmetic; the day is clamped to the month's end."""
    total = d.month - 1 + months
    year, month = d.year + total // 12, total % 12 + 1
    return d.replace(year=year, month=month,
                     day=min(d.day, calendar.monthrange(year, month)[1]))


def _iso(value):
    """date -> 'YYYY-MM-DD'; True, False and None pass through."""
    return value.isoformat() if isinstance(value, date) else value


def _parse_export(text: str):
    """(date or None, readable). Empty text is (None, True)."""
    if not text:
        return None, True
    m = _EXPORT_DATE.match(text.strip())
    if not m:
        return None, False
    try:
        return date.fromisoformat(m.group(1)), True
    except ValueError:
        return None, False


def _state(eol, support, as_of: date, window_end: date) -> str:
    """endoflife.date polarity: eol true = ended; support false = ended."""
    if eol is True or (isinstance(eol, date) and eol <= as_of):
        return "past_eol"
    if isinstance(eol, date) and eol <= window_end:
        return "ends_soon"
    if support is False or (isinstance(support, date) and support <= as_of):
        return "mainstream_ended"
    return "supported"


def _read_exports(texts: list):
    """(date or None, readable, conflict, raw) for a group's export dates.

    Texts that parse to the same date count once; each unreadable text is
    its own value. More than one value is a conflict and nothing is used.
    """
    values = set()
    for text in texts:
        parsed, readable = _parse_export(text)
        values.add(parsed if readable else ("unreadable", text))
    raw = "; ".join(texts) or None
    if len(values) > 1:
        return None, True, True, raw
    if not values:
        return None, True, False, None
    (value,) = values
    if isinstance(value, date):
        return value, True, False, raw
    return None, False, False, raw


def _exception(exceptions: Exceptions, products: list, scopes: list,
               as_of: date):
    """(active, expired) for the most specific matching exception."""
    for scope in scopes:
        for product in products:
            row = exceptions.find(product, scope)
            if row is not None:
                active = exceptions.active(product, scope, as_of)
                return active, not active
    return False, False


def _item(group: dict, data: Data, golden: Golden, exceptions: Exceptions,
          tracking: dict, as_of: date, window_end: date,
          golden_clashes: list) -> dict:
    name, version = group["name"], group["version"]
    norm_name = normalize_name(name)
    match = match_product(name, version, data.aliases, data.products,
                          catalog_index=data.matching_index(),
                          publisher=group["publisher"])
    cycle = match.cycle
    export_date, export_readable, export_conflict, export_raw = \
        _read_exports(list(group.get("export_eols") or []))

    eol_endoflife = cycle.get("eol") if cycle else None
    eol_used, eol_source = None, None
    golden_applied, golden_expired = None, False
    disagree = None
    decision = []
    state_endoflife = None

    if cycle is None:
        state = "unmatched"
    else:
        eol_used, eol_source = eol_endoflife, "endoflife.date"
        row = golden.for_product(match.product, norm_name)
        if golden.has_two_rows(match.product, norm_name):
            golden_clashes.append(group["id"])
        if row is not None and Golden.is_expired(row, as_of):
            golden_expired = True
            disagree = GOLDEN_EXPIRED
        elif row is not None and row["source"] == "export":
            if export_conflict:
                disagree = EXPORT_DATES_CONFLICT
            elif export_date is None:
                disagree = GOLDEN_EXPORT_UNUSABLE
            else:
                eol_used, eol_source = export_date, "export"
                golden_applied = "export"
        elif row is not None and row["source"] == "manual":
            eol_used, eol_source = row["manual_eol"], "manual"
            golden_applied = "manual"
        elif row is not None:
            golden_applied = "endoflife.date"
        if row is None or golden_expired:
            if not export_readable:
                disagree = disagree or EXPORT_DATE_UNREADABLE
            elif export_date is not None:
                if not isinstance(eol_endoflife, date):
                    disagree = disagree or NO_ENDOFLIFE_DATE
                elif export_date != eol_endoflife:
                    disagree = disagree or DIFFERENT_DATE
        state = _state(eol_used, cycle.get("support"), as_of, window_end)
        state_endoflife = _state(eol_endoflife, cycle.get("support"), as_of,
                                 window_end)
        if export_conflict:
            # Rows disagree among themselves: always a person's call, even
            # under an active golden source (which then cannot be "export").
            disagree = disagree or EXPORT_DATES_CONFLICT
            decision.append(EXPORT_DATES_CONFLICT)
        if eol_endoflife is None and export_date is not None:
            # No endoflife.date date against the user's own dated evidence.
            decision.append(NO_ENDOFLIFE_DATE)

    if disagree in (GOLDEN_EXPIRED, GOLDEN_EXPORT_UNUSABLE,
                    EXPORT_DATE_UNREADABLE, EXPORT_DATES_CONFLICT):
        decision.append(disagree)

    products = [p for p in (match.product, norm_name) if p]
    scopes = [s for s in ((cycle or {}).get("cycle"), version) if s] + [""]
    accepted, exc_expired = _exception(exceptions, products, scopes, as_of)
    if exc_expired:
        decision.append(EXCEPTION_EXPIRED)

    kev = None
    if state in ("past_eol", "ends_soon"):
        if match.kev:
            kev = kev_match(data.kev, match.kev["vendor"],
                            match.kev["product"])
        else:
            kev = kev_match(data.kev, group["publisher"], name)

    refs = tracking.get(group["id"]) or {}
    return {
        "id": group["id"],
        "name": name,
        "version": version,
        "publisher": group["publisher"],
        "owners": sorted(group["owners"]),
        "rows": group["rows"],
        "product": match.product,
        "cycle": cycle.get("cycle") if cycle else None,
        "state": state,
        "state_endoflife": state_endoflife,
        "reason": match.reason,
        "match_source": match.source,
        "eol_endoflife": _iso(eol_endoflife),
        "eol_export": _iso(export_date),
        "eol_export_raw": export_raw,
        "eol_used": _iso(eol_used),
        "eol_source": eol_source,
        "support": _iso(cycle.get("support")) if cycle else None,
        "extended_support": _iso(cycle.get("extended")) if cycle else None,
        "golden_applied": golden_applied,
        "golden_expired": golden_expired,
        "dates_disagree": disagree,
        "accepted_risk": accepted,
        "exception_expired": exc_expired,
        "decision_needed": sorted(set(decision)),
        "kev": kev,
        "kev_stale": bool(kev is not None and not data.kev_current),
        "change_ref": refs.get("change_ref") or None,
        "problem_ref": refs.get("problem_ref") or None,
    }


def _lists(items: list) -> dict:
    out = {name: [] for name in LISTS}
    for it in items:
        if it["state"] in ("past_eol", "ends_soon", "unmatched"):
            out[it["state"]].append(it["id"])
        if it["dates_disagree"]:
            out["dates_disagree"].append(it["id"])
        if it["accepted_risk"]:
            out["accepted_risk"].append(it["id"])
        if not it["owners"]:
            out["ownerless"].append(it["id"])
        if it["kev"]:
            out["review_urgently"].append(it["id"])
        if it["state_endoflife"] is not None \
                and it["state_endoflife"] != it["state"]:
            out["golden_overrides"].append(it["id"])
    return {k: sorted(v) for k, v in out.items()}


def _previous_states(previous) -> dict | None:
    if not isinstance(previous, dict) \
            or type(previous.get("schema_version")) is not int \
            or previous["schema_version"] != SCHEMA_VERSION \
            or not isinstance(previous.get("items"), list):
        return None
    states = {}
    for it in previous["items"]:
        if not isinstance(it, dict) or not isinstance(it.get("id"), str) \
                or not _ID.fullmatch(it["id"]) \
                or it.get("state") not in STATES:
            return None
        states[it["id"]] = it["state"]
    return states


def _diff(items: list, before: dict | None) -> dict:
    if before is None:
        return {"available": False, "new": [], "resolved": [],
                "changed_state": []}
    now = {it["id"]: it["state"] for it in items}
    return {
        "available": True,
        "new": sorted(set(now) - set(before)),
        "resolved": sorted(set(before) - set(now)),
        "changed_state": [{"id": i, "from": before[i], "to": now[i]}
                          for i in sorted(set(now) & set(before))
                          if before[i] != now[i]],
    }


def assess(groups: dict, data: Data, golden: Golden, exceptions: Exceptions,
           tracking: dict, as_of: date, lookahead_months: int = 12,
           previous: dict | None = None) -> dict:
    """Assess grouped inventory items against the loaded data."""
    if isinstance(as_of, datetime) or not isinstance(as_of, date):
        raise ValueError("as_of must be a date")
    if isinstance(lookahead_months, bool) or not isinstance(
            lookahead_months, int) or not \
            0 <= lookahead_months <= MAX_LOOKAHEAD_MONTHS:
        raise InputError("lookahead must be a whole number of months from "
                         "0 to %d" % MAX_LOOKAHEAD_MONTHS)
    window_end = add_months(as_of, lookahead_months)

    clashes: list = []
    items = [_item(groups[gid], data, golden, exceptions, tracking, as_of,
                   window_end, clashes) for gid in sorted(groups)]
    apply_classification(items, groups, data)
    lists = _lists(items)

    warnings = list(data.warnings)
    if not data.kev_current and not any("not current" in w for w in warnings):
        warnings.append(KEV_NOT_CURRENT)
    if clashes:
        warnings.append(GOLDEN_CLASH % len(clashes))
    absent = sum(1 for it in items
                 if PARENT_ABSENT in it["classification_basis"])
    if absent:
        warnings.append(PARENTS_ABSENT % absent)
    before = None
    if previous is not None:
        before = _previous_states(previous)
        if before is None:
            warnings.append(PREVIOUS_UNUSABLE)

    states = {s: 0 for s in STATES}
    for it in items:
        states[it["state"]] += 1
    by_id = {it["id"]: it for it in items}
    breakdown = {"needs_review": 0, "parts_with_parent": 0,
                 "parts_parent_absent": 0}
    for gid in lists["unmatched"]:
        it = by_id[gid]
        if it["classification"] in ("unknown", "governable"):
            breakdown["needs_review"] += 1
        elif it["classification"] == "bundle_member" and it["inherited_from"]:
            breakdown["parts_with_parent"] += 1
        else:
            breakdown["parts_parent_absent"] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of.isoformat(),
        "lookahead_months": lookahead_months,
        "data_release": {
            "id": data.release_id,
            "file_hashes": dict(sorted(data.file_hashes.items())),
            "kev_catalog_version": data.kev_catalog_version,
            "kev_age_days": data.kev_age_days,
            "eol_age_days": data.eol_age_days,
        },
        "kev_current": data.kev_current,
        "warnings": warnings,
        "items": items,
        "lists": lists,
        "counts": {
            "items": len(items),
            "rows": sum(it["rows"] for it in items),
            "states": states,
            "lists": {k: len(v) for k, v in lists.items()},
            "classification": {c: sum(1 for it in items
                                      if it["classification"] == c)
                               for c in CLASSES},
            # Splits the unmatched total; the three numbers add up to it.
            "unmatched_breakdown": breakdown,
            # Parts whose parent is past or near end of life. A count, not
            # a list: a part never enters a list through its parent.
            "inherited_attention": sum(
                1 for it in items if it["inherited_lifecycle"]
                and it["inherited_lifecycle"]["state"] in inherited_states),
        },
        "diff": _diff(items, before),
    }
