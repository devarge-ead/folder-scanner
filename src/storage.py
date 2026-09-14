"""Persistence for the application settings and folder list.

A JSON file is created automatically next to the executable (in dev mode it is
placed in the project root). It stores the selected folders with their checkbox
state, plus the last used settings and languages.
"""

import json
import os
import sys


def _app_dir() -> str:
    """Directory where the JSON storage lives (next to the executable)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


STORAGE_PATH = os.path.join(_app_dir(), "storage.json")


def default_state() -> dict:
    """Return a fresh default state object."""
    return {
        "folders": [],
        "settings": {
            "match_method": "exact",
            "fuzzy_threshold": 85,
            "file_types": {
                "filename": True,
                "word": True,
                "excel": True,
                "pdf": True,
                "txt": True,
            },
            "ui_language": "en",
        },
    }


def load() -> dict:
    """Load persisted state, falling back to defaults when unavailable."""
    state = default_state()
    try:
        with open(STORAGE_PATH, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError, TypeError):
        return state

    if isinstance(raw, dict):
        if isinstance(raw.get("folders"), list):
            state["folders"] = [
                f for f in raw["folders"] if isinstance(f, dict) and "path" in f
            ]
        settings = raw.get("settings")
        if isinstance(settings, dict):
            state["settings"].update(settings)
    return state


def save(state: dict) -> None:
    """Write the current state to the JSON file (best effort)."""
    try:
        with open(STORAGE_PATH, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
    except OSError:
        pass