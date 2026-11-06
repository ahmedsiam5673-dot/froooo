"""Entry point (used by `python main.py` and by PyInstaller)."""
import sys

from fro.app import run

if __name__ == "__main__":
    sys.exit(run(sys.argv))
