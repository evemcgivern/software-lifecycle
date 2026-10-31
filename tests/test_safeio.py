import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swlc.safeio import write_text


class WriteTextTests(unittest.TestCase):
    def test_writes_without_fchmod(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "out.txt")
            # patch.dict restores os as it was, whether or not it had fchmod.
            with mock.patch.dict(os.__dict__):
                os.__dict__.pop("fchmod", None)
                self.assertFalse(hasattr(os, "fchmod"))
                write_text(target, "hello")
            self.assertEqual(Path(target).read_text("utf-8"), "hello")

    @unittest.skipIf(sys.platform == "win32" and sys.version_info < (3, 13),
                     "os.fchmod is missing on Windows before Python 3.13")
    def test_writes_with_fchmod(self):
        self.assertTrue(hasattr(os, "fchmod"))
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "out.txt")
            write_text(target, "hello")
            self.assertEqual(Path(target).read_text("utf-8"), "hello")


if __name__ == "__main__":
    unittest.main()
