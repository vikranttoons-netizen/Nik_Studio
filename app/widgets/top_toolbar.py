from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)


class TopToolbar(QWidget):

    def __init__(self):
        super().__init__()

        self.setFixedHeight(70)

        layout = QHBoxLayout(self)

        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.title = QLabel("🎬 Episode Workspace")

        self.title.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
        """)

        self.title.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )

        self.save = QPushButton("💾 Save")

        self.generateImage = QPushButton("🖼 Generate")

        self.generateVideo = QPushButton("🎥 Video")

        self.voice = QPushButton("🎙 Voice")

        self.music = QPushButton("🎵 Music")

        self.export = QPushButton("📤 Export")

        buttons = [
            self.save,
            self.generateImage,
            self.generateVideo,
            self.voice,
            self.music,
            self.export,
        ]

        for btn in buttons:
            btn.setMinimumHeight(42)
            btn.setMinimumWidth(120)

        layout.addWidget(self.title)
        layout.addWidget(self.save)
        layout.addWidget(self.generateImage)
        layout.addWidget(self.generateVideo)
        layout.addWidget(self.voice)
        layout.addWidget(self.music)
        layout.addWidget(self.export)