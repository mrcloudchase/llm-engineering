import unittest
from prices import receipt


class TestReceipt(unittest.TestCase):
    def test_with_a_coupon(self):
        self.assertEqual(receipt([(10, 2), (5, 1)], "CA", "SAVE10"), "\n".join([
            "Items            3",
            "Subtotal     25.00",
            "Coupon       -2.50",
            "Tax           1.63",
            "Shipping      5.00",
            "Total        29.13",
        ]))

    def test_without_a_coupon(self):
        self.assertEqual(receipt([(30, 2)], "OR"), "\n".join([
            "Items            2",
            "Subtotal     60.00",
            "Tax           0.00",
            "Shipping      0.00",
            "Total        60.00",
        ]))


if __name__ == "__main__":
    unittest.main()
