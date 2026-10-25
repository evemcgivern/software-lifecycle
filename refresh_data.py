#!/usr/bin/env python3
"""Refresh the CISA KEV and endoflife.date snapshots.

This is the only file in the project that opens a network connection. The
tool itself (swlc/) never does. Each command writes canonical JSON (sorted
keys, indent 2, ASCII, trailing newline) and never writes a fetch time:
dates come from the feeds' own fields or from explicit flags.

Commands:
  kev --out DIR                       download KEV, write DIR/kev.json
  eol --upstream-commit SHA --out DIR build DIR/<product>.json at SHA
  manifest --dir DIR ...              rebuild DIR/manifest.json
  check-kev --new FILE --old FILE     publish gate for a new kev.json
  eol-summary --new DIR --old DIR     change summary for the weekly PR

Exit codes: 0 ok; 1 gate failed or refresh failed; 2 usage error.
Messages are fixed text plus counts and product ids, never feed content.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import ssl
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from swlc.data import validate_eol, validate_kev  # noqa: E402
from swlc.errors import DataError  # noqa: E402

KEV_URL = ("https://www.cisa.gov/sites/default/files/feeds/"
           "known_exploited_vulnerabilities.json")
EOL_REPO = "endoflife-date/endoflife.date"
EOL_ARCHIVE_URL = ("https://codeload.github.com/endoflife-date/"
                   "endoflife.date/tar.gz/%s")
USER_AGENT = ("software-lifecycle-refresh/1 "
              "(+https://github.com/evemcgivern/software-lifecycle)")
TIMEOUT = 60
KEV_MAX_BYTES = 32 * 1024 * 1024
ARCHIVE_MAX_BYTES = 16 * 1024 * 1024
UNPACKED_MAX_BYTES = 128 * 1024 * 1024
PRODUCT_MAX_BYTES = 1024 * 1024
PRODUCTS_MAX = 5000

# The KEV feed has no licence field. CISA publishes the catalog under CC0
# 1.0 (https://github.com/cisagov/kev-data), so the note is a constant that
# this script writes into kev.json, and the daily gate checks it is there.
LICENCE_NOTE = "CC0 1.0"
DATA_FORMAT = 1
MIN_TOOL_VERSION = "0.1.0"
COUNT_TOLERANCE = 0.20
EOL_CHANGE_SHARE = 0.10

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PRODUCT_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*")
_CYCLE_RE = re.compile(r"[a-z0-9.\-+_]+")  # upstream's own releaseCycle rule
_CATALOG_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z.\-]{0,31}")
_RELEASE_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z._\-]{0,63}")
_REQUIRED = ("aliases.json", "profiles.json", "kev.json")


class RefreshError(Exception):
    """A refresh step failed. The message is fixed text, safe to print."""


def canonical(obj) -> bytes:
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True)
    return (text + "\n").encode("ascii")


# --- fetching ---------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RefreshError("the server sent a redirect; redirects are refused")


def fetch(url: str, max_bytes: int, timeout: float = TIMEOUT,
          allow_loopback_http: bool = False) -> bytes:
    """GET one URL over HTTPS with a size cap and no redirects.

    allow_loopback_http exists for the tests: it lets plain HTTP reach
    127.0.0.1 and nothing else.
    """
    parts = urllib.parse.urlsplit(url)
    loopback = (allow_loopback_http and parts.scheme == "http"
                and parts.hostname == "127.0.0.1")
    if not (parts.scheme == "https" and parts.hostname) and not loopback:
        raise RefreshError("only https URLs are fetched")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with opener.open(request, timeout=timeout) as resp:
            if resp.status != 200:
                raise RefreshError("the server answered HTTP %d" % resp.status)
            length = resp.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise RefreshError("the download is larger than %d bytes"
                                   % max_bytes)
            chunks, total = [], 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RefreshError("the download is larger than %d bytes"
                                       % max_bytes)
                chunks.append(chunk)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise RefreshError("the server answered HTTP %d" % exc.code) from None
    except (urllib.error.URLError, OSError, ValueError):
        raise RefreshError("the download failed") from None
    return b"".join(chunks)


# --- KEV --------------------------------------------------------------------

def _feed_text(item, key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RefreshError("KEV feed: an entry has no %s" % key)
    return value


def kev_from_feed(raw: bytes) -> dict:
    """Turn the CISA feed into kev.json: ids, names and dates only."""
    try:
        feed = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        raise RefreshError("KEV feed: not valid UTF-8 JSON") from None
    if not isinstance(feed, dict) or not isinstance(
            feed.get("vulnerabilities"), list):
        raise RefreshError("KEV feed: no vulnerabilities list")
    released = feed.get("dateReleased")
    if not isinstance(released, str) or not _DATE_RE.match(released):
        raise RefreshError("KEV feed: dateReleased does not start with a date")
    version = feed.get("catalogVersion")
    if not isinstance(version, str) or not _CATALOG_RE.fullmatch(version):
        raise RefreshError("KEV feed: catalogVersion is missing or unusual")
    vulns = feed["vulnerabilities"]
    count = feed.get("count")
    if isinstance(count, bool) or count != len(vulns):
        raise RefreshError("KEV feed: count does not match the entries")
    entries, seen = [], set()
    for item in vulns:
        if not isinstance(item, dict):
            raise RefreshError("KEV feed: an entry is not an object")
        entry = {key: _feed_text(item, key) for key in
                 ("cveID", "vendorProject", "product", "dateAdded")}
        if entry["cveID"] in seen:
            raise RefreshError("KEV feed: a cveID appears twice")
        seen.add(entry["cveID"])
        entries.append(entry)
    entries.sort(key=lambda e: e["cveID"])
    obj = {"catalogVersion": version, "dateReleased": released[:10],
           "license": LICENCE_NOTE, "entries": entries}
    try:
        validate_kev(obj)
    except DataError as exc:
        raise RefreshError("KEV feed fails the schema check: %s" % exc) from None
    return obj


def check_kev(new, old, allow_removed: bool = False) -> list:
    """Publish gate. Returns failure reasons; an empty list means publish."""
    fails = []
    try:
        validate_kev(new)
    except DataError as exc:
        fails.append("new KEV file fails the schema check: %s" % exc)
    try:
        validate_kev(old)
    except DataError as exc:
        fails.append("previous KEV file fails the schema check: %s" % exc)
    if fails:
        return fails
    new_ids = {e["cveID"] for e in new["entries"]}
    old_ids = {e["cveID"] for e in old["entries"]}
    low = len(old_ids) * (1 - COUNT_TOLERANCE)
    high = len(old_ids) * (1 + COUNT_TOLERANCE)
    if not old_ids:
        fails.append("previous KEV file has no entries to compare against")
    elif not low <= len(new_ids) <= high:
        fails.append("entry count %d is outside 20%% of the previous %d"
                     % (len(new_ids), len(old_ids)))
    removed = old_ids - new_ids
    if removed and not allow_removed:
        fails.append("entries removed since the previous release: %d"
                     % len(removed))
    if new.get("license") != LICENCE_NOTE:
        fails.append("the CC0 licence note is missing from the new KEV file")
    return fails


def _md(text: str) -> str:
    """Make feed text inert inside a Markdown table cell."""
    text = " ".join(str(text).split())[:120]
    return re.sub(r"[^0-9A-Za-z .,_:/()+-]", "", text)


def kev_digest(new, old) -> str:
    """Markdown list of entries added since old: cve id, vendor, product."""
    old_ids = {e["cveID"] for e in old["entries"]}
    added = [e for e in new["entries"] if e["cveID"] not in old_ids]
    lines = ["## KEV entries added", "",
             "Entries added since the previous data release: %d." % len(added),
             ""]
    if added:
        lines += ["| CVE | Vendor | Product |", "| --- | --- | --- |"]
        lines += ["| %s | %s | %s |" % (_md(e["cveID"]),
                                        _md(e["vendorProject"]),
                                        _md(e["product"])) for e in added]
    return "\n".join(lines) + "\n"


# --- endoflife.date front matter --------------------------------------------
#
# Upstream product files are products/<name>.md: YAML front matter between
# two "---" lines, then page text. This is not a YAML parser. It reads one
# narrow, strict subset and refuses anything else, so an upstream format
# change stops the refresh instead of producing wrong dates.
#
# Read from the top level: permalink (the product id, as the upstream API
# uses it) and whether an eoesColumn key exists. Everything else at the top
# level is skipped. Inside the top-level "releases:" list, each item starts
# with "- key:" (at column 0 or 2 in the real files) and its other keys sit
# at the same column as that first key. Read from each item: releaseCycle,
# releaseDate, eol, eoas, eoes. Other keys and anything nested deeper are
# skipped. Page text after the closing "---" (descriptions, CC BY-SA) is
# never read.
#
# Mapping onto the snapshot, as upstream's v0 API (generate-api-v0.rb) does:
#   releaseCycle -> cycle
#   releaseDate  -> releaseDate
#   eol          -> eol: a date, or true (ended) / false (not ended)
#   eoas         -> support: a date stays a date; a boolean flips, because
#                   eoas: true means active support HAS ended, and the
#                   snapshot's support: true means support is ongoing
#   eoes         -> extendedSupport: same flip; when the product has an
#                   eoesColumn but the release has no eoes, false
#
# Values must be plain dates (YYYY-MM-DD), true or false; releaseCycle may be
# quoted. Quoted dates, anchors, tags, flow collections, block scalars,
# tabs and CRLF line ends are refused.

_TOP_RE = re.compile(r"([A-Za-z0-9_]+):(?:[ ]+(.*))?$")
_ITEM_RE = re.compile(r"( *)-( +)([A-Za-z0-9_]+):(?:[ ]+(.*))?$")
_KEY_RE = re.compile(r"( *)([A-Za-z0-9_]+):(?:[ ]+(.*))?$")
_READ = ("releaseCycle", "releaseDate", "eol", "eoas", "eoes")
_YAML_WORDS = {"true", "false", "yes", "no", "on", "off", "null", "~", "y",
               "n"}


def _bad(product: str, why: str) -> RefreshError:
    return RefreshError("endoflife.date %s: %s" % (product, why))


def _strip_comment(value: str) -> str:
    """Drop a trailing ' # comment' from an unquoted value."""
    match = re.search(r"\s#", value)
    return (value[:match.start()] if match else value).strip()


def _scalar(value, key: str, where: str):
    value = (value or "").strip()
    if not value:
        raise _bad(where, "%s has no value" % key)
    if value[0] in "\"'":
        quote = value[0]
        end = value.find(quote, 1)
        if end < 0 or "\\" in value[1:end]:
            raise _bad(where, "%s has a quoted value it cannot read" % key)
        rest = value[end + 1:].strip()
        if rest and not rest.startswith("#"):
            raise _bad(where, "%s has text after a quoted value" % key)
        text, quoted = value[1:end], True
    else:
        text, quoted = _strip_comment(value), False
    if key == "releaseCycle":
        if not _CYCLE_RE.fullmatch(text):
            raise _bad(where, "a releaseCycle has characters it cannot read")
        if not quoted and (text in _YAML_WORDS or _DATE_RE.fullmatch(text)
                           or re.fullmatch(r"[-+]?[0-9_.]+(e[-+]?[0-9]+)?",
                                           text)):
            raise _bad(where, "an unquoted releaseCycle looks like a number")
        return text
    if quoted:
        raise _bad(where, "%s is quoted; expected a plain date or "
                          "true/false" % key)
    if text in ("true", "false"):
        return text == "true"
    if not _DATE_RE.fullmatch(text):
        raise _bad(where, "%s is not a date or true/false" % key)
    try:
        date.fromisoformat(text)
    except ValueError:
        raise _bad(where, "%s is not a real calendar date" % key) from None
    return text


def _front_matter(text: str) -> list:
    if "\r" in text or text.startswith("﻿"):
        raise _bad("file", "unexpected line endings or byte-order mark")
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        raise _bad("file", "no front matter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise _bad("file", "front matter is not closed") from None
    return lines[1:end]


def _parse_releases(block: list, where: str) -> list:
    """The lines under 'releases:' -> list of {key: raw value} for _READ."""
    items, item_col, key_col, last_key = [], None, None, None
    for line in block:
        stripped = line.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("\t") or line.startswith("\t"):
            raise _bad(where, "tab indentation")
        indent = len(line) - len(stripped)
        if key_col is not None and indent > key_col:
            if last_key in _READ:
                raise _bad(where, "%s has a nested value" % last_key)
            continue  # nested content of a key this script does not read
        match = _ITEM_RE.match(line)
        if match and (item_col is None or (
                len(match.group(1)) == item_col and
                len(match.group(1)) + 1 + len(match.group(2)) == key_col)):
            item_col = len(match.group(1))
            key_col = item_col + 1 + len(match.group(2))
            items.append({})
            key, value = match.group(3), match.group(4)
        else:
            match = _KEY_RE.match(line)
            if not match or key_col is None or len(match.group(1)) != key_col:
                raise _bad(where, "a releases line has an unexpected layout")
            key, value = match.group(2), match.group(3)
        if key in items[-1]:
            raise _bad(where, "a release lists %s twice" % key)
        if key in _READ:
            if value is not None and value.strip() and value.strip()[0] in "|>[{&*!":
                raise _bad(where, "%s has a value it cannot read" % key)
            items[-1][key] = value
        else:
            items[-1][key] = None
        last_key = key
    return items


def product_from_markdown(text: str) -> tuple:
    """One upstream product file -> (product id, list of cycle dicts)."""
    lines = _front_matter(text)
    top, releases_block, current = {}, None, None
    for line in lines:
        if not line or line.startswith("#"):
            continue
        if line[0] not in " -\t":
            match = _TOP_RE.match(line)
            if not match:
                raise _bad("file", "a top-level line has an unexpected layout")
            current = match.group(1)
            if current in top:
                raise _bad("file", "a top-level key appears twice")
            top[current] = match.group(2)
            if current == "releases":
                if (match.group(2) or "").strip():
                    raise _bad("file", "releases is not a block list")
                releases_block = []
            continue
        if current == "releases":
            releases_block.append(line)
    permalink = _strip_comment(top.get("permalink") or "")
    if not permalink.startswith("/") or not _PRODUCT_RE.fullmatch(
            permalink[1:]):
        raise _bad("file", "permalink is missing or not a plain product id")
    pid = permalink[1:]
    if not releases_block:
        raise _bad(pid, "no releases list")
    cycles, seen = [], set()
    for raw in _parse_releases(releases_block, pid):
        if raw.get("releaseCycle") is None:
            raise _bad(pid, "a release has no releaseCycle")
        cycle = {"cycle": _scalar(raw["releaseCycle"], "releaseCycle", pid)}
        if cycle["cycle"] in seen:
            raise _bad(pid, "a releaseCycle appears twice")
        seen.add(cycle["cycle"])
        for key, out in (("releaseDate", "releaseDate"), ("eol", "eol")):
            if key in raw:
                cycle[out] = _scalar(raw[key], key, pid)
        for key, out in (("eoas", "support"), ("eoes", "extendedSupport")):
            if key in raw:
                value = _scalar(raw[key], key, pid)
                cycle[out] = (not value) if isinstance(value, bool) else value
        if "eoesColumn" in top and "eoes" not in raw:
            cycle["extendedSupport"] = False
        cycles.append(cycle)
    if not cycles:
        raise _bad(pid, "no releases")
    try:
        validate_eol(cycles)
    except DataError as exc:
        raise _bad(pid, "fails the schema check: %s" % exc) from None
    return pid, cycles


def eol_from_archive(raw: bytes, sha: str) -> dict:
    """GitHub's tar.gz of the upstream repo at sha -> {product id: cycles}."""
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
            unpacked = gz.read(UNPACKED_MAX_BYTES + 1)
    except (OSError, EOFError):
        raise RefreshError("endoflife.date archive is not a gzip file") from None
    if len(unpacked) > UNPACKED_MAX_BYTES:
        raise RefreshError("endoflife.date archive unpacks too large")
    prefix = "endoflife.date-%s/products/" % sha
    products = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(unpacked), mode="r:") as tar:
            if tar.pax_headers.get("comment") != sha:
                raise RefreshError(
                    "endoflife.date archive is not for the pinned commit")
            for member in tar:
                name = member.name
                if not name.startswith(prefix) or not name.endswith(".md"):
                    continue
                if "/" in name[len(prefix):]:
                    continue
                if not member.isreg():
                    raise RefreshError(
                        "endoflife.date archive has a product that is not "
                        "a regular file")
                if member.size > PRODUCT_MAX_BYTES:
                    raise RefreshError(
                        "endoflife.date archive has an oversized product")
                if len(products) >= PRODUCTS_MAX:
                    raise RefreshError(
                        "endoflife.date archive has too many products")
                data = tar.extractfile(member).read(PRODUCT_MAX_BYTES + 1)
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    raise RefreshError("endoflife.date archive has a product "
                                       "that is not UTF-8") from None
                pid, cycles = product_from_markdown(text)
                if pid in products:
                    raise RefreshError("endoflife.date archive has two "
                                       "products with id %s" % pid)
                products[pid] = cycles
    except tarfile.TarError:
        raise RefreshError("endoflife.date archive is not a tar file") from None
    if not products:
        raise RefreshError("endoflife.date archive has no product files")
    return products


# --- writing ----------------------------------------------------------------

def _empty_dir(path: str) -> Path:
    out = Path(path)
    if out.is_symlink() or (out.exists() and not out.is_dir()):
        raise RefreshError("--out is not a folder")
    if out.exists() and any(out.iterdir()):
        raise RefreshError("--out folder is not empty")
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_kev(out_dir: str, obj: dict) -> Path:
    path = _empty_dir(out_dir) / "kev.json"
    path.write_bytes(canonical(obj))
    return path


def write_eol(out_dir: str, products: dict) -> None:
    out = _empty_dir(out_dir)
    for pid in sorted(products):
        if not _PRODUCT_RE.fullmatch(pid):
            raise RefreshError("a product id is not allowed")
        (out / (pid + ".json")).write_bytes(canonical(products[pid]))


def manifest_bytes(files: dict, kev_date: str, eol_date: str,
                   upstream_commit: str, kev_catalog_version: str,
                   release_id: str) -> bytes:
    """files maps relative names to bytes; the manifest lists each one."""
    listing = {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        for name, data in files.items()
    }
    return canonical({
        "data_format": DATA_FORMAT,
        "release_id": release_id,
        "min_tool_version": MIN_TOOL_VERSION,
        "upstream_commit": upstream_commit,
        "kev_catalog_version": kev_catalog_version,
        "kev_date": kev_date,
        "eol_date": eol_date,
        "files": listing,
    })


def build_manifest(data_dir: str, kev_date: str, eol_date: str,
                   upstream_commit: str, kev_catalog_version: str,
                   release_id: str) -> bytes:
    """Write data_dir/manifest.json for aliases, profiles, kev and eol/*."""
    root = Path(data_dir)
    if root.is_symlink() or not root.is_dir():
        raise RefreshError("--dir is not a folder")
    files = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise RefreshError("data folder holds a symbolic link")
        if path.is_dir():
            if rel != "eol":
                raise RefreshError("data folder holds an unexpected folder")
            continue
        if rel == "manifest.json" or path.name == ".DS_Store":
            continue
        if not (rel in _REQUIRED or (
                rel.startswith("eol/") and rel.endswith(".json")
                and _PRODUCT_RE.fullmatch(rel[4:-5]))):
            raise RefreshError("data folder holds an unexpected file")
        files[rel] = path.read_bytes()
    for name in _REQUIRED:
        if name not in files:
            raise RefreshError("data folder is missing %s" % name)
    raw = manifest_bytes(files, kev_date, eol_date, upstream_commit,
                         kev_catalog_version, release_id)
    (root / "manifest.json").write_bytes(raw)
    return raw


# --- weekly change summary --------------------------------------------------

_DATE_FIELDS = ("releaseDate", "eol", "support", "extendedSupport")


def eol_change_summary(new: dict, old: dict) -> dict:
    """Compare {product: cycles} snapshots. Flags removals and big changes."""
    removed = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    total = changed = cycles_added = cycles_removed = 0
    changed_products = set()
    for pid in sorted(old):
        old_cycles = {c["cycle"]: c for c in old[pid]}
        new_cycles = {c["cycle"]: c for c in new.get(pid, [])}
        for cid, cycle in old_cycles.items():
            other = new_cycles.get(cid)
            if pid in new and other is None:
                cycles_removed += 1
            for field in _DATE_FIELDS:
                if field not in cycle:
                    continue
                total += 1
                if other is None or other.get(field) != cycle[field]:
                    changed += 1
                    changed_products.add(pid)
        if pid in new:
            cycles_added += len(set(new_cycles) - set(old_cycles))
    share = (changed / total) if total else 0.0
    reasons = []
    if removed:
        reasons.append("products that disappeared: %d" % len(removed))
    if share > EOL_CHANGE_SHARE:
        reasons.append("more than 10%% of dates changed (%d of %d)"
                       % (changed, total))
    return {
        "products_old": len(old), "products_new": len(new),
        "products_added": added, "products_removed": removed,
        "products_changed": sorted(changed_products - set(removed)),
        "cycles_added": cycles_added, "cycles_removed": cycles_removed,
        "dates_total": total, "dates_changed": changed,
        "flagged": bool(reasons), "reasons": reasons,
    }


def summary_text(summary: dict) -> str:
    """Fixed-text Markdown for the weekly pull request body."""
    def ids(names):
        return ", ".join("`%s`" % n for n in names) if names else "none"
    lines = ["## endoflife.date change summary", ""]
    if summary["flagged"]:
        lines += ["**Flagged for a careful review:** " +
                  "; ".join(summary["reasons"]) + ".", ""]
    else:
        lines += ["Not flagged: no product disappeared and 10% or fewer of "
                  "dates changed.", ""]
    lines += [
        "- Products: %d before, %d after" % (summary["products_old"],
                                            summary["products_new"]),
        "- Products added: %s" % ids(summary["products_added"]),
        "- Products removed: %s" % ids(summary["products_removed"]),
        "- Products with changed dates: %s" % ids(summary["products_changed"]),
        "- Cycles added: %d, cycles removed: %d" % (summary["cycles_added"],
                                                    summary["cycles_removed"]),
        "- Dates changed: %d of %d" % (summary["dates_changed"],
                                       summary["dates_total"]),
    ]
    return "\n".join(lines) + "\n"


def _load_eol_dir(path: str) -> dict:
    root = Path(path)
    if not root.is_dir():
        raise RefreshError("an eol folder was not found")
    products = {}
    for item in sorted(root.glob("*.json")):
        pid = item.name[:-5]
        if item.is_symlink() or not _PRODUCT_RE.fullmatch(pid):
            raise RefreshError("an eol folder holds a file that is not allowed")
        try:
            obj = json.loads(item.read_bytes().decode("utf-8"))
            validate_eol(obj)
        except (ValueError, RecursionError):
            raise RefreshError("eol file %s is not valid JSON" % pid) from None
        except DataError as exc:
            raise RefreshError("eol file %s fails the schema check: %s"
                               % (pid, exc)) from None
        products[pid] = obj
    return products


def _load_json(path: str, label: str):
    try:
        return json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, ValueError, RecursionError):
        raise RefreshError("%s KEV file cannot be read as JSON" % label) from None


# --- command line -----------------------------------------------------------

def _pattern(regex, label: str):
    def check(text: str) -> str:
        if not regex.fullmatch(text):
            raise argparse.ArgumentTypeError("%s has an unexpected form" % label)
        return text
    return check


def _iso(text: str) -> str:
    if not _DATE_RE.fullmatch(text):
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD")
    try:
        date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("not a real calendar date") from None
    return text


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="refresh_data.py",
        description="Refresh the KEV and endoflife.date data snapshots.")
    sub = parser.add_subparsers(dest="command", required=True)
    kev = sub.add_parser("kev", help="download the CISA KEV catalog")
    kev.add_argument("--out", required=True, metavar="DIR")
    eol = sub.add_parser("eol", help="build the endoflife.date snapshot")
    eol.add_argument("--upstream-commit", required=True, metavar="SHA",
                     type=_pattern(_SHA_RE, "--upstream-commit"))
    eol.add_argument("--out", required=True, metavar="DIR")
    man = sub.add_parser("manifest", help="rebuild manifest.json")
    man.add_argument("--dir", required=True, metavar="DIR")
    man.add_argument("--kev-date", required=True, type=_iso)
    man.add_argument("--eol-date", required=True, type=_iso)
    man.add_argument("--upstream-commit", required=True, metavar="SHA",
                     type=_pattern(_SHA_RE, "--upstream-commit"))
    man.add_argument("--kev-catalog-version", required=True, metavar="V",
                     type=_pattern(_CATALOG_RE, "--kev-catalog-version"))
    man.add_argument("--release-id", required=True, metavar="ID",
                     type=_pattern(_RELEASE_RE, "--release-id"))
    check = sub.add_parser("check-kev", help="publish gate for kev.json")
    check.add_argument("--new", required=True, metavar="FILE")
    check.add_argument("--old", required=True, metavar="FILE")
    check.add_argument("--allow-removed", action="store_true",
                       help="accept entries removed from the catalog")
    check.add_argument("--digest", metavar="FILE",
                       help="write a Markdown list of added entries")
    summary = sub.add_parser("eol-summary", help="weekly change summary")
    summary.add_argument("--new", required=True, metavar="DIR")
    summary.add_argument("--old", required=True, metavar="DIR")
    return parser


def _run(args) -> int:
    if args.command == "kev":
        obj = kev_from_feed(fetch(KEV_URL, KEV_MAX_BYTES))
        write_kev(args.out, obj)
        print("KEV written: %d entries" % len(obj["entries"]))
        return 0
    if args.command == "eol":
        _empty_dir(args.out)
        raw = fetch(EOL_ARCHIVE_URL % args.upstream_commit, ARCHIVE_MAX_BYTES)
        products = eol_from_archive(raw, args.upstream_commit)
        write_eol(args.out, products)
        print("endoflife.date written: %d products" % len(products))
        return 0
    if args.command == "manifest":
        build_manifest(args.dir, args.kev_date, args.eol_date,
                       args.upstream_commit, args.kev_catalog_version,
                       args.release_id)
        print("Manifest written")
        return 0
    if args.command == "check-kev":
        new = _load_json(args.new, "new")
        old = _load_json(args.old, "previous")
        fails = check_kev(new, old, allow_removed=args.allow_removed)
        if fails:
            for reason in fails:
                print("KEV gate failed: %s" % reason, file=sys.stderr)
            return 1
        if args.digest:
            Path(args.digest).write_text(kev_digest(new, old), "utf-8")
        old_ids = {e["cveID"] for e in old["entries"]}
        added = sum(1 for e in new["entries"] if e["cveID"] not in old_ids)
        print("KEV gate passed: %d entries, %d added"
              % (len(new["entries"]), added))
        return 0
    summary = eol_change_summary(_load_eol_dir(args.new),
                                 _load_eol_dir(args.old))
    sys.stdout.write(summary_text(summary))
    return 1 if summary["flagged"] else 0


def main(argv: list | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except RefreshError as exc:
        print("Refresh failed: %s" % exc, file=sys.stderr)
        return 1
    except OSError:
        print("Refresh failed: a file could not be read or written",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
