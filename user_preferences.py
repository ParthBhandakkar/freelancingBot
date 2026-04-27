"""Compatibility module expected by browser/engine.py.

This freelancing bot does not use JSON-based user preferences.
Only the browser profile directory helper is required.
"""
from __future__ import annotations

from pathlib import Path

from config import BROWSER_DATA_DIR


def agent_browser_data_dir() -> Path:
    path = BROWSER_DATA_DIR / "agent_browser_freelancing"
    path.mkdir(parents=True, exist_ok=True)
    return path


def active_automation_user_id() -> str:
    return "freelancing_default"

