from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .errors import DataError
from .matching import _check as _check_alias
from .normalize import normalize_name

SUPPORTED_DATA_FORMATS = (1, 2)
KEV_WARN_DAYS = 3
KEV_STALE_DAYS = 7
EOL_WARN_DAYS = 30

_REQUIRED = ("aliases.json", "profiles.json", "kev.json")
# Format 2 adds the product catalog and the hand-kept curation file.
_REQUIRED_V2 = _REQUIRED + ("products.json", "curation.json")
_NAME_RE = re.compile(r"(?:aliases|profiles|kev)\.json|eol/[a-z0-9][a-z0-9_.-]*\.json")
_NAME_RE_V2 = re.compile(
    r"(?:aliases|profiles|kev|products|curation)\.json"
    r"|eol/[a-z0-9][a-z0-9_.-]*\.json")
_ID_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*")
NO_CATALOG_WARNING = ("This data release has no product catalog; "
                      "generated matching is off.")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SHA_RE = re.compile(r"[0-9a-f]{64}")
_VERSION_RE = re.compile(r"\d{1,6}(?:\.\d{1,6}){0,2}")
_IGNORED_NAMES = frozenset((".DS_Store", "Thumbs.db", "desktop.ini"))
FUTURE_TOLERANCE_DAYS = 1
_MANIFEST = "manifest.json"


@dataclass
class Data:
    release_id: str
    file_hashes: dict
    aliases: list
    products: dict
    kev: list
    kev_catalog_version: str
    kev_age_days: int
    eol_age_days: int
    kev_current: bool = True
    warnings: list = field(default_factory=list)
    profiles: dict = field(default_factory=dict)
    # Format 2 only: id -> record from products.json, and the validated
    # curation.json. Both are None for a format 1 data folder.
    catalog: dict | None = None
    curation: dict | None = None


def tool_version() -> str:
    """The skill's VERSION file, at the repo root."""
    path = Path(__file__).resolve().parents[1] / "VERSION"
    try:
        text = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        raise DataError("VERSION file is missing or unreadable")
    if not _VERSION_RE.fullmatch(text):
        raise DataError("VERSION file is not a version number")
    return text


def _version_tuple(text: str) -> tuple:
    nums = [int(p) for p in text.split(".")]
    return tuple(nums + [0] * (3 - len(nums)))


# --- schema checks (public: refresh_data.py reuses them) ------------------

def _date(value, where: str) -> date:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise DataError("%s: expected a YYYY-MM-DD date" % where)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise DataError("%s: not a real calendar date" % where)


def _text(value, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataError("%s: expected a non-empty string" % where)
    return value


def _date_or_flag(value, where: str):
    """A date string, true, false, or absent/null."""
    if value is None or isinstance(value, bool):
        return value
    return _date(value, where)


def validate_kev(obj) -> list:
    """Check a parsed kev.json; return entries as normalized dicts."""
    if not isinstance(obj, dict):
        raise DataError("top level must be an object")
    _text(obj.get("catalogVersion"), "catalogVersion")
    _date(obj.get("dateReleased"), "dateReleased")
    entries = obj.get("entries")
    if not isinstance(entries, list):
        raise DataError("entries: expected a list")
    out = []
    for pos, item in enumerate(entries, 1):
        where = "entries[%d]" % pos
        if not isinstance(item, dict):
            raise DataError("%s: expected an object" % where)
        cve = _text(item.get("cveID"), where + ".cveID")
        vendor = _text(item.get("vendorProject"), where + ".vendorProject")
        product = _text(item.get("product"), where + ".product")
        added = _date(item.get("dateAdded"), where + ".dateAdded")
        out.append({"vendor": normalize_name(vendor),
                    "product": normalize_name(product),
                    "date_added": added, "cve": cve})
    return out


def validate_eol(obj) -> list:
    """Check a parsed eol/<product>.json; return cycle dicts with dates parsed."""
    if not isinstance(obj, list):
        raise DataError("top level must be a list of cycles")
    # Boolean polarity follows endoflife.date: "eol": true means past end
    # of life, false means none announced; "support" and "extendedSupport"
    # true mean that support is still ongoing, false that it has ended.
    out = []
    for pos, item in enumerate(obj, 1):
        where = "cycles[%d]" % pos
        if not isinstance(item, dict):
            raise DataError("%s: expected an object" % where)
        out.append({
            "cycle": _text(item.get("cycle"), where + ".cycle"),
            "eol": _date_or_flag(item.get("eol"), where + ".eol"),
            "support": _date_or_flag(item.get("support"), where + ".support"),
            "extended": _date_or_flag(
                item.get("extendedSupport"), where + ".extendedSupport"),
        })
    return out


def _validate_aliases(obj) -> list:
    if not isinstance(obj, dict) or not isinstance(obj.get("aliases"), list):
        raise DataError("expected an object with an 'aliases' list")
    for pos, entry in enumerate(obj["aliases"], 1):
        _check_alias(entry, pos)
    return obj["aliases"]


def _validate_profiles(obj) -> dict:
    if not isinstance(obj, dict):
        raise DataError("top level must be an object")
    profiles = obj.get("profiles", {})
    if not isinstance(profiles, dict):
        raise DataError("'profiles' must be an object")
    for pname, prof in profiles.items():
        cols = prof.get("columns") if isinstance(prof, dict) else None
        if not isinstance(cols, dict) or not all(
                isinstance(k, str) and isinstance(v, list)
                and all(isinstance(i, str) for i in v)
                for k, v in cols.items()):
            raise DataError(
                "a profile's 'columns' must map names to lists of strings")
    return profiles


def _ident(value, where: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise DataError("%s: expected a product id" % where)
    return value


def _keys(obj, allowed: tuple, where: str) -> None:
    if not isinstance(obj, dict):
        raise DataError("%s: expected an object" % where)
    if set(obj) != set(allowed):
        raise DataError("%s: unexpected or missing keys" % where)


def _is_format_one(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) \
        and value == 1


def _str_list(value, where: str, lower: bool = False) -> list:
    """A strictly sorted list of non-empty strings (so no duplicates)."""
    if not isinstance(value, list):
        raise DataError("%s: expected a list" % where)
    for item in value:
        if not isinstance(item, str) or not item.strip() \
                or item != item.strip() or (lower and item != item.lower()):
            raise DataError("%s: expected plain non-empty %sstrings"
                            % (where, "lowercase " if lower else ""))
    if any(a >= b for a, b in zip(value, value[1:])):
        raise DataError("%s: must be sorted with no duplicates" % where)
    return value


def validate_products(obj) -> dict:
    """Check a parsed products.json; return {product id: record}."""
    _keys(obj, ("format", "products"), "top level")
    if not _is_format_one(obj["format"]):
        raise DataError("format: expected 1")
    items = obj["products"]
    if not isinstance(items, list):
        raise DataError("products: expected a list")
    out, last = {}, None
    for pos, item in enumerate(items, 1):
        where = "products[%d]" % pos
        _keys(item, ("id", "title", "category", "vendors", "namespaces"),
              where)
        pid = _ident(item["id"], where + ".id")
        if last is not None and pid <= last:
            raise DataError("%s: ids must be sorted with no duplicates"
                            % where)
        last = pid
        _text(item["title"], where + ".title")
        _text(item["category"], where + ".category")
        _str_list(item["vendors"], where + ".vendors")
        _str_list(item["namespaces"], where + ".namespaces", lower=True)
        out[pid] = item
    return out


def _https(value, where: str) -> str:
    if (not isinstance(value, str) or not value.startswith("https://")
            or len(value) <= len("https://") or len(value) > 500
            or any(c.isspace() or ord(c) < 33 or ord(c) > 126
                   for c in value)):
        raise DataError("%s: expected an https URL" % where)
    return value


def validate_curation(obj, product_ids=None) -> dict:
    """Check a parsed curation.json; return it. With product_ids, every
    product it names must be in that collection."""
    _keys(obj, ("format", "publisher_aliases", "single_word_allowlist",
                "exclusions", "generated_off"), "top level")
    if not _is_format_one(obj["format"]):
        raise DataError("format: expected 1")
    named = []

    aliases = obj["publisher_aliases"]
    if not isinstance(aliases, dict):
        raise DataError("publisher_aliases: expected an object")
    for pid, phrases in aliases.items():
        where = "publisher_aliases entry"
        _ident(pid, where)
        if not isinstance(phrases, list) or not phrases:
            raise DataError("%s: expected a non-empty list" % where)
        _str_list(phrases, where, lower=True)
        named.append(pid)

    allow = obj["single_word_allowlist"]
    if not isinstance(allow, list):
        raise DataError("single_word_allowlist: expected a list")
    seen = set()
    for pos, item in enumerate(allow, 1):
        where = "single_word_allowlist[%d]" % pos
        _keys(item, ("product", "reason", "source"), where)
        pid = _ident(item["product"], where + ".product")
        if pid in seen:
            raise DataError("%s: product listed twice" % where)
        seen.add(pid)
        _text(item["reason"], where + ".reason")
        _https(item["source"], where + ".source")
        named.append(pid)

    excl = obj["exclusions"]
    if not isinstance(excl, list):
        raise DataError("exclusions: expected a list")
    seen = set()
    for pos, item in enumerate(excl, 1):
        where = "exclusions[%d]" % pos
        _keys(item, ("product", "name", "publisher", "reason", "gold"), where)
        pid = _ident(item["product"], where + ".product")
        name = _text(item["name"], where + ".name")
        pub = item["publisher"]
        if not isinstance(pub, str) or pub != pub.lower() \
                or pub != pub.strip() or any(c.isspace() for c in pub):
            raise DataError("%s.publisher: expected a lowercase token or "
                            "an empty string" % where)
        _text(item["reason"], where + ".reason")
        gold = _text(item["gold"], where + ".gold")
        if gold.count("|") != 2:
            raise DataError("%s.gold: expected name|publisher|version"
                            % where)
        if (pid, name, pub) in seen:
            raise DataError("%s: duplicate exclusion" % where)
        seen.add((pid, name, pub))
        named.append(pid)

    off = obj["generated_off"]
    if not isinstance(off, list):
        raise DataError("generated_off: expected a list")
    _str_list(off, "generated_off")
    for pid in off:
        _ident(pid, "generated_off")
    named.extend(off)

    if product_ids is not None:
        known = set(product_ids)
        if any(pid not in known for pid in named):
            raise DataError("a product named here is not in the catalog")
    return obj


# --- manifest and file verification ---------------------------------------

def _parse(raw: bytes, name: str):
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError, MemoryError):
        raise DataError("%s: not valid UTF-8 JSON" % name)


def _wrap(name: str, func, *args):
    try:
        return func(*args)
    except DataError as exc:
        raise DataError("%s: %s" % (name, exc)) from None


def _read_manifest(data_dir: str) -> dict:
    path = os.path.join(data_dir, _MANIFEST)
    if os.path.islink(path) or not os.path.isfile(path):
        raise DataError("%s is missing" % _MANIFEST)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        raise DataError("%s cannot be read" % _MANIFEST)
    m = _parse(raw, _MANIFEST)

    def check(m):
        if not isinstance(m, dict):
            raise DataError("top level must be an object")
        if m.get("data_format") not in SUPPORTED_DATA_FORMATS or isinstance(
                m.get("data_format"), bool):
            raise DataError("data format is not supported by this tool")
        fmt = m["data_format"]
        _text(m.get("release_id"), "release_id")
        _text(m.get("kev_catalog_version"), "kev_catalog_version")
        _text(m.get("upstream_commit"), "upstream_commit")
        _date(m.get("kev_date"), "kev_date")
        _date(m.get("eol_date"), "eol_date")
        minimum = m.get("min_tool_version")
        if not isinstance(minimum, str) or not _VERSION_RE.fullmatch(minimum):
            raise DataError("min_tool_version: expected a version number")
        files = m.get("files")
        if not isinstance(files, dict) or not files:
            raise DataError("files: expected a non-empty object")
        for name, meta in files.items():
            if not (_NAME_RE_V2 if fmt == 2 else _NAME_RE).fullmatch(name):
                raise DataError("files: a listed file name is not allowed")
            if not isinstance(meta, dict):
                raise DataError("files: bad entry for %s" % name)
            sha, size = meta.get("sha256"), meta.get("size")
            if not isinstance(sha, str) or not _SHA_RE.fullmatch(sha):
                raise DataError("files: bad sha256 for %s" % name)
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise DataError("files: bad size for %s" % name)
        for name in (_REQUIRED_V2 if fmt == 2 else _REQUIRED):
            if name not in files:
                raise DataError("files: %s is not listed" % name)

    _wrap(_MANIFEST, check, m)
    if _version_tuple(m["min_tool_version"]) > _version_tuple(tool_version()):
        raise DataError(
            "data needs tool version %s or newer; this is %s"
            % (m["min_tool_version"], tool_version()))
    return m


def _listing(data_dir: str) -> set:
    """Every file under data_dir, as '/'-joined relative names."""
    found = set()
    for root, dirs, files in os.walk(data_dir):
        for d in dirs:
            if os.path.islink(os.path.join(root, d)):
                raise DataError("%s: symbolic links are not allowed" % d)
        for f in files:
            if f in _IGNORED_NAMES:
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, data_dir).replace(os.sep, "/")
            if os.path.islink(full):
                raise DataError("%s: symbolic links are not allowed" % rel)
            found.add(rel)
    return found


def _verify(data_dir: str) -> tuple:
    """Check the manifest and every file; return (manifest, {name: bytes})."""
    if not os.path.isdir(data_dir):
        raise DataError("data directory not found")
    manifest = _read_manifest(data_dir)
    listed = manifest["files"]
    extra = _listing(data_dir) - set(listed) - {_MANIFEST}
    if extra:
        raise DataError("%s: file is not listed in the manifest"
                        % sorted(extra)[0])
    blobs = {}
    for name in sorted(listed):
        meta = listed[name]
        path = os.path.join(data_dir, *name.split("/"))
        if not os.path.isfile(path):
            raise DataError("%s: listed in the manifest but missing" % name)
        if os.path.getsize(path) != meta["size"]:
            raise DataError("%s: size does not match the manifest" % name)
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError:
            raise DataError("%s: cannot be read" % name)
        if len(raw) != meta["size"]:
            raise DataError("%s: size does not match the manifest" % name)
        if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise DataError("%s: SHA-256 does not match the manifest" % name)
        blobs[name] = raw
    return manifest, blobs


def _parse_all(blobs: dict) -> tuple:
    """Returns (aliases, kev, eol products, profiles, catalog, curation);
    catalog and curation are None when products.json is not in blobs."""
    aliases = _wrap("aliases.json", _validate_aliases,
                    _parse(blobs["aliases.json"], "aliases.json"))
    profiles = _wrap("profiles.json", _validate_profiles,
                     _parse(blobs["profiles.json"], "profiles.json"))
    kev = _wrap("kev.json", validate_kev,
                _parse(blobs["kev.json"], "kev.json"))
    products = {}
    for name in sorted(blobs):
        if name.startswith("eol/"):
            products[name[4:-5]] = _wrap(
                name, validate_eol, _parse(blobs[name], name))
    catalog = curation = None
    if "products.json" in blobs:
        catalog = _wrap("products.json", validate_products,
                        _parse(blobs["products.json"], "products.json"))
        curation = _wrap("curation.json", validate_curation,
                         _parse(blobs["curation.json"], "curation.json"))
    return aliases, kev, products, profiles, catalog, curation


def load_data(data_dir: str, as_of: date) -> Data:
    """Verify the manifest and files first, then parse. Raises DataError."""
    manifest, blobs = _verify(data_dir)
    aliases, kev, products, profiles, catalog, curation = _parse_all(blobs)
    kev_age = (as_of - date.fromisoformat(manifest["kev_date"])).days
    eol_age = (as_of - date.fromisoformat(manifest["eol_date"])).days
    warnings = []
    future = -FUTURE_TOLERANCE_DAYS
    if kev_age < future:
        warnings.append("KEV snapshot date is in the future; "
                        "it is not current")
    elif kev_age > KEV_STALE_DAYS:
        warnings.append(
            "KEV snapshot is %d days old; it is not current" % kev_age)
    elif kev_age > KEV_WARN_DAYS:
        warnings.append("KEV snapshot is %d days old" % kev_age)
    if eol_age < future:
        warnings.append("End-of-life snapshot date is in the future")
    elif eol_age > EOL_WARN_DAYS:
        warnings.append("End-of-life snapshot is %d days old" % eol_age)
    if catalog is None:
        warnings.append(NO_CATALOG_WARNING)
    return Data(
        release_id=manifest["release_id"],
        file_hashes={n: manifest["files"][n]["sha256"] for n in blobs},
        aliases=aliases, products=products, kev=kev,
        kev_catalog_version=manifest["kev_catalog_version"],
        kev_age_days=kev_age, eol_age_days=eol_age,
        kev_current=future <= kev_age <= KEV_STALE_DAYS,
        warnings=warnings, profiles=profiles,
        catalog=catalog, curation=curation)


def kev_match(kev: list, vendor: str, product: str) -> bool:
    """Exact match on normalized vendor and product; empty never matches."""
    v, p = normalize_name(vendor or ""), normalize_name(product or "")
    if not v or not p:
        return False
    return any(e["vendor"] == v and e["product"] == p for e in kev)


def verify_data(data_dir: str) -> int:
    """For verify-data: hashes plus schemas, no staleness. 0 ok, 4 failed."""
    try:
        manifest, blobs = _verify(data_dir)
        _parse_all(blobs)
    except DataError as exc:
        print("Data check failed: %s" % exc, file=sys.stderr)
        return 4
    print("Data check passed: release %s, %d files verified"
          % (manifest["release_id"], len(blobs)))
    return 0
