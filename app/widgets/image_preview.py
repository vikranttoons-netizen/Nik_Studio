from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class ImagePreview(QLabel):

    def __init__(self):
        super().__init__()

        self.setAlignment(Qt.AlignCenter)

        self.setMinimumSize(700, 500)

        self.setWordWrap(True)

        self.setStyleSheet("""
            border:2px solid #444;
            border-radius:8px;
            background:#202124;
        """)

        self.setText("No Image")

        # Remembered so the image can be redrawn when the panel resizes.
        self._pixmap = None

    # ------------------------------------------------------------------

    def show_scene(self, episode_folder, scene):

        self._pixmap = None

        if scene is None or not scene.image:

            stage = scene.pipeline.image if scene else None

            if stage is not None and stage.is_failed:
                self.setText(f"❌ {stage.error}")
            elif stage is not None and stage.status.value == "waiting":
                self.setText(
                    "⏳ Waiting for the cloud GPU.\n\n"
                    "Run the Colab worker, then press Import Results."
                )
            else:
                self.setText("No image yet — press 🚀 Render Episode")

            return

        image_path = Path(episode_folder) / scene.image

        if not image_path.exists():

            self.setText(f"Image not found:\n{scene.image}")

            return

        pix = QPixmap(str(image_path))

        if pix.isNull():

            self.setText(f"Unable to load image:\n{scene.image}")

            return

        self._pixmap = pix

        self._draw()

    # ------------------------------------------------------------------

    def _draw(self):

        if self._pixmap is None:
            return

        self.setPixmap(
            self._pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def resizeEvent(self, event):

        super().resizeEvent(event)

        # Without this the preview stays at its old size when the window
        # is resized.
        self._draw()
