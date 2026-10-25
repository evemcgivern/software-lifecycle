"""Simulate the weekly end-of-life job's own gate.

The weekly workflow rewrites data/manifest.json with a later end-of-life
date and then runs the whole test suite before it opens a pull request. This
test copies the working tree, runs the workflow's own manifest step with
later fake dates, and runs the whole suite in the copy. Anything in the
suite that depends on the bundled data's dates fails here.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from refresh_data import canonical  # noqa: E402
from test_workflows import (  # noqa: E402
    read, run_blocks, run_script, step_script)

STEP = "Update data/eol and the manifest, then run the checks"
SKIP = ("__pycache__", ".git", ".superpowers", "*.pyc")


REMOVED = "backdrop"        # a product no alias or gold row uses
RETITLED = "akeneo-pim"
ADDED = "zz-gate-sim-product"


def step_env(text, step_name):
    """{name: value} from the env: block of the step with this name."""
    lines = text.split("\n")
    start = lines.index("      - name: " + step_name)
    out, inside = {}, False
    for line in lines[start + 1:]:
        if line.startswith("      - ") or line.startswith("        run:"):
            break
        if line == "        env:":
            inside = True
        elif inside and line.strip().startswith("#"):
            continue
        elif inside and line.startswith("          "):
            key, _, value = line.strip().partition(": ")
            out[key] = value
        else:
            inside = False
    return out


def weekly_flags():
    """The step's env values that are literals (no expressions), as the
    workflow sets them: quotes dropped."""
    return {k: v.strip('"') for k, v in
            step_env(read("eol-weekly.yml"), STEP).items() if "${{" not in v}


def changed_catalog(runner, repo):
    """Stage what a weekly build could produce: a new product, a removed
    product and a retitled one, in both the eol folder and products.json."""
    shutil.copytree(repo / "data" / "eol", runner / "eol")
    (runner / "eol" / (REMOVED + ".json")).unlink()
    shutil.copy(runner / "eol" / (RETITLED + ".json"),
                runner / "eol" / (ADDED + ".json"))
    catalog = json.loads((repo / "data" / "products.json").read_text("utf-8"))
    products = []
    for rec in catalog["products"]:
        if rec["id"] == REMOVED:
            continue
        if rec["id"] == RETITLED:
            rec = dict(rec, title=rec["title"] + " Edited")
        products.append(rec)
    products.append({"id": ADDED, "title": "Gate Sim Product",
                     "category": "app", "vendors": ["gatesim"],
                     "namespaces": []})
    products.sort(key=lambda r: r["id"])
    (runner / "products.json").write_bytes(
        canonical(dict(catalog, products=products)))


def simulate(eol_days, kev_days=0, suite=True, catalog_change=False,
             curation_names=None, tail=3000, pattern=None, flags=None):
    """Apply the workflow's manifest step to a copy; return suite output.

    catalog_change stages a changed catalog (see changed_catalog);
    curation_names puts that product id in the copy's curation.json first.
    The suite runs with the step's own env flags (SWLC_WEEKLY_JOB) and
    SWLC_GATE_SIM. With pattern, only those test files run, verbose, with
    flags (default: the step's flags, no SWLC_GATE_SIM)."""
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text("utf-8"))
    eol_day = (date.fromisoformat(manifest["eol_date"])
               + timedelta(days=eol_days)).isoformat()
    kev_day = (date.fromisoformat(manifest["kev_date"])
               + timedelta(days=kev_days)).isoformat()
    script = step_script(read("eol-weekly.yml"), STEP)
    script = script[:script.index("python3 -B -m unittest discover")]
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(*SKIP))
        mpath = repo / "data" / "manifest.json"
        copy = json.loads(mpath.read_text("utf-8"))
        copy["kev_date"] = kev_day
        mpath.write_text(json.dumps(copy), encoding="utf-8")

        if curation_names:
            cpath = repo / "data" / "curation.json"
            curation = json.loads(cpath.read_text("utf-8"))
            curation["generated_off"] = [curation_names]
            cpath.write_bytes(canonical(curation))

        def setup(runner):
            if catalog_change:
                changed_catalog(runner, repo)
                return
            # The weekly build step's outputs: the eol folder and a
            # regenerated products.json.
            shutil.copytree(repo / "data" / "eol", runner / "eol")
            shutil.copy(repo / "data" / "products.json",
                        runner / "products.json")

        env = {"UPSTREAM_SHA": "0123456789abcdef0123456789abcdef01234567",
               "UPSTREAM_DAY": eol_day, "_SETUP": setup}
        code, out, _ = run_script(
            script, env, repo,
            stubs={"python3": 'exec "%s" "$@"' % sys.executable})
        if code != 0:
            return code, out[-tail:] if tail else out
        text = (repo / "data" / "manifest.json").read_text("utf-8")
        if '"release_id": "main-eol-%s"' % eol_day not in text:
            return 1, "manifest release id not rewritten"
        env = {k: v for k, v in os.environ.items()
               if k not in ("SWLC_GATE_SIM", "SWLC_WEEKLY_JOB")}
        if pattern is None:
            env.update(weekly_flags(), SWLC_GATE_SIM="1")
            args = []
        else:
            env.update(weekly_flags() if flags is None else flags)
            args = ["-v", "-p", pattern]
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s",
             "tests"] + args, cwd=str(repo), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, timeout=600)
        return proc.returncode, proc.stdout[-tail:] if tail else proc.stdout


@unittest.skipUnless(shutil.which("bash"), "needs bash")
@unittest.skipIf(os.environ.get("SWLC_GATE_SIM"),
                 "already inside the simulation copy")
class WeeklyGateSimulation(unittest.TestCase):
    def test_suite_passes_after_a_later_end_of_life_date(self):
        code, out = simulate(eol_days=30)
        self.assertEqual(code, 0, out)

    def test_suite_does_not_depend_on_kev_freshness(self):
        code, out = simulate(eol_days=30, kev_days=20)
        self.assertEqual(code, 0, out)

    def test_suite_passes_with_a_changed_catalog(self):
        # A new product, a removed one and a retitle, with no curation
        # entry touching the removed product.
        code, out = simulate(eol_days=30, catalog_change=True)
        self.assertEqual(code, 0, out)

    def test_curation_naming_a_removed_product_blocks_the_update(self):
        # The weekly job must stop, and say why, when curation.json still
        # names a product the new data no longer has.
        code, out = simulate(eol_days=30, catalog_change=True,
                             curation_names=REMOVED, tail=None)
        self.assertNotEqual(code, 0, out[-1500:])
        self.assertIn("curation.json: a product named here is not in the "
                      "catalog", out)
        self.assertNotIn(REMOVED, out.split("curation.json:")[1][:80])

    def test_the_same_curation_entry_is_fine_while_the_product_exists(self):
        code, out = simulate(eol_days=30, curation_names=REMOVED)
        self.assertEqual(code, 0, out)

    def test_generated_floor_is_reported_not_gating_in_the_weekly_job(self):
        # The retitled product has generated gold rows. With the flags the
        # workflow sets, the generated floor is reported and the benchmark
        # passes; with no flag (a pull request or a local run) it fails.
        code, out = simulate(eol_days=30, catalog_change=True,
                             pattern="test_benchmark.py", tail=None)
        self.assertEqual(code, 0, out[-1500:])
        self.assertIn("reported, not gating", out)
        code, out = simulate(eol_days=30, catalog_change=True,
                             pattern="test_benchmark.py", flags={},
                             tail=None)
        self.assertNotEqual(code, 0, out[-1500:])
        self.assertIn("generated correct fell below the floor", out)


class WeeklyWorkflowFlagTests(unittest.TestCase):
    def test_the_full_suite_step_sets_the_weekly_flag(self):
        self.assertEqual(step_env(read("eol-weekly.yml"), STEP).get(
            "SWLC_WEEKLY_JOB"), '"1"')
        self.assertEqual(weekly_flags(), {"SWLC_WEEKLY_JOB": "1"})
        self.assertIn("python3 -B -m unittest discover -s tests",
                      step_script(read("eol-weekly.yml"), STEP))

    def test_no_expression_in_any_run_body(self):
        lines = list(run_blocks(read("eol-weekly.yml")))
        self.assertTrue(lines)
        for number, line in lines:
            self.assertNotIn("${{", line, "eol-weekly.yml:%d" % number)


if __name__ == "__main__":
    unittest.main()
