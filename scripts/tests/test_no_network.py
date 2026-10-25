import ast
import socket
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import make_data_dir, run_main, write_inventory

SWLC = Path(__file__).resolve().parents[1] / "swlc"
BANNED = {"urllib", "http", "socket", "ssl", "ftplib", "smtplib", "requests"}


def _boom(*args, **kwargs):
    raise AssertionError("network access attempted")


class _BlockedSocket:
    def __init__(self, *args, **kwargs):
        raise AssertionError("network socket created")


class NoNetworkTests(unittest.TestCase):
    def test_check_runs_with_network_calls_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_dir(tmp, "2026-10-22", "2026-10-20")
            inv = write_inventory(Path(tmp) / "inv.csv")
            out = Path(tmp) / "out"
            with mock.patch.object(socket.socket, "connect", _boom), \
                    mock.patch.object(socket, "socket", _BlockedSocket), \
                    mock.patch.object(socket, "create_connection", _boom), \
                    mock.patch.object(urllib.request, "urlopen", _boom):
                code, _, err = run_main(
                    ["check", inv, "--data", data, "--as-of", "2026-10-24",
                     "--out", str(out)])
                self.assertEqual(code, 0, err)
                code, _, err = run_main(["verify-data", "--data", data])
                self.assertEqual(code, 0, err)
            self.assertTrue((out / "report.json").is_file())

    def test_no_swlc_module_imports_a_network_library(self):
        files = sorted(SWLC.glob("*.py"))
        self.assertIn("cli.py", [f.name for f in files])
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    self.assertNotIn(name.split(".")[0], BANNED,
                                     "%s imports %s" % (path.name, name))


if __name__ == "__main__":
    unittest.main()
