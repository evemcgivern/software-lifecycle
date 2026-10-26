from __future__ import annotations

import contextlib
import csv
import io
from pathlib import Path

from make_fixtures import build, canonical, resign


def make_data_dir(tmp, kev_date, eol_date, data_format=2) -> str:
    """Build a valid synthetic data dir under tmp; return its path."""
    dest = Path(tmp) / "data"
    build(dest, kev_date, eol_date, data_format)
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


# The fixture inventory plus parts and their Parent column, for the
# classification views. "Demo OS 1.0" is past end of life in the fixture data.
PARENT_HEADER = FIXTURE_HEADER + ["Parent"]
PARENT_ROWS = [r + [""] for r in FIXTURE_ROWS] + [
    ["Security Update for Demo OS 1.0 (KB5000001)", "1", "Acme Software",
     "gil", "", ""],
    ["Demo Addon", "1", "Acme Software", "hal", "", "Demo OS 1.0"],
    ["Lone Addon", "1", "Acme Software", "ida", "", "Nothing Here"],
    [EVIL + " Suite", "1", "Acme Software", "jon", "", ""],
    ["Evil Child", "1", "Acme Software", "kim", "", EVIL + " Suite"],
    [SCRIPT + " Suite", "1", "Acme Software", "lee", "", ""],
    ["Script Child", "1", "Acme Software", "max", "", SCRIPT + " Suite"],
    ["Gone Child", "1", "Acme Software", "ned", "", "Demo OS 2.0"],
]


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
