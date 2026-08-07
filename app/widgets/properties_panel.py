from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QFormLayout,
)


class PropertiesPanel(QWidget):

    def __init__(self):
        super().__init__()

        layout = QFormLayout(self)

        self.name = QLabel("-")
        self.status = QLabel("-")
        self.image = QLabel("-")
        self.video = QLabel("-")

        layout.addRow("Scene", self.name)
        layout.addRow("Status", self.status)
        layout.addRow("Image", self.image)
        layout.addRow("Video", self.video)

    def show_scene(self, scene):

        self.name.setText(scene.name)
        self.status.setText(scene.status)
        self.image.setText(scene.image)
        self.video.setText(scene.video)