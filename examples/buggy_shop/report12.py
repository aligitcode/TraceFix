from settings12 import DEFAULT_TAX


def build_report():
    subtotal = 100
    return subtotal * (1 + DEFAULT_TAX)
