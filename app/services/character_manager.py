import json
from pathlib import Path

from models.character import Character


class CharacterManager:

    def __init__(self, json_file):

        self.json_file = Path(json_file)

        self.characters = []

        self.load()

    # -------------------------------------------------

    def load(self):

        self.characters.clear()

        if not self.json_file.exists():
            return

        with open(self.json_file, "r", encoding="utf-8") as f:

            data = json.load(f)

        for item in data:

            self.characters.append(
                Character.from_dict(item)
            )

    # -------------------------------------------------

    def save(self):

        data = []

        for character in self.characters:

            data.append(
                character.to_dict()
            )

        with open(self.json_file, "w", encoding="utf-8") as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )

    # -------------------------------------------------

    def add(self, character):

        self.characters.append(character)

        self.save()

    # -------------------------------------------------

    def remove(self, character_id):

        self.characters = [

            c for c in self.characters

            if c.id != character_id

        ]

        self.save()

    # -------------------------------------------------

    def find(self, character_id):

        for character in self.characters:

            if character.id == character_id:
                return character

        return None

    # -------------------------------------------------

    def names(self):

        return [

            c.name

            for c in self.characters

        ]