"""Build the synthetic data directory used by the tests.

All content is hand-written and fictional. Run this file to regenerate the
committed copy under fixtures/data/.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMITTED = HERE / "fixtures" / "data"
COMMITTED_KEV_DATE = "2026-10-22"
COMMITTED_EOL_DATE = "2026-10-20"

ALIASES = {
    "format": 1,
    "aliases": [
        {"key": "example sql", "match": "exact", "product": "examplesql",
         "version_from": "version"},
        {"key": "demo os", "match": "prefix", "product": "demoos",
         "version_from": "name"},
        # Added for the demo estate (examples/); every product is fictional.
        {"key": "tidewater suite", "match": "exact",
         "product": "tidewatersuite", "version_from": "version"},
        {"key": "brightline editor", "match": "exact",
         "product": "brightlineeditor", "version_from": "version"},
        {"key": "mapleton reports", "match": "exact",
         "product": "mapletonreports", "version_from": "version"},
        {"key": "ironwood scheduler", "match": "exact",
         "product": "ironwoodscheduler", "version_from": "version"},
        {"key": "northwind gateway", "match": "exact",
         "product": "northwindgateway", "version_from": "version",
         "kev": {"vendor": "Example Corp", "product": "Gateway Server"}},
        {"key": "quillbase database", "match": "exact",
         "product": "quillbase", "version_from": "version",
         "build_map": {"12.0.6024": "2014", "15.0.2000": "2019"}},
        {"key": "harborview crm", "match": "exact",
         "product": "harborviewcrm", "version_from": "version"},
        {"key": "pinecone archive", "match": "exact",
         "product": "pineconearchive", "version_from": "version"},
        {"key": "redwood backup", "match": "exact",
         "product": "redwoodbackup", "version_from": "version"},
        {"key": "copperfield notes", "match": "exact",
         "product": "copperfieldnotes", "version_from": "version"},
        {"key": "lantern viewer", "match": "exact",
         "product": "lanternviewer", "version_from": "version"},
        # Two products claim the name "Orbit Client": a planted AMBIGUOUS.
        {"key": "orbit", "match": "prefix", "product": "tidewatersuite",
         "version_from": "version"},
        {"key": "orbit client", "match": "prefix",
         "product": "mapletonreports", "version_from": "version"},
    ],
}

PROFILES = {
    "format": 1,
    "profiles": {
        "demo": {"status": "Unverified",
                 "columns": {"name": ["Product"], "version": ["Version"]}},
    },
}

EOL = {
    "examplesql.json": [
        {"cycle": "14", "eol": True, "support": False},
        {"cycle": "15", "eol": "2026-12-31", "support": "2024-12-31",
         "extendedSupport": "2028-12-31"},
        {"cycle": "16", "eol": False, "support": True},
    ],
    "demoos.json": [
        {"cycle": "1.0", "eol": "2025-06-30", "support": "2024-06-30"},
        {"cycle": "2.0", "eol": "2030-01-31", "support": "2028-01-31"},
    ],
    # Demo estate products. Checked on 2026-10-24 with a 12 month window
    # (ends 2027-10-24): tidewater cycle 1 ends on the check date, cycle 2 on
    # the last day of the window, cycle 3 one day after it.
    "tidewatersuite.json": [
        {"cycle": "1", "eol": "2026-10-24", "support": "2025-10-24"},
        {"cycle": "2", "eol": "2027-10-24", "support": "2026-01-01"},
        {"cycle": "3", "eol": "2027-10-25", "support": "2027-01-01"},
        {"cycle": "4", "eol": "2026-03-01", "support": "2025-03-01"},
        {"cycle": "5", "eol": "2027-03-15", "support": "2026-03-15"},
        {"cycle": "6", "eol": "2031-01-01", "support": "2029-01-01"},
    ],
    # Same end date, opposite support flag: 7 is mainstream_ended, 8 is
    # supported.
    "brightlineeditor.json": [
        {"cycle": "7", "eol": "2029-01-01", "support": False},
        {"cycle": "8", "eol": "2029-01-01", "support": True},
    ],
    # No end-of-life date at all (the key is absent).
    "mapletonreports.json": [
        {"cycle": "3", "support": True},
    ],
    "ironwoodscheduler.json": [
        {"cycle": "2", "eol": "2028-05-31", "support": True},
    ],
    "northwindgateway.json": [
        {"cycle": "4", "eol": "2025-12-31", "support": "2024-12-31"},
        {"cycle": "5", "eol": "2030-12-31", "support": "2029-12-31"},
    ],
    "quillbase.json": [
        {"cycle": "2014", "eol": "2024-07-09", "support": "2019-07-09"},
        {"cycle": "2019", "eol": "2030-01-08", "support": "2028-02-29"},
    ],
    "harborviewcrm.json": [
        {"cycle": "5", "eol": "2028-01-01", "support": True},
    ],
    "pineconearchive.json": [
        {"cycle": "2", "eol": "2027-02-28", "support": "2025-12-31"},
    ],
    "redwoodbackup.json": [
        {"cycle": "1", "eol": "2025-01-31", "support": "2024-01-31"},
        {"cycle": "3", "eol": "2030-06-30", "support": "2028-06-30"},
    ],
    "copperfieldnotes.json": [
        {"cycle": "2", "eol": "2031-03-31", "support": "2029-03-31"},
    ],
    "lanternviewer.json": [
        {"cycle": "11", "eol": False, "support": True},
    ],
}


def canonical(obj) -> bytes:
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True)
    return (text + "\n").encode("ascii")


def _iso(value) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)


def data_files(kev_date, eol_date) -> dict:
    """Relative path -> bytes for every file except the manifest."""
    kev = {
        "catalogVersion": "2026.10.22",
        "dateReleased": _iso(kev_date),
        "license": "CC0 1.0",
        "entries": [
            {"cveID": "CVE-2099-0001", "vendorProject": "Example Vendor",
             "product": "Example SQL", "dateAdded": "2026-09-01"},
            {"cveID": "CVE-2099-0002", "vendorProject": "Example Corp",
             "product": "Gateway Server", "dateAdded": "2026-08-15"},
        ],
    }
    files = {
        "aliases.json": canonical(ALIASES),
        "profiles.json": canonical(PROFILES),
        "kev.json": canonical(kev),
    }
    for name, cycles in EOL.items():
        files["eol/" + name] = canonical(cycles)
    return files


def manifest_bytes(files: dict, kev_date, eol_date) -> bytes:
    listing = {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        for name, data in files.items()
    }
    manifest = {
        "data_format": 1,
        "release_id": "fixture-1",
        "min_tool_version": "0.1.0",
        "upstream_commit": "0" * 40,
        "kev_catalog_version": "2026.10.22",
        "kev_date": _iso(kev_date),
        "eol_date": _iso(eol_date),
        "files": listing,
    }
    return canonical(manifest)


def build(dest, kev_date=COMMITTED_KEV_DATE,
          eol_date=COMMITTED_EOL_DATE) -> Path:
    dest = Path(dest)
    files = data_files(kev_date, eol_date)
    for name, data in files.items():
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (dest / "manifest.json").write_bytes(
        manifest_bytes(files, kev_date, eol_date))
    return dest


def resign(dest) -> None:
    """Rewrite manifest.json from the files now on disk (listing-matched)."""
    dest = Path(dest)
    manifest = json.loads((dest / "manifest.json").read_bytes())
    files = {name: (dest / name).read_bytes() for name in manifest["files"]}
    (dest / "manifest.json").write_bytes(
        manifest_bytes(files, manifest["kev_date"], manifest["eol_date"]))


if __name__ == "__main__":
    build(COMMITTED)
