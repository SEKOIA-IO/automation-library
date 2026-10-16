import sys
from pathlib import Path

# Ensure local module package is importable during test collection.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
