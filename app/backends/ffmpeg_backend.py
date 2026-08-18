import subprocess

from backends.base_backend import (
    BaseBackend,
    BackendError,
    BackendUnavailable,
)

from services.ffmpeg_locator import find_ffmpeg, ffmpeg_help


class FFmpegBackend(BaseBackend):
    """
    Turns a scene's still image into a moving clip with FFmpeg.

    No AI model is involved. A slow zoom and drift across the still (the
    Ken Burns effect) is what makes a slideshow read as a video, and it is
    fast, free and predictable. When a real video model is added later it
    implements the same generate_video() and drops straight in - nothing
    in the UI changes.
    """

    name = "FFmpeg"
    supports = ("video",)

    # 16:9, the shape asked for. 9:16 and 1:1 come from episode.json.
    ASPECTS = {
        "16:9": (1920, 1080),
        "9:16": (1080, 1920),
        "1:1": (1080, 1080),
    }

    DEFAULT_ASPECT = "16:9"
    DEFAULT_DURATION = 4.0
    DEFAULT_FPS = 24

    # How far the zoom travels over the clip. 1.12 is a gentle drift -
    # enough to feel alive, not enough to look like a zoom.
    ZOOM = 1.12

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def executable(self):
        return find_ffmpeg(self.setting("ffmpeg"))

    def is_available(self):
        return bool(self.executable())

    def unavailable_reason(self):

        if self.is_available():
            return ""

        return ffmpeg_help()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def size(self):
        """Output size in pixels, from the episode's aspect ratio."""

        aspect = str(self.setting("aspect", self.DEFAULT_ASPECT)).strip()

        if aspect in self.ASPECTS:
            return self.ASPECTS[aspect]

        # An explicit "1920x1080" also works.
        try:
            width, height = (int(v) for v in aspect.lower().split("x")[:2])
            return max(2, width - width % 2), max(2, height - height % 2)
        except (ValueError, TypeError):
            return self.ASPECTS[self.DEFAULT_ASPECT]

    def fps(self):

        try:
            return max(1, int(self.setting("fps", self.DEFAULT_FPS)))
        except (ValueError, TypeError):
            return self.DEFAULT_FPS

    def duration(self, scene):
        """
        How long this scene is on screen.

        A per-scene duration in scene.metadata wins, so one shot can be
        held longer than the rest. Once voice generation exists, the
        narration length will set this instead.
        """

        for value in (
            scene.metadata.get("duration"),
            self.setting("scene_duration"),
        ):
            try:
                if value is not None and float(value) > 0:
                    return float(value)
            except (ValueError, TypeError):
                continue

        return self.DEFAULT_DURATION

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_video(self, scene, prompt, negative=""):

        if not self.is_available():
            raise BackendUnavailable(self.unavailable_reason())

        image = scene.pipeline.image.output

        if not image:
            raise BackendError(
                f"{scene.name} has no image yet. Render the images first."
            )

        source = self.episode_folder / image

        if not source.exists():
            raise BackendError(
                f"{scene.name}: image file is missing ({image})."
            )

        absolute, relative = self.output_path(
            "Videos",
            f"{scene.name}.mp4",
        )

        width, height = self.size()
        fps = self.fps()
        seconds = self.duration(scene)

        frames = max(1, int(round(seconds * fps)))

        command = [
            self.executable(),
            "-y",
            "-loglevel", "error",
            "-loop", "1",
            "-i", str(source),
            "-t", f"{seconds}",
            "-filter_complex", self.filter_chain(width, height, fps, frames),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "20",
            "-r", str(fps),
            str(absolute),
        ]

        self.run(command, scene.name)

        if not absolute.exists() or absolute.stat().st_size == 0:
            raise BackendError(
                f"{scene.name}: FFmpeg produced no video file."
            )

        return relative

    # ------------------------------------------------------------------

    def filter_chain(self, width, height, fps, frames):
        """
        Build the pan/zoom filter.

        The source is usually a square AI image being fitted into a 16:9
        frame, so it is scaled to cover the frame and the overflow is
        cropped rather than letterboxed - black bars down the sides would
        look like a mistake.

        The upscale before zoompan is what keeps the movement smooth:
        zoompan works on whole source pixels, so zooming a frame-sized
        image makes the motion visibly step.
        """

        big_width = width * 4
        big_height = height * 4

        return (
            f"scale={big_width}:{big_height}"
            f":force_original_aspect_ratio=increase,"
            f"crop={big_width}:{big_height},"
            f"zoompan="
            f"z='min(zoom+{(self.ZOOM - 1) / frames:.8f},{self.ZOOM})'"
            f":x='iw/2-(iw/zoom/2)'"
            f":y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={width}x{height}:fps={fps},"
            f"format=yuv420p"
        )

    # ------------------------------------------------------------------

    def run(self, command, label):
        """Run FFmpeg and turn a failure into a readable message."""

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=int(self.setting("ffmpeg_timeout", 600)),
            )

        except FileNotFoundError as error:
            raise BackendUnavailable(self.unavailable_reason()) from error

        except subprocess.TimeoutExpired as error:
            raise BackendError(
                f"{label}: FFmpeg took too long and was stopped."
            ) from error

        if result.returncode != 0:

            # FFmpeg errors are many lines of detail; the last lines are
            # the ones that say what actually went wrong.
            detail = (result.stderr or "").strip().splitlines()

            raise BackendError(
                f"{label}: FFmpeg failed.\n"
                + "\n".join(detail[-4:])
            )

        return result
