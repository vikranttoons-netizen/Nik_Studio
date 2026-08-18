import json
import shutil
from datetime import datetime
from pathlib import Path

from backends.base_backend import (
    BaseBackend,
    BackendDeferred,
    BackendError,
)


class ColabBackend(BaseBackend):
    """
    Generates images on a free Colab GPU.

    Colab cannot be called like a function - it runs somewhere else, on
    its own schedule. So rendering here is a two step conversation
    through a shared folder (Google Drive):

        Nik Studio writes   Jobs/Scene01.json
        Colab picks it up, generates, writes   Results/Scene01.png
        Nik Studio imports it into             Images/Scene01.png

    generate_image() therefore does not return an image. It queues the
    job and raises BackendDeferred, which the renderer records as a
    WAITING stage. Calling collect_results() later finishes the job.

    The Colab side of this conversation is colab/nik_studio_worker.py.
    """

    name = "Colab"
    supports = ("image",)

    JOBS_FOLDER = "Jobs"
    RESULTS_FOLDER = "Results"

    # ------------------------------------------------------------------
    # Where the two sides meet
    # ------------------------------------------------------------------

    @property
    def exchange_folder(self):
        """
        The folder Nik Studio and Colab both see.

        By default that is the episode folder itself, which means the
        whole episode has to live in Google Drive.

        Set "sync_folder" in episode.json to keep the project on a local
        disk and share only the handful of files Colab actually needs:

            "sync_folder": "G:\\My Drive\\NikStudio\\Exchange"

        Only job files go up and finished images come down. Generated
        images, clips and the final video all stay in the episode folder
        on the local disk.
        """

        folder = self.setting("sync_folder")

        if not folder:
            return self.episode_folder

        # Keyed by episode name so several episodes can share one folder.
        return Path(folder).expanduser() / self.episode_folder.name

    @property
    def jobs_folder(self):
        return self.exchange_folder / self.JOBS_FOLDER

    @property
    def results_folder(self):
        return self.exchange_folder / self.RESULTS_FOLDER

    # ------------------------------------------------------------------
    # Queueing work
    # ------------------------------------------------------------------

    def generate_image(self, scene, prompt, negative="",
                       references=None):

        if not prompt.strip():
            raise BackendError(
                f"{scene.name} has an empty prompt - nothing to generate."
            )

        # If the result is already sitting in the inbox from an earlier
        # run, take it now instead of queueing the same work twice.
        imported = self.import_result(scene)

        if imported:
            return imported

        self.write_job(scene, prompt, negative, references)

        raise BackendDeferred(
            f"{scene.name} queued for Colab.",
            job_folder=self.jobs_folder,
        )

    # ------------------------------------------------------------------

    def write_job(self, scene, prompt, negative="",
                  references=None):

        self.jobs_folder.mkdir(parents=True, exist_ok=True)
        self.results_folder.mkdir(parents=True, exist_ok=True)

        width, height = self.image_size()

        job = {
            "id": f"{scene.name}_image",
            "type": "image",
            "scene": scene.name,
            "prompt": prompt,
            "negative_prompt": negative,
            "reference_images": self.copy_references(references),
            "reference_strength": float(
                self.setting("reference_strength", 0.6)
            ),
            "model": self.setting("model", "stabilityai/sdxl-turbo"),
            "steps": int(self.setting("steps", 4)),
            "guidance": float(self.setting("guidance", 0.0)),
            "width": width,
            "height": height,
            "seed": int(self.setting("seed", -1)),
            "output": f"{self.RESULTS_FOLDER}/{scene.name}.png",
            "status": "waiting",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        job_file = self.jobs_folder / f"{scene.name}.json"

        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(job, f, indent=4, ensure_ascii=False)

        return job_file

    # ------------------------------------------------------------------

    REFERENCE_FOLDER = "Reference"

    def copy_references(self, references):
        """
        Put the character reference pictures where Colab can reach them.

        They live on the local disk, so with a sync_folder in use they
        have to be copied across. They are small and change rarely, so a
        copy is only made when the file is not already there with the same
        size.

        Returns paths relative to the shared folder, for the job file.
        """

        if not references:
            return []

        folder = self.exchange_folder / self.REFERENCE_FOLDER

        folder.mkdir(parents=True, exist_ok=True)

        names = []

        for source in references:

            source = Path(source)

            if not source.exists():
                continue

            target = folder / source.name

            if (
                not target.exists()
                or target.stat().st_size != source.stat().st_size
            ):
                shutil.copy2(source, target)

            names.append(f"{self.REFERENCE_FOLDER}/{source.name}")

        return names

    # ------------------------------------------------------------------
    # Collecting finished work
    # ------------------------------------------------------------------

    def result_file(self, scene):
        """The finished image Colab left for this scene, if any."""

        for suffix in (".png", ".jpg", ".jpeg", ".webp"):

            candidate = self.results_folder / f"{scene.name}{suffix}"

            if candidate.exists() and candidate.stat().st_size > 0:
                return candidate

        return None

    def import_result(self, scene):
        """
        Move a finished image from the Results inbox into Images/.
        Returns the new relative path, or None if nothing is waiting.
        """

        result = self.result_file(scene)

        if result is None:
            return None

        absolute, relative = self.output_path(
            "Images",
            f"{scene.name}{result.suffix}",
        )

        shutil.move(str(result), str(absolute))

        # The job is done, so retire its request file.
        job_file = self.jobs_folder / f"{scene.name}.json"

        if job_file.exists():
            job_file.unlink()

        return relative

    def collect_results(self, scenes):
        """
        Import every finished image that has come back from Colab.

        Returns {scene_name: relative_path} for the scenes that were
        updated, so the renderer can mark those stages completed.
        """

        collected = {}

        for scene in scenes:

            relative = self.import_result(scene)

            if relative:
                collected[scene.name] = relative

        return collected

    def pending_jobs(self):
        """Job files still waiting for Colab to pick them up."""

        if not self.jobs_folder.exists():
            return []

        return sorted(self.jobs_folder.glob("*.json"))

