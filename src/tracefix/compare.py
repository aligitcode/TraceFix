"""Put several saved result files side by side (a Markdown table for the report).

    python compare_runs.py results/baseline_bugs11_14.json results/after_evidence.json results/latest_baseline.json

A cell says whether the behaviour was correct, the confidence the model gave, and FALSE-CONF when the
verifier called the answer supported although the behaviour was wrong. A dash means no answer was
recorded for that bug, which is not the same as a wrong answer.
"""

import json
from pathlib import Path


def load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = {row["bug"]: row for row in data.get("rows", [])}
    return {"name": Path(path).stem, "meta": data.get("meta", {}), "rows": rows}


def answered(row: dict) -> bool:
    return "llm_error" not in row and "correct_behavior" in row


def cell(row) -> str:
    if row is None or not answered(row):
        return "-"
    text = "ok" if row["correct_behavior"] else "WRONG"
    if row.get("confidence"):
        text += f" ({row['confidence']})"
    if row.get("false_confidence"):
        text += " FALSE-CONF"
    return text


def summarize(run: dict) -> dict:
    rows = list(run["rows"].values())
    got = [r for r in rows if answered(r)]
    return {
        "total": len(rows),
        "answered": len(got),
        "correct": sum(1 for r in got if r["correct_behavior"]),
        "false_confidence": sum(1 for r in got if r.get("false_confidence")),
    }


def bug_order(name: str):
    digits = "".join(ch for ch in name if ch.isdigit())
    return (int(digits) if digits else 10**6, name)


def table(runs: list[dict]) -> str:
    bugs = sorted({bug for run in runs for bug in run["rows"]}, key=bug_order)
    header = "| bug | " + " | ".join(run["name"] for run in runs) + " |"
    rule = "|---|" + "---|" * len(runs)
    lines = [header, rule]
    for bug in bugs:
        lines.append(f"| {bug} | " + " | ".join(cell(run["rows"].get(bug)) for run in runs) + " |")
    lines.append("")
    lines.append("| run | model | mode | commit | answered | correct behaviour | false confidence |")
    lines.append("|---|---|---|---|---|---|---|")
    for run in runs:
        s, m = summarize(run), run["meta"]
        lines.append(
            f"| {run['name']} | {m.get('model', '?')} | {m.get('mode', 'tracefix')} | {m.get('commit', '?')} | "
            f"{s['answered']} / {s['total']} | {s['correct']} / {s['answered']} | {s['false_confidence']} |"
        )
    return "\n".join(lines)
