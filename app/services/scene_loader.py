import json
from pathlib import Path

from models.scene import Scene


class SceneLoader:

    def __init__(self, episode_folder):

        self.episode_folder = Path(episode_folder)

    def load(self):

        file = self.episode_folder / "scenes.json"

        with open(file, "r", encoding="utf-8-sig") as f:

            data = json.load(f)

        scenes = []

        for s in data["scenes"]:

            scenes.append(
                Scene(
                    id=s["id"],
                    name=s["name"],
                    prompt=s["prompt"],
                    image=s["image"],
                    video=s["video"],
                    status=s["status"],
                )
            )

        return scenes