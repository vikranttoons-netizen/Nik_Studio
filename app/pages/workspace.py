from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)

from widgets.top_toolbar import TopToolbar
from widgets.scene_panel import ScenePanel
from widgets.image_preview import ImagePreview
from widgets.prompt_editor import PromptEditor
from widgets.properties_panel import PropertiesPanel
from widgets.render_status import RenderStatus

from managers.project_manager import ProjectManager

from services.background_worker import RenderWorker
from services.scene_editor import SceneEditor
from services.worker_manager import RenderTask

from core.project import Project


class WorkspacePage(QWidget):
    """
    The workspace: pick an episode, edit prompts, press 🚀 Render Episode.

    The page never touches a model or a backend. It hands the scenes to
    the renderer on a background thread and shows what comes back.
    """

    def __init__(self):
        super().__init__()

        # Which episode to open comes from the project folder and is
        # remembered between sessions, instead of a hardcoded path.
        self.project = Project()

        self.episode_folder = self.project.last_episode()

        self.manager = ProjectManager(self.episode_folder)

        self.task = None

        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # =====================================================
        # Top Toolbar
        # =====================================================

        self.toolbar = TopToolbar()
        main_layout.addWidget(self.toolbar)

        self.status = RenderStatus()
        main_layout.addWidget(self.status)

        # =====================================================
        # Main Workspace
        # =====================================================

        center = QHBoxLayout()

        # Scene list, with the buttons that add / remove / reorder scenes
        self.scene_panel = ScenePanel()
        self.scene_list = self.scene_panel.list

        center.addWidget(self.scene_panel, 1)

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
        # Signals
        # =====================================================

        self.scene_list.currentRowChanged.connect(self.scene_changed)

        self.toolbar.episodes.currentTextChanged.connect(
            self.episode_changed
        )

        self.toolbar.save.clicked.connect(self.save_scene)

        self.toolbar.renderScene.clicked.connect(self.render_scene)

        self.toolbar.renderEpisode.clicked.connect(self.render_episode)

        self.toolbar.importResults.clicked.connect(self.import_results)

        self.toolbar.export.clicked.connect(self.export_episode)

        self.toolbar.cancel.clicked.connect(self.cancel_render)

        self.scene_panel.add.clicked.connect(self.add_scene)
        self.scene_panel.delete.clicked.connect(self.delete_scene)
        self.scene_panel.up.clicked.connect(self.move_scene_up)
        self.scene_panel.down.clicked.connect(self.move_scene_down)

        # =====================================================
        # Load
        # =====================================================

        self.load_episode_list()

    # =====================================================
    # Episodes
    # =====================================================

    def load_episode_list(self):
        """Fill the episode picker and open the remembered episode."""

        names = self.project.episode_names()

        combo = self.toolbar.episodes

        combo.blockSignals(True)
        combo.clear()
        combo.addItems(names)

        if self.episode_folder is not None:

            index = combo.findText(self.episode_folder.name)

            if index >= 0:
                combo.setCurrentIndex(index)

        combo.blockSignals(False)

        if not names:

            self.toolbar.title.setText("🎬 No episodes found")

            self.properties.clear()

            self.preview.setText(
                "No episodes found in\n"
                f"{self.project.episodes}\n\n"
                "Create a folder there with a scenes.json to get started."
            )

            return

        self.open_episode(combo.currentText())

    # ------------------------------------------------------------------

    def episode_changed(self, name):

        if name:
            self.open_episode(name)

    # ------------------------------------------------------------------

    def open_episode(self, name):

        self.episode_folder = self.project.episode_path(name)

        self.manager = ProjectManager(self.episode_folder)

        self.project.write_last_episode(name)

        settings = self.manager.settings()

        backend = settings.get("backend", "Colab")

        self.toolbar.title.setText(f"🎬 {name}   ·   {backend}")

        # Hover to see exactly which folder on disk this is.
        self.toolbar.episodes.setToolTip(str(self.episode_folder))
        self.toolbar.title.setToolTip(str(self.episode_folder))

        self.load_scenes()

    # ------------------------------------------------------------------

    def load_scenes(self):

        scenes = self.scene_list.load_episode(self.episode_folder)

        if not scenes:

            self.prompt.show_scene(None)
            self.properties.clear()

            self.preview.setText(
                f"No scenes in {self.episode_folder.name}.\n\n"
                "Add a scenes.json to this episode folder."
            )

            return

        self.scene_list.setCurrentRow(0)

        # setCurrentRow only fires when the row actually changes, so the
        # first scene is shown explicitly.
        self.scene_changed(0)

    # =====================================================
    # Scene selection
    # =====================================================

    def scene_changed(self, row):

        scene = self.scene_list.current_scene()

        if scene is None:
            return

        self.prompt.show_scene(scene)
        self.properties.show_scene(scene)

        self.preview.show_scene(self.episode_folder, scene)

    # ------------------------------------------------------------------

    def refresh_current_scene(self):
        """Redraw everything from the scene objects after a render."""

        self.scene_list.refresh()

        scene = self.scene_list.current_scene()

        if scene is None:
            return

        self.properties.show_scene(scene)

        self.preview.show_scene(self.episode_folder, scene)

    # =====================================================
    # Editing the scene list
    # =====================================================

    def editor(self):
        return SceneEditor(self.scene_list.scenes)

    # ------------------------------------------------------------------

    def apply_scene_edit(self, row, message):
        """
        Redraw and save after the scene list changed, then select `row`.
        """

        self.scene_list.refresh()

        if row < 0:
            self.prompt.show_scene(None)
            self.properties.clear()
            self.preview.setText("No scenes — press ➕ to add one")
        else:
            self.scene_list.setCurrentRow(row)
            self.scene_changed(row)

        self.manager.save(self.scene_list.scenes)

        self.status.begin(message)
        self.status.end(message)

    # ------------------------------------------------------------------

    def add_scene(self):

        if not self.has_episode():
            return

        # Keep whatever is being typed before the list changes under it.
        self.prompt.save_scene()

        row = self.editor().add(after=self.scene_list.currentRow())

        self.apply_scene_edit(
            row,
            f"➕ Added {self.scene_list.scenes[row].name}",
        )

    # ------------------------------------------------------------------

    def delete_scene(self):

        scene = self.scene_list.current_scene()

        if scene is None:
            self.warn("Select a scene to delete.")
            return

        answer = QMessageBox.question(
            self,
            "Nik Studio",
            f"Remove {scene.name} from this episode?\n\n"
            "Any image or clip already made for it stays on disk.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        row = self.editor().delete(self.scene_list.currentRow())

        self.apply_scene_edit(row, f"🗑 Removed {scene.name}")

    # ------------------------------------------------------------------

    def move_scene_up(self):
        self.move_scene(-1)

    def move_scene_down(self):
        self.move_scene(1)

    def move_scene(self, offset):

        if self.scene_list.current_scene() is None:
            self.warn("Select a scene to move.")
            return

        self.prompt.save_scene()

        start = self.scene_list.currentRow()

        row = self.editor().move(start, offset)

        if row == start:
            # Already at the top or the bottom.
            return

        self.apply_scene_edit(
            row,
            f"↕ Moved {self.scene_list.scenes[row].name} "
            f"to position {row + 1}",
        )

    # =====================================================
    # Saving
    # =====================================================

    def save_scene(self):

        if not self.has_episode():
            return

        # Move whatever is in the editor into the scene object first.
        self.prompt.save_scene()

        self.manager.save(self.scene_list.scenes)

        self.refresh_current_scene()

        self.status.begin("💾 Saved.")
        self.status.end("💾 Saved.")

    # =====================================================
    # Rendering
    # =====================================================

    def render_scene(self):
        """Render the selected scene, even if it is already done."""

        scene = self.scene_list.current_scene()

        if scene is None:
            self.warn("Select a scene first.")
            return

        self.start_render(
            scenes=[scene],
            force=True,
            label=f"Rendering {scene.name}",
            # One scene is usually re-rendered to check it; rebuilding the
            # whole episode video every time would be slow.
            compose=False,
        )

    # ------------------------------------------------------------------

    def render_episode(self):
        """
        Render every scene that still needs it.

        Scenes that are already done are skipped, so pressing this again
        after an interrupted render picks up where it left off.
        """

        if not self.scene_list.scenes:
            self.warn("This episode has no scenes yet.")
            return

        self.start_render(
            scenes=self.scene_list.scenes,
            force=False,
            label="Rendering episode",
        )

    # ------------------------------------------------------------------

    def import_results(self):
        """Pull in finished images that came back from the cloud GPU."""

        if not self.scene_list.scenes:
            self.warn("This episode has no scenes yet.")
            return

        self.start_render(
            scenes=self.scene_list.scenes,
            force=False,
            label="Importing results",
            job=RenderWorker.COLLECT,
        )

    # ------------------------------------------------------------------

    def start_render(
        self,
        scenes,
        force,
        label,
        job=RenderWorker.RENDER,
        compose=True,
    ):

        if not self.has_episode():
            return

        if self.task is not None and self.task.is_running:
            self.warn("A render is already running.")
            return

        # Never render a stale prompt.
        self.prompt.save_scene()
        self.manager.save(self.scene_list.scenes)

        self.toolbar.set_rendering(True)
        self.scene_panel.set_enabled(False)
        self.prompt.setReadOnly(True)

        self.status.begin(f"{label}…")

        self.task = RenderTask(
            self.episode_folder,
            scenes,
            stages=("image", "video"),
            force=force,
            job=job,
            compose=compose,
            # Render Scene renders one scene but must still save them all.
            all_scenes=self.scene_list.scenes,
            parent=self,
        )

        self.task.progress.connect(self.status.update_progress)
        self.task.finished.connect(self.render_finished)

        self.task.start()

    # ------------------------------------------------------------------

    def cancel_render(self):

        if self.task is not None and self.task.is_running:

            self.task.cancel()

            self.status.message.setText(
                "Stopping after the current scene…"
            )

    # ------------------------------------------------------------------

    def render_finished(self, result):

        self.toolbar.set_rendering(False)
        self.scene_panel.set_enabled(True)
        self.prompt.setReadOnly(False)

        self.status.end(result.message or "Done.")

        # The renderer wrote scenes.json and updated the scene objects
        # in place, so the UI just has to redraw.
        self.refresh_current_scene()

        self.task = None

        if result.errors:
            self.show_result("Render finished with problems", result)

        elif result.waiting:
            self.show_result("Jobs sent to the cloud GPU", result)

    # =====================================================
    # Export
    # =====================================================

    def export_episode(self):

        if not self.has_episode():
            return

        self.prompt.save_scene()
        self.manager.save(self.scene_list.scenes)

        zip_file = self.manager.export()

        self.status.begin("Exported.")
        self.status.end(f"📤 Exported : {zip_file}")

    # =====================================================
    # Shutdown
    # =====================================================

    def shutdown(self):
        """
        Stop a running render before the window closes.

        Letting Qt destroy a QThread while it is still running crashes the
        app, so the render is asked to stop and then waited for.
        """

        if self.task is None or not self.task.is_running:
            return

        self.task.cancel()

        self.task.thread.quit()
        self.task.thread.wait(30000)

    # =====================================================
    # Helpers
    # =====================================================

    def has_episode(self):

        if self.episode_folder is None:
            self.warn(
                "No episode is open.\n\n"
                f"Add an episode folder inside:\n{self.project.episodes}"
            )
            return False

        return True

    def warn(self, message):

        QMessageBox.information(self, "Nik Studio", message)

    def show_result(self, title, result):

        box = QMessageBox(self)

        box.setWindowTitle("Nik Studio")
        box.setText(title)
        box.setDetailedText(result.summary())
        box.setIcon(
            QMessageBox.Warning if result.errors else QMessageBox.Information
        )

        box.exec()
