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
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import bpy


FPS = 24

# The same sky the .blend is built with.
SKY = (0.53, 0.75, 0.95)
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

# When the rig has not got the movement a line asks for, what will do
# instead - in order, best first. Standing still is the last resort,
# not the first: a character frozen through a whole line is worse for
# a two year old than a wave that came out as a clap.
STAND_INS = {
    # A line with no verb in it lands here, and in a game pack the
    # idle is a statue. A song for two year olds cannot hold on a
    # statue for four seconds.
    "idle":   ("sway", "dance", "walk", "clap", "jump"),
    "wave":   ("clap", "point", "victory", "jump"),
    "clap":   ("victory", "wave", "jump"),
    "jump":   ("roll", "clap", "walk"),
    "walk":   ("run", "walk carry", "jump"),
    "sway":   ("dance", "walk", "clap", "jump"),
    "point":  ("pick up", "wave", "clap"),
    "crouch": ("sit down", "pick up", "stand up", "roll"),
    "nod":    ("crouch", "pick up", "clap"),
    "spin":   ("turn", "roll", "walk"),
}

# Never, whatever a line seems to ask for and whatever is missing.
# A pack built for games ships these and this is a children's channel.
NEVER = ("death", "defeat", "punch", "kick", "shoot", "sword", "slash",
         "stab", "hit", "die", "dead", "attack", "gun", "knife")


def allowed(name):
    """Is this movement one a nursery rhyme can use?"""

    plain = name.lower()

    return not any(word in plain for word in NEVER)


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




def worn_by(item, rig):
    """Is this object part of that character?"""

    parent = item.parent

    while parent:

        if parent is rig:
            return True

        parent = parent.parent

    # A body is usually driven by the armature rather than parented to
    # it, and the modifier is what says so.
    for change in getattr(item, "modifiers", ()):

        if change.type == "ARMATURE" and change.object is rig:
            return True

    return False


def span_of(rig):
    """
    How low and how high the character actually reaches.

    Not the armature's own size, which is what a bone happens to
    measure and has nothing to do with the body hanging off it. What is
    seen is the mesh, so the mesh is what is measured.
    """

    from mathutils import Vector

    low = high = None

    for item in bpy.data.objects:

        if item.type != "MESH" or item.name == "Ground":
            continue

        if not worn_by(item, rig):
            continue

        for corner in item.bound_box:

            up = (item.matrix_world @ Vector(corner[:])).z

            low = up if low is None else min(low, up)

            high = up if high is None else max(high, up)

    if low is None:

        tall = max(0.5, rig.dimensions.z or 1.6)

        return 0.0, tall

    return low, high


def aim_cameras(rig, width, height):
    """
    Re-frame every camera for this character and this picture size.

    Done here rather than only when the .blend is built, because the
    frame's shape is not known until the render is asked for, and
    because a .blend built before this existed is then fixed too.
    """

    low, high = span_of(rig)

    tall = max(0.5, high - low)

    for camera in bpy.data.objects:

        if camera.type != "CAMERA" or "fill" not in camera:
            continue

        target = bpy.data.objects.get(f"{camera.name}_Target")

        if target is None:
            continue

        lens = camera.data.lens

        # Blender fits the 36mm sensor across the longer side of the
        # picture, so on a landscape frame its height is the smaller
        # share.
        sensor = 36.0 * min(1.0, height / width)

        away = (tall / camera["fill"]) * lens / sensor

        up = low + tall * camera["aim"]

        camera.location = (0.0, -away, up)

        target.location = (0.0, 0.0, up)

    return tall


# What a renderer is called changes between Blender versions, and
# asking for one that is not there is a TypeError rather than a
# fallback. EEVEE was BLENDER_EEVEE, then BLENDER_EEVEE_NEXT, and
# Colab does not install the same Blender this was written against.
ENGINE_ALSO = {
    "BLENDER_EEVEE_NEXT": ("BLENDER_EEVEE", "BLENDER_WORKBENCH"),
    "BLENDER_EEVEE": ("BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"),
    "CYCLES": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"),
}


def an_engine(wanted, scene=None):
    """
    The renderer asked for, or the nearest one this Blender has.

    Found out by setting it, not by reading the list of engines: that
    list is what Blender was built knowing about and leaves out
    Workbench entirely on a build that renders with it perfectly well.
    The same lesson as the encoder - ask by doing.
    """

    scene = scene or bpy.context.scene

    before = scene.render.engine

    for name in (wanted, *ENGINE_ALSO.get(wanted, ())):

        try:
            scene.render.engine = name

        except TypeError:
            continue

        scene.render.engine = before

        if name != wanted:
            print(f"  ! No {wanted} in this Blender. Using {name}.")

        return name

    raise SystemExit(
        f"No renderer called {wanted}, and no stand-in for it."
    )


def flat_but_visible(scene):
    """
    Workbench, told to show colour and sky instead of grey on black.

    Workbench is what runs without a GPU, and out of the box it paints
    an unlit grey model against a black void - which says nothing about
    whether a shot is right.
    """

    shading = scene.display.shading

    shading.light = "STUDIO"

    for wanted in ("TEXTURE", "MATERIAL", "OBJECT"):

        try:
            shading.color_type = wanted

            break

        except TypeError:
            continue

    shading.show_shadows = True

    shading.background_type = "VIEWPORT"

    shading.background_color = SKY


def ffmpeg():
    """Wherever ffmpeg is - the one imageio carries, or the system's."""

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()

    except Exception:
        return "ffmpeg"


def looks_the_same(one, other):
    """Are these two frames near enough the same picture?"""

    def grey(path):

        return subprocess.run(
            [ffmpeg(), "-v", "error", "-i", str(path),
             "-vf", "scale=64:36", "-pix_fmt", "gray",
             "-f", "rawvideo", "-"],
            capture_output=True,
        ).stdout

    here, there = grey(one), grey(other)

    if not here or len(here) != len(there):
        return False

    apart = sum(abs(a - b) for a, b in zip(here, there)) / len(here)

    return apart < 3.0


def ordered(frames, wanted):
    """
    The frames, in the order that fills a shot of `wanted` frames.

    An action is usually shorter than the shot it has to cover - a
    walk cycle is under a second - and holding on the last pose for
    the rest is the standing-still problem again. So it repeats.

    A cycle repeats straight: a walk that ends where it began walks on
    without a seam. Anything else goes forwards and back, because a
    clap played from the top jumps and a clap played backwards does
    not.
    """

    if not frames or len(frames) >= wanted:
        return frames[:wanted] or frames

    if looks_the_same(frames[0], frames[-1]):
        run = frames

    else:
        run = frames + frames[-2:0:-1]

    order = []

    while len(order) < wanted:
        order.extend(run)

    return order[:wanted]


def join(pictures, target, wanted=0):
    """A folder of numbered PNGs -> one mp4 of the length asked for."""

    pictures = Path(pictures)

    frames = sorted(pictures.glob("f*.png"))

    if not frames:
        raise SystemExit(f"Blender rendered no frames into {pictures}.")

    laid_out = pictures / "in order"

    laid_out.mkdir(exist_ok=True)

    for number, frame in enumerate(ordered(frames, wanted or len(frames)),
                                   start=1):

        placed = laid_out / f"g{number:04d}.png"

        try:
            os.link(frame, placed)

        except OSError:
            shutil.copyfile(frame, placed)

    made = subprocess.run(
        [ffmpeg(), "-y", "-v", "error",
         "-framerate", str(FPS),
         "-i", str(laid_out / "g%04d.png"),
         "-c:v", "libx264", "-crf", "18",
         "-pix_fmt", "yuv420p",
         str(target)],
        capture_output=True, text=True,
    )

    if made.returncode != 0 or not Path(target).exists():
        raise SystemExit(
            "The frames rendered but ffmpeg would not join them:\n"
            + (made.stderr or "").strip()
        )


def curves_of(action):
    """
    Every f-curve in an action, whichever Blender this is.

    Blender 4.4 moved them: an action used to hold its curves directly
    and now holds layers, which hold strips, which hold a channelbag
    per slot, which holds the curves. Colab installs the new one and
    this reads both - and if it can read neither, it says so by
    returning nothing rather than by stopping the render.
    """

    curves = list(getattr(action, "fcurves", None) or ())

    if curves:
        return curves

    for layer in getattr(action, "layers", None) or ():

        for strip in getattr(layer, "strips", None) or ():

            for bag in getattr(strip, "channelbags", None) or ():

                curves.extend(getattr(bag, "fcurves", None) or ())

            if curves:
                continue

            # The other way in, when channelbags is not a collection:
            # one bag per slot, asked for by name.
            asking = getattr(strip, "channelbag", None)

            if not callable(asking):
                continue

            for slot in getattr(action, "slots", None) or ():

                try:
                    bag = asking(slot)

                except (TypeError, RuntimeError):
                    continue

                if bag is not None:
                    curves.extend(getattr(bag, "fcurves", None) or ())

    return curves


def liveliness(action):
    """How much this action actually moves, in its own units."""

    total = 0.0

    for curve in curves_of(action):

        values = [point.co[1] for point in curve.keyframe_points]

        if len(values) > 1:
            total += max(values) - min(values)

    return total


def too_still(action, among):
    """
    Is this one a statue, next to the others in the file?

    Judged against the rest rather than against a number, because a
    unit is a metre in one pack and a centimetre in the next. A pack's
    idle can be a full breathing cycle or it can be nothing at all,
    and the two look the same from outside.
    """

    scores = sorted(liveliness(other) for other in among)

    if not scores:
        return False

    middle = scores[len(scores) // 2]

    # Every action reading as motionless means the curves could not be
    # read at all, not that the pack is full of statues. Nothing is
    # rejected then - a wrong guess here would replace every movement
    # in the film.
    if middle <= 0.0:
        return False

    return liveliness(action) < middle * 0.25


def stand_in_for(action_name):
    """
    The nearest movement the rig actually has, and what it cost.

    Returns (action, instead_of) - instead_of is the name that was
    asked for, when something else had to be used.
    """

    usable = [act for act in bpy.data.actions if allowed(act.name)]

    action = bpy.data.actions.get(action_name)

    if (action is not None and allowed(action_name)
            and not too_still(action, usable)):
        return action, ""

    for other in STAND_INS.get(action_name, ()):

        stand_in = bpy.data.actions.get(other)

        if (stand_in is not None and allowed(other)
                and not too_still(stand_in, usable)):
            return stand_in, action_name

    # Nothing close. Anything that moves and is not violent beats
    # standing still, so take the liveliest one going.
    moving = [act for act in usable if act.name != FALLBACK_ACTION]

    if moving:
        return max(moving, key=liveliness), action_name

    # Only then, and only because something has to be on the rig.
    return action or bpy.data.actions.get(FALLBACK_ACTION), action_name


def play(rig, action_name):
    """Put an action on the rig, and say how long it runs."""

    action, instead = stand_in_for(action_name)

    if action is None:
        raise SystemExit(f"No action '{action_name}' and no fallback.")

    if rig.animation_data is None:
        rig.animation_data_create()

    rig.animation_data.action = action

    start, end = (int(round(v)) for v in action.frame_range)

    called = action.name if not instead else f"{action.name} (for {instead})"

    return called, max(1, end - start), start


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

    # Render the action once, however short it is. Holding on the last
    # pose for the rest of the shot is the standing-still problem
    # again, so instead the frames repeat - straight for a cycle,
    # forwards and back for anything else.
    scene.frame_end = start + min(wanted, length)

    scene.render.fps = FPS

    # What the action has to give, and what the shot asks for. The
    # second is what comes out, because the frames repeat to fill it.
    rendered = scene.frame_end - scene.frame_start + 1

    # Blender writes the frames and ffmpeg makes the film, always.
    # Blender installed with pip is built without ffmpeg and cannot
    # write video at all, and even where it can, a clip it wrote
    # cannot have its frames reordered to fill the shot.
    pictures = Path(target).with_suffix("")

    if pictures.exists():
        shutil.rmtree(pictures)

    pictures.mkdir(parents=True)

    scene.render.filepath = str(pictures / "f")

    scene.render.image_settings.file_format = "PNG"

    bpy.ops.render.render(animation=True)

    join(pictures, target, wanted)

    shutil.rmtree(pictures)

    if rendered < wanted:
        name = f"{name} x{wanted / rendered:.1f}"

    return name, camera_name, wanted


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
        scene.render.engine = an_engine(engine)

    tall = aim_cameras(rig, width, height)

    print(f"Framing   : {tall:.2f} units tall, cameras set for "
          f"{width}x{height}")

    if scene.render.engine == "BLENDER_WORKBENCH":
        flat_but_visible(scene)

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
