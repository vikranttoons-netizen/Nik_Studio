from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)

from widgets.scene_list import SceneList
from widgets.image_preview import ImagePreview
from widgets.prompt_editor import PromptEditor
from widgets.properties_panel import PropertiesPanel
from widgets.bottom_toolbar import BottomToolbar


class WorkspacePage(QWidget):

    def __init__(self):
        super().__init__()

        self.setObjectName("WorkspacePage")

        self.episode_folder = r"D:\NikStudio\Episodes\Bath Time Song"

        main_layout = QVBoxLayout(self)

        # ---------------- Header ----------------

        header = QLabel("🎬 Episode Workspace")
        header.setStyleSheet("""
            font-size:26px;
            font-weight:bold;
            padding:10px;
            color:white;
        """)

        main_layout.addWidget(header)

        # ---------------- Center ----------------

        center_layout = QHBoxLayout()

        # Scene List
        self.scene_list = SceneList()
        center_layout.addWidget(self.scene_list, 1)

        # Image Preview
        self.preview = ImagePreview()
        center_layout.addWidget(self.preview, 3)

        # Right Panel
        right_layout = QVBoxLayout()

        prompt_title = QLabel("📝 Prompt")
        prompt_title.setStyleSheet("""
            font-size:18px;
            font-weight:bold;
        """)

        self.prompt = PromptEditor()

        prop_title = QLabel("⚙ Properties")
        prop_title.setStyleSheet("""
            font-size:18px;
            font-weight:bold;
        """)

        self.properties = PropertiesPanel()

        right_layout.addWidget(prompt_title)
        right_layout.addWidget(self.prompt, 3)

        right_layout.addWidget(prop_title)
        right_layout.addWidget(self.properties, 2)

        center_layout.addLayout(right_layout, 2)

        main_layout.addLayout(center_layout)

        # ---------------- Bottom Toolbar ----------------

        self.toolbar = BottomToolbar()

        main_layout.addWidget(self.toolbar)

        # ---------------- Load Episode ----------------

        try:

            self.scene_list.load_episode(self.episode_folder)

            self.scene_list.currentRowChanged.connect(
                self.scene_changed
            )

            if self.scene_list.count() > 0:
                self.scene_list.setCurrentRow(0)

        except Exception as e:

            print("Workspace initialization:", e)

    def scene_changed(self, row):

        if row < 0:
            return

        if row >= len(self.scene_list.scenes):
            return

        scene = self.scene_list.scenes[row]

        # Update Prompt
        self.prompt.show_scene(scene)

        # Update Properties
        self.properties.show_scene(scene)

        # Update Image Preview
        self.preview.show_scene(
            self.episode_folder,
            scene
        )