#!/usr/bin/env python3
"""Offline schema v3 migration; the original data/ is never switched here."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weimingzi_corpus.schema_migration import main


if __name__ == "__main__":
    raise SystemExit(main())
