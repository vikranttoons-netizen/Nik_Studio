import sys
from pathlib import Path

# Allow "python app/main.py" from the project root as well as
# "python main.py" from inside the app folder.
APP_DIR = Path(__file__).resolve().parent

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402


def main():

    app = QApplication(sys.argv)

    window = MainWindow()

    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
