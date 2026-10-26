from parse14 import to_number


def total_price(items):
    total = 0
    for item in items:
        total += to_number(item["price"])
    return total
