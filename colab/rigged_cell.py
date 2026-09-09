# ======================================================================
# NIK STUDIO - RIGGED.  Run this one cell. That is the whole notebook.
# ======================================================================
#
# Nothing to upload. The two scripts this needs are carried inside this
# cell, so Drive only ever holds your own things: the character pack,
# the script, the song.
#
#     My Drive / NikStudio / Mixamo /      the character pack, unzipped
#     My Drive / NikStudio / Moves /       an animation library (if any)
#     My Drive / NikStudio / input /       script.txt
#
# ----------------------------------------------------------- SETTINGS

BUILD = "2026-09-22 - textures found, and no black cut-outs"

DRIVE = "/content/drive/MyDrive"

FOLDER = DRIVE + "/NikStudio"

# Where the character pack is, inside FOLDER. Searched all the way
# down, so an unzipped pack can go in whole.
MIXAMO = "Mixamo"

# Which character, when the pack has many. Part of the file name is
# enough - "Casual_Male", "Boy". Left empty, one is chosen: a plain
# everyday character rather than the pack's blank mannequin or its
# zombies and knights.
CHARACTER = ""

# A second folder, inside FOLDER, read for movements only. A character
# pack is built for games - it ships death and punching, and a nursery
# rhyme wants clapping and waving. Free CC0 library, name your own
# price (put 0):  https://quaternius.itch.io/universal-animation-library
MOVEMENTS = ""

# How much of a small child to make the character. 0 leaves whoever was
# downloaded alone; 1.0 gives a toddler's shape - body to 70%, head to
# 125%, which on a grown-up rig puts the head at about a fifth of the
# height. Every free rigged character is a grown-up; this is how ours
# is not.
CHILD = 1.0

# Flat and fast and no GPU, for checking that the movements are right.
# "BLENDER_EEVEE_NEXT" is the one that looks like something, and wants
# a GPU turned on.
ENGINE = "BLENDER_WORKBENCH"

WIDTH, HEIGHT = 1024, 576

# How long one clip is. The edit cuts every 2.8s and slides the clip to
# put its movement on the beat, so a second of slack is worth having.
CLIP_SECONDS = 4.0

# Only make this many, to see what they look like. 0 makes all of them.
# Two, this time, only to see whether the colour came back - forty-four
# is forty minutes and there is no sense spending it on a black
# silhouette.
FIRST_ONLY = 2

# Build Nik.blend again even when the settings have not changed. Only
# needed after dropping another file into one of the folders.
REBUILD = False

# ------------------------------------------------------ nothing below

import base64
import os
import subprocess
import sys
from pathlib import Path

print(f"Notebook  : {BUILD}")

# Blender. A restarted or reconnected session loses it, and the only
# sign of that is an import error inside a file nobody here wrote.
try:
    import bpy

except ImportError:

    print("\nBlender is not in this session. Installing it - about two "
          "minutes.\n")

    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "bpy", "imageio-ffmpeg"], check=True)

    try:
        import bpy

    except ImportError:
        raise SystemExit(
            "Blender installed, but the session has to be restarted "
            "before it can be\nused.\n\n"
            "    Runtime > Restart session, then run this cell again."
        )

HOME = Path(FOLDER)

try:
    from google.colab import drive

    drive.mount("/content/drive")

except ImportError:

    # Not Colab. Fine - FOLDER is then a folder on this machine.
    pass

except Exception as trouble:

    print(f"\nDrive did not mount ({type(trouble).__name__}).")

    if not HOME.exists():
        raise SystemExit(
            "\nGoogle Drive is not connected, so nothing below can "
            "find your files.\nEverything after this would complain "
            "about the wrong thing.\n\n"
            "Usually the permission window was closed, or never "
            "appeared:\n\n"
            "    1. Run this cell again, and when the window opens, "
            "pick your account\n       and click through every "
            "'Allow'. It asks for a lot; that is normal.\n\n"
            "    2. If no window appears, allow pop-ups for "
            "colab.research.google.com\n       in the address bar, "
            "then run the cell again.\n\n"
            "    3. Still nothing: Runtime > Disconnect and delete "
            "runtime, then run\n       the cell again."
        )

    print("            (but the folder is there, so carrying on)")

INTO = HOME / "Output" / "Clips"

# The two scripts, written out of this cell. They used to have to be
# uploaded to Drive and kept in step by hand, which went wrong every
# time one of them changed.
HERE = Path("/content/nikstudio")

HERE.mkdir(parents=True, exist_ok=True)

for name, packed in MODULES.items():

    (HERE / name).write_bytes(base64.b64decode(packed))

sys.path.insert(0, str(HERE))

for name in list(sys.modules):

    if name in ("from_mixamo", "nik_blender"):
        del sys.modules[name]

import from_mixamo
import nik_blender

# ------------------------------------------------------- the character

BLEND = HOME / "Nik.blend"

# What Nik.blend was made from, written down beside it. A .blend built
# by an older notebook, or from a different character, is not the one
# these settings ask for - and finding that out from a mangled name in
# the render is too late.
RECIPE = f"{BUILD} | {MIXAMO} | {CHARACTER} | {MOVEMENTS} | {CHILD}"

STAMP = HOME / "Nik.blend.made"

BEFORE = STAMP.read_text(encoding="utf-8") if STAMP.exists() else ""

if BLEND.exists() and not REBUILD and BEFORE != RECIPE:

    print(f"\nNik.blend was made by:\n    {BEFORE or 'an older notebook'}"
          f"\nand these settings say:\n    {RECIPE}\nso it is being "
          f"made again.")

if REBUILD or not BLEND.exists() or BEFORE != RECIPE:

    downloads = HOME / MIXAMO

    if not downloads.exists():

        near = (", ".join(sorted(path.name for path in HOME.iterdir()))
                if HOME.exists() else "")

        raise SystemExit(
            f"No {downloads}.\n\n"
            "Download a character pack - CC0, from quaternius.com - and "
            "put it in\nthere. The zip goes in unzipped and whole; "
            "subfolders are read.\n\n"
            + (f"What is in {HOME}: {near}" if near
               else f"{HOME} is empty, or is not the right folder.")
        )

    found = from_mixamo.model_files(downloads, CHARACTER)

    if not found:
        raise SystemExit(f"No .fbx, .glb or .gltf anywhere under "
                         f"{downloads}.")

    if len(found) > 1:

        print(f"\n{len(found)} character file(s) in there. Taking: "
              f"{found[0].stem}")

        if not CHARACTER:
            print("   CHARACTER = \"<part of a file name>\" picks a "
                  "different one. Some of\n   the others: "
                  + ", ".join(sorted(path.stem for path in found[1:])[:24]))

    print(f"\nBuilding {BLEND.name}:")

    library = HOME / MOVEMENTS if MOVEMENTS else ""

    if library and not Path(library).exists():
        raise SystemExit(f"No {library}. MOVEMENTS names a folder "
                         f"inside {HOME}.")

    from_mixamo.build(downloads, BLEND, CHARACTER, library, CHILD)

    STAMP.write_text(RECIPE, encoding="utf-8")

else:
    print(f"\n{BLEND.name} is already there, made by these same "
          f"settings.\n            REBUILD = True to make it again "
          f"anyway - after putting a new\n            file in one of "
          f"the folders.")

# ------------------------------------------------------------ the shots

script = None

for where in ("input", "Input"):

    script = next((path for path in (HOME / where).glob("*.txt")
                   if not path.stem.lower().startswith("lyric")), None)

    if script:
        break

if script is None:
    raise SystemExit(
        f"No script.txt in {HOME}/input.\n\n"
        "It is the same one the AI notebook uses - one scene a line."
    )

print(f"\nScript    : {script}")

lines = nik_blender.scenes_in(script)

print(f"Scenes    : {len(lines)}")

if FIRST_ONLY:

    short = HERE / "first.txt"

    short.write_text("\n".join(lines[:FIRST_ONLY]) + "\n",
                     encoding="utf-8")

    script = short

    print(f"            only the first {FIRST_ONLY} - FIRST_ONLY = 0 "
          f"for all of them")

# ---------------------------------------------------------- the render

INTO.mkdir(parents=True, exist_ok=True)

print()

nik_blender.render(
    BLEND, script, INTO,
    width=WIDTH, height=HEIGHT,
    seconds=CLIP_SECONDS, engine=ENGINE,
)

made = sorted(INTO.glob("Scene*.mp4"))

print(f"\n{len(made)} clip(s) in {INTO}")

# --------------------------------------------------- how much they move


def motion_of(video):
    """The same measure the AI notebook prints, so the two compare."""

    reading = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vf",
         "scale=160:90,format=gray,tblend=all_mode=difference,"
         "signalstats,metadata=print:file=-",
         "-f", "null", os.devnull],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )

    scores = [float(row.rsplit("=", 1)[-1])
              for row in (reading.stdout or "").splitlines()
              if "signalstats.YAVG" in row]

    scores = scores[1:] or scores

    return sum(scores) / len(scores) if scores else 0.0


if made:

    print("\nMovement, clip by clip:")

    for clip in made[:8]:
        print(f"  {clip.stem:<10} {motion_of(clip):.2f}")

    print("\n  For comparison: the AI clips measured 3 to 5. Anything "
          "under 1 is a\n  character standing still, and means the "
          "movement that line asked for\n  is not in the pack.")

try:
    from IPython.display import Video, display

    if made:
        display(Video(str(made[0]), embed=True, width=640))

except Exception:
    pass

print("\n\nNext: open NikStudio_Animate.ipynb and set")
print('    SOURCE = "clips"')
print('    RUN    = "video"')
print("\nIt will cut the video from these - beat cut, words on screen, "
      "the song,\nthe preview. Nothing is generated.")
