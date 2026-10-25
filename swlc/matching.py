from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

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
    if "build_map" in entry:
        bmap = entry["build_map"]
        if not isinstance(bmap, dict) or not bmap:
            raise bad("'build_map' must be a non-empty object")
        for value in bmap.values():
            values = value if isinstance(value, list) else [value]
            if not values or not all(isinstance(v, str) and v.strip()
                                     for v in values):
                raise bad("'build_map' values must be cycle strings")
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
    hit, result = _curated(name, version, aliases, products)
    if result.product is not None:
        result = replace(result, source=CURATED)
    if catalog_index is None:
        return result
    if hit:
        if result.product is None:
            return result
        others, _tails = catalog_index.lookup(name, publisher)
        if any(pid != result.product for pid in others):
            return MatchResult(None, None, AMBIGUOUS)
        return result
    return _generated(name, version, publisher, catalog_index, products)


def _generated(name: str, version: str, publisher: str, index,
               products: dict[str, list[dict]]) -> MatchResult:
    """Generated matching (rule C). The version column is used; when it is
    empty, a version token split off the name is used instead. When both
    exist and disagree, the row is not decided: NO_CYCLE, product known."""
    pids, tails = index.lookup(name, publisher)
    if not pids:
        return MatchResult(None, None, NO_ALIAS)
    if len(pids) > 1:
        return MatchResult(None, None, AMBIGUOUS)
    product = pids[0]
    tail = tails[product]

    def result(cycle, reason):
        return MatchResult(product, cycle, reason, source=GENERATED)

    column = split_version(version or "")
    parts = column or split_version(tail or "")
    if not parts:
        return result(None, NO_VERSION)
    labels = [c.get("cycle", "") for c in products.get(product) or []]
    best, tied = best_cycle(parts, labels)
    if best is None:
        return result(None, NO_CYCLE)
    if len(_distinct_by_parts(tied)) > 1:
        return result(None, AMBIGUOUS)
    if column and tail and _disagree(split_version(tail), column, labels):
        return result(None, NO_CYCLE)
    return result(_cycle_dict(products[product], best), None)


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
             products: dict[str, list[dict]]) -> tuple:
    """(hit, MatchResult) from the alias table. hit is True when any alias
    key hits the name, whatever the result: a hit with no result still
    decides the row and stops generated matching."""
    norm = normalize_name(name or "")
    hits: list[tuple[str, dict]] = []
    for pos, entry in enumerate(aliases, 1):
        _check(entry, pos)
        key = _norm_key(entry["key"])
        if _hits(norm, key, entry["match"]):
            hits.append((key, entry))
    if not hits:
        return False, MatchResult(None, None, NO_ALIAS)
    return True, _decide(norm, version, hits, products)


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
        if column and _map_disagrees(column, targets, bmap, labels):
            return finish(MatchResult(product, None, NO_CYCLE), used)
        return finish(_exact_cycle(product, targets, products, labels), used)

    best, tied = best_cycle(parts, labels)
    if best is None:
        return finish(MatchResult(product, None, NO_CYCLE), first)
    used = len(split_version(best))
    if len(_distinct_by_parts(tied)) > 1:
        return finish(MatchResult(product, None, AMBIGUOUS), used)
    if column and _disagree(parts, column, labels):
        return finish(MatchResult(product, None, NO_CYCLE), used)
    return finish(MatchResult(product, _cycle_dict(products[product], best),
                              None), used)


def _map_disagrees(column: list[str], targets: list[str], bmap: dict,
                   labels: list[str]) -> bool:
    """For a build-map alias reading the name: the map's keys are name forms
    (years) and the column is usually a build number in another space, so
    the column counts only when it reads as a map key or as a cycle label
    itself; then it must name the same cycle as the name."""
    want = set(_distinct_by_parts(targets))
    key, tied = best_cycle(column, list(bmap))
    if key is not None and set(_distinct_by_parts(_targets(bmap, tied))) \
            != want:
        return True
    by_label = _picks(column, labels)
    return bool(by_label) and by_label != want


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
