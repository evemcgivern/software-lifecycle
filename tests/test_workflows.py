"""Static checks on the GitHub Actions files.

The workflows cannot run here, so these tests read them as text. They use
no YAML library (standard library only); each check is a line-based rule
that is stricter than it needs to be.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"
WORKFLOWS = GITHUB / "workflows"
NAMES = ("ci.yml", "kev-daily.yml", "eol-weekly.yml")
USES_RE = re.compile(
    r"^\s*(?:- )?uses: ([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@([0-9a-f]{40})"
    r" # v\d+\.\d+\.\d+$")


def read(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def run_blocks(text):
    """Yield (line number, text) for every line that belongs to a run: key."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        match = re.match(r"^(\s*(?:- )?)run:(.*)$", lines[i])
        if not match:
            i += 1
            continue
        key_col = len(match.group(1))
        rest = match.group(2).strip()
        yield i + 1, rest
        i += 1
        if rest and rest[0] in "|>":
            while i < len(lines) and (not lines[i].strip() or
                                      len(lines[i]) - len(lines[i].lstrip())
                                      > key_col):
                yield i + 1, lines[i]
                i += 1


def block(text, key):
    """The lines under a top-level key, up to the next top-level key."""
    lines = text.split("\n")
    start = lines.index(key + ":")
    out = []
    for line in lines[start + 1:]:
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        out.append(line)
    return out


class WorkflowFileTests(unittest.TestCase):
    def test_all_workflows_exist(self):
        found = sorted(p.name for p in WORKFLOWS.glob("*.yml"))
        self.assertEqual(found, sorted(NAMES))
        self.assertEqual(list(WORKFLOWS.glob("*.yaml")), [])

    def test_every_uses_is_pinned_to_a_full_sha(self):
        count = 0
        for name in NAMES:
            for number, line in enumerate(read(name).split("\n"), 1):
                if "uses:" in line and not line.lstrip().startswith("#"):
                    count += 1
                    self.assertRegex(line, USES_RE,
                                     "%s:%d is not pinned" % (name, number))
        self.assertGreater(count, 5)

    def test_one_sha_per_action(self):
        pins = {}
        for name in NAMES:
            for line in read(name).split("\n"):
                match = USES_RE.match(line)
                if match:
                    pins.setdefault(match.group(1), set()).add(match.group(2))
        for action, shas in pins.items():
            self.assertEqual(len(shas), 1, action)

    def test_no_risky_triggers_or_words(self):
        for name in NAMES:
            text = read(name)
            for word in ("pull_request_target", "workflow_run",
                         "--no-verify", "force"):
                self.assertNotIn(word, text.lower(), "%s: %s" % (name, word))
            self.assertNotIn("\t", text, name)

    def test_top_level_permissions_are_read_only(self):
        for name in NAMES:
            text = read(name)
            self.assertIn("\npermissions:\n", text, name)
            perms = [l.strip() for l in block(text, "permissions") if l.strip()]
            self.assertEqual(perms, ["contents: read"], name)

    def test_no_expressions_inside_run_blocks(self):
        for name in NAMES:
            lines = list(run_blocks(read(name)))
            self.assertTrue(lines, name)
            for number, line in lines:
                self.assertNotIn("${{", line, "%s:%d" % (name, number))

    def test_no_expressions_in_step_names(self):
        for name in NAMES:
            for number, line in enumerate(read(name).split("\n"), 1):
                if re.match(r"^\s*(?:- )?name:", line):
                    self.assertNotIn("${{", line, "%s:%d" % (name, number))

    def test_only_the_job_token_is_used(self):
        for name in NAMES:
            for secret in re.findall(r"secrets\.([A-Za-z0-9_]+)", read(name)):
                self.assertEqual(secret, "GITHUB_TOKEN", name)

    def test_expressions_use_known_contexts_only(self):
        allowed = ("github.", "inputs.", "steps.", "needs.", "matrix.",
                   "runner.temp")
        for name in NAMES:
            for expr in re.findall(r"\$\{\{(.*?)\}\}", read(name)):
                self.assertTrue(any(a in expr for a in allowed),
                                "%s: %s" % (name, expr))
                for bad in ("github.event.", "github.head_ref"):
                    self.assertNotIn(bad, expr, name)


class CiWorkflowTests(unittest.TestCase):
    def test_matrix_and_test_command(self):
        text = read("ci.yml")
        self.assertIn('python: ["3.9", "3.10", "3.11", "3.12", "3.13"]', text)
        self.assertIn("python3 -B -m unittest discover -s tests", text)
        self.assertIn("pull_request:", text)
        self.assertIn("branches: [main]", text)

    def test_upstream_format_job_runs_on_schedule_only(self):
        text = read("ci.yml")
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("  upstream-format:\n    if: github.event_name == "
                      "'schedule' || github.event_name == "
                      "'workflow_dispatch'", text)
        self.assertIn("refresh_data.py kev", text)
        self.assertIn("refresh_data.py eol", text)

    def test_sbom_job(self):
        text = read("ci.yml")
        self.assertIn("  sbom:", text)
        self.assertIn('"bomFormat": "CycloneDX"', text)
        self.assertIn("actions/upload-artifact@", text)

    def test_checkouts_keep_no_credentials(self):
        for name in ("ci.yml", "kev-daily.yml"):
            text = read(name)
            self.assertEqual(text.count("actions/checkout@"),
                             text.count("persist-credentials: false"), name)


class KevDailyTests(unittest.TestCase):
    def setUp(self):
        self.text = read("kev-daily.yml")

    def test_daily_schedule_off_the_hour(self):
        match = re.search(r'- cron: "(\d+) (\d+) \* \* \*"', self.text)
        self.assertTrue(match)
        self.assertNotEqual(match.group(1), "0")

    def test_manual_runs_default_to_dry_run(self):
        lines = block(self.text, "on")
        joined = "\n".join(lines)
        self.assertIn("workflow_dispatch:", joined)
        start = joined.index("dry_run:")
        chunk = joined[start:start + 200]
        self.assertIn("type: boolean", chunk)
        self.assertIn("default: true", chunk)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.text)

    def test_never_overlaps(self):
        self.assertIn("concurrency:\n  group: data-release\n"
                      "  cancel-in-progress: false", self.text)

    def test_write_permissions_are_per_job(self):
        self.assertIn("      contents: write\n      id-token: write\n"
                      "      attestations: write", self.text)
        self.assertIn("      issues: write", self.text)

    def test_release_steps(self):
        for needle in ("refresh_data.py kev", "refresh_data.py check-kev",
                       "refresh_data.py manifest",
                       "software_lifecycle.py verify-data",
                       "gh release download", "gh attestation verify",
                       "actions/attest-build-provenance@",
                       "gh release create", "--latest=false",
                       "data-gate-failed", "GITHUB_STEP_SUMMARY"):
            self.assertIn(needle, self.text, needle)

    def test_release_id_form_is_checked(self):
        self.assertIn(r"^data-[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+$",
                      self.text)


class EolWeeklyTests(unittest.TestCase):
    def setUp(self):
        self.text = read("eol-weekly.yml")

    def test_opens_a_pull_request_and_never_pushes_main(self):
        self.assertIn("gh pr create", self.text)
        self.assertIn("--body-file", self.text)
        self.assertIn("--base main", self.text)
        self.assertIn('branch="data/eol-', self.text)
        self.assertIn('"HEAD:refs/heads/$branch"', self.text)
        for bad in ("push origin main", "HEAD:main", "refs/heads/main"):
            self.assertNotIn(bad, self.text)

    def test_weekly_schedule(self):
        self.assertRegex(self.text, r'- cron: "\d+ \d+ \* \* [0-6]"')
        self.assertIn("workflow_dispatch:", self.text)

    def test_steps(self):
        for needle in ("refresh_data.py eol --upstream-commit",
                       "refresh_data.py eol-summary",
                       "refresh_data.py manifest",
                       "software_lifecycle.py verify-data",
                       "python3 -B -m unittest discover -s tests"):
            self.assertIn(needle, self.text, needle)


class RepoFilesTests(unittest.TestCase):
    def test_dependabot_watches_actions_weekly(self):
        text = (GITHUB / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn('package-ecosystem: "github-actions"', text)
        self.assertIn('interval: "weekly"', text)

    def test_issue_template_asks_for_names_only(self):
        text = (GITHUB / "ISSUE_TEMPLATE" / "unmatched-product.yml").read_text(
            encoding="utf-8")
        for needle in ("Product name", "Publisher", "Version string format",
                       "inventory rows", "internal application names",
                       "owner names"):
            self.assertIn(needle, text, needle)
        config = (GITHUB / "ISSUE_TEMPLATE" / "config.yml").read_text(
            encoding="utf-8")
        self.assertIn("blank_issues_enabled: false", config)
        self.assertIn("SECURITY.md", config)

    def test_security_file_makes_no_offline_signature_claim(self):
        text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("gh attestation verify", text)
        self.assertIn("--repo evemcgivern/software-lifecycle", text)
        self.assertIn("not independently assessed", text)
        self.assertIn("does not and cannot verify signatures offline", text)
        self.assertIn("private vulnerability reporting", text)


if __name__ == "__main__":
    unittest.main()
