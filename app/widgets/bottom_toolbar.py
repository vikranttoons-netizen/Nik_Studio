from PySide6.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
    QSizePolicy,
)


class BottomToolbar(QWidget):

    def __init__(self):
        super().__init__()

        self.setFixedHeight(70)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        layout = QHBoxLayout(self)

        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        self.save = QPushButton("💾 Save")
        self.generateImage = QPushButton("🖼 Generate Image")
        self.generateVideo = QPushButton("🎥 Generate Video")
        self.export = QPushButton("📤 Export")

        buttons = [
            self.save,
            self.generateImage,
            self.generateVideo,
            self.export,
        ]

        for btn in buttons:
            btn.setMinimumHeight(42)
            btn.setMinimumWidth(150)
            layout.addWidget(btn)

        layout.addStretch()