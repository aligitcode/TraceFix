DISCOUNTS = {"SAVE10": 0.10, "SAVE20": 0.20}

def apply_discount(price, code):
    return price * (1 - DISCOUNTS[code])
