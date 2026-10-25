from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date

from .errors import InputError
from .inputs import read_rows
from .normalize import normalize_name

SCHEMA_VERSION = "1"
SOURCES = ("export", "endoflife.date", "manual")

_GOLDEN_COLS = ("schema_version", "product", "source", "manual_eol",
                "reason", "set_by", "set_on", "review_by")
_EXC_COLS = ("schema_version", "product", "scope", "compensating_controls",
             "risk_owner", "approver", "requested_by", "expires_on",
             "reference")
_TRACK_COLS = ("schema_version", "item_id", "change_ref", "problem_ref")

_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_SLUG = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")


def _product_key(value: str) -> str:
    """A lowercase endoflife.date slug is kept as is; anything else is
    reduced with normalize_name."""
    value = value.strip()
    return value if _SLUG.match(value) else normalize_name(value)


def _who(value: str) -> str:
    """Plain comparison key: NFKC, casefold, collapse spaces, strip."""
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(text.split())


def _read(path: str, columns: tuple) -> list:
    """Read an override CSV with the safe reader; check columns and version.

    Returns [(data_row_number, {column: stripped text})]. Errors name the
    data row number and column names only, never cell text.
    """
    rows, headers = read_rows(path, allow_empty=True)
    by_fold = {h.casefold(): h for h in headers}
    missing = [c for c in columns if c not in by_fold]
    if missing:
        raise InputError("missing required column(s): %s"
                         % ", ".join(missing))
    out = []
    for n, raw in enumerate(rows, 1):
        row = {c: (raw.get(by_fold[c]) or "").strip() for c in columns}
        if row["schema_version"] != SCHEMA_VERSION:
            raise InputError(
                "unsupported schema_version in data row %d (not counting the "
                "header); this tool reads version %s" % (n, SCHEMA_VERSION))
        out.append((n, row))
    return out


def _date(text: str, column: str, n: int) -> date | None:
    if not text:
        return None
    if not _ISO.match(text):
        raise InputError("%s in data row %d (not counting the header) is not a date in "
                         "YYYY-MM-DD form"
                         % (column, n))
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise InputError("%s in data row %d (not counting the header) is not a "
                         "real date"
                         % (column, n)) from None


def _require(row: dict, column: str, n: int) -> None:
    if not row[column]:
        raise InputError("%s is required in data row %d (not counting the header)"
                         % (column, n))


class Golden:
    """Golden-source rows keyed by product key (see ``_product_key``)."""

    def __init__(self, rows: dict | None = None) -> None:
        self.rows: dict[str, dict] = rows or {}

    def for_product(self, product_id: str, normalized_name: str) -> dict | None:
        """Row for an endoflife.date product id, else for the normalized
        product name; None when neither is listed."""
        for key in (product_id, normalized_name):
            if key in self.rows:
                return self.rows[key]
        return None

    @staticmethod
    def is_expired(row: dict, as_of: date) -> bool:
        """review_by is inclusive: expired the day after."""
        review = row.get("review_by")
        return review is not None and as_of > review

    def expired(self, as_of: date) -> list:
        return [r for r in self.rows.values() if self.is_expired(r, as_of)]


class Exceptions:
    """Risk exceptions keyed by (product key, normalized scope)."""

    def __init__(self, rows: dict | None = None) -> None:
        self.rows: dict[tuple, dict] = rows or {}

    @staticmethod
    def _scope(scope: str) -> str:
        return _who(scope or "")

    def find(self, product: str, scope: str) -> dict | None:
        """Matching row whether or not it has expired (for the report).
        ``product`` is a product id or a name; both forms are tried."""
        s = self._scope(scope)
        for key in (product.strip(), _product_key(product)):
            if (key, s) in self.rows:
                return self.rows[(key, s)]
        return None

    def active(self, product: str, scope: str, as_of: date) -> bool:
        """True through expires_on (inclusive); False the day after."""
        row = self.find(product, scope)
        return row is not None and as_of <= row["expires_on"]


def load_golden(path: str | None) -> Golden:
    if path is None:
        return Golden()
    rows: dict[str, dict] = {}
    for n, r in _read(path, _GOLDEN_COLS):
        _require(r, "product", n)
        if r["source"] not in SOURCES:
            raise InputError(
                "source in data row %d (not counting the header) must be one "
                "of: %s" % (n, ", ".join(SOURCES)))
        manual = _date(r["manual_eol"], "manual_eol", n)
        if r["source"] == "manual" and manual is None:
            raise InputError(
                "manual_eol is required in data row %d (not counting the "
                "header) when source is manual" % n)
        if r["source"] != "manual" and manual is not None:
            raise InputError(
                "manual_eol in data row %d (not counting the header) is only "
                "allowed when source is manual" % n)
        key = _product_key(r["product"])
        if key in rows:
            raise InputError("data row %d (not counting the header) repeats "
                             "a product already listed" % n)
        rows[key] = {
            "product": key, "source": r["source"], "manual_eol": manual,
            "reason": r["reason"], "set_by": r["set_by"],
            "set_on": _date(r["set_on"], "set_on", n),
            "review_by": _date(r["review_by"], "review_by", n),
        }
    return Golden(rows)


def load_exceptions(path: str | None) -> Exceptions:
    if path is None:
        return Exceptions()
    rows: dict[tuple, dict] = {}
    for n, r in _read(path, _EXC_COLS):
        _require(r, "product", n)
        for col in ("risk_owner", "approver", "requested_by", "expires_on",
                    "reference"):
            _require(r, col, n)
        if _who(r["approver"]) == _who(r["requested_by"]):
            raise InputError(
                "approver and requested_by are the same person in data row %d "
                "(not counting the header); an exception needs a different "
                "approver" % n)
        key = (_product_key(r["product"]), _who(r["scope"]))
        if key in rows:
            raise InputError(
                "data row %d (not counting the header) repeats a product and "
                "scope already listed" % n)
        rows[key] = {
            "product": key[0], "scope": r["scope"],
            "compensating_controls": r["compensating_controls"],
            "risk_owner": r["risk_owner"], "approver": r["approver"],
            "requested_by": r["requested_by"],
            "expires_on": _date(r["expires_on"], "expires_on", n),
            "reference": r["reference"],
        }
    return Exceptions(rows)


def load_tracking(path: str | None) -> dict[str, dict]:
    if path is None:
        return {}
    out: dict[str, dict] = {}
    for n, r in _read(path, _TRACK_COLS):
        _require(r, "item_id", n)
        if r["item_id"] in out:
            raise InputError("data row %d (not counting the header) repeats an "
                             "item_id already listed" % n)
        out[r["item_id"]] = {"change_ref": r["change_ref"],
                             "problem_ref": r["problem_ref"]}
    return out


def file_hash(path: str | None) -> str:
    """SHA-256 hex of the raw bytes; "" for no path or a missing file."""
    if path is None:
        return ""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise InputError("cannot read override file (%s)" % exc.strerror) \
            from None
