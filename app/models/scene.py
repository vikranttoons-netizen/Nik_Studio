from pipeline.pipeline import ScenePipeline
from pipeline.status import StageStatus


class Scene:
    """
    One scene of an episode.

    Backward compatibility note
    ---------------------------
    The old model was a flat dataclass with `image`, `video` and `status`.
    Those three names still work exactly as before, but they are now
    *views* onto the pipeline instead of separate fields, so there is only
    ever one source of truth:

        scene.image   ->  scene.pipeline.image.output
        scene.video   ->  scene.pipeline.video.output
        scene.status  ->  summary of all five stages

    Old scenes.json files (id/name/prompt/image/video/status) load
    correctly, and saving always writes those keys back out, so a project
    stays readable by older builds.
    """

    def __init__(
        self,
        id=0,
        name="",
        prompt="",
        image="",
        video="",
        status="",
        characters=None,
        pipeline=None,
        metadata=None,
    ):

        self.id = id
        self.name = name
        self.prompt = prompt

        self.characters = list(characters or [])
        self.metadata = dict(metadata or {})

        self.pipeline = pipeline or ScenePipeline()

        # Feed the old flat fields into the pipeline. This only fills
        # stages the pipeline does not already know about.
        self.pipeline.adopt_legacy(
            image=image,
            video=video,
            status=status,
        )

    # ------------------------------------------------------------------
    # Legacy field views
    # ------------------------------------------------------------------

    @property
    def image(self):
        return self.pipeline.image.output

    @image.setter
    def image(self, value):
        self.pipeline.image.output = value or ""

    @property
    def video(self):
        return self.pipeline.video.output

    @video.setter
    def video(self, value):
        self.pipeline.video.output = value or ""

    @property
    def voice(self):
        return self.pipeline.voice.output

    @property
    def music(self):
        return self.pipeline.music.output

    @property
    def final(self):
        return self.pipeline.final.output

    @property
    def status(self):
        """
        One word summarising the whole scene. Derived from the pipeline,
        so it can never disagree with the individual stages.
        """

        stages = list(self.pipeline)

        if any(s.status == StageStatus.FAILED for s in stages):
            return "failed"

        if any(s.status == StageStatus.RUNNING for s in stages):
            return "running"

        if all(s.status == StageStatus.COMPLETED for s in stages):
            return "completed"

        if any(s.status == StageStatus.COMPLETED for s in stages):
            return "in_progress"

        # Queued on a cloud GPU and not back yet.
        if any(s.status == StageStatus.WAITING for s in stages):
            return "waiting"

        return "pending"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data):

        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            prompt=data.get("prompt", "") or "",
            image=data.get("image", "") or "",
            video=data.get("video", "") or "",
            status=data.get("status", "") or "",
            characters=data.get("characters") or [],
            pipeline=(
                ScenePipeline.from_dict(data["pipeline"])
                if data.get("pipeline")
                else None
            ),
            metadata=data.get("metadata") or {},
        )

    def to_dict(self):
        """
        Write both the new and the old shape.

        The legacy keys come first so the file still looks familiar and
        older builds of Nik Studio can keep reading it.
        """

        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "image": self.image,
            "video": self.video,
            "status": self.status,
            "characters": list(self.characters),
            "pipeline": self.pipeline.to_dict(),
            "metadata": dict(self.metadata),
        }

    # ------------------------------------------------------------------

    def __repr__(self):

        return (
            f"Scene(id={self.id!r}, name={self.name!r}, "
            f"status={self.status!r})"
        )
