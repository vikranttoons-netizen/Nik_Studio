import json
from pathlib import Path

from models.scene import Scene


class SceneLoader:
    """Reads scenes.json into Scene objects."""

    def __init__(self, episode_folder):

        self.episode_folder = Path(episode_folder)

    @property
    def file(self):
        return self.episode_folder / "scenes.json"

    def load(self):

        if not self.file.exists():
            return []

        # utf-8-sig because some project files were written by tools that
        # add a byte order mark.
        with open(self.file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        return [
            Scene.from_dict(item)
            for item in data.get("scenes", [])
        ]
