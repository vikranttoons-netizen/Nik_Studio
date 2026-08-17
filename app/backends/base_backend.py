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

    # Image sizes that suit an SDXL class model, per aspect ratio.
    #
    # These are NOT the video sizes. A diffusion model is trained at about
    # a megapixel and gets slow, hungry and badly composed if pushed to
    # 1920x1080, so images are generated near 1024 and the video stage
    # scales them up to full HD.
    IMAGE_SIZES = {
        "16:9": (1344, 768),
        "9:16": (768, 1344),
        "1:1": (1024, 1024),
        "4:3": (1152, 896),
        "3:4": (896, 1152),
    }

    DEFAULT_IMAGE_SIZE = (1024, 1024)

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

    # ------------------------------------------------------------------

    def image_size(self):
        """
        The size to generate images at, as (width, height).

        Taken from "image_size" in episode.json when set, otherwise chosen
        to match the episode's aspect ratio. Generating at the video's
        aspect means the video stage crops almost nothing away.

        "resolution" is deliberately not used here - that is the size of
        the finished video, which is far larger than any diffusion model
        should be asked for.
        """

        explicit = self.setting("image_size")

        if explicit:

            size = self.parse_size(explicit)

            if size:
                return size

        aspect = str(self.setting("aspect", "16:9")).strip()

        if aspect in self.IMAGE_SIZES:
            return self.IMAGE_SIZES[aspect]

        # An aspect written as "1344x768" is accepted too.
        size = self.parse_size(aspect)

        return size or self.DEFAULT_IMAGE_SIZE

    @staticmethod
    def parse_size(value):
        """
        Turn "1344x768" into (1344, 768), rounded down to a multiple of 8
        because diffusion models require it. Returns None if unreadable.
        """

        try:
            width, height = (
                int(v)
                for v in str(value).lower().split("x")[:2]
            )
        except (ValueError, TypeError):
            return None

        if width <= 0 or height <= 0:
            return None

        return (
            max(256, width - width % 8),
            max(256, height - height % 8),
        )
