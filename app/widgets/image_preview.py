from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class ImagePreview(QLabel):

    def __init__(self):
        super().__init__()

        self.setAlignment(Qt.AlignCenter)

        self.setText("No Image")

        self.setMinimumSize(700, 500)

    def load_image(self, image_path):

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