from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout
)

from widgets.character_panel import CharacterPanel


class CharactersPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.panel = CharacterPanel()

        layout.addWidget(self.panel)