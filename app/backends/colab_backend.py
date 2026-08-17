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

    @property
    def jobs_folder(self):
        return self.episode_folder / self.JOBS_FOLDER

    @property
    def results_folder(self):
        return self.episode_folder / self.RESULTS_FOLDER

    # ------------------------------------------------------------------
    # Queueing work
    # ------------------------------------------------------------------

    def generate_image(self, scene, prompt):

        if not prompt.strip():
            raise BackendError(
                f"{scene.name} has an empty prompt - nothing to generate."
            )

        # If the result is already sitting in the inbox from an earlier
        # run, take it now instead of queueing the same work twice.
        imported = self.import_result(scene)

        if imported:
            return imported

        self.write_job(scene, prompt)

        raise BackendDeferred(
            f"{scene.name} queued for Colab.",
            job_folder=self.jobs_folder,
        )

    # ------------------------------------------------------------------

    def write_job(self, scene, prompt):

        self.jobs_folder.mkdir(parents=True, exist_ok=True)
        self.results_folder.mkdir(parents=True, exist_ok=True)

        width, height = self._resolution()

        job = {
            "id": f"{scene.name}_image",
            "type": "image",
            "scene": scene.name,
            "prompt": prompt,
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

    # ------------------------------------------------------------------

    def _resolution(self):

        text = str(self.setting("resolution", "1024x1024")).lower()

        try:
            width, height = (int(v) for v in text.split("x")[:2])
        except (ValueError, TypeError):
            width, height = 1024, 1024

        width = max(256, width - width % 8)
        height = max(256, height - height % 8)

        return width, height
