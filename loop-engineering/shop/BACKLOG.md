# Backlog

The shop's code is in `prices.py`. Each feature has its own test file, and a feature is done when its tests pass. Work on one feature at a time: make its tests pass before you start the next.

1. **discount**: `total(items, discount)` takes the discount off as a flat amount, but it's a percentage: 10 off a 25.00 basket is 22.50. (`test_discount.py`)
2. **count**: `count(items)` returns how many items are in the basket, counting quantities. (`test_count.py`)
3. **tax**: `tax(amount, region)` returns the sales tax on an amount: 7.25% in CA, 4% in NY, none in OR. Round half up to the cent, so 0.725 is 0.73. An unknown region raises `ValueError`. (`test_tax.py`)
4. **shipping**: `shipping(subtotal)` is 5.00, and free at 50.00 or more. An empty basket ships free. (`test_shipping.py`)
5. **coupons**: `apply_coupon(amount, code)` takes a coupon off: `SAVE10` is 10% off, `FLAT5` is 5.00 off but never below zero. Codes ignore case. An unknown code raises `ValueError`. (`test_coupons.py`)
6. **receipt**: `receipt(items, region, code=None)` returns the receipt as text: the item count, subtotal, coupon (only if there is one), tax, shipping and total. The coupon comes off before tax and shipping. (`test_receipt.py`)
