import json

data = json.load(open("results/latest.json", encoding="utf-8"))

def walk(node, label=""):
    if isinstance(node, dict):
        if "likely_cause" in node:
            print("-----", label)
            print(node["likely_cause"])
        for k, v in node.items():
            walk(v, str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{label}[{i}]")

walk(data)
