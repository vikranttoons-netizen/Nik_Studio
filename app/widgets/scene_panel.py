from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)

from widgets.scene_list import SceneList


class ScenePanel(QWidget):
    """
    The scene list plus the buttons that edit it.

    Up and Down matter more than they look: the scene order is the order
    the clips are stitched together in the final video.
    """

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.list = SceneList()

        layout.addWidget(self.list)

        # ------------------------------------------------------- buttons

        row = QHBoxLayout()
        row.setSpacing(4)

        self.add = QPushButton("➕")
        self.delete = QPushButton("🗑")
        self.up = QPushButton("▲")
        self.down = QPushButton("▼")

        self.add.setToolTip("Add a scene below the selected one")
        self.delete.setToolTip(
            "Remove the selected scene\n"
            "(images and clips already made are kept on disk)"
        )
        self.up.setToolTip("Move the scene earlier in the episode")
        self.down.setToolTip("Move the scene later in the episode")

        for button in (self.add, self.delete, self.up, self.down):
            button.setMinimumHeight(34)
            button.setStyleSheet("text-align:center; font-size:14px;")
            row.addWidget(button)

        layout.addLayout(row)

    # ------------------------------------------------------------------

    def set_enabled(self, enabled):

        for button in (self.add, self.delete, self.up, self.down):
            button.setEnabled(enabled)
