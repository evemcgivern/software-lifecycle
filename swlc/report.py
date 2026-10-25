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
    ("review_urgently", "Review urgently", "review_urgently"),
    ("accepted_risk", "Accepted risk", None),
    ("ownerless", "Ownerless", None),
    ("golden_overrides", "Golden source overrides", None),
)
CSV_COLUMNS = (
    "id", "name", "version", "publisher", "owners", "rows", "state",
    "reason", "product", "cycle", "eol_used", "eol_source", "eol_endoflife",
    "eol_export", "eol_export_raw", "support", "extended_support",
    "golden_applied", "golden_expired", "dates_disagree", "accepted_risk",
    "exception_expired", "decision_needed", "kev", "kev_stale",
    "change_ref", "problem_ref", "lists", "match_source")

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


def _item_block(it: dict, eol_snap: str) -> list:
    head = "- **%s** %s" % (_name(it["name"]), _disp(it["version"]))
    if it["publisher"]:
        head += ", publisher %s" % _disp(it["publisher"])
    out = [head + " (id `%s`)" % it["id"]]
    sub = []
    sub.append("State: %s" % STATE_TEXT[it["state"]])
    if it.get("match_source") in SOURCE_TEXT:
        sub.append("Product %s." % SOURCE_TEXT[it["match_source"]])
    owners = ", ".join(_disp(o) for o in it["owners"])
    if owners:
        sub.append("Owners: %s. Rows: %d" % (owners, it["rows"]))
    else:
        sub.append("Owners: none listed. This item cannot be actioned until "
                   "an owner is named. Rows: %d" % it["rows"])
    if it["state"] == "unmatched":
        sub.append(_unmatched_line(it))
    sub.extend(_date_lines(it, eol_snap))
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


def _kev_age_text(result: dict) -> str:
    age = result["data_release"]["kev_age_days"]
    if age < 0:
        return "KEV snapshot date is later than the checked-on date"
    return "KEV snapshot is %s old" % _days(age)


def render_markdown(result: dict, meta: dict) -> str:
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
    out += ["", "Items: %d (rows: %d). %s." % (
        result["counts"]["items"], result["counts"]["rows"],
        "; ".join("%s %d" % (h.lower(), counts[name])
                  for name, h, _ in SECTIONS))]
    out += ["", MATCH_CAVEAT]

    for number, (name, heading, _) in enumerate(SECTIONS, 1):
        ids = result["lists"][name]
        out += ["", "## %s (%d)" % (heading, len(ids)), ""]
        if name == "review_urgently":
            out += ["Needs review, not a finding that any version is "
                    "affected. KEV is checked only for matched items that "
                    "are past end of life or end within the window.", ""]
        if not ids:
            if name == "review_urgently" and not result["kev_current"]:
                out.append("None listed. KEV overlay is not current, so "
                           "this does not show there are none.")
            else:
                out.append("None.")
            continue
        for gid in ids:
            out.extend(_item_block(items[gid], eol_snap))

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


def render_csv(result: dict) -> str:
    member = {}
    for name, ids in result["lists"].items():
        for gid in ids:
            member.setdefault(gid, []).append(name)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n",
                        quoting=csv.QUOTE_ALL)
    writer.writerow(CSV_COLUMNS)
    for it in result["items"]:
        row = dict(it)
        row["owners"] = "; ".join(it["owners"])
        row["decision_needed"] = "; ".join(it["decision_needed"])
        row["lists"] = "; ".join(sorted(member.get(it["id"], [])))
        writer.writerow([_cell(row.get(col)) for col in CSV_COLUMNS])
    return buf.getvalue()
