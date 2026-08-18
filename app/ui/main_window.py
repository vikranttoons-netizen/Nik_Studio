from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
)

from ui.sidebar import Sidebar
from ui.content import Content

from core.project import Project


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # The folder is in the title because Nik Studio can be pointed at
        # a different one (Google Drive, say) with NIKSTUDIO_ROOT, and it
        # is otherwise impossible to tell which copy you are looking at.
        self.setWindowTitle(f"Nik Studio  —  {Project().root}")

        self.resize(1600, 900)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar = Sidebar()
        self.content = Content()

        layout.addWidget(self.sidebar)
        layout.addWidget(self.content)

        # ---------------- Navigation ----------------

        self.sidebar.dashboard.clicked.connect(
            lambda: self.content.setCurrentWidget(self.content.dashboard)
        )

        self.sidebar.workspace.clicked.connect(
            lambda: self.content.setCurrentWidget(self.content.workspace)
        )

        self.sidebar.episodes.clicked.connect(
            lambda: self.content.setCurrentWidget(self.content.episodes)
        )

        self.sidebar.images.clicked.connect(
            lambda: self.content.setCurrentWidget(self.content.images)
        )

        self.sidebar.videos.clicked.connect(
            lambda: self.content.setCurrentWidget(self.content.videos)
        )

        self.sidebar.export.clicked.connect(
            lambda: self.content.setCurrentWidget(self.content.export)
        )

        self.sidebar.settings.clicked.connect(
            lambda: self.content.setCurrentWidget(self.content.settings)
        )

        # Show dashboard by default
        self.content.setCurrentWidget(self.content.dashboard)

        self.setStyleSheet(self.THEME)

    # ---------------- Shutdown ----------------

    def closeEvent(self, event):

        # A render runs on its own thread. Qt crashes if that thread is
        # still running when the window is destroyed.
        self.content.workspace.shutdown()

        super().closeEvent(event)

    # ---------------- Theme ----------------

    THEME = """
        QMainWindow {
            background: #1E1E1E;
        }

        QWidget {
            background: #252526;
            color: white;
        }

        QPushButton {
            background: #2D2D30;
            border: none;
            padding: 10px;
            text-align: left;
            font-size: 15px;
        }

        QPushButton:hover {
            background: #3E3E42;
        }

        QPushButton:disabled {
            color: #888;
        }

        QListWidget {
            background: #1E1E1E;
            border: 1px solid #3C3C3C;
            color: white;
        }

        QTextEdit {
            background: #1E1E1E;
            border: 1px solid #3C3C3C;
            color: white;
            font-size: 14px;
        }

        QComboBox {
            background: #1E1E1E;
            border: 1px solid #3C3C3C;
            color: white;
            padding: 4px;
        }

        QProgressBar {
            background: #1E1E1E;
            border: 1px solid #3C3C3C;
            text-align: center;
            color: white;
        }

        QProgressBar::chunk {
            background: #0E639C;
        }

        QLabel {
            color: white;
        }
    """