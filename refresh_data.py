#!/usr/bin/env python3
"""Refresh the CISA KEV and endoflife.date snapshots.

This is the only file in the project that opens a network connection. The
tool itself (swlc/) never does. Each command writes canonical JSON (sorted
keys, indent 2, ASCII, trailing newline) and never writes a fetch time:
dates come from the feeds' own fields or from explicit flags.

Commands:
  kev --out DIR                       download KEV, write DIR/kev.json
  eol --upstream-commit SHA --out DIR [--products-out FILE]
                                      build DIR/<product>.json at SHA, and
                                      the products.json catalog if asked
  manifest --dir DIR ...              rebuild DIR/manifest.json
  check-kev --new FILE --old FILE     publish gate for a new kev.json
  zip --dir DIR --out FILE            reproducible zip of a data folder
  eol-summary --new DIR --old DIR [--new-products F --old-products F]
                                      change summary for the weekly PR

Exit codes: 0 ok; 1 gate failed or refresh failed; 2 usage error. For
eol-summary: 0 clean, 1 flagged (a summary is written either way), 2 error
(nothing is written to stdout).
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
import unicodedata
import urllib.error
import zipfile
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from swlc.data import validate_eol, validate_kev, validate_products  # noqa: E402
from swlc.data import _VENDOR_RE as _LOADER_VENDOR_RE  # noqa: E402
from swlc.normalize import normalize_name  # noqa: E402
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
DATA_FORMAT = 2
MIN_TOOL_VERSION = "0.1.0"
COUNT_TOLERANCE = 0.20
MAX_TEXT = 200
ADDED_MIN, ADDED_SHARE = 50, 0.10      # a normal day adds a handful
CHANGED_MIN, CHANGED_SHARE = 3, 0.01   # CISA renames a few entries
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
EOL_CHANGE_SHARE = 0.10

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_CVE_RE = re.compile(r"CVE-[0-9]{4}-[0-9]{4,}")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PRODUCT_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*")
_CYCLE_RE = re.compile(r"[a-z0-9.\-+_]+")  # upstream's own releaseCycle rule
_CATALOG_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z.\-]{0,31}")
_RELEASE_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z._\-]{0,63}")
# Data format 2: products.json is generated here; curation.json is a
# hand-kept file, listed in the manifest but never written by this script.
_REQUIRED = ("aliases.json", "profiles.json", "kev.json", "products.json",
             "curation.json")


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


def _bad_char(text: str) -> bool:
    """Control, format (zero-width, bidi override) or line separator."""
    return any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp")
               for c in text)


def _catalog_key(text: str):
    if not re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,6}){0,5}", text):
        return None
    return tuple(int(part) for part in text.split("."))


def _content_fails(new, old) -> list:
    """Checks on the new file alone and against the baseline, never relaxed."""
    fails = []
    strings = [new.get(k) for k in ("catalogVersion", "dateReleased",
                                    "license")]
    strings += [v for e in new["entries"] for v in e.values()]
    long_fields = sum(1 for v in strings
                      if isinstance(v, str) and len(v) > MAX_TEXT)
    if long_fields:
        fails.append("fields longer than %d characters: %d"
                     % (MAX_TEXT, long_fields))
    entries = new["entries"]
    bad_ids = sum(1 for e in entries if not _CVE_RE.fullmatch(e["cveID"]))
    if bad_ids:
        fails.append("cveID values not in the CVE-YYYY-NNNN form: %d" % bad_ids)
    bad_text = sum(1 for e in entries if any(
        _bad_char(e[k]) for k in ("cveID", "vendorProject", "product")))
    if bad_text:
        fails.append("entries with control, zero-width or bidi characters: %d"
                     % bad_text)
    if len({e["cveID"] for e in entries}) != len(entries):
        fails.append("a cveID appears twice in the new KEV file")
    late = sum(1 for e in entries if e["dateAdded"] > new["dateReleased"])
    if late:
        fails.append("entries with a dateAdded after dateReleased: %d" % late)
    if new["dateReleased"] < old["dateReleased"]:
        fails.append("dateReleased is older than the previous release")
    new_key = _catalog_key(new["catalogVersion"])
    old_key = _catalog_key(old["catalogVersion"])
    if new_key is None or old_key is None:
        fails.append("catalogVersion has an unexpected form")
    elif new_key < old_key:
        fails.append("catalogVersion is older than the previous release")
    return fails


def check_kev(new, old, allow_removed: bool = False,
              allow_bulk: bool = False) -> list:
    """Publish gate. Returns failure reasons; an empty list means publish.

    allow_removed accepts entries CISA removed. allow_bulk (a person's
    override) relaxes only the volume checks: the count range, the number
    of additions and the number of changed entries.
    """
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
    fails += _content_fails(new, old)
    new_ids = {e["cveID"] for e in new["entries"]}
    old_entries = {e["cveID"]: (e["vendorProject"], e["product"],
                                e["dateAdded"]) for e in old["entries"]}
    old_ids = set(old_entries)
    low = len(old_ids) * (1 - COUNT_TOLERANCE)
    high = len(old_ids) * (1 + COUNT_TOLERANCE)
    if not old_ids:
        fails.append("previous KEV file has no entries to compare against")
    elif not low <= len(new_ids) <= high and not allow_bulk:
        fails.append("entry count %d is outside 20%% of the previous %d"
                     % (len(new_ids), len(old_ids)))
    added = len(new_ids - old_ids)
    if added > max(ADDED_MIN, len(old_ids) * ADDED_SHARE) and not allow_bulk:
        fails.append("entries added in one release: %d; a bulk change needs "
                     "a person's override" % added)
    changed = sum(1 for e in new["entries"] if e["cveID"] in old_entries and
                  (e["vendorProject"], e["product"], e["dateAdded"])
                  != old_entries[e["cveID"]])
    if changed > max(CHANGED_MIN, len(old_ids) * CHANGED_SHARE) \
            and not allow_bulk:
        fails.append("existing entries whose vendor, product or dateAdded "
                     "changed: %d" % changed)
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


def _permalink_id(top: dict) -> str:
    permalink = _strip_comment(top.get("permalink") or "")
    if not permalink.startswith("/") or not _PRODUCT_RE.fullmatch(
            permalink[1:]):
        raise _bad("file", "permalink is missing or not a plain product id")
    return permalink[1:]


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
    pid = _permalink_id(top)
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


# --- product catalog (products.json) ----------------------------------------
#
# The same upstream front matter, at the same pinned commit, also gives the
# product catalog. Only these upstream fields are read for it:
#   permalink    -> id (shared with the eol files)
#   title        -> title
#   category     -> category
#   identifiers  -> entries of kind cpe (the vendor part, in both the
#                   cpe:/a:vendor:product and cpe:2.3:a:vendor:product
#                   forms) and kind purl (the owner part, for purl types
#                   that have one: see _OWNER_PURLS). Entries of any other
#                   kind (repology) are skipped.
# Nothing else is read: no descriptions, slugs, alternate_urls, page text
# or dates.

_IDENT_RE = re.compile(r"\s*-\s+([A-Za-z0-9_]+):(?:[ ]+(.*))?$")
# The loader's own vendor pattern, applied after lowercasing, so a vendor
# that passes refresh never fails the loader.
_VENDOR_RE = _LOADER_VENDOR_RE
_NAMESPACE_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*")
# Purl types that give a namespace; every other type (deb, rpm, apk, alpm,
# docker, oci, brew, scoop, chocolatey, winget, nuget, pypi, gem, cargo, hex,
# generic, swid) gives none: their namespaces name a distribution, a tap or a
# repackager, not the product's owner.
_OWNER_PURLS = ("github", "npm", "composer", "golang", "maven")


def _plain_text(value, key: str, where: str) -> str:
    """A title or identifier value: plain or quoted, no escapes."""
    value = (value or "").strip()
    if not value:
        raise _bad(where, "%s has no value" % key)
    if value[0] in "\"'":
        quote = value[0]
        pos = 1
        while True:
            end = value.find(quote, pos)
            if end < 0:
                raise _bad(where, "%s has a quoted value it cannot read" % key)
            if quote == "'" and value[end + 1:end + 2] == "'":
                pos = end + 2
                continue
            break
        inner = value[1:end]
        if quote == '"' and "\\" in inner:
            raise _bad(where, "%s has a quoted value it cannot read" % key)
        rest = value[end + 1:].strip()
        if rest and not rest.startswith("#"):
            raise _bad(where, "%s has text after a quoted value" % key)
        text = inner.replace("''", "'") if quote == "'" else inner
    else:
        if value[0] in "|>[{&*!%@`":
            raise _bad(where, "%s has a value it cannot read" % key)
        text = _strip_comment(value)
    if not text or len(text) > MAX_TEXT or _bad_char(text):
        raise _bad(where, "%s has a value that is empty, too long or has "
                          "unreadable characters" % key)
    return text


def cpe_vendor(value: str, where: str):
    """The vendor token of a CPE 2.2 URI or 2.3 string; None for * or -."""
    parts = value.split(":")
    if value.startswith("cpe:2.3:") and len(parts) >= 5:
        vendor = parts[3]
    elif value.startswith("cpe:/") and len(parts) >= 3:
        vendor = parts[2]
    else:
        raise _bad(where, "a cpe identifier has an unexpected form")
    if vendor in ("*", "-", ""):
        return None
    vendor = vendor.lower()
    if not _VENDOR_RE.fullmatch(vendor):
        raise _bad(where, "a cpe vendor has characters it cannot read")
    return vendor


def purl_namespace(value: str, where: str):
    """The owner part of a purl, decoded and lower-cased.

    github, npm and composer: the first namespace segment (npm without its
    @). golang: the owner segment, only for module paths on github.com.
    maven: the whole group id. None for every other type, or when there is
    no namespace. A decoded value with unexpected characters stops the
    refresh."""
    if not value.startswith("pkg:"):
        raise _bad(where, "a purl identifier has an unexpected form")
    path = value[4:].split("#")[0].split("?")[0]
    segments = path.split("/")
    if len(segments) < 2 or not segments[0]:
        raise _bad(where, "a purl identifier has an unexpected form")
    kind = segments[0]
    if kind not in _OWNER_PURLS or len(segments) < 3:
        return None
    spaces = [urllib.parse.unquote(seg).lower() for seg in segments[1:-1]]
    if kind == "golang":
        if spaces[0] != "github.com" or len(spaces) < 2:
            return None
        space = spaces[1]
    elif kind == "maven":
        space = ".".join(spaces)
    else:
        space = spaces[0]
    if kind == "npm" and space.startswith("@"):
        space = space[1:]
    if not space:
        return None
    if not _NAMESPACE_RE.fullmatch(space):
        raise _bad(where, "a purl namespace has characters it cannot read")
    return space


def product_record_from_markdown(text: str) -> dict:
    """One upstream product file -> one products.json record."""
    top, blocks, current = {}, {}, None
    for line in _front_matter(text):
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
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    pid = _permalink_id(top)
    vendors, spaces = set(), set()
    if (top.get("identifiers") or "").strip():
        raise _bad(pid, "identifiers is not a block list")
    for line in blocks.get("identifiers", []):
        if not line.strip() or line.strip().startswith("#"):
            continue
        match = _IDENT_RE.match(line)
        if not match:
            raise _bad(pid, "an identifiers line has an unexpected layout")
        kind = match.group(1)
        if kind not in ("cpe", "purl"):
            continue
        value = _plain_text(match.group(2), kind, pid)
        if kind == "cpe":
            vendor = cpe_vendor(value, pid)
            if vendor:
                vendors.add(vendor)
        else:
            space = purl_namespace(value, pid)
            if space:
                spaces.add(space)
    return {
        "id": pid,
        "title": _plain_text(top.get("title"), "title", pid),
        "category": _plain_text(top.get("category"), "category", pid),
        "vendors": sorted(vendors),
        "namespaces": sorted(spaces),
    }


def eol_from_archive(raw: bytes, sha: str, catalog: dict | None = None) -> dict:
    """GitHub's tar.gz of the upstream repo at sha -> {product id: cycles}.

    When catalog is a dict, it is filled with {product id: products.json
    record} from the same files."""
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
                if catalog is not None:
                    catalog[pid] = product_record_from_markdown(text)
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


def products_bytes(catalog: dict) -> bytes:
    """Canonical products.json bytes for {product id: record}."""
    obj = {"format": 1, "products": [catalog[pid] for pid in sorted(catalog)]}
    try:
        validate_products(obj)
    except DataError as exc:
        raise RefreshError("the product catalog fails the schema check: %s"
                           % exc) from None
    return canonical(obj)


def write_products(path: str, catalog: dict) -> None:
    target = Path(path)
    if target.is_symlink() or target.exists():
        raise RefreshError("--products-out already exists")
    target.write_bytes(products_bytes(catalog))


def manifest_bytes(files: dict, kev_date: str, eol_date: str,
                   upstream_commit: str, kev_catalog_version: str,
                   release_id: str, data_format: int = DATA_FORMAT) -> bytes:
    """files maps relative names to bytes; the manifest lists each one."""
    listing = {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        for name, data in files.items()
    }
    return canonical({
        "data_format": data_format,
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
    """Write data_dir/manifest.json (data format 2) for aliases, profiles, kev,
    products, curation and eol/*."""
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


def write_zip(data_dir: str, out_path: str) -> None:
    """Zip a data folder reproducibly: sorted names, fixed times, stored."""
    root = Path(data_dir)
    if root.is_symlink() or not root.is_dir():
        raise RefreshError("--dir is not a folder")
    paths = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RefreshError("data folder holds a symbolic link")
        if path.is_file() and path.name != ".DS_Store":
            paths.append((path.relative_to(root).as_posix(), path))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as zf:
        for name, path in sorted(paths):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.create_system = 3
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


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
            for cid in set(old_cycles) & set(new_cycles):
                for field in _DATE_FIELDS:
                    if field in new_cycles[cid] and field not in old_cycles[cid]:
                        total += 1
                        changed += 1
                        changed_products.add(pid)
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


def _collisions(catalog: dict) -> list:
    by_title = {}
    for pid in sorted(catalog):
        by_title.setdefault(
            normalize_name(catalog[pid]["title"]), []).append(pid)
    return [{"title": title, "ids": ids}
            for title, ids in sorted(by_title.items()) if len(ids) > 1]


def products_change_summary(new: dict, old: dict) -> dict:
    """Compare {product id: record} catalogs: added, removed and retitled
    products, vendor and namespace changes on existing products, and
    normalized-title collisions (all, and those not in the old catalog).

    flagged is true for a new collision or for any vendor or namespace
    change on an existing product: those two lists decide one-word matches.
    Removed products flag through the eol summary."""
    both = sorted(set(new) & set(old))
    list_changes = []
    for pid in both:
        change = {"id": pid}
        for key in ("vendors", "namespaces"):
            was, now = set(old[pid][key]), set(new[pid][key])
            change[key + "_added"] = sorted(now - was)
            change[key + "_removed"] = sorted(was - now)
        if any(change[k] for k in change if k != "id"):
            list_changes.append(change)
    collisions = _collisions(new)
    seen = {(c["title"], tuple(c["ids"])) for c in _collisions(old)}
    new_collisions = [c for c in collisions
                      if (c["title"], tuple(c["ids"])) not in seen]
    reasons = []
    if new_collisions:
        reasons.append("new normalized-title collisions: %d"
                       % len(new_collisions))
    if list_changes:
        reasons.append("vendor or namespace changes on existing products: "
                       "%d" % len(list_changes))
    return {
        "products_old": len(old), "products_new": len(new),
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "retitled": [
            {"id": pid, "old": old[pid]["title"], "new": new[pid]["title"]}
            for pid in both if new[pid]["title"] != old[pid]["title"]],
        "list_changes": list_changes,
        "collisions": collisions,
        "new_collisions": new_collisions,
        "flagged": bool(reasons), "reasons": reasons,
    }


def products_summary_text(summary: dict) -> str:
    """Fixed-text Markdown section for the weekly pull request body.
    Titles come from upstream, so they are shown as code with backticks
    removed. Vendors and namespaces are checked tokens."""
    def ids(names):
        return ", ".join("`%s`" % n for n in names) if names else "none"

    def title(text):
        return "`%s`" % text.replace("`", "'")
    retitled = ", ".join("`%s` (%s to %s)" % (r["id"], title(r["old"]),
                                            title(r["new"]))
                         for r in summary["retitled"]) or "none"

    def collisions(items):
        return "; ".join("%s: %s" % (title(c["title"]), ids(c["ids"]))
                         for c in items) or "none"
    lines = ["## Product catalog change summary", ""]
    if summary["flagged"]:
        lines += ["**Flagged for a careful review:** " +
                  "; ".join(summary["reasons"]) + ".", ""]
    else:
        lines += ["Not flagged: no new title collision and no vendor or "
                  "namespace change on an existing product.", ""]
    lines += [
        "- Products: %d before, %d after" % (summary["products_old"],
                                            summary["products_new"]),
        "- Products added: %s" % ids(summary["added"]),
        "- Products removed: %s" % ids(summary["removed"]),
        "- Products retitled: %s" % retitled,
        "- New normalized-title collisions: %s"
        % collisions(summary["new_collisions"]),
        "- All normalized-title collisions: %s"
        % collisions(summary["collisions"]),
    ]
    if summary["list_changes"]:
        lines.append("- Vendor and namespace changes:")
        for change in summary["list_changes"]:
            parts = []
            for key, label in (("vendors", "vendor"),
                               ("namespaces", "namespace")):
                if change[key + "_added"]:
                    parts.append("%s added %s" % (
                        label, ids(change[key + "_added"])))
                if change[key + "_removed"]:
                    parts.append("%s removed %s" % (
                        label, ids(change[key + "_removed"])))
            lines.append("  - `%s`: %s" % (change["id"], "; ".join(parts)))
    else:
        lines.append("- Vendor and namespace changes: none")
    return "\n".join(lines) + "\n"


def _load_catalog(path: str, label: str) -> dict:
    try:
        obj = json.loads(Path(path).read_bytes().decode("utf-8"))
        return validate_products(obj)
    except (OSError, ValueError, RecursionError):
        raise RefreshError("%s products file cannot be read as JSON"
                           % label) from None
    except DataError as exc:
        raise RefreshError("%s products file fails the schema check: %s"
                           % (label, exc)) from None


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
    eol.add_argument("--products-out", metavar="FILE",
                     help="also write the product catalog (products.json)")
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
    check.add_argument("--allow-bulk", action="store_true",
                       help="a person's override for a bulk change")
    check.add_argument("--digest", metavar="FILE",
                       help="write a Markdown list of added entries")
    pack = sub.add_parser("zip", help="zip a data folder reproducibly")
    pack.add_argument("--dir", required=True, metavar="DIR")
    pack.add_argument("--out", required=True, metavar="FILE")
    summary = sub.add_parser("eol-summary", help="weekly change summary")
    summary.add_argument("--new", required=True, metavar="DIR")
    summary.add_argument("--old", required=True, metavar="DIR")
    summary.add_argument("--new-products", metavar="FILE",
                         help="new products.json; adds a catalog section")
    summary.add_argument("--old-products", metavar="FILE",
                         help="previous products.json (with --new-products)")
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
        catalog = {} if args.products_out else None
        products = eol_from_archive(raw, args.upstream_commit, catalog)
        write_eol(args.out, products)
        if args.products_out:
            write_products(args.products_out, catalog)
        print("endoflife.date written: %d products" % len(products))
        return 0
    if args.command == "manifest":
        build_manifest(args.dir, args.kev_date, args.eol_date,
                       args.upstream_commit, args.kev_catalog_version,
                       args.release_id)
        print("Manifest written")
        return 0
    if args.command == "zip":
        write_zip(args.dir, args.out)
        print("Zip written")
        return 0
    if args.command == "check-kev":
        new = _load_json(args.new, "new")
        old = _load_json(args.old, "previous")
        fails = check_kev(new, old, allow_removed=args.allow_removed,
                          allow_bulk=args.allow_bulk)
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
    if bool(args.new_products) != bool(args.old_products):
        raise RefreshError("--new-products and --old-products go together")
    # Load and check everything before writing a word, so an error never
    # leaves a summary behind.
    eol = eol_change_summary(_load_eol_dir(args.new),
                             _load_eol_dir(args.old))
    catalog = None
    if args.new_products:
        catalog = products_change_summary(
            _load_catalog(args.new_products, "new"),
            _load_catalog(args.old_products, "previous"))
    sys.stdout.write(summary_text(eol))
    if catalog is not None:
        sys.stdout.write("\n" + products_summary_text(catalog))
    return 1 if eol["flagged"] or (catalog and catalog["flagged"]) else 0


def main(argv: list | None = None) -> int:
    args = _parser().parse_args(argv)
    # eol-summary exits 0 (clean) or 1 (flagged) with a summary written;
    # any error is 2, so a caller can tell "flagged" from "failed".
    failed = 2 if args.command == "eol-summary" else 1
    try:
        return _run(args)
    except RefreshError as exc:
        print("Refresh failed: %s" % exc, file=sys.stderr)
        return failed
    except OSError:
        print("Refresh failed: a file could not be read or written",
              file=sys.stderr)
        return failed


if __name__ == "__main__":
    sys.exit(main())
