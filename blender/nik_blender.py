"""
Nik Studio - the Blender half.

    python blender/nik_blender.py template Nik.blend
    python blender/nik_blender.py render Nik.blend script.txt Clips/

The AI video models could not hold a character still from one clip to
the next, and could not be told what to do. A rigged 3D character can do
both, because it is the same model every time and the movement is
animated rather than guessed at.

This renders the clips. Everything after that - cutting to the beat, the
song, the encode, the vertical cut - is the pipeline that already
exists, unchanged.

WHAT YOUR .blend MUST CONTAIN
-----------------------------
Build to this and the tool will drive it.

  One armature          the character's rig. Any name.

  Actions on that rig   the movements, named for what they are:
                        idle, walk, wave, clap, jump, sway, point,
                        crouch, nod, spin
                        `idle` is required - it is what plays when a
                        line asks for something you have not animated.

  Three cameras         Cam_Wide, Cam_Medium, Cam_Close
                        A line starting "Wide shot of" gets Cam_Wide,
                        "Close up of" gets Cam_Close, anything else
                        gets Cam_Medium.

Anything else in the file - the set, the light, the animals - is yours
and is left alone.
"""

import json
import re
import sys
from pathlib import Path

import bpy


FPS = 24
CLIP_SECONDS = 2.0

# Cameras, by how the script line begins.
FRAMINGS = {
    "wide shot": "Cam_Wide",
    "close up": "Cam_Close",
}

DEFAULT_CAMERA = "Cam_Medium"

# What a line has to say for an action to be chosen. Order does not
# matter: whichever word comes first in the sentence wins, because that
# is the verb the line is actually about.
ACTIONS = [
    ("wave", ("wave", "waves", "waving", "goodbye", "hello")),
    ("clap", ("clap", "claps", "clapping", "pats")),
    ("jump", ("jump", "jumps", "hop", "hops", "bouncing")),
    ("walk", ("walk", "walks", "walking", "run", "runs", "arrives")),
    ("sway", ("sway", "sways", "dance", "dances", "dancing", "taps")),
    ("point", ("point", "points", "pointing", "holds", "reaches")),
    ("crouch", ("crouch", "crouches", "kneel", "kneels",
                "sit", "sits", "sitting")),
    ("nod", ("nod", "nods", "nodding")),
    ("spin", ("spin", "spins", "turns", "twirls")),
]

FALLBACK_ACTION = "idle"


# ======================================================================
# Reading the script
# ======================================================================

def scenes_in(script):
    """The lines that are scenes: not blank, not commented out."""

    lines = [
        line.strip()
        for line in Path(script).read_text(encoding="utf-8").splitlines()
    ]

    return [line for line in lines if line and not line.startswith("#")]


def action_for(line):
    """
    Which movement this line is asking for.

    Only the first clause is read - everything up to the first comma.
    A script line is written as "what he does, who else is there, what
    the background is doing", so looking at the whole line picks up the
    wrong verb: "Close up of the puppy barking, Nik stands nearby,
    flowers nod in the breeze" was making the boy nod.
    """

    doing = line.split(",")[0].lower()

    found = []

    # Whatever the rig itself can do, by its own name. This is what
    # makes the library grow: add a "twirl" action to the .blend and a
    # line that says "twirls" starts using it, with no code change.
    for action in bpy.data.actions:

        for form in (action.name.lower(), action.name.lower() + "s",
                     action.name.lower() + "es"):

            match = re.search(rf"\b{re.escape(form)}\b", doing)

            if match:
                found.append((match.start(), action.name))
                break

    for name, words in ACTIONS:
        for word in words:
            match = re.search(rf"\b{word}\b", doing)
            if match:
                found.append((match.start(), name))
                break

    if not found:
        return FALLBACK_ACTION

    # The earliest verb in the sentence is the one it is about.
    # "He crouches down and holds out one hand" is a crouch, not a
    # point, and a list order cannot know that.
    return min(found)[1]


def camera_for(line):
    """Which camera this line is asking for."""

    lowered = line.lower()

    for opening, camera in FRAMINGS.items():
        if lowered.startswith(opening):
            return camera

    return DEFAULT_CAMERA


# ======================================================================
# Checking the file before anything expensive happens
# ======================================================================

def armature_in(scene=None):
    """The rig. There should be exactly one."""

    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE"]

    if not rigs:
        raise SystemExit(
            "No armature in this .blend.\n\n"
            "The character has to be rigged - a mesh on its own cannot "
            "be posed, so there is\nnothing for the tool to animate."
        )

    if len(rigs) > 1:
        names = ", ".join(rig.name for rig in rigs)
        raise SystemExit(
            f"{len(rigs)} armatures in this .blend: {names}\n\n"
            "Keep one rig in the file, or join them. The tool cannot "
            "know which is the character."
        )

    return rigs[0]


def check(rig):
    """
    Everything the file has to have, said all at once.

    One complaint at a time means opening Blender, fixing, saving and
    running again for each - so they are gathered up.
    """

    problems = []

    actions = {action.name for action in bpy.data.actions}

    if FALLBACK_ACTION not in actions:
        problems.append(
            f"No action called '{FALLBACK_ACTION}'. It is the one that "
            "plays when a line asks for\n     a movement you have not "
            "animated, so it is the only one that is required."
        )

    wanted = {name for name, _ in ACTIONS}

    missing = sorted(wanted - actions)

    if missing:
        problems.append(
            "These movements have no action, so those lines will fall "
            f"back to '{FALLBACK_ACTION}':\n     "
            + ", ".join(missing)
        )

    cameras = {
        o.name for o in bpy.data.objects if o.type == "CAMERA"
    }

    for name in (DEFAULT_CAMERA, *FRAMINGS.values()):
        if name not in cameras:
            problems.append(
                f"No camera called '{name}'."
                + (" Wide and close lines will use it too."
                   if name == DEFAULT_CAMERA else "")
            )

    return problems


def report(rig):
    """What the tool can see in the file."""

    actions = sorted(action.name for action in bpy.data.actions)
    cameras = sorted(o.name for o in bpy.data.objects if o.type == "CAMERA")

    print(f"Rig       : {rig.name}")
    print(f"Actions   : {len(actions)} ({', '.join(actions) or 'none'})")
    print(f"Cameras   : {len(cameras)} ({', '.join(cameras) or 'none'})")


# ======================================================================
# Rendering
# ======================================================================

def play(rig, action_name):
    """Put an action on the rig, and say how long it runs."""

    action = bpy.data.actions.get(action_name)

    if action is None:
        action = bpy.data.actions.get(FALLBACK_ACTION)

    if action is None:
        raise SystemExit(f"No action '{action_name}' and no fallback.")

    if rig.animation_data is None:
        rig.animation_data_create()

    rig.animation_data.action = action

    start, end = (int(round(v)) for v in action.frame_range)

    return action.name, max(1, end - start), start


def render_scene(rig, line, target, seconds=CLIP_SECONDS):
    """One line of the script -> one clip."""

    scene = bpy.context.scene

    name, length, start = play(rig, action_for(line))

    camera_name = camera_for(line)

    camera = bpy.data.objects.get(camera_name)

    if camera is None:
        camera = bpy.data.objects.get(DEFAULT_CAMERA)

    if camera is not None:
        scene.camera = camera

    wanted = int(round(seconds * FPS))

    scene.frame_start = start

    # An action shorter than the clip is looped by the tool afterwards -
    # the same forwards-and-back the AI clips get - so render what there
    # is rather than hold on the last frame.
    scene.frame_end = start + min(wanted, length)

    scene.render.fps = FPS
    scene.render.filepath = str(target)

    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"

    bpy.ops.render.render(animation=True)

    return name, camera_name, scene.frame_end - scene.frame_start + 1


def render(blend, script, into, width=960, height=544,
           seconds=CLIP_SECONDS, engine=None):
    """
    Every line of the script, into `into` as SceneNN.mp4.

    `engine` overrides what the .blend asks for. BLENDER_WORKBENCH
    renders flat and fast and needs no GPU, which is what you want when
    you are checking that the shots come out right rather than how they
    look - and it is the only way this runs on a machine without one.
    """

    bpy.ops.wm.open_mainfile(filepath=str(blend))

    rig = armature_in()

    report(rig)

    problems = check(rig)

    for problem in problems:
        print(f"  ! {problem}")

    lines = scenes_in(script)

    if not lines:
        raise SystemExit(f"{script} has no scenes in it.")

    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100

    if engine:
        scene.render.engine = engine

    made = []

    for number, line in enumerate(lines, start=1):

        target = into / f"Scene{number:02d}.mp4"

        action, camera, frames = render_scene(rig, line, target, seconds)

        print(f"[{number}/{len(lines)}] {target.name}: "
              f"{action} on {camera}, {frames} frames")

        made.append({"scene": target.name, "action": action,
                     "camera": camera, "frames": frames, "line": line})

    (into / "rendered.json").write_text(
        json.dumps(made, indent=1), encoding="utf-8"
    )

    return made


# ======================================================================
# A file shaped the way the tool expects
# ======================================================================
#
# Not a character - a stand-in. Its point is that the pipeline can be
# run today, and that there is something to compare against while you
# build the real one: open it, see what is named what, and replace the
# body with yours.

BODY = (
    # name,      radius, (x, y, z)
    ("Head",     0.42,   (0.0, 0.0, 1.55)),
    ("Body",     0.38,   (0.0, 0.0, 0.95)),
    ("ArmLeft",  0.12,   (0.42, 0.0, 1.05)),
    ("ArmRight", 0.12,   (-0.42, 0.0, 1.05)),
    ("LegLeft",  0.14,   (0.18, 0.0, 0.35)),
    ("LegRight", 0.14,   (-0.18, 0.0, 0.35)),
)

CAMERAS = (
    # name,        (x, y, z),            (rx, ry, rz) in degrees
    ("Cam_Wide",   (0.0, -6.5, 1.6),     (86.0, 0.0, 0.0)),
    ("Cam_Medium", (0.0, -3.6, 1.4),     (88.0, 0.0, 0.0)),
    ("Cam_Close",  (0.35, -1.7, 1.6),    (89.0, 0.0, 8.0)),
)

# How the stand-in moves, so every action name in ACTIONS exists.
# Each is (bone, channel, [(frame, value), ...]) on the root bone.
# 48 frames is two seconds at 24fps, which is a whole clip. Shorter
# actions are looped by the edit, but a movement that covers the shot
# without repeating reads better.
MOVEMENTS = {
    "idle":   [(1, 0.00), (24, 0.02), (48, 0.00)],
    "walk":   [(1, 0.00), (12, 0.10), (24, 0.00), (36, -0.10), (48, 0.00)],
    "wave":   [(1, 0.00), (16, 0.35), (32, -0.10), (48, 0.00)],
    "clap":   [(1, 0.00), (8, 0.18), (16, 0.00), (24, 0.18), (32, 0.00),
               (40, 0.18), (48, 0.00)],
    "jump":   [(1, 0.00), (12, 0.55), (24, 0.00), (36, 0.30), (48, 0.00)],
    "sway":   [(1, -0.15), (24, 0.15), (48, -0.15)],
    "point":  [(1, 0.00), (20, 0.28), (48, 0.28)],
    "crouch": [(1, 0.00), (20, -0.35), (48, -0.35)],
    "nod":    [(1, 0.00), (12, -0.12), (24, 0.00), (36, -0.12), (48, 0.00)],
    "spin":   [(1, 0.00), (24, 0.06), (48, 0.00)],
}


def clear():
    """An empty file, with none of the default cube's furniture."""

    bpy.ops.wm.read_factory_settings(use_empty=True)


def build_body(rig):

    from mathutils import Vector

    for name, radius, where in BODY:

        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=where)

        part = bpy.context.active_object
        part.name = name

        # Parented to the rig, so moving the bone moves all of it. A
        # real character is weight painted; this is a stand-in.
        part.parent = rig
        part.parent_type = "OBJECT"
        part.matrix_parent_inverse = rig.matrix_world.inverted()


def build_actions(rig):
    """One action per name in ACTIONS, plus idle."""

    rig.animation_data_create()

    for name, keys in MOVEMENTS.items():

        action = bpy.data.actions.new(name=name)

        # Without this, Blender throws away every action that nothing is
        # currently using the moment the file is saved - and only the
        # last one assigned is in use. Ten actions were built and one
        # survived. It is the same flag as the shield icon in the Action
        # editor, and a character's action library needs it on all of
        # them.
        action.use_fake_user = True

        rig.animation_data.action = action

        for frame, value in keys:
            rig.location.z = value
            rig.keyframe_insert(data_path="location", index=2, frame=frame)

    rig.location.z = 0.0
    rig.animation_data.action = bpy.data.actions.get(FALLBACK_ACTION)


def build_cameras():

    from math import radians

    for name, where, rotation in CAMERAS:

        bpy.ops.object.camera_add(
            location=where,
            rotation=tuple(radians(r) for r in rotation),
        )

        bpy.context.active_object.name = name


def template(target):
    """Write a .blend that meets the contract."""

    clear()

    bpy.ops.object.armature_add(location=(0.0, 0.0, 0.0))

    rig = bpy.context.active_object
    rig.name = "NikRig"

    build_body(rig)
    build_actions(rig)
    build_cameras()

    bpy.ops.object.light_add(type="SUN", location=(2.0, -3.0, 5.0))

    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0.0, 0.0, 0.0))
    bpy.context.active_object.name = "Ground"

    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.camera = bpy.data.objects.get(DEFAULT_CAMERA)

    # Eevee: fast enough to render a whole episode on a laptop.
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.save_as_mainfile(filepath=str(target))

    return target


# ======================================================================

def main(argv):

    if len(argv) < 2:
        raise SystemExit(__doc__.strip())

    what = argv[0]

    if what == "template":
        made = template(argv[1])
        print(f"Wrote {made}")
        return 0

    if what == "render":

        if len(argv) < 3:
            raise SystemExit("render needs: <blend> <script.txt> <into>")

        render(
            argv[1], argv[2],
            argv[3] if len(argv) > 3 else "Clips",
            engine=argv[4] if len(argv) > 4 else None,
        )
        return 0

    raise SystemExit(f"Unknown command: {what}")


if __name__ == "__main__":

    # Under `blender -b -P script -- args`, ours start after the --.
    argv = sys.argv[1:]

    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]

    raise SystemExit(main(argv))
