#!/usr/bin/env python3
"""Write the synthetic demo estate: inventory, answer key, tracking file
and support-records file, and the sample report made from them.

    python3 examples/generate.py [OUTDIR]

OUTDIR defaults to this folder. A fixed seed makes every run byte-identical.
All products, publishers and owners are fictional. The planted cases are
checked against tests/fixtures/data on 2026-10-24 (a 12 month window ends
2027-10-24), with golden-sources.csv and exceptions.csv from this folder.
The expected states below are written by hand, not read from the tool.
sample-report.md is the tool's own report.md for the demo run on that
date, made from the generated files.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from swlc.cli import main as swlc_main  # noqa: E402
from swlc.inputs import item_id  # noqa: E402

SEED = 20261024
TOTAL_ROWS = 60
HEADER = ["Software Name", "Version", "Publisher", "Owner", "Install Count",
          "End of Life", "Parent"]
TEAMS = ["Finance Systems", "Infrastructure", "Support Desk", "HR Systems",
         "Marketing Ops", "Records Office", "Facilities"]
PAST, SOON, SUPPORTED, MAINSTREAM, UNMATCHED = (
    "past_eol", "ends_soon", "supported", "mainstream_ended", "unmatched")
EC, EV, SS = "Example Corp", "Example Vendor", "Sample Systems Inc"
FS, PL, NS = "Fictional Software Ltd", "Placeholder Labs", "Northwind Software"
HOSTILE = "Hostile Corp"
ACME = "Acme Corp"
INHERITED_STATES = (PAST, SOON, MAINSTREAM)


def case(label, name, version, publisher, state, lists=(), *, rows=None,
         reason=None, disagree=None, decision=(), parent="",
         classification=None, inherited_state=None, count_text=None):
    """One planted item. rows is [(owner, export date)]; default is one
    row owned by Finance Systems with no export date. parent is the Parent
    cell; a parent case also gives its class and the parent's state.
    count_text replaces the random Install Count cell of each row."""
    return {
        "case": label, "name": name, "version": version,
        "publisher": publisher, "state": state, "reason": reason,
        "lists": sorted(lists), "dates_disagree": disagree,
        "decision_needed": sorted(decision),
        "rows": rows or [("Finance Systems", "")], "parent": parent,
        "classification": classification,
        "inherited_state": inherited_state, "count_text": count_text,
    }


CASES = [
    case("past_eol_date", "Tidewater Suite", "4.2", EC, PAST, [PAST]),
    case("past_eol_flag", "Example SQL", "14", SS, PAST, [PAST]),
    case("eol_on_check_date", "Tidewater Suite", "1.0", EC, PAST, [PAST]),
    case("ends_within_12_months", "Tidewater Suite", "5.0", EC, SOON, [SOON]),
    case("window_edge_in", "Tidewater Suite", "2.0", EC, SOON, [SOON]),
    case("window_edge_out", "Tidewater Suite", "3.0", EC, SUPPORTED),
    case("dates_differ", "Tidewater Suite", "5.1", EC, SOON,
         [SOON, "dates_disagree"], rows=[("Finance Systems", "2027-04-30")],
         disagree="DIFFERENT_DATE"),
    case("no_endoflife_date", "Mapleton Reports", "3.1", FS, SUPPORTED,
         ["dates_disagree"], rows=[("Records Office", "2028-06-30")],
         disagree="NO_ENDOFLIFE_DATE", decision=["NO_ENDOFLIFE_DATE"]),
    case("export_dates_conflict", "Ironwood Scheduler", "2.0", PL, SUPPORTED,
         ["dates_disagree"],
         rows=[("Facilities", "2028-05-31"), ("Facilities", "2028-06-30")],
         disagree="EXPORT_DATES_CONFLICT",
         decision=["EXPORT_DATES_CONFLICT"]),
    case("no_alias", "Mystery Tool", "3.1", "Nobody Inc", UNMATCHED,
         [UNMATCHED], reason="NO_ALIAS"),
    case("no_cycle", "Brightline Editor", "9.0", FS, UNMATCHED, [UNMATCHED],
         reason="NO_CYCLE"),
    case("no_version", "Brightline Editor", "", FS, UNMATCHED, [UNMATCHED],
         reason="NO_VERSION"),
    case("ambiguous", "Orbit Client", "2", FS, UNMATCHED, [UNMATCHED],
         reason="AMBIGUOUS"),
    case("kev_alias_pair_past_eol", "Northwind Gateway", "4.1", NS, PAST,
         [PAST, "review_urgently"]),
    case("kev_alias_pair_supported_no_overlay", "Northwind Gateway", "5.0",
         NS, SUPPORTED),
    case("kev_product_ends_soon", "Example SQL", "15", EV, SOON,
         [SOON, "review_urgently"]),
    case("kev_product_supported_no_overlay", "Example SQL", "16", EV,
         SUPPORTED),
    case("golden_expired", "Pinecone Archive", "2.0", PL, SOON,
         [SOON, "dates_disagree"], rows=[("Records Office", "2027-05-31")],
         disagree="GOLDEN_EXPIRED", decision=["GOLDEN_EXPIRED"]),
    case("golden_active_moves_state", "Harborview CRM", "5.1", FS, PAST,
         [PAST, "golden_overrides"],
         rows=[("Marketing Ops", "2026-06-30")]),
    case("exception_active", "Demo OS 1.0", "1.0", FS, PAST,
         [PAST, "accepted_risk"],
         rows=[("Infrastructure", ""), ("Support Desk", "")]),
    # A count cell that is not a whole number: ignored and counted in
    # counts.count_invalid_cells, so the item has no count and comes last.
    case("exception_expired", "Redwood Backup", "1.0", SS, PAST, [PAST],
         rows=[("Infrastructure", "")], decision=["EXCEPTION_EXPIRED"],
         count_text="about 40"),
    case("ownerless", "Tidewater Suite", "6.0", EC, SUPPORTED, ["ownerless"],
         rows=[("", "")]),
    case("build_number_mapped", "Quillbase Database", "12.0.6024.0", PL,
         PAST, [PAST], rows=[("Infrastructure", "")]),
    case("build_number_supported", "Quillbase Database", "15.0.2000.5", PL,
         SUPPORTED, rows=[("Infrastructure", "")]),
    case("support_false_mainstream_ended", "Brightline Editor", "7.0", FS,
         MAINSTREAM),
    case("support_true_supported", "Brightline Editor", "8.0", FS,
         SUPPORTED),
    case("hostile_formula", "=cmd|' /C calc'!A0", "9", HOSTILE, UNMATCHED,
         [UNMATCHED], reason="NO_ALIAS"),
    case("hostile_markup", "<script>alert(1)</script>", "1", HOSTILE,
         UNMATCHED, [UNMATCHED], reason="NO_ALIAS"),
    case("hostile_pipe_backtick", "Util | `rm -rf` tool", "2", HOSTILE,
         UNMATCHED, [UNMATCHED], reason="NO_ALIAS"),
    # A product title with no publisher: unmatched on purpose, listed
    # under "Names to review" (item key ambiguity), never a finding.
    case("names_to_review", "Quillbase", "2019", "", UNMATCHED, [UNMATCHED],
         reason="NO_ALIAS"),
    # Parent cases: the part keeps its own state and lists; the parent's
    # state is shown against it and never puts it in past_eol.
    case("part-parent-past-eol", "Harborview CRM Mail Connector", "5.1.2",
         FS, UNMATCHED, [UNMATCHED], reason="NO_ALIAS",
         parent="Harborview CRM", classification="bundle_member",
         inherited_state=PAST),
    case("part-parent-absent", "Fieldnote Sync Agent", "1.2", PL, UNMATCHED,
         [UNMATCHED], reason="NO_ALIAS", parent="Demo OS 2.0",
         classification="bundle_member"),
    case("os-patch-one-os", "Security Update for Demo OS 1.0 (KB5000001)",
         "1", ACME, UNMATCHED, [UNMATCHED], reason="NO_ALIAS",
         classification="bundle_member", inherited_state=PAST),
]

# Filler: ordinary supported software, so only the planted rows reach a list.
FILLER = [
    ("Tidewater Suite", EC, "6.%d", (1, 4)),
    ("Brightline Editor", FS, "8.%d", (1, 3)),
    ("Mapleton Reports", FS, "3.%d", (2, 5)),
    ("Quillbase Database", PL, "15.0.2000.%d", (1, 4)),
    ("Copperfield Notes", PL, "2.%d", (0, 6)),
    ("Lantern Viewer", EC, "11.%d", (0, 5)),
    ("Redwood Backup", SS, "3.%d", (0, 4)),
]

TRACKING = [("exception_active", "CHG-1001", "PRB-2001"),
            ("past_eol_date", "CHG-1002", "")]

# Support records: (record_ref, product, scope, kind, ends_on, owner_role,
# planted cases the record fits). Fictional references. A record never
# changes a state or a list; the answer key says which items it is shown on.
FILLER_LANTERN = "filler:lanternviewer"
SUPPORT_RECORDS = [
    ("SR-1001", "tidewatersuite", "4", "extended support", "2027-06-30",
     "Application owner", ["past_eol_date"]),
    ("SR-1002", "examplesql", "14", "extended support", "2026-06-30", "",
     ["past_eol_flag"]),
    ("SR-1003", "tidewatersuite", "5.0", "vendor support", "2028-03-31",
     "ITAM lead", ["ends_within_12_months"]),
    ("SR-1004", "northwindgateway", "", "vendor support", "2029-01-31",
     "Infrastructure lead",
     ["kev_alias_pair_past_eol", "kev_alias_pair_supported_no_overlay"]),
    ("SR-1005", "copperfieldnotes", "9", "extended support", "2027-01-31",
     "", []),
    ("SR-1006", "brightlineeditor", "9.0", "vendor support", "2028-12-31",
     "", []),
    ("SR-1007", "lanternviewer", "", "vendor support", "2027-12-31",
     "Desktop lead", [FILLER_LANTERN]),
]
WINDOW = ("2026-10-24", "2027-10-24")


def _csv_bytes(rows) -> bytes:
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue().encode("utf-8")


def _key(c) -> tuple:
    return (c["publisher"], c["name"], c["version"])


def _support_key(ids: dict) -> dict:
    out: dict = {}
    for ref, _p, _s, _k, _e, _r, fits in SUPPORT_RECORDS:
        for label in fits:
            key = label if label == FILLER_LANTERN else ids[label]
            out.setdefault(key, []).append(ref)
    return {k: sorted(v) for k, v in sorted(out.items())}


def sample_report(files: dict) -> bytes:
    """Run the demo check on the generated files (with golden-sources.csv
    and exceptions.csv from this folder) and return its report.md."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for name in ("software-inventory.csv", "tracking.csv",
                     "support-records.csv"):
            (tmp_path / name).write_bytes(files[name])
        out = tmp_path / "out"
        argv = ["check", str(tmp_path / "software-inventory.csv"),
                "--data", str(ROOT / "tests" / "fixtures" / "data"),
                "--as-of", WINDOW[0],
                "--golden", str(HERE / "golden-sources.csv"),
                "--exceptions", str(HERE / "exceptions.csv"),
                "--tracking", str(tmp_path / "tracking.csv"),
                "--support-records", str(tmp_path / "support-records.csv"),
                "--out", str(out)]
        with contextlib.redirect_stdout(io.StringIO()):
            code = swlc_main(argv)
        if code != 0:
            raise SystemExit("demo check failed with exit code %d" % code)
        return (out / "report.md").read_bytes()


def build() -> dict:
    """Return {file name: bytes} for every generated file."""
    rng = random.Random(SEED)
    planted = {_key(c) for c in CASES}
    rows = []
    counts: dict = {}
    for c in CASES:
        for owner, export in c["rows"]:
            count = rng.randint(1, 400)
            if c["count_text"] is None:
                counts[c["case"]] = counts.get(c["case"], 0) + count
            else:
                count = c["count_text"]
            rows.append([c["name"], c["version"], c["publisher"], owner,
                         count, export, c["parent"]])
    while len(rows) < TOTAL_ROWS:
        name, publisher, fmt, span = rng.choice(FILLER)
        version = fmt if span is None else fmt % rng.randint(*span)
        if (publisher, name, version) in planted:
            continue
        shown = "%s %s" % (name, version) if name == "Demo OS" else name
        rows.append([shown, version, publisher, rng.choice(TEAMS),
                     rng.randint(1, 400), "", ""])
    rng.shuffle(rows)

    ids = {c["case"]: item_id(*_key(c)) for c in CASES}
    lists = {}
    for c in CASES:
        for name in c["lists"]:
            lists.setdefault(name, []).append(ids[c["case"]])
    key = {
        "format": 1,
        "as_of": "2026-10-24",
        "lookahead_months": 12,
        "lists": {name: sorted(lists.get(name, [])) for name in (
            "past_eol", "ends_soon", "dates_disagree", "unmatched",
            "accepted_risk", "ownerless", "review_urgently",
            "golden_overrides")},
        "cases": {ids[c["case"]]: {
            **{k: c[k] for k in ("case", "name", "version", "state",
                                 "reason", "lists", "dates_disagree",
                                 "decision_needed", "classification",
                                 "inherited_state")
               if k not in ("classification", "inherited_state")
               or c["classification"] is not None},
            # The sum of the item's Install Count cells, or None.
            "install_count": counts.get(c["case"])}
            for c in CASES},
        "counts": {"count_invalid_cells": sum(
            len(c["rows"]) for c in CASES if c["count_text"] is not None),
            "inherited_attention": sum(
            1 for c in CASES if c["inherited_state"] in INHERITED_STATES),
            "support_records": {
                "listed": sum(1 for r in SUPPORT_RECORDS if r[6]),
                "ending_soon": sum(1 for r in SUPPORT_RECORDS
                                   if WINDOW[0] < r[4] <= WINDOW[1]),
                "not_matched": sum(1 for r in SUPPORT_RECORDS
                                   if not r[6])}},
        # Planted item ID -> record refs shown on it. FILLER_LANTERN means
        # every Lantern Viewer filler item.
        "support_records": _support_key(ids),
    }
    support = [["schema_version", "record_ref", "product", "scope", "kind",
                "ends_on", "owner_role"]]
    support += [["1", ref, product, scope, kind, ends, role]
                for ref, product, scope, kind, ends, role, _fits
                in SUPPORT_RECORDS]
    tracking = [["schema_version", "item_id", "change_ref", "problem_ref"]]
    tracking += [["1", ids[label], chg, prb] for label, chg, prb in TRACKING]
    files = {
        "software-inventory.csv": _csv_bytes([HEADER] + rows),
        "answer-key.json": (json.dumps(key, sort_keys=True, indent=2)
                            + "\n").encode("ascii"),
        "tracking.csv": _csv_bytes(tracking),
        "support-records.csv": _csv_bytes(support),
    }
    files["sample-report.md"] = sample_report(files)
    return files


def main(argv: list) -> int:
    dest = Path(argv[1]) if len(argv) > 1 else HERE
    for name, data in build().items():
        (dest / name).write_bytes(data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
