"""Static checks on the GitHub Actions files.

The workflows cannot run here, so these tests read them as text. They use
no YAML library (standard library only); each check is a line-based rule
that is stricter than it needs to be.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"
WORKFLOWS = GITHUB / "workflows"
NAMES = ("ci.yml", "kev-daily.yml", "eol-weekly.yml")
VERIFY = ("gh attestation verify data.zip --repo evemcgivern/software-lifecycle"
          " --signer-workflow evemcgivern/software-lifecycle/.github/workflows/"
          "kev-daily.yml --source-ref refs/heads/main")
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


def jobs(text):
    """{job name: [lines]} for the jobs under the top-level jobs: key."""
    out, current = {}, None
    for line in block(text, "jobs"):
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            current = match.group(1)
            out[current] = []
        elif current:
            out[current].append(line)
    return out


def job_key(lines, key):
    """The value of a job-level key (indent 4), or None."""
    for line in lines:
        match = re.match(r"^    %s:(.*)$" % re.escape(key), line)
        if match:
            return match.group(1).strip()
    return None


def lint(text):
    """Problems in one workflow's text; an empty list means clean."""
    problems = []
    lines = text.split("\n")
    for number, line in enumerate(lines, 1):
        match = re.match(r"^(\s*)permissions:(.*)$", line)
        if match:
            if match.group(2).strip():
                problems.append("%d: permissions must be a block" % number)
            col = len(match.group(1))
            for entry in lines[number:]:
                if not entry.strip():
                    continue
                if len(entry) - len(entry.lstrip()) <= col:
                    break
                if not re.match(r"^\s+[a-z-]+: (read|write|none)$", entry):
                    problems.append("%d: odd permission line" % number)
        if "write-all" in line or "read-all" in line:
            problems.append("%d: write-all or read-all" % number)
        if re.match(r"^\s*(?:- )?if:", line) and "github.event." in line:
            problems.append("%d: github.event in an if" % number)
    for name, body in jobs(text).items():
        if any(l.strip() == "id-token: write" for l in body) and \
                name != "publish":
            problems.append("%s: id-token write outside publish" % name)
        if not (job_key(body, "timeout-minutes") or "").isdigit():
            problems.append("%s: no timeout-minutes" % name)
    return problems


def step_script(text, step_name):
    """The run: block of the step with this name, dedented."""
    lines = text.split("\n")
    start = lines.index("      - name: " + step_name)
    for i in range(start + 1, len(lines)):
        if re.match(r"^        run: \|$", lines[i]):
            break
        if lines[i].startswith("      - "):
            raise ValueError("step has no run block")
    body = []
    for line in lines[i + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= 8:
            break
        body.append(line[10:])
    return "\n".join(body) + "\n"


def run_script(script, env, cwd, stubs=None):
    """Run a step script the way Actions does; return (code, output, files).

    stubs maps command names to shell bodies placed first on PATH.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for name, body in (stubs or {}).items():
            path = bin_dir / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(0o755)
        (tmp / "step.sh").write_text(script)
        full = {"PATH": "%s:%s" % (bin_dir, os.environ.get("PATH", "")),
                "HOME": str(tmp), "RUNNER_TEMP": str(tmp / "runner"),
                "GITHUB_OUTPUT": str(tmp / "output"),
                "GITHUB_STEP_SUMMARY": str(tmp / "summary"),
                "STUB_LOG": str(tmp / "stub.log")}
        (tmp / "runner").mkdir()
        full.update(env)
        setup = full.pop("_SETUP", None)
        if setup:
            setup(Path(full["RUNNER_TEMP"]))
        proc = subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail",
             str(tmp / "step.sh")], cwd=str(cwd), env=full,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, timeout=60)
        files = {}
        for name in ("output", "stub.log"):
            path = tmp / name
            files[name] = path.read_text() if path.exists() else ""
        return proc.returncode, proc.stdout, files


MODE_STEP = "Decide the run mode"
PUBLISH_IF = ("github.ref == 'refs/heads/main' && "
              "needs.build.outputs.dry_run == 'false' && "
              "needs.build.outputs.changed == 'true'")
GOOD_REASON = "Bulk backfill approved after reading the CISA notice"


def _mode(text, cwd, **env):
    base = {"IS_MANUAL": "true", "REF": "refs/heads/main",
            "DRY_RUN_INPUT": "", "ALLOW_REMOVED_INPUT": "false",
            "OVERRIDE_INPUT": "false", "OVERRIDE_REASON": ""}
    base.update(env)
    code, out, files = run_script(step_script(text, MODE_STEP), base, cwd)
    values = dict(line.split("=", 1) for line in files["output"].split("\n")
                  if "=" in line)
    return code, values


def kev_guards(text):
    """Problems with kev-daily.yml's publish guards; empty means sound."""
    problems = []
    publish_if = " ".join((job_key(jobs(text)["publish"], "if") or "").split())
    if publish_if != PUBLISH_IF:
        problems.append("publish if is not exactly the main-only condition")
    for bad in ("||", "always()", "cancelled()"):
        if bad in publish_if:
            problems.append("publish if holds %s" % bad)
    baseline = step_script(text, "Get the previous KEV snapshot")
    joined = baseline.replace("\\\n", " ")
    commands = [l for l in joined.split("\n") if "gh attestation verify" in l]
    if len(commands) != 1:
        problems.append("baseline step must hold one attestation check")
    else:
        for flag in ("--repo evemcgivern/software-lifecycle",
                     "--signer-workflow evemcgivern/software-lifecycle/"
                     ".github/workflows/kev-daily.yml",
                     "--source-ref refs/heads/main"):
            if flag not in commands[0]:
                problems.append("baseline check lacks %s" % flag.split()[0])
    with tempfile.TemporaryDirectory() as cwd:
        for env in ({"REF": "refs/heads/feature", "OVERRIDE_INPUT": "true",
                     "OVERRIDE_REASON": GOOD_REASON},
                    {"REF": "refs/heads/feature",
                     "ALLOW_REMOVED_INPUT": "true"}):
            code, _ = _mode(text, cwd, **env)
            if code == 0:
                problems.append("an override ran on a branch other than main")
        for reason in ("short", "see https://example.com/x for details",
                       "reason: with a colon here", "line one ok\nline two"):
            code, _ = _mode(text, cwd, OVERRIDE_INPUT="true",
                            OVERRIDE_REASON=reason)
            if code == 0:
                problems.append("an unsafe override reason was accepted")
        code, values = _mode(text, cwd, OVERRIDE_INPUT="true",
                             OVERRIDE_REASON=GOOD_REASON, DRY_RUN_INPUT="false")
        if code != 0 or values.get("allow_bulk") != "true":
            problems.append("a valid override on main was refused")
        for dry_input, expected in (("", "true"), ("true", "true"),
                                    ("false", "false")):
            code, values = _mode(text, cwd, DRY_RUN_INPUT=dry_input)
            if code != 0 or values.get("dry_run") != expected:
                problems.append("manual dry_run %r did not give %s"
                                % (dry_input, expected))
        code, values = _mode(text, cwd, IS_MANUAL="false", DRY_RUN_INPUT="")
        if values.get("dry_run") != "false":
            problems.append("a scheduled run became a dry run")
    publish = step_script(text, "Create the data release")
    if "pattern='^[A-Za-z0-9 .,;()_-]{10,200}$'" not in publish:
        problems.append("publish step does not recheck the reason pattern")
    return problems


PROPOSE_STEP = "Push a branch and open the pull request"
PROCEED = "Opening a pull request from"


def _propose(text, gh_exit=0, gh_out="", ls_exit=2, omit=None):
    def setup(runner):
        update = runner / "update"
        (update / "eol").mkdir(parents=True)
        (update / "eol" / "demo.json").write_text("[]\n")
        for name, body in (("manifest.json", "{}\n"),
                           ("products.json", "{}\n"),
                           ("pr-body.md", "body\n")):
            if name != omit:
                (update / name).write_text(body)
    stubs = {
        "gh": 'echo "gh $*" >> "$STUB_LOG"\n'
              'if [ "$1 $2" = "pr list" ]; then printf "%s" "$STUB_GH_OUT";'
              ' exit "$STUB_GH_EXIT"; fi\nexit 0',
        "git": 'echo "git $*" >> "$STUB_LOG"\n'
               'if [ "$1" = "ls-remote" ]; then exit "$STUB_LS_EXIT"; fi\nexit 0',
        "base64": "cat > /dev/null; echo eA==",
    }
    env = {"GH_TOKEN": "token", "UPSTREAM_SHA": "a" * 40, "FLAGGED": "false",
           "STUB_GH_EXIT": str(gh_exit), "STUB_GH_OUT": gh_out,
           "STUB_LS_EXIT": str(ls_exit), "_SETUP": setup}
    with tempfile.TemporaryDirectory() as cwd:
        (Path(cwd) / "data" / "eol").mkdir(parents=True)
        return run_script(step_script(text, PROPOSE_STEP), env, cwd, stubs)


def weekly_guards(text):
    """Problems with eol-weekly.yml's pull request guards."""
    problems = []
    for label, kwargs in (("gh pr list failing", {"gh_exit": 1}),
                          ("git ls-remote failing", {"ls_exit": 128})):
        code, out, files = _propose(text, **kwargs)
        if code == 0 or PROCEED in out or " push " in files["stub.log"]:
            problems.append("%s did not stop the job" % label)
    code, out, files = _propose(text, gh_out="data/eol-2026-10-01\n")
    if code != 0 or " push " in files["stub.log"]:
        problems.append("an open data/eol pull request did not stop quietly")
    code, out, files = _propose(text, ls_exit=0)
    if code == 0 or " push " in files["stub.log"]:
        problems.append("an existing branch did not stop the job")
    for name in ("manifest.json", "products.json", "pr-body.md"):
        code, out, files = _propose(text, omit=name)
        if code == 0 or " push " in files["stub.log"]:
            problems.append("an update without %s did not stop the job"
                            % name)
    code, out, files = _propose(text)
    if code != 0 or PROCEED not in out or " push " not in files["stub.log"]:
        problems.append("the normal path did not push: %s" % out[-300:])
    return problems


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

    def test_lint_is_clean(self):
        for name in NAMES:
            self.assertEqual(lint(read(name)), [], name)

    def test_lint_catches_each_mutation(self):
        text = read("kev-daily.yml")
        mutations = [
            ("    permissions:\n      issues: write",
             "    permissions: write-all"),
            ("    permissions:\n      issues: write",
             "    permissions:\n      issues: write\n      id-token: write"),
            ("    permissions:\n      issues: write",
             "    permissions:\n      issues: write-all"),
            ("      - name: Fetch the KEV catalog\n",
             "      - name: Fetch the KEV catalog\n"
             "        if: github.event.issue.title == 'x'\n"),
            ("    timeout-minutes: 10\n", ""),
        ]
        for old, new in mutations:
            self.assertIn(old, text)
            self.assertTrue(lint(text.replace(old, new, 1)), new)

    def test_every_checkout_keeps_no_credentials(self):
        for name in NAMES:
            text = read(name)
            self.assertEqual(text.count("actions/checkout@"),
                             text.count("persist-credentials: false"), name)

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

    def test_matrix_runner_is_pinned(self):
        self.assertEqual(job_key(jobs(read("ci.yml"))["test"], "runs-on"),
                         "ubuntu-24.04")

    def test_windows_job_is_informational(self):
        job = jobs(read("ci.yml"))["test-windows"]
        self.assertEqual(job_key(job, "runs-on"), "windows-latest")
        self.assertEqual(job_key(job, "continue-on-error"), "true")
        body = "\n".join(job)
        self.assertIn("run: python -B -m unittest discover -s tests", body)
        self.assertNotIn("matrix", body)

    def test_timeouts(self):
        expected = {"test": "10", "test-windows": "15", "sbom": "10",
                    "upstream-format": "15"}
        found = {n: job_key(b, "timeout-minutes")
                 for n, b in jobs(read("ci.yml")).items()}
        self.assertEqual(found, expected)


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

    def test_publish_only_from_main_through_an_environment(self):
        body = jobs(self.text)["publish"]
        self.assertTrue(job_key(body, "if").startswith(
            "github.ref == 'refs/heads/main' && "))
        self.assertEqual(job_key(body, "environment"), "data-release")
        self.assertEqual(job_key(body, "timeout-minutes"), "15")

    def test_baseline_and_notes_pin_signer_and_ref(self):
        self.assertIn("--signer-workflow evemcgivern/software-lifecycle/"
                      ".github/workflows/kev-daily.yml", self.text)
        self.assertIn("--source-ref refs/heads/main", self.text)
        self.assertIn(VERIFY, self.text)

    def test_override_needs_a_reason_and_main(self):
        lines = "\n".join(block(self.text, "on"))
        for needle in ("override_gate:", "override_reason:",
                       "type: string"):
            self.assertIn(needle, lines)
        chunk = lines[lines.index("override_gate:"):][:200]
        self.assertIn("type: boolean", chunk)
        self.assertIn("default: false", chunk)
        chunk = lines[lines.index("allow_removed:"):][:200]
        self.assertIn("default: false", chunk)
        mode = self.text[self.text.index("- name: Decide the run mode"):]
        mode = mode[:mode.index("- name:", 10)]
        self.assertIn('[ "$REF" = "refs/heads/main" ]', mode)
        self.assertIn("REF: ${{ github.ref }}", mode)
        self.assertIn("--allow-bulk", self.text)
        self.assertIn("Override reason", self.text)

    def test_data_zip_ships_the_catalog_and_curation_files(self):
        script = step_script(
            self.text, "Assemble, verify and zip the data folder")
        copies = [l for l in script.split("\n")
                  if l.startswith("cp data/aliases.json")]
        self.assertEqual(len(copies), 1)
        for name in ("aliases.json", "profiles.json", "products.json",
                     "curation.json"):
            self.assertIn("data/" + name, copies[0])
        self.assertIn('"$out/"', copies[0])

    def test_zip_is_reproducible(self):
        self.assertIn("refresh_data.py zip --dir", self.text)
        # No shell zip command: it records file times and directory order.
        self.assertIsNone(re.search(r"(?<![\w./-])zip -[A-Za-z]", self.text))
        self.assertIsNotNone(re.search(r"(?<![\w./-])zip -[A-Za-z]",
                                       "(cd x && zip -X -r a.zip .)"))

    def test_missing_bundled_data_is_plain_text(self):
        self.assertIn("Main has no bundled end-of-life data", self.text)

    def test_failed_dry_runs_open_no_issue(self):
        body = jobs(self.text)["report"]
        condition = job_key(body, "if")
        self.assertIn("github.event_name == 'schedule' || "
                      "needs.build.outputs.dry_run == 'false'", condition)
        self.assertNotIn("!= 'true'", condition)

    def test_timeouts(self):
        found = {n: job_key(b, "timeout-minutes")
                 for n, b in jobs(self.text).items()}
        self.assertEqual(found, {"build": "15", "publish": "15",
                                 "report": "10"})

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

    def test_push_credential_only_in_the_push_job(self):
        found = jobs(self.text)
        self.assertEqual(sorted(found), ["build", "propose", "report"])
        build = "\n".join(found["build"])
        self.assertNotIn("contents: write", build)
        self.assertNotIn("git push", build)
        self.assertEqual(self.text.count("extraheader"), 1)
        self.assertIn("::add-mask::", self.text)
        for name, minutes in (("build", "15"), ("propose", "15"),
                              ("report", "10")):
            self.assertEqual(job_key(found[name], "timeout-minutes"), minutes)

    def test_stops_when_a_data_pr_is_open(self):
        self.assertIn("gh pr list --state open", self.text)
        self.assertIn("grep -q '^data/eol-'", self.text)

    def test_summary_exit_codes_are_read_strictly(self):
        script = step_script(self.text,
                             "Build the snapshot and summarise the changes")
        flat = " ".join(script.split())
        self.assertIn('if [ "$status" -gt 1 ] || ! grep -q', flat)
        self.assertIn("--old-products data/products.json", flat)
        self.assertIn('if [ "$status" -eq 1 ]; then flagged=true;', flat)

    def test_failure_report_job_mirrors_the_daily_one(self):
        found = jobs(self.text)
        report = "\n".join(found["report"])
        self.assertEqual(
            [l.strip() for l in found["report"]
             if l.strip().startswith(("issues:", "contents:", "pull-requests:",
                                      "id-token:"))], ["issues: write"])
        for name in ("build", "propose"):
            self.assertNotIn("issues:", "\n".join(found[name]))
        self.assertEqual(job_key(found["report"], "needs"),
                         "[build, propose]")
        condition = " ".join(job_key(found["report"], "if").split())
        self.assertEqual(
            condition, "always() && (needs.build.result == 'failure' || "
            "needs.propose.result == 'failure')")
        self.assertIn("eol-weekly-failed", report)
        self.assertIn("gh issue create", report)
        self.assertIn("gh issue comment", report)
        self.assertIn("--body-file body.md", report)
        script = step_script(self.text,
                             "Open or update the eol-weekly-failed issue")
        self.assertNotIn("${{", script)
        # The body is fixed text plus the run URL built from runner variables.
        self.assertIn("$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/"
                      "$GITHUB_RUN_ID", script)
        for word in ("UPSTREAM", "summary.md", "RUNNER_TEMP", "cat \"$"):
            self.assertNotIn(word, script)

    def test_weekly_schedule(self):
        self.assertRegex(self.text, r'- cron: "\d+ \d+ \* \* [0-6]"')
        self.assertIn("workflow_dispatch:", self.text)

    def test_catalog_is_regenerated_summarised_and_committed(self):
        for needle in ('--products-out "$RUNNER_TEMP/products.json"',
                       '--new-products "$RUNNER_TEMP/products.json"',
                       "--old-products data/products.json",
                       'cp "$RUNNER_TEMP/products.json" data/products.json',
                       'cp data/products.json "$update/products.json"',
                       'cp "$update/products.json" data/products.json',
                       "git add data/eol data/products.json "
                       "data/manifest.json"):
            self.assertIn(needle, self.text, needle)
        # A change to products.json alone also opens a pull request.
        self.assertIn('cmp -s "$RUNNER_TEMP/products.json" '
                      "data/products.json", self.text)

    def test_pr_body_says_a_failing_curation_test_blocks_the_pr(self):
        script = step_script(
            self.text, "Update data/eol and the manifest, then run the checks")
        for needle in ("curation checks and the benchmark",
                       "no pull request until the maintainer fixes it "
                       "(see docs/sop.md)",
                       'Follow \\"Maintainer: when the weekly data job '
                       'fails\\" in docs/sop.md'):
            self.assertIn(needle, " ".join(script.split()), needle)
        self.assertIn("python3 -B -m unittest discover -s tests || {",
                      script)
        sop = (WORKFLOWS.parents[1] / "docs" / "sop.md").read_text("utf-8")
        self.assertIn("\n## Maintainer: when the weekly data job fails\n",
                      sop)

    def test_steps(self):
        for needle in ("refresh_data.py eol --upstream-commit",
                       "refresh_data.py eol-summary",
                       "refresh_data.py manifest",
                       "software_lifecycle.py verify-data",
                       "python3 -B -m unittest discover -s tests"):
            self.assertIn(needle, self.text, needle)


class ReportLabelTests(unittest.TestCase):
    def test_both_report_jobs_create_their_label(self):
        # A missing label makes "gh issue create --label" fail, so each
        # report job creates its own label before it opens an issue.
        for name, label in (("eol-weekly.yml", "eol-weekly-failed"),
                            ("kev-daily.yml", "data-gate-failed")):
            with self.subTest(workflow=name):
                body = "\n".join(jobs(read(name))["report"])
                self.assertIn("gh label create %s " % label, body)
                self.assertLess(body.index("gh label create %s " % label),
                                body.index("gh issue create"))


class RepoFilesTests(unittest.TestCase):
    def test_dependabot_watches_actions_weekly(self):
        text = (GITHUB / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn('package-ecosystem: "github-actions"', text)
        self.assertIn('interval: "weekly"', text)

    def test_readme_has_maintainer_notes(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Maintaining", text)
        self.assertIn("60 days", text)
        self.assertIn("ubuntu-24.04", text)

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
        self.assertIn(VERIFY, text)
        self.assertIn("data-release", text)
        self.assertIn("environment", text)
        self.assertIn("not independently assessed", text)
        self.assertIn("does not and cannot verify signatures offline", text)
        self.assertIn("private vulnerability reporting", text)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class WeeklyManifestTests(unittest.TestCase):
    """Run the weekly workflow's own manifest step on a scratch copy of the
    data, then run the data checks against that copy."""

    def test_weekly_manifest_passes_the_data_checks(self):
        import sys
        script = step_script(
            read("eol-weekly.yml"),
            "Update data/eol and the manifest, then run the checks")
        cut = script.index("python3 -B -m unittest discover -s tests")
        script = script[:cut]
        self.assertIn("--release-id", script)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo = tmp / "repo"
            repo.mkdir()
            shutil.copytree(ROOT / "data", repo / "data")
            shutil.copytree(ROOT / "swlc", repo / "swlc",
                            ignore=shutil.ignore_patterns("__pycache__"))
            for name in ("refresh_data.py", "software_lifecycle.py", "VERSION"):
                shutil.copy(ROOT / name, repo / name)

            def setup(runner):
                shutil.copytree(repo / "data" / "eol", runner / "eol")
                shutil.copy(repo / "data" / "products.json",
                            runner / "products.json")

            env = {"UPSTREAM_SHA": "0123456789abcdef0123456789abcdef01234567",
                   "UPSTREAM_DAY": "2026-11-02", "_SETUP": setup}
            code, out, _ = run_script(
                script, env, repo,
                stubs={"python3": 'exec "%s" "$@"' % sys.executable})
            self.assertEqual(code, 0, out)
            manifest = (repo / "data" / "manifest.json").read_text("utf-8")
            self.assertIn('"release_id": "main-eol-2026-11-02"', manifest)
            self.assertIn('"products.json"', manifest)
            self.assertIn('"curation.json"', manifest)
            test_env = dict(os.environ,
                            SWLC_DATA_DIR=str(repo / "data"))
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "discover", "-s",
                 "tests", "-p", "test_bundled_data.py"], cwd=str(ROOT),
                env=test_env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, timeout=300)
            self.assertEqual(proc.returncode, 0, proc.stdout)


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class GuardBehaviourTests(unittest.TestCase):
    """Run the guard scripts with stubs, and prove the checks catch edits."""

    def test_kev_daily_guards_hold(self):
        self.assertEqual(kev_guards(read("kev-daily.yml")), [])

    def test_kev_daily_guard_mutations_are_caught(self):
        text = read("kev-daily.yml")
        baseline_flags = (
            "              --signer-workflow evemcgivern/software-lifecycle/"
            ".github/workflows/kev-daily.yml \\\n"
            "              --source-ref refs/heads/main\n")
        mutations = [
            ("needs.build.outputs.changed == 'true'\n",
             "needs.build.outputs.changed == 'true' || always()\n"),
            ("    if: github.ref == 'refs/heads/main' && ",
             "    if: "),
            ("--repo evemcgivern/software-lifecycle \\\n" + baseline_flags,
             "--repo evemcgivern/software-lifecycle\n"),
            ('              if [ "$on_main" != "true" ]; then',
             "              if false; then"),
            ('if [ "$DRY_RUN_INPUT" != "false" ]; then dry_run=true; fi',
             'if [ "$DRY_RUN_INPUT" = "true" ]; then dry_run=true; fi'),
            ("pattern='^[A-Za-z0-9 .,;()_-]{10,200}$'\n"
             "              if ! [[",
             "pattern='^[A-Za-z0-9 .,:;()_/-]{10,200}$'\n"
             "              if ! [["),
        ]
        for old, new in mutations:
            self.assertIn(old, text)
            self.assertTrue(kev_guards(text.replace(old, new, 1)), new)

    def test_eol_weekly_guards_hold(self):
        self.assertEqual(weekly_guards(read("eol-weekly.yml")), [])

    def test_eol_weekly_fail_open_forms_are_caught(self):
        text = read("eol-weekly.yml")
        script = step_script(text, PROPOSE_STEP)
        start = script.index('if ! open_heads="$(')
        end = script.index("if ! printf '%s' \"$UPSTREAM_SHA\"")
        old_pr = script[start:end]
        fail_open_pr = (
            "if gh pr list --state open --limit 200 --json headRefName "
            "--jq '.[].headRefName' | grep -q '^data/eol-'; then\n"
            '  echo "::notice::open"\n  exit 0\nfi\n')
        start = script.index("status=0\ngit ls-remote")
        end = script.index('echo "Opening a pull request')
        old_ls = script[start:end]
        fail_open_ls = (
            'if git ls-remote --exit-code --heads origin "$branch" '
            '> /dev/null; then\n  echo "exists"\n  exit 1\nfi\n')
        for old, new in ((old_pr, fail_open_pr), (old_ls, fail_open_ls)):
            indented = "".join("          " + l if l.strip() else l
                               for l in old.splitlines(True))
            replaced = "".join("          " + l if l.strip() else l
                               for l in new.splitlines(True))
            self.assertIn(indented, text)
            mutated = text.replace(indented, replaced, 1)
            self.assertTrue(weekly_guards(mutated), new)
