from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from .catalog_match import TITLE_NEEDS_PUBLISHER, _has_run, tokens
from .errors import DataError
from .normalize import best_cycle, normalize_name, split_version

NO_ALIAS = "NO_ALIAS"
NO_CYCLE = "NO_CYCLE"
NO_VERSION = "NO_VERSION"
AMBIGUOUS = "AMBIGUOUS"

_MODES = ("exact", "prefix")
_SOURCES = ("name", "version")


CURATED = "curated"
GENERATED = "generated"


@dataclass(frozen=True)
class MatchResult:
    product: str | None
    cycle: dict | None
    reason: str | None
    kev: dict | None = None
    # Which table found the product: CURATED (aliases.json), GENERATED
    # (product titles in products.json), or None when no product is known.
    source: str | None = None


def _check(entry: dict, pos: int) -> None:
    """Reject a malformed alias entry. Names the entry position only."""
    def bad(what: str) -> DataError:
        return DataError("alias entry %d: %s" % (pos, what))

    if not isinstance(entry, dict):
        raise bad("not an object")
    for field in ("key", "product"):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            raise bad("missing or empty '%s'" % field)
    if entry.get("match") not in _MODES:
        raise bad("'match' must be exact or prefix")
    if entry.get("version_from") not in _SOURCES:
        raise bad("'version_from' must be name or version")
    if "cycle" in entry and not (isinstance(entry["cycle"], str)
                                 and entry["cycle"].strip()):
        raise bad("'cycle' must be a non-empty string")
    for field in ("build_map", "column_map"):
        if field not in entry:
            continue
        bmap = entry[field]
        if not isinstance(bmap, dict) or not bmap:
            raise bad("'%s' must be a non-empty object" % field)
        if not all(isinstance(k, str) and k.strip() for k in bmap):
            raise bad("'%s' keys must be non-empty strings" % field)
        for value in bmap.values():
            values = value if isinstance(value, list) else [value]
            if not values or not all(isinstance(v, str) and v.strip()
                                     for v in values):
                raise bad("'%s' values must be cycle strings" % field)
    if "column_map" in entry and ("build_map" not in entry
                                  or entry["version_from"] != "name"):
        # column_map only checks the version column against a year read
        # from the name through build_map; anywhere else it would be
        # silently ignored.
        raise bad("'column_map' needs 'build_map' and version_from name")
    if "kev" in entry:
        kev = entry["kev"]
        if not isinstance(kev, dict) or set(kev) != {"vendor", "product"} \
                or not all(isinstance(v, str) and v.strip()
                           for v in kev.values()):
            raise bad("'kev' must be an object with non-empty 'vendor' and "
                      "'product' strings")
    if "note" in entry and not (isinstance(entry["note"], str)
                                and entry["note"].strip()):
        raise bad("'note' must be a non-empty string")
    if "edition_words" in entry:
        words = entry["edition_words"]
        if not isinstance(words, list) or not all(
                isinstance(w, str) and w.strip() for w in words):
            raise bad("'edition_words' must be a list of words")
    if "numbered_words" in entry:
        words = entry["numbered_words"]
        if not isinstance(words, list) or not words or not all(
                isinstance(w, str) and w.strip() for w in words):
            raise bad("'numbered_words' must be a non-empty list of words")
    if "publisher" in entry:
        pubs = entry["publisher"]
        if not isinstance(pubs, list) or not pubs or not all(
                isinstance(p, str) and tokens(p) for p in pubs):
            raise bad("'publisher' must be a non-empty list of publisher "
                      "words")


def _publisher_ok(entry: dict, publisher: str) -> bool:
    """An alias with a 'publisher' list applies only when the row's
    publisher holds one of those phrases as a run of whole words."""
    if "publisher" not in entry:
        return True
    pub = tokens(publisher)
    return any(_has_run(pub, tokens(p)) for p in entry["publisher"])


def _hits(name: str, key: str, mode: str) -> bool:
    """Exact or anchored literal prefix on normalized text, whole words."""
    if not key:
        return False
    if mode == "exact":
        return name == key
    return name == key or name.startswith(key + " ")


def _rule(entry: dict) -> tuple:
    bmap = entry.get("build_map")
    frozen = None
    if bmap is not None:
        frozen = tuple(sorted(
            (k, tuple(v) if isinstance(v, list) else (v,))
            for k, v in bmap.items()))
    words = tuple(sorted(entry.get("edition_words") or []))
    numbered = tuple(sorted(entry.get("numbered_words") or []))
    return (entry["version_from"], entry.get("cycle"), frozen, words,
            numbered)


def _distinct_by_parts(labels: list[str]) -> list[tuple[str, ...]]:
    seen: list[tuple[str, ...]] = []
    for label in labels:
        parts = tuple(split_version(label))
        if parts not in seen:
            seen.append(parts)
    return seen


def match_product(name: str, version: str, aliases: list[dict],
                  products: dict[str, list[dict]], catalog_index=None,
                  publisher: str = "") -> MatchResult:
    """Map a raw name and version to (product, cycle dict), or a reason code.

    Never guesses: no fuzzy scores, no regular expressions built from alias
    text. A name hitting aliases for two products, or a version fitting
    several cycles, is AMBIGUOUS.

    Precedence when catalog_index (swlc.catalog_match.build_index) is given:
    a curated alias that hits the name decides the row, even when it ends
    in NO_CYCLE, NO_VERSION, AMBIGUOUS or a rejected tail (NO_ALIAS); a
    curated product X while generated matching finds another product Y is
    AMBIGUOUS. Generated matching runs only when no alias hits. Without
    catalog_index, generated matching is off and only aliases are used.
    """
    return _match(name, version, aliases, products, catalog_index,
                  publisher, False)[0]


def match_noted(name: str, version: str, aliases: list[dict],
                products: dict[str, list[dict]], catalog_index=None,
                publisher: str = "") -> tuple:
    """(MatchResult, review code or None). The MatchResult is always the
    one match_product gives. The code (TITLE_NEEDS_PUBLISHER or
    TITLE_NOT_ON_LIST, see swlc/catalog_match.py) is set only when no
    curated alias hit, generated matching found no product, and the
    catalog lookup refused the row on purpose. The other code,
    SHARED_SUPPORT_LINES (curated review_versions), comes with a product
    and no cycle: generated matching picked the product, but the version
    column or the version in the name starts with a listed prefix. A
    product whose curated alias was blocked by its publisher guard gives
    no code. Neither does TITLE_NEEDS_PUBLISHER when the version column is
    not empty and decides no single cycle of the refused products ("99.9",
    "banana"): that is a version mismatch, not a missing publisher. An
    empty version keeps the code."""
    return _match(name, version, aliases, products, catalog_index,
                  publisher, True)


def _match(name, version, aliases, products, catalog_index, publisher,
           noted: bool) -> tuple:
    hit, result, blocked = _curated(name, version, aliases, products,
                                    publisher)
    if result.product is not None:
        result = replace(result, source=CURATED)
    if catalog_index is None:
        return result, None
    if hit:
        if result.product is None:
            return result, None
        others, _tails = catalog_index.lookup(
            name, publisher, _fits(version, catalog_index, products))
        if any(pid != result.product for pid in others):
            return MatchResult(None, None, AMBIGUOUS), None
        return result, None
    return _generated(name, version, publisher, catalog_index, products,
                      blocked, noted)


def _generated(name: str, version: str, publisher: str, index,
               products: dict[str, list[dict]],
               blocked: frozenset = frozenset(),
               noted: bool = False) -> tuple:
    """Generated matching (rule C): (MatchResult, review code or None).
    Products in blocked (their alias hit
    the name but its publisher guard failed) are never matched here. The version column is used; when it is
    empty, a version token split off the name is used instead. When both
    exist and disagree, the row is not decided: NO_CYCLE, product known.
    So is a version starting with a curated no_cycle_versions prefix. A
    version column or name version starting with a curated review_versions
    prefix is not decided either, and also gets that entry's review code,
    unless the version names one support line (11-ltsc keeps cycle
    11-ltsc)."""
    fits = _fits(version, index, products)
    if noted:
        pids, tails, note = index.lookup_noted(name, publisher, fits)
    else:
        (pids, tails), note = index.lookup(name, publisher, fits), None
    pids = tuple(p for p in pids if p not in blocked)
    if not pids:
        code = None
        if note is not None and not blocked.intersection(note[1]):
            code = note[0]
            if code == TITLE_NEEDS_PUBLISHER and (version or "").strip() \
                    and not any(_generated_cycle(p, None, version, index,
                                                 products)[0] is not None
                                for p in note[1]):
                code = None
        return MatchResult(None, None, NO_ALIAS), code
    if len(pids) > 1:
        return MatchResult(None, None, AMBIGUOUS), None
    product = pids[0]
    cycle, reason = _generated_cycle(product, tails[product], version,
                                     index, products)
    prefixes, review = index.review.get(product, ((), None))
    versions = (split_version(version or ""),
                split_version(tails[product] or ""))
    if review is not None and _old_numbering(prefixes, versions) \
            and (cycle is None
                 or tuple(split_version(cycle.get("cycle", ""))) in prefixes) \
            and not _names_line(prefixes, versions, products.get(product)):
        # A version that fits several support lines (curated).
        return (MatchResult(product, None, NO_CYCLE, source=GENERATED),
                review if noted else None)
    return MatchResult(product, cycle, reason, source=GENERATED), None


def _names_line(prefixes: tuple, versions: tuple, cycles) -> bool:
    """Whether a version names one support line under a review prefix
    (11-ltsc, 11-server): it starts with a longer cycle label that starts
    with the prefix. Such a row is not flagged for review."""
    for label in (c.get("cycle", "") for c in cycles or ()):
        parts = tuple(split_version(label))
        if any(len(parts) > len(p) and parts[:len(p)] == p
               and tuple(v[:len(parts)]) == parts
               for p in prefixes for v in versions):
            return True
    return False


def _fits(version: str, index, products: dict[str, list[dict]]):
    """The check the version-in-name rule needs (see
    swlc/catalog_match.py): whether this row's version decides one cycle
    of a product, given the version token split off the name."""
    def fits(product: str, tail: str) -> bool:
        cycle, _reason = _generated_cycle(product, tail, version, index,
                                          products)
        return cycle is not None
    return fits


def _generated_cycle(product: str, tail, version: str, index,
                     products: dict[str, list[dict]]) -> tuple:
    """(cycle dict or None, reason code) for a generated match."""
    column = split_version(version or "")
    parts = column or split_version(tail or "")
    if not parts:
        return None, NO_VERSION
    if _old_numbering(index.no_cycle.get(product, ()),
                      (parts, split_version(tail or ""))):
        # A version in a numbering the cycles do not use (curated).
        return None, NO_CYCLE
    labels = [c.get("cycle", "") for c in products.get(product) or []]
    best, tied = best_cycle(parts, labels)
    if best is None:
        return None, NO_CYCLE
    if len(_distinct_by_parts(tied)) > 1:
        return None, AMBIGUOUS
    if _finer_cycle_missed(parts, best, labels):
        return None, NO_CYCLE
    if column and tail and _disagree(split_version(tail), column, labels):
        return None, NO_CYCLE
    return _cycle_dict(products[product], best), None


def _old_numbering(prefixes: tuple, versions: tuple) -> bool:
    """Whether any version starts with one of the curated prefixes."""
    return any(tuple(v[:len(p)]) == p for p in prefixes for v in versions)


def _finer_cycle_missed(parts: list[str], best: str,
                        labels: list[str]) -> bool:
    """Mixed-granularity guard. When the chosen cycle has child cycles in
    the same product (4.6 has 4.6.1 and 4.6.2; 2 has 2.426), the version
    has another part after the cycle's depth that is the next part of none
    of them, and that part is shaped like a build (not all digits, more
    than three digits, or zero-padded: 4.6.01590, 4.8.4084), the version
    may belong to a child the data cannot name: the cycle is not decided.
    A plain number of three digits or fewer with no leading zero is a
    patch or minor release of the cycle itself (Log4j 2.17.1 is 2, Jenkins
    2.587 is 2). A cycle with no children is unchanged (Python 3.12.1150.0
    is 3.12)."""
    base = split_version(best)
    depth = len(base)
    if len(parts) <= depth:
        return False
    nexts = set()
    for label in labels:
        lp = split_version(label)
        if len(lp) > depth and lp[:depth] == base:
            nexts.add(lp[depth])
    extra = parts[depth]
    if not nexts or extra in nexts:
        return False
    plain = extra.isdigit() and len(extra) <= 3 \
        and not (len(extra) > 1 and extra[0] == "0")
    return not plain


def _picks(parts: list[str], labels: list[str]) -> set:
    """The distinct cycles (as part tuples) a version picks; empty if none."""
    best, tied = best_cycle(parts, labels)
    return set(_distinct_by_parts(tied)) if best is not None else set()


def _disagree(name_parts: list[str], column: list[str],
              labels: list[str]) -> bool:
    """Whether the version read from the name and the version column
    disagree. When both pick a cycle they must pick the same one; when
    either picks none, they must be equal on their shared leading parts."""
    by_name, by_column = _picks(name_parts, labels), _picks(column, labels)
    if by_name and by_column:
        return by_name != by_column
    n = min(len(name_parts), len(column))
    return name_parts[:n] != column[:n]


def _curated(name: str, version: str, aliases: list[dict],
             products: dict[str, list[dict]], publisher: str = "") -> tuple:
    """(hit, MatchResult, blocked) from the alias table. hit is True when
    any alias key hits the name, whatever the result: a hit with no result
    still decides the row and stops generated matching. An alias whose
    'publisher' list the row's publisher does not satisfy does not hit, but
    its product goes in blocked so generated matching cannot find it."""
    norm = normalize_name(name or "")
    hits, blocked = _alias_hits(norm, aliases, publisher)
    if not hits:
        return False, MatchResult(None, None, NO_ALIAS), blocked
    return True, _decide(norm, version, hits, products), blocked


def _alias_hits(norm: str, aliases: list[dict], publisher: str) -> tuple:
    """(hits, blocked) for a normalized name, in alias table order. An
    AliasTable gives only the entries that can hit; a plain list is
    scanned in full."""
    if isinstance(aliases, AliasTable):
        candidates = aliases.candidates(norm)
    else:
        candidates = _keyed(aliases)
    hits: list[tuple[str, dict]] = []
    blocked = set()
    for key, entry in candidates:
        if not _hits(norm, key, entry["match"]):
            continue
        if _publisher_ok(entry, publisher):
            hits.append((key, entry))
        else:
            blocked.add(entry["product"])
    return hits, frozenset(blocked)


def _keyed(aliases: list[dict]):
    """(normalized key, entry) for each entry, checked first, in order."""
    for pos, entry in enumerate(aliases, 1):
        _check_once(entry, pos)
        yield _norm_key(entry["key"]), entry


def _first_word(text: str) -> str:
    return text.partition(" ")[0]


class AliasTable(list):
    """The alias list of one loaded data folder. A plain list that also
    groups its entries by the first word of their normalized key, built
    on first use and dropped when the list changes. _hits needs the name
    to equal the key or to start with the key and a space, so a name can
    only hit keys with the same first word: a row looks at one group, not
    the whole table. Entries keep table order within a group. Each
    entry's key is read once, when the groups are built: changing an
    entry in place after first use is not supported. Neither is changing
    the list through list's own methods (list.append(table, x)), which
    bypass the reset."""

    _groups = None

    def candidates(self, norm: str) -> list:
        if self._groups is None:
            groups: dict = {}
            for key, entry in _keyed(self):
                if key:  # an empty key never hits
                    groups.setdefault(_first_word(key), []).append(
                        (key, entry))
            self._groups = groups
        return self._groups.get(_first_word(norm), [])

    def __reduce_ex__(self, protocol):
        # Copies and pickles are plain lists, without the groups.
        return list, (list(self),)


def _changes(name: str):
    method = getattr(list, name)

    def change(self, *args, **kwargs):
        self._groups = None
        return method(self, *args, **kwargs)
    return change


for _name in ("__init__", "__setitem__", "__delitem__", "__iadd__",
              "__imul__", "append", "extend", "insert", "pop", "remove", "clear",
              "sort", "reverse"):
    setattr(AliasTable, _name, _changes(_name))


# Alias entries already checked, by id. The entry itself is kept as the
# value, so an id is never reused by another object while it is listed.
# Checking every entry on every row cost more than the matching itself.
_CHECKED: dict = {}


def _check_once(entry, pos: int) -> None:
    if _CHECKED.get(id(entry)) is entry:
        return
    _check(entry, pos)
    if len(_CHECKED) >= 4096:
        _CHECKED.clear()
    _CHECKED[id(entry)] = entry


@lru_cache(maxsize=4096)
def _norm_key(key: str) -> str:
    return normalize_name(key)


def _decide(norm: str, version: str, hits: list,
            products: dict[str, list[dict]]) -> MatchResult:
    if len({e["product"] for _, e in hits}) > 1:
        return MatchResult(None, None, AMBIGUOUS)

    # Same product: exact beats prefix, then the longest key wins.
    if any(e["match"] == "exact" for _, e in hits):
        hits = [(k, e) for k, e in hits if e["match"] == "exact"]
    longest = max(len(k) for k, _ in hits)
    hits = [(k, e) for k, e in hits if len(k) == longest]
    key, entry = hits[0]
    product = entry["product"]
    if len({_rule(e) for _, e in hits}) > 1:
        return MatchResult(product, None, AMBIGUOUS)

    labels = [c.get("cycle", "") for c in products.get(product) or []]
    rest = norm[len(key):].split()
    from_name = entry["version_from"] == "name"

    def finish(result: MatchResult, used_parts: int) -> MatchResult:
        # Prefix aliases are strict: words left after the key (and after
        # the version text read from the name) must be edition words, or a
        # numbered word and its number ("update 23").
        if entry["match"] == "prefix":
            skip = _words_for_parts(rest, used_parts) if from_name else 0
            if not _tail_ok(rest[skip:], entry.get("edition_words") or [],
                            entry.get("numbered_words") or []):
                return MatchResult(None, None, NO_ALIAS)
        if result.cycle is not None and "kev" in entry:
            # The alias's sourced CISA KEV pair rides along with a match.
            return replace(result, kev=dict(entry["kev"]))
        return result

    if "cycle" in entry:
        return finish(
            _exact_cycle(product, [entry["cycle"]], products, labels), 0)

    text = " ".join(rest) if from_name else (version or "")
    parts = split_version(text)
    if not parts:
        if from_name and _year_clash(split_version(version or ""), labels):
            # The name gives no version and the column is a calendar
            # version (2023.22.1) for a product whose cycles are not years
            # (Python 3.x): another product with the same name.
            return finish(MatchResult(None, None, NO_ALIAS), 0)
        return finish(MatchResult(product, None, NO_VERSION), 0)

    # When no version matched, treat the first name word as the version,
    # but only when it looks like one (starts with a digit, or v and a
    # digit): "Python Launcher" must not read "launcher" as a version and
    # so slip past the tail-word rule.
    first = len(split_version(rest[0])) \
        if rest and _versionish(rest[0]) else 0
    # Name/version cross-check: an alias that reads the version from the
    # name, on a row whose version column is not empty, decides only when
    # the two agree. Otherwise the row is NO_CYCLE (product known).
    column = split_version(version or "") if from_name else []
    bmap = entry.get("build_map")
    if bmap is not None:
        # Strict: a version outside the map never falls back to direct
        # matching, so a service-pack build cannot land on an RTM cycle.
        best_key, tied_keys = best_cycle(parts, list(bmap))
        if best_key is None:
            return finish(MatchResult(product, None, NO_CYCLE), first)
        targets = _targets(bmap, tied_keys)
        used = len(split_version(best_key))
        if column and _map_disagrees(column, targets, bmap, labels,
                                     entry.get("column_map")):
            return finish(MatchResult(product, None, NO_CYCLE), used)
        return finish(_exact_cycle(product, targets, products, labels), used)

    best, tied = best_cycle(parts, labels)
    if best is None:
        return finish(MatchResult(product, None, NO_CYCLE), first)
    used = len(split_version(best))
    if len(_distinct_by_parts(tied)) > 1:
        return finish(MatchResult(product, None, AMBIGUOUS), used)
    if _finer_cycle_missed(parts, best, labels):
        return finish(MatchResult(product, None, NO_CYCLE), used)
    if column and _disagree(parts, column, labels):
        return finish(MatchResult(product, None, NO_CYCLE), used)
    return finish(MatchResult(product, _cycle_dict(products[product], best),
                              None), used)


def _map_disagrees(column: list[str], targets: list[str], bmap: dict,
                   labels: list[str], cmap=None) -> bool:
    """For a build-map alias reading the name. The map's keys are name
    forms (years) and the column is usually a build number in another
    space, so the column counts only when its leading parts are a key of
    the alias's column_map (builds to the cycles they can be), a key of
    the build_map, or a cycle label. Then the cycle the name gives must be
    among the cycles the column can be; otherwise the row is not decided.
    A column that is none of these is not checked."""
    want = set(_distinct_by_parts(targets))
    for space in (cmap, bmap):
        if not space:
            continue
        key, tied = best_cycle(column, list(space))
        if key is not None and not want <= set(
                _distinct_by_parts(_targets(space, tied))):
            return True
    by_label = _picks(column, labels)
    return bool(by_label) and not want <= by_label


def _is_year(part: str) -> bool:
    return len(part) == 4 and part.isdigit() and 1990 <= int(part) <= 2100


def _year_clash(column: list[str], labels: list[str]) -> bool:
    """Whether the column's first part is a year while no cycle of the
    product starts with one."""
    if not column or not _is_year(column[0]):
        return False
    return not any(_is_year((split_version(label) or [""])[0])
                   for label in labels)


def _versionish(word: str) -> bool:
    return word[:1].isdigit() or (word[:1] == "v" and word[1:2].isdigit())


def _targets(bmap: dict, keys: list[str]) -> list[str]:
    out: list[str] = []
    for k in keys:
        value = bmap[k]
        out.extend(value if isinstance(value, list) else [value])
    return out


def _words_for_parts(words: list[str], used_parts: int) -> int:
    """Fewest leading whole words whose version parts cover used_parts."""
    if used_parts <= 0:
        return 0
    for count in range(1, len(words) + 1):
        if len(split_version(" ".join(words[:count]))) >= used_parts:
            return count
    return len(words)


def _tail_ok(words: list[str], edition_words: list[str],
             numbered_words=()) -> bool:
    """Every tail word is an edition word or bare punctuation ("-"). A
    numbered word must be followed by one whole number (one to three ASCII
    digits, no leading zero), a whole number is allowed only right after a
    numbered word, and only one numbered word may appear: "cumulative
    update 23" passes; "update", "cumulative 23", "23 update", "update 14
    14", "update 14 update 2", "update 014" and "update 1000" do not."""
    allowed = {normalize_name(w) for w in edition_words}
    numbered = {normalize_name(w) for w in numbered_words}

    def number(word: str) -> bool:
        return (word.isascii() and word.isdigit() and len(word) <= 3
                and word[0] != "0")

    if sum(w in numbered for w in words) > 1:
        return False
    for i, w in enumerate(words):
        if not w.strip(".-_"):
            continue
        if w in numbered:
            if i + 1 >= len(words) or not number(words[i + 1]):
                return False
        elif not (w in allowed
                  or (number(w) and i > 0 and words[i - 1] in numbered)):
            return False
    return True


def _exact_cycle(product: str, targets: list[str],
                 products: dict[str, list[dict]],
                 labels: list[str]) -> MatchResult:
    """Resolve alias-named cycle labels; each must exist exactly."""
    wanted = _distinct_by_parts(targets)
    if len(wanted) > 1:
        return MatchResult(product, None, AMBIGUOUS)
    if not wanted or not wanted[0]:
        return MatchResult(product, None, NO_CYCLE)
    for label in labels:
        if tuple(split_version(label)) == wanted[0]:
            return MatchResult(product, _cycle_dict(products[product], label),
                               None)
    return MatchResult(product, None, NO_CYCLE)


def _cycle_dict(cycles: list[dict], label: str) -> dict:
    for cyc in cycles:
        if cyc.get("cycle", "") == label:
            return cyc
    raise AssertionError("cycle label vanished")  # pragma: no cover
