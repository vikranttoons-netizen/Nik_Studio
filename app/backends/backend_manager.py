from backends.local_backend import LocalBackend
from backends.colab_backend import ColabBackend


class BackendManager:
    """
    Picks the backend for an episode by name.

    This is the only place that knows which classes exist, so the UI and
    the renderer never mention a specific model or provider.
    """

    BACKENDS = {
        "local": LocalBackend,
        "colab": ColabBackend,
    }

    DEFAULT = "colab"

    # ------------------------------------------------------------------

    @classmethod
    def names(cls):
        """Display names for a backend picker, e.g. ["Local", "Colab"]."""

        return [
            backend.name
            for backend in cls.BACKENDS.values()
        ]

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

    @classmethod
    def from_settings(cls, episode_folder, settings=None):
        """Create the backend named in episode.json."""

        settings = dict(settings or {})

        return cls.create(
            settings.get("backend", cls.DEFAULT),
            episode_folder,
            settings,
        )
