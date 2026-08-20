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

# How long one picture can hold the screen, in seconds.
#
# The model is only ever asked for a short clip, because that is as far
# as it holds your picture before it starts inventing - at eight seconds
# the face melted at two and the scene was gone by four. Anything longer
# is filled by playing that clip forwards, then backwards, then forwards
# again.
#
# So the question is not "how long a clip" but "how many times does the
# same movement come round". Twice is unnoticeable. Four times is not.
# Worked out the same way the notebook does it, from the frames the
# model is actually asked for, so the two never disagree about how many
# pictures a song needs. (frames - 1) has to divide by 8, and the
# forwards-and-back pair drops a frame at each end of the reversed half.
FPS = 24
ASKED_FOR = 3.0

FRAMES = max(25, round((ASKED_FOR * FPS - 1) / 8) * 8 + 1)

CLIP_SECONDS = FRAMES / FPS
BOUNCE_SECONDS = (2 * FRAMES - 2) / FPS

COMFORTABLE = BOUNCE_SECONDS * 2


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


def default_source(destination=None):
    """
    Where to take the pictures from, when --from was not given.

    The Colab folder itself comes first. Once someone has put their own
    pictures and song in there, that is plainly what they mean - reaching
    past it for an episode's old renders is how you end up preparing a
    folder full of pictures you replaced last week.

    Only when that folder has nothing in it does an episode get used.
    """

    if destination and destination.is_dir() and pictures_in(destination):
        return destination

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

    same = (
        destination is not None
        and source.is_dir()
        and destination.is_dir()
        and source.resolve() == destination.resolve()
    )

    print(f"\nPictures and song from : {source}")

    if same:
        print("                         (the Colab folder itself - "
              "tidying it in place)")

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

    shapes = {}

    for picture in pictures:

        size = picture_size(picture)

        if size is None:
            problems.append(
                f"{picture.name} is not a picture the tool can open. "
                "Re-save it as a PNG."
            )
            continue

        width, height = size

        shapes.setdefault(round(width / height, 2), []).append(picture.name)

        print(f"       {picture.name:<28} {width}x{height}")

    if len(shapes) > 1:

        # Name the odd ones out. "Some pictures are a different shape" is
        # true and useless; which ones, and how much gets cut off, is
        # what lets someone decide whether to re-crop or leave it.
        usual = max(shapes, key=lambda ratio: len(shapes[ratio]))

        odd = [
            (ratio, names) for ratio, names in shapes.items()
            if ratio != usual
        ]

        lines = []

        for ratio, names in sorted(odd, key=lambda pair: -len(pair[1])):

            # Everything is cropped to cover a 16:9 frame, so a squarer
            # picture loses the top and bottom.
            lost = max(0, round((1 - ratio / usual) * 100))

            shown = ", ".join(names[:4])

            if len(names) > 4:
                shown += f" and {len(names) - 4} more"

            lines.append(
                f"           {shown} — about {lost}% taller than the rest, "
                "so more is cropped off the top and bottom"
            )

        notes.append(
            f"{sum(len(names) for _, names in odd)} of {len(pictures)} "
            "pictures are a different shape:\n"
            + "\n".join(lines)
            + "\n           Not fatal - they will simply be framed "
              "differently from the others."
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

        needed = max(1, int(seconds / COMFORTABLE + 0.999))

        times = share / BOUNCE_SECONDS

        if times > 4:
            problems.append(
                f"{share:.0f}s per picture, but a clip covers "
                f"{BOUNCE_SECONDS:.1f}s, so the same movement\n"
                f"           would come round {times:.0f} times over and be "
                f"obvious.\n"
                f"           Use about {needed} pictures for a "
                f"{seconds:.0f}s song."
            )

        elif times > 2:
            notes.append(
                f"{share:.1f}s a picture against a {BOUNCE_SECONDS:.1f}s "
                f"clip means the movement comes round {times:.1f} times. "
                f"Watchable, but {needed} pictures would be better."
            )

        elif share > CLIP_SECONDS:
            print(f"{OK} each clip plays forwards and back to fill "
                  f"{share:.1f}s")
            print(f"       The model is only asked for "
                  f"{CLIP_SECONDS:.1f}s, which is as long as it holds\n"
                  f"       your picture. Nothing is stretched.")

        else:
            print(f"{OK} one clip covers each picture outright")

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

    # Everything is copied to one side first and moved into place after.
    # The source is often the destination - someone fills the Colab
    # folder themselves and runs this to tidy it - and renaming in place
    # would have one picture land on another before it had been read.
    staging = destination / ".prepare"

    if staging.exists():
        shutil.rmtree(staging)

    staging.mkdir()

    planned = []

    for number, picture in enumerate(pictures, start=1):
        planned.append(
            (picture, f"Scene{number:02d}{picture.suffix.lower()}")
        )

    if song:
        planned.append((song, f"song{song.suffix.lower()}"))

    for original, name in planned:
        shutil.copy2(original, staging / name)

    written = []

    for original, name in planned:

        target = destination / name

        shutil.move(str(staging / name), str(target))

        written.append(target)

        arrow = "" if original.name == name else f"   <- {original.name}"

        print(f"       {name}{arrow}")

    shutil.rmtree(staging, ignore_errors=True)

    # ------------------------------------------------- the old names

    # When the Colab folder was also the source, the files that were
    # just renumbered are still sitting there under their old names -
    # and the notebook would read them as extra scenes. Only the files
    # this run actually consumed are removed.
    kept = {name for _, name in planned}

    for original, _ in planned:

        if original.name in kept or not original.exists():
            continue

        if original.parent.resolve() != destination.resolve():
            continue

        original.unlink()

        print(f"       removed {original.name} (renamed above)")

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

    destination = (
        Path(arguments.destination).expanduser()
        if arguments.destination else default_destination()
    )

    source = (
        Path(arguments.source).expanduser()
        if arguments.source else default_source(destination)
    )

    if source is None:
        print(f"{BAD} No pictures anywhere, and no --from folder given.")
        return 1

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
