from PySide6.QtWidgets import QListWidget

from services.scene_loader import SceneLoader


class SceneList(QListWidget):

    def __init__(self):
        super().__init__()

        self.setMinimumWidth(220)

        self.scenes = []

    def load_episode(self, episode_folder):

        self.clear()

        loader = SceneLoader(episode_folder)

        self.scenes = loader.load()

        for scene in self.scenes:

            self.addItem(scene.name)