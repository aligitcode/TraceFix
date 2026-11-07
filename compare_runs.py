"""Print a Markdown table comparing saved result files. See src/tracefix/compare.py."""

import sys

from tracefix.compare import load, table

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python compare_runs.py results/a.json results/b.json ...")
        sys.exit(2)
    print(table([load(path) for path in sys.argv[1:]]))
