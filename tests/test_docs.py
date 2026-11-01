"""Keep the docs, templates and crosswalk true to the code."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swlc import assess, cli, matching, overrides, support
from swlc.inputs import GENERIC_ALIASES, map_columns, read_rows
from swlc.report import CLAIMS_LINE, DECISION_TEXT, KEV_LINE

DOCS = ROOT / "docs"
TEMPLATES = ROOT / "templates"
README = ROOT / "README.md"
DEMO = ROOT / "examples" / "software-inventory.csv"
FIXTURE_DATA = ROOT / "tests" / "fixtures" / "data"

CROSSWALK_HEADER = [
    "id", "theme", "iso19770_1", "itil4", "iso20000_1", "cobit2019",
    "nist_800_53", "nist_csf2", "cis_v8", "iso27001", "summary", "verified",
    "unverified_columns"]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


ROOT_MD = ["README.md", "CONTRIBUTING.md", "SECURITY.md", "AGENTS.md",
           "CLAUDE.md"]
GITHUB = ROOT / ".github"
TEXT_SUFFIXES = (".csv", ".md", ".json", ".py", ".txt")


def github_files() -> list:
    return sorted(p for p in GITHUB.rglob("*") if p.is_file())


def doc_files() -> list:
    return [ROOT / n for n in ROOT_MD] + sorted(DOCS.glob("*.md"))


def public_files() -> list:
    """The scanned set: root markdown, docs, templates and everything
    under .github. Not data/."""
    out = doc_files() + sorted(DOCS.glob("*.csv"))
    out += [p for p in sorted(TEMPLATES.iterdir()) if p.is_file()]
    out += github_files()
    out += [p for p in sorted((ROOT / "tests" / "benchmark").iterdir())
            if p.is_file() and p.suffix in (".csv", ".md", ".json")]
    out += [ROOT / "CHANGELOG.md", ROOT / "THIRD-PARTY.md"]
    out += [p for p in sorted((ROOT / "examples").rglob("*"))
            if p.is_file() and p.suffix in TEXT_SUFFIXES]
    out += sorted((ROOT / "swlc").glob("*.py"))
    out += [ROOT / "swlc_mcp.py"]
    return out


def sentences(body: str) -> list:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n\s*\n", body) if s.strip()]


class TemplateTests(unittest.TestCase):
    def test_override_templates_load_as_empty(self):
        p = TEMPLATES
        self.assertEqual(overrides.load_golden(str(p / "golden-sources.csv")).rows, {})
        self.assertEqual(
            overrides.load_exceptions(str(p / "exceptions.csv")).rows, {})
        self.assertEqual(overrides.load_tracking(str(p / "tracking.csv")), {})
        self.assertEqual(support.load_support_records(
            str(p / "support-records.csv"), set()), [])

    def test_override_template_columns_match_the_loader(self):
        for name, cols in (("golden-sources.csv", overrides._GOLDEN_COLS),
                           ("exceptions.csv", overrides._EXC_COLS),
                           ("tracking.csv", overrides._TRACK_COLS),
                           ("support-records.csv", support.COLUMNS)):
            with open(TEMPLATES / name, newline="", encoding="utf-8") as fh:
                self.assertEqual(next(csv.reader(fh)), list(cols), name)
            self.assertEqual(cols[0], "schema_version")

    def test_inventory_template_maps(self):
        rows, headers = read_rows(str(TEMPLATES / "inventory-template.csv"),
                                  allow_empty=True)
        self.assertEqual(rows, [])
        found = map_columns(headers, None, None)
        self.assertEqual(sorted(found), sorted(GENERIC_ALIASES))

    def test_columns_example_is_accepted(self):
        obj = json.loads(text(TEMPLATES / "columns.example.json"))
        with tempfile.TemporaryDirectory() as tmp:
            cli._read_columns(str(TEMPLATES / "columns.example.json"))
        self.assertTrue(set(obj) <= set(GENERIC_ALIASES))


class CrosswalkTests(unittest.TestCase):
    def rows(self):
        with open(DOCS / "crosswalk.csv", newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            return header, [dict(zip(header, r)) for r in reader]

    def test_header_and_ids(self):
        header, rows = self.rows()
        self.assertEqual(header, CROSSWALK_HEADER)
        ids = [r["id"] for r in rows]
        self.assertEqual(ids, ["XW-029", "XW-030", "XW-031", "XW-032"])
        self.assertEqual(len(set(ids)), len(ids))

    def test_verified_rule(self):
        _, rows = self.rows()
        for r in rows:
            self.assertEqual(len(r), len(CROSSWALK_HEADER))
            if r["verified"].strip():
                self.assertEqual(r["unverified_columns"].strip(), "", r["id"])
            for col in r["unverified_columns"].split(";"):
                if col.strip():
                    self.assertIn(col.strip(), CROSSWALK_HEADER)

    def test_pm5_not_cited_for_end_of_life(self):
        _, rows = self.rows()
        xw029 = [r for r in rows if r["id"] == "XW-029"][0]
        self.assertNotIn("PM-5", xw029["nist_800_53"])
        self.assertIn("SA-22", xw029["nist_800_53"])
        self.assertIn("CM-8", xw029["nist_800_53"])

    def test_cobit_cells_use_practice_ids(self):
        _, rows = self.rows()
        by_id = {r["id"]: r["cobit2019"] for r in rows}
        self.assertTrue(by_id["XW-029"].startswith("BAI09.01"))
        self.assertNotIn("APO10", by_id["XW-029"])
        self.assertIn("DSS05.07", by_id["XW-030"])
        self.assertIn("BAI09.01", by_id["XW-032"])
        for r in rows:
            self.assertNotIn("cobit2019", r["unverified_columns"])

    def test_unverified_columns_match_themes(self):
        _, rows = self.rows()
        themes = text(DOCS / "themes.md")
        for r in rows:
            m = re.search(re.escape(r["id"]) + r": ((?:`[a-z0-9_]+`(?: \([^)]*\))?,?\s*)+)", themes[themes.index("`unverified_columns`"):])
            self.assertIsNotNone(m, r["id"])
            listed = sorted(re.findall(r"`([a-z0-9_]+)`", m.group(1)))
            self.assertEqual(listed, sorted(r["unverified_columns"].split(";")), r["id"])

    def test_iso19770_clause_8_3_agrees(self):
        _, rows = self.rows()
        self.assertIn("8.3", rows[0]["iso19770_1"].split("; "))
        usage = " ".join(text(DOCS / "usage.md").split())
        self.assertIn("clause 8.3 (core data management, p.22", usage)
        self.assertNotIn("Not found / Unverified, because no public source", usage)

    def test_cycle_warning_and_cis_cadence_note(self):
        themes = " ".join(text(DOCS / "themes.md").split())
        self.assertIn("CSAM p.165", themes)
        self.assertIn("Do not use it for cycle logic", themes)
        _, rows = self.rows()
        summary = rows[0]["summary"]
        self.assertIn("monthly", summary)
        self.assertIn("quarterly", summary)

    def test_cis_title_hedge_removed(self):
        themes = " ".join(text(DOCS / "themes.md").split())
        self.assertNotIn("same in v8 and v8.1", themes)
        self.assertNotIn("matching titles", themes)

    def test_iso19770_1_is_checked_but_itil_and_20000_are_not(self):
        _, rows = self.rows()
        for r in rows:
            cols = r["unverified_columns"].split(";")
            for checked in ("iso27001", "iso19770_1", "nist_csf2", "nist_800_53"):
                self.assertNotIn(checked, cols, r["id"])
            for unchecked in ("itil4", "iso20000_1"):
                self.assertIn(unchecked, cols, r["id"])
            self.assertEqual(r["verified"].strip(), "", r["id"])
        self.assertNotIn("DSS05.01", text(DOCS / "themes.md"))
        self.assertEqual(rows[3]["cis_v8"], "")

    def test_dropped_citations_are_gone_from_the_csv(self):
        raw = text(DOCS / "crosswalk.csv")
        for dropped in ("A.5.33", "GV.RM-02", "PM-16"):
            self.assertNotIn(dropped, raw)

    def test_added_citations_are_in_the_csv(self):
        raw = text(DOCS / "crosswalk.csv")
        for added in ("A.5.2", "CA-6", "RA-3", "6.2.4"):
            self.assertIn(added, raw)

    def test_themes_gives_the_itil_secondary_source_reason(self):
        themes = " ".join(text(DOCS / "themes.md").split())
        self.assertIn("secondary book, not the official practice guides", themes)
        self.assertIn("NIST.CSWP.40", themes)
        self.assertIn("Amendment 1 (2024)", themes)

    def test_retirement_cell_text(self):
        _, rows = self.rows()
        self.assertIn("Annex A Retirement (Table A.1)", rows[0]["iso19770_1"])

    def test_amendment_1_caveat_sentence(self):
        themes = " ".join(text(DOCS / "themes.md").split())
        self.assertIn("Amendment 1 (2024) was not opened: Unverified.", themes)

    def test_no_verdict_cell_says_added(self):
        themes = text(DOCS / "themes.md")
        table = [ln for ln in themes.splitlines() if ln.startswith("| ")]
        self.assertGreater(len(table), 30)
        for ln in table:
            self.assertNotIn("Added", ln.split("|")[-2], ln)


class LinkTests(unittest.TestCase):
    def test_relative_links_resolve(self):
        link = re.compile(r"\]\(([^)\s]+)\)")
        for path in doc_files():
            for target in link.findall(text(path)):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue
                rel = target.split("#")[0]
                self.assertTrue((path.parent / rel).exists(),
                                "%s -> %s" % (path.name, target))


class FixedWordingTests(unittest.TestCase):
    def test_readme_lines(self):
        body = " ".join(text(README).split())
        self.assertEqual(body.count(CLAIMS_LINE), 1)
        self.assertEqual(body.count(KEV_LINE), 1)
        security = " ".join(text(ROOT / "SECURITY.md").split())
        self.assertEqual(security.count(CLAIMS_LINE), 1)


def workflow_check_names() -> list:
    body = text(GITHUB / "workflows" / "ci.yml")
    jobs = body.split("\njobs:\n", 1)[1]
    test_job = re.search(r"^  test:\n(.*?)(?=^  [a-z]+:\n)", jobs,
                         re.S | re.M).group(1)
    assert "name:" not in test_job.split("steps:")[0]
    versions = re.search(r"python: \[(.*?)\]", test_job).group(1)
    return ["test (%s)" % v.strip('" ') for v in versions.split(",")]


def parse_form(path: Path) -> dict:
    """A small structural reader for an issue form."""
    lines = text(path).split("\n")
    top = {}
    for line in lines:
        m = re.match(r"^([a-z_]+):(.*)$", line)
        if m:
            top[m.group(1)] = m.group(2).strip()
    body = text(path)
    ids = re.findall(r"^    id: (\S+)$", body, re.M)
    types = re.findall(r"^  - type: (\S+)$", body, re.M)
    labels = re.findall(r'"([^"]+)"', top.get("labels", ""))
    return {"top": top, "ids": ids, "types": types, "labels": labels,
            "text": body}


class NewFilesTests(unittest.TestCase):
    FORMS = ("bug-report.yml", "feature-request.yml", "unmatched-product.yml")

    def test_files_exist(self):
        for rel in ("SECURITY.md", "CONTRIBUTING.md", "AGENTS.md",
                    "CLAUDE.md", ".github/CODEOWNERS",
                    ".github/PULL_REQUEST_TEMPLATE.md",
                    ".github/ISSUE_TEMPLATE/config.yml"):
            self.assertTrue((ROOT / rel).is_file(), rel)
        for name in self.FORMS:
            self.assertTrue((GITHUB / "ISSUE_TEMPLATE" / name).is_file())
        self.assertEqual(text(GITHUB / "CODEOWNERS").strip(),
                         "* @evemcgivern")

    def test_issue_forms_are_well_formed(self):
        labels = set()
        for name in self.FORMS:
            form = parse_form(GITHUB / "ISSUE_TEMPLATE" / name)
            for key in ("name", "description", "labels", "body"):
                self.assertIn(key, form["top"], name)
            self.assertTrue(form["labels"], name)
            labels |= set(form["labels"])
            self.assertEqual(len(form["ids"]), len(set(form["ids"])), name)
            self.assertIn("markdown", form["types"], name)
            self.assertIn("checkboxes", form["types"], name)
            flat = " ".join(form["text"].split())
            self.assertIn("Do not paste inventory rows", flat, name)
            self.assertIn("required: true", flat, name)
        self.assertEqual(labels, {"bug", "enhancement", "alias-request"})
        contributing = text(ROOT / "CONTRIBUTING.md")
        for label in labels:
            self.assertIn("`%s`" % label, contributing)

    def test_warning_is_the_first_body_element(self):
        for name in self.FORMS:
            body = text(GITHUB / "ISSUE_TEMPLATE" / name)
            first = body.split("\nbody:\n", 1)[1].split("\n  - type:")[0]
            self.assertIn("type: markdown", first, name)
            self.assertIn("Do not paste inventory rows",
                          " ".join(first.split()), name)

    def test_public_status_and_reporting_pointer(self):
        for name in ("SECURITY.md", "CONTRIBUTING.md"):
            flat = " ".join(text(ROOT / name).replace("> ", " ").split())
            self.assertNotIn("currently private", flat.lower(), name)
            self.assertIn("**Security** tab", flat, name)
            self.assertIn("**Report a vulnerability**", flat, name)
            self.assertIn("private vulnerability reporting", flat.lower(),
                          name)

    def test_private_era_claims_are_gone(self):
        for name in ("README.md", "SECURITY.md", "docs/quick-start.md"):
            low = " ".join(text(ROOT / name).split()).lower()
            for phrase in ("disabled while the repository is private",
                           "enterprise cloud", "until the first release",
                           "paused"):
                self.assertNotIn(phrase, low, "%s: %s" % (name, phrase))

    def test_agents_blocked_rule(self):
        flat = " ".join(text(ROOT / "AGENTS.md").split())
        self.assertIn("If a hook, a test, a guard or branch protection "
                      "blocks you, stop and ask in the issue. Do not work "
                      "around it.", flat)

    def test_agents_and_contributing_agree_on_data_files(self):
        for name in ("AGENTS.md", "CONTRIBUTING.md"):
            flat = " ".join(text(ROOT / name).split())
            self.assertIn("data/profiles.json", flat, name)
            self.assertIn("data/aliases.json", flat, name)
            self.assertIn("data/curation.json", flat, name)
            self.assertIn("source URL", flat, name)
            self.assertIn("negative corpus row", flat, name)

    def test_config_keeps_blank_issues_off_and_links_security(self):
        config = text(GITHUB / "ISSUE_TEMPLATE" / "config.yml")
        self.assertIn("blank_issues_enabled: false", config)
        self.assertIn("/blob/main/SECURITY.md", config)

    def test_claude_md_is_a_pointer(self):
        path = ROOT / "CLAUDE.md"
        self.assertFalse(path.is_symlink())
        body = text(path)
        self.assertIn("AGENTS.md", body)
        self.assertLess(len(body.strip().split("\n")), 10)

    def test_contributing_names_the_real_checks_and_command(self):
        body = text(ROOT / "CONTRIBUTING.md")
        names = workflow_check_names()
        self.assertEqual(len(names), 5)
        for name in names:
            self.assertIn("`%s`" % name, body)
        self.assertIn("python3 -B -m unittest discover -s tests", body)
        self.assertIn("discover -s tests -p 'test_x.py'", body)

    def test_agents_md_has_each_hard_rule(self):
        body = text(ROOT / "AGENTS.md")
        for keyword in ("--counts-only", "tests/make_fixtures.py",
                        "dependencies", "pull_request_target",
                        "schema_version", "Never push to main",
                        "Never force-push", "commit SHA", "claims line",
                        "KEV line", "synthetic", "test_weekly_gate"):
            self.assertIn(keyword, body, keyword)

    def test_security_md_command_matches_the_release_notes(self):
        workflow = text(GITHUB / "workflows" / "kev-daily.yml")
        command = re.search(r"^\s+(gh attestation verify data\.zip --repo "
                            r"\S+ --signer-workflow \S+ --source-ref \S+)$",
                            workflow, re.M).group(1)
        self.assertIn(command, text(ROOT / "SECURITY.md"))
        self.assertIn(command, text(README))


def parser_flags() -> set:
    parser = cli._parser()
    flags = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                flags.add(name)
                for a in sub._actions:
                    flags.update(o for o in a.option_strings
                                 if o.startswith("--"))
    return flags


def table_cells(body: str, heading: str) -> list:
    """First cell of each row of the first table under the heading."""
    match = re.search(r"^#+ %s\n" % re.escape(heading), body, re.M)
    assert match, "heading not found: " + heading
    lines = body[match.end():].split("\n")
    out, started = [], False
    for line in lines:
        if line.startswith("|"):
            started = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set(cells[0]) <= set("-: ") or cells[0] in ("Key", "Field",
                                                          "Flag", "State",
                                                          "List", "Code"):
                continue
            out.append(cells[0])
        elif started:
            break
    return out


def ticks(cells: list) -> set:
    return {t for c in cells for t in re.findall(r"`([^`]+)`", c)}


class UsageTests(unittest.TestCase):
    def test_flag_table_matches_parser(self):
        body = text(DOCS / "usage.md")
        documented = set()
        for heading in ("check", "preflight"):
            for cell in table_cells(body, heading):
                documented |= set(re.findall(r"`(--[a-z-]+)", cell))
        real = {f for f in parser_flags() if f.startswith("--")}
        self.assertIn("--counts-only", real)
        self.assertEqual(documented, real)

    def test_commands_documented(self):
        body = text(DOCS / "usage.md")
        for name in ("check", "preflight", "verify-data"):
            self.assertIn("## " + name, body)


def usage_section(heading: str) -> str:
    body = text(DOCS / "usage.md")
    start = body.find("## " + heading + "\n")
    if start < 0:
        return ""
    end = body.find("\n## ", start + 1)
    return body[start:] if end < 0 else body[start:end]


class ClassDefinitionsDocTests(unittest.TestCase):
    def test_usage_defines_each_class(self):
        section = usage_section("What kind of item this is")
        self.assertTrue(section, "usage.md has no classification section")
        flat = " ".join(section.split())
        for name in ("governable", "component", "bundle_member", "unknown"):
            self.assertIn("`%s`" % name, flat)
        self.assertIn("Never default to governable.", flat)
        for sent in re.split(r"(?<=[.!?])\s+", flat):
            if "ISO/IEC 19770-2 clause" in sent:
                self.assertIn("Unverified", sent)


def code_constants() -> set:
    out = set()
    for mod in (assess, matching):
        out |= {v for k, v in vars(mod).items()
                if isinstance(v, str) and k == v and k.isupper()}
    out |= set(DECISION_TEXT)
    return out


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from datetime import date
        when = date(2026, 10, 24)
        cls.report = cli.run(str(DEMO), data=str(FIXTURE_DATA), as_of=when)
        prev = json.loads(json.dumps(cls.report))
        prev["items"][0]["state"] = "unmatched" \
            if prev["items"][0]["state"] != "unmatched" else "supported"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "previous.json"
            path.write_text(json.dumps(prev), encoding="utf-8")
            cls.second = cli.run(str(DEMO), data=str(FIXTURE_DATA),
                                 as_of=when, previous=str(path))
        cls.body = text(DOCS / "report-schema.md")

    def documented(self, heading):
        return ticks(table_cells(self.body, heading))

    def test_key_tables_match_real_keys(self):
        r, second = self.report, self.second
        item_keys = set(r["items"][0])
        for item in r["items"]:
            self.assertEqual(set(item), item_keys)
        entry = second["diff"]["changed_state"][0]
        expected = {
            "Top-level keys": set(r),
            "data_release": set(r["data_release"]),
            "counts": set(r["counts"]),
            "counts.classification": set(r["counts"]["classification"]),
            "counts.unmatched_breakdown": set(
                r["counts"]["unmatched_breakdown"]),
            "counts.support_records": set(r["counts"]["support_records"]),
            "meta": set(r["meta"]),
            "meta.data_release": set(r["meta"]["data_release"]),
            # support_records is there only with --support-records.
            "meta.override_hashes": set(r["meta"]["override_hashes"])
            | {"support_records"},
            "meta.profile": set(r["meta"]["profile"]),
            "Items": item_keys,
            "diff": set(r["diff"]),
            "diff.changed_state": set(entry),
        }
        for heading, real in expected.items():
            self.assertEqual(self.documented(heading), real, heading)

    def test_states_lists_reasons(self):
        self.assertEqual(self.documented("States"), set(assess.STATES))
        self.assertEqual(self.documented("Lists"), set(assess.LISTS))
        reasons = {matching.NO_ALIAS, matching.NO_CYCLE, matching.NO_VERSION,
                   matching.AMBIGUOUS}
        self.assertEqual(
            self.documented("Reason codes (unmatched items)"), reasons)

    def test_codes_documented(self):
        codes = code_constants()
        self.assertIn("DIFFERENT_DATE", codes)
        self.assertIn("NO_ALIAS", codes)
        for code in codes:
            self.assertIn(code, self.body, code)
        for heading in ("dates_disagree codes", "decision_needed codes"):
            self.assertTrue(self.documented(heading) <= codes, heading)

    def test_override_columns_match_loader(self):
        for heading, cols in (("golden-sources.csv", overrides._GOLDEN_COLS),
                              ("exceptions.csv", overrides._EXC_COLS),
                              ("tracking.csv", overrides._TRACK_COLS),
                              ("support-records.csv", support.COLUMNS)):
            self.assertEqual(self.documented(heading), set(cols), heading)

    def test_support_record_entry_keys_documented(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sr.csv"
            path.write_text(",".join(support.COLUMNS) + "\n1,SR-1,"
                            "tidewatersuite,,extended support,2027-01-31,"
                            "\n", encoding="utf-8")
            from datetime import date
            r = cli.run(str(DEMO), data=str(FIXTURE_DATA),
                        as_of=date(2026, 10, 24), support_records=str(path))
        entries = [e for it in r["items"] for e in it["support_records"]]
        self.assertTrue(entries)
        self.assertEqual(self.documented("support_records"), set(entries[0]))


# Plain words that are not identifying.
BANNED = ["job search", "portfolio", "resume", "/users/", "/applications/",
          "gmail"]
# SHA-256 digests of lowercased words and lowercased adjacent word pairs.
# Only digests are kept here; a failure prints the file and the digest.
BANNED_DIGESTS = {
    "405e6e0273215dab5aa088d765d9883727f078fbc89dd6fef0723476eb26d3d9",
    "8517b64a7dfada982abdf62810e1c248d645151dc3d2352075c5cad87b3a2221",
    "260048fecac2c70eec2c08b2ad96a098476bc27718691747028f4d9abf42e690",
    "51e2a46721d104d9148d85b617833e7745fdbd6795cb0b502a5b6ea31d33378e",
    "f3497d75b9f10b708886174a926d7986b1d550be7c8054bc42949a39fac2a83d",
    "219035c2a453fa863fc625ca5ef56b07138b9e1e604142ceaf970f1eb995286f",
    "e6a8c3c3eb2f7d82046ac47721aba4d02095bfbf3bcf9c0a1e7d163aa23887dd",
    "702e1c9fc717e96e333f1f7767755f07c0e610056d5587dd96abeace75aede17",
}


def signed_problems(body: str) -> list:
    """Sentences that use the word "signed" outside a rule sentence.

    Text is cut into units at blank lines and list items (wrapped lines are
    joined), then into sentences at . ! ?. The stricter option is used: the
    word is allowed only in a sentence of the form "never call/say/claim/
    write ... signed" or "does not claim/say ... signed". A bare "never"
    elsewhere in the sentence is not enough.
    """
    units, current = [], []
    for line in body.split("\n"):
        if not line.strip() or re.match(r"\s*(?:[-*]|[0-9]+\.)\s", line):
            if current:
                units.append(" ".join(current))
            current = [] if not line.strip() else [line.strip()]
        else:
            current.append(line.strip())
    if current:
        units.append(" ".join(current))
    allowed = re.compile(r"never (?:call|say|claim|write)[^.]*signed|"
                         r"does not (?:claim|say)[^.]*signed")
    out = []
    for unit in units:
        for sent in re.split(r"(?<=[.!?])\s+", unit):
            low = sent.lower()
            if re.search(r"\bsigned\b", low) and not allowed.search(low):
                out.append(sent)
    return out


def hashed_terms(body: str) -> set:
    words = re.findall(r"[a-z0-9]+", body.lower())
    terms = set(words) | {a + " " + b for a, b in zip(words, words[1:])}
    return {hashlib.sha256(t.encode("utf-8")).hexdigest() for t in terms}


class BannedWordTests(unittest.TestCase):
    def test_banned_words(self):
        for path in public_files():
            low = text(path).lower()
            for word in BANNED:
                self.assertNotIn(word, low, "%s: %s" % (path.name, word))
            hit = hashed_terms(low) & BANNED_DIGESTS
            self.assertFalse(hit, "%s: banned term, digest %s"
                             % (path.name, sorted(hit)))

    def test_signed_only_in_rule_sentences(self):
        for path in public_files():
            self.assertEqual(signed_problems(text(path)), [], path.name)

    def test_signed_check_catches_bad_sentences(self):
        bad = [
            "- Releases are never changed\n- Releases are signed\n",
            "Data releases are never re-tagged and are signed by the "
            "workflow.",
            "Never trust a release that is not signed.",
            "Our releases are signed.",
            "Each release has a GPG-signed tag.",
        ]
        for body in bad:
            self.assertTrue(signed_problems(body), body)
        good = ['Never call a release "signed".',
                "The project does not claim that a release is signed."]
        for body in good:
            self.assertEqual(signed_problems(body), [], body)
        for name in ("AGENTS.md", "CONTRIBUTING.md"):
            body = text(ROOT / name)
            self.assertRegex(" ".join(body.split()),
                             r'Never call a release "signed"')

    def test_no_overclaims_or_email_addresses(self):
        files = [ROOT / n for n in ("SECURITY.md", "CONTRIBUTING.md",
                                    "AGENTS.md", "README.md")]
        files += [p for p in github_files() if "workflows" not in p.parts]
        phrases = ("enterprise-grade", "enterprise-secure", "audited and",
                   "certified", "fully compliant")
        for path in files:
            low = text(path).replace(CLAIMS_LINE, "").lower()
            for phrase in phrases:
                self.assertNotIn(phrase, low, path.name)
            self.assertIsNone(
                re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text(path)),
                path.name)

    def test_bod_22_01_only_as_superseded(self):
        for path in public_files():
            for s in sentences(text(path)):
                if "BOD 22-01" in s:
                    self.assertIn("superseded", s, path.name)

    def test_vulnerable_only_in_never_sentence(self):
        for path in public_files():
            for s in sentences(text(path)):
                if "vulnerable" in s.lower():
                    self.assertIn("never", s.lower(), path.name)


ASSISTANT_SETUP = DOCS / "assistant-setup.md"


def prompt_blocks(body: str) -> list:
    """The copy-paste prompts: fenced blocks tagged `text`."""
    return re.findall(r"^```text\n(.*?)^```", body, re.M | re.S)


class AssistantSetupTests(unittest.TestCase):
    def test_start_here_links_resolve(self):
        link = re.compile(r"\]\(([^)\s]+)\)")
        for path in (README, ASSISTANT_SETUP):
            targets = link.findall(text(path))
            self.assertTrue(targets, path.name)
            for target in targets:
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue
                self.assertTrue(
                    (path.parent / target.split("#")[0]).exists(),
                    "%s -> %s" % (path.name, target))

    def test_readme_routes_each_reader(self):
        body = text(README)
        start = body.split("## Start here", 1)[1].split("\n## ", 1)[0]
        for target in ("docs/assistant-setup.md", "docs/quick-start.md",
                       "docs/glossary.md", "docs/usage.md", "docs/sop.md",
                       "CONTRIBUTING.md"):
            self.assertIn("(%s)" % target, start, target)

    def test_each_prompt_keeps_the_inventory_closed(self):
        blocks = prompt_blocks(text(ASSISTANT_SETUP))
        self.assertEqual(len(blocks), 3)
        runners, guide = blocks[:2], blocks[2]
        for block in runners:
            flat = " ".join(block.split())
            self.assertIn("Do not open, read, print, summarise or quote "
                          "my inventory.", flat)
            self.assertIn("report.md, report.csv or report.json", flat)
            self.assertIn("Do not repeat the item IDs back to me", flat)
            self.assertIn("Do not run anything that uses the network", flat)
            self.assertNotIn("clone https", flat)
        flat = " ".join(guide.split())
        self.assertIn("Never ask me to paste, attach or upload my "
                      "inventory or the files report.md, report.csv or "
                      "report.json.", flat)
        self.assertIn("Never ask me to paste item IDs", flat)
        self.assertIn("leave out every line that lists item IDs", flat)
        for block in blocks:
            flat = " ".join(block.split())
            self.assertIn("--counts-only", flat)
            self.assertIn("confidential", flat)
            self.assertIn("refresh_data.py", flat)
            self.assertIn("Not found", flat)
            self.assertIn("python3 --version", flat)
            # Every command in a prompt parses with the real parser.
            for command in re.findall(
                    r"`python3 software_lifecycle\.py ([^`]+)`", flat):
                args = cli._parser().parse_args(command.split())
                self.assertIn(args.command, ("check", "preflight"))

    def test_fallback_section_withholds_item_ids(self):
        body = text(ASSISTANT_SETUP)
        section = body.split("## If your assistant cannot run commands",
                             1)[1].split("\n## ", 1)[0]
        flat = " ".join(section.split())
        self.assertIn("Leave out every line that lists item IDs", flat)
        for name in ("checked_on", "kev_current", "count_total"):
            self.assertIn("`%s`" % name, flat)

    def test_summary_line_names_are_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = subprocess.run(
                [sys.executable, "-B", str(ROOT / "software_lifecycle.py"),
                 "check", str(DEMO), "--data", str(FIXTURE_DATA),
                 "--as-of", "2026-10-24", "--counts-only", "--out", tmp],
                capture_output=True, text=True, check=True).stdout
        firsts = {line.split()[0] for line in out.splitlines()}
        flat = " ".join(text(ASSISTANT_SETUP).split())
        for name in ("checked_on", "kev_current", "items", "states",
                     "classification", "ambiguous_review",
                     "support_records", "count_total"):
            self.assertIn(name, firsts)
            self.assertIn("`%s`" % name, flat)

    def test_runner_prompts_name_both_commands(self):
        blocks = prompt_blocks(text(ASSISTANT_SETUP))
        for block in blocks[:2]:
            self.assertIn("preflight ../inventory.csv", block)
            self.assertIn("check ../inventory.csv --counts-only "
                          "--out ../swlc-out", block)

    def test_privacy_rule_is_stated(self):
        flat = " ".join(text(ASSISTANT_SETUP).split())
        self.assertIn("Anything an assistant opens goes to the company that "
                      "runs it.", flat)
        self.assertIn("That is a request. Nothing technical stops an "
                      "assistant from ignoring it.", flat)
        self.assertIn("Never attach or paste the inventory", flat)
        self.assertIn("checked on 2026-11-01", flat)

    def test_chat_only_products_never_get_yes(self):
        rows = [line for line in text(ASSISTANT_SETUP).split("\n")
                if line.startswith("| ")]
        by_name = {r.split("|")[1].strip(): r.split("|")[2].strip()
                   for r in rows}
        for name in ("Claude Desktop chat", "Perplexity",
                     "Any other chat assistant"):
            self.assertIn(name, by_name)
            self.assertTrue(by_name[name].startswith("No."), name)
            self.assertNotIn("yes", by_name[name].lower(), name)
        for name in ("Claude Code", "Codex (CLI or IDE extension)",
                     "ChatGPT desktop app",
                     "GitHub Copilot (CLI and VS Code agent mode)"):
            self.assertTrue(by_name[name].startswith("Yes"), name)
        cloud = by_name["Copilot coding agent, Codex cloud, hosted sandboxes"]
        self.assertIn("Do not use with a real inventory", cloud)

    def test_agents_md_tells_agents_to_use_counts_only(self):
        body = text(ROOT / "AGENTS.md")
        self.assertIn("--counts-only", body)
        self.assertIn("docs/assistant-setup.md", body)
        self.assertIn("Do not open, read, print, summarise or quote",
                      " ".join(body.split()))
        self.assertIn("Do not list the item IDs back", " ".join(body.split()))

    def test_claude_md_imports_agents_md(self):
        lines = text(ROOT / "CLAUDE.md").split("\n")
        self.assertIn("@AGENTS.md", lines)


MCP_SETUP = DOCS / "mcp-setup.md"


class McpSetupDocTests(unittest.TestCase):
    def test_links_resolve_and_entry_points_link_once(self):
        link = re.compile(r"\]\(([^)\s]+)\)")
        for target in link.findall(text(MCP_SETUP)):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            self.assertTrue((DOCS / target.split("#")[0]).exists(), target)
        start = text(README).split("## Start here", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(start.count("(docs/mcp-setup.md)"), 1)
        row = [r for r in start.split("\n") if "mcp-setup" in r][0]
        self.assertIn("optional, advanced", row)
        self.assertIn("Unverified", row)
        rows = {r.split("|")[1].strip(): r for r in
                text(ASSISTANT_SETUP).split("\n") if r.startswith("| ")}
        for name in ("Claude Desktop chat", "ChatGPT desktop app"):
            self.assertEqual(rows[name].count("(mcp-setup.md)"), 1, name)
            self.assertIn("Optional, advanced", rows[name])
            self.assertIn("Unverified", rows[name])

    def test_says_counts_only_and_what_is_not_protected(self):
        flat = " ".join(text(MCP_SETUP).split())
        for phrase in (
                "It never returns item IDs, names, versions, publishers or "
                "owners.",
                "The counts, and the path you type, still go to the company "
                "that runs the chat app",
                "Other tools in the same app can still read files.",
                "Do not attach, upload or paste your inventory or a report "
                "into the chat.",
                "is **not built yet** and is untested",
                "**Unverified**",
                "never runs `refresh_data.py`"):
            self.assertIn(phrase, flat)
        self.assertIn("--counts-only", flat)
        for phrase in (
                "It refuses a path whose file itself is a symlink; a "
                "symlinked parent folder is followed",
                "`swlc-out-inventory`",
                "the folder name also ends in a short code made from the "
                "name",
                "Running it again on the same file replaces that file's "
                "report.",
                "iCloud, OneDrive, Dropbox",
                "The assistant chooses the path, so it chooses where the "
                "report folder lands",
                "out of scope",
                "A check can take up to 280 seconds"):
            self.assertIn(phrase, flat)
        self.assertNotIn("refuses symlinks", flat)

    def test_other_docs_point_to_the_server(self):
        for path in (README, DOCS / "quick-start.md", DOCS / "usage.md",
                     DOCS / "sop.md", DOCS / "glossary.md",
                     ROOT / "SECURITY.md"):
            self.assertIn("mcp-setup.md)", text(path), path.name)
        flat = " ".join(text(ROOT / "SECURITY.md").split())
        scope = flat.split("## Scope", 1)[1].split("## ", 1)[0]
        self.assertIn("`swlc_mcp.py`", scope)
        self.assertIn("## What the MCP server protects", text(
            ROOT / "SECURITY.md"))
        glossary = text(DOCS / "glossary.md")
        for term in ("**MCP server.**", "**Tool.**", "**stdio.**",
                     "**Allow-list.**"):
            self.assertIn(term, glossary)
        usage = " ".join(text(DOCS / "usage.md").split())
        self.assertIn("`swlc_mcp.py` is a separate, optional entry point, "
                      "not a command of `software_lifecycle.py`", usage)
        self.assertIn("discover -s tests -p 'test_mcp.py'",
                      text(ROOT / "CONTRIBUTING.md"))

    def test_config_keys_and_tool_names_match_the_server(self):
        import swlc_mcp
        body = text(MCP_SETUP)
        names = [t["name"] for t in swlc_mcp.TOOLS]
        self.assertIn('enabled_tools = ["%s"]' % '", "'.join(
            sorted(names, reverse=True)), body)
        self.assertIn('default_tools_approval_mode = "prompt"', body)
        for code in preflight_codes():
            self.assertIn("`%s`" % code, body)
        self.assertIn(str(swlc_mcp.MAX_CSV_BYTES), body)
        self.assertIn(str(swlc_mcp.MAX_PATH_CHARS), body)
        self.assertIn("after %d seconds" % swlc_mcp.TIMEOUT_SECONDS, body)


def preflight_codes() -> list:
    from swlc import preflight
    return list(preflight.FIX_TEXT)


class ReaderDocsTests(unittest.TestCase):
    def test_quick_start_commands_parse(self):
        body = text(DOCS / "quick-start.md")
        # Join indented lines continued with " \\" (shell) or " `"
        # (PowerShell), then keep the commands.
        joined = re.sub(r" [\\`]\n +", " ", body)
        commands = re.findall(
            r"^    (?:python3|py) software_lifecycle\.py (.+)$", joined, re.M)
        self.assertGreaterEqual(len(commands), 4)
        demos = []
        for command in commands:
            args = cli._parser().parse_args(command.split())
            self.assertIn(args.command, ("check", "preflight"), command)
            self.assertNotIn("/tmp", command)
            if command.startswith("check examples/"):
                demos.append(args)
        # Both demo blocks pass every sample file, so the run gives the
        # committed examples/sample-report.md.
        self.assertEqual(len(demos), 2)
        for args in demos:
            self.assertEqual(str(args.as_of), "2026-10-24")
            self.assertEqual(
                (args.data, args.golden, args.exceptions, args.tracking,
                 args.support_records),
                ("tests/fixtures/data", "examples/golden-sources.csv",
                 "examples/exceptions.csv", "examples/tracking.csv",
                 "examples/support-records.csv"))

    def test_glossary_quotes_the_kev_line(self):
        flat = " ".join(text(DOCS / "glossary.md").split())
        self.assertIn(KEV_LINE, flat)


class PlatformGuideTests(unittest.TestCase):
    def test_sources_section(self):
        body = text(DOCS / "platform-guide.md")
        self.assertIn("## Sources", body)
        sources = body.split("## Sources", 1)[1]
        for vendor in ("flexera", "servicenow", "rapid7"):
            self.assertRegex(sources.lower(), r"https://[^\s)]*%s" % vendor)

    def test_mbs_not_expanded(self):
        body = text(DOCS / "platform-guide.md").replace("servicenow-mbs", "")
        self.assertIsNone(re.search(r"\bmbs\b", body, re.I))


class CoverageAndDataTextTests(unittest.TestCase):
    def test_alias_counts_match_the_files(self):
        aliases = json.loads(text(ROOT / "data" / "aliases.json"))["aliases"]
        products = {a["product"] for a in aliases}
        body = " ".join(text(README).split())
        self.assertIn("%d aliases for %d products (%s)" % (
            len(aliases), len(products), ", ".join(sorted(
                products, key=lambda p: [a["product"] for a in aliases
                                         ].index(p)))), body)
        self.assertGreater(len(list((ROOT / "data" / "eol").glob("*.json"))),
                           400)

    def test_no_stale_release_or_commit_text(self):
        manifest = json.loads(text(ROOT / "data" / "manifest.json"))
        for path in (README, ROOT / "THIRD-PARTY.md"):
            body = text(path)
            for sha in re.findall(r"\b[0-9a-f]{40}\b", body):
                self.assertEqual(sha, manifest["upstream_commit"], path.name)
            self.assertIsNone(re.search(r"bundled-[0-9]{4}", body), path.name)


class DataFolderDocsTests(unittest.TestCase):
    def section(self):
        body = text(DOCS / "usage.md")
        start = body.index("## The data folder")
        return body[start:body.index("\n## ", start + 5)]

    def test_every_bundled_data_file_is_described(self):
        sec = self.section()
        manifest = json.loads(text(ROOT / "data" / "manifest.json"))
        names = {n for n in manifest["files"] if not n.startswith("eol/")}
        for name in names | {"eol/*.json"}:
            self.assertIn("`%s`" % name, sec, name)
        self.assertEqual(manifest["data_format"], 2)
        self.assertIn("`data_format` in the manifest is 2", sec)

    def test_report_schema_quotes_the_match_caveat(self):
        from swlc.report import MATCH_CAVEAT
        flat = " ".join(text(DOCS / "report-schema.md").split())
        self.assertEqual(flat.count(MATCH_CAVEAT), 1)

    def test_fixed_warning_text_is_quoted_from_the_code(self):
        from swlc.data import NO_CATALOG_WARNING
        flat = " ".join(self.section().split())
        self.assertIn(NO_CATALOG_WARNING, flat)

    def test_fixed_classification_text_is_quoted(self):
        from swlc.assess import PARENTS_ABSENT
        from swlc.report import HIDDEN_LINE, INHERITED_HEADING
        flat = " ".join((text(DOCS / "report-schema.md") + " " +
                         text(DOCS / "usage.md")).split())
        self.assertIn(PARENTS_ABSENT.replace("%d ", ""), flat)
        self.assertIn(HIDDEN_LINE.replace("%d ", "").split(":")[0], flat)
        self.assertIn(INHERITED_HEADING, flat)

    def test_agents_and_contributing_agree_on_floor_keys(self):
        floor = json.loads(text(ROOT / "tests" / "benchmark" / "floor.json"))
        for name in ("AGENTS.md", "CONTRIBUTING.md"):
            flat = " ".join(text(ROOT / name).split())
            for key in floor:
                if key != "note":
                    self.assertIn("`%s`" % key, flat, (name, key))

    def test_changelog_mentions_classification(self):
        body = text(ROOT / "CHANGELOG.md")
        start = body.index("## 0.2.0")
        end = body.find("\n## ", start + 5)
        sec = " ".join(body[start:end if end > 0 else None].split())
        self.assertIn("classification", sec)
        self.assertIn("`--governable-only`", sec)
        self.assertIn("parent column", sec)
        self.assertIn("`--fail-on` is unchanged", sec)

    def test_agents_layout_lists_every_swlc_module(self):
        body = text(ROOT / "AGENTS.md")
        start = body.index("## Layout")
        layout = body[start:body.index("\n## ", start + 5)]
        for path in sorted((ROOT / "swlc").glob("*.py")):
            if path.name != "__init__.py":
                self.assertIn("`swlc/%s`" % path.name, layout, path.name)

    def test_hand_kept_and_generated_files_match_the_agents_rule(self):
        sec = self.section()
        rows = {m.group(1): m.group(2) for m in re.finditer(
            r"^\| `([a-z./*]+)` \| ([^|]+?) \|", sec, re.M)}
        hand = {n for n, who in rows.items() if "by hand" in who}
        self.assertEqual(hand, {"aliases.json", "profiles.json",
                                "curation.json"})
        agents = " ".join(text(ROOT / "AGENTS.md").split())
        for name in hand:
            self.assertIn("`%s`" % name, agents)

    def test_documented_curation_keys_match_the_real_file(self):
        sec = self.section()
        for key in json.loads(text(ROOT / "data" / "curation.json")):
            self.assertIn("`%s`" % key, sec, key)


class ExtendingAliasesTests(unittest.TestCase):
    def section(self):
        body = text(DOCS / "usage.md")
        start = body.index("## Extending the alias table")
        return body[start:body.index("\n## ", start + 5)]

    def test_every_alias_field_is_listed(self):
        sec = self.section()
        aliases = json.loads(text(ROOT / "data" / "aliases.json"))["aliases"]
        fields = {f for a in aliases for f in a} | {"numbered_words"}
        for field in sorted(fields):
            self.assertIn("`%s`" % field, sec, field)

    def test_worked_example_and_manifest_command_work(self):
        sec = self.section()
        block = re.search(r"\n       (\{\n.*?\n       \})\n", sec, re.S)
        entry = json.loads(re.sub(r"\n       ", "\n", block.group(1)))
        self.assertTrue((ROOT / "data" / "eol" /
                         (entry["product"] + ".json")).is_file())
        command = [l for l in sec.split("\n")
                   if "refresh_data.py manifest" in l][0].strip()
        manifest = json.loads(text(ROOT / "data" / "manifest.json"))
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "my-data"
            shutil.copytree(ROOT / "data", copy)
            path = copy / "aliases.json"
            obj = json.loads(text(path))
            obj["aliases"].append(entry)
            path.write_text(json.dumps(obj), encoding="utf-8")
            for token, value in (
                    ("KEV_CATALOG_VERSION", manifest["kev_catalog_version"]),
                    ("KEV_DATE", manifest["kev_date"]),
                    ("EOL_DATE", manifest["eol_date"]),
                    ("UPSTREAM_COMMIT", manifest["upstream_commit"]),
                    ("../my-data", str(copy))):
                command = command.replace(token, value)
            argv = command.split()
            self.assertEqual(argv[:2], ["python3", "refresh_data.py"])
            argv[0] = sys.executable
            proc = subprocess.run(argv, cwd=str(ROOT), stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,
                                  universal_newlines=True)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            inv = Path(tmp) / "inv.csv"
            inv.write_text("name,version\nnginx,1.24\n", encoding="utf-8")
            from datetime import date
            report = cli.run(str(inv), data=str(copy),
                             as_of=date.fromisoformat(manifest["kev_date"]))
            self.assertEqual(report["items"][0]["product"], "nginx")
            self.assertNotEqual(report["items"][0]["state"], "unmatched")
            plain = cli.run(str(inv), as_of=date.fromisoformat(
                manifest["kev_date"]))
            self.assertEqual(plain["items"][0]["state"], "unmatched")


if __name__ == "__main__":
    unittest.main()
