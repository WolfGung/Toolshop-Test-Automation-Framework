"""Root conftest.

Makes `src/` importable without an editable install, so `pytest` works from a
clean checkout with nothing but `pip install -r requirements.txt`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
