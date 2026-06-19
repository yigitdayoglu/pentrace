"""Yol cozumleme — hem gelistirmede hem PyInstaller paketinde dogru calisir.

- resource_path: paketlenmis (salt-okunur) kaynaklar (frontend/dist, wordlists)
- data_dir:      yazilabilir veri (SQLite DB, raporlar) — masaustunde %APPDATA%/PentraCe
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    """Salt-okunur paketli kaynak. PyInstaller _MEIPASS farkindaligi."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    # Gelistirme: proje koku (backend'in ust dizini)
    return Path(__file__).resolve().parent.parent / rel


def data_dir() -> Path:
    """Yazilabilir veri dizini. PENTRACE_DATA_DIR env > backend dizini (dev)."""
    env = os.environ.get("PENTRACE_DATA_DIR")
    p = Path(env) if env else Path(__file__).resolve().parent
    p.mkdir(parents=True, exist_ok=True)
    return p
