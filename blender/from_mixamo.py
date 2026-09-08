"""
Nik Studio - build a .blend out of downloaded character files.

    python blender/from_mixamo.py Downloads/ Nik.blend

So that nobody has to open Blender.

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
    "sit": "crouch", "kneeling": "crouch",
    "nodding": "nod", "nod": "nod", "yes": "nod",
    "spinning": "spin", "spin": "spin", "turning": "turn",
}


def our_name_for(name):
    """Their name for a movement -> ours."""

    plain = name.strip().lower()

    # Every exporter decorates the name. Mixamo calls a single download
    # "mixamo.com"; the FBX importer writes "Armature|Walk"; the glTF
    # importer writes "Walk_Armature"; Blender adds ".001" when a name
    # is taken. None of that is the movement.
    plain = re.sub(r"\.\d+$", "", plain)

    plain = re.sub(r"[|_\-.]+", " ", plain)

    plain = re.sub(r"\b(armature|rig|action|mixamo com|take \d+)\b",
                   " ", plain)

    plain = " ".join(plain.split())

    return ALIASES.get(plain, plain or "idle")


CAMERAS = {
    "Cam_Wide":   ((0.0, -7.0, 1.6), 0.8),
    "Cam_Medium": ((0.0, -4.2, 1.4), 1.1),
    "Cam_Close":  ((0.0, -1.9, 1.45), 1.5),
}


def clear():
    """An empty file, including the datablocks nothing points at."""

    bpy.ops.wm.read_factory_settings(use_empty=True)


READABLE = (".fbx", ".glb", ".gltf")


def model_files(folder):
    """The character files in a folder, in a sensible order."""

    return sorted(
        (path for path in Path(folder).iterdir()
         if path.suffix.lower() in READABLE),
        key=lambda path: path.name.lower(),
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


def build_cameras(height=1.6):
    """Three cameras, all looking at the character."""

    aim = bpy.data.objects.new("Cam_Target", None)

    bpy.context.scene.collection.objects.link(aim)

    aim.location = (0.0, 0.0, height * 0.55)

    for name, (where, zoom) in CAMERAS.items():

        camera = bpy.data.cameras.new(name)

        camera.lens = 50.0 * zoom

        made = bpy.data.objects.new(name, camera)

        bpy.context.scene.collection.objects.link(made)

        made.location = (where[0], where[1], where[2] * height / 1.6)

        # Pointed by a constraint rather than by arithmetic, so moving
        # a camera in Blender later keeps it aimed.
        track = made.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

    return aim


def build(folder, target):
    """A folder of downloads -> one .blend the renderer can use."""

    files = model_files(folder)

    if not files:
        raise SystemExit(
            f"No .fbx, .glb or .gltf files in {folder}.\n\n"
            "Download a character - with its animations, or with one "
            "file each - and\nput them there."
        )

    clear()

    character = None

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

            named = [keep(action, action.name) for action in actions]

            print(f"  {path.name}: the character"
                  + (f", and {len(named)} movement(s): "
                     + ", ".join(sorted(named)) if named else ""))

            continue

        if not actions:

            print(f"  {path.name}: nothing animated in it - skipped")

        elif len(actions) == 1:

            # One movement in the file, so the file name is what it is
            # called. This is the Mixamo case, where the name inside is
            # always "mixamo.com".
            name = keep(actions[0], path.stem)

            print(f"  {path.name}: '{name}'")

        else:

            named = [keep(action, action.name) for action in actions]

            print(f"  {path.name}: {len(named)} movement(s): "
                  + ", ".join(sorted(named)))

        # The rig that came with the animations has served its purpose.
        for item in arrived:
            bpy.data.objects.remove(item, do_unlink=True)

    if character is None:
        raise SystemExit(
            "None of those files has a body in it.\n\n"
            "One of them has to be the character. From Mixamo that is "
            "the T-Pose\ndownload; from a character pack it is usually "
            "the only file."
        )

    tall = max(0.5, character.dimensions.z or 1.6)

    build_cameras(tall)

    bpy.ops.object.light_add(type="SUN", location=(3.0, -4.0, 6.0))

    bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0.0, 0.0, 0.0))

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
    print(f"  character : {character.name}, {tall:.2f} units tall")
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

    build(argv[0], argv[1])

    return 0


if __name__ == "__main__":

    argv = sys.argv[1:]

    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]

    raise SystemExit(main(argv))
