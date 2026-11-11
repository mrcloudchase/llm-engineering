# Hidden acceptance tests: the feature requests, and what "done right" means for each. The agents never see this file.
# uv run ../acceptance.py              lists the requests
# uv run ../acceptance.py gift_wrap    checks the shop folder you're in against one of them
import subprocess, sys

REQUESTS = {                                             # name: (the request, as a person would write it; the checks that say it was done right)
    "gift_wrap": ("Add gift wrap at £3 per item. total(basket, gift_wrap=True) adds £3 for every item, counting quantities "
                  "(two mugs are two items). receipt(basket, gift_wrap=True) shows the charge on its own line, like "
                  "'Gift wrap: £6.00', just above the total, and the total includes it.",
                  ["total([('mug', 8.5, 2), ('card', 2.0, 1)], gift_wrap=True) == 28.0",
                   "total([('mug', 8.5, 2), ('card', 2.0, 1)]) == 19.0",
                   "receipt([('mug', 8.5, 2), ('card', 2.0, 1)], gift_wrap=True).splitlines()[-2] == 'Gift wrap: £9.00'",
                   "receipt([('mug', 8.5, 2), ('card', 2.0, 1)], gift_wrap=True).splitlines()[-1] == 'Total: £28.00'",
                   "'Gift wrap' not in receipt([('mug', 8.5, 2), ('card', 2.0, 1)])"]),
    "three_for_two": ("Cards are now 3 for 2: for every three cards in a basket, one is free. Count cards across every line "
                      "named 'card'. When cards have different prices, the cheapest ones are the free ones.",
                      ["total([('card', 2.0, 3)]) == 4.0",
                       "total([('card', 2.0, 7)]) == 10.0",
                       "total([('card', 2.0, 2), ('card', 3.5, 1)]) == 5.5",
                       "total([('card', 2.0, 1), ('card', 3.5, 5)]) == 14.0",
                       "total([('mug', 8.5, 2), ('card', 2.0, 1)]) == 19.0",
                       "receipt([('card', 2.0, 3)]).splitlines()[-1] == 'Total: £4.00'"]),
    "christmas": ("Christmas offers, all in one change. 1) Cards are 3 for 2: for every three cards in a basket, counted across "
                  "every line named 'card', one is free, and the free ones are the cheapest. 2) Members get 10% off what's left "
                  "when that comes to £20 or more: total(basket, member=True). 3) total(basket, gift_wrap=True) adds £3 for every "
                  "item, counting quantities; gift wrap is never discounted. 4) receipt(basket, member=..., gift_wrap=...) shows "
                  "each offer that applies on its own line above the total, in this order and format: 'Card offer: -£2.00', "
                  "'Member discount: -£1.80', 'Gift wrap: £9.00'. Round money to the penny.",
                  ["total([('card', 2.0, 3), ('mug', 8.5, 2)]) == 21.0",
                   "total([('card', 2.0, 3), ('mug', 8.5, 2)], member=True) == 18.9",
                   "total([('card', 2.0, 3), ('mug', 8.5, 2)], member=True, gift_wrap=True) == 33.9",
                   "total([('card', 5.0, 3), ('mug', 4.5, 2)], member=True) == 19.0",
                   "total([('card', 5.0, 3), ('mug', 5.0, 2)], member=True) == 18.0",
                   "receipt([('card', 2.0, 3), ('mug', 8.5, 2)], member=True, gift_wrap=True).splitlines()[-4:] == "
                   "['Card offer: -£2.00', 'Member discount: -£2.10', 'Gift wrap: £15.00', 'Total: £33.90']",
                   "receipt([('mug', 8.5, 2)], member=True) == '2 x mug: £17.00\\nTotal: £17.00'"]),
    "gift_receipt": ("Add gift receipts: receipt(basket, gift=True) lists the items without their prices and leaves out "
                     "the total, so it can go in the box with a present.",
                     ["receipt([('mug', 8.5, 2), ('card', 2.0, 1)], gift=True).splitlines()[0].strip().rstrip(':') == '2 x mug'",
                      "len(receipt([('mug', 8.5, 2), ('card', 2.0, 1)], gift=True).splitlines()) == 2",
                      "'£' not in receipt([('mug', 8.5, 2), ('card', 2.0, 1)], gift=True)",
                      "receipt([('mug', 8.5, 2), ('card', 2.0, 1)]) == '2 x mug: £17.00\\n1 x card: £2.00\\nTotal: £19.00'"]),
}

def passes(expression, folder="."):                      # one check, in a fresh Python, on the shop in folder
    code = f"from prices import *\nfrom receipt import *\nimport sys\nsys.exit(0 if ({expression}) else 1)"
    return subprocess.run([sys.executable, "-B", "-c", code], cwd=folder, capture_output=True).returncode == 0

def check(name, folder="."):                             # every check for one request, plus the shop's own tests
    checks = REQUESTS[name][1] + ["the shop's own tests pass"]
    own = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q"], cwd=folder, capture_output=True).returncode == 0
    return [(c, passes(c, folder)) for c in checks[:-1]] + [(checks[-1], own)]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        for name, (request, _) in REQUESTS.items(): print(f"{name:14} {request}")
        sys.exit()
    results = check(sys.argv[1])
    for c, ok in results: print(("PASS  " if ok else "FAIL  ") + c)
    print(f"{sys.argv[1]}: {sum(ok for _, ok in results)}/{len(results)} checks passed")
