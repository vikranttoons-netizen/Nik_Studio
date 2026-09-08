"""
Nik Studio - build a .blend out of Mixamo downloads.

    python blender/from_mixamo.py Mixamo/ Nik.blend

So that nobody has to open Blender.

WHAT TO PUT IN THE FOLDER
-------------------------
From mixamo.com, free account, everything free for commercial use:

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

import sys
from pathlib import Path

import bpy


# Where the three cameras sit, relative to a character about 1.6 units
# tall standing at the origin, and how much of them each one holds.
CAMERAS = {
    "Cam_Wide":   ((0.0, -7.0, 1.6), 0.8),
    "Cam_Medium": ((0.0, -4.2, 1.4), 1.1),
    "Cam_Close":  ((0.0, -1.9, 1.45), 1.5),
}


def clear():
    """An empty file, including the datablocks nothing points at."""

    bpy.ops.wm.read_factory_settings(use_empty=True)


def fbx_files(folder):
    """The .fbx in a folder, in a sensible order."""

    return sorted(
        (path for path in Path(folder).iterdir()
         if path.suffix.lower() == ".fbx"),
        key=lambda path: path.name.lower(),
    )


def bring_in(path):
    """
    Import one FBX and say what arrived.

    Returns (objects, armature, action) - the action being whatever
    animation came with it, or None for a plain T-pose character.
    """

    before = set(bpy.data.objects)

    bpy.ops.import_scene.fbx(filepath=str(path))

    arrived = [item for item in bpy.data.objects if item not in before]

    rig = next((item for item in arrived if item.type == "ARMATURE"), None)

    action = None

    if rig and rig.animation_data and rig.animation_data.action:
        action = rig.animation_data.action

    return arrived, rig, action


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
    """A folder of Mixamo downloads -> one .blend the renderer can use."""

    files = fbx_files(folder)

    if not files:
        raise SystemExit(
            f"No .fbx files in {folder}.\n\n"
            "Download a character and its movements from mixamo.com and "
            "put them there."
        )

    clear()

    character = None

    kept = {}

    for path in files:

        arrived, rig, action = bring_in(path)

        wanted = path.stem.lower()

        if character is None and rig and has_mesh(arrived):

            character = rig

            character.name = "Rig"

            if action:
                action.name = wanted
                kept[wanted] = action

            print(f"  {path.name}: the character"
                  + (f", and a '{wanted}' action" if action else ""))

            continue

        if action:

            action.name = wanted

            action.use_fake_user = True

            kept[wanted] = action

            print(f"  {path.name}: '{wanted}'")

        else:
            print(f"  {path.name}: nothing animated in it - skipped")

        # The rig that came with the animation has served its purpose.
        for item in arrived:
            bpy.data.objects.remove(item, do_unlink=True)

    if character is None:
        raise SystemExit(
            "None of those files has a body in it.\n\n"
            "One of them has to be the character, downloaded from Mixamo "
            "as a T-Pose."
        )

    for action in kept.values():
        action.use_fake_user = True

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
        print("\n  ! No 'idle'. It is the one that plays for a line with "
              "no verb in it,\n    so download one and call the file "
              "idle.fbx.")

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
