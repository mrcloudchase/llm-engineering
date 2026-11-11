import unittest
from prices import apply_coupon


class TestCoupons(unittest.TestCase):
    def test_percent_off(self):
        self.assertEqual(apply_coupon(25, "SAVE10"), 22.5)

    def test_flat_off(self):
        self.assertEqual(apply_coupon(25, "FLAT5"), 20)

    def test_never_below_zero(self):
        self.assertEqual(apply_coupon(3, "FLAT5"), 0)

    def test_ignores_case(self):
        self.assertEqual(apply_coupon(25, "save10"), 22.5)

    def test_unknown_code(self):
        with self.assertRaises(ValueError):
            apply_coupon(25, "FREE")


if __name__ == "__main__":
    unittest.main()
