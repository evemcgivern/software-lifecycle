#!/usr/bin/env python3
"""Build the Claude Desktop extension package (.mcpb) for swlc_mcp.py.

Run it as `python3 tools/build_mcpb.py --out DIR`. It writes
DIR/software-lifecycle-<version>.mcpb (default DIR: dist/, which git
ignores), then prints every file in it and the SHA-256 of the package.

The package is a zip file. Its layout matches the repo root, so
swlc_mcp.py finds software_lifecycle.py, swlc/, data/ and VERSION next to
it, as it does in a clone. Only files on the allow-list go in; any other
file found in a folder that is copied (a stray .csv in data/, say) stops
the build. The same sources give the same bytes: fixed timestamps, sorted
entries, fixed permissions and LF line endings. The version comes from
VERSION and is written into manifest.json and pyproject.toml here.

Standard library only, no network. The package is unsigned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Package path -> source path, relative to the repo root.
FIXED = {
    "manifest.json": "mcpb/manifest.json",
    "pyproject.toml": "mcpb/pyproject.toml",
    "README.md": "mcpb/README.md",
    "swlc_mcp.py": "swlc_mcp.py",
    "software_lifecycle.py": "software_lifecycle.py",
    "VERSION": "VERSION",
    "LICENSE": "LICENSE",
    "THIRD-PARTY.md": "THIRD-PARTY.md",
}
# Folders copied whole: (folder, allowed package-path pattern).
TREES = (
    ("swlc", re.compile(r"swlc/[a-z_]+\.py")),
    ("data", re.compile(r"data/(?:eol/)?[a-z0-9][a-z0-9._-]*\.json")),
)
# Never copied and never an error: the interpreter's cache and macOS
# Finder files.
SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {".DS_Store"}
# A last check on every path, whatever the patterns above say.
REFUSED = re.compile(r"(?:^|/)(?:tests?|examples|docs|\.github|\.git|"
                     r"swlc-out[^/]*)(?:/|$)|\.csv$|"
                     r"(?:^|/)report\.(?:md|csv|json)$", re.I)
DATE = (1980, 1, 1, 0, 0, 0)
MODE = 0o644


class BuildError(Exception):
    """A file that may not go into the package, or a bad source."""


def version(root: Path) -> str:
    text = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", text):
        raise BuildError("VERSION is not a plain x.y.z version: %r" % text)
    return text


def collect(root: Path) -> dict:
    """Return {package path: source Path}, or raise BuildError."""
    files = {name: root / src for name, src in FIXED.items()}
    for folder, allowed in TREES:
        base = root / folder
        if not base.is_dir():
            raise BuildError("missing folder: %s" % folder)
        for path in sorted(base.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if set(path.relative_to(root).parts) & SKIP_DIRS:
                continue
            # Any link stops the build, a linked folder included.
            if path.is_symlink():
                raise BuildError("a link, not on the allow-list: %s" % rel)
            if path.is_dir() or path.name in SKIP_FILES:
                continue
            if not path.is_file() \
                    or not allowed.fullmatch(rel):
                raise BuildError("not on the allow-list: %s" % rel)
            files[rel] = path
    for name, path in files.items():
        if REFUSED.search(name):
            raise BuildError("refused path: %s" % name)
        if path.is_symlink() or not path.is_file():
            raise BuildError("missing or not a regular file: %s" % name)
    return files


def content(name: str, path: Path, ver: str) -> bytes:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    if name == "manifest.json":
        manifest = json.loads(raw.decode("utf-8"))
        if "version" in manifest:
            raise BuildError("mcpb/manifest.json must not hold a version; "
                             "it comes from VERSION")
        out = {}
        for key, value in manifest.items():
            out[key] = value
            if key == "name":
                out["version"] = ver
        return (json.dumps(out, indent=2, ensure_ascii=False)
                + "\n").encode("utf-8")
    if name == "pyproject.toml":
        text = raw.decode("utf-8")
        if re.search(r"^version\s*=", text, re.M):
            raise BuildError("mcpb/pyproject.toml must not hold a version; "
                             "it comes from VERSION")
        text, n = re.subn(r"^(name = .*)$", r'\1\nversion = "%s"' % ver,
                          text, count=1, flags=re.M)
        if n != 1:
            raise BuildError("mcpb/pyproject.toml has no name line")
        return text.encode("utf-8")
    return raw


def build(out_dir: Path, root: Path = ROOT) -> tuple:
    """Write the package. Return (package path, sorted names, SHA-256)."""
    ver = version(root)
    files = collect(root)
    names = sorted(files)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ("software-lifecycle-%s.mcpb" % ver)
    tmp = target.with_name(target.name + ".part")
    with zipfile.ZipFile(str(tmp), "w") as zf:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100000 | MODE) << 16
            zf.writestr(info, content(name, files[name], ver))
    tmp.replace(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return target, names, digest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=str(ROOT / "dist"),
                        help="folder for the .mcpb file (default: dist/)")
    args = parser.parse_args(argv)
    try:
        target, names, digest = build(Path(args.out))
    except (BuildError, OSError, ValueError) as exc:
        sys.stderr.write("build_mcpb: refused: %s\n" % exc)
        return 1
    for name in names:
        print(name)
    print("%d files" % len(names))
    print("package %s" % target)
    print("sha256 %s" % digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
