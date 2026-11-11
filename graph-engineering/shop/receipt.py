"""The receipt a customer gets with their basket."""
from prices import total


def receipt(basket):
    """One line per item, then the total."""
    lines = [f"{quantity} x {name}: £{price * quantity:.2f}" for name, price, quantity in basket]
    lines.append(f"Total: £{total(basket):.2f}")
    return "\n".join(lines)
