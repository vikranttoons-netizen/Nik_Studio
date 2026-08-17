import shutil
import subprocess
from pathlib import Path


class ComposeError(Exception):
    """The final video could not be assembled."""


class EpisodeComposer:
    """
    Stitches the scene clips into one playable episode.

    This is the last step of the pipeline:

        Videos/Scene01.mp4
        Videos/Scene02.mp4   ->   Exports/Episode.mp4
        Videos/Scene03.mp4

    The clips are joined in scene order - the order shown in the scene
    list - not in filename order, so moving a scene up or down in the UI
    really does change the edit.
    """

    OUTPUT_FOLDER = "Exports"

    def __init__(self, episode_folder, settings=None):

        self.episode_folder = Path(episode_folder)
        self.settings = dict(settings or {})

    # ------------------------------------------------------------------

    def executable(self):
        return self.settings.get("ffmpeg") or shutil.which("ffmpeg") or ""

    def is_available(self):
        return bool(self.executable())

    def unavailable_reason(self):

        if self.is_available():
            return ""

        return (
            "FFmpeg was not found, so the final video cannot be "
            "assembled.\n\n"
            "Install it with:\n"
            "  winget install Gyan.FFmpeg\n\n"
            "Then close and reopen Nik Studio."
        )

    # ------------------------------------------------------------------

    def output_name(self):

        title = self.settings.get("title") or self.episode_folder.name

        # Keep the filename safe on Windows.
        safe = "".join(
            character
            for character in str(title)
            if character.isalnum() or character in " -_"
        ).strip()

        return f"{safe or 'Episode'}.mp4"

    @property
    def output_path(self):
        return self.episode_folder / self.OUTPUT_FOLDER / self.output_name()

    # ------------------------------------------------------------------

    def clips(self, scenes):
        """
        The clips to join, in scene order.

        Scenes with no clip yet are skipped rather than treated as an
        error, so a partly rendered episode still produces a watchable
        preview of what is done.
        """

        found = []
        missing = []

        for scene in scenes:

            output = scene.pipeline.video.output

            if not output:
                missing.append(scene.name)
                continue

            path = self.episode_folder / output

            if not path.exists() or path.stat().st_size == 0:
                missing.append(scene.name)
                continue

            found.append(path)

        return found, missing

    # ------------------------------------------------------------------

    def compose(self, scenes):
        """
        Build the episode video. Returns the path relative to the episode
        folder.
        """

        if not self.is_available():
            raise ComposeError(self.unavailable_reason())

        clips, missing = self.clips(scenes)

        if not clips:
            raise ComposeError(
                "There are no scene clips to join yet.\n\n"
                "Render the episode first so each scene has a video."
            )

        output = self.output_path

        output.parent.mkdir(parents=True, exist_ok=True)

        # FFmpeg's concat demuxer reads the clip list from a file. Paths
        # are quoted because episode names contain spaces.
        list_file = output.parent / "clips.txt"

        with open(list_file, "w", encoding="utf-8") as f:
            for clip in clips:
                safe = str(clip.resolve()).replace("'", r"'\''")
                f.write(f"file '{safe}'\n")

        command = [
            self.executable(),
            "-y",
            "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            # The clips were all written by the same backend with the same
            # settings, so they can be joined without re-encoding.
            "-c", "copy",
            "-movflags", "+faststart",
            str(output),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=int(self.settings.get("ffmpeg_timeout", 1800)),
            )

        except FileNotFoundError as error:
            raise ComposeError(self.unavailable_reason()) from error

        except subprocess.TimeoutExpired as error:
            raise ComposeError(
                "FFmpeg took too long joining the clips and was stopped."
            ) from error

        finally:
            list_file.unlink(missing_ok=True)

        if result.returncode != 0:

            detail = (result.stderr or "").strip().splitlines()

            raise ComposeError(
                "FFmpeg could not join the clips.\n"
                + "\n".join(detail[-4:])
            )

        if not output.exists() or output.stat().st_size == 0:
            raise ComposeError("FFmpeg produced no video file.")

        self.missing = missing

        return f"{self.OUTPUT_FOLDER}/{output.name}"
