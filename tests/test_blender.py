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

def main():

    with tempfile.TemporaryDirectory() as temporary:

        root = Path(temporary)

        test_template_keeps_its_actions(root)
        test_the_line_chooses_the_movement(root)
        test_renders_a_clip_per_scene(root)
        test_says_what_is_missing(root)
        test_an_unrigged_file_is_refused(root)

    print("\nALL BLENDER TESTS PASSED")


if __name__ == "__main__":
    main()
