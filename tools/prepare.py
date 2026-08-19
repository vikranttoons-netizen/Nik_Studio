"""
Nik Studio — get the Colab folder ready, and check it before you pay.

    python tools\\prepare.py                 see what would happen
    python tools\\prepare.py --copy          actually build the folder

Running a GPU costs money now, so everything that can be checked without
one is checked here first: that the pictures open, that the song can be
read, that there are enough pictures for the song, and that no clip left
over from a previous run will be quietly reused.

It writes the folder NikStudio_Animate.ipynb expects:

    <Drive>\\NikStudio\\Input\\Scene01.png
    <Drive>\\NikStudio\\Input\\Scene02.png
    <Drive>\\NikStudio\\Input\\song.mp3
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "app"))


OK = "[ OK ]"
BAD = "[FAIL]"
WARN = "[WARN]"

PICTURE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
AUDIO_SUFFIXES = (".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac")

# The longest clip the model will make, in seconds. Everything past this
# has to be filled by slowing the clip down, which looks wrong past about
# double. Used here only to say how many pictures a song needs.
LONGEST_CLIP = 8.0


# ----------------------------------------------------------------------
# Ordering
# ----------------------------------------------------------------------

def natural_key(path):
    """
    Sort "Scene2" before "Scene10".

    Plain alphabetical order puts "10" before "2", which silently shuffles
    someone's scenes. The numbers in a name are compared as numbers.
    """

    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", str(path.name))
    ]


# ----------------------------------------------------------------------
# Finding things
# ----------------------------------------------------------------------

def pictures_in(folder):

    return sorted(
        (p for p in folder.iterdir()
         if p.is_file() and p.suffix.lower() in PICTURE_SUFFIXES),
        key=natural_key,
    )


def songs_in(folder):

    return sorted(
        (p for p in folder.iterdir()
         if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES),
        key=natural_key,
    )


def gather(source):
    """
    The pictures and songs to use.

    An episode folder keeps them apart, in Images/ and Audio/. A folder
    someone assembled by hand has them side by side. Both are accepted,
    because insisting on one is how people end up with an empty run.
    """

    pictures, songs = [], []

    for sub in ("Images", ""):

        folder = source / sub if sub else source

        if folder.is_dir():
            pictures = pictures_in(folder)

        if pictures:
            break

    for sub in ("Audio", ""):

        folder = source / sub if sub else source

        if folder.is_dir():
            songs = songs_in(folder)

        if songs:
            break

    return pictures, songs


def default_source():
    """The episode to take pictures from, when none was named."""

    from core.project import Project

    project = Project()

    names = project.episode_names()

    return project.episode_path(names[0]) if names else None


def default_destination():
    """
    Where to build the Input folder, when none was named.

    Taken from nikstudio.local.json, which is where machine specific
    paths belong - it is not in git, so a Drive letter that only exists
    on one PC never collides with an update.
    """

    from core.project import Project

    local = Project().local_settings()

    named = local.get("input_folder")

    if named:
        return Path(named).expanduser()

    # The sync folder is already inside Drive, so the Input folder the
    # notebook wants is its neighbour.
    sync = local.get("sync_folder")

    if sync:
        return Path(sync).expanduser().parent / "Input"

    return None


# ----------------------------------------------------------------------
# Checking
# ----------------------------------------------------------------------

def picture_size(path):
    """(width, height), or None when the file is not really an image."""

    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        with Image.open(path) as image:
            image.verify()

        with Image.open(path) as image:
            return image.size

    except Exception:
        return None


def song_seconds(path):
    """Length of the song, or None when it cannot be read."""

    from services.audio_track import duration

    return duration(path)


def report(source, destination):
    """
    Look at everything and say what is wrong.

    Returns (problems, notes, pictures, song, seconds). A problem stops
    the run; a note is worth knowing but not fatal.
    """

    problems, notes = [], []

    print(f"\nPictures and song from : {source}")
    print(f"Colab folder to build  : {destination or '(not set)'}")

    if destination is None:
        problems.append(
            "No Colab folder set. Either pass --to \"G:\\My Drive\\"
            "NikStudio\\Input\", or put this in nikstudio.local.json:\n"
            '           {"input_folder": "G:\\\\My Drive\\\\NikStudio\\\\Input"}'
        )

    if not source.is_dir():
        problems.append(f"No such folder: {source}")
        return problems, notes, [], None, None

    pictures, songs = gather(source)

    # ----------------------------------------------------------- pictures

    print()

    if not pictures:
        problems.append(
            f"No pictures found in {source} (looked in Images\\ too)."
        )
    else:
        print(f"{OK} {len(pictures)} picture(s)")

    shapes = set()

    for picture in pictures:

        size = picture_size(picture)

        if size is None:
            problems.append(
                f"{picture.name} is not a picture the tool can open. "
                "Re-save it as a PNG."
            )
            continue

        width, height = size

        shapes.add(round(width / height, 2))

        print(f"       {picture.name:<28} {width}x{height}")

    if len(shapes) > 1:
        notes.append(
            "The pictures are not all the same shape, so some will be "
            "cropped more than others. Not fatal, but they will not match."
        )

    # --------------------------------------------------------------- song

    print()

    song = None
    seconds = None

    if not songs:
        notes.append(
            f"No song in {source} (looked in Audio\\ too). Each picture "
            "will get a fixed 5 seconds instead."
        )
        print(f"{WARN} no song")

    else:

        song = songs[0]

        if len(songs) > 1:
            notes.append(
                f"{len(songs)} audio files found; using {song.name}. "
                "Move the others out to be sure."
            )

        seconds = song_seconds(song)

        if not seconds:
            problems.append(
                f"{song.name} cannot be read. Check FFmpeg is installed "
                "(pip install -r requirements.txt) and the file plays."
            )
        else:
            print(f"{OK} {song.name} — {seconds:.1f}s")

    # ------------------------------------------------- enough pictures?

    if pictures and seconds:

        share = seconds / len(pictures)

        print(f"\n       {len(pictures)} picture(s) over {seconds:.0f}s "
              f"= {share:.1f}s each")

        needed = max(1, int(seconds / LONGEST_CLIP + 0.999))

        if share > LONGEST_CLIP * 2:
            problems.append(
                f"{share:.0f}s per picture, but the longest clip the model "
                f"makes is {LONGEST_CLIP:.0f}s, so each would be slowed "
                f"{share / LONGEST_CLIP:.1f}x and look wrong.\n"
                f"           Use about {needed} pictures for a "
                f"{seconds:.0f}s song."
            )

        elif share > LONGEST_CLIP:
            notes.append(
                f"Each picture is on screen {share:.1f}s but clips are at "
                f"most {LONGEST_CLIP:.0f}s, so they will be slowed "
                f"{share / LONGEST_CLIP:.2f}x. That reads as slow motion. "
                f"{needed} pictures would need no slowing at all."
            )

        else:
            print(f"{OK} clips will not need slowing down")

    return problems, notes, pictures, song, seconds


# ----------------------------------------------------------------------
# Building the folder
# ----------------------------------------------------------------------

def build(destination, pictures, song):
    """
    Copy everything in, numbered in order, and say what happened.

    Pictures are renumbered rather than copied under their own names so
    that the order in Drive is the order on screen - Colab sorts by name,
    and "shot10" before "shot2" is not what anyone means.
    """

    destination.mkdir(parents=True, exist_ok=True)

    written = []

    for number, picture in enumerate(pictures, start=1):

        target = destination / f"Scene{number:02d}{picture.suffix.lower()}"

        shutil.copy2(picture, target)

        written.append(target)

        arrow = "" if picture.name == target.name else f"   <- {picture.name}"

        print(f"       {target.name}{arrow}")

    if song:

        target = destination / f"song{song.suffix.lower()}"

        shutil.copy2(song, target)

        written.append(target)

        print(f"       {target.name}   <- {song.name}")

    # ------------------------------------------------------- stale files

    # Anything left from a previous, longer episode would be picked up by
    # the notebook as an extra scene. Only files this tool writes are
    # removed, so nothing of the user's own is ever touched.
    kept = {path.name for path in written}

    for existing in sorted(destination.iterdir()):

        if not existing.is_file() or existing.name in kept:
            continue

        looks_ours = (
            re.fullmatch(r"Scene\d{2}\..+", existing.name)
            or re.fullmatch(r"song\..+", existing.name)
        )

        if looks_ours:
            existing.unlink()
            print(f"       removed {existing.name} (left from last time)")

    return written


def stale_clips(destination, pictures):
    """
    Clips from a previous run that no longer match the pictures.

    The notebook skips a clip that already exists, which is what makes a
    dead session cheap - but it also means a changed picture would keep
    its old clip. Say so plainly rather than let it happen quietly.
    """

    clips = destination.parent / "Output" / "Clips"

    if not clips.is_dir():
        return []

    return sorted(
        clip for clip in clips.glob("Scene*.mp4")
        if clip.is_file()
    )


# ----------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Build and check the Colab Input folder.",
    )

    parser.add_argument(
        "--from", dest="source",
        help="Folder with the pictures and song. "
             "Defaults to your first episode.",
    )

    parser.add_argument(
        "--to", dest="destination",
        help="The Input folder in Google Drive. Defaults to "
             "input_folder in nikstudio.local.json.",
    )

    parser.add_argument(
        "--copy", action="store_true",
        help="Actually copy the files. Without this, nothing is written.",
    )

    arguments = parser.parse_args()

    source = (
        Path(arguments.source).expanduser()
        if arguments.source else default_source()
    )

    if source is None:
        print(f"{BAD} No episodes found, and no --from folder given.")
        return 1

    destination = (
        Path(arguments.destination).expanduser()
        if arguments.destination else default_destination()
    )

    problems, notes, pictures, song, seconds = report(source, destination)

    # ----------------------------------------------------------- verdict

    print()

    for note in notes:
        print(f"{WARN} {note}")

    for problem in problems:
        print(f"{BAD} {problem}")

    if problems:
        print("\nNot ready. Fix the above, then run this again.")
        return 1

    existing = stale_clips(destination, pictures) if destination else []

    if existing:
        print(
            f"{WARN} {len(existing)} clip(s) already in Output\\Clips. The "
            "notebook reuses\n       clips by name, so delete them if the "
            "pictures have changed."
        )

    if not arguments.copy:
        print(
            f"\n{OK} Everything checks out. Nothing has been copied yet.\n"
            "       Run it again with --copy to build the folder:\n\n"
            "           python tools\\prepare.py --copy"
        )
        return 0

    print(f"\nCopying into {destination}\n")

    build(destination, pictures, song)

    print(
        f"\n{OK} Ready. Open colab\\NikStudio_Animate.ipynb in Colab,\n"
        "       set Runtime > Change runtime type > L4 GPU,\n"
        "       and run its two cells."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
