"""
Checks the Blender half: the template, the script mapping, the render.

The AI video models could not hold the character still between clips and
could not be told what to do. A rigged character can do both. This tests
the part that drives it - everything after, the beat cut and the song
and the encode, is the pipeline that already exists.

Needs the `bpy` package (`pip install bpy`). No GPU: the render is done
with Workbench, which is flat and fast and proves the shots come out
right rather than how they look.

Run from the project root:

    python tests/test_blender.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "blender"))

try:
    import bpy                                        # noqa: F401
except ImportError:
    raise SystemExit(
        "bpy is not installed, so the Blender half cannot be tested.\n"
        "    pip install bpy"
    )

import nik_blender                                    # noqa: E402


def heading(text):
    print()
    print("=" * 68)
    print(text)
    print("=" * 68)


SCRIPT = """\
He walks into the meadow, the puppy watches him curiously, butterflies drift above the flowers, the camera does not move
He waves toward the puppy, the puppy wags its tail, leaves sway gently overhead, the camera does not move
Close up of the puppy barking cheerfully, Nik stands nearby, flowers nod in the breeze, the camera does not move
He crouches down and holds out one hand, the kitten bounces happily towards it, clouds drift slowly overhead, the camera does not move
Wide shot of Nik sitting with the animals, the puppy, kitten and duckling cuddle beside him, leaves sway gently, the camera does not move
"""


# ======================================================================

def test_template_keeps_its_actions(root):

    heading("1  The template has everything the tool asks of a .blend")

    blend = nik_blender.template(root / "Nik_Template.blend")

    assert blend.exists(), blend

    # Re-opened, because the question is what survived being saved.
    bpy.ops.wm.open_mainfile(filepath=str(blend))

    actions = sorted(action.name for action in bpy.data.actions)
    cameras = sorted(o.name for o in bpy.data.objects if o.type == "CAMERA")

    print(f"   actions: {actions}")
    print(f"   cameras: {cameras}")

    wanted = sorted({name for name, _ in nik_blender.ACTIONS}
                    | {nik_blender.FALLBACK_ACTION})

    # Blender discards actions nothing is using the moment the file is
    # saved. Ten were built and one survived, until use_fake_user.
    assert actions == wanted, (actions, wanted)

    assert cameras == ["Cam_Close", "Cam_Medium", "Cam_Wide"], cameras

    rig = nik_blender.armature_in()

    assert nik_blender.check(rig) == [], nik_blender.check(rig)

    print("\n   [OK] ten actions and three cameras, and nothing to complain of")


def test_the_line_chooses_the_movement(root):

    heading("2  The movement comes from what he does, not the scenery")

    for line, action, camera in [
        ("He walks into the meadow, the puppy watches him",
         "walk", "Cam_Medium"),
        ("He waves toward the puppy, leaves sway gently",
         "wave", "Cam_Medium"),

        # The trap. "flowers nod in the breeze" was making the boy nod,
        # and the shot is not even of him.
        ("Close up of the puppy barking, Nik stands nearby, "
         "flowers nod in the breeze",
         "idle", "Cam_Close"),

        # Two verbs in one clause: the first is what it is about.
        ("He crouches down and holds out one hand, the kitten bounces",
         "crouch", "Cam_Medium"),

        ("Wide shot of Nik sitting with the animals, leaves sway",
         "crouch", "Cam_Wide"),
    ]:
        got = nik_blender.action_for(line)
        framing = nik_blender.camera_for(line)

        print(f"   {got:<7} {framing:<11} {line.split(',')[0][:44]}")

        assert got == action, (line, got, action)
        assert framing == camera, (line, framing, camera)

    print("\n   [OK] the scenery cannot hijack the action")


def test_renders_a_clip_per_scene(root):

    heading("3  One line of the script, one clip")

    blend = root / "Nik_Template.blend"

    script = root / "script.txt"
    script.write_text(SCRIPT, encoding="utf-8")

    clips = root / "Clips"

    made = nik_blender.render(
        blend, script, clips,
        width=320, height=180,
        engine="BLENDER_WORKBENCH",
    )

    print()

    for entry in made:
        print(f"   {entry['scene']:<13} {entry['action']:<7} "
              f"{entry['camera']:<11} {entry['frames']:>3} frames")

    assert len(made) == 5, made

    for number in range(1, 6):
        clip = clips / f"Scene{number:02d}.mp4"
        assert clip.exists() and clip.stat().st_size > 0, clip

    # The close up of the puppy is the third line, and it is a close up.
    assert made[2]["camera"] == "Cam_Close", made[2]

    # It asks for no movement of its own, so it asks for 'idle' - and
    # since the template's idle barely moves, something that does is
    # put in its place and says what it stood in for. A shot held on a
    # motionless character for four seconds is the thing being fixed.
    assert "idle" in made[2]["action"], made[2]

    written = json.loads((clips / "rendered.json").read_text(encoding="utf-8"))

    assert written == made, "rendered.json does not match what was returned"

    print("\n   [OK] five clips, each with the movement its line asked for")


def test_says_what_is_missing(root):

    heading("4  A .blend that is not ready says so, all at once")

    nik_blender.clear()

    bpy.ops.object.armature_add()

    rig = bpy.context.active_object

    problems = nik_blender.check(rig)

    for problem in problems:
        print(f"   ! {problem.splitlines()[0][:62]}")

    # No actions and no cameras: it should name every one of them, not
    # stop at the first, or fixing it means opening Blender five times.
    assert any("idle" in p for p in problems), problems
    assert any("Cam_Wide" in p for p in problems), problems
    assert any("Cam_Close" in p for p in problems), problems
    assert any("Cam_Medium" in p for p in problems), problems

    print("\n   [OK] every missing piece named in one go")


def test_an_unrigged_file_is_refused(root):

    heading("5  A mesh with no rig cannot be animated, and it says why")

    nik_blender.clear()

    bpy.ops.mesh.primitive_uv_sphere_add()

    try:
        nik_blender.armature_in()
    except SystemExit as stop:
        print("  ", str(stop).splitlines()[0])
        assert "rigged" in str(stop), stop
    else:
        raise AssertionError("a file with no armature was accepted")

    print("\n   [OK] refused, and said what is missing")


# ======================================================================

def make_fbx(folder):
    """
    Real FBX files, exported by Blender itself.

    Not a stand-in: from_mixamo.py has to survive an actual import, and
    an import is most of what it does.
    """

    import bpy

    folder.mkdir(parents=True, exist_ok=True)

    def fresh():
        bpy.ops.wm.read_factory_settings(use_empty=True)

    # The character: a rig with a body on it, and no animation, which
    # is what Mixamo calls a T-Pose download.
    fresh()

    bpy.ops.object.armature_add(location=(0, 0, 0))

    rig = bpy.context.active_object

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.8, location=(0, 0, 0.9))

    bpy.context.active_object.parent = rig

    bpy.ops.export_scene.fbx(filepath=str(folder / "nik_character.fbx"))

    # The movements: a rig each, animated, no body.
    for name, lift in (("idle", 0.05), ("clap", 0.2), ("jump", 0.9)):

        fresh()

        bpy.ops.object.armature_add(location=(0, 0, 0))

        made = bpy.context.active_object

        made.animation_data_create()

        made.animation_data.action = bpy.data.actions.new("Take 001")

        for frame, height in ((1, 0.0), (12, lift), (24, 0.0)):
            made.location.z = height
            made.keyframe_insert("location", frame=frame)

        bpy.ops.export_scene.fbx(filepath=str(folder / f"{name}.fbx"))

    return folder


def test_a_folder_of_downloads_becomes_a_blend(root):

    heading("6  A folder of Mixamo downloads becomes a .blend")

    import from_mixamo

    folder = make_fbx(root / "Mixamo")

    made = from_mixamo.build(folder, root / "FromMixamo.blend")

    assert made.exists(), "no .blend was written"

    import bpy

    bpy.ops.wm.open_mainfile(filepath=str(made))

    actions = {action.name for action in bpy.data.actions}

    cameras = {item.name for item in bpy.data.objects
               if item.type == "CAMERA"}

    print(f"   actions : {', '.join(sorted(actions))}")
    print(f"   cameras : {', '.join(sorted(cameras))}")

    # The file name is the action name, because the action name is what
    # a line of the script is matched against. That is the whole of the
    # naming work anybody has to do.
    assert {"idle", "clap", "jump"} <= actions, actions

    assert cameras == {"Cam_Wide", "Cam_Medium", "Cam_Close"}, cameras

    # One armature, the one with the body on it. The rigs that came
    # attached to the animations are gone.
    rigs = [item for item in bpy.data.objects if item.type == "ARMATURE"]

    assert len(rigs) == 1, [r.name for r in rigs]

    print(f"   one rig : {rigs[0].name}")

    # Fake users, or Blender drops an action nothing is playing the
    # moment the file is saved.
    assert all(bpy.data.actions[name].use_fake_user
               for name in ("idle", "clap", "jump"))

    # And it renders, which is the only thing that matters.
    script = root / "mixamo.txt"

    script.write_text("He claps his hands twice\n"
                      "He jumps up and down twice\n", encoding="utf-8")

    nik_blender.render(
        made,
        script,
        root / "MixamoClips",
        width=160, height=90, seconds=1.0, engine="BLENDER_WORKBENCH",
    )

    clips = sorted((root / "MixamoClips").glob("Scene*.mp4"))

    print(f"   rendered: {', '.join(c.name for c in clips)}")

    assert len(clips) == 2, clips

    print("\n   [OK] downloads in, a .blend out, nobody opened Blender")


def test_one_file_with_every_movement_in_it(root):

    heading("8  One file with all the movements in it")

    import bpy, from_mixamo

    folder = root / "Pack"

    folder.mkdir(parents=True, exist_ok=True)

    # How the CC0 character packs ship - Quaternius, Kenney: one file,
    # the character and several animations, each on its own NLA track.
    # Mixamo's one-file-per-movement is the other shape and is already
    # covered; this is the one that needs no account anywhere.
    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.object.armature_add(location=(0, 0, 0))

    rig = bpy.context.active_object

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7, location=(0, 0, 0.9))

    bpy.context.active_object.parent = rig

    rig.animation_data_create()

    for name, lift in (("Idle", 0.05), ("Walk", 0.3), ("Jump", 0.9)):

        action = bpy.data.actions.new(name)

        action.use_fake_user = True

        rig.animation_data.action = action

        for frame, height in ((1, 0.0), (12, lift), (24, 0.0)):
            rig.location.z = height
            rig.keyframe_insert("location", frame=frame)

        track = rig.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 1, action)

        rig.animation_data.action = None

    bpy.ops.export_scene.gltf(filepath=str(folder / "character_pack.glb"),
                              export_format="GLB")

    made = from_mixamo.build(folder, root / "Pack.blend")

    bpy.ops.wm.open_mainfile(filepath=str(made))

    actions = {action.name for action in bpy.data.actions}

    print(f"   actions : {', '.join(sorted(actions))}")

    # The glTF importer calls them "Walk_Armature", the FBX one calls
    # them "Armature|Walk", and Mixamo calls a single download
    # "mixamo.com". None of that is the movement, and the movement is
    # what the script is matched against.
    assert {"idle", "walk", "jump"} <= actions, actions

    print("\n   [OK] one download, no account, every movement named "
          "right")


def test_names_are_cleaned_up(root):

    heading("9  Whatever the exporter called it")

    import from_mixamo

    for given, wanted in (
        ("Armature|Walk", "walk"),
        # What Quaternius's pack actually contained, through Blender's
        # FBX importer. "characterarmature" is one word, so looking for
        # "armature" inside it found nothing and every movement came
        # out called "characterarmature characterarmature idle".
        ("CharacterArmature|CharacterArmature|Idle", "idle"),
        ("CharacterArmature|CharacterArmature|Walk", "walk"),
        ("CharacterArmature|CharacterArmature|SitDown", "crouch"),
        ("CharacterArmature|CharacterArmature|Victory", "clap"),
        ("CharacterArmature|CharacterArmature|SwordSlash", "sword slash"),
        ("Walk_Armature", "walk"),
        ("mixamo.com", "idle"),
        ("Breathing Idle", "idle"),
        ("Samba Dancing", "sway"),
        ("Clapping.001", "clap"),
        ("Waving", "wave"),
        ("Running", "walk"),
        ("twirl", "twirl"),
    ):
        got = from_mixamo.our_name_for(given)

        print(f"   {given:<18} -> {got}")

        assert got == wanted, (given, got, wanted)

    print("\n   [OK] the decoration comes off, the movement stays")


def test_an_unzipped_pack_of_many_characters(root):

    heading("10  A pack of many characters, unzipped, subfolders and all")

    import bpy, from_mixamo

    # What actually arrives: a zip that unpacks into FBX/ and glTF/,
    # with fifty characters in it, each one carrying its own
    # animations. Nothing at the top level, and the other forty-nine
    # are not more movements for ours - their actions are posed for
    # their own skeletons.
    folder = root / "BigPack"

    inside = folder / "glTF"

    inside.mkdir(parents=True, exist_ok=True)

    def a_character(path, lift):

        bpy.ops.wm.read_factory_settings(use_empty=True)

        bpy.ops.object.armature_add(location=(0, 0, 0))

        rig = bpy.context.active_object

        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7,
                                             location=(0, 0, 0.9))

        bpy.context.active_object.parent = rig

        rig.animation_data_create()

        for name in ("Idle", "Walk"):

            action = bpy.data.actions.new(name)

            action.use_fake_user = True

            rig.animation_data.action = action

            for frame, height in ((1, 0.0), (12, lift), (24, 0.0)):
                rig.location.z = height
                rig.keyframe_insert("location", frame=frame)

            track = rig.animation_data.nla_tracks.new()
            track.name = name
            track.strips.new(name, 1, action)

            rig.animation_data.action = None

        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB")

    a_character(inside / "Astronaut.glb", 0.3)
    a_character(inside / "Boy.glb", 0.5)

    # No argument: the first by name, and the other one left alone.
    made = from_mixamo.build(folder, root / "First.blend")

    bpy.ops.wm.open_mainfile(filepath=str(made))

    actions = {action.name for action in bpy.data.actions}

    print(f"   default    : {', '.join(sorted(actions))}")

    assert actions == {"idle", "walk"}, actions

    # Named: the same two movements, but taken from the one asked for.
    made = from_mixamo.build(folder, root / "Chosen.blend", "Boy")

    bpy.ops.wm.open_mainfile(filepath=str(made))

    actions = {action.name for action in bpy.data.actions}

    print(f"   asked 'Boy': {', '.join(sorted(actions))}")

    assert actions == {"idle", "walk"}, actions

    print("\n   [OK] found in subfolders, one character taken, the "
          "rest ignored")


def test_a_folder_with_no_character_is_refused(root):

    heading("7  A folder with no character in it says so")

    import from_mixamo, bpy

    folder = root / "NoBody"

    folder.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.object.armature_add(location=(0, 0, 0))

    bpy.ops.export_scene.fbx(filepath=str(folder / "clap.fbx"))

    try:
        from_mixamo.build(folder, root / "Nothing.blend")

    except SystemExit as stop:
        print("  ", str(stop).splitlines()[0])
        assert "has a body in it" in str(stop), stop

    else:
        raise AssertionError("a folder with no character was accepted")

    print("\n   [OK] refused, and said what to download")


def test_one_file_per_movement_per_character(root):

    heading("11  A pack with a file per movement, per character")

    import bpy, from_mixamo

    # The other shape a big pack comes in, and the dangerous one: every
    # character has a folder, and inside it the files are named for the
    # movement only. "Walk.fbx" appears fifty times, once per character,
    # and every one of those walks is posed for its own skeleton.
    folder = root / "PerMovement"

    def a_clip(path, lift, mesh=True):

        bpy.ops.wm.read_factory_settings(use_empty=True)

        bpy.ops.object.armature_add(location=(0, 0, 0))

        rig = bpy.context.active_object

        if mesh:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7,
                                                 location=(0, 0, 0.9))
            bpy.context.active_object.parent = rig

        rig.animation_data_create()

        action = bpy.data.actions.new("Take 001")

        rig.animation_data.action = action

        for frame, height in ((1, 0.0), (12, lift), (24, 0.0)):
            rig.location.z = height
            rig.keyframe_insert("location", frame=frame)

        path.parent.mkdir(parents=True, exist_ok=True)

        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB")

    a_clip(folder / "Astronaut" / "Idle.glb", 0.05)
    a_clip(folder / "Astronaut" / "Walk.glb", 0.3)
    a_clip(folder / "Astronaut" / "Jump.glb", 0.9)

    # Somebody else's walk, in somebody else's folder.
    a_clip(folder / "Zombie" / "Walk.glb", 0.4)

    made = from_mixamo.build(folder, root / "PerMovement.blend")

    bpy.ops.wm.open_mainfile(filepath=str(made))

    actions = {action.name for action in bpy.data.actions}

    print(f"   actions : {', '.join(sorted(actions))}")

    # One walk, not two. "walk2" would mean the zombie's got in.
    assert actions == {"idle", "walk", "jump"}, actions

    print("\n   [OK] the folder decides whose movement it is")


def test_movements_from_a_second_folder(root):

    heading("12  Movements from a library, character from a pack")

    import bpy, from_mixamo

    # A game character pack ships what a game wants. A nursery rhyme
    # wants clapping and waving, and those come from an animation
    # library built on the same rig - a different folder, read for its
    # movements only, mannequin thrown away.
    pack = root / "GamePack"

    library = root / "Library"

    pack.mkdir(parents=True, exist_ok=True)

    library.mkdir(parents=True, exist_ok=True)

    def a_file(path, names, mesh=True):

        bpy.ops.wm.read_factory_settings(use_empty=True)

        bpy.ops.object.armature_add(location=(0, 0, 0))

        rig = bpy.context.active_object

        if mesh:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7,
                                                 location=(0, 0, 0.9))
            bpy.context.active_object.parent = rig

        rig.animation_data_create()

        for index, name in enumerate(names):

            action = bpy.data.actions.new(name)

            action.use_fake_user = True

            rig.animation_data.action = action

            for frame, height in ((1, 0.0), (12, 0.2 + index * 0.1),
                                  (24, 0.0)):
                rig.location.z = height
                rig.keyframe_insert("location", frame=frame)

            track = rig.animation_data.nla_tracks.new()
            track.name = name
            track.strips.new(name, 1, action)

            rig.animation_data.action = None

        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB")

    a_file(pack / "BaseCharacter.glb", ["Idle", "Jump", "SwordSlash"])

    # The mannequin has a body too, and it must not be mistaken for
    # another character and skipped.
    a_file(library / "Gestures.glb", ["Clapping", "Waving"])

    made = from_mixamo.build(pack, root / "Both.blend",
                             movements=library)

    bpy.ops.wm.open_mainfile(filepath=str(made))

    actions = {action.name for action in bpy.data.actions}

    print(f"   actions : {', '.join(sorted(actions))}")

    assert {"idle", "jump", "clap", "wave"} <= actions, actions

    # One body in the file, not two, and nothing the importer left
    # lying about. Ground is ours and is meant to be there.
    bodies = [item.name for item in bpy.data.objects
              if item.type == "MESH" and item.name != "Ground"]

    print(f"   bodies  : {', '.join(bodies)}")

    assert len(bodies) == 1, bodies

    print("\n   [OK] the game pack lends the body, the library lends "
          "the movements")


def test_a_clip_lasts_as_long_as_the_shot(root):

    heading("13  A short action still fills the shot")

    import bpy, nik_blender

    # A walk cycle is under a second and the shot is nearly three, and
    # what came back was a 0.92 second clip. Holding the last pose for
    # the rest is the standing-still problem again, so the frames
    # repeat instead - and Blender installed with pip cannot write
    # video at all, so ffmpeg makes every clip either way.
    blend = root / "Length.blend"

    nik_blender.template(blend)

    script = root / "one.txt"

    script.write_text(SCRIPT.splitlines()[0] + "\n", encoding="utf-8")

    into = root / "LengthClips"

    wanted = 2.5

    nik_blender.render(blend, script, into, width=160, height=96,
                       seconds=wanted, engine="BLENDER_WORKBENCH")

    clip = into / "Scene01.mp4"

    assert clip.exists(), clip

    # Counted by decoding it, so this needs nothing but the ffmpeg
    # the renderer already uses.
    decoded = subprocess.run(
        [nik_blender.ffmpeg(), "-v", "info", "-i", str(clip),
         "-vf", "showinfo", "-f", "null", os.devnull],
        capture_output=True, text=True)

    seen = (decoded.stderr or "").count("pts_time:")

    how_long = seen / nik_blender.FPS

    print(f"   {seen} frames at {nik_blender.FPS}fps")

    print(f"   asked {wanted}s, got {how_long:.2f}s")

    assert abs(how_long - wanted) < 0.15, (how_long, wanted)

    # And the frames were a means, not an output.
    leftover = [item.name for item in into.iterdir() if item.is_dir()]

    print(f"   leftover: {leftover or 'none'}")

    assert not leftover, leftover

    print("\n   [OK] the clip is as long as the shot, whatever the "
          "action was")


def test_a_cycle_repeats_and_a_gesture_turns_back(root):

    heading("13b  How the frames repeat depends on the action")

    import nik_blender

    # A walk that ends where it began walks on without a seam, so it
    # repeats straight. A clap does not end where it began, and played
    # from the top it jumps - so it goes forwards and back.
    frames = [root / f"f{n:04d}.png" for n in range(1, 5)]

    was = nik_blender.looks_the_same

    try:
        nik_blender.looks_the_same = lambda one, other: True

        cycle = nik_blender.ordered(frames, 10)

        nik_blender.looks_the_same = lambda one, other: False

        gesture = nik_blender.ordered(frames, 10)

    finally:
        nik_blender.looks_the_same = was

    def shape(order):
        return [int(path.stem[1:]) for path in order]

    print(f"   cycle  : {shape(cycle)}")

    print(f"   gesture: {shape(gesture)}")

    assert shape(cycle) == [1, 2, 3, 4, 1, 2, 3, 4, 1, 2]

    assert shape(gesture) == [1, 2, 3, 4, 3, 2, 1, 2, 3, 4]

    # Never longer than asked for, and never shorter.
    for count in (1, 4, 7, 25):
        assert len(nik_blender.ordered(frames, count)) == count, count

    print("\n   [OK] a walk walks on, a clap turns back")


def test_a_tall_character_still_fits_in_the_frame(root):

    heading("14  A character of any height fits, head and feet")

    import bpy, from_mixamo, nik_blender

    # The pack imported at 3.85 units and the cameras were placed for
    # something 1.6 tall, so the render came out cut off at the shins
    # against a black void. The height is not knowable in advance, so
    # the framing has to be worked out from it.
    folder = root / "Tall"

    folder.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.object.armature_add(location=(0, 0, 0))

    rig = bpy.context.active_object

    # A body four units tall, standing on the ground - feet at zero,
    # head at four.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 2.0))

    body = bpy.context.active_object

    body.scale = (0.35, 0.2, 4.0)

    body.parent = rig

    rig.animation_data_create()

    action = bpy.data.actions.new("Idle")

    action.use_fake_user = True

    rig.animation_data.action = action

    for frame, lean in ((1, 0.0), (12, 0.15), (24, 0.0)):
        rig.rotation_euler.y = lean
        rig.keyframe_insert("rotation_euler", frame=frame)

    track = rig.animation_data.nla_tracks.new()
    track.name = "Idle"
    track.strips.new("Idle", 1, action)

    rig.animation_data.action = None

    bpy.ops.export_scene.gltf(filepath=str(folder / "Tall.glb"),
                              export_format="GLB")

    made = from_mixamo.build(folder, root / "Tall.blend")

    into = root / "TallClips"

    script = root / "wide.txt"

    script.write_text("Wide shot of him standing in the meadow, the "
                      "camera does not move\n", encoding="utf-8")

    nik_blender.render(made, script, into, width=320, height=180,
                       seconds=0.3, engine="BLENDER_WORKBENCH")

    clip = into / "Scene01.mp4"

    assert clip.exists(), clip

    # Look at the picture. Sky and ground stretch right across the
    # frame, so they cannot be told apart from the character by
    # brightness alone - but they are the same at the edge as in the
    # middle, and the character is not. Every row where the middle
    # differs from the edge is a row the character is standing in.
    wide, high = 320, 180

    raw = subprocess.run(
        [nik_blender.ffmpeg(), "-v", "error", "-i", str(clip),
         "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True,
    ).stdout

    assert len(raw) >= wide * high, len(raw)

    rows = [raw[y * wide:(y + 1) * wide] for y in range(high)]

    here = [y for y, row in enumerate(rows)
            if abs(row[wide // 2] - row[3]) > 20]

    assert here, "the character is not in the picture at all"

    top, bottom = here[0], here[-1]

    print(f"   character rows {top}..{bottom} of {high}")

    # Head not jammed against the ceiling, feet not cut by the floor.
    assert top > 2, f"the head is at row {top} - cut off at the top"

    assert bottom < high - 3, (f"the feet are at row {bottom} of "
                               f"{high} - cut off at the bottom")

    # And it is actually in shot, not a speck in the distance. A wide
    # shot is asked for, and CAMERAS says that fills half the frame.
    filled = (bottom - top) / high

    print(f"   fills {filled:.0%} of the frame height")

    assert 0.3 < filled < 0.8, filled

    print("\n   [OK] rendered against a sky, framed for its own height")


def test_a_grown_up_rig_becomes_a_child(root):

    heading("15  A grown-up rig, given a child's proportions")

    import bpy, from_mixamo, nik_blender

    # Free rigged characters are grown-ups, and a free rigged toddler
    # that also takes an animation library does not exist. What reads
    # as a small child is proportion, not anatomy - so the proportions
    # are changed here, on whatever rig arrives, and the animations
    # still play because the skeleton is the same skeleton.
    folder = root / "GrownUp"

    folder.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.object.armature_add(location=(0, 0, 0))

    rig = bpy.context.active_object

    bpy.context.view_layer.objects.active = rig

    bpy.ops.object.mode_set(mode="EDIT")

    spine = rig.data.edit_bones[0]

    spine.name = "Spine"

    spine.head = (0.0, 0.0, 0.0)

    spine.tail = (0.0, 0.0, 3.0)

    neck = rig.data.edit_bones.new("Head")

    neck.head = (0.0, 0.0, 3.0)

    neck.tail = (0.0, 0.0, 4.0)

    neck.parent = spine

    bpy.ops.object.mode_set(mode="OBJECT")

    # A body from the floor to the neck, and a head above it.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 1.5))

    body = bpy.context.active_object

    body.name = "Body"

    body.scale = (0.4, 0.3, 3.0)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 3.5))

    skull = bpy.context.active_object

    skull.name = "Skull"

    for part, bone in ((body, "Spine"), (skull, "Head")):

        bpy.context.view_layer.objects.active = part

        bpy.ops.object.transform_apply(location=False, rotation=False,
                                       scale=True)

        group = part.vertex_groups.new(name=bone)

        group.add(range(len(part.data.vertices)), 1.0, "REPLACE")

        change = part.modifiers.new("Armature", "ARMATURE")

        change.object = rig

        part.parent = rig

    rig.animation_data_create()

    action = bpy.data.actions.new("Idle")

    action.use_fake_user = True

    rig.animation_data.action = action

    for frame, turn in ((1, 0.0), (12, 0.3), (24, 0.0)):
        rig.rotation_euler.z = turn
        rig.keyframe_insert("rotation_euler", frame=frame)

    track = rig.animation_data.nla_tracks.new()
    track.name = "Idle"
    track.strips.new("Idle", 1, action)

    rig.animation_data.action = None

    bpy.ops.export_scene.gltf(filepath=str(folder / "Grown.glb"),
                              export_format="GLB")

    def proportions(blend):
        """How tall it is, and what share of that is head."""

        bpy.ops.wm.open_mainfile(filepath=str(blend))

        rig = nik_blender.armature_in()

        low, high = nik_blender.span_of(rig)

        skull = bpy.data.objects.get("Skull")

        head = skull.dimensions.z

        return high - low, head

    grown = from_mixamo.build(folder, root / "Grown.blend")

    tall, head = proportions(grown)

    print(f"   grown up: {tall:.2f} tall, head {head:.2f} "
          f"= {head / tall:.0%} of it")

    # Which bone it worked around, said out loud. Going into edit mode
    # invalidates every reference into rig.data.bones without
    # complaining, so a name read afterwards can name a different bone
    # entirely - and then the head is not the head and nothing grows.
    bpy.ops.wm.open_mainfile(filepath=str(grown))

    around = from_mixamo.childlike(nik_blender.armature_in(), 1.0)

    print(f"   worked around: {around}")

    assert around == "Head", around

    kid = from_mixamo.build(folder, root / "Kid.blend", child=1.0)

    small, big_head = proportions(kid)

    print(f"   child   : {small:.2f} tall, head {big_head:.2f} "
          f"= {big_head / small:.0%} of it")

    # Shorter overall, a bigger head, and so a much larger share of it.
    assert small < tall, (small, tall)

    assert big_head > head, (big_head, head)

    assert big_head / small > (head / tall) * 1.4, (
        big_head / small, head / tall)

    # And it still animates: the action survived, and the render runs.
    assert "idle" in {action.name for action in bpy.data.actions}

    script = root / "kid.txt"

    script.write_text("Wide shot of him standing in the meadow, the "
                      "camera does not move\n", encoding="utf-8")

    into = root / "KidClips"

    nik_blender.render(kid, script, into, width=160, height=96,
                       seconds=0.3, engine="BLENDER_WORKBENCH")

    assert (into / "Scene01.mp4").exists()

    print("\n   [OK] shorter body, bigger head, and it still moves")


def liveliness_of(action):

    import nik_blender

    return nik_blender.liveliness(action)


def test_a_missing_movement_does_not_freeze_the_shot(root):

    heading("16  A movement the pack has not got is not a frozen shot")

    import bpy, nik_blender

    # Two clips came back measuring 0.06 - a character standing dead
    # still for four seconds - because the line asked for a wave, the
    # game pack has no wave, and the fallback was 'idle', which in that
    # pack is a statue. Standing still is the last resort now.
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # The pack's idle is a statue - that is what a 0.06 clip was - so
    # it is given almost no movement here, and the others real amounts.
    for name, length, moves in (("idle", 40, 0.001), ("clap", 30, 1.0),
                                ("walk", 24, 0.8), ("crouch", 20, 0.6),
                                ("sword slash", 60, 2.0),
                                ("death", 90, 3.0)):

        action = bpy.data.actions.new(name)

        action.use_fake_user = True

        curve = action.fcurves.new("location", index=2)

        curve.keyframe_points.insert(1, 0.0)

        curve.keyframe_points.insert(length, moves)

    for asked, wanted in (("wave", "clap"), ("clap", "clap"),
                          ("sway", "walk"), ("spin", "walk"),
                          ("nod", "crouch"), ("walk", "walk"),
                          # The one that was still coming back frozen:
                          # a line with no verb asks for 'idle', the
                          # idle is there, and it does nothing.
                          ("idle", "walk")):

        got, instead = nik_blender.stand_in_for(asked)

        print(f"   {asked:<6} -> {got.name}"
              + (f"  (asked for {instead})" if instead else ""))

        assert got.name == wanted, (asked, got.name, wanted)

    # Never the violent ones, however long they are and however little
    # else there is.
    for banned in ("death", "sword slash", "punch"):

        got, _ = nik_blender.stand_in_for(banned)

        assert nik_blender.allowed(got.name), (banned, got.name)

    # And a still action is refused even when it is asked for by name.
    still = bpy.data.actions.get("idle")

    usable = [act for act in bpy.data.actions
              if nik_blender.allowed(act.name)]

    assert nik_blender.too_still(still, usable), liveliness_of(still)

    assert not nik_blender.too_still(bpy.data.actions.get("clap"), usable)

    print("\n   [OK] something that moves, and never the sword")


def test_the_notebook_carries_the_code_it_runs(root):

    heading("17  The notebook cannot be out of step with the scripts")

    import base64, json

    # Three files had to be kept in step by hand - the notebook and the
    # two scripts uploaded beside it in Drive - and a run went wrong
    # every time one of them was the old one. The notebook is generated
    # from the scripts now, so this checks it was regenerated.
    made = json.loads(
        (PROJECT_ROOT / "colab" / "NikStudio_Rigged.ipynb").read_text(
            encoding="utf-8"))

    code = [cell for cell in made["cells"] if cell["cell_type"] == "code"]

    assert len(code) == 1, f"{len(code)} code cells, should be one"

    cell = "".join(code[0]["source"])

    inside = {}

    exec(cell[cell.index("MODULES = {"):cell.index("import base64")],
         inside)

    for name, blob in inside["MODULES"].items():

        carried = base64.b64decode(blob).decode("utf-8")

        onshelf = (PROJECT_ROOT / "blender" / name).read_text(
            encoding="utf-8")

        print(f"   {name:<18} {len(carried)} chars, same as blender/: "
              f"{carried == onshelf}")

        assert carried == onshelf, (
            f"{name} in the notebook is not the one in blender/. "
            f"Run: python colab/build_rigged_notebook.py")

    print("\n   [OK] one cell, and it carries exactly what is tested")


class Slotted:
    """
    An action shaped the way Blender 4.4 and later shape one.

    This container has Blender 4.2, where an action holds its curves
    directly. Colab installs a newer one, where they are down inside
    layers, strips and channelbags - and reaching for the old place
    there is an AttributeError that stopped the render after the
    character, the cameras and the framing were all correct.
    """

    class Curve:

        def __init__(self, values):

            self.keyframe_points = [
                type("Point", (), {"co": (index + 1.0, value)})()
                for index, value in enumerate(values)
            ]

    class Bag:

        def __init__(self, curves):
            self.fcurves = curves

    class Strip:

        def __init__(self, bags):
            self.channelbags = bags

    class Layer:

        def __init__(self, strips):
            self.strips = strips

    def __init__(self, name, values):

        self.name = name

        self.layers = [Slotted.Layer([
            Slotted.Strip([Slotted.Bag([Slotted.Curve(values)])])])]


def test_the_curves_are_found_on_any_blender(root):

    heading("18  Where the curves live changed, and both places work")

    import nik_blender

    new_shape = Slotted("clap", [0.0, 1.0, 0.0])

    found = nik_blender.curves_of(new_shape)

    print(f"   layers/strips/channelbags: {len(found)} curve(s), "
          f"liveliness {nik_blender.liveliness(new_shape):.2f}")

    assert len(found) == 1, found

    assert nik_blender.liveliness(new_shape) == 1.0

    # And nothing readable at all must not turn every movement in the
    # film into a stand-in.
    class Unreadable:

        name = "idle"

    blank = [Unreadable(), Unreadable()]

    assert nik_blender.liveliness(blank[0]) == 0.0

    assert not nik_blender.too_still(blank[0], blank)

    print("   unreadable curves     : nothing rejected")

    print("\n   [OK] old shape, new shape, and neither")


def test_a_missing_texture_is_not_a_black_cut_out(root):

    heading("19  A part whose colour was in a missing texture")

    import bpy, from_mixamo

    # The character came out with a black head. A material that takes
    # all its colour from an image keeps black as its own colour -
    # there is nothing for it to hold - so when the image is not found
    # the part renders as a silhouette, and no one can judge the shot.
    bpy.ops.wm.read_factory_settings(use_empty=True)

    def a_material(name, colour, picture):

        stuff = bpy.data.materials.new(name)

        stuff.use_nodes = True

        stuff.diffuse_color = colour

        if picture is not None:

            node = stuff.node_tree.nodes.new("ShaderNodeTexImage")

            node.image = picture

        return stuff

    lost = bpy.data.images.new("face.png", 4, 4)

    lost.source = "FILE"

    lost.filepath = "/nowhere/face.png"

    lost.reload()

    real = bpy.data.images.new("shirt.png", 4, 4)

    head = a_material("Head", (0.0, 0.0, 0.0, 1.0), lost)

    shirt = a_material("Shirt", (0.0, 0.0, 0.0, 1.0), real)

    boots = a_material("Boots", (0.02, 0.02, 0.02, 1.0), None)

    trews = a_material("Trousers", (0.3, 0.2, 0.6, 1.0), None)

    fixed = from_mixamo.not_a_silhouette()

    for stuff in (head, shirt, boots, trews):
        print(f"   {stuff.name:<10} {tuple(round(v, 2) for v in stuff.diffuse_color[:3])}")

    # The head had a picture and it is gone, so it gets a colour.
    assert max(head.diffuse_color[:3]) > 0.3, head.diffuse_color[:]

    # The shirt's picture is there - leave it to the picture.
    assert max(shirt.diffuse_color[:3]) < 0.05, shirt.diffuse_color[:]

    # Boots are meant to be black. Nothing was lost, so nothing is
    # invented.
    assert max(boots.diffuse_color[:3]) < 0.05, boots.diffuse_color[:]

    assert abs(trews.diffuse_color[2] - 0.6) < 0.01, trews.diffuse_color[:]

    assert fixed == 1, fixed

    print("\n   [OK] only what lost its colour, and nothing that "
          "meant to be dark")


# ======================================================================

def main():

    with tempfile.TemporaryDirectory() as temporary:

        root = Path(temporary)

        test_template_keeps_its_actions(root)
        test_the_line_chooses_the_movement(root)
        test_renders_a_clip_per_scene(root)
        test_says_what_is_missing(root)
        test_an_unrigged_file_is_refused(root)
        test_a_folder_of_downloads_becomes_a_blend(root)
        test_one_file_with_every_movement_in_it(root)
        test_names_are_cleaned_up(root)
        test_a_folder_with_no_character_is_refused(root)
        test_an_unzipped_pack_of_many_characters(root)
        test_one_file_per_movement_per_character(root)
        test_movements_from_a_second_folder(root)
        test_a_clip_lasts_as_long_as_the_shot(root)
        test_a_cycle_repeats_and_a_gesture_turns_back(root)
        test_a_tall_character_still_fits_in_the_frame(root)
        test_a_grown_up_rig_becomes_a_child(root)
        test_a_missing_movement_does_not_freeze_the_shot(root)
        test_the_curves_are_found_on_any_blender(root)
        test_a_missing_texture_is_not_a_black_cut_out(root)
        test_the_notebook_carries_the_code_it_runs(root)

    print("\nALL BLENDER TESTS PASSED")


if __name__ == "__main__":

    main()

    # bpy as a module segfaults on interpreter teardown after a run
    # like this one - the tests have already passed by then, and an
    # exit code of 139 on a green run is worse than useless.
    sys.stdout.flush()

    os._exit(0)
