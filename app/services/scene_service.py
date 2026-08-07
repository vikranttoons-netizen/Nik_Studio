import json
from pathlib import Path


class SceneSaver:

    def __init__(self, episode_folder):
        self.episode_folder = Path(episode_folder)

    def save(self, scenes):

        data = {
            "scenes": []
        }

        for scene in scenes:

            data["scenes"].append({
                "id": scene.id,
                "name": scene.name,
                "prompt": scene.prompt,
                "image": scene.image,
                "video": scene.video,
                "status": scene.status
            })

        file = self.episode_folder / "scenes.json"

        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)