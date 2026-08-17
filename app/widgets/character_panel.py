from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QPushButton,
    QLabel
)

from core.project import Project
from services.character_manager import CharacterManager


class CharacterPanel(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Characters"))

        self.list = QListWidget()

        layout.addWidget(self.list)

        self.add_button = QPushButton("➕ Add Character")
        self.edit_button = QPushButton("✏ Edit Character")
        self.delete_button = QPushButton("🗑 Delete Character")

        layout.addWidget(self.add_button)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.delete_button)

        self.manager = CharacterManager(
            Project().characters_file
        )

        self.reload()

    # -----------------------------------

    def reload(self):

        self.list.clear()

        for character in self.manager.characters:

            self.list.addItem(character.name)

    # -----------------------------------

    def current_character(self):

        row = self.list.currentRow()

        if row < 0:
            return None

        return self.manager.characters[row]