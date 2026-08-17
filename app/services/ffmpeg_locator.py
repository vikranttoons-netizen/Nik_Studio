import shutil
from pathlib import Path


def find_ffmpeg(configured=None):
    """
    Find a usable ffmpeg, or return "" when there is none.

    Looked for in this order:

      1. the path set as "ffmpeg" in episode.json, if it really exists
      2. ffmpeg on PATH, the normal case after a system install
      3. the copy bundled with the imageio-ffmpeg package

    Point 3 matters on Windows: `winget` does not exist on every machine,
    and installing FFmpeg by hand means unzipping it and editing PATH.
    `pip install imageio-ffmpeg` needs neither admin rights nor PATH
    changes, so it is the easy way out - and it is found automatically.
    """

    if configured:

        if Path(configured).exists():
            return str(configured)

        found = shutil.which(str(configured))

        if found:
            return found

    found = shutil.which("ffmpeg")

    if found:
        return found

    try:
        import imageio_ffmpeg
    except ImportError:
        return ""

    try:
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        # The package is installed but its binary is missing or broken.
        return ""

    return bundled if bundled and Path(bundled).exists() else ""


def ffmpeg_help():
    """What to tell the user when no ffmpeg could be found."""

    return (
        "FFmpeg was not found. It turns your scene images into video, so "
        "it is needed to produce the final MP4.\n\n"
        "The easiest way to install it:\n"
        "    pip install imageio-ffmpeg\n\n"
        "Then close and reopen Nik Studio.\n\n"
        "Other options:\n"
        "  winget install Gyan.FFmpeg      (if your Windows has winget)\n"
        "  choco install ffmpeg            (if you use Chocolatey)\n\n"
        "If FFmpeg is already on this machine, put its full path in the "
        "episode's episode.json:\n"
        '    "ffmpeg": "C:\\\\ffmpeg\\\\bin\\\\ffmpeg.exe"'
    )
