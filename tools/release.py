#!/usr/bin/env python3
"""Derive the release view: one head transcript per item, confirmations applied."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weimingzi_corpus.release import main

if __name__ == "__main__":
    raise SystemExit(main())
