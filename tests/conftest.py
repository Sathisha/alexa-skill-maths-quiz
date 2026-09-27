import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT / "lambda", ROOT / "scripts"):
    sys.path.insert(0, str(path))
