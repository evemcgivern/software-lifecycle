from __future__ import annotations

from dataclasses import dataclass

from .errors import DataError
from .normalize import best_cycle, normalize_name, split_version

NO_ALIAS = "NO_ALIAS"
NO_CYCLE = "NO_CYCLE"
NO_VERSION = "NO_VERSION"
AMBIGUOUS = "AMBIGUOUS"

_MODES = ("exact", "prefix")
_SOURCES = ("name", "version")


@dataclass(frozen=True)
class MatchResult:
    product: str | None
    cycle: dict | None
    reason: str | None


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
    return (entry["version_from"], entry.get("cycle"), frozen)


def _distinct_by_parts(labels: list[str]) -> list[tuple[str, ...]]:
    seen: list[tuple[str, ...]] = []
    for label in labels:
        parts = tuple(split_version(label))
        if parts not in seen:
            seen.append(parts)
    return seen


def match_product(name: str, version: str, aliases: list[dict],
                  products: dict[str, list[dict]]) -> MatchResult:
    """Map a raw name and version to (product, cycle dict), or a reason code.

    Never guesses: no fuzzy scores, no regular expressions built from alias
    text. A name hitting aliases for two products, or a version fitting
    several cycles, is AMBIGUOUS.
    """
    norm = normalize_name(name or "")
    hits: list[tuple[str, dict]] = []
    for pos, entry in enumerate(aliases, 1):
        _check(entry, pos)
        key = normalize_name(entry["key"])
        if _hits(norm, key, entry["match"]):
            hits.append((key, entry))
    if not hits:
        return MatchResult(None, None, NO_ALIAS)
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

    if "cycle" in entry:
        return _exact_cycle(product, [entry["cycle"]], products, labels)

    if entry["version_from"] == "name":
        text = norm[len(key):]
    else:
        text = version or ""
    parts = split_version(text)
    if not parts:
        return MatchResult(product, None, NO_VERSION)

    bmap = entry.get("build_map")
    if bmap is not None:
        # Strict: a version outside the map never falls back to direct
        # matching, so a service-pack build cannot land on an RTM cycle.
        best_key, tied_keys = best_cycle(parts, list(bmap))
        if best_key is None:
            return MatchResult(product, None, NO_CYCLE)
        targets: list[str] = []
        for k in tied_keys:
            value = bmap[k]
            targets.extend(value if isinstance(value, list) else [value])
        return _exact_cycle(product, targets, products, labels)

    best, tied = best_cycle(parts, labels)
    if best is None:
        return MatchResult(product, None, NO_CYCLE)
    if len(_distinct_by_parts(tied)) > 1:
        return MatchResult(product, None, AMBIGUOUS)
    return MatchResult(product, _cycle_dict(products[product], best), None)


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
