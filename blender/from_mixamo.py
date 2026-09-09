"""
Nik Studio - build a .blend out of downloaded character files.

    python blender/from_mixamo.py Downloads/ Nik.blend
    python blender/from_mixamo.py Downloads/ Nik.blend Boy
    python blender/from_mixamo.py Downloads/ Nik.blend Boy Animations/

So that nobody has to open Blender.

The folder is searched all the way down, so an unzipped pack can go in
whole - the FBX/ and glTF/ folders inside it do not have to be dug out.

A third argument is part of a file name, and picks which character to
use when a pack has fifty of them. Without it, the first one by name.

A fourth is a second folder, read for movements only. Character packs
are built for games and ship death and punching; a nursery rhyme needs
clapping and waving, which come from an animation library instead.

It takes .fbx, .glb and .gltf, and it does not care which way the
animations arrive:

  ONE FILE PER MOVEMENT      how Mixamo hands them over. The file name
                             becomes the action name.

  ONE FILE, MANY MOVEMENTS   how the CC0 character packs ship -
                             Quaternius, Kenney. The names inside the
                             file are used, mapped to ours where they
                             are recognisable.

Mixamo is still there and still free, but Adobe has not updated it in
years and its support calls it unsupported, so it is worth knowing it
is not the only door.

WHAT TO PUT IN THE FOLDER
-------------------------
Either a character pack with its animations in one file, or, from
mixamo.com with a free account:

  1. A character, downloaded with NO animation ("T-Pose"). Name the
     file for the character, anything you like.

  2. One FBX per movement, downloaded WITH SKIN off ("Without Skin" is
     smaller and imports faster, but either works). Name each file for
     the movement, because the file name becomes the action name and
     the action name is what the script matches on:

         idle.fbx      required - what plays for a line with no verb
         clap.fbx      wave.fbx     jump.fbx     walk.fbx
         sway.fbx      point.fbx    crouch.fbx   nod.fbx    spin.fbx

     Mixamo calls them other things - "Clapping", "Waving", "Jumping".
     Rename the files. That is the whole of the naming work.

The character is whichever file has a mesh in it. Everything else is
read for its animation and thrown away.
"""

import re
import sys
from pathlib import Path

import bpy

# The renderer knows how a character is measured and what "part of the
# character" means; there is no reason for two answers to that.
from nik_blender import span_of, worn_by


# Where the three cameras sit, relative to a character about 1.6 units
# tall standing at the origin, and how much of them each one holds.
# What the world calls a movement, and what we call it. Anything not
# in here keeps its own name lowercased, which is usually fine - the
# script is matched on the verb, not on this list.
ALIASES = {
    "breathing idle": "idle", "idle": "idle", "standing": "idle",
    "clapping": "clap", "clap": "clap", "applaud": "clap",
    "waving": "wave", "wave": "wave", "hello": "wave",
    "jumping": "jump", "jump": "jump", "jumping up": "jump",
    "walking": "walk", "walk": "walk", "running": "walk", "run": "walk",
    "dancing": "sway", "dance": "sway", "samba dancing": "sway",
    "swaying": "sway", "sway": "sway",
    "pointing": "point", "point": "point",
    "crouching": "crouch", "crouch": "crouch", "sitting": "crouch",
    "sit": "crouch", "kneeling": "crouch", "sit down": "crouch",
    "sitdown": "crouch",
    # What the game packs call things. A nursery rhyme has no word for
    # "victory", but a victory pose is arms up and cheering, which is
    # the nearest thing they ship to a clap.
    "victory": "clap", "cheer": "clap", "cheering": "clap",
    "celebrate": "clap", "yes": "nod",
    "nodding": "nod", "nod": "nod",
    "spinning": "spin", "spin": "spin", "turning": "turn",
}


# Words that are the exporter talking, not the movement. Matched
# whole, or as the tail of a word: Blender's FBX importer writes
# "CharacterArmature|CharacterArmature|Idle", and "characterarmature"
# is one word, so looking for "armature" on its own finds nothing.
NOISE = {"action", "mixamo", "com", "take", "root", "avatar", "anim",
         "animation", "clip", "default"}

TAILS = ("armature", "rig", "skeleton")


def plain_name(name):
    """Their name with the exporter's decoration off. May be empty."""

    # Blender adds ".001" when a name is taken. Off first, so that it
    # is not mistaken for a word.
    plain = re.sub(r"\.\d+$", "", name.strip())

    words = []

    for word in re.split(r"[|_\-. ]+", plain):

        if not word or word.isdigit():
            continue

        low = word.lower()

        if low in NOISE or low.endswith(TAILS):
            continue

        # "SitDown" is two words. The split has to happen after the
        # noise check, so that "CharacterArmature" is still one word
        # and can be thrown away whole.
        for piece in re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", word).split():

            piece = piece.lower()

            if words and piece == words[-1]:
                continue

            words.append(piece)

    return " ".join(words)


def our_name_for(name):
    """Their name for a movement -> ours."""

    plain = plain_name(name)

    return ALIASES.get(plain, plain or "idle")


KNOWN = set(ALIASES.values())


def stated_movement(name):
    """
    The movement this name says outright, or "" if it says none.

    Mixamo calls every single download "mixamo.com", which says
    nothing, and the file name has to speak instead. A pack that calls
    its action "Idle" has already said it, and the file name -
    "Tall.glb", "BaseCharacter.fbx" - must not talk over it.
    """

    plain = plain_name(name)

    if not plain:
        return ""

    ours = ALIASES.get(plain, plain)

    return ours if ours in KNOWN else ""


def first_word(stem):
    """The leading word of a file name, which is usually who it is."""

    parts = [part for part in re.split(r"[|_\-. ]+", stem.strip()) if part]

    return parts[0].lower() if parts else ""


def without(stem, word):
    """The same name with that leading word taken off."""

    parts = [part for part in re.split(r"[|_\-. ]+", stem.strip()) if part]

    if parts and parts[0].lower() == word and len(parts) > 1:
        parts = parts[1:]

    return " ".join(parts) or stem


def a_movement(stem):
    """True if the file is named for a movement we know."""

    return our_name_for(stem) in set(ALIASES.values())


# What each camera is for, and how it is worked out rather than
# guessed: a lens, how much of the frame's height the character should
# fill, and how far up the character to look. The distance follows from
# those and from how tall the character turns out to be, which is not
# known until the file is opened - a pack that imports four units tall
# was being framed by the knees.
CAMERAS = {
    "Cam_Wide":   (35.0, 0.50, 0.55),
    "Cam_Medium": (50.0, 0.75, 0.55),
    "Cam_Close":  (85.0, 2.20, 0.88),
}

# The sky. Workbench paints it flat, EEVEE lights the character with
# it, and black behind a dark character is why the first clips looked
# like a silhouette in a cave.
SKY = (0.53, 0.75, 0.95)


def clear():
    """An empty file, including the datablocks nothing points at."""

    bpy.ops.wm.read_factory_settings(use_empty=True)


READABLE = (".fbx", ".glb", ".gltf")


def model_files(folder, wanted=""):
    """
    The character files in a folder and everything under it.

    A downloaded pack is a zip, and a zip unpacks into folders - FBX/,
    glTF/, Blend/ - so looking only at the top level finds nothing.

    `wanted` is part of a file name. Anything matching it is put first,
    which is how a pack of fifty characters is told which one is ours:
    the character is the first file with a body in it.
    """

    low = wanted.strip().lower()

    found = [path for path in Path(folder).rglob("*")
             if path.suffix.lower() in READABLE
             and not any(part.startswith("__") for part in path.parts)]

    return sorted(
        found,
        key=lambda path: (0 if low and low in path.name.lower() else 1,
                          str(path).lower()),
    )


def bring_in(path):
    """
    Import one file and say what arrived.

    Returns (objects, armature, actions) - every action the file
    brought, which is one for a Mixamo download and several for a
    character pack.
    """

    before = set(bpy.data.objects)

    known = set(bpy.data.actions)

    if path.suffix.lower() == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))

    arrived = [item for item in bpy.data.objects if item not in before]

    rig = next((item for item in arrived if item.type == "ARMATURE"), None)

    # Every action the file brought, not just the one currently
    # playing: a pack ships several and only one of them is assigned.
    actions = [act for act in bpy.data.actions if act not in known]

    return arrived, rig, actions


def has_mesh(objects):
    """A character comes with a body; an animation does not have to."""

    return any(item.type == "MESH" for item in objects)


def place(camera, target, low, tall, wide=16, high=9):
    """
    Put one camera where its whole subject fits.

    The lens and the fraction of the frame to fill are on the camera
    already; what is left is arithmetic. A camera sees, at distance d,
    a height of d * sensor / lens - so to show `tall / fill` of world,
    stand back by that much times lens over sensor.
    """

    lens = camera.data.lens

    fill = camera.get("fill", 0.75)

    look = camera.get("aim", 0.55)

    # Blender fits the 36mm sensor across the longer side of the image,
    # so on a landscape frame the height of it is the smaller share.
    sensor = 36.0 * min(1.0, high / wide)

    away = (tall / fill) * lens / sensor

    up = low + tall * look

    camera.location = (0.0, -away, up)

    target.location = (0.0, 0.0, up)


def build_cameras(low=0.0, tall=1.6):
    """Three cameras, each aimed at what it is for."""

    made = []

    for name, (lens, fill, look) in CAMERAS.items():

        camera = bpy.data.cameras.new(name)

        camera.lens = lens

        thing = bpy.data.objects.new(name, camera)

        bpy.context.scene.collection.objects.link(thing)

        thing["fill"] = fill

        thing["aim"] = look

        # Its own target, because a close-up looks at the face and a
        # wide shot looks at the middle, and one shared point cannot be
        # both.
        aim = bpy.data.objects.new(f"{name}_Target", None)

        bpy.context.scene.collection.objects.link(aim)

        # Pointed by a constraint rather than by arithmetic, so moving
        # a camera in Blender later keeps it aimed.
        track = thing.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        place(thing, aim, low, tall)

        made.append(thing)

    return made


def build(folder, target, wanted="", movements=""):
    """
    A folder of downloads -> one .blend the renderer can use.

    `movements` is a second folder, read for its animations only. A
    character pack ships the movements a game wants - death, punch,
    sword slash - and a nursery rhyme wants clapping and waving, which
    come from an animation library instead. Whatever is in there is
    taken as a movement whether it has a body attached or not.
    """

    files = model_files(folder, wanted)

    library = model_files(movements) if movements else []

    if not files:
        raise SystemExit(
            f"No .fbx, .glb or .gltf files in {folder}.\n\n"
            "Download a character - with its animations, or with one "
            "file each - and\nput them there."
        )

    clear()

    character = None

    # The leading word of the character's file name. In a pack that
    # gives one file per movement per character - Astronaut_Idle.fbx,
    # Astronaut_Walk.fbx - it is what says which files are still ours.
    family = ""

    # And the folder it was found in. A pack that gives every character
    # its own folder names the files inside them for the movement only
    # - Astronaut/Walk.fbx, Boy/Walk.fbx - so the folder is the only
    # thing that says whose walk it is.
    home = None

    kept = {}

    def keep(action, called):
        """Name an action ours, without treading on one already kept."""

        name = our_name_for(called)

        if name in kept:

            number = 2

            while f"{name}{number}" in kept:
                number += 1

            name = f"{name}{number}"

        action.name = name

        action.use_fake_user = True

        kept[name] = action

        return name

    for path in files:

        arrived, rig, actions = bring_in(path)

        if character is None and rig and has_mesh(arrived):

            character = rig

            character.name = "Rig"

            family = first_word(path.stem)

            home = path.parent

            if len(actions) == 1:

                # One movement in the character's own file. Whichever
                # of the two names actually names a movement wins.
                only = actions[0]

                named = [keep(only, only.name if stated_movement(only.name)
                              else without(path.stem, family))]

            else:
                named = [keep(action, action.name) for action in actions]

            print(f"  {path.name}: the character"
                  + (f", and {len(named)} movement(s): "
                     + ", ".join(sorted(named)) if named else ""))

            # A file that arrived with a body AND its own movements is a
            # whole character in one file, which is how the CC0 packs
            # ship. The rest of the folder is then forty-nine OTHER
            # characters, not more movements for this one, and their
            # actions are posed for their own skeletons.
            if len(named) > 1 and len(files) > 1:

                print(f"            {len(files) - 1} other file(s) in "
                      f"the folder are other characters -\n"
                      f"            ignored. To use one of those "
                      f"instead, pass part of its\n"
                      f"            file name as the third argument.")

                break

            continue

        ours = path.parent == home and (a_movement(path.stem)
                                        or first_word(path.stem) == family)

        if has_mesh(arrived) and not ours:

            # It brought its own body and its name says nothing about
            # ours, so it is one of the other forty-nine characters in
            # the pack. Its animations are posed for its own skeleton.
            print(f"  {path.name}: another character - skipped")

            for item in arrived:
                bpy.data.objects.remove(item, do_unlink=True)

            continue

        if not actions:

            print(f"  {path.name}: nothing animated in it - skipped")

        elif len(actions) == 1:

            # One movement in the file. This is the Mixamo case, where
            # the name inside is always "mixamo.com" and the file name
            # is the only one saying anything.
            only = actions[0]

            name = keep(only, only.name if stated_movement(only.name)
                        else without(path.stem, family))

            print(f"  {path.name}: '{name}'")

        else:

            named = [keep(action, action.name) for action in actions]

            print(f"  {path.name}: {len(named)} movement(s): "
                  + ", ".join(sorted(named)))

        # The rig that came with the animations has served its purpose.
        for item in arrived:
            bpy.data.objects.remove(item, do_unlink=True)

    for path in library:

        arrived, rig, actions = bring_in(path)

        if not actions:

            print(f"  {path.name}: nothing animated in it - skipped")

        elif len(actions) == 1:

            print(f"  {path.name}: '{keep(actions[0], path.stem)}'")

        else:

            named = [keep(action, action.name) for action in actions]

            print(f"  {path.name}: {len(named)} movement(s): "
                  + ", ".join(sorted(named)))

        # Only the animation was wanted; the body it arrived on is a
        # mannequin and goes.
        for item in arrived:
            bpy.data.objects.remove(item, do_unlink=True)

    if character is None:
        raise SystemExit(
            "None of those files has a body in it.\n\n"
            "One of them has to be the character. From Mixamo that is "
            "the T-Pose\ndownload; from a character pack it is usually "
            "the only file."
        )

    # An importer leaves things behind - a node it could not place, a
    # mannequin's stray part. Anything that is not the character and
    # does not hang off the character is not wanted in the shot.
    strays = [item for item in bpy.data.objects
              if item is not character and not worn_by(item, character)]

    for item in strays:
        bpy.data.objects.remove(item, do_unlink=True)

    if strays:
        print(f"  {len(strays)} stray object(s) the importer left - "
              f"removed")

    low, high = span_of(character)

    tall = max(0.5, high - low)

    build_cameras(low, tall)

    bpy.ops.object.light_add(type="SUN", location=(3.0 * tall, -4.0 * tall,
                                                   6.0 * tall))

    if bpy.context.scene.world is None:
        bpy.context.scene.world = bpy.data.worlds.new("World")

    bpy.context.scene.world.color = SKY

    bpy.ops.mesh.primitive_plane_add(size=40.0 * tall,
                                     location=(0.0, 0.0, 0.0))

    bpy.context.active_object.name = "Ground"

    scene = bpy.context.scene

    scene.render.fps = 24

    scene.camera = bpy.data.objects.get("Cam_Medium")

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"

    target = Path(target)

    target.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.save_as_mainfile(filepath=str(target))

    print(f"\n{target}")
    print(f"  character : {character.name}, {tall:.2f} units tall "
          f"(from {low:.2f} to {high:.2f})")
    print(f"  actions   : {len(kept)} ({', '.join(sorted(kept)) or 'none'})")
    print(f"  cameras   : {', '.join(CAMERAS)}")

    if "idle" not in kept:
        print("\n  ! No 'idle'. It is the one that plays for a line "
              "with no verb in it.\n    Rename one of the above to "
              "idle, or download a standing one.")

    return target


def main(argv):

    if len(argv) < 2:
        raise SystemExit(__doc__.strip())

    build(argv[0], argv[1],
          argv[2] if len(argv) > 2 else "",
          argv[3] if len(argv) > 3 else "")

    return 0


if __name__ == "__main__":

    argv = sys.argv[1:]

    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]

    raise SystemExit(main(argv))
