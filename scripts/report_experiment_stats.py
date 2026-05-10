#!/usr/bin/env python3
"""Compatibility wrapper for the experiment stats reporter."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "pipeline" / "report_experiment_stats.py"
    runpy.run_path(str(target), run_name="__main__")
