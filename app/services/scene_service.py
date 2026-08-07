from pathlib import Path


class SceneService:

    def __init__(self, episode_path):
        self.episode_path = Path(episode_path)

    def get_images(self):

        folder = self.episode_path / "Images"

        if not folder.exists():
            return []

        return sorted(folder.glob("*.png"))

    def get_videos(self):

        folder = self.episode_path / "Videos"

        if not folder.exists():
            return []

        return sorted(folder.glob("*.mp4"))