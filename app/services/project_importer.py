from pathlib import Path
from zipfile import ZipFile


class ProjectImporter:

    def __init__(self, episode_folder):
        self.episode_folder = Path(episode_folder)

    def import_zip(self, zip_path):
        zip_path = Path(zip_path)

        if not zip_path.exists():
            raise FileNotFoundError(f"ZIP file not found: {zip_path}")

        with ZipFile(zip_path, "r") as zipf:
            zipf.extractall(self.episode_folder)

        print("✅ Project Imported Successfully")