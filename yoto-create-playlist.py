#!/usr/bin/env python3
"""Thin wrapper so `python3 yoto-create-playlist.py "..."` keeps working.

Most users will invoke this directly. Power users can also do:
    python3 -m yoto_bridge "..."
"""

import sys
from pathlib import Path

# Make the package importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.bridge.cli import main

if __name__ == "__main__":
    main()