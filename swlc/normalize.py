from __future__ import annotations

import re
import unicodedata

# Frozen list of tokens dropped from product names.
_DROP_TOKENS = ("(64-bit)", "(32-bit)", "x64", "x86", "en-us")
_DROP_RE = re.compile(
    r"(?<!\S)(?:" + "|".join(re.escape(t) for t in _DROP_TOKENS) + r")(?!\S)"
)
_SPACE_RE = re.compile(r"\s+")
_VERSION_SPLIT_RE = re.compile(r"[.\-_\s]+")


def _pass(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = unicodedata.normalize("NFKC", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return _SPACE_RE.sub(" ", _DROP_RE.sub(" ", text)).strip()


def normalize_name(raw: str) -> str:
    """NFKC, casefold, collapse whitespace, drop frozen tokens, strip.

    Repeats until stable so that dropping a token never leaves a new one
    behind (keeps the function idempotent).
    """
    text = raw
    while True:
        new = _pass(text)
        if new == text:
            return new
        text = new


def is_multi_line(raw: str) -> bool:
    """Whether a version cell holds more than one line. Line breaks at
    either end are ignored."""
    return len(raw.strip().splitlines()) > 1


_ENTRY_SPLIT_RE = re.compile(r"[\s,;|/&()\[\]]+")
_BITNESS_RE = re.compile(r"(?<![\w.])(?:16|32|64)[\s-]?bit(?!\w)", re.I)
# A piece that is only a version number, and the words that may join them.
_NUMBER_RE = re.compile(r"v?[0-9]+(?:[._][0-9]+)*", re.I)
# One version written with commas, as in Windows file details.
_COMMA_VERSION_RE = re.compile(r"[0-9]+(?:\s*,\s*[0-9]+){3}")
_JOIN_WORDS = ("and", "or", "also")


def version_entries(raw: str) -> list[str]:
    """The distinct pieces of a version cell that could be the entries of
    a version list, in cell order. Bitness ("64-bit") is dropped. When the
    cell holds only version numbers and joining words, the entries are the
    numbers. Otherwise another word is there ("kernel", "LTS"), so a
    number may belong to something else: a one-line cell gives nothing,
    and a cell with several lines gives only a plain number that starts
    a line."""
    text = _BITNESS_RE.sub(" ", raw)
    if _COMMA_VERSION_RE.fullmatch(text.strip()):
        return []
    pieces = [p for p in _ENTRY_SPLIT_RE.split(text)
              if p and p.casefold() not in _JOIN_WORDS]
    if not all(_NUMBER_RE.fullmatch(p) for p in pieces):
        lines = text.strip().splitlines()
        firsts = [line.split()[0] for line in lines if line.split()]
        pieces = [w for w in firsts if _NUMBER_RE.fullmatch(w)] \
            if len(lines) > 1 else []
    return list(dict.fromkeys(pieces))


def split_version(raw: str) -> list[str]:
    """Strip a leading ``v``; split on ``.``, ``-``, ``_`` and space."""
    text = unicodedata.normalize("NFKC", raw).casefold().strip()
    if text.startswith("v"):
        text = text[1:]
    return [p for p in _VERSION_SPLIT_RE.split(text) if p]


def cycle_matches(version_parts: list[str], cycle: str) -> bool:
    """True when the cycle's parts equal the leading version parts.

    Whole parts are compared as strings, never prefixes of a part.
    """
    cycle_parts = split_version(cycle)
    if not cycle_parts or len(cycle_parts) > len(version_parts):
        return False
    return [p.casefold() for p in version_parts[: len(cycle_parts)]] == cycle_parts


def best_cycle(
    version_parts: list[str], cycles: list[str]
) -> tuple[str | None, list[str]]:
    """Longest matching cycle, plus every cycle that fits equally long."""
    matched = [(len(split_version(c)), c) for c in cycles if cycle_matches(version_parts, c)]
    if not matched:
        return None, []
    longest = max(n for n, _ in matched)
    tied = [c for n, c in matched if n == longest]
    return tied[0], tied
