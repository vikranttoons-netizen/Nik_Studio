from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout
)

from ui.sidebar import Sidebar
from ui.workspace import Workspace


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Nik Studio")

        self.resize(1500,900)

        central = QWidget()

        self.setCentralWidget(central)

        layout = QHBoxLayout(central)

        layout.setContentsMargins(0,0,0,0)

        self.sidebar = Sidebar()

        self.workspace = Workspace()

        layout.addWidget(self.sidebar)

        layout.addWidget(self.workspace)

        self.setStyleSheet("""

        QMainWindow{

            background:#1E1E1E;

        }

        QWidget{

            background:#252526;

            color:white;

        }

        QPushButton{

            background:#2D2D30;

            border:none;

            text-align:left;

            padding-left:20px;

            font-size:15px;

        }

        QPushButton:hover{

            background:#3A3D41;

        }

        """)