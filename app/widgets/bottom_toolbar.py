from PySide6.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
)


class BottomToolbar(QWidget):

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)

        buttons = [
            "🖼 Generate Image",
            "🎥 Generate Video",
            "🎙 Generate Voice",
            "🎵 Generate Music",
            "📤 Export"
        ]

        for text in buttons:
            layout.addWidget(QPushButton(text))