from backends.local_backend import LocalBackend
from backends.colab_backend import ColabBackend
from backends.ffmpeg_backend import FFmpegBackend


class BackendManager:
    """
    Picks the backend for a job.

    This is the only place that knows which classes exist, so the UI and
    the renderer never mention a specific model or provider.

    Different stages need different backends: images come from a GPU
    (local or Colab), video comes from FFmpeg. An episode.json can name
    one per stage:

        "backend": "Colab",
        "backends": { "video": "FFmpeg" }

    Only "backend" is required - it sets the image backend, and every
    other stage falls back to whichever backend can do that stage.
    """

    BACKENDS = {
        "local": LocalBackend,
        "colab": ColabBackend,
        "ffmpeg": FFmpegBackend,
    }

    DEFAULT = "colab"

    # Used when a stage has no backend named for it.
    STAGE_DEFAULTS = {
        "image": "colab",
        "video": "ffmpeg",
    }

    # ------------------------------------------------------------------

    @classmethod
    def names(cls):
        """Display names for a backend picker, e.g. ["Local", "Colab"]."""

        return [backend.name for backend in cls.BACKENDS.values()]

    @classmethod
    def create(cls, name, episode_folder, settings=None):

        key = str(name or cls.DEFAULT).strip().lower()

        backend_class = cls.BACKENDS.get(key)

        if backend_class is None:
            raise ValueError(
                f"Unknown backend '{name}'. "
                f"Available: {', '.join(cls.names())}"
            )

        return backend_class(episode_folder, settings)

    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, episode_folder, settings=None):
        """The image backend named in episode.json."""

        settings = dict(settings or {})

        return cls.create(
            settings.get("backend", cls.DEFAULT),
            episode_folder,
            settings,
        )

    # ------------------------------------------------------------------

    @classmethod
    def for_stage(cls, stage, episode_folder, settings=None):
        """
        The backend that renders `stage`.

        Looked up in order: the "backends" map in episode.json, then
        "backend" for the image stage, then the built in default for that
        stage.
        """

        settings = dict(settings or {})

        per_stage = settings.get("backends") or {}

        name = per_stage.get(stage)

        if not name and stage == "image":
            name = settings.get("backend")

        if not name:
            name = cls.STAGE_DEFAULTS.get(stage)

        if not name:
            raise ValueError(
                f"No backend is configured for the '{stage}' stage."
            )

        return cls.create(name, episode_folder, settings)
