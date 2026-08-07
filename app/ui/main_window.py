from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
)

from ui.sidebar import Sidebar
from ui.content import Content


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Nik Studio")

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

        self.setStyleSheet("""
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

        QLabel {
            color: white;
        }
        """)