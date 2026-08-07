from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt


class VideosPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Videos")
        title.setAlignment(Qt.AlignCenter)

        title.setStyleSheet("""
            font-size:32px;
            font-weight:bold;
            color:white;
        """)

        layout.addWidget(title)

        layout.addStretch()