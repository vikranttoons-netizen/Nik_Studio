import json
from pathlib import Path


class JobCreator:

    def __init__(self, episode_folder):
        self.episode_folder = Path(episode_folder)

    def create_image_job(self, scene):

        # Scene folder
        scene_folder = self.episode_folder / scene.name
        scene_folder.mkdir(parents=True, exist_ok=True)

        # prompt.txt
        prompt_file = scene_folder / "prompt.txt"

        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(scene.prompt)

        # settings.json
        settings = {
            "model": "sdxl-turbo",
            "steps": 4,
            "guidance": 2.0,
            "width": 1024,
            "height": 1024,
            "seed": -1
        }

        with open(scene_folder / "settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)

        # status.json
        status = {
            "status": "waiting"
        }

        with open(scene_folder / "status.json", "w", encoding="utf-8") as f:
            json.dump(status, f, indent=4)

        print(f"✅ Image Job Created : {scene.name}")