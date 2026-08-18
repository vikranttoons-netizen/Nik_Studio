import json
from pathlib import Path


class EpisodeLoader:
    """
    Reads an episode's settings.

    What comes back is episode.json with the machine's own settings
    layered on top. Machine specific values - the Google Drive sync
    folder, a path to ffmpeg - belong in nikstudio.local.json at the
    project root, which is not in git, so pulling an update never
    collides with them.
    """

    def __init__(self, episode_path):

        self.episode_path = Path(episode_path)

    def load(self, local=True):

        config = self.episode_path / "episode.json"

        if not config.exists():
            raise FileNotFoundError(config)

        with open(config, "r", encoding="utf-8-sig") as f:
            settings = json.load(f)

        if not local:
            return settings

        return {**settings, **self.local_settings()}

    @staticmethod
    def local_settings():

        # Imported here to keep this module usable on its own.
        from core.project import Project

        return Project().local_settings()
