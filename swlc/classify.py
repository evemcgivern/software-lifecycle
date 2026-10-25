"""What kind of item a row is: governable, component, bundle_member, unknown.

Pure and per item: a name, a version, the matched product and the loaded
data in, one Classification out. No inventory context here; parent links
from the inventory are a later step. The first confident hit wins and every
signal that fired is recorded in ``basis``. Publisher only confirms a
curated entry; it never decides a class by itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .catalog_match import strip_arch, tokens
from .normalize import best_cycle, normalize_name, split_version

CLASSES = ("governable", "component", "bundle_member", "unknown")
GOVERNABLE_CATEGORIES = frozenset({"server-app", "app", "os", "database",
                                   "lang", "service"})
# Classes a curated row or product entry may set. bundle_member needs a
# parent, so it comes only from bundle_parents.
CURATED_CLASSES = ("governable", "component", "unknown")

# Signal codes (classification_basis)
ROW_OVERRIDE = "row_override"
PRODUCT_OVERRIDE = "product_override"
CURATED_PARENT = "curated_parent"
SUITE_NO_FIT = "suite_no_fit"
NAME_PART = "name_part"
NAME_OS_PART = "name_os_part"
CATEGORY = "category_governable"
STANDALONE = "standalone_by_default"
DEVICE = "device_category"
UNCATEGORIZED = "category_unknown"
NO_SIGNAL = "no_signal"
VERSION_SHAPE = "version_shape"

_VERSION_TOKEN = re.compile(r"v?\d+(?:\.\d+)*[a-z]?")
_YEAR_OR_VERSION = re.compile(r"\d+(?:\.\d+)*(?:[a-z]+\d*)?")
_TRAILING_GROUPS = re.compile(r"(?:\s*[(\[][^()\[\]]*[)\]])+\Z")
_TRAILING_SEP = re.compile(r"[\s\-:,;]+\Z")

# os_part: KB numbers anywhere; "update for" leading; "hotfix" leading or
# last; "language pack" as the last words; "driver" as the last word, or
# "driver [version] for ...", after at least one other word.
_KB = re.compile(r"\bkb\d{6,8}\b")
_UPDATE_FOR = re.compile(r"\A(?:security )?update for\b")
_HOTFIX = re.compile(r"\Ahotfix\b|\bhotfix\Z")
_LANGUAGE_PACK = re.compile(r"\blanguage pack\Z")
_DRIVER = re.compile(r"\S \bdriver(?:\Z| (?:\d+(?:\.\d+)* )?for \S)")
# part: a C++ runtime year anywhere; "redistributable" last; "runtime" or
# "sdk" last after another word; font, codec, extension, plugin, add-in
# (or plural) last after another word, or "add-in for ...".
_VCPP = re.compile(r"\bvisual c\+\+ 20\d\d\b")
_REDIST = re.compile(r"\bredistributable\Z")
_RUNTIME_SDK = re.compile(r"\S \b(?:runtime|sdk)\Z")
_LAST_PART = re.compile(
    r"\S \b(?:font|codec|extension|plugin|plug-in|add-in)s?\Z"
    r"|\S \badd-in for \S")
# One lowercase package token: lib*, *-dev, or a font package (font-*,
# fonts-*, ttf-*). A lib* name that is a catalog title is skipped.
_LIB = re.compile(r"\A(?:lib\S+|\S+-dev)\Z")
_FONT_PACKAGE = re.compile(r"\A(?:fonts?|ttf)-\S+\Z")


@dataclass(frozen=True)
class Classification:
    cls: str
    basis: tuple
    parent_ref: dict | None = None


def _base(name: str) -> str:
    """Normalized name without architecture or locale groups, a trailing
    version token, or trailing separators."""
    words = strip_arch(normalize_name(name or "")).split()
    if len(words) > 1 and _VERSION_TOKEN.fullmatch(words[-1]):
        words.pop()
    return _TRAILING_SEP.sub("", " ".join(words))


def _part(name: str):
    """(kind, is_lib, last word) for the first pattern that fires, or
    (None, False, None)."""
    base = _base(name)
    bare = _TRAILING_SEP.sub("", _TRAILING_GROUPS.sub("", base))
    last = bare.rsplit(" ", 1)[-1] if bare else None
    if _KB.search(base) or _UPDATE_FOR.search(bare) or _HOTFIX.search(bare) \
            or _LANGUAGE_PACK.search(bare) or _DRIVER.search(bare):
        return "os_part", False, last
    if _VCPP.search(bare) or _REDIST.search(bare) \
            or _RUNTIME_SDK.search(bare) or _LAST_PART.search(bare):
        return "part", False, last
    raw = (name or "").strip()
    if raw == raw.lower() and " " not in bare:
        if _LIB.fullmatch(bare):
            return "part", True, last
        if _FONT_PACKAGE.fullmatch(bare):
            return "part", False, last
    return None, False, last


def part_kind(name: str) -> str | None:
    """None, "part" or "os_part", from the name alone."""
    return _part(name)[0]


# The catalog's ids and normalized titles, built once per catalog object:
# (catalog, frozenset). One entry only, so a run never holds two catalogs.
_LEADS: list = [None, frozenset()]


def _catalog_names(catalog: dict) -> frozenset:
    if _LEADS[0] is not catalog:
        names = set(catalog)
        names.update(normalize_name(rec.get("title") or "")
                     for rec in catalog.values())
        _LEADS[0], _LEADS[1] = catalog, frozenset(names)
    return _LEADS[1]


def _catalog_lead(base: str, catalog: dict) -> bool:
    """True when a one-word name is a catalog product's id or title, or
    starts with one followed by "-" (libreoffice, libreoffice-writer)."""
    names = _catalog_names(catalog)
    return base in names or base.split("-", 1)[0] in names


def _publisher_has(word: str, publisher: str) -> bool:
    return not word or word in tokens(publisher)


def _row_hit(rows, name: str, publisher: str):
    forms = {normalize_name(name or ""), _base(name)}
    for row in rows:
        if row["name"] in forms and _publisher_has(row["publisher"],
                                                   publisher):
            return row
    return None


def _leading(base: str, prefix: str):
    """The words after prefix when prefix is the base's leading whole
    words, else None."""
    words, want = base.split(), prefix.split()
    if words[:len(want)] != want:
        return None
    return words[len(want):]


def _parent_hit(parents, base: str, publisher: str):
    """The entry with the longest matching prefix, and the words after it."""
    best, best_tail = None, None
    for entry in parents:
        tail = _leading(base, entry["name_prefix"])
        if tail is not None and _publisher_has(entry["publisher"],
                                               publisher) \
                and (best is None or len(entry["name_prefix"].split())
                     > len(best["name_prefix"].split())):
            best, best_tail = entry, tail
    return best, best_tail


# Words a suite tail may hold besides year and version words: separators,
# the word "version", a KB number in brackets, a three-letter language code
# in brackets ("(deu)"), and the language word on Office proofing tools.
_TAIL_WORDS = frozenset(("-", "version", "english"))
_TAIL_GROUP = re.compile(r"\((?:kb\d{6,8}|[a-z]{3})\)")
# "for x64-based systems" on Windows update names.
_FOR_SYSTEMS = re.compile(r"(?:x64|x86|arm64)-based")


def _tail_words(tail: list):
    """The year and version words of a suite tail, or None when the tail
    holds any other word."""
    words = list(tail)
    if len(words) >= 3 and words[-1] == "systems" \
            and _FOR_SYSTEMS.fullmatch(words[-2]) and words[-3] == "for":
        words = words[:-3]
    out = []
    for word in words:
        if _YEAR_OR_VERSION.fullmatch(word):
            out.append(word)
        elif word not in _TAIL_WORDS and not _TAIL_GROUP.fullmatch(word):
            return None
    return out


def _suite_cycles(tail: list, version: str, cycles: list) -> set:
    """Cycles of the parent that fit. The tail after the prefix may hold
    only year and version words (and the few words above); they are read in
    order as one version ("10 version 22h2" gives 10, 22h2). With no such
    word the version column is used. Any other word: no fit."""
    found = _tail_words(tail[:-1] if tail and _TAIL_GROUP.fullmatch(tail[-1])
                        else tail)
    if found is None:
        return set()
    parts = []
    for word in found:
        parts.extend(split_version(word))
    if not parts:
        parts = split_version(version)
    return set(best_cycle(parts, cycles)[1]) if parts else set()


def _has_version(item: dict) -> bool:
    if (item.get("version") or "").strip():
        return True
    words = strip_arch(normalize_name(item.get("name") or "")).split()
    return any(_VERSION_TOKEN.fullmatch(w) and any(c.isdigit() for c in w)
               for w in words)


def classify(item: dict, publisher: str, data) -> Classification:
    """Classify one item (the dict assess builds) from its own evidence."""
    curation = data.curation or {}
    catalog = data.catalog or {}
    name, version = item.get("name") or "", item.get("version") or ""
    product = item.get("product")
    category = (catalog.get(product) or {}).get("category") if product \
        else None
    prod_entry = (curation.get("classification_products") or {}).get(
        product) if product else None
    basis = []
    decided = None
    parent_ref = None

    # 1. curated row
    row = _row_hit(curation.get("classification_rows") or [], name,
                   publisher)
    if row is not None:
        basis.append(ROW_OVERRIDE)
        decided = row["class"]

    # 2. curated suite parent
    base = _base(name)
    entry, tail = _parent_hit(curation.get("bundle_parents") or [],
                              strip_arch(normalize_name(name)), publisher)
    if entry is not None:
        labels = [c["cycle"] for c in data.products.get(entry["parent"], [])]
        fits = _suite_cycles(tail, version, labels)
        if len(fits) == 1:
            basis.append(CURATED_PARENT)
            if decided is None:
                decided = "bundle_member"
                parent_ref = {"kind": "product",
                              "value": "%s/%s" % (entry["parent"],
                                                  fits.pop()),
                              "basis": CURATED_PARENT}
        else:
            basis.append(SUITE_NO_FIT)
            decided = decided or "unknown"

    # 3. name pattern (D1: a standalone runtime keeps its trailing
    # "Runtime" or "SDK")
    standalone = category == "lang" or (
        prod_entry is not None and prod_entry["class"] == "governable")
    kind, is_lib, last = _part(name)
    if kind is not None and standalone and last in ("runtime", "sdk"):
        kind = None
    if kind is not None and is_lib and _catalog_lead(base, catalog):
        kind = None
    if kind is not None:
        basis.append(NAME_OS_PART if kind == "os_part" else NAME_PART)
        decided = decided or "component"

    # 4. curated product class, 5. catalog category
    governable = False
    if prod_entry is not None:
        basis.append(PRODUCT_OVERRIDE)
        governable = prod_entry["class"] == "governable"
        if decided is None and not governable:
            decided = prod_entry["class"]
    elif category in GOVERNABLE_CATEGORIES:
        basis.append(CATEGORY)
        governable = True
    if governable and standalone:
        basis.append(STANDALONE)
    if governable and decided is None:
        if _has_version(item):
            decided = "governable"
        else:
            basis.append(VERSION_SHAPE)
            decided = "unknown"

    # 6. nothing confident
    if decided is None:
        if category == "device":
            basis.append(DEVICE)
        elif category is not None:
            basis.append(UNCATEGORIZED)
        else:
            basis.append(NO_SIGNAL)
        decided = "unknown"
    return Classification(decided, tuple(basis), parent_ref)


def apply_classification(items: list, groups: dict, data) -> None:
    """Set the classification keys on every item, in place."""
    for it in items:
        result = classify(it, it.get("publisher") or "", data)
        it["classification"] = result.cls
        it["classification_basis"] = list(result.basis)
        it["parent_ref"] = result.parent_ref
        it["inherited_from"] = None
        it["inherited_lifecycle"] = None
