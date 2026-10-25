from __future__ import annotations

import csv
import hashlib
import io
import re

from .errors import DataError, InputError
from .normalize import normalize_name

REQUIRED = ("name", "version")
OPTIONAL = ("publisher", "owner", "count", "export_eol", "export_support")

# Generic aliases, matched after _norm_header (case, punctuation and
# spacing ignored). The canonical field name is always an alias of itself.
GENERIC_ALIASES: dict[str, list[str]] = {
    "name": ["name", "software name", "software", "product", "product name",
             "display name", "application", "application name", "app name",
             "title"],
    "version": ["version", "software version", "product version",
                "display version", "app version", "release", "build"],
    "publisher": ["publisher", "vendor", "manufacturer", "software publisher",
                  "software vendor", "company"],
    "owner": ["owner", "assigned to", "business owner", "technical owner",
              "application owner", "managed by", "contact", "owned by"],
    "count": ["count", "install count", "installs", "installations",
              "installed count", "number of installs", "quantity", "qty",
              "instances", "device count"],
    "export_eol": ["export eol", "end of life", "eol", "eol date",
                   "end of life date", "end of life eol"],
    "export_support": ["export support", "end of support", "eos",
                       "end of support date", "support end date",
                       "support end"],
}

_HEADER_JUNK = re.compile(r"[^0-9a-z]+")


def _norm_header(text: str) -> str:
    return _HEADER_JUNK.sub(" ", text.casefold()).strip()


def _line_of(data: bytes, offset: int) -> int:
    return data.count(b"\n", 0, offset) + 1


def _show(text: str, limit: int = 60) -> str:
    """Header text for an error message, cut to a bounded length."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


def _seen(headers: list[str], limit: int = 20) -> str:
    shown = ", ".join("%d:%s" % (i, _show(h))
                      for i, h in enumerate(headers[:limit], 1))
    extra = len(headers) - limit
    return shown + ("; and %d more" % extra if extra > 0 else "")


def _decode(data: bytes, encoding: str | None) -> str:
    if encoding is None:
        codec = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    else:
        codec = encoding
    try:
        text = data.decode(codec)
    except LookupError:
        raise InputError(
            "unknown encoding; pass --encoding with a valid name") from None
    except UnicodeDecodeError as exc:
        raise InputError(
            "file is not valid %s: bad byte at line %d; pass --encoding "
            "(for example cp1252)" % (codec, _line_of(data, exc.start))
        ) from None
    nul = text.find("\x00")
    if nul != -1:
        hint = "" if encoding else (
            "; if the file is UTF-16 or UTF-32, pass --encoding")
        raise InputError("NUL character found at line %d%s"
                         % (text.count("\n", 0, nul) + 1, hint))
    return text[1:] if text.startswith("﻿") else text


def read_rows(path: str, encoding: str | None = None,
              max_rows: int = 200_000,
              max_field: int = 65_536,
              max_bytes: int = 256 * 1024 * 1024) -> tuple[list[dict], list[str]]:
    """Read a CSV into (rows, headers). Errors name line numbers only."""
    try:
        with open(path, "rb") as fh:
            data = fh.read(max_bytes + 1)
    except OSError as exc:
        raise InputError(
            "cannot read input file (%s)" % exc.strerror) from None
    if len(data) > max_bytes:
        raise InputError("input file is larger than %d bytes" % max_bytes)
    if not data.strip():
        raise InputError("input file is empty")
    text = _decode(data, encoding)
    reader = csv.reader(io.StringIO(text, newline=""))
    rows: list[dict] = []
    headers: list[str] | None = None
    try:
        for record in reader:
            line = reader.line_num
            if not any(cell.strip() for cell in record):
                continue
            if any(len(cell) > max_field for cell in record):
                raise InputError(
                    "field longer than %d characters at line %d"
                    % (max_field, line))
            if headers is None:
                headers = [h.strip() for h in record]
                seen: dict[str, int] = {}
                for pos, h in enumerate(headers, 1):
                    if not h:
                        raise InputError(
                            "empty column name at position %d in header at "
                            "line %d" % (pos, line))
                    key = h.casefold()
                    if key in seen:
                        raise InputError(
                            "duplicate column name '%s' at positions %d and %d "
                            "in header at line %d"
                            % (_show(h), seen[key], pos, line))
                    seen[key] = pos
                continue
            if len(record) > len(headers):
                raise InputError(
                    "line %d has more fields than the header" % line)
            if len(rows) >= max_rows:
                raise InputError(
                    "more than %d data rows; stopped at line %d"
                    % (max_rows, line))
            record = record + [""] * (len(headers) - len(record))
            rows.append(dict(zip(headers, record)))
    except csv.Error:
        raise InputError(
            "malformed CSV at line %d" % reader.line_num) from None
    if headers is None or not rows:
        raise InputError("input has a header but no data rows")
    return rows, headers


def map_columns(headers: list[str], profile: dict | None,
                extra_aliases: dict | None) -> dict[str, str]:
    """Map canonical field names to header names. Never guesses.

    ``profile`` is a profile's ``columns`` dict (canonical name to alias
    list); ``extra_aliases`` has the same shape. Both add to the generic list.
    """
    lookup: dict[str, set[str]] = {}
    for source in (GENERIC_ALIASES, profile or {}, extra_aliases or {}):
        for canon, aliases in source.items():
            for alias in [canon, *aliases]:
                lookup.setdefault(_norm_header(alias), set()).add(canon)
    found: dict[str, str] = {}
    where: dict[str, int] = {}
    for pos, header in enumerate(headers, 1):
        canons = lookup.get(_norm_header(header), set())
        if len(canons) > 1:
            raise InputError(
                "column %d '%s' matches more than one field (%s)"
                % (pos, _show(header), ", ".join(sorted(canons))))
        for canon in canons:
            if canon in found:
                raise InputError(
                    "two columns map to field '%s': column %d '%s' and "
                    "column %d '%s'"
                    % (canon, where[canon], _show(found[canon]), pos,
                       _show(header)))
            found[canon] = header
            where[canon] = pos
    for canon in REQUIRED:
        if canon not in found:
            raise InputError(
                "no column found for required field '%s'; columns seen: %s"
                % (canon, _seen(headers)))
    return found


def item_id(publisher: str, name: str, version: str) -> str:
    parts = "\x1f".join(normalize_name(p) for p in (publisher, name, version))
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:12]


def group_rows(rows: list[dict], colmap: dict[str, str]) -> dict[str, dict]:
    def cell(row: dict, field: str) -> str:
        col = colmap.get(field)
        return (row.get(col) or "").strip() if col else ""

    groups: dict[str, dict] = {}
    keys: dict[str, tuple] = {}
    owners: dict[str, set] = {}
    for row in rows:
        pub, name, ver = (cell(row, f) for f in ("publisher", "name", "version"))
        key = tuple(normalize_name(x) for x in (pub, name, ver))
        gid = item_id(pub, name, ver)
        if gid in keys and keys[gid] != key:
            raise DataError(
                "two different items share ID %s; cannot continue" % gid)
        keys[gid] = key
        grp = groups.get(gid)
        if grp is None:
            grp = groups[gid] = {"id": gid, "rows": 0, "owners": [],
                                 "export_eol": "", "publisher": pub,
                                 "name": name, "version": ver}
            owners[gid] = set()
        grp["rows"] += 1
        owner = cell(row, "owner")
        if owner:
            owners[gid].add(owner)
        eol = cell(row, "export_eol")
        if eol and not grp["export_eol"]:
            grp["export_eol"] = eol
    for gid, grp in groups.items():
        grp["owners"] = sorted(owners[gid])
    return groups
