"""Support records: the owner's own list of support records per product.

A record is shown beside the vendor's dates and nothing more. It never
changes an item's state, never enters a list and never feeds --fail-on.
The tool does not check that a record was paid for or is current.
"""
from __future__ import annotations

from datetime import date

from .errors import InputError
from .overrides import _date, _read, _require, _who

COLUMNS = ("schema_version", "record_ref", "product", "scope", "kind",
           "ends_on", "owner_role")
MAX_REF = 64
MAX_KIND = 40
MAX_SCOPE = 64
MAX_ROLE = 80
MAX_ROWS = 2000
MAX_PER_PRODUCT = 25
_LIMITS = (("record_ref", MAX_REF), ("scope", MAX_SCOPE), ("kind", MAX_KIND),
           ("owner_role", MAX_ROLE))


def load_support_records(path: str | None, products) -> list | None:
    """Read a support-records CSV; None when no file was given.

    ``products`` is the set of endoflife.date product ids in the loaded
    data. Errors name the data row number and the column, never the cell
    text. Columns not listed in COLUMNS are ignored, as in the other
    override files.
    """
    if path is None:
        return None
    out: list = []
    refs: set = set()
    per_product: dict = {}
    for n, r in _read(path, COLUMNS):
        if n > MAX_ROWS:
            raise InputError(
                "more than %d data rows; stopped at data row %d (not "
                "counting the header)" % (MAX_ROWS, n))
        for col in ("record_ref", "product", "kind", "ends_on"):
            _require(r, col, n)
        for col, limit in _LIMITS:
            if len(r[col]) > limit:
                raise InputError(
                    "%s in data row %d (not counting the header) is longer "
                    "than %d characters" % (col, n, limit))
        if r["product"] not in products:
            raise InputError(
                "product in data row %d (not counting the header) is not an "
                "endoflife.date product id in the loaded data" % n)
        per_product[r["product"]] = per_product.get(r["product"], 0) + 1
        if per_product[r["product"]] > MAX_PER_PRODUCT:
            raise InputError(
                "data row %d (not counting the header) is more than %d "
                "records for one product" % (n, MAX_PER_PRODUCT))
        ref_key = _who(r["record_ref"])
        if ref_key in refs:
            raise InputError("data row %d (not counting the header) repeats "
                             "a record_ref already listed" % n)
        refs.add(ref_key)
        out.append({"record_ref": r["record_ref"], "product": r["product"],
                    "scope": r["scope"], "kind": r["kind"],
                    "ends_on": _date(r["ends_on"], "ends_on", n),
                    "owner_role": r["owner_role"] or None})
    out.sort(key=lambda rec: (rec["ends_on"], rec["record_ref"]))
    return out


def _fits(record: dict, item: dict) -> bool:
    """A matched item (product and cycle known) whose product agrees, and
    whose cycle label or version agrees when the record has a scope."""
    if item["cycle"] is None or item["product"] != record["product"]:
        return False
    scope = _who(record["scope"])
    return not scope or scope in (_who(item["cycle"]),
                                  _who(item["version"] or ""))


def ending_soon(record: dict, as_of: date, window_end: date) -> bool:
    """ends_on after the checked-on date, up to the window end inclusive.
    The same rule as an item's state: a date on or before the checked-on
    date has ended (see assess._state)."""
    return as_of < record["ends_on"] <= window_end


def attach(items: list, records: list | None, as_of: date,
           window_end: date) -> dict:
    """Set item["support_records"] on every item; return the counts.

    Only the new key is written; nothing else on an item changes.
    """
    for it in items:
        it["support_records"] = []
    counts = {"listed": 0, "ending_soon": 0, "not_matched": 0}
    by_product: dict = {}
    for it in items:
        if it["product"] is not None and it["cycle"] is not None:
            by_product.setdefault(it["product"], []).append(it)
    for rec in records or ():
        hit = False
        for it in by_product.get(rec["product"], ()):
            if _fits(rec, it):
                hit = True
                it["support_records"].append({
                    "record_ref": rec["record_ref"], "kind": rec["kind"],
                    "scope": rec["scope"] or None,
                    "ends_on": rec["ends_on"].isoformat(),
                    "owner_role": rec["owner_role"]})
        counts["listed" if hit else "not_matched"] += 1
        if ending_soon(rec, as_of, window_end):
            counts["ending_soon"] += 1
    for it in items:
        it["support_records"].sort(
            key=lambda e: (e["ends_on"], e["record_ref"]))
    return counts

