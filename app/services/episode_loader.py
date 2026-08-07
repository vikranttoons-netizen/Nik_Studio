import json
from pathlib import Path


class EpisodeLoader:

    def __init__(self, episode_path):

        self.episode_path = Path(episode_path)

    def load(self):

        config = self.episode_path / "episode.json"

        if not config.exists():
            raise FileNotFoundError(config)

        with open(config, "r", encoding="utf-8-sig") as f:
            return json.load(f)