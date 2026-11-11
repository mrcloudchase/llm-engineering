import unittest
from prices import shipping


class TestShipping(unittest.TestCase):
    def test_under_the_threshold(self):
        self.assertEqual(shipping(49.99), 5)

    def test_free_at_the_threshold(self):
        self.assertEqual(shipping(50), 0)

    def test_empty_basket(self):
        self.assertEqual(shipping(0), 0)


if __name__ == "__main__":
    unittest.main()
