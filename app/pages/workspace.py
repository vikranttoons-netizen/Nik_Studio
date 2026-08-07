from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)

from widgets.scene_list import SceneList
from widgets.image_preview import ImagePreview
from widgets.prompt_editor import PromptEditor
from widgets.properties_panel import PropertiesPanel
from widgets.bottom_toolbar import BottomToolbar

from services.scene_saver import SceneSaver


class WorkspacePage(QWidget):

    def __init__(self):
        super().__init__()

        self.episode_folder = r"D:\NikStudio\Episodes\Bath Time Song"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        header = QLabel("🎬 Episode Workspace")
        header.setStyleSheet("""
            font-size:28px;
            font-weight:bold;
        """)

        main_layout.addWidget(header)

        center = QHBoxLayout()
        center.setSpacing(12)

        self.scene_list = SceneList()
        center.addWidget(self.scene_list, 1)

        self.preview = ImagePreview()
        center.addWidget(self.preview, 3)

        right = QVBoxLayout()

        lbl1 = QLabel("📝 Prompt")
        lbl1.setStyleSheet("font-size:16px;font-weight:bold;")

        self.prompt = PromptEditor()

        lbl2 = QLabel("⚙ Properties")
        lbl2.setStyleSheet("font-size:16px;font-weight:bold;")

        self.properties = PropertiesPanel()

        right.addWidget(lbl1)
        right.addWidget(self.prompt, 3)

        right.addWidget(lbl2)
        right.addWidget(self.properties, 2)

        center.addLayout(right, 2)

        main_layout.addLayout(center, 1)

        self.toolbar = BottomToolbar()

        main_layout.addWidget(self.toolbar, 0)

        self.scene_list.load_episode(self.episode_folder)

        self.scene_list.currentRowChanged.connect(
            self.scene_changed
        )

        self.toolbar.save.clicked.connect(
            self.save_scene
        )

        if self.scene_list.count():
            self.scene_list.setCurrentRow(0)

    def scene_changed(self, row):

        if row < 0:
            return

        scene = self.scene_list.scenes[row]

        self.prompt.show_scene(scene)

        self.properties.show_scene(scene)

        self.preview.show_scene(
            self.episode_folder,
            scene
        )

    def save_scene(self):

        row = self.scene_list.currentRow()

        if row < 0:
            return

        self.prompt.save_scene()

        SceneSaver(self.episode_folder).save(
            self.scene_list.scenes
        )

        QMessageBox.information(
            self,
            "Saved",
            "Scene saved successfully!"
        )