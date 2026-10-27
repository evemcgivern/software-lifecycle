"""Command line: flags, exit codes, and the only clock read (in main)."""
from __future__ import annotations

import argparse
import errno
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from .assess import LISTS, MAX_LOOKAHEAD_MONTHS, assess
from .data import load_data, tool_version, verify_data
from .errors import DataError, InputError
from .inputs import GENERIC_ALIASES, group_rows, map_columns, read_rows
from .overrides import file_hash, load_exceptions, load_golden, load_tracking
from .report import (hidden_line, render_csv, render_json, render_markdown)
from .safeio import write_text

EXIT_OK, EXIT_USAGE, EXIT_INPUT, EXIT_DATA = 0, 2, 3, 4
EXIT_FINDINGS, EXIT_UNEXPECTED = 10, 70

FAIL_ON_NAMES = ("past_eol", "ends_soon", "review_urgently",
                 "dates_disagree", "unmatched")
OUTPUT_FILES = ("report.json", "report.md", "report.csv")
BUNDLED_DATA = str(Path(__file__).resolve().parents[1] / "data")
MAX_PREVIOUS_BYTES = 64 * 1024 * 1024
MAX_COLUMNS_BYTES = 1024 * 1024
MIN_YEAR, MAX_YEAR = 1990, 2200
_DATE_FLAG = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
MAX_ALIASES_PER_FIELD = 100
MAX_ALIAS_CHARS = 200


QUIET_TEXT = ("the input could not be used; rerun locally without "
              "--counts-only for details")


class OutputError(InputError):
    """A failure writing the output; its text never holds file content."""


class UsageError(Exception):
    """A bad flag combination or value. Maps to exit code 2."""


# --- bounded, strict JSON input ---------------------------------------------

def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def _no_constants(name):
    raise ValueError("non-standard number")


def _read_json(path: str, max_bytes: int, what: str):
    try:
        with open(path, "rb") as fh:
            raw = fh.read(max_bytes + 1)
    except OSError as exc:
        raise InputError("cannot read %s file (%s)"
                         % (what, exc.strerror)) from None
    if len(raw) > max_bytes:
        raise InputError("%s file is larger than %d bytes" % (what, max_bytes))
    try:
        return json.loads(raw.decode("utf-8"),
                          object_pairs_hook=_no_duplicates,
                          parse_constant=_no_constants)
    except (ValueError, RecursionError, MemoryError):
        raise InputError("%s file is not strict UTF-8 JSON" % what) from None


def _read_columns(path: str) -> dict:
    obj = _read_json(path, MAX_COLUMNS_BYTES, "columns")
    ok = isinstance(obj, dict)
    if ok:
        for key, aliases in obj.items():
            if key not in GENERIC_ALIASES or not isinstance(aliases, list) \
                    or len(aliases) > MAX_ALIASES_PER_FIELD \
                    or not all(isinstance(a, str) and 0 < len(a)
                               <= MAX_ALIAS_CHARS for a in aliases):
                ok = False
                break
    if not ok:
        raise InputError(
            "columns file must be an object mapping a field name (%s) to a "
            "list of header names" % ", ".join(GENERIC_ALIASES))
    return obj


# --- building the report -----------------------------------------------------

def build(inventory_path: str, *, as_of: date, data: str | None = None,
          lookahead_months: int = 12, profile: str = "generic",
          columns: str | None = None, golden: str | None = None,
          exceptions: str | None = None, tracking: str | None = None,
          previous: str | None = None, encoding: str | None = None):
    """Run the whole check; return (result, meta). Raises the tool's errors."""
    loaded = load_data(data or BUNDLED_DATA, as_of)
    if profile == "generic":
        columns_map, status = None, None
    else:
        if profile not in loaded.profiles:
            raise UsageError(
                "unknown profile; available: generic%s"
                % "".join(", " + name for name in sorted(loaded.profiles)))
        entry = loaded.profiles[profile]
        columns_map = entry["columns"]
        status = entry.get("status") or "Unverified"
    extra = _read_columns(columns) if columns else None
    rows, headers = read_rows(inventory_path, encoding)
    colmap = map_columns(headers, columns_map, extra)
    groups = group_rows(rows, colmap)
    prior = _read_json(previous, MAX_PREVIOUS_BYTES, "previous report") \
        if previous else None
    try:
        result = assess(groups, loaded, load_golden(golden),
                        load_exceptions(exceptions), load_tracking(tracking),
                        as_of, lookahead_months, prior)
    except (OverflowError, ValueError):
        raise UsageError("a date is out of range") from None
    meta = {
        "tool_version": tool_version(),
        "data_release": {"id": loaded.release_id,
                         "file_hashes": dict(sorted(
                             loaded.file_hashes.items()))},
        "override_hashes": {"golden": file_hash(golden),
                            "exceptions": file_hash(exceptions),
                            "tracking": file_hash(tracking)},
        "profile": {"name": profile, "status": status},
        "encoding": encoding or "utf-8",
    }
    return result, meta


def run(inventory_path: str, **options) -> dict:
    """Importable entry: the same dict that report.json holds."""
    result, meta = build(inventory_path, **options)
    return json.loads(render_json(result, meta))


# --- command line ---

def _iso_date(text: str) -> date:
    bad = argparse.ArgumentTypeError(
        "expected a date as YYYY-MM-DD, years %d to %d"
        % (MIN_YEAR, MAX_YEAR))
    if not _DATE_FLAG.fullmatch(text):
        raise bad
    try:
        value = date.fromisoformat(text)
    except ValueError:
        raise bad from None
    if not MIN_YEAR <= value.year <= MAX_YEAR:
        raise bad
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="software_lifecycle.py",
        description="Check a software inventory against bundled "
                    "end-of-life and KEV snapshots. Runs offline.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="check an inventory CSV")
    check.add_argument("inventory", metavar="INVENTORY",
                       help="the inventory CSV export, with a header row")
    check.add_argument("--data", metavar="DIR",
                       help="data folder to use instead of the bundled data")
    check.add_argument("--as-of", type=_iso_date, metavar="YYYY-MM-DD",
                       help="check as of this date (default: today)")
    check.add_argument("--lookahead-months", type=int, default=12,
                       metavar="N",
                       help="months ahead that count as ends soon, 0 to "
                            "600 (default: 12)")
    check.add_argument("--profile", default="generic", metavar="NAME",
                       help="extra column headings for an export source: "
                            "flexera, servicenow-mbs or rapid7 (default: "
                            "generic)")
    check.add_argument("--columns", metavar="FILE",
                       help="JSON file that adds column headings")
    check.add_argument("--golden", metavar="FILE",
                       help="golden-sources CSV: which end-of-life date is "
                            "right for a product")
    check.add_argument("--exceptions", metavar="FILE",
                       help="exceptions CSV: accepted risk")
    check.add_argument("--tracking", metavar="FILE",
                       help="tracking CSV: change and problem references")
    check.add_argument("--previous", metavar="REPORT.json",
                       help="an earlier report.json, to show what changed")
    check.add_argument("--out", metavar="DIR",
                       help="folder for report.json, report.md and "
                            "report.csv")
    check.add_argument("--counts-only", action="store_true",
                       help="print only counts and item IDs (needs --out)")
    check.add_argument("--governable-only", action="store_true",
                       help="report.md and report.csv leave out components "
                            "and bundle members; report.json is unchanged")
    check.add_argument("--fail-on", metavar="LIST",
                       help="exit 10 if any named list has items: "
                            + ", ".join(FAIL_ON_NAMES))
    check.add_argument("--encoding", metavar="NAME",
                       help="text encoding of the inventory if not UTF-8")
    verify = sub.add_parser("verify-data", help="verify the data directory")
    verify.add_argument("--data", metavar="DIR",
                        help="data folder to verify (default: bundled data)")
    return parser


def _fail_on(text: str | None) -> list:
    if text is None:
        return []
    names = [n.strip() for n in text.split(",")]
    if not text.strip() or any(n not in FAIL_ON_NAMES for n in names):
        raise UsageError("--fail-on takes a comma list of: %s"
                         % ", ".join(FAIL_ON_NAMES))
    return sorted(set(names))


def _same_file(path: str, other: str) -> bool:
    if os.path.realpath(path) == os.path.realpath(other):
        return True
    try:
        return os.path.samefile(path, other)
    except OSError:
        return False


def _check_out(out: str, inventory: str) -> None:
    if _same_file(out, inventory):
        raise UsageError("--out must be a directory, not the input file")
    if os.path.islink(out):
        raise OutputError("refusing to write through a symlink")
    if os.path.exists(out) and not os.path.isdir(out):
        raise UsageError("--out must be a directory")
    for name in OUTPUT_FILES:
        target = os.path.join(out, name)
        if os.path.islink(target):
            raise OutputError("refusing to write through a symlink")
        if _same_file(target, inventory):
            raise OutputError("refusing to overwrite the input file")


def _write_out(out: str, inventory: str, result: dict, meta: dict,
               governable_only: bool = False) -> None:
    texts = (render_json(result, meta),
             render_markdown(result, meta, governable_only),
             render_csv(result, governable_only))
    try:
        os.makedirs(out, mode=0o700, exist_ok=True)
        for name, text in zip(OUTPUT_FILES, texts):
            write_text(os.path.join(out, name), text, inventory)
    except OutputError:
        raise
    except InputError as exc:
        raise OutputError(str(exc)) from None
    except OSError as exc:
        raise OutputError("cannot write output (%s)"
                         % errno.errorcode.get(exc.errno, "OSError")) \
            from None


def _counts_text(result: dict) -> str:
    counts = result["counts"]
    lines = ["checked_on %s" % result["as_of"],
             "kev_current %s" % ("true" if result["kev_current"] else "false"),
             "items %d rows %d" % (counts["items"], counts["rows"]),
             "states " + " ".join("%s=%d" % (k, v) for k, v
                                  in sorted(counts["states"].items())),
             "classification " + " ".join(
                 "%s=%d" % (k, v) for k, v
                 in sorted(counts["classification"].items())),
             "ambiguous_review %d" % counts["ambiguous_review"]]
    for name in LISTS:
        ids = result["lists"][name]
        lines.append("%s %d%s" % (name, len(ids),
                                  ": " + " ".join(ids) if ids else ""))
    return "\n".join(lines) + "\n"


def _check(args) -> int:
    fail_on = _fail_on(args.fail_on)
    if args.counts_only and not args.out:
        raise UsageError("--counts-only needs --out")
    if not 0 <= args.lookahead_months <= MAX_LOOKAHEAD_MONTHS:
        raise UsageError("--lookahead-months must be from 0 to %d"
                         % MAX_LOOKAHEAD_MONTHS)
    if args.out:
        _check_out(args.out, args.inventory)
    as_of = args.as_of or date.today()  # only clock read in the tool
    result, meta = build(
        args.inventory, as_of=as_of, data=args.data,
        lookahead_months=args.lookahead_months, profile=args.profile,
        columns=args.columns, golden=args.golden,
        exceptions=args.exceptions, tracking=args.tracking,
        previous=args.previous, encoding=args.encoding)
    if args.out:
        _write_out(args.out, args.inventory, result, meta,
                   args.governable_only)
    if args.counts_only:
        sys.stdout.write(_counts_text(result))
    elif args.out:
        print("Wrote %s to %s" % (", ".join(OUTPUT_FILES), args.out))
        if args.governable_only:
            print(hidden_line(result))
    else:
        sys.stdout.write(render_markdown(result, meta, args.governable_only))
    hit = [n for n in fail_on if result["lists"][n]]
    if hit:
        print("Findings present in: %s" % ", ".join(hit), file=sys.stderr)
        return EXIT_FINDINGS
    return EXIT_OK


def main(argv: list | None = None) -> int:
    quiet = False
    try:
        args = _parser().parse_args(argv)
        quiet = bool(getattr(args, "counts_only", False))
        if args.command == "verify-data":
            return verify_data(args.data or BUNDLED_DATA)
        return _check(args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    except UsageError as exc:
        print("Usage error: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    except InputError as exc:
        print("Input error: %s" % (QUIET_TEXT if quiet and not isinstance(
            exc, OutputError) else exc), file=sys.stderr)
        return EXIT_INPUT
    except DataError as exc:
        print("Data check failed: %s" % (QUIET_TEXT if quiet else exc),
              file=sys.stderr)
        return EXIT_DATA
    except Exception as exc:
        print(type(exc).__name__, file=sys.stderr)
        return EXIT_UNEXPECTED
