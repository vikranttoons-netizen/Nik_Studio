from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton


class Sidebar(QWidget):

    def __init__(self):
        super().__init__()

        self.setFixedWidth(220)

        layout = QVBoxLayout(self)

        self.dashboard = QPushButton("🏠 Dashboard")
        self.workspace = QPushButton("🎬 Workspace")
        self.episodes = QPushButton("📂 Episodes")
        self.images = QPushButton("🖼 Images")
        self.videos = QPushButton("🎥 Videos")
        self.export = QPushButton("📤 Export")
        self.settings = QPushButton("⚙ Settings")

        buttons = [
            self.dashboard,
            self.workspace,
            self.episodes,
            self.images,
            self.videos,
            self.export,
            self.settings,
        ]

        for button in buttons:
            button.setMinimumHeight(42)
            layout.addWidget(button)

        layout.addStretch()