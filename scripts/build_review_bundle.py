#!/usr/bin/env python3
"""Compatibility wrapper for the canonical review entrypoint."""

from __future__ import annotations

import runpy
from pathlib import Path


runpy.run_path(Path(__file__).resolve().parent / "review" / "build_review_bundle.py", run_name="__main__")
