from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class ImagePreview(QLabel):

    def __init__(self):
        super().__init__()

        self.setAlignment(Qt.AlignCenter)

        self.setMinimumSize(700, 500)

        self.setStyleSheet("""
            border:2px solid #444;
            border-radius:8px;
            background:#202124;
        """)

        self.setText("No Image")

    def show_scene(self, episode_folder, scene):

        image_path = Path(episode_folder) / scene.image

        if not image_path.exists():

            self.setText("Image not found")

            return

        pix = QPixmap(str(image_path))

        if pix.isNull():

            self.setText("Unable to load image")

            return

        self.setPixmap(
            pix.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )