from ratelib11 import split_cost


def process_order(order):
    people = len(order["names"]) - 1
    return split_cost(sum(order["items"]), people)
