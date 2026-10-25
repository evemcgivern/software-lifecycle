import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swlc.normalize import best_cycle, cycle_matches, normalize_name, split_version


class NormalizeNameTests(unittest.TestCase):
    def test_sql_server_example(self):
        self.assertEqual(
            normalize_name("Microsoft SQL Server 2016 Standard Edition (64-bit)"),
            "microsoft sql server 2016 standard edition",
        )

    def test_frozen_tokens_dropped(self):
        self.assertEqual(normalize_name("Foo (32-bit) x64 X86 en-US"), "foo")

    def test_whitespace_and_nfkc(self):
        self.assertEqual(normalize_name("  Ｆoo \t  Bar\n"), "foo bar")

    def test_idempotent_random(self):
        rng = random.Random(1234)
        alphabet = "abcXYZ019 \t-_.()ＡÉß" + "x64" + "(64-bit)"
        for _ in range(500):
            s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
            once = normalize_name(s)
            self.assertEqual(normalize_name(once), once, repr(s))

    def test_idempotent_with_adjacent_tokens(self):
        for s in ["x6x64 4", "(64-(64-bit)bit)", "en-en-usus"]:
            once = normalize_name(s)
            self.assertEqual(normalize_name(once), once, repr(s))


class SplitVersionTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(split_version("v13.0.5026"), ["13", "0", "5026"])
        self.assertEqual(split_version("2016 Standard"), ["2016", "standard"])
        self.assertEqual(split_version("1_2-3  4"), ["1", "2", "3", "4"])
        self.assertEqual(split_version(""), [])
        self.assertEqual(split_version("..-"), [])


class CycleMatchTests(unittest.TestCase):
    def test_no_prefix_match_within_part(self):
        self.assertFalse(cycle_matches(["11"], "1"))
        self.assertFalse(cycle_matches(["3", "10"], "3.1"))

    def test_leading_parts(self):
        self.assertTrue(cycle_matches(["2016", "standard"], "2016"))
        self.assertTrue(cycle_matches(["13", "0", "5026"], "13.0"))
        self.assertFalse(cycle_matches(["13"], "13.0"))
        self.assertFalse(cycle_matches(["13"], ""))

    def test_best_cycle(self):
        self.assertEqual(
            best_cycle(["13", "0", "5026"], ["13.0", "13"]), ("13.0", ["13.0"])
        )
        self.assertEqual(best_cycle(["9"], ["1", "10"]), (None, []))

    def test_best_cycle_ambiguity(self):
        best, tied = best_cycle(["13", "0"], ["13.0", "13_0", "13"])
        self.assertEqual(best, "13.0")
        self.assertEqual(tied, ["13.0", "13_0"])

    def test_random_single_part_no_false_match(self):
        rng = random.Random(1234)
        for _ in range(500):
            c = str(rng.randint(1, 999))
            d = str(rng.randint(0, 9))
            self.assertFalse(cycle_matches(split_version(f"{c}{d}"), c), (c, d))


if __name__ == "__main__":
    unittest.main()
