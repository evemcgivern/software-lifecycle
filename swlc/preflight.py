"""Preflight: say whether `check` can use an inventory export.

Read-only and offline. The output holds the file's column titles and
numbers only: never a cell value, a row or a name taken from a row.
"""
from __future__ import annotations

import json
import os
import shlex
import stat

from . import inputs
from .classify import _PLACEHOLDERS
from .errors import InputError
from .inputs import _norm_header, _show, map_columns, read_rows
from .normalize import normalize_name

PREFLIGHT_VERSION = 1
FIELDS = ("name", "publisher", "version", "count", "parent")
CORE = ("name", "publisher", "version")
SNIFF_BYTES = 64 * 1024
# The same first characters that report.csv neutralizes.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
NEXT_OUT = "../swlc-out"

FIX_TEXT = {
    "NO_ROWS": "The file has a header row but no data rows. Export it "
               "again with its rows.",
    "NO_NAME": "No name column was found. Rename the column that holds the "
               "software name to Name, or pass --columns FILE.",
    "NO_VERSION": "No version column was found. Rename the column that "
                  "holds the version to Version, or pass --columns FILE.",
    "NO_PUBLISHER": "No publisher column was found. Matching uses the "
                    "publisher when there is one; add a Publisher column if "
                    "the export has it.",
    "NO_COUNT": "No count column was found. That is fine: the report counts "
                "inventory rows and keeps its usual order. Add a count "
                "column to rank items by it.",
    "NO_PARENT": "No parent column was found. That is fine; add one if the "
                 "export has it (see \"The Parent column\" in "
                 "docs/usage.md).",
    "BLANK_NAME": "Some rows have a blank name cell. Those rows cannot be "
                  "matched; fill them in or drop them.",
    "BLANK_VERSION": "Some rows have a blank version cell. Those rows cannot "
                     "be matched to a cycle; fill them in where you can.",
    "PLACEHOLDER": "Some Parent cells hold a placeholder such as n/a, none "
                   "or unknown. check reads those as no parent.",
    "FORMULA": "Some cells start like a spreadsheet formula (=, +, -, @). "
               "report.csv neutralizes them; check the export if you did "
               "not expect them.",
    "OTHER_PROFILE": "Another profile fits this file better than the one "
                     "passed; see \"best fit\" above. The next command "
                     "keeps the profile you passed.",
}
BLOCKING = ("NO_ROWS", "NO_NAME", "NO_VERSION")


_WIDE_BOMS = (b"\xff\xfe", b"\xfe\xff")


def _line_endings(head: bytes, encoding: str | None, more: bool) -> str:
    """CRLF, LF, CR, mixed or none; unknown when the bytes are not
    ASCII-compatible (UTF-16, UTF-32), where a byte count would be wrong."""
    try:
        wide = encoding is not None and "\r\n".encode(encoding) != b"\r\n"
    except (LookupError, UnicodeError):
        wide = True
    if wide or b"\x00" in head or head.startswith(_WIDE_BOMS):
        return "unknown"
    if more and head.endswith(b"\r"):
        head = head[:-1]  # its LF may be just past the sample
    crlf = head.count(b"\r\n")
    kinds = [name for name, n in (("CRLF", crlf),
                                  ("LF", head.count(b"\n") - crlf),
                                  ("CR", head.count(b"\r") - crlf)) if n]
    return "mixed" if len(kinds) > 1 else kinds[0] if kinds else "none"


def _sniff(path: str, encoding: str | None) -> dict:
    try:
        info = os.stat(path)
    except OSError as exc:
        raise InputError(
            "cannot read input file (%s)" % exc.strerror) from None
    # Before any open: a FIFO would block and /dev/zero never ends.
    if not stat.S_ISREG(info.st_mode):
        raise InputError("input is not a regular file")
    size = info.st_size
    try:
        with open(path, "rb") as fh:
            head = fh.read(SNIFF_BYTES)
    except OSError as exc:
        raise InputError(
            "cannot read input file (%s)" % exc.strerror) from None
    return {"bytes": size, "bom": head.startswith(b"\xef\xbb\xbf"),
            "line_endings": _line_endings(head, encoding,
                                          size > len(head))}


def _score(headers: list, profiles: dict, extra: dict | None) -> dict:
    """For each profile: which fields its own headings matched, and whether
    it fits (its name, publisher and version headings all matched)."""
    seen = {_norm_header(h) for h in headers}
    out = {}
    for name in sorted(profiles):
        cols = profiles[name]["columns"]
        matched = sorted(f for f, aliases in cols.items()
                         if any(_norm_header(a) in seen for a in aliases))
        core = [f for f in CORE if f in cols]
        fits = bool(core) and all(f in matched for f in core)
        if fits:
            try:
                map_columns(headers, cols, extra, require=False)
            except InputError:
                fits = False
        out[name] = {"matched": matched, "listed": len(cols), "fits": fits}
    return out


def _best(scores: dict) -> tuple:
    fit = [n for n in sorted(scores) if scores[n]["fits"]]
    if not fit:
        return "generic", ("no profile's own headings for name, publisher "
                           "and version all matched; the generic headings "
                           "fit")
    top = max(len(scores[n]["matched"]) for n in fit)
    tied = [n for n in fit if len(scores[n]["matched"]) == top]
    best = tied[0]
    how = ("its headings matched %d of the %d fields it lists (%s)"
           % (top, scores[best]["listed"], ", ".join(scores[best]["matched"])))
    if len(tied) > 1:
        how += "; tied with %s, first by name chosen" % ", ".join(tied[1:])
    return best, how


def _next_command(path: str, profile: str, columns: str | None,
                  encoding: str | None) -> str:
    parts = ["python3", "software_lifecycle.py", "check", path]
    if profile != "generic":
        parts += ["--profile", profile]
    if columns:
        parts += ["--columns", columns]
    if encoding:
        parts += ["--encoding", encoding]
    parts += ["--out", NEXT_OUT]
    return " ".join(shlex.quote(p) for p in parts)


def inspect(path: str, profiles: dict, profile: str | None = None,
            columns: str | None = None, extra: dict | None = None,
            encoding: str | None = None) -> dict:
    """Return the preflight result. Raises InputError when the file cannot
    be read as a CSV with a header; its text never holds file content."""
    sniff = _sniff(path, encoding)
    rows, headers = read_rows(path, encoding, max_rows=inputs.MAX_ROWS,
                              max_bytes=inputs.MAX_BYTES, allow_empty=True)
    scores = _score(headers, profiles, extra)
    best, how = _best(scores)
    used = profile or best
    colmap = map_columns(headers,
                         profiles[used]["columns"] if used != "generic"
                         else None, extra, require=False)
    blank = {f: 0 for f in colmap}
    # Only the Parent column treats placeholders as blank in check.
    placeholder = {"parent": 0} if "parent" in colmap else {}
    formula = 0
    for row in rows:
        for field, col in colmap.items():
            cell = row.get(col) or ""
            if not cell.strip():
                blank[field] += 1
            elif field in placeholder \
                    and normalize_name(cell) in _PLACEHOLDERS:
                placeholder[field] += 1
        formula += sum(1 for cell in row.values()
                       if cell[:1] in FORMULA_START)
    fix = []
    if not rows:
        fix.append("NO_ROWS")
    for field in FIELDS:
        if field not in colmap:
            fix.append("NO_" + field.upper())
    if blank.get("name"):
        fix.append("BLANK_NAME")
    if blank.get("version"):
        fix.append("BLANK_VERSION")
    if any(placeholder.values()):
        fix.append("PLACEHOLDER")
    if formula:
        fix.append("FORMULA")
    if profile and profile != best and best != "generic":
        fix.append("OTHER_PROFILE")
    status = None if used == "generic" else (
        profiles[used].get("status") or "Unverified")
    return {
        "preflight_version": PREFLIGHT_VERSION,
        "ok": not any(code in BLOCKING for code in fix),
        "file": {"readable": True,
                 "encoding": encoding or "utf-8",
                 "bom": sniff["bom"],
                 "line_endings": sniff["line_endings"],
                 "bytes": sniff["bytes"],
                 "rows": len(rows)},
        "limits": {"max_rows": inputs.MAX_ROWS,
                   "max_bytes": inputs.MAX_BYTES,
                   "within": True},
        "profile": {"best": best, "how": how, "used": used,
                    "status": status, "scores": scores},
        "columns": {f: (_show(colmap[f]) if f in colmap else None)
                    for f in FIELDS},
        "other_columns": {f: _show(colmap[f]) for f in sorted(colmap)
                          if f not in FIELDS},
        "blank_cells": dict(sorted(blank.items())),
        "placeholder_cells": placeholder,
        "formula_cells": formula,
        "fix": [{"code": c, "blocking": c in BLOCKING, "text": FIX_TEXT[c]}
                for c in fix],
        "next_command": _next_command(path, used, columns, encoding),
    }


def render_json(result: dict) -> str:
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def error_json(message: str, code: int) -> str:
    return json.dumps({"preflight_version": PREFLIGHT_VERSION, "ok": False,
                       "exit_code": code, "error": message},
                      indent=2, sort_keys=True) + "\n"


def render_text(result: dict) -> str:
    f, lim, prof = result["file"], result["limits"], result["profile"]
    enc = "UTF-8" if f["encoding"] == "utf-8" else f["encoding"]
    lines = [
        "Preflight (reads the file only; writes nothing)",
        "",
        "File",
        "  readable: yes",
        "  encoding: %s%s" % (enc, ", with a byte order mark"
                              if f["bom"] else ""),
        "  line endings: %s" % f["line_endings"],
        "  data rows: %d (limit %d)" % (f["rows"], lim["max_rows"]),
        "  size: %d bytes (limit %d)" % (f["bytes"], lim["max_bytes"]),
        "  limits: within both",
        "",
        "Profile",
        "  best fit: %s" % prof["best"],
        "  how: %s" % prof["how"],
        "  used for this check: %s%s" % (
            prof["used"], " (%s)" % prof["status"] if prof["status"] else ""),
        "",
        "Columns",
    ]
    for field, header in result["columns"].items():
        lines.append("  %s: %s" % (field, "found \"%s\"" % header
                                   if header else "not found"))
    for field, header in result["other_columns"].items():
        lines.append("  %s: found \"%s\"" % (field, header))
    lines += ["", "Blank cells, by column"]
    lines += ["  %s: %d" % kv for kv in result["blank_cells"].items()]
    lines += ["", "Placeholder Parent cells (n/a, none, unknown and the "
              "like)"]
    lines += ["  %s: %d" % kv for kv in result["placeholder_cells"].items()]
    lines += ["", "Cells that start like a spreadsheet formula: %d"
              % result["formula_cells"], "", "What to fix"]
    if result["fix"]:
        lines += ["  - %s%s" % ("[must fix] " if item["blocking"] else "",
                                item["text"]) for item in result["fix"]]
    else:
        lines.append("  Nothing.")
    lines += ["", "Next command" if result["ok"]
              else "Next command, after the must-fix items",
              "  " + result["next_command"]]
    return "\n".join(lines) + "\n"
