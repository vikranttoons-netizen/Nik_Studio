from dataclasses import dataclass, field


@dataclass
class RenderProgress:
    """
    A single progress update, sent to the UI while rendering runs.

    The UI uses this to show what is happening without knowing anything
    about backends or models.
    """

    scene: str = ""
    stage: str = ""
    status: str = ""
    message: str = ""
    index: int = 0
    total: int = 0

    def text(self):

        position = ""

        if self.total:
            position = f"[{self.index}/{self.total}] "

        parts = [p for p in (self.scene, self.stage) if p]

        head = " · ".join(parts)

        if self.message:
            return f"{position}{head} — {self.message}"

        return f"{position}{head} {self.status}"


@dataclass
class RenderResult:
    """
    What a render produced. Returned by both SceneRenderer and
    EpisodeRenderer so the UI can report progress and problems without
    knowing how the rendering happened.

    `waiting` holds work handed off to a cloud GPU that has not come back
    yet - that is not a failure, so it does not clear `success`.
    """

    success: bool = True
    message: str = ""

    rendered_images: list = field(default_factory=list)
    rendered_videos: list = field(default_factory=list)
    rendered_audio: list = field(default_factory=list)

    final_video: str = ""

    skipped: list = field(default_factory=list)
    waiting: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    # ------------------------------------------------------------------

    # Which list each pipeline stage reports into.
    STAGE_BUCKETS = {
        "image": "rendered_images",
        "video": "rendered_videos",
        "voice": "rendered_audio",
        "music": "rendered_audio",
    }

    def record(self, stage, output):
        """File the output of a completed stage into the right list."""

        if stage == "final":
            self.final_video = output
            return

        bucket = self.STAGE_BUCKETS.get(stage)

        if bucket:
            getattr(self, bucket).append(output)

    def add_error(self, scene, stage, error):

        self.success = False

        self.errors.append(
            {
                "scene": scene,
                "stage": stage,
                "error": str(error),
            }
        )

    def add_waiting(self, scene, stage, message=""):

        self.waiting.append(
            {
                "scene": scene,
                "stage": stage,
                "message": str(message),
            }
        )

    def add_skipped(self, scene, stage):

        self.skipped.append(
            {
                "scene": scene,
                "stage": stage,
            }
        )

    # ------------------------------------------------------------------

    def merge(self, other):
        """Fold a scene result into this episode result."""

        self.rendered_images.extend(other.rendered_images)
        self.rendered_videos.extend(other.rendered_videos)
        self.rendered_audio.extend(other.rendered_audio)

        self.skipped.extend(other.skipped)
        self.waiting.extend(other.waiting)
        self.errors.extend(other.errors)

        if other.final_video:
            self.final_video = other.final_video

        if not other.success:
            self.success = False

        return self

    # ------------------------------------------------------------------

    @property
    def rendered_count(self):

        return (
            len(self.rendered_images)
            + len(self.rendered_videos)
            + len(self.rendered_audio)
        )

    def summary(self):
        """One readable paragraph for the UI."""

        lines = []

        if self.rendered_images:
            lines.append(f"🖼 Images rendered : {len(self.rendered_images)}")

        if self.rendered_videos:
            lines.append(f"🎥 Videos rendered : {len(self.rendered_videos)}")

        if self.rendered_audio:
            lines.append(f"🎙 Audio rendered  : {len(self.rendered_audio)}")

        if self.final_video:
            lines.append(f"🎬 Final video     : {self.final_video}")

        if self.skipped:
            lines.append(
                f"⏭ Already done     : {len(self.skipped)} (skipped)"
            )

        if self.waiting:
            lines.append(
                f"⏳ Waiting on cloud : {len(self.waiting)}"
            )

        if self.errors:
            lines.append(f"❌ Failed          : {len(self.errors)}")

            for item in self.errors:
                lines.append(
                    f"   • {item['scene']} ({item['stage']}): "
                    f"{item['error']}"
                )

        if not lines:
            lines.append("Nothing to render.")

        if self.message:
            lines.insert(0, self.message)

        return "\n".join(lines)
