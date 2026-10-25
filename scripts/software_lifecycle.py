#!/usr/bin/env python3
"""Entry point: python3 software_lifecycle.py check INVENTORY ..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from swlc.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
