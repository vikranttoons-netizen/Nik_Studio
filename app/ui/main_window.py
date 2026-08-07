from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout

from ui.sidebar import Sidebar
from ui.content import Content


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Nik Studio")

        self.resize(1500, 900)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar = Sidebar()
        self.content = Content()

        layout.addWidget(self.sidebar)
        layout.addWidget(self.content)

        # Navigation
        self.sidebar.dashboard.clicked.connect(
            lambda: self.content.setCurrentIndex(0)
        )

        self.sidebar.episodes.clicked.connect(
            lambda: self.content.setCurrentIndex(1)
        )

        self.sidebar.images.clicked.connect(
            lambda: self.content.setCurrentIndex(2)
        )

        self.sidebar.videos.clicked.connect(
            lambda: self.content.setCurrentIndex(3)
        )

        self.sidebar.export.clicked.connect(
            lambda: self.content.setCurrentIndex(4)
        )

        self.sidebar.settings.clicked.connect(
            lambda: self.content.setCurrentIndex(5)
        )

        self.setStyleSheet("""
            QMainWindow {
                background:#1E1E1E;
            }

            QWidget {
                background:#252526;
                color:white;
            }

            QPushButton {
                background:#2D2D30;
                border:none;
                text-align:left;
                padding-left:20px;
                font-size:15px;
            }

            QPushButton:hover {
                background:#3A3D41;
            }

            QListWidget {
                background:#1E1E1E;
                color:white;
                border:none;
            }
        """)