import unittest
from prices import tax


class TestTax(unittest.TestCase):
    def test_california(self):
        self.assertEqual(tax(100, "CA"), 7.25)

    def test_new_york(self):
        self.assertEqual(tax(22.5, "NY"), 0.9)

    def test_oregon(self):
        self.assertEqual(tax(100, "OR"), 0)

    def test_rounds_half_up(self):
        self.assertEqual(tax(10, "CA"), 0.73)

    def test_unknown_region(self):
        with self.assertRaises(ValueError):
            tax(10, "ZZ")


if __name__ == "__main__":
    unittest.main()
