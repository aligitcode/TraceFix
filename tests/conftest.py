import sys
from pathlib import Path

# evaluate.py lives in the repository root, next to examples/, so tests can import and run it.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
