from pipeline.stage import Stage
from pipeline.status import StageStatus


# The production stages, in the order they run.
STAGES = ("image", "video", "voice", "music", "final")


class ScenePipeline:
    """
    The five production stages of one scene.

    Access a stage either as an attribute or by name:

        scene.pipeline.image
        scene.pipeline["image"]
    """

    def __init__(self, stages=None):

        self.stages = {}

        for name in STAGES:

            if stages and name in stages:
                self.stages[name] = stages[name]
            else:
                self.stages[name] = Stage(name=name)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def __getitem__(self, name):
        return self.stages[name]

    def __iter__(self):
        """Iterate stages in production order."""
        for name in STAGES:
            yield self.stages[name]

    @property
    def image(self):
        return self.stages["image"]

    @property
    def video(self):
        return self.stages["video"]

    @property
    def voice(self):
        return self.stages["voice"]

    @property
    def music(self):
        return self.stages["music"]

    @property
    def final(self):
        return self.stages["final"]

    # ------------------------------------------------------------------
    # Queries used by the renderer and the UI
    # ------------------------------------------------------------------

    def is_completed(self, name):
        return self.stages[name].is_completed

    def failed_stages(self):
        return [s for s in self if s.is_failed]

    def completed_stages(self):
        return [s for s in self if s.is_completed]

    def progress(self):
        """Return (completed, total) counting only the stages we render."""
        return (len(self.completed_stages()), len(STAGES))

    def reset(self, name=None):
        """Reset one stage, or all of them."""

        if name:
            self.stages[name].reset()
            return

        for stage in self:
            stage.reset()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data):

        data = data or {}

        stages = {
            name: Stage.from_dict(name, data.get(name))
            for name in STAGES
        }

        return cls(stages)

    def to_dict(self):

        return {
            name: self.stages[name].to_dict()
            for name in STAGES
        }

    # ------------------------------------------------------------------
    # Backward compatibility with the old flat scene format
    # ------------------------------------------------------------------

    def adopt_legacy(self, image="", video="", status=""):
        """
        Fill the pipeline from the old scenes.json fields.

        Old files only had `image`, `video` and one overall `status`.
        A stage counts as completed if the old file recorded an output
        path for it, which is the only thing the old format could tell us.
        """

        legacy_status = StageStatus.parse(status)

        for name, output in (("image", image), ("video", video)):

            stage = self.stages[name]

            # Never overwrite real pipeline data.
            if stage.output or stage.status != StageStatus.NOT_STARTED:
                continue

            if output:
                stage.output = output

                if legacy_status == StageStatus.FAILED:
                    stage.status = StageStatus.FAILED
                else:
                    stage.status = StageStatus.COMPLETED
