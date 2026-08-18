import os
from pathlib import Path


class Project:
    """
    Where everything lives on disk.

    The root used to be hardcoded to D:/NikStudio, which meant the app
    only worked on one machine and in one folder. It is now worked out
    from the location of this file, so the project can be cloned or moved
    anywhere. Set the NIKSTUDIO_ROOT environment variable to override it.
    """

    def __init__(self, root=None):

        self.root = Path(root).expanduser() if root else self.detect_root()

        self.episodes = self.root / "Episodes"
        self.outputs = self.root / "Outputs"
        self.assets = self.root / "Assets"
        self.models = self.root / "Models"

    # ------------------------------------------------------------------

    @staticmethod
    def detect_root():

        override = os.environ.get("NIKSTUDIO_ROOT")

        if override:
            return Path(override).expanduser()

        # app/core/project.py  ->  app/core  ->  app  ->  project root
        return Path(__file__).resolve().parents[2]

    # ------------------------------------------------------------------
    # Episodes
    # ------------------------------------------------------------------

    def episode_names(self):
        """All episode folder names, sorted."""

        if not self.episodes.exists():
            return []

        return sorted(
            folder.name
            for folder in self.episodes.iterdir()
            if folder.is_dir()
        )

    def episode_path(self, name):
        return self.episodes / name

    def last_episode(self):
        """
        The episode the app should open on start up: the one recorded in
        the app's state file if it still exists, otherwise the first one
        found on disk.
        """

        remembered = self.read_last_episode()

        if remembered and self.episode_path(remembered).exists():
            return self.episode_path(remembered)

        names = self.episode_names()

        return self.episode_path(names[0]) if names else None

    # ------------------------------------------------------------------
    # Remembering the open episode between sessions
    # ------------------------------------------------------------------

    @property
    def state_file(self):
        return Path(__file__).resolve().parents[1] / "data" / "state.json"

    def read_last_episode(self):

        import json

        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, "r", encoding="utf-8-sig") as f:
                return json.load(f).get("last_episode")
        except (OSError, ValueError):
            return None

    def write_last_episode(self, name):

        import json

        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump({"last_episode": name}, f, indent=4)
        except OSError:
            # Remembering the last episode is a convenience, never fatal.
            pass

    # ------------------------------------------------------------------

    @property
    def local_settings_file(self):
        """
        Machine specific settings, kept out of git.

        Things like the Google Drive sync folder and the path to ffmpeg
        differ on every machine. Keeping them in episode.json - which is
        shared - makes every `git pull` collide. They live here instead.
        """

        return self.root / "nikstudio.local.json"

    def local_settings(self):

        import json

        if not self.local_settings_file.exists():
            return {}

        try:
            with open(self.local_settings_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}

        return data if isinstance(data, dict) else {}

    @property
    def characters_file(self):
        return Path(__file__).resolve().parents[1] / "data" / "characters.json"

    # ------------------------------------------------------------------

    def info(self):

        print("=" * 50)
        print("Nik Studio")
        print("=" * 50)

        print("Root      :", self.root)
        print("Episodes  :", self.episodes)
        print("Outputs   :", self.outputs)
        print("Assets    :", self.assets)
        print("Models    :", self.models)
