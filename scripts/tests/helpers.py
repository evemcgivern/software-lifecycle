from __future__ import annotations

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
