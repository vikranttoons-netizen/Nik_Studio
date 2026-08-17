"""
Nik Studio launcher.

Run this from anywhere:

    python NikStudio.py
"""

import sys
from pathlib import Path

# The app package imports modules as "ui.main_window", "models.scene" etc,
# so the app folder has to be on the import path.
APP_DIR = Path(__file__).resolve().parent / "app"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import main  # noqa: E402


if __name__ == "__main__":
    main()
