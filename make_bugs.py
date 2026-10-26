import json
from pathlib import Path

d = Path("examples/buggy_shop")
files = {
    "run_bug11.py": 'from orders11 import process_order\n\nprint(process_order({"items": [10, 20], "names": ["ali"]}))\n',
    "orders11.py": 'from ratelib11 import split_cost\n\n\ndef process_order(order):\n    people = len(order["names"]) - 1\n    return split_cost(sum(order["items"]), people)\n',
    "ratelib11.py": 'def split_cost(total, people):\n    return total / people\n',
    "run_bug12.py": 'from report12 import build_report\n\nprint(build_report())\n',
    "settings12.py": 'DEFAULT_TAX = "0.2"\n',
    "report12.py": 'from settings12 import DEFAULT_TAX\n\n\ndef build_report():\n    subtotal = 100\n    return subtotal * (1 + DEFAULT_TAX)\n',
    "run_bug13.py": 'from users13 import greet_all\n\ngreet_all([{"name": "ali"}, {"nam": "sara"}])\n',
    "users13.py": 'from fmt13 import shout\n\n\ndef greet_all(users):\n    for user in users:\n        print(shout(user))\n',
    "fmt13.py": 'def shout(user):\n    return "HELLO " + user["name"].upper()\n',
    "run_bug14.py": 'from cart14 import total_price\n\nprint(total_price([{"price": 5}, {"price": 7}]))\n',
    "cart14.py": 'from parse14 import to_number\n\n\ndef total_price(items):\n    total = 0\n    for item in items:\n        total += to_number(item["price"])\n    return total\n',
    "parse14.py": 'def to_number(value):\n    if isinstance(value, str):\n        return float(value)\n',
}
for name, text in files.items():
    (d / name).write_text(text, encoding="utf-8")

p = Path("examples/expected.json")
cases = json.loads(p.read_text(encoding="utf-8"))
new = [
    {"script": "examples/buggy_shop/run_bug11.py", "error_type": "ZeroDivisionError", "file": "ratelib11.py", "line": 2, "cause_file": "orders11.py", "cause_line": 5, "evidence_sufficient": True},
    {"script": "examples/buggy_shop/run_bug12.py", "error_type": "TypeError", "file": "report12.py", "line": 6, "cause_file": "settings12.py", "cause_line": 1, "evidence_sufficient": True},
    {"script": "examples/buggy_shop/run_bug13.py", "error_type": "KeyError", "file": "fmt13.py", "line": 2, "cause_file": "run_bug13.py", "cause_line": 3, "evidence_sufficient": True},
    {"script": "examples/buggy_shop/run_bug14.py", "error_type": "TypeError", "file": "cart14.py", "line": 7, "cause_file": "parse14.py", "cause_line": 2, "evidence_sufficient": True},
]
have = {c["script"] for c in cases}
cases += [c for c in new if c["script"] not in have]
p.write_text("[\n" + ",\n".join("  " + json.dumps(c) for c in cases) + "\n]\n", encoding="utf-8")
print(len(cases), "cases")
