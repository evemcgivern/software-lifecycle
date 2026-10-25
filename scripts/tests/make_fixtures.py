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
        {"cycle": "14", "eol": True, "support": True},
        {"cycle": "15", "eol": "2026-12-31", "support": "2024-12-31",
         "extendedSupport": "2028-12-31"},
        {"cycle": "16", "eol": False, "support": False},
    ],
    "demoos.json": [
        {"cycle": "1.0", "eol": "2025-06-30", "support": "2024-06-30"},
        {"cycle": "2.0", "eol": "2030-01-31", "support": "2028-01-31"},
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
