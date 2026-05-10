#!/usr/bin/env python3
"""Compatibility wrapper for the canonical pipeline entrypoint."""

from __future__ import annotations

import runpy
from pathlib import Path


runpy.run_path(Path(__file__).resolve().parent / "pipeline" / "run_policy_expansion.py", run_name="__main__")
