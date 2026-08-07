from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
)

from widgets.top_toolbar import TopToolbar
from widgets.scene_list import SceneList
from widgets.image_preview import ImagePreview
from widgets.prompt_editor import PromptEditor
from widgets.properties_panel import PropertiesPanel

from managers.project_manager import ProjectManager


class WorkspacePage(QWidget):

    def __init__(self):
        super().__init__()

        self.episode_folder = r"D:\NikStudio\Episodes\Bath Time Song"

        # Main Project Manager
        self.manager = ProjectManager(
            self.episode_folder
        )

        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # =====================================================
        # Top Toolbar
        # =====================================================

        self.toolbar = TopToolbar()
        main_layout.addWidget(self.toolbar)

        # =====================================================
        # Main Workspace
        # =====================================================

        center = QHBoxLayout()

        # Scene List
        self.scene_list = SceneList()
        center.addWidget(self.scene_list, 1)

        # Preview
        self.preview = ImagePreview()
        center.addWidget(self.preview, 3)

        # Right Panel
        right = QVBoxLayout()

        self.prompt = PromptEditor()
        self.properties = PropertiesPanel()

        right.addWidget(self.prompt, 3)
        right.addWidget(self.properties, 2)

        center.addLayout(right, 2)

        main_layout.addLayout(center)

        # =====================================================
        # Load Episode
        # =====================================================

        self.scene_list.load_episode(
            self.episode_folder
        )

        self.scene_list.currentRowChanged.connect(
            self.scene_changed
        )

        self.toolbar.save.clicked.connect(
            self.save_scene
        )

        self.toolbar.generateImage.clicked.connect(
            self.generate_image
        )

        self.toolbar.generateVideo.clicked.connect(
            self.generate_video
        )

        if self.scene_list.count() > 0:
            self.scene_list.setCurrentRow(0)

    # =====================================================

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

    # =====================================================

    def save_scene(self):

        self.prompt.save_scene()

        self.manager.save(
            self.scene_list.scenes
        )

        print("✅ Scene Saved")

    # =====================================================

    def generate_image(self):

        row = self.scene_list.currentRow()

        if row < 0:
            return

        # Save latest prompt into the scene object
        self.prompt.save_scene()

        # Save scenes.json
        self.manager.save(
            self.scene_list.scenes
        )

        # Current Scene
        scene = self.scene_list.scenes[row]

        # Create Image Job
        self.manager.create_image_job(scene)

        print("✅ Image Job Created")

    # =====================================================

    def generate_video(self):

        print("🎥 Generate Video Clicked")