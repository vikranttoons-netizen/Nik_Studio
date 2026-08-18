from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QSizePolicy,
)


class TopToolbar(QWidget):
    """
    The workspace toolbar.

    The old toolbar had one button per AI step (Generate / Video / Voice /
    Music). The creator should not have to think in those terms, so it now
    has the two buttons that matter - render this scene, or render the
    whole episode - plus the episode picker that replaced the hardcoded
    episode path.

    Buttons for stages that have no working backend yet are deliberately
    absent rather than present and dead.
    """

    def __init__(self):
        super().__init__()

        self.setFixedHeight(80)

        layout = QHBoxLayout(self)

        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # -------------------------------------------------- episode picker

        left = QVBoxLayout()
        left.setSpacing(2)

        self.title = QLabel("🎬 Episode Workspace")

        self.title.setStyleSheet("""
            font-size:20px;
            font-weight:bold;
        """)

        self.episodes = QComboBox()
        self.episodes.setMinimumWidth(260)

        left.addWidget(self.title)
        left.addWidget(self.episodes)

        left_holder = QWidget()
        left_holder.setLayout(left)
        left_holder.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        layout.addWidget(left_holder)

        # -------------------------------------------------------- buttons

        self.save = QPushButton("💾 Save")

        self.renderScene = QPushButton("🎬 Render Scene")

        self.renderEpisode = QPushButton("🚀 RENDER EPISODE")

        # Render Episode deliberately skips finished work. This is for
        # when the settings changed and everything should be made again.
        self.redoEpisode = QPushButton("↻")
        self.redoEpisode.setToolTip(
            "Render every scene again, including the ones already done"
        )

        self.importResults = QPushButton("📥 Import Results")

        self.export = QPushButton("📤 Export")

        self.cancel = QPushButton("✋ Stop")
        self.cancel.setVisible(False)

        for button in self.buttons():
            button.setMinimumHeight(46)
            button.setMinimumWidth(120)

        # A deliberate re-render is not the main action; keep it small.
        self.redoEpisode.setMinimumWidth(46)
        self.redoEpisode.setStyleSheet("text-align:center; font-size:16px;")

        # The main action gets to look like the main action.
        self.renderEpisode.setMinimumWidth(190)
        self.renderEpisode.setStyleSheet("""
            QPushButton {
                background:#0E639C;
                font-size:15px;
                font-weight:bold;
                text-align:center;
                border-radius:4px;
            }
            QPushButton:hover {
                background:#1177BB;
            }
            QPushButton:disabled {
                background:#333;
                color:#888;
            }
        """)

        for button in self.buttons():
            layout.addWidget(button)

    # ------------------------------------------------------------------

    def buttons(self):

        return [
            self.save,
            self.renderScene,
            self.renderEpisode,
            self.redoEpisode,
            self.importResults,
            self.export,
            self.cancel,
        ]

    # ------------------------------------------------------------------

    def set_rendering(self, rendering):
        """
        While a render runs, everything that could change the project is
        disabled - otherwise an edit could be overwritten when the
        renderer saves scenes.json.
        """

        for button in self.buttons():
            button.setEnabled(not rendering)

        self.episodes.setEnabled(not rendering)

        self.cancel.setVisible(rendering)
        self.cancel.setEnabled(rendering)
