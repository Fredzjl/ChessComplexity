#!/usr/bin/env python3
"""Compatibility wrapper for the canonical setup entrypoint."""

from __future__ import annotations

import runpy
from pathlib import Path


runpy.run_path(Path(__file__).resolve().parent / "setup" / "verify_maia2.py", run_name="__main__")
