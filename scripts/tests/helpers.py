from __future__ import annotations

import contextlib
import csv
import io
from pathlib import Path

from make_fixtures import build, canonical, resign


def make_data_dir(tmp, kev_date, eol_date) -> str:
    """Build a valid synthetic data dir under tmp; return its path."""
    dest = Path(tmp) / "data"
    build(dest, kev_date, eol_date)
    return str(dest)


def replace_file(data_dir, name, content) -> None:
    """Replace a data file (bytes, or an object written as JSON) and re-sign
    the manifest so only schema checks can object."""
    data = content if isinstance(content, bytes) else canonical(content)
    path = Path(data_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    resign(data_dir)


# --- shared by the report and command-line tests ---------------------------

FIXTURE_HEADER = ["Product", "Version", "Publisher", "Owner", "End of life"]
EVIL = "=cmd|' /C calc'!A0"
SCRIPT = "<script>alert(1)</script>"
FIXTURE_ROWS = [
    ["Example SQL", "14", "Example Vendor", "alice", ""],
    ["Example SQL", "15", "Example Vendor", "bob", "2027-01-31"],
    ["Example SQL", "16", "Other Publisher", "", ""],
    ["Demo OS 1.0", "1.0", "Acme Software", "carol", ""],
    ["Mystery Tool", "3.1", "Nobody Inc", "dave", ""],
    [EVIL, "9", "Evil Corp", "erin", ""],
    [SCRIPT, "1", "Tag Corp", "frank", ""],
]
FIXTURE_NAMES = ("Example SQL", "Demo OS", "Mystery Tool", "Example Vendor",
                 "Other Publisher", "Acme Software", "Nobody Inc", "alice",
                 "bob", "carol", "dave", "erin", "frank", "Evil Corp",
                 "Tag Corp", "calc", "script")


def write_inventory(path, rows=None, header=None) -> str:
    rows = FIXTURE_ROWS if rows is None else rows
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header or FIXTURE_HEADER)
        writer.writerows(rows)
    return str(path)


def run_main(argv):
    """Call swlc.cli.main; return (exit code, stdout text, stderr text)."""
    from swlc.cli import main
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()
