from services.scene_saver import SceneSaver
from services.scene_loader import SceneLoader
from services.episode_loader import EpisodeLoader
from services.job_creator import JobCreator
from services.project_exporter import ProjectExporter
from services.project_importer import ProjectImporter


class ProjectManager:

    def __init__(self, episode_folder):
        self.episode_folder = episode_folder

    # ----------------------------------------

    def load(self):
        return SceneLoader(self.episode_folder).load()

    # ----------------------------------------

    def save(self, scenes):
        SceneSaver(
            self.episode_folder
        ).save(scenes)

    # ----------------------------------------

    def settings(self):
        """Contents of episode.json, or {} when there is not one."""

        try:
            return EpisodeLoader(self.episode_folder).load()
        except (FileNotFoundError, ValueError):
            return {}

    # ----------------------------------------

    def create_image_job(self, scene):
        JobCreator(
            self.episode_folder
        ).create_image_job(scene)

    # ----------------------------------------

    def export(self):
        return ProjectExporter(
            self.episode_folder
        ).export()

    # ----------------------------------------

    def import_results(self, zip_file):
        ProjectImporter(
            self.episode_folder
        ).import_zip(zip_file)
