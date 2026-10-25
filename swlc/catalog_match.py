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
joined-up strings. A phrase that equals the product's own one-word title
(vendor "prometheus" for Prometheus) is stricter: the publisher, without
corporate words (inc, ltd, gmbh, foundation, the, ...), must be exactly that
phrase, so "Prometheus Group Inc." does not confirm Prometheus. Known limit:
a same-name vendor ("Moodle Pty Ltd" for Moodle) still confirms.

A one-word title matches only when the publisher confirms the product (or a
step c drop did, which needs the same confirmation) or the product is on
single_word_allowlist. Products on generated_off and products whose catalog
category is "device" never match here. An exclusion blocks one product when
its cleaned name equals ANY candidate form of the row (whole, cleaned,
vendor-dropped, version-split) and, when given, its publisher token is in
the publisher; exclusions never touch curated aliases. A name of more than
MAX_WORDS words is never matched by title.
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
# A locale is a language-region tag (with "-" or "_"): an ISO 639-1
# language and an ISO 3166-1 region. Fixed lists, so results match on
# every Python version; a word such as "go-to" is never a locale.
_LANGS = frozenset((
    "aa ab ae af ak am an ar as av ay az ba be bg bi bm bn bo br bs ca "
    "ce ch co cr cs cu cv cy da de dv dz ee el en eo es et eu fa ff fi "
    "fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie "
    "ig ii ik io is it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv "
    "kw ky la lb lg li ln lo lt lu lv mg mh mi mk ml mn mr ms mt my na "
    "nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu rm "
    "rn ro ru rw sa sc sd se sg si sk sl sm sn so sq sr ss st su sv sw "
    "ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi vo wa "
    "wo xh yi yo za zh zu"
).split())
_REGIONS = frozenset((
    "ad ae af ag ai al am ao aq ar as at au aw ax az ba bb bd be bf bg "
    "bh bi bj bl bm bn bo bq br bs bt bv bw by bz ca cc cd cf cg ch ci "
    "ck cl cm cn co cr cu cv cw cx cy cz de dj dk dm do dz ec ee eg eh "
    "er es et fi fj fk fm fo fr ga gb gd ge gf gg gh gi gl gm gn gp gq "
    "gr gs gt gu gw gy hk hm hn hr ht hu id ie il im in io iq ir is it "
    "je jm jo jp ke kg kh ki km kn kp kr kw ky kz la lb lc li lk lr ls "
    "lt lu lv ly ma mc md me mf mg mh mk ml mm mn mo mp mq mr ms mt mu "
    "mv mw mx my mz na nc ne nf ng ni nl no np nr nu nz om pa pe pf pg "
    "ph pk pl pm pn pr ps pt pw py qa re ro rs ru rw sa sb sc sd se sg "
    "sh si sj sk sl sm sn so sr ss st sv sx sy sz tc td tf tg th tj tk "
    "tl tm tn to tr tt tv tw tz ua ug um us uy uz va vc ve vg vi vn vu "
    "wf ws ye yt za zm zw"
).split())


def _is_locale(word: str) -> bool:
    lang, sep, region = word.replace("_", "-").partition("-")
    return bool(sep) and lang in _LANGS and region in _REGIONS
_GROUP_RE = re.compile(r"[(\[]([^()\[\]]*)[)\]]")
_VENDOR_SPLIT_RE = re.compile(r"[_.-]+")
# Publisher words that say what kind of body the publisher is, not who it
# is. Removed before the strict check on a vendor word that is also the
# product's own one-word title.
CORPORATE_WORDS = frozenset((
    "inc", "incorporated", "ltd", "limited", "llc", "gmbh", "corp",
    "corporation", "co", "company", "pty", "plc", "sa", "ag", "bv",
    "foundation", "project", "team", "org", "organization", "software",
    "the"))
# Names with more words than this are never matched by title: no product
# title is that long, and it bounds the work on a hostile row.
MAX_WORDS = 64


def tokens(text: str) -> tuple:
    """Whole letter-and-digit tokens of normalized text."""
    return tuple(_TOKEN_RE.findall(normalize_name(text or "")))


def _arch_or_locale(word: str) -> bool:
    return word in _ARCH_WORDS or _is_locale(word)


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
    self_titles: MappingProxyType  # one-word id -> its title as tokens
    phrases: MappingProxyType     # id -> confirming token phrases (sorted)
    leads: MappingProxyType       # leading phrase -> ids it confirms
    max_lead: int                 # longest leading phrase, in tokens
    allow: frozenset              # single_word_allowlist ids
    off: frozenset                # generated_off ids
    devices: frozenset            # ids with category "device"
    exclusions: MappingProxyType  # cleaned name -> ((id, publisher), ...)

    def phrase_ok(self, pid: str, phrase: tuple, pub: tuple) -> bool:
        """Whether this confirming phrase of pid is in the publisher. A
        phrase equal to the product's own one-word title (vendor
        "prometheus" for Prometheus) confirms only when the publisher,
        without corporate words, is exactly that phrase."""
        if self.self_titles.get(pid) == phrase:
            return tuple(t for t in pub if t not in CORPORATE_WORDS) \
                == phrase
        return _has_run(pub, phrase)

    def confirms(self, pid: str, pub: tuple) -> bool:
        return any(self.phrase_ok(pid, p, pub)
                   for p in self.phrases.get(pid, ()))

    def _excluded(self, forms: set, pub: tuple) -> set:
        """Ids an exclusion blocks for any candidate form of this row."""
        out = set()
        for form in forms:
            for pid, phrase in self.exclusions.get(form, ()):
                if not phrase or _has_run(pub, phrase):
                    out.add(pid)
        return out

    def lookup(self, name: str, publisher: str = "") -> tuple:
        """(product ids, {id: version token or None}).

        No ids: no generated match. One id: that product. More: AMBIGUOUS.
        """
        norm = normalize_name(name or "")
        clean = strip_arch(norm)
        words = clean.split(" ")
        if len(words) > MAX_WORDS:
            return (), {}
        pub = tokens(publisher)

        # Leading phrases that are runs of the publisher, at most max_lead
        # words, each position looked at once.
        leading = []
        for k in range(1, min(len(words), self.max_lead + 1)):
            if not _TOKEN_RE.fullmatch(words[k - 1]):
                break
            lead = tuple(words[:k])
            if _has_run(pub, lead):
                leading.append((lead, " ".join(words[k:])))

        # Every candidate form, for the exclusions: the whole and cleaned
        # name, the vendor-dropped forms and each with its version split off.
        forms = {norm, clean}
        forms.update(rest for _lead, rest in leading)
        for form in list(forms):
            split = split_tail(form)
            if split:
                forms.add(split[0])
        blocked = self._excluded(forms, pub)

        def allowed(pid, confirmed):
            if pid in self.off or pid in self.devices or pid in blocked:
                return False
            if pid in self.one_word and pid not in self.allow:
                return confirmed or self.confirms(pid, pub)
            return True

        # Level 1: the whole name, then the name without arch/locale groups.
        for cand in (norm, clean):
            pids = self.titles.get(cand)
            if pids:
                ok = tuple(p for p in pids if allowed(p, False))
                return ok, {p: None for p in ok}

        # Level 2: vendor-dropped forms and version-split forms, pooled.
        found = {}

        def take(cand, tail, only=None):
            for pid in self.titles.get(cand, ()):
                if only is not None and pid not in only:
                    continue
                if pid not in found and allowed(pid, only is not None):
                    found[pid] = tail

        dropped = []
        for lead, rest in leading:
            pids = frozenset(p for p in self.leads.get(lead, ())
                             if self.phrase_ok(p, lead, pub))
            if pids:
                dropped.append((rest, pids))
        for cand, pids in dropped:
            take(cand, None, pids)
        for cand in (norm, clean):
            split = split_tail(cand)
            if split:
                take(split[0], split[1])
        for cand, pids in dropped:
            split = split_tail(cand)
            if split:
                take(split[0], split[1], pids)
        ids = tuple(sorted(found))
        return ids, {p: found[p] for p in ids}


def _vendor_phrase(vendor: str) -> tuple:
    return tuple(t for t in _VENDOR_SPLIT_RE.split(vendor) if t)


def build_index(catalog: dict, curation=None) -> CatalogIndex:
    """Build the read-only index. catalog: {id: products.json record};
    curation: the validated curation.json, or None for an empty one."""
    cur = curation or {}
    titles, one_word, self_titles, phrases, leads = {}, set(), {}, {}, {}
    devices = set()
    aliases = cur.get("publisher_aliases") or {}
    for pid in sorted(catalog):
        rec = catalog[pid]
        title = normalize_name(rec["title"])
        titles.setdefault(title, []).append(pid)
        if " " not in title:
            one_word.add(pid)
            self_titles[pid] = tokens(title)
        if rec.get("category") == "device":
            devices.add(pid)
        found = set()
        for vendor in rec.get("vendors") or ():
            found.add(_vendor_phrase(vendor))
        for space in rec.get("namespaces") or ():
            found.add((space,))
        for phrase in (aliases.get(pid) or {}).get("phrases") or ():
            found.add(tokens(phrase))
        found.discard(())
        phrases[pid] = tuple(sorted(found))
        for phrase in found:
            leads.setdefault(phrase, set()).add(pid)
    exclusions = {}
    for item in cur.get("exclusions") or ():
        name = strip_arch(normalize_name(item["name"]))
        exclusions.setdefault(name, set()).add(
            (item["product"], tokens(item["publisher"])))
    return CatalogIndex(
        titles=MappingProxyType({k: tuple(v) for k, v in titles.items()}),
        one_word=frozenset(one_word),
        self_titles=MappingProxyType(self_titles),
        phrases=MappingProxyType(phrases),
        leads=MappingProxyType({k: frozenset(v) for k, v in leads.items()}),
        max_lead=max((len(k) for k in leads), default=0),
        allow=frozenset(i["product"]
                        for i in cur.get("single_word_allowlist") or ()),
        off=frozenset(cur.get("generated_off") or ()),
        devices=frozenset(devices),
        exclusions=MappingProxyType(
            {k: tuple(sorted(v)) for k, v in exclusions.items()}))
