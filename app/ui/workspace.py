from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt


class Workspace(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        label = QLabel("Welcome to Nik Studio")
        label.setAlignment(Qt.AlignCenter)

        label.setStyleSheet("""
            font-size:30px;
            font-weight:bold;
            color:white;
        """)

        layout.addWidget(label)