"""Render an assessment result as JSON, Markdown and CSV.

Pure: no file access, no clock. Every date line names its source; text taken
from the inventory is cleaned, cut to MAX_DISPLAY characters and escaped
before it reaches Markdown, and CSV cells that a spreadsheet could read as a
formula are neutralized.
"""
from __future__ import annotations

import csv
import html
import io
import json
import unicodedata
from datetime import date, timedelta

from .assess import add_months
from .classify import PARENT_ABSENT, PARENT_NO_DATE, inherited_states

MAX_DISPLAY = 120

KEV_LINE = ("The vendor and product appear in CISA KEV. This does not mean "
            "your version is affected.")
CLAIMS_LINE = ("Runs locally with no network by default; built to "
               "enterprise security practices; not independently assessed.")
# Fixed text, printed once in report.md under the summary counts.
MATCH_CAVEAT = ("Matches rest on name and publisher only. Rows we could not "
                "tell apart are listed as unmatched. Check the source and "
                "cycle before relying on any row.")

STATE_TEXT = {
    "supported": "supported",
    "mainstream_ended": "mainstream support has ended",
    "ends_soon": "ends within the lookahead window",
    "past_eol": "past end of life",
    "unmatched": "could not be matched",
}
REASON_TEXT = {
    "NO_ALIAS": "no alias entry or product title fits this name",
    "NO_CYCLE": ("no cycle matches this version, or the version in the name "
                 "disagrees with it"),
    "NO_VERSION": "no version given",
    "AMBIGUOUS": "more than one cycle fits this version",
}
REASON_TEXT_NO_PRODUCT = {
    "AMBIGUOUS": "the name fits more than one product",
}
SOURCE_TEXT = {
    "curated": "matched by a curated alias",
    "generated": "matched by product title",
}
DECISION_TEXT = {
    "DIFFERENT_DATE": (
        "The export date and the endoflife.date date differ. The ITAM lead "
        "settles which date to use. Nothing here is auto-resolved."),
    "NO_ENDOFLIFE_DATE": (
        "endoflife.date has no date to compare with the export date. The "
        "ITAM lead settles which date to use."),
    "EXPORT_DATE_UNREADABLE": (
        "The export date could not be read as YYYY-MM-DD. The ITAM lead "
        "settles the date."),
    "EXPORT_DATES_CONFLICT": (
        "Rows for this item carry different export dates. The ITAM lead "
        "settles the date."),
    "GOLDEN_EXPIRED": (
        "The golden source's review-by date has passed, so the item is "
        "back on the dates-disagree list. The ITAM lead settles the date "
        "and renews or ends the golden source."),
    "GOLDEN_EXPORT_UNUSABLE": (
        "Your golden-sources file says to use the export date, but the "
        "export has no usable date. The ITAM lead settles the date."),
    "EXCEPTION_EXPIRED": (
        "The risk exception has expired. The asset owner requests risk "
        "acceptance again; the risk owner and an independent approver sign "
        "off. The tool names roles and never assigns people."),
}
# (list name, heading, finding type or None)
SECTIONS = (
    ("past_eol", "Past end of life", "past_eol"),
    ("ends_soon", "Ends within the lookahead window", "ends_soon"),
    ("dates_disagree", "Dates disagree", "dates_disagree"),
    ("unmatched", "Couldn't match", "unmatched"),
    ("review_urgently", "In CISA KEV, past or near end of life", "review_urgently"),
    ("accepted_risk", "Accepted risk", None),
    ("ownerless", "Ownerless", None),
    ("golden_overrides", "Golden source overrides", None),
)
INHERITED_HEADING = "Parent's date (inherited, not this item's own)"
HIDDEN_LINE = "%d items hidden: %d components, %d bundle members"
NO_PARENT_DATE = "parent has no date"
NEEDS_REVIEW_LEAD = ("Needs review: %d. Parts with a parent are listed in "
                     "their own section.")
PARTS = ("component", "bundle_member")
REVIEW_HEADING = "Names to review"
REVIEW_COLUMN = "Review reason"
REVIEW_POINTER = ("Names to review: %d of these were left unmatched on "
                  "purpose; see \"%s\" below.")
REVIEW_LEAD = ("Unmatched on purpose, not a finding. Each name looks like a "
               "catalog product, but there is not enough evidence to match "
               "it, so no product, cycle, date or state is claimed. To "
               "settle one, add a publisher that names the vendor, ask for "
               "a curated alias, or record that it is a different product. "
               "These items are also counted under "
               "\"Couldn't match\".")
SUPPORT_HEADING = "Support records"
SUPPORT_COLUMN = "Support records (from your file)"
SUPPORT_NOTE = ("A support record is listed in your file: %s, %s, %s on %s "
                "(scope: %s).")
SUPPORT_ANY_SCOPE = "any cycle of this product"
SUPPORT_CAVEAT = "The tool does not check that this record is current."
SUPPORT_CAVEAT_MANY = ("The tool does not check that these records are "
                       "current.")
# At most this many records per item in report.md and report.csv;
# report.json keeps them all.
SUPPORT_SHOWN = 10
SUPPORT_MORE = "and %d more in report.json"
NOT_MATCHED_LABEL = "Not matched to a dated item in this inventory"
SUPPORT_LEAD = (
    "From your support-records file, shown beside the vendor's dates. A "
    "record never changes an item's state, never puts an item on a list "
    "and never affects --fail-on. The tool does not check that a record "
    "was paid for or is current. Discovery coverage is unknown: software "
    "missing from this inventory may still be in use. Extended support may "
    "include only some fixes or editions. Record references are "
    "confidential; keep this report as private as the file.")
SUPPORT_COUNTS_LEAD = (
    "Listed: records that fit at least one dated item (an item with a "
    "product and cycle). Not matched to a dated item: records that fit "
    "none; this includes a product that appears in this inventory without "
    "a decided cycle or version. Listed and not matched add up to the "
    "records in the file. Ending within the lookahead window counts "
    "records from either group that end after the checked-on date and by "
    "the end of the window, so the counts overlap.")
SUPPORT_COUNTS = ("Listed against dated items in this inventory: %d. Ending "
                  "within the lookahead window: %d. " + NOT_MATCHED_LABEL
                  + ": %d.")
# Item sections whose items get a support-record note line.
SUPPORT_SECTIONS = ("past_eol", "ends_soon")
CSV_COLUMNS = (
    "id", "name", "version", "publisher", "owners", "rows", "state",
    "reason", "product", "cycle", "eol_used", "eol_source", "eol_endoflife",
    "eol_export", "eol_export_raw", "support", "extended_support",
    "golden_applied", "golden_expired", "dates_disagree", "accepted_risk",
    "exception_expired", "decision_needed", "kev", "kev_stale",
    "change_ref", "problem_ref", "lists", "match_source",
    "classification", "parent_ref", INHERITED_HEADING, REVIEW_COLUMN,
    SUPPORT_COLUMN)

_MD_SPECIAL = "\\`*_[]()#|~!"


# --- JSON ------------------------------------------------------------------

def render_json(result: dict, meta: dict) -> str:
    """Canonical JSON: sorted keys, ASCII only, trailing newline."""
    body = dict(result)
    body["meta"] = meta
    return json.dumps(body, sort_keys=True, indent=2) + "\n"


# --- text cleaning ---------------------------------------------------------

def _clean(text) -> str:
    kept = []
    for ch in str(text):
        cat = unicodedata.category(ch)
        if cat == "Cf":
            continue
        kept.append(" " if cat in ("Cc", "Zl", "Zp") else ch)
    return " ".join("".join(kept).split())


def _disp(text) -> str:
    """Inventory text for Markdown: cleaned, truncated, then escaped."""
    text = _clean(text)
    if len(text) > MAX_DISPLAY:
        text = text[:MAX_DISPLAY] + "..."
    text = "".join("\\" + ch if ch in _MD_SPECIAL else ch for ch in text)
    return html.escape(text, quote=True).replace("://", ":\\//")


def _name(text) -> str:
    return _disp(text) or "(blank)"


# --- Markdown --------------------------------------------------------------

def _snapshot(result: dict, key: str) -> str:
    as_of = date.fromisoformat(result["as_of"])
    return (as_of - timedelta(days=result["data_release"][key])).isoformat()


def _days(n: int) -> str:
    return "%d day" % n if n == 1 else "%d days" % n


def _val(value) -> str:
    if value is True:
        return "reached (no date given)"
    if value is False:
        return "none announced"
    return str(value)


def _flag_val(value, ended: str, ongoing: str) -> str:
    if value is True:
        return ongoing
    if value is False:
        return ended
    return str(value)


def _decision_lines(item: dict) -> list:
    codes = []
    if item.get("dates_disagree"):
        codes.append(item["dates_disagree"])
    codes.extend(item.get("decision_needed") or [])
    seen, out = set(), []
    for code in codes:
        if code in seen or code not in DECISION_TEXT:
            continue
        seen.add(code)
        out.append("**Decision needed:** " + DECISION_TEXT[code])
    return out


def _date_lines(it: dict, eol_snap: str) -> list:
    if it["state"] == "unmatched":
        return []
    eol_src = "per endoflife.date, snapshot " + eol_snap
    lines = []
    used = it["eol_used"]
    src = it["eol_source"]
    if src == "endoflife.date":
        where = eol_src
    elif src == "export":
        where = "per your export"
    else:
        where = "per your golden-sources file (manual date)"
    if used is None:
        lines.append("End of life: no date given %s" % eol_src)
    else:
        text = "End of life: %s %s" % (_val(used), where)
        if it["golden_applied"]:
            text += "; golden source per your file"
        lines.append(text)
    other = "Other date, shown beside the one used: " if it[
        "golden_applied"] else "Other date: "
    if src != "endoflife.date" and it["eol_endoflife"] is not None:
        lines.append(other + "%s %s" % (_val(it["eol_endoflife"]), eol_src))
    if src != "export" and it["eol_export_raw"]:
        shown = it["eol_export"] or "unreadable text: %s" % _disp(
            it["eol_export_raw"])
        lines.append(other + "%s per your export" % shown)
    if it["support"] is not None:
        lines.append("Mainstream support: %s %s" % (
            _flag_val(it["support"], "ended", "ongoing"), eol_src))
    if it["extended_support"] is not None:
        lines.append("Extended support: %s %s" % (
            _flag_val(it["extended_support"], "ended", "ongoing"), eol_src))
    return lines


def _unmatched_line(it: dict) -> str:
    reason = it["reason"]
    if it["product"]:
        why = REASON_TEXT.get(reason, "unknown")
        lead = ("product known (%s), but no cycle was matched"
                % _disp(it["product"]))
    else:
        why = REASON_TEXT_NO_PRODUCT.get(reason) or REASON_TEXT.get(
            reason, "unknown")
        lead = "no known product was matched"
    return ("**Unverified:** %s. Reason %s: %s. No end-of-life date is "
            "claimed." % (lead, reason, why))


def hidden_counts(result: dict) -> tuple:
    """(components, bundle members) that --governable-only leaves out."""
    kinds = [it["classification"] for it in result["items"]]
    return kinds.count("component"), kinds.count("bundle_member")


def hidden_line(result: dict) -> str:
    comp, member = hidden_counts(result)
    return HIDDEN_LINE % (comp + member, comp, member)


def _needs_review(it: dict) -> bool:
    return it["classification"] not in PARTS


def _parent_item(it: dict, by_id: dict):
    ref = it["parent_ref"]
    if ref is None or ref["kind"] == "product":
        return None
    return by_id.get(ref["value"])


def _parent_shown(it: dict, by_id: dict) -> str:
    """The parent as Markdown text: its name, never the raw Parent cell."""
    parent = _parent_item(it, by_id)
    if parent is not None:
        return _name(parent["name"])
    return _disp(it["parent_ref"]["value"])


def _parent_lines(it: dict, by_id: dict) -> list:
    ref = it["parent_ref"]
    life = it["inherited_lifecycle"]
    if ref is None:
        return []
    if life:
        eol = "no date given" if life["eol"] is None else _val(life["eol"])
        return ["%s: end of life %s per endoflife.date, state %s, from "
                "parent %s (id `%s`)" % (
                    INHERITED_HEADING, eol,
                    STATE_TEXT.get(life["state"], _disp(life["state"])),
                    _parent_shown(it, by_id), life["parent_id"])]
    if PARENT_ABSENT in it["classification_basis"]:
        return ["Parent: %s, not in this inventory. No date shown."
                % _parent_shown(it, by_id)]
    parent = _parent_item(it, by_id)
    lines = []
    if parent is not None:
        lines.append("Parent: %s (id `%s`)" % (_name(parent["name"]),
                                               parent["id"]))
    if PARENT_NO_DATE in it["classification_basis"]:
        lines.append("%s: %s" % (INHERITED_HEADING, NO_PARENT_DATE))
    return lines


def _ends_word(ends_on: str, as_of: str) -> str:
    """The item-state rule: a date on or before the checked-on date has
    ended (see assess._state)."""
    return "ended" if ends_on <= as_of else "ends"


def _shown(it: dict, as_of: str) -> tuple:
    """(entries to print, how many more are only in report.json).

    Records that have not ended come first, nearest end first, then
    ended ones, most recently ended first, so the cap never hides the
    next end date. report.json keeps its own order."""
    entries = it.get("support_records") or []
    ahead = [e for e in entries if e["ends_on"] > as_of]
    ended = [e for e in entries if e["ends_on"] <= as_of]
    ended = sorted(ended, key=lambda e: e["ends_on"], reverse=True)
    ordered = ahead + ended
    return ordered[:SUPPORT_SHOWN], max(0, len(ordered) - SUPPORT_SHOWN)


def _support_lines(it: dict, as_of: str) -> list:
    entries, more = _shown(it, as_of)
    if not entries:
        return []
    out = [SUPPORT_NOTE % (_disp(e["record_ref"]), _disp(e["kind"]),
                           _ends_word(e["ends_on"], as_of), e["ends_on"],
                           _disp(e["scope"]) if e["scope"]
                           else SUPPORT_ANY_SCOPE)
           for e in entries]
    if more:
        out.append(SUPPORT_MORE % more + ".")
    out.append(SUPPORT_CAVEAT if len(entries) == 1 and not more
               else SUPPORT_CAVEAT_MANY)
    return out


def _support_cell(it: dict, as_of: str) -> str:
    entries, more = _shown(it, as_of)
    parts = ["%s, %s, %s on %s, scope %s%s" % (
        e["record_ref"], e["kind"], _ends_word(e["ends_on"], as_of),
        e["ends_on"], e["scope"] or SUPPORT_ANY_SCOPE,
        ", owner role " + e["owner_role"] if e["owner_role"] else "")
        for e in entries]
    if more:
        parts.append(SUPPORT_MORE % more)
    return "; ".join(parts)


def _record_line(rec: dict, as_of: str) -> str:
    ends_on = rec["ends_on"].isoformat()
    return "- %s, product %s, scope %s, %s, %s on %s." % (
        _disp(rec["record_ref"]), _disp(rec["product"]),
        _disp(rec["scope"]) if rec["scope"] else SUPPORT_ANY_SCOPE,
        _disp(rec["kind"]), _ends_word(ends_on, as_of), ends_on)


def _support_section(result: dict, records: list) -> list:
    """The "Support records" section: records ending within the window and
    records that fit no dated item here. Record fields only, no inventory
    text."""
    as_of = result["as_of"]
    end = add_months(date.fromisoformat(as_of), result["lookahead_months"])
    listed = {e["record_ref"] for it in result["items"]
              for e in it.get("support_records") or ()}
    soon = [r for r in records
            if as_of < r["ends_on"].isoformat() <= end.isoformat()]
    none = [r for r in records if r["record_ref"] not in listed]
    counts = result["counts"]["support_records"]
    out = ["", "## %s" % SUPPORT_HEADING, "", SUPPORT_LEAD, "",
           SUPPORT_COUNTS_LEAD, "",
           SUPPORT_COUNTS % (counts["listed"], counts["ending_soon"],
                             counts["not_matched"]), ""]
    for label, chosen in (("Ending within the lookahead window", soon),
                          (NOT_MATCHED_LABEL, none)):
        out += ["%s (%d):" % (label, len(chosen)), ""]
        out += [_record_line(r, as_of) for r in chosen] or ["None."]
        out.append("")
    return out[:-1]


def _item_block(it: dict, eol_snap: str, by_id: dict,
                as_of: str | None = None) -> list:
    head = "- **%s** %s" % (_name(it["name"]), _disp(it["version"]))
    if it["publisher"]:
        head += ", publisher %s" % _disp(it["publisher"])
    out = [head + " (id `%s`)" % it["id"]]
    sub = []
    sub.append("State: %s" % STATE_TEXT[it["state"]])
    sub.append("Classification: %s (basis: %s)" % (
        it["classification"],
        ", ".join(it["classification_basis"]) or "none"))
    sub.extend(_parent_lines(it, by_id))
    if it.get("match_source") in SOURCE_TEXT:
        sub.append("Product %s." % SOURCE_TEXT[it["match_source"]])
    owners = ", ".join(_disp(o) for o in it["owners"])
    if owners:
        sub.append("Owners: %s. Inventory rows: %d" % (owners, it["rows"]))
    else:
        sub.append("Owners: none listed. This item cannot be actioned until "
                   "an owner is named. Inventory rows: %d" % it["rows"])
    if it["state"] == "unmatched":
        sub.append(_unmatched_line(it))
    sub.extend(_date_lines(it, eol_snap))
    if as_of is not None:
        sub.extend(_support_lines(it, as_of))
    if it["dates_disagree"]:
        sub.append("Dates disagree: %s" % it["dates_disagree"])
    if it["accepted_risk"]:
        sub.append("Accepted risk per your exceptions file. The tool lists "
                   "it and does not confirm the sign-off.")
    if it["kev"]:
        text = "KEV: %s Needs review." % KEV_LINE
        if it["kev_stale"]:
            text += " KEV data was not current when this was checked."
        sub.append(text)
    for key, label in (("change_ref", "Change"), ("problem_ref", "Problem")):
        if it[key]:
            sub.append("%s reference: %s" % (label, _disp(it[key])))
    sub.extend(_decision_lines(it))
    out.extend("  - " + line for line in sub)
    return out


def _review_block(it: dict) -> list:
    """An ambiguous item: name, version, publisher and the fixed reason.
    No product, cycle, date or state."""
    head = "- **%s**" % _name(it["name"])
    if _disp(it["version"]):
        head += " " + _disp(it["version"])
    if it["publisher"]:
        head += ", publisher %s" % _disp(it["publisher"])
    return [head + " (id `%s`)" % it["id"],
            "  - Review: %s" % it["ambiguity"]["reason"]]


def _kev_age_text(result: dict) -> str:
    age = result["data_release"]["kev_age_days"]
    if age < 0:
        return "KEV snapshot date is later than the checked-on date"
    return "KEV snapshot is %s old" % _days(age)


def render_markdown(result: dict, meta: dict,
                    governable_only: bool = False,
                    support_records: list | None = None) -> str:
    """``support_records`` is the loaded file (swlc.support), or None when
    no file was given; then the "Support records" section is left out."""
    rel = result["data_release"]
    eol_snap = _snapshot(result, "eol_age_days")
    kev_snap = _snapshot(result, "kev_age_days")
    items = {it["id"]: it for it in result["items"]}
    counts = result["counts"]["lists"]
    out = ["# Software lifecycle report", ""]
    out.append("Checked on: %s. Lookahead: %d months."
               % (result["as_of"], result["lookahead_months"]))
    out.append("Tool version: %s. Data release: %s."
               % (_disp(meta.get("tool_version", "")), _disp(rel["id"])))
    out.append("End-of-life dates: per endoflife.date, snapshot %s "
               "(%s old)." % (eol_snap, _days(rel["eol_age_days"])))
    out.append("KEV: CISA KEV catalog %s, snapshot %s (%s old)."
               % (_disp(rel["kev_catalog_version"]), kev_snap,
                  _days(rel["kev_age_days"])))
    profile = meta.get("profile") or {}
    if profile.get("name") and profile["name"] != "generic":
        out.append("Profile: %s. **Unverified:** this profile has not been "
                   "checked against real exports (status: %s)."
                   % (_disp(profile["name"]),
                      _disp(profile.get("status") or "Unverified")))
    out.append("")
    out.append(CLAIMS_LINE)
    out.append("")
    out.append("This report shows end-of-life dates from your data and the "
               "snapshots above. It does not say whether any version is "
               "affected by a flaw. It contains text from your inventory; "
               "keep it as private as the inventory.")
    if not result["kev_current"]:
        out += ["", "KEV overlay is not current. %s." % _kev_age_text(result)]
    for warning in result["warnings"]:
        out += ["", "Warning: %s" % _disp(warning)]
    ambiguous = [it["id"] for it in result["items"] if it["ambiguity"]]
    out += ["", "Items: %d (rows: %d; inventory rows, not installs). %s; %s %d." % (
        result["counts"]["items"], result["counts"]["rows"],
        "; ".join("%s %d" % (h.lower().replace("cisa kev", "CISA KEV"),
                             counts[name])
                  for name, h, _ in SECTIONS),
        REVIEW_HEADING.lower(), len(ambiguous))]
    out += ["", MATCH_CAVEAT]
    if governable_only:
        out += ["", hidden_line(result)]

    def hidden(gid):
        return governable_only and not _needs_review(items[gid])

    def emit(heading, count, ids, lead=None, none_text="None.",
             notes=False):
        out.extend(["", "## %s (%d)" % (heading, count), ""])
        if lead:
            out.extend(lead)
        shown = [gid for gid in ids if not hidden(gid)]
        if not ids:
            out.append(none_text)
        elif not shown:
            out.append("All of these are hidden by --governable-only.")
        for gid in shown:
            out.extend(_item_block(items[gid], eol_snap, items,
                                   result["as_of"] if notes else None))

    unmatched = result["lists"]["unmatched"]
    review = [gid for gid in unmatched if _needs_review(items[gid])]
    parts = [gid for gid in unmatched if not _needs_review(items[gid])]
    attention = [it["id"] for it in result["items"]
                 if it["inherited_lifecycle"]
                 and it["inherited_lifecycle"]["state"] in inherited_states]
    for name, heading, _ in SECTIONS:
        ids = result["lists"][name]
        if name == "unmatched":
            emit(heading, len(ids), review,
                 [NEEDS_REVIEW_LEAD % len(review),
                  REVIEW_POINTER % (len(ambiguous), REVIEW_HEADING), ""])
            # Never hidden: an ambiguous item is never a part.
            out.extend(["", "## %s (%d)" % (REVIEW_HEADING, len(ambiguous)),
                        "", REVIEW_LEAD, ""])
            if not ambiguous:
                out.append("None.")
            for gid in ambiguous:
                out.extend(_review_block(items[gid]))
            emit("Parts that could not be matched", len(parts), parts)
            emit("Parts of a parent past or near end of life",
                 len(attention), attention)
            continue
        lead = None
        none_text = "None."
        if name == "review_urgently":
            lead = ["Needs review, not a finding that any version is "
                    "affected. KEV is checked only for matched items that "
                    "are past end of life or end within the window.", ""]
            if not result["kev_current"]:
                none_text = ("None listed. KEV overlay is not current, so "
                             "this does not show there are none.")
        emit(heading, len(ids), ids, lead, none_text,
             name in SUPPORT_SECTIONS)

    if support_records is not None:
        out += _support_section(result, support_records)

    diff = result["diff"]
    if diff["available"]:
        out += ["", "## Changes since the previous report", ""]
        out.append("New: %s" % (", ".join("`%s`" % _disp(i) for i in diff["new"])
                                or "none"))
        out.append("")
        out.append("No longer present: %s" % (
            ", ".join("`%s`" % _disp(i) for i in diff["resolved"]) or "none"))
        out.append("")
        out.append("State changed: %s" % (
            ", ".join("`%s` %s to %s" % (_disp(c["id"]), _disp(c["from"]),
                                         _disp(c["to"]))
                      for c in diff["changed_state"]) or "none"))

    findings = [{"type": ftype, "id": gid}
                for name, _, ftype in SECTIONS if ftype
                for gid in result["lists"][name]]
    body = ",\n ".join(json.dumps(f) for f in findings)
    out += ["", "```findings", "[" + body + "]", "```", ""]
    return "\n".join(out)


# --- CSV -------------------------------------------------------------------

def _cell(value) -> str:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    text = str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def _parent_cell(it: dict, by_id: dict) -> str:
    ref = it["parent_ref"]
    if ref is None:
        return ""
    parent = _parent_item(it, by_id)
    value = ref["value"] if parent is None else parent["name"]
    return ref["kind"] + ":" + _cell(value)


def _inherited_cell(it: dict):
    life = it["inherited_lifecycle"]
    if life:
        return NO_PARENT_DATE if life["eol"] is None else life["eol"]
    return NO_PARENT_DATE if PARENT_NO_DATE in it[
        "classification_basis"] else ""


def render_csv(result: dict, governable_only: bool = False) -> str:
    by_id = {it["id"]: it for it in result["items"]}
    member = {}
    for name, ids in result["lists"].items():
        for gid in ids:
            member.setdefault(gid, []).append(name)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n",
                        quoting=csv.QUOTE_ALL)
    writer.writerow(CSV_COLUMNS)
    for it in result["items"]:
        if governable_only and not _needs_review(it):
            continue
        row = dict(it)
        row["parent_ref"] = _parent_cell(it, by_id)
        row[INHERITED_HEADING] = _inherited_cell(it)
        row[REVIEW_COLUMN] = (it["ambiguity"] or {}).get("reason")
        row[SUPPORT_COLUMN] = _support_cell(it, result["as_of"])
        row["owners"] = "; ".join(it["owners"])
        row["decision_needed"] = "; ".join(it["decision_needed"])
        row["lists"] = "; ".join(sorted(member.get(it["id"], [])))
        writer.writerow([_cell(row.get(col)) for col in CSV_COLUMNS])
    return buf.getvalue()
