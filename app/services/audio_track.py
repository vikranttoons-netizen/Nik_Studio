import re
import subprocess
from pathlib import Path

from services.ffmpeg_locator import find_ffmpeg


# Audio files an episode might carry, in the order they are preferred.
AUDIO_SUFFIXES = (".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac")

# Where a song is looked for inside the episode.
AUDIO_FOLDER = "Audio"


def find_track(episode_folder, settings=None):
    """
    The song for this episode, or None.

    Either named outright in episode.json:

        "music": "Audio/bath time song.mp3"

    or simply dropped into the episode's Audio folder, which is the way
    most people will do it.
    """

    episode_folder = Path(episode_folder)
    settings = dict(settings or {})

    named = settings.get("music")

    if named:

        path = Path(named).expanduser()

        if not path.is_absolute():
            path = episode_folder / path

        return path if path.exists() else None

    folder = episode_folder / AUDIO_FOLDER

    if not folder.exists():
        return None

    tracks = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES
    )

    return tracks[0] if tracks else None


# ----------------------------------------------------------------------


DURATION_PATTERN = re.compile(
    r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)"
)


def duration(path, ffmpeg=None):
    """
    Length of an audio file in seconds, or None if it cannot be read.

    Read with ffmpeg rather than ffprobe on purpose: the ffmpeg that
    `pip install imageio-ffmpeg` provides does not include ffprobe, and
    that is the copy most people here will be running.

    Asking ffmpeg to decode a file without giving it an output is an
    error, so it exits non-zero - but it prints the duration first, which
    is all this needs.
    """

    executable = ffmpeg or find_ffmpeg()

    if not executable:
        return None

    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            # Say how to read it. Without this, Python decodes ffmpeg's
            # output with whatever the system prefers - cp1252 on a
            # Windows machine - and a song whose tags carry a byte that
            # codec has no letter for kills the reader thread. The file
            # is fine; only the reading of ffmpeg's chatter about it was
            # not. Nothing here needs those bytes to be right, so a
            # replacement character in a log line is no loss.
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    match = DURATION_PATTERN.search(result.stderr or "")

    if not match:
        return None

    hours, minutes, seconds = match.groups()

    total = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    return total if total > 0 else None


# ----------------------------------------------------------------------


def fit_scene_durations(scenes, total_seconds, minimum=1.0):
    """
    Spread `total_seconds` across the scenes, so the pictures last exactly
    as long as the song.

    A scene with its own "duration" in metadata keeps it - that is how you
    hold one shot longer - and what is left over is divided evenly between
    the rest.

    Returns {scene name: seconds}. Nothing is written to the scenes here;
    the caller decides what to do with the answer.
    """

    if not scenes or not total_seconds or total_seconds <= 0:
        return {}

    fixed = {}
    flexible = []

    for scene in scenes:

        value = scene.metadata.get("duration")

        try:
            if value is not None and float(value) > 0:
                fixed[scene.name] = float(value)
                continue
        except (ValueError, TypeError):
            pass

        flexible.append(scene)

    if not flexible:
        return fixed

    remaining = total_seconds - sum(fixed.values())

    # The fixed scenes can already be longer than the song. Rather than
    # handing out negative time, give every flexible scene the minimum.
    share = max(minimum, remaining / len(flexible))

    for scene in flexible:
        fixed[scene.name] = share

    return fixed
