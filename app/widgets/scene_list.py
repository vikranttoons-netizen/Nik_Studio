from PySide6.QtWidgets import QListWidget

from services.scene_loader import SceneLoader


class SceneList(QListWidget):
    """
    The scene list down the left of the workspace.

    Each row carries the scene's image status, so it is obvious at a
    glance which scenes still need rendering.
    """

    ICONS = {
        "completed": "🟢",
        "running": "🟡",
        "waiting": "⏳",
        "failed": "🔴",
    }

    def __init__(self):
        super().__init__()

        self.setMinimumWidth(220)

        self.scenes = []

    # ------------------------------------------------------------------

    def load_episode(self, episode_folder):

        self.scenes = []

        if episode_folder:
            self.scenes = SceneLoader(episode_folder).load()

        self.refresh()

        return self.scenes

    # ------------------------------------------------------------------

    def refresh(self):
        """
        Redraw the rows from the current scene objects, keeping the
        selection. Called after a render so the list reflects reality.
        """

        selected = self.currentRow()

        self.blockSignals(True)

        self.clear()

        for scene in self.scenes:

            icon = self.ICONS.get(
                scene.pipeline.image.status.value,
                "⚪",
            )

            self.addItem(f"{icon}  {scene.name}")

        self.blockSignals(False)

        if 0 <= selected < self.count():
            self.setCurrentRow(selected)

    # ------------------------------------------------------------------

    def current_scene(self):

        row = self.currentRow()

        if row < 0 or row >= len(self.scenes):
            return None

        return self.scenes[row]
