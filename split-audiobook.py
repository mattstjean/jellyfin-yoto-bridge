#!/usr/bin/env python3
"""Thin wrapper so `python3 split-audiobook.py "..."` works without needing to `pip install` the package. The real entry point is split_audiobook.main().
"""

import sys
from pathlib import Path

# Make the package importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.split_audiobook import main

if __name__ == "__main__":
    main()