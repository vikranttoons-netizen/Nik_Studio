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
    assert made[2]["action"] == "idle", made[2]

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


def test_renders_without_ffmpeg_inside_blender(root):

    heading("13  A Blender built without ffmpeg still makes mp4s")

    import bpy, nik_blender

    # Blender installed with pip - which is the only way to have it in
    # Colab - is built without ffmpeg, so FFMPEG is not among the
    # formats it will write and asking for it is a TypeError. This
    # container's Blender does have it, so the other path is forced.
    blend = root / "NoFF.blend"

    nik_blender.template(blend)

    script = root / "two.txt"

    script.write_text("\n".join(SCRIPT.splitlines()[:2]) + "\n",
                      encoding="utf-8")

    into = root / "NoFFClips"

    was = nik_blender.writes_video

    nik_blender.writes_video = lambda: False

    try:
        nik_blender.render(blend, script, into, width=160, height=96,
                           seconds=0.5, engine="BLENDER_WORKBENCH")

    finally:
        nik_blender.writes_video = was

    # And the other way round: a Blender that claims it can encode and
    # then throws when asked must not take 44 clips down with it. This
    # is what Colab actually did.
    into_lied = root / "LiedClips"

    nik_blender._WRITES_VIDEO = True

    told = {"asked": 0}

    real = nik_blender.as_video

    def refuse(scene, target):

        told["asked"] += 1

        raise TypeError('bpy_struct: enum "FFMPEG" not found')

    try:
        nik_blender.as_video = refuse

        nik_blender.render(blend, script, into_lied, width=160,
                           height=96, seconds=0.5,
                           engine="BLENDER_WORKBENCH")

    finally:
        nik_blender.as_video = real

        nik_blender._WRITES_VIDEO = None

    lied = sorted(into_lied.glob("Scene*.mp4"))

    print(f"   after a lie: {', '.join(path.name for path in lied)} "
          f"(refused {told['asked']}x)")

    assert len(lied) == 2, [path.name for path in lied]

    # It should stop asking after the first refusal, not once a clip.
    assert told["asked"] == 1, told

    made = sorted(into.glob("Scene*.mp4"))

    print(f"   made    : {', '.join(path.name for path in made)}")

    assert len(made) == 2, [path.name for path in made]

    for path in made:
        assert path.stat().st_size > 0, path

    # The frames were a means, not an output.
    leftover = [item.name for item in into.iterdir() if item.is_dir()]

    print(f"   leftover: {leftover or 'none'}")

    assert not leftover, leftover

    print("\n   [OK] stills out of Blender, mp4 out of ffmpeg, "
          "nothing left behind")


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
        test_renders_without_ffmpeg_inside_blender(root)

    print("\nALL BLENDER TESTS PASSED")


if __name__ == "__main__":

    main()

    # bpy as a module segfaults on interpreter teardown after a run
    # like this one - the tests have already passed by then, and an
    # exit code of 139 on a green run is worse than useless.
    sys.stdout.flush()

    os._exit(0)
