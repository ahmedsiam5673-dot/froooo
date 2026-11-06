"""Where Fro keeps its files (settings, notes, logs) and where bundled assets live."""
import os
import sys
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    d = Path(base) / "Fro"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resource(*parts: str) -> Path:
    """Path to a bundled file (works both from source and from the PyInstaller exe)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base.joinpath(*parts)
