from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from .catalog_match import _has_run, tokens
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
    return (entry["version_from"], entry.get("cycle"), frozen, words)


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
    hit, result, blocked = _curated(name, version, aliases, products,
                                    publisher)
    if result.product is not None:
        result = replace(result, source=CURATED)
    if catalog_index is None:
        return result
    if hit:
        if result.product is None:
            return result
        others, _tails = catalog_index.lookup(
            name, publisher, _fits(version, catalog_index, products))
        if any(pid != result.product for pid in others):
            return MatchResult(None, None, AMBIGUOUS)
        return result
    return _generated(name, version, publisher, catalog_index, products,
                      blocked)


def _generated(name: str, version: str, publisher: str, index,
               products: dict[str, list[dict]],
               blocked: frozenset = frozenset()) -> MatchResult:
    """Generated matching (rule C). Products in blocked (their alias hit
    the name but its publisher guard failed) are never matched here. The version column is used; when it is
    empty, a version token split off the name is used instead. When both
    exist and disagree, the row is not decided: NO_CYCLE, product known.
    So is a version starting with a curated no_cycle_versions prefix."""
    pids, tails = index.lookup(name, publisher,
                               _fits(version, index, products))
    pids = tuple(p for p in pids if p not in blocked)
    if not pids:
        return MatchResult(None, None, NO_ALIAS)
    if len(pids) > 1:
        return MatchResult(None, None, AMBIGUOUS)
    product = pids[0]
    cycle, reason = _generated_cycle(product, tails[product], version,
                                     index, products)
    return MatchResult(product, cycle, reason, source=GENERATED)


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
    hits: list[tuple[str, dict]] = []
    blocked = set()
    for pos, entry in enumerate(aliases, 1):
        _check(entry, pos)
        key = _norm_key(entry["key"])
        if not _hits(norm, key, entry["match"]):
            continue
        if _publisher_ok(entry, publisher):
            hits.append((key, entry))
        else:
            blocked.add(entry["product"])
    blocked = frozenset(blocked)
    if not hits:
        return False, MatchResult(None, None, NO_ALIAS), blocked
    return True, _decide(norm, version, hits, products), blocked


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
        # the version text read from the name) must be edition words.
        if entry["match"] == "prefix":
            skip = _words_for_parts(rest, used_parts) if from_name else 0
            if not _tail_ok(rest[skip:], entry.get("edition_words") or []):
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


def _tail_ok(words: list[str], edition_words: list[str]) -> bool:
    """Every tail word is an edition word or bare punctuation ("-")."""
    allowed = {normalize_name(w) for w in edition_words}
    return all(not w.strip(".-_") or w in allowed for w in words)


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
