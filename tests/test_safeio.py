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
            with mock.patch.object(os, "fchmod", create=True):
                del os.fchmod
                self.assertFalse(hasattr(os, "fchmod"))
                write_text(target, "hello")
            self.assertEqual(Path(target).read_text("utf-8"), "hello")

    def test_writes_with_fchmod(self):
        self.assertTrue(hasattr(os, "fchmod"))
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "out.txt")
            write_text(target, "hello")
            self.assertEqual(Path(target).read_text("utf-8"), "hello")


if __name__ == "__main__":
    unittest.main()
