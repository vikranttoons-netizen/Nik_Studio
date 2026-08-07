from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json


class ProjectExporter:

    def __init__(self, episode_folder):
        self.episode_folder = Path(episode_folder)

    def export(self):

        zip_file = self.episode_folder / "Episode.zip"

        if zip_file.exists():
            zip_file.unlink()

        manifest = {
            "episode": self.episode_folder.name,
            "version": "1.0"
        }

        manifest_path = self.episode_folder / "manifest.json"

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)

        with ZipFile(zip_file, "w", ZIP_DEFLATED) as zipf:

            for file in self.episode_folder.rglob("*"):

                if file == zip_file:
                    continue

                zipf.write(
                    file,
                    file.relative_to(self.episode_folder)
                )

        print(f"✅ Exported : {zip_file}")

        return zip_file