from cart15 import add_item


def pay(cart):
    (only_item,) = cart
    return only_item


print(pay(add_item("apple")))
print(pay(add_item("pear")))
