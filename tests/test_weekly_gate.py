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

from test_workflows import read, run_script, step_script  # noqa: E402

STEP = "Update data/eol and the manifest, then run the checks"
SKIP = ("__pycache__", ".git", ".superpowers", "*.pyc")


def simulate(eol_days, kev_days=0, suite=True):
    """Apply the workflow's manifest step to a copy; return suite output."""
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

        def setup(runner):
            shutil.copytree(repo / "data" / "eol", runner / "eol")

        env = {"UPSTREAM_SHA": "0123456789abcdef0123456789abcdef01234567",
               "UPSTREAM_DAY": eol_day, "_SETUP": setup}
        code, out, _ = run_script(
            script, env, repo,
            stubs={"python3": 'exec "%s" "$@"' % sys.executable})
        if code != 0:
            return code, out
        text = (repo / "data" / "manifest.json").read_text("utf-8")
        if '"release_id": "main-eol-%s"' % eol_day not in text:
            return 1, "manifest release id not rewritten"
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s",
             "tests"], cwd=str(repo),
            env=dict(os.environ, SWLC_GATE_SIM="1"),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, timeout=600)
        return proc.returncode, proc.stdout[-3000:]


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


if __name__ == "__main__":
    unittest.main()
