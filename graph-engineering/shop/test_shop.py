import unittest
from prices import subtotal, total
from receipt import receipt

BASKET = [("mug", 8.5, 2), ("card", 2.0, 1)]


class TestShop(unittest.TestCase):
    def test_subtotal(self):
        self.assertEqual(subtotal(BASKET), 19.0)

    def test_total(self):
        self.assertEqual(total(BASKET), 19.0)

    def test_receipt(self):
        self.assertEqual(receipt(BASKET), "2 x mug: £17.00\n1 x card: £2.00\nTotal: £19.00")


if __name__ == "__main__":
    unittest.main()
