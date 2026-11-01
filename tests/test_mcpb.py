"""The Claude Desktop package (.mcpb): manifest, allow-list, same bytes on
every build, and a real counts-only session from the unpacked package."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_mcpb  # noqa: E402
import swlc_mcp  # noqa: E402
from swlc import assess  # noqa: E402

DEMO = ROOT / "examples" / "software-inventory.csv"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
ITEM_ID = re.compile(r"\b[0-9a-f]{12}\b")
ALLOWED_FIRST = {"checked_on", "kev_current", "items", "states",
                 "classification", "ambiguous_review", "support_records",
                 "count_total", "note:"} | set(assess.LISTS)
ALLOWED_PATH = re.compile(
    r"(?:manifest\.json|pyproject\.toml|README\.md|swlc_mcp\.py|"
    r"software_lifecycle\.py|VERSION|LICENSE|THIRD-PARTY\.md|"
    r"swlc/[a-z_]+\.py|data/(?:eol/)?[a-z0-9][a-z0-9._-]*\.json)")


def first_sentence(text: str) -> str:
    return text.split(". ", 1)[0].rstrip(".") + "."


def session(server: Path, messages: list) -> dict:
    body = "".join(json.dumps(m) + "\n" for m in messages).encode("utf-8")
    proc = subprocess.run([sys.executable, "-B", str(server)], input=body,
                          capture_output=True, timeout=600,
                          cwd=str(server.parent))
    return {m["id"]: m for m in
            (json.loads(line) for line in proc.stdout.decode().splitlines())}


def copy_sources(dest: Path) -> None:
    """Copy just what the build reads into dest."""
    for src in build_mcpb.FIXED.values():
        (dest / src).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(ROOT / src), str(dest / src))
    for folder, _ in build_mcpb.TREES:
        shutil.copytree(str(ROOT / folder), str(dest / folder),
                        ignore=shutil.ignore_patterns("__pycache__"))


class McpbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.path, cls.names, cls.digest = build_mcpb.build(cls.out / "a")
        with zipfile.ZipFile(str(cls.path)) as zf:
            cls.manifest = json.loads(zf.read("manifest.json"))
            cls.pyproject = zf.read("pyproject.toml").decode("utf-8")
            cls.infos = zf.infolist()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_manifest_has_the_required_fields(self):
        m = self.manifest
        for key in ("manifest_version", "name", "version", "description",
                    "author", "server"):
            self.assertIn(key, m)
        self.assertEqual(m["manifest_version"], "0.4")
        self.assertEqual(m["name"], "software-lifecycle")
        self.assertEqual(m["author"], {"name": "Eve McGivern"})
        self.assertEqual(m["license"], "MIT")
        self.assertEqual(m["server"]["type"], "uv")
        self.assertEqual(m["server"]["entry_point"], "swlc_mcp.py")
        self.assertIn(m["server"]["entry_point"], self.names)
        self.assertEqual(m["compatibility"]["runtimes"], {"python": ">=3.9"})
        self.assertEqual(sorted(m["compatibility"]["platforms"]),
                         ["darwin", "linux", "win32"])

    def test_version_comes_from_version_file(self):
        self.assertEqual(self.manifest["version"], VERSION)
        self.assertIn('\nversion = "%s"\n' % VERSION, self.pyproject)
        self.assertEqual(self.path.name, "software-lifecycle-%s.mcpb"
                         % VERSION)
        source = json.loads((ROOT / "mcpb" / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertNotIn("version", source)

    def test_pyproject_has_no_dependencies(self):
        self.assertIn("\ndependencies = []\n", self.pyproject)
        self.assertIn('\nrequires-python = ">=3.9"\n', self.pyproject)
        self.assertNotIn("[build-system]", self.pyproject)
        self.assertNotIn("optional-dependencies", self.pyproject)

    def test_tools_match_the_server(self):
        listed = [{"name": t["name"],
                   "description": first_sentence(t["description"])}
                  for t in swlc_mcp.TOOLS]
        self.assertEqual(sorted(self.manifest["tools"],
                                key=lambda t: t["name"]),
                         sorted(listed, key=lambda t: t["name"]))

    def test_build_is_byte_for_byte_the_same(self):
        again, names, digest = build_mcpb.build(self.out / "b")
        self.assertEqual(again.read_bytes(), self.path.read_bytes())
        self.assertEqual((names, digest), (self.names, self.digest))
        self.assertEqual([i.filename for i in self.infos], sorted(self.names))
        for info in self.infos:
            self.assertEqual(info.date_time, build_mcpb.DATE)
            self.assertEqual(info.external_attr >> 16, 0o100644)

    def test_only_allow_listed_paths(self):
        self.assertIn("swlc/cli.py", self.names)
        self.assertIn("data/manifest.json", self.names)
        self.assertTrue(any(n.startswith("data/eol/") for n in self.names))
        for name in self.names:
            self.assertRegex(name, ALLOWED_PATH)
            self.assertFalse(name.endswith(".csv"), name)
            self.assertNotRegex(name, r"(^|/)(tests?|examples|docs|\.github)/")
            self.assertNotIn("swlc-out", name)
            self.assertNotIn("__pycache__", name)

    def test_unpacked_server_lists_the_same_tools_and_returns_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            unpacked, inv_dir = Path(tmp) / "pkg", Path(tmp) / "inv"
            inv_dir.mkdir()
            with zipfile.ZipFile(str(self.path)) as zf:
                zf.extractall(str(unpacked))
            inv = inv_dir / "demo.csv"
            shutil.copy2(str(DEMO), str(inv))
            got = session(unpacked / "swlc_mcp.py", [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "check_counts",
                            "arguments": {"path": str(inv)}}}])
            self.assertEqual(got[1]["result"]["serverInfo"]["version"],
                             VERSION)
            served = sorted(t["name"] for t in got[2]["result"]["tools"])
            self.assertEqual(served, sorted(t["name"] for t in
                                            self.manifest["tools"]))
            result = got[3]["result"]
            self.assertFalse(result["isError"], result)
            text = result["content"][0]["text"]
            self.assertTrue(text.startswith("checked_on "), text)
            self.assertIn("items 50 rows 60", text)
            self.assertIsNone(ITEM_ID.search(text), text)
            for line in text.split("\n"):
                self.assertIn(line.split()[0], ALLOWED_FIRST, line)
            self.assertTrue((inv_dir / "swlc-out-demo" / "report.json")
                            .is_file())

    def test_stray_file_stops_the_build(self):
        for stray in ("data/stray.csv", "data/eol/notes.txt",
                      "swlc/scratch.txt"):
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "src"
                copy_sources(src)
                (src / stray).write_text("x\n", encoding="utf-8")
                with self.assertRaisesRegex(build_mcpb.BuildError,
                                            "not on the allow-list"):
                    build_mcpb.build(Path(tmp) / "out", root=src)
                self.assertFalse((Path(tmp) / "out").exists()
                                 and any((Path(tmp) / "out").iterdir()))

    def test_refused_paths_stop_the_build_whatever_the_list_says(self):
        for name, src in (("examples/software-inventory.csv",
                           "examples/software-inventory.csv"),
                          ("tests/helpers.py", "tests/helpers.py"),
                          ("swlc-out-demo/report.md", "README.md")):
            fixed = dict(build_mcpb.FIXED, **{name: src})
            with tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(build_mcpb, "FIXED", fixed):
                with self.assertRaisesRegex(build_mcpb.BuildError,
                                            "refused path"):
                    build_mcpb.build(Path(tmp))

    def test_command_line_prints_files_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, "-B", str(ROOT / "tools" / "build_mcpb.py"),
                 "--out", tmp], capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = proc.stdout.splitlines()
            self.assertIn("swlc_mcp.py", lines)
            self.assertEqual(lines[-1], "sha256 " + self.digest)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             [self.path.name])

    def test_dist_is_ignored_by_git(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").split("\n")
        self.assertIn("dist/", lines)


if __name__ == "__main__":
    unittest.main()
