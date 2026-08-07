from services.scene_saver import SceneSaver
from services.job_creator import JobCreator
from services.project_exporter import ProjectExporter
from services.project_importer import ProjectImporter


class ProjectManager:

    def __init__(self, episode_folder):
        self.episode_folder = episode_folder

    # ----------------------------------------

    def save(self, scenes):
        SceneSaver(
            self.episode_folder
        ).save(scenes)

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