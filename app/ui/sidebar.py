from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton


class Sidebar(QWidget):

    def __init__(self):
        super().__init__()

        self.setFixedWidth(220)

        layout = QVBoxLayout(self)

        pages = [
            "🏠 Dashboard",
            "📂 Episodes",
            "🖼 Images",
            "🎥 Videos",
            "🎵 Audio",
            "🤖 AI Models",
            "📤 Export",
            "⚙ Settings"
        ]

        for page in pages:
            btn = QPushButton(page)
            btn.setMinimumHeight(42)
            layout.addWidget(btn)

        layout.addStretch()