"""Generated matching: an inventory name to a product title in the catalog.

Used only when no curated alias decides a row (see swlc/matching.py). The
index is built once per data release from products.json and curation.json
and never changes after that. No fuzzy scores, no prefixes of words, no
slugs: a candidate either equals a normalized product title or it does not.

Candidate order (the row's raw name is first normalized by normalize_name):

  step  candidate                                       example
  ----  ----------------------------------------------  ------------------------
  a     the whole normalized name                       "bind 9"
  b     a, with architecture and locale groups dropped  "foo (x64 en-us)" -> "foo"
        (in parentheses or brackets anywhere, or bare
        at the end)
  c     b, with a leading vendor phrase dropped: only   "mozilla firefox" with
        a phrase that confirms that product and also    publisher Mozilla
        appears in the row's publisher                  -> "firefox"
  d     a, b and each c form with a trailing version    "foo 2.1" -> "foo" + 2.1
        token split off (v?N(.N)*[a-z]?; "8u392" is
        not split)

  Level 1 is a then b: the first of them that equals a title decides, even
  when that product is then refused (a one-word title the publisher does not
  confirm, an exclusion, generated_off): a name that is exactly a title is
  never matched to a different product through a split.
  Level 2 pools every c and d candidate: two different products found there
  make the row AMBIGUOUS. A product found by several candidates keeps the
  first (earliest in the order above).

Vendor check: the row's publisher is normalized and split into whole tokens
on any character that is not a letter or digit. A product's confirming
phrases are its CPE vendors (split on "_", "-" and "."), its purl
namespaces (kept whole, so a dotted maven group id or a hyphenated owner
never equals a publisher token) and its curated publisher_aliases. A phrase
confirms only as a contiguous run of whole tokens: no fragments, prefixes or
joined-up strings.

A one-word title matches only when the publisher confirms the product (or a
step c drop did, which needs the same confirmation) or the product is on
single_word_allowlist. Products on generated_off never match here.
Exclusions block one product for one cleaned name (and, when given, a
publisher token); they never touch curated aliases.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType

from .normalize import normalize_name

_TOKEN_RE = re.compile(r"[^\W_]+")
_TAIL_RE = re.compile(r"v?\d+(?:\.\d+)*[a-z]?")
_ARCH_WORDS = frozenset(("x64", "x86", "amd64", "arm64", "aarch64",
                         "32-bit", "64-bit"))
_LOCALE_RE = re.compile(r"[a-z]{2}[-_][a-z]{2}")
_GROUP_RE = re.compile(r"[(\[]([^()\[\]]*)[)\]]")
_VENDOR_SPLIT_RE = re.compile(r"[_.-]+")


def tokens(text: str) -> tuple:
    """Whole letter-and-digit tokens of normalized text."""
    return tuple(_TOKEN_RE.findall(normalize_name(text or "")))


def _arch_or_locale(word: str) -> bool:
    return word in _ARCH_WORDS or bool(_LOCALE_RE.fullmatch(word))


def strip_arch(norm: str) -> str:
    """Drop architecture and locale groups from a normalized name: a group
    in parentheses or brackets made only of such words, anywhere, and such
    bare words at the end."""
    def group(m):
        words = m.group(1).replace(",", " ").split()
        return " " if words and all(_arch_or_locale(w) for w in words) \
            else m.group(0)

    words = _GROUP_RE.sub(group, norm).split()
    while len(words) > 1 and _arch_or_locale(words[-1]):
        words.pop()
    return " ".join(words)


def split_tail(cand: str):
    """(name, version token) when the last word is a version token, else
    None. A one-word candidate is never split."""
    head, sep, last = cand.rpartition(" ")
    if sep and head and _TAIL_RE.fullmatch(last):
        return head, last
    return None


def _has_run(pub: tuple, phrase: tuple) -> bool:
    n = len(phrase)
    return any(pub[i:i + n] == phrase for i in range(len(pub) - n + 1))


@dataclass(frozen=True)
class CatalogIndex:
    """Read-only lookups built once from products.json and curation.json."""
    titles: MappingProxyType      # normalized title -> product ids (sorted)
    one_word: frozenset           # ids whose normalized title is one word
    phrases: MappingProxyType     # id -> confirming token phrases (sorted)
    leads: MappingProxyType       # leading phrase -> ids it confirms
    allow: frozenset              # single_word_allowlist ids
    off: frozenset                # generated_off ids
    exclusions: MappingProxyType  # (cleaned name, id) -> publisher phrases

    def confirms(self, pid: str, pub: tuple) -> bool:
        return any(_has_run(pub, p) for p in self.phrases.get(pid, ()))

    def _allowed(self, pid: str, clean: str, norm: str, pub: tuple,
                 confirmed: bool) -> bool:
        if pid in self.off:
            return False
        for name in (clean, norm):
            for phrase in self.exclusions.get((name, pid), ()):
                if not phrase or _has_run(pub, phrase):
                    return False
        if pid in self.one_word and pid not in self.allow:
            return confirmed or self.confirms(pid, pub)
        return True

    def lookup(self, name: str, publisher: str = "") -> tuple:
        """(product ids, {id: version token or None}).

        No ids: no generated match. One id: that product. More: AMBIGUOUS.
        """
        norm = normalize_name(name or "")
        clean = strip_arch(norm)
        pub = tokens(publisher)

        # Level 1: the whole name, then the name without arch/locale groups.
        for cand in (norm, clean):
            pids = self.titles.get(cand)
            if pids:
                ok = tuple(p for p in pids
                           if self._allowed(p, clean, norm, pub, False))
                return ok, {p: None for p in ok}

        # Level 2: vendor-dropped forms and version-split forms, pooled.
        found = {}

        def take(cand, tail, only=None, confirmed=False):
            for pid in self.titles.get(cand, ()):
                if only is not None and pid not in only:
                    continue
                if pid not in found and self._allowed(
                        pid, clean, norm, pub, confirmed):
                    found[pid] = tail

        dropped = []
        words = clean.split(" ")
        for k in range(1, len(words)):
            lead = tuple(words[:k])
            if not all(_TOKEN_RE.fullmatch(w) for w in lead):
                break
            pids = self.leads.get(lead)
            if pids and _has_run(pub, lead):
                dropped.append((" ".join(words[k:]), pids))
        for cand, pids in dropped:
            take(cand, None, pids, True)
        for cand in (norm, clean):
            split = split_tail(cand)
            if split:
                take(split[0], split[1])
        for cand, pids in dropped:
            split = split_tail(cand)
            if split:
                take(split[0], split[1], pids, True)
        ids = tuple(sorted(found))
        return ids, {p: found[p] for p in ids}


def _vendor_phrase(vendor: str) -> tuple:
    return tuple(t for t in _VENDOR_SPLIT_RE.split(vendor) if t)


def build_index(catalog: dict, curation=None) -> CatalogIndex:
    """Build the read-only index. catalog: {id: products.json record};
    curation: the validated curation.json, or None for an empty one."""
    cur = curation or {}
    titles, one_word, phrases, leads = {}, set(), {}, {}
    aliases = cur.get("publisher_aliases") or {}
    for pid in sorted(catalog):
        rec = catalog[pid]
        title = normalize_name(rec["title"])
        titles.setdefault(title, []).append(pid)
        if " " not in title:
            one_word.add(pid)
        found = set()
        for vendor in rec.get("vendors") or ():
            found.add(_vendor_phrase(vendor))
        for space in rec.get("namespaces") or ():
            found.add((space,))
        for phrase in aliases.get(pid) or ():
            found.add(tokens(phrase))
        found.discard(())
        phrases[pid] = tuple(sorted(found))
        for phrase in found:
            leads.setdefault(phrase, set()).add(pid)
    exclusions = {}
    for item in cur.get("exclusions") or ():
        key = (strip_arch(normalize_name(item["name"])), item["product"])
        exclusions.setdefault(key, set()).add(tokens(item["publisher"]))
    return CatalogIndex(
        titles=MappingProxyType({k: tuple(v) for k, v in titles.items()}),
        one_word=frozenset(one_word),
        phrases=MappingProxyType(phrases),
        leads=MappingProxyType({k: frozenset(v) for k, v in leads.items()}),
        allow=frozenset(i["product"]
                        for i in cur.get("single_word_allowlist") or ()),
        off=frozenset(cur.get("generated_off") or ()),
        exclusions=MappingProxyType(
            {k: tuple(sorted(v)) for k, v in exclusions.items()}))
