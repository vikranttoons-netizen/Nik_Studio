import json
import os
from pathlib import Path


class SceneSaver:
    """
    Writes scenes.json.

    Saving goes through a temporary file and then replaces the real one,
    so an interrupted save can never leave a half written scenes.json
    behind and lose the whole episode.
    """

    def __init__(self, episode_folder):
        self.episode_folder = Path(episode_folder)

    @property
    def file(self):
        return self.episode_folder / "scenes.json"

    def save(self, scenes):

        self.episode_folder.mkdir(parents=True, exist_ok=True)

        data = {
            "scenes": [scene.to_dict() for scene in scenes]
        }

        temp = self.file.with_suffix(".json.tmp")

        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        os.replace(temp, self.file)

        return self.file
