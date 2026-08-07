from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton
)


class Sidebar(QWidget):

    pageChanged = Signal(str)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.projects = QPushButton("📁 Projects")
        self.workspace = QPushButton("🎬 Workspace")
        self.characters = QPushButton("👤 Characters")
        self.assets = QPushButton("🖼 Assets")
        self.render = QPushButton("📋 Render")
        self.settings = QPushButton("⚙ Settings")

        buttons = [
            (self.projects, "projects"),
            (self.workspace, "workspace"),
            (self.characters, "characters"),
            (self.assets, "assets"),
            (self.render, "render"),
            (self.settings, "settings")
        ]

        for button, page in buttons:
            button.clicked.connect(
                lambda checked=False, p=page: self.pageChanged.emit(p)
            )
            layout.addWidget(button)

        layout.addStretch()