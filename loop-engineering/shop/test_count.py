import unittest
from prices import count


class TestCount(unittest.TestCase):
    def test_counts_quantities(self):
        self.assertEqual(count([(10, 2), (5, 1)]), 3)

    def test_empty_basket(self):
        self.assertEqual(count([]), 0)


if __name__ == "__main__":
    unittest.main()
