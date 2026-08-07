from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton


class Sidebar(QWidget):

    def __init__(self):
        super().__init__()

        self.setFixedWidth(220)

        layout = QVBoxLayout(self)

        self.dashboard = QPushButton("🏠 Dashboard")
        self.episodes = QPushButton("📂 Episodes")
        self.images = QPushButton("🖼 Images")
        self.videos = QPushButton("🎥 Videos")
        self.export = QPushButton("📤 Export")
        self.settings = QPushButton("⚙ Settings")

        buttons = [
            self.dashboard,
            self.episodes,
            self.images,
            self.videos,
            self.export,
            self.settings,
        ]

        for b in buttons:
            b.setMinimumHeight(42)
            layout.addWidget(b)

        layout.addStretch()