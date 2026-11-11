"""Prices for a basket. A basket is a list of (name, price, quantity) lines; prices are in pounds."""


def subtotal(basket):
    """Each line's price times its quantity, added up."""
    return round(sum(price * quantity for name, price, quantity in basket), 2)


def total(basket):
    """What the customer pays."""
    return subtotal(basket)
