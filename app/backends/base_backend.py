from abc import ABC
from pathlib import Path


class BackendError(Exception):
    """Generation was attempted and failed."""


class BackendUnavailable(BackendError):
    """
    The backend cannot run here at all - a missing GPU, a missing python
    package, a model that is not downloaded. The message should tell the
    user in plain language what to do about it.
    """


class BackendDeferred(Exception):
    """
    Not an error. The work was handed off somewhere else (Google Colab,
    RunPod) and the result will arrive later.

    The renderer turns this into a WAITING stage rather than a failure,
    so the episode can be resumed once the results come back.
    """

    def __init__(self, message="", job_folder=None):
        super().__init__(message)
        self.job_folder = job_folder


class BaseBackend(ABC):
    """
    Everything that can actually produce a file for a scene.

    A backend is handed a scene plus an already built prompt and returns
    the path of the file it created, relative to the episode folder.
    Relative paths keep a project portable when it is zipped up and
    opened on another machine.

    Backends declare what they can do in `supports`, so the renderer can
    skip stages a backend has no implementation for instead of crashing.
    """

    name = "base"
    supports = ()

    def __init__(self, episode_folder, settings=None):

        self.episode_folder = Path(episode_folder)
        self.settings = dict(settings or {})

    # ------------------------------------------------------------------

    def is_available(self):
        """Can this backend run right now? Checked before rendering."""
        return True

    def unavailable_reason(self):
        """Plain language explanation shown to the user when it cannot."""
        return ""

    def can(self, stage):
        return stage in self.supports

    def close(self):
        """Release models / GPU memory. Called when rendering finishes."""

    # ------------------------------------------------------------------
    # Generation
    #
    # Each returns a path relative to the episode folder, or raises
    # BackendError / BackendUnavailable / BackendDeferred.
    # ------------------------------------------------------------------

    def generate_image(self, scene, prompt):
        raise BackendUnavailable(
            f"{self.name} cannot generate images."
        )

    def generate_video(self, scene, prompt):
        raise BackendUnavailable(
            f"{self.name} cannot generate videos."
        )

    def generate_voice(self, scene, prompt):
        raise BackendUnavailable(
            f"{self.name} cannot generate voice."
        )

    def generate_music(self, scene, prompt):
        raise BackendUnavailable(
            f"{self.name} cannot generate music."
        )

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------

    def output_path(self, folder, filename):
        """
        Build (absolute path, relative path) for an output file and make
        sure the folder exists.
        """

        relative = f"{folder}/{filename}"

        absolute = self.episode_folder / folder / filename

        absolute.parent.mkdir(parents=True, exist_ok=True)

        return absolute, relative

    def setting(self, key, default=None):
        return self.settings.get(key, default)
