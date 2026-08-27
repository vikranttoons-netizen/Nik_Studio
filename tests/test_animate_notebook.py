"""
Runs cell 2 of colab/NikStudio_Animate.ipynb for real, with a stand-in
for the model.

Everything except the GPU is the notebook's own code: the ordering, the
pre-flight checks, the song split, the frame counts, the stretch and
trim, the concat, the audio mux, and the stamps that decide whether a
clip can be reused. Only the model is pretended.

This matters more than a usual test. The notebook runs on a GPU that is
charged by the minute, so a mistake in it is not just a failure - it is a
failure someone paid for.

Needs FFmpeg on PATH (or imageio-ffmpeg installed). No GPU.

Run from the project root:

    python tests/test_animate_notebook.py
"""

import builtins
import io
import json
import subprocess
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "app"))

NOTEBOOK = PROJECT_ROOT / "colab" / "NikStudio_Animate.ipynb"

from PIL import Image                                 # noqa: E402
from services.ffmpeg_locator import find_ffmpeg       # noqa: E402


def heading(text):
    print()
    print("=" * 68)
    print(text)
    print("=" * 68)


# ======================================================================
# The stand-in GPU
# ======================================================================

class OutOfMemory(Exception):
    """Stands in for torch.cuda.OutOfMemoryError."""


CALLS = []

LOADED = []

CASTING = []

OFFLOADED = []

FAIL_FIRST_CALL = [False]

HAS_GPU = [True]

MOUNT_FAILS = [False]

BEATS = [None]

UPLOADS = [{}]

DOWNLOADED = []

SHIFTED = []

DRAWN = []

LIKENESS = []

EYES = []

DRAW_NEGATIVE_SEEN = []

# Every frame identical, so the only thing that can move in the
# finished video is the camera. Used by the beat-pulse test, which is
# measuring the camera and nothing else.
STILL_FRAMES = [False]


def textured(width, height):
    """A still picture with enough detail in it to see a zoom."""

    import random

    speckle = Image.new("RGB", (32, 18))

    rolls = random.Random(7)

    speckle.putdata([
        (rolls.randrange(256), rolls.randrange(256), rolls.randrange(256))
        for _ in range(32 * 18)
    ])

    return speckle.resize((width, height), Image.NEAREST)


class StandInDrawing:
    """Stands in for SDXL with an IP-Adapter on it."""

    def load_ip_adapter(self, repository, **kw):
        LIKENESS.append(dict(kw, repository=repository))

    def set_ip_adapter_scale(self, scale):
        LIKENESS.append({"scale": scale})

    def enable_model_cpu_offload(self):
        return None

    def to(self, device):
        return self

    def __call__(self, **asked):

        DRAWN.append(asked)

        DRAW_NEGATIVE_SEEN.append(asked.get("negative_prompt", ""))

        return types.SimpleNamespace(images=[
            Image.new("RGB", (asked["width"], asked["height"]),
                      (30, 160, 90))
        ])


class StandInPipeline:
    """
    Answers the calls the notebook makes on the real pipeline, and
    records what it was asked for so the test can check it.
    """

    def __init__(self, transformer=None):
        self.transformer = transformer or types.SimpleNamespace(
            to=lambda device: None
        )
        self.vae = types.SimpleNamespace(
            to=lambda device: None,
            enable_tiling=lambda: None,
        )
        self.text_encoder = types.SimpleNamespace(to=lambda device: None)
        self.scheduler = types.SimpleNamespace(config={})

    def to(self, device):
        return self

    def enable_model_cpu_offload(self):
        return None

    def __call__(self, **asked):

        CALLS.append(asked)

        if FAIL_FIRST_CALL[0] and len(CALLS) == 1:
            raise OutOfMemory("pretending the card is full")

        width, height = asked["width"], asked["height"]

        if STILL_FRAMES[0]:
            one = textured(width, height)
            frames = [one.copy() for _ in range(asked["num_frames"])]
        else:
            frames = [
                Image.new("RGB", (width, height),
                          (number * 3 % 255, 80, 160))
                for number in range(asked["num_frames"])
            ]

        return types.SimpleNamespace(frames=[frames])


def export_to_video(frames, path, fps=24):
    """What diffusers.utils.export_to_video does, via ffmpeg."""

    folder = Path(path).parent / "_frames"
    folder.mkdir(parents=True, exist_ok=True)

    for number, frame in enumerate(frames):
        frame.save(folder / f"{number:05d}.png")

    subprocess.run(
        [
            find_ffmpeg(), "-y", "-loglevel", "error",
            "-framerate", str(fps),
            "-i", str(folder / "%05d.png"),
            "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
    )

    for leftover in folder.iterdir():
        leftover.unlink()

    folder.rmdir()


def install_stand_ins(vram, ram, capability):

    torch = types.ModuleType("torch")
    torch.bfloat16, torch.float16 = "bfloat16", "float16"
    torch.float32 = "float32"
    torch.float8_e4m3fn = "fp8"
    torch.device = lambda name: name
    torch.OutOfMemoryError = OutOfMemory
    torch.Generator = lambda *a, **k: types.SimpleNamespace(
        manual_seed=lambda seed: None
    )
    torch.cuda = types.SimpleNamespace(
        is_available=lambda: HAS_GPU[0],
        get_device_name=lambda index=0: "Stand-in GPU",
        get_device_properties=lambda index=0: types.SimpleNamespace(
            total_memory=vram * 1e9
        ),
        get_device_capability=lambda: (capability, 0),
        memory_allocated=lambda: 9.4e9,
        empty_cache=lambda: None,
        OutOfMemoryError=OutOfMemory,
    )
    sys.modules["torch"] = torch

    def load(model, **kw):
        LOADED.append(model)
        return StandInPipeline(kw.get("transformer"))

    class StandInTransformer:
        def to(self, device):
            return self

        def enable_layerwise_casting(self, **kw):
            CASTING.append(kw)

        def enable_group_offload(self, **kw):
            OFFLOADED.append(("transformer", kw))

    diffusers = types.ModuleType("diffusers")
    diffusers.AutoModel = types.SimpleNamespace(
        from_pretrained=lambda model, **kw: StandInTransformer()
    )
    hooks = types.ModuleType("diffusers.hooks")
    hooks.apply_group_offloading = lambda module, **kw: OFFLOADED.append(
        ("component", kw)
    )
    diffusers.hooks = hooks
    sys.modules["diffusers.hooks"] = hooks
    diffusers.LTXImageToVideoPipeline = types.SimpleNamespace(
        from_pretrained=load
    )
    diffusers.LTXConditionPipeline = types.SimpleNamespace(
        from_pretrained=load
    )
    def load_drawing(model, **kw):
        LOADED.append(model)
        return StandInDrawing()

    diffusers.StableDiffusionXLPipeline = types.SimpleNamespace(
        from_pretrained=load_drawing
    )
    diffusers.WanPipeline = types.SimpleNamespace(from_pretrained=load)
    diffusers.WanImageToVideoPipeline = types.SimpleNamespace(
        from_pretrained=load
    )
    diffusers.AutoencoderKLWan = types.SimpleNamespace(
        from_pretrained=lambda model, **kw: types.SimpleNamespace(
            to=lambda device: None, enable_tiling=lambda: None
        )
    )
    diffusers.UniPCMultistepScheduler = types.SimpleNamespace(
        from_config=lambda config, **kw: SHIFTED.append(kw)
    )
    utilities = types.ModuleType("diffusers.utils")
    utilities.export_to_video = export_to_video
    diffusers.utils = utilities
    sys.modules["diffusers"] = diffusers
    sys.modules["diffusers.utils"] = utilities

    transformers = types.ModuleType("transformers")
    transformers.BitsAndBytesConfig = lambda **kw: None
    transformers.T5EncoderModel = types.SimpleNamespace(
        from_pretrained=lambda *a, **kw: object()
    )

    # The IP-Adapter's own image encoder. Which one is loaded is the
    # whole of the bug this stands in for, so the subfolder is recorded.
    transformers.CLIPVisionModelWithProjection = types.SimpleNamespace(
        from_pretrained=lambda model, **kw: EYES.append(
            dict(kw, repository=model)
        )
    )
    transformers.CLIPImageProcessor = lambda *a, **kw: object()
    sys.modules["transformers"] = transformers

    display = types.ModuleType("IPython.display")
    display.Video = lambda *a, **kw: "<video>"
    display.display = lambda *a, **kw: None
    package = types.ModuleType("IPython")
    package.display = display
    sys.modules["IPython"] = package
    sys.modules["IPython.display"] = display

    builtins.display = lambda *a, **kw: None

    if BEATS[0] is not None:
        librosa = types.ModuleType("librosa")
        librosa.load = lambda path, sr=None, mono=True: ([], 22050)
        librosa.beat = types.SimpleNamespace(
            beat_track=lambda y, sr: (120.0, BEATS[0])
        )
        librosa.frames_to_time = lambda frames, sr: frames
        sys.modules["librosa"] = librosa
    else:
        sys.modules.pop("librosa", None)

    psutil = types.ModuleType("psutil")
    psutil.virtual_memory = lambda: types.SimpleNamespace(total=ram * 1e9)
    sys.modules["psutil"] = psutil

    if MOUNT_FAILS[0]:

        class MessageError(Exception):
            pass

        def refuse(*a, **kw):
            raise MessageError("credential propagation was unsuccessful")

        def hand_over(names):
            """What files.upload() does: puts them in the cwd."""
            for name, data in UPLOADS[0].items():
                Path(name).write_bytes(data)
            return dict(UPLOADS[0])

        colab = types.ModuleType("google.colab")
        colab.drive = types.SimpleNamespace(mount=refuse)
        colab.files = types.SimpleNamespace(
            upload=lambda: hand_over(UPLOADS[0]),
            download=lambda path: DOWNLOADED.append(path),
        )
        google = types.ModuleType("google")
        google.colab = colab
        sys.modules["google"] = google
        sys.modules["google.colab"] = colab

    else:
        for name in ("google", "google.colab"):
            sys.modules.pop(name, None)


# ======================================================================

def cell_two():

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))

    return "".join(notebook["cells"][2]["source"])


def run(drive, vram=24.0, ram=53.0, capability=8, out_of_memory=False,
        mounted=None, gpu=True, test_one=False, mount_fails=False,
        beats=None, short=False, full_size=False,
        uploads=None, local=None, fast=False, force="",
        quality="good"):
    """
    Run the notebook against a folder. Returns (printed, refusal, calls)
    where refusal is the message it stopped with, or "".

    `mounted` stands in for /content/drive/MyDrive, so what happens when
    the folder is not where it was expected can be tested too.
    """

    CALLS.clear()

    LOADED.clear()

    CASTING.clear()

    OFFLOADED.clear()

    DRAWN.clear()

    LIKENESS.clear()

    EYES.clear()

    DRAW_NEGATIVE_SEEN.clear()

    FAIL_FIRST_CALL[0] = out_of_memory

    HAS_GPU[0] = gpu

    MOUNT_FAILS[0] = mount_fails

    BEATS[0] = beats

    UPLOADS[0] = uploads or {}

    DOWNLOADED.clear()

    install_stand_ins(vram, ram, capability)

    source = cell_two().replace(
        'FOLDER = DRIVE + "/NikStudio"',
        f"FOLDER = {str(drive)!r}",
    ).replace(
        'DRIVE = "/content/drive/MyDrive"',
        f"DRIVE = {str(mounted or '/content/drive/MyDrive')!r}",
    ).replace(
        'LOCAL = "/content/NikStudio"',
        f"LOCAL = {str(local or '/content/NikStudio')!r}",
    ).replace(
        "TEST_ONE_PICTURE = False",
        f"TEST_ONE_PICTURE = {test_one}",
    ).replace(
        "MAKE_SHORT = True",
        f"MAKE_SHORT = {short}",
    ).replace(
        "FAST_MODEL = False",
        f"FAST_MODEL = {fast}",
    ).replace(
        'FORCE_MODEL = ""',
        f"FORCE_MODEL = {force!r}",
    ).replace(
        'QUALITY = "good"',
        f"QUALITY = {quality!r}",
    )

    if not full_size:
        # The edit does the same work at any size, and at 1920x1080
        # every test spends minutes inside ffmpeg. A ninth of the pixels,
        # unless the finished size is what the test is about.
        source = source.replace(
            "OUTPUT_WIDTH, OUTPUT_HEIGHT = 1920, 1080",
            "OUTPUT_WIDTH, OUTPUT_HEIGHT = 640, 360",
        )

    printed = io.StringIO()

    refusal = ""

    try:
        with redirect_stdout(printed):
            exec(compile(source, "NikStudio_Animate cell 2", "exec"),
                 {"__name__": "__main__"})

    except SystemExit as stop:
        refusal = str(stop)

    return printed.getvalue(), refusal, list(CALLS)


# ----------------------------------------------------------------------

def make_input(folder, names, song_seconds=19, colour=(40, 120, 200)):

    inside = folder / "Input"
    inside.mkdir(parents=True, exist_ok=True)

    for name in names:
        Image.new("RGB", (1408, 768), colour).save(inside / name)

    if song_seconds:
        subprocess.run(
            [
                find_ffmpeg(), "-y", "-loglevel", "error",
                "-f", "lavfi",
                "-i", f"sine=frequency=440:duration={song_seconds}",
                str(inside / "song.mp3"),
            ],
            check=True,
        )

    return folder


def probe(path, entries):

    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", entries,
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True,
    )

    return result.stdout.split()


# ======================================================================

def test_end_to_end(root):

    heading("1  Pictures and a song become one MP4")

    drive = make_input(root / "Whole", ["shot1.png", "shot2.png",
                                        "shot10.png"])

    printed, refusal, calls = run(drive)

    assert not refusal, refusal

    order = [
        line.split()[1].rstrip(":") for line in printed.splitlines()
        if line.startswith("[") and "animating" in line
    ]

    print("   order  :", order)

    # "shot2" must not land after "shot10" just because 1 sorts before 2.
    assert order == ["shot1", "shot2", "shot10"], order
    assert len(calls) == 3, calls

    final = drive / "Output" / "Episode.mp4"

    assert final.exists(), "no Episode.mp4"

    length = float(probe(final, "format=duration")[0])
    streams = probe(final, "stream=codec_type")

    print(f"   output : {length:.1f}s, streams {streams}")

    assert "video" in streams and "audio" in streams, streams
    assert abs(length - 19) < 0.5, length

    print("\n   [OK] right order, right length, song attached")


def test_resume(root):

    heading("2  A second run remakes nothing")

    drive = make_input(root / "Resume", ["Scene01.png", "Scene02.png"])

    run(drive)

    printed, refusal, calls = run(drive)

    assert not refusal, refusal

    print(f"   model asked for {len(calls)} clip(s)")

    assert calls == [], calls
    assert printed.count("already made, skipping") == 2, printed

    print("\n   [OK] a dead session costs one clip, not all of them")


def test_changed_picture_is_not_skipped(root):

    heading("3  A replaced picture does not keep its old clip")

    drive = make_input(root / "Changed", ["Scene01.png", "Scene02.png"])

    run(drive)

    # The name is the same; the picture is not.
    Image.new("RGB", (1408, 768), (200, 40, 40)).save(
        drive / "Input" / "Scene02.png"
    )

    printed, refusal, calls = run(drive)

    assert not refusal, refusal

    print("  ", [line.strip() for line in printed.splitlines()
                 if "Scene0" in line and ("skip" in line or "again" in line)])

    assert len(calls) == 1, calls
    assert "Scene02: changed since last time" in printed

    print("\n   [OK] only the picture that changed was made again")


def test_refuses_too_few_pictures(root):

    heading("4  Too few pictures for the song stops before the GPU")

    # One picture asked to carry a minute. Even at the lowest frame rate
    # a clip covers about 16s, so this one would have to be stretched
    # nearly four times over.
    drive = make_input(root / "Thin", ["Scene01.png"], song_seconds=60)

    printed, refusal, calls = run(drive)

    print("  ", refusal.strip().splitlines()[2].strip()[:66], "...")

    assert calls == [], "the model was loaded anyway"
    assert "Stopping before the GPU is used" in refusal
    assert "about 5 shots" in refusal, refusal

    print("\n   [OK] refused, and said how many pictures it needs")


def test_the_edit_cuts_it_up(root):

    heading("4b  Eleven clips become an edit of many short shots")

    # 11 pictures over a two minute song. The old answer was eleven
    # eleven-second holds, which is a slideshow. The answer now is to
    # cut every few seconds and come back to each clip more than once.
    drive = make_input(
        root / "Long",
        [f"Scene{n:02d}.png" for n in range(1, 12)],
        song_seconds=125,
    )

    printed, refusal, calls = run(drive, full_size=True)

    assert not refusal, refusal

    # The model is asked for one shot's worth and no more, whatever the
    # song is doing. 97 frames is 4.0s at 24fps - a good second longer
    # than a shot needs, because a model given "he claps three times"
    # and three seconds does three claps in three seconds, and the
    # first clip that came back was frantic.
    asked = {call["num_frames"] for call in calls}

    assert asked == {97}, asked
    assert len(calls) == 11, len(calls)

    editing = [line for line in printed.splitlines()
               if line.startswith("Editing:")][0]

    print("  ", editing.strip())

    shots = int(editing.split()[1])

    # 125 seconds cut every ~2.8s is around forty shots, and certainly
    # a lot more than the eleven clips they are drawn from.
    assert shots > 30, shots

    final = drive / "Output" / "Episode.mp4"

    length = float(probe(final, "format=duration")[0])
    size = probe(final, "stream=width,height")

    print(f"   {len(calls)} clips -> {shots} shots -> {length:.1f}s "
          f"at {size[0]}x{size[1]}")

    assert abs(length - 125) < 1.5, length
    assert size[:2] == ["1920", "1080"], size

    print("\n   [OK] eleven clips, forty-odd shots, and it fits the song")


def test_cuts_land_on_the_beat(root):

    heading("4c  The cuts land on the beat, not on a stopwatch")

    drive = make_input(root / "Beat", ["Scene01.png", "Scene02.png"],
                       song_seconds=19)

    # A slow, deliberately uneven beat, so a grid cannot fake it.
    beat = [1.3, 2.6, 3.9, 5.2, 6.5, 7.8, 9.1, 10.4, 11.7, 13.0,
            14.3, 15.6, 16.9, 18.2]

    printed, refusal, _ = run(drive, beats=beat)

    assert not refusal, refusal
    assert "cut on the beat" in printed, printed
    assert "could not find the beat" not in printed, printed
    assert "even grid" not in printed, printed

    # Rebuilt the way the notebook does, to check where the cuts fell.
    points, target = [0.0], 2.8

    for moment in beat:
        if moment - points[-1] >= target:
            points.append(moment)

    print(f"   {len(beat)} beats -> cuts at "
          f"{[round(p, 1) for p in points[1:]]}")

    assert all(point in beat for point in points[1:]), points

    print("\n   [OK] every cut is on a beat of the song")


def test_without_librosa(root):

    heading("4d  No beat detection is a plainer edit, not a failure")

    drive = make_input(root / "NoBeat", ["Scene01.png", "Scene02.png"],
                       song_seconds=19)

    printed, refusal, _ = run(drive)

    assert not refusal, refusal
    assert "could not find the beat" in printed, printed
    assert "cut on an even grid" in printed, printed
    assert "cut on the beat" not in printed, printed

    final = drive / "Output" / "Episode.mp4"

    length = float(probe(final, "format=duration")[0])

    print(f"   fell back to an even grid -> {length:.1f}s")

    assert abs(length - 19) < 0.6, length

    print("\n   [OK] still cut up, just on an even grid")


def test_refuses_broken_picture(root):

    heading("5  A file that is not really a picture stops the run")

    drive = make_input(root / "Broken", ["Scene01.png", "Scene02.png",
                                         "Scene03.png"])

    (drive / "Input" / "Scene02.png").write_text("not a picture")

    printed, refusal, calls = run(drive)

    print("  ", refusal.strip().splitlines()[-3].strip())

    assert calls == [], "the model was loaded anyway"
    assert "Scene02.png will not open" in refusal, refusal

    print("\n   [OK] caught before a minute of GPU time was spent")


def test_settings_follow_the_machine(root):

    heading("6  Precision and 8-bit follow the card; size follows the model")

    drive = make_input(root / "Tiers", ["Scene01.png", "Scene02.png",
                                        "Scene03.png"])

    for label, vram, ram, capability, precision, quantised, size in [
        ("A100 40GB, 83GB RAM", 40, 83, 8, "bfloat16", False, 1024),
        ("L4 24GB, 13GB RAM  ", 24, 12.7, 8, "bfloat16", True, 768),
        ("T4 16GB, 13GB RAM  ", 15.6, 12.7, 7, "float16", True, 768),
    ]:
        # Two of these cards are too small for Wan and would be sent
        # away. This test is about precision and fitting, so it says
        # "small on purpose" and gets on with it.
        printed, refusal, calls = run(
            drive, vram, ram, capability,
            force="" if vram >= 20 and ram >= 30 else "small",
        )

        assert not refusal, refusal

        assert precision in printed, printed
        assert ("text encoder in 8-bit" in printed) is quantised, printed

        # The size asked for comes from what the model was trained on.
        # A bigger card is a reason to run a bigger model, never a
        # reason to push a model past what it knows - 1024x576 on the 2B
        # is where the picture came apart.
        assert all(call["width"] == size for call in calls), calls

        print(f"   {label}: {size}px wide, {precision}"
              f"{', 8-bit' if quantised else ''}")

        for clip in (drive / "Output" / "Clips").glob("*"):
            clip.unlink()

    print("\n   [OK] the card changes how it fits, not what it asks for")


def test_out_of_memory_is_survived(root):

    heading("7  A full card gives a shorter clip, not a dead run")

    drive = make_input(root / "Oom", ["Scene01.png", "Scene02.png"])

    printed, refusal, calls = run(drive, out_of_memory=True)

    assert not refusal, refusal

    print("  ", [line.strip() for line in printed.splitlines()
                 if "ran out" in line])

    assert "card ran out of room" in printed, printed
    assert len(calls) == 3, calls          # one failed, then two clips

    assert (drive / "Output" / "Episode.mp4").exists()

    print("\n   [OK] recovered and still produced the video")


def test_without_a_song(root):

    heading("8  No song is a warning, not a failure")

    drive = make_input(root / "Silent", ["Scene01.png", "Scene02.png"],
                       song_seconds=0)

    printed, refusal, calls = run(drive)

    assert not refusal, refusal
    assert "none found" in printed, printed

    final = drive / "Output" / "Episode.mp4"

    length = float(probe(final, "format=duration")[0])

    print(f"   {len(calls)} pictures at 5s each -> {length:.1f}s, "
          f"streams {probe(final, 'stream=codec_type')}")

    assert abs(length - 10) < 0.5, length

    print("\n   [OK] falls back to a fixed length per picture")



def test_finds_a_folder_that_moved(root):

    heading("9  A folder that is not where it was expected")

    mounted = root / "Mounted"

    # What the user actually has: pictures under a differently named
    # parent, which is what a second Google account or a stray folder
    # looks like from in here.
    real = mounted / "Kids" / "NikStudio" / "Input"

    make_input(real.parent, ["Scene01.png", "Scene02.png"])

    printed, refusal, calls = run(
        root / "Nowhere" / "NikStudio", mounted=mounted,
    )

    print("  ", [line.strip() for line in printed.splitlines()
                 if "Found your pictures" in line][0])

    assert not refusal, refusal
    assert len(calls) == 2, calls
    assert (real.parent / "Output" / "Episode.mp4").exists()

    print("\n   [OK] found it, and wrote the video beside it")


def test_says_what_it_can_see(root):

    heading("10  Nothing found at all is a map, not a shrug")

    mounted = root / "Bare"

    for name in ("Photos", "Documents", "Colab Notebooks"):
        (mounted / name).mkdir(parents=True)

    printed, refusal, calls = run(
        root / "Missing" / "NikStudio", mounted=mounted,
    )

    print("  ", refusal.strip().splitlines()[-3].strip())
    print("  ", refusal.strip().splitlines()[-1].strip())

    assert calls == [], calls
    assert "same Google account" in refusal, refusal
    assert "Photos" in refusal and "Documents" in refusal, refusal

    print("\n   [OK] names the two usual causes and lists the Drive")


def test_offers_the_choices(root):

    heading("11  Several candidates are offered, not guessed between")

    mounted = root / "Several"

    for parent in ("First", "Second"):
        make_input(mounted / parent / "NikStudio", ["Scene01.png"])

    printed, refusal, calls = run(
        root / "Absent" / "NikStudio", mounted=mounted,
    )

    print("  ", [line.strip() for line in refusal.splitlines()
                 if line.strip().startswith(str(mounted))])

    assert calls == [], calls
    assert "First" in refusal and "Second" in refusal, refusal
    assert "put the right one in FOLDER" in refusal, refusal

    print("\n   [OK] two matches, so it asks instead of choosing")



def test_checks_before_a_gpu_is_needed(root):

    heading("12  Every check runs with no GPU, so checking is free")

    drive = make_input(root / "Free", ["Scene01.png", "Scene02.png"])

    printed, refusal, calls = run(drive, gpu=False)

    print("  ", refusal.strip().splitlines()[0])

    assert calls == [], "the model was loaded without a GPU"
    assert "Everything checks out" in printed, printed
    assert "cost nothing" in refusal, refusal
    assert "L4 GPU" in refusal, refusal

    # A bad folder must still be caught, and caught the same way.
    broken = make_input(root / "FreeBad", ["Scene01.png"])
    (broken / "Input" / "Scene01.png").write_text("not a picture")

    _, refusal, calls = run(broken, gpu=False)

    assert calls == [], calls
    assert "will not open" in refusal, refusal

    print("   a broken picture is caught without a GPU too")

    print("\n   [OK] nothing is spent finding out the files are wrong")



def test_one_picture_on_its_own(root):

    heading("13  Trying one picture out, without the song in the way")

    drive = make_input(
        root / "TestOne",
        [f"Scene{n:02d}.png" for n in range(1, 12)],
        song_seconds=125,
    )

    printed, refusal, calls = run(drive, test_one=True)

    assert not refusal, refusal

    print("  ", [line.strip() for line in printed.splitlines()
                 if line.startswith("TEST")][0])

    # One clip, from the first picture, at its own length - not looped
    # to fill a slot and not cut to a share of the song.
    assert len(calls) == 1, calls
    assert calls[0]["num_frames"] == 97, calls
    assert "back and forth" not in printed, printed

    final = drive / "Output" / "Episode.mp4"

    length = float(probe(final, "format=duration")[0])
    streams = probe(final, "stream=codec_type")

    print(f"   {length:.1f}s, streams {streams}")

    assert abs(length - 97 / 24) < 0.3, length
    assert "audio" not in streams, "the song was laid over a test clip"

    # Nor the words. The first test clip came back with a line of the
    # song burned across it, which is not what a test of the model is
    # for.
    assert "drawn on" not in printed, printed

    print("\n   [OK] one clip, its own length, nothing over the top")


def test_the_refusal_offers_the_test(root):

    heading("14  Being refused tells you how to try one picture")

    drive = make_input(root / "Hint", ["Scene01.png"], song_seconds=125)

    _, refusal, calls = run(drive)

    print("  ", [line.strip() for line in refusal.splitlines()
                 if "TEST_ONE_PICTURE" in line][0][:70], "...")

    assert calls == [], calls
    assert "TEST_ONE_PICTURE = True" in refusal, refusal

    print("\n   [OK] the way out is in the message, not in my head")



def test_drive_refusing_to_connect(root):

    heading("15  Drive refusing to sign in no longer stops the run")

    # What Colab does when the browser blocks the sign-in popup. Asking
    # someone to fight their cookie settings before they can see a
    # single clip is not a reasonable thing to do, so it carries on with
    # the session's own disk instead.
    printed, refusal, calls = run(
        root / "Missing" / "NikStudio",
        mounted=root / "NotMounted",
        mount_fails=True,
        # Where the run lands without Drive. Pinned to this test's own
        # folder: on the real thing it is /content/NikStudio, and one
        # test leaving clips there is another test finding them already
        # made and generating nothing.
        local=root / "NoDriveSession",
        uploads={
            "script.txt": b"He waves at the puppy\nHe claps his hands\n",
        },
    )

    assert not refusal, refusal

    print("  ", [line.strip() for line in printed.splitlines()
                 if "would not connect" in line][0][:66], "...")
    print("  ", [line.strip() for line in printed.splitlines()
                 if "Carrying on" in line][0][:66], "...")

    assert "third-party cookies" in printed, printed
    assert "Carrying on without it" in printed, printed

    # And it really did the work, from files handed straight over.
    assert len(calls) == 2, calls

    print(f"   {len(DOWNLOADED)} file(s) handed back to the PC")

    assert DOWNLOADED, "the video was left in a session about to be deleted"

    print("\n   [OK] no Drive, no stopping - uploaded in, downloaded out")



def test_the_machine_picks_the_model(root):

    heading("16  A card with room for it gets the model that moves")

    drive = make_input(root / "Models", ["Scene01.png", "Scene02.png"])

    SHIFTED.clear()

    # The default, on a card that can take it. Wan, because motion is
    # the whole complaint about what LTX gave back - and at real
    # guidance, so the negative prompt is read.
    printed, refusal, calls = run(drive, 24, 57, 8)

    assert not refusal, refusal

    print(f"   L4 24GB, default   : {LOADED[-1].split('/')[-1]}")

    assert LOADED[-1].endswith("Wan2.2-TI2V-5B-Diffusers"), LOADED[-1]
    assert all(c["num_inference_steps"] == 30 for c in calls), calls
    assert all(c["guidance_scale"] == 5.0 for c in calls), calls

    # Wan has no frame_rate argument, and the LTX-only settings must
    # not be sent to it.
    assert all("frame_rate" not in c for c in calls), calls
    assert all("image_cond_noise_scale" not in c for c in calls), calls

    # 1024x576 by default - 1.9x up to 1080p rather than the 2.3x
    # that 832x480 needed, which was most of the softness. Both
    # divide by 32, which the Wan VAE requires.
    assert all(c["width"] == 1024 and c["height"] == 576 for c in calls)

    # And the clip covers a whole shot on its own, so nothing has to be
    # played backwards to fill the time.
    assert all(c["num_frames"] == 97 for c in calls), calls
    assert "forwards only" in printed, printed

    # One setting, three answers, and the finished size is what makes
    # the difference: 832x480 is stretched 2.3 times to reach 1080p.
    #
    # flow_shift follows the size rather than being one number. Wan is
    # tuned at 5.0 for 720p and 3.0 for 480p, and the 720p figure on a
    # 480p clip drifts magenta and bends the arms where they do not
    # bend - which is exactly what the first draft clip did.
    for quality, size, steps, shift in (("draft", 832, 25, 3.0),
                                        ("good", 1024, 30, 3.0),
                                        ("best", 1280, 30, 5.0)):

        for clip in (drive / "Output" / "Clips").glob("*"):
            clip.unlink()

        SHIFTED.clear()

        printed, refusal, calls = run(drive, 24, 57, 8, quality=quality)

        assert not refusal, refusal
        assert all(c["width"] == size for c in calls), calls
        assert all(c["num_inference_steps"] == steps for c in calls), calls
        assert SHIFTED and SHIFTED[0]["flow_shift"] == shift, (quality,
                                                               SHIFTED)

        print(f"   QUALITY {quality:<7}: {size} wide, {steps} steps, "
              f"flow_shift {shift}")

    for clip in (drive / "Output" / "Clips").glob("*"):
        clip.unlink()

    # FAST_MODEL is how you buy speed back, knowingly.
    printed, refusal, calls = run(drive, 24, 57, 8, fast=True)

    assert not refusal, refusal

    print(f"   L4 24GB, FAST_MODEL: {LOADED[-1].split('/')[-1]}")

    assert "13B-distilled" in LOADED[-1], LOADED[-1]
    assert all(c["num_inference_steps"] == 8 for c in calls), calls
    assert all(c["guidance_scale"] == 1.0 for c in calls), calls
    assert all(c["image_cond_noise_scale"] == 0.0 for c in calls)

    # fp8 storage and leaf offloading, or 13B in bfloat16 is 26GB
    # against a 24GB card.
    assert CASTING and CASTING[0]["storage_dtype"] == "fp8", CASTING

    for clip in (drive / "Output" / "Clips").glob("*"):
        clip.unlink()

    # And a small card cannot run either, so it gets the 2B.
    printed, refusal, calls = run(drive, 15.6, 12.7, 7, force="small")

    assert not refusal, refusal

    print(f"   T4 16GB            : {LOADED[-1].split('/')[-1]}")

    assert LOADED[-1] == "Lightricks/LTX-Video", LOADED[-1]
    assert all(c["width"] == 768 for c in calls), calls

    print("\n   [OK] obedient by default, fast on request, small where it must")


def test_a_small_card_is_sent_away(root):

    heading("23  A card too small for the model that moves stops the run")

    drive = make_input(root / "SmallCard", ["Scene01.png", "Scene02.png"])

    # A T4, with a GPU really connected. The notebook used to print
    # which model it had picked and carry on regardless - an hour spent
    # on the model whose whole problem is that it does not move.
    printed, refusal, calls = run(drive, 15.6, 12.7, 7)

    assert calls == [], "an hour of the wrong model was spent anyway"

    print("  ", refusal.strip().splitlines()[2].strip())

    assert "L4 GPU" in refusal, refusal
    assert "drifts rather than moves" in refusal, refusal
    assert 'FORCE_MODEL = "small"' in refusal, refusal

    # The free check on a CPU runtime must still do its job: it has no
    # card to judge, so it assumes the one you are about to turn on.
    printed, refusal, calls = run(drive, 15.6, 12.7, 7, gpu=False)

    assert "cost nothing" in refusal, refusal
    assert "L4 GPU > Save" in refusal, refusal

    print("   the free check on a CPU runtime still runs")

    # And it can be overruled, knowingly.
    printed, refusal, calls = run(drive, 15.6, 12.7, 7, force="small")

    assert not refusal, refusal
    assert len(calls) == 2, calls

    print("\n   [OK] stopped before the hour, and can be overruled")


def test_one_picture_of_him(root):

    heading("24  One picture of Nik, and every scene is drawn from him")

    drive = make_input(root / "Reference", [], song_seconds=19)

    inside = drive / "Input"

    # The reference, and nothing else that looks like a scene.
    Image.new("RGB", (768, 768), (210, 170, 140)).save(inside / "nik.png")

    (inside / "script.txt").write_text(
        "He waves both hands above his head, the puppy sitting beside "
        "him\n"
        "He claps his hands three times quickly, the puppy bouncing\n"
        "He jumps up and down twice, the duckling flapping beside him\n",
        encoding="utf-8",
    )

    printed, refusal, calls = run(drive)

    assert not refusal, refusal

    # It is the boy, not a scene. Animating it would put a picture of
    # him standing on his own into the middle of the video, and it must
    # not be counted when the run works out whether there is enough for
    # the song either.
    assert "every scene is drawn from him" in printed, printed
    assert len(calls) == 3, calls

    print(f"   {len(DRAWN)} scene(s) drawn, {len(calls)} clip(s) animated")

    assert len(DRAWN) == 3, DRAWN

    # The reference is in front of the drawing model for every one, and
    # pulling at the strength that was asked for.
    assert all(draw["ip_adapter_image"] is not None for draw in DRAWN)
    assert {"scale": 0.5} in LIKENESS, LIKENESS

    # The image encoder is named rather than left to SDXL's default.
    # ip-adapter-plus_sdxl_vit-h wants CLIP ViT-H at 1280 wide; SDXL
    # ships ViT-bigG at 1664, and the mismatch fails inside the first
    # step with "mat1 and mat2 shapes cannot be multiplied".
    assert EYES, "no image encoder was chosen - SDXL's default will not fit"
    assert EYES[0]["subfolder"] == "models/image_encoder", EYES

    print(f"   image encoder: {EYES[0]['repository']}/"
          f"{EYES[0]['subfolder']}")

    # And what SDXL is asked to draw fits in the 77 tokens it reads.
    # The video prompt is about 225, and the first attempt sent that -
    # so the framing, the character and the style were all cut off.
    for draw in DRAWN:

        words = len(draw["prompt"].split())

        assert words <= 55, (words, draw["prompt"])

        assert "chubby cheerful" not in draw["prompt"], draw["prompt"]
        assert "Pixar" in draw["prompt"], draw["prompt"]
        assert "wide shot" in draw["prompt"], draw["prompt"]

        # And somewhere to stand. Without this a drawing came back
        # perfectly lit and perfectly framed against a flat black
        # nothing - and the video model animates what it is given, so
        # no meadow arrives later.
        assert "sunny green meadow" in draw["prompt"], draw["prompt"]

        # And what "full body" means, said in words a drawing can be
        # checked against - "full body, centred" on its own came back
        # with his legs cut off at the shins and a hand off the edge.
        assert "hair to shoes inside the frame" in draw["prompt"]

    assert "black background" in DRAW_NEGATIVE_SEEN[0], DRAW_NEGATIVE_SEEN

    print(f"   drawing prompt: {max(len(d['prompt'].split()) for d in DRAWN)}"
          " words at its longest, against the 55 that fit")

    weights = [entry for entry in LIKENESS if "weight_name" in entry]

    assert weights and "sdxl" in weights[0]["weight_name"], weights

    # Drawn at a size SDXL knows, not at the video size.
    assert all(draw["width"] == 1344 and draw["height"] == 768
               for draw in DRAWN), DRAWN

    # And the video is made FROM the drawings - words alone would send
    # no picture at all.
    assert all("image" in call for call in calls), calls
    assert all(call["width"] == 1024 for call in calls), calls

    scenes = sorted((drive / "Output" / "Scenes").glob("*.png"))

    print(f"   kept on disk: {', '.join(f.name for f in scenes)}")

    assert len(scenes) == 3, scenes

    # Second time round nothing is drawn again.
    printed, refusal, calls = run(drive)

    assert not refusal, refusal
    assert DRAWN == [], "the scenes were drawn a second time"

    print("   a second run drew nothing and animated nothing")

    print("\n   [OK] one reference in, the same boy in every scene")


def test_a_preview_small_enough_to_send(root):

    heading("25  A copy small enough to send back")

    drive = make_input(root / "Preview", ["Scene01.png", "Scene02.png"])

    printed, refusal, calls = run(drive, full_size=True)

    assert not refusal, refusal

    preview = drive / "Output" / "Episode_Preview.mp4"

    assert preview.exists(), "no preview was made"

    big = (drive / "Output" / "Episode.mp4").stat().st_size

    small = preview.stat().st_size

    print(f"   Episode.mp4 {big / 1e6:.1f}MB -> "
          f"Episode_Preview.mp4 {small / 1e6:.1f}MB")

    assert small < 25e6, small
    assert small < big, (small, big)

    wide = int(probe(preview, "stream=width")[0])

    assert wide in (640, 480, 384), wide

    print("\n   [OK] the finished video can always be sent back")


def test_the_helper_wan_needs(root):

    heading("26  The one small package Wan dies without")

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))

    packages = "".join(notebook["cells"][1]["source"])

    source = "".join(notebook["cells"][2]["source"])

    # Wan runs every prompt through ftfy.fix_text, and diffusers imports
    # ftfy only if it is already installed - so a runtime without it
    # says nothing, downloads 31GB, and dies on the first clip with
    # "name 'ftfy' is not defined". That is a very long way to travel
    # for a 60KB package.
    assert "ftfy" in packages, packages

    print("   cell 1 installs it")

    # And cell 2 puts it back if cell 1 was skipped. This only works
    # while nothing above it has imported diffusers - that import is
    # what decides whether ftfy is available.
    heals = source.index('find_spec("ftfy")')

    first_diffusers = source.index("from diffusers import")

    assert heals < first_diffusers, (heals, first_diffusers)

    print("   cell 2 puts it back, before the first diffusers import")

    print("\n   [OK] neither cell can lose an hour to a missing helper")


def test_it_says_which_notebook_it_is(root):

    heading("27  Every run says which notebook it is")

    drive = make_input(root / "Build", ["Scene01.png", "Scene02.png"])

    printed, refusal, calls = run(drive)

    assert not refusal, refusal

    line = [row for row in printed.splitlines()
            if row.startswith("Notebook")][0]

    print(f"   {line.strip()}")

    # First line of the run, above the card. There is no other way to
    # tell one notebook from another once it is open in Colab, and a
    # clip made by an older one looks exactly like a clip the new one
    # declined to change.
    assert printed.strip().splitlines()[0].startswith("Notebook"), printed

    assert len(line.split(":", 1)[1].strip()) > 8, line

    print("\n   [OK] a run can be identified from its own output")


def test_the_cuts_follow_the_words(root):

    heading("28  The picture changes when the words do")

    beat = [n * 0.5 for n in range(1, 40)]

    drive = make_input(root / "Words", ["Scene01.png", "Scene02.png"],
                       song_seconds=19)

    (drive / "Input" / "lyrics.txt").write_text(
        "Clap your hands\nWag your tail\nMeow meow meow\n"
        "Quack quack quack\nSing with me\nWave goodbye\n",
        encoding="utf-8",
    )

    printed, refusal, calls = run(drive, beats=beat)

    assert not refusal, refusal

    line = [row for row in printed.splitlines()
            if row.startswith("Editing:")][0]

    print(f"   {line.strip()}")

    # A cut on a beat is right, but a beat is not what anyone hears
    # change - the line of the song is.
    assert "cut where each line of the song starts" in printed, printed

    # Six lines over nineteen seconds is about three seconds each,
    # which is a shot. So the shots should follow the lines, near
    # enough - not a stopwatch, and not one long take.
    shots = int(line.split()[1])

    assert 5 <= shots <= 8, line

    print(f"   6 lines of song -> {shots} shots")

    # Without lyrics it falls back to the beat, and says so.
    plain = make_input(root / "NoWords", ["Scene01.png", "Scene02.png"],
                       song_seconds=19)

    printed, refusal, calls = run(plain, beats=beat)

    assert not refusal, refusal
    assert "cut on the beat" in printed, printed

    print("   no lyrics -> back to the beat, and it says so")

    print("\n   [OK] the words and the picture change together")


def test_a_scene_for_every_line(root):

    heading("29  One scene per line means the picture shows the words")

    beat = [n * 0.5 for n in range(1, 40)]

    words = ["Clap your hands", "Wag your tail", "Meow meow meow",
             "Quack quack quack", "Sing with me", "Wave goodbye"]

    # Six lines, six scenes, in the same order.
    drive = make_input(root / "LineForLine", [], song_seconds=19)

    inside = drive / "Input"

    (inside / "lyrics.txt").write_text("\n".join(words) + "\n",
                                       encoding="utf-8")

    (inside / "script.txt").write_text(
        "\n".join(f"He does thing number {n}, the puppy beside him"
                  for n in range(1, len(words) + 1)) + "\n",
        encoding="utf-8",
    )

    printed, refusal, calls = run(drive, beats=beat)

    assert not refusal, refusal

    assert "One scene per line" in printed, printed

    print(f"   {len(words)} lines, {len(calls)} scenes -> lined up "
          "one to one")

    assert len(calls) == len(words), calls

    # And the complaint when they do not match names the number to
    # write, because this is the difference between a video of a song
    # and a video with a song over it.
    (inside / "script.txt").write_text(
        "He does one thing, the puppy beside him\n"
        "He does another, the kitten beside him\n",
        encoding="utf-8",
    )

    printed, refusal, calls = run(drive, beats=beat)

    assert not refusal, refusal

    assert "do not line up" in printed, printed
    assert f"Write {len(words)} scenes" in printed, printed

    complaint = [row for row in printed.splitlines()
                 if "Write " in row and "scenes" in row][0]

    print(f"  {complaint}")

    # And a test run - the cheapest check there is - still answers the
    # most important question. It drops the song and the words, which
    # is right, and it used to drop this with them.
    for clip in (drive / "Output" / "Clips").glob("*"):
        clip.unlink()

    printed, refusal, calls = run(drive, beats=beat, test_one=True)

    assert not refusal, refusal
    assert len(calls) == 1, calls
    assert "do not line up" in printed, printed

    print("   a one-clip test run still says whether they line up")

    print("\n   [OK] lined up when it can, and says how when it cannot")


def test_written_scenes(root):

    heading("17  Scenes written as text, with no pictures at all")

    drive = root / "Written"

    inside = drive / "Input"
    inside.mkdir(parents=True)

    (inside / "script.txt").write_text(
        "\n".join([
            "# the opening, parked for now",
            "",
            "Nik waves at the puppy while the flowers sway around them",
            "Nik runs down the garden path, the kitten chasing him",
            "Nik claps his hands as butterflies circle overhead",
        ]),
        encoding="utf-8",
    )

    subprocess.run(
        [
            find_ffmpeg(), "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=19",
            str(inside / "song.mp3"),
        ],
        check=True,
    )

    printed, refusal, calls = run(drive)

    assert not refusal, refusal

    print("  ", [line.strip() for line in printed.splitlines()
                 if line.startswith("From")][0])

    # The commented line and the blank one are not scenes.
    assert len(calls) == 3, calls

    # Nothing is sent but words - there is no picture to condition on.
    assert all("image" not in call for call in calls), calls

    # The ACTION leads. Burying it behind sixty words of costume
    # description got back a boy standing still in an empty field, so
    # the order is the point and the test holds it.
    assert calls[0]["prompt"].startswith("Nik waves at the puppy"), \
        calls[0]["prompt"][:80]
    assert calls[1]["prompt"].startswith("Nik runs down the garden path"), \
        calls[1]["prompt"][:80]

    # The character and the style are still in every one, behind it -
    # they are what keeps him the same boy from clip to clip.
    assert all("chubby cheerful 3 year old" in call["prompt"]
               for call in calls), calls[0]["prompt"]
    assert all("3D rendered CGI animation" in call["prompt"]
               for call in calls), calls[0]["prompt"]

    # And the framing sits between them, second only to the action.
    # The first Wan clip cut the top of his head off and then walked
    # him out of the picture, because nothing said where to stand.
    for call in calls:

        where = call["prompt"]

        assert "medium wide shot" in where, where
        assert "stays fully in frame" in where, where

        assert (where.index("medium wide shot")
                < where.index("chubby cheerful")
                < where.index("3D rendered CGI")), where

    # Four sentences, not one run-on. Without the full stops the
    # description ran straight into the action - "blue canvas sneakers
    # Close up of the puppy" - and was read as one clause.
    for call in calls:
        assert call["prompt"].count(". ") >= 3, call["prompt"]
        assert call["prompt"].endswith("."), call["prompt"]

    # The faults that clip had are named in the negative prompt, which
    # this model does read.
    assert "cropped head" in calls[0]["negative_prompt"]
    assert "character walking out of frame" in calls[0]["negative_prompt"]

    final = drive / "Output" / "Episode.mp4"

    length = float(probe(final, "format=duration")[0])

    print(f"   3 written scenes -> {length:.1f}s with the song")

    assert abs(length - 19) < 0.6, length

    print("\n   [OK] words in, video out, no pictures involved")


def test_a_script_wins_over_pictures(root):

    heading("18  A script.txt is what you meant, not the old pictures")

    drive = make_input(root / "Both", ["Scene01.png", "Scene02.png"])

    (drive / "Input" / "script.txt").write_text(
        "Nik jumps in a puddle\n"
        "Nik shakes the water off his hands\n"
        "Nik laughs at the puppy\n",
        encoding="utf-8",
    )

    printed, refusal, calls = run(drive)

    assert not refusal, refusal

    print("  ", [line.strip() for line in printed.splitlines()
                 if "being ignored" in line][0][:70], "...")

    assert len(calls) == 3, calls
    assert all("image" not in call for call in calls), calls
    assert "being ignored" in printed, printed

    print("\n   [OK] the written scenes ran, and it said the pictures are idle")



def test_the_vertical_cut(root):

    heading("19  A vertical cut for Shorts, beside the wide one")

    drive = make_input(root / "Short", ["Scene01.png", "Scene02.png",
                                        "Scene03.png"], song_seconds=19)

    printed, refusal, _ = run(drive, short=True, full_size=True)

    assert not refusal, refusal

    wide = drive / "Output" / "Episode.mp4"
    tall = drive / "Output" / "Episode_Short.mp4"

    assert tall.exists(), "no Shorts cut"

    wide_size = probe(wide, "stream=width,height")
    tall_size = probe(tall, "stream=width,height")

    print(f"   {wide_size[0]}x{wide_size[1]} and "
          f"{tall_size[0]}x{tall_size[1]}")

    assert wide_size[:2] == ["1920", "1080"], wide_size
    assert tall_size[:2] == ["1080", "1920"], tall_size

    # Under a minute, or YouTube does not treat it as a Short.
    assert float(probe(tall, "format=duration")[0]) <= 60

    print("\n   [OK] both cuts written, and the tall one is under a minute")



def test_the_script_under_any_name(root):

    heading("20  The notebook finds the script whatever it is called")

    for number, name in enumerate(
        ("script.txt.txt", "Script.txt", "my scenes.txt"), start=1
    ):
        drive = root / f"Named{number}"

        inside = drive / "Input"
        inside.mkdir(parents=True)

        (inside / name).write_text(
            "He waves at the puppy\n"
            "He claps his hands\n"
            "He jumps up and down\n",
            encoding="utf-8",
        )

        subprocess.run(
            [
                find_ffmpeg(), "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=19",
                str(inside / "song.mp3"),
            ],
            check=True,
        )

        printed, refusal, calls = run(drive)

        assert not refusal, (name, refusal)
        assert len(calls) == 3, (name, calls)

        print(f"   {name:<16} -> 3 scene(s), no pictures needed")

    print("\n   [OK] Explorer's hidden extension cannot break it")



def test_the_words_on_screen(root):

    heading("21  The words of the song, drawn on and on the beat")

    drive = make_input(root / "Sing", ["Scene01.png", "Scene02.png",
                                       "Scene03.png"], song_seconds=19)

    (drive / "Input" / "lyrics.txt").write_text(
        "# the chorus\n"
        "One little elephant went out to play\n"
        "Upon a spider's web one day\n"
        "He had such enormous fun\n"
        "That he called for another elephant to come\n",
        encoding="utf-8",
    )

    printed, refusal, _ = run(drive, full_size=True, short=True)

    assert not refusal, refusal

    print("  ", [l.strip() for l in printed.splitlines()
                 if l.startswith("Lyrics")][0])

    # The lyric sheet must not be mistaken for the script.
    assert "3 picture(s)" in printed or "From       : 3 picture" in printed, \
        printed

    sheet = drive / "Output" / "lyrics_1920x1080.ass"

    assert sheet.exists(), "no subtitle file was written"

    written = sheet.read_text(encoding="utf-8")

    dialogue = [l for l in written.splitlines() if l.startswith("Dialogue:")]

    print(f"   {len(dialogue)} lines timed, "
          f"font {[l for l in written.splitlines() if l.startswith('Style:')][0].split(',')[1]}")

    # The commented line is not a lyric.
    assert len(dialogue) == 4, dialogue

    # And they are inside the song, in order.
    starts = [line.split(",")[1] for line in dialogue]
    assert starts == sorted(starts), starts

    # The words are really on the picture: the bottom of the frame has
    # to differ from the same run without them.
    plain = make_input(root / "Quiet", ["Scene01.png", "Scene02.png",
                                        "Scene03.png"], song_seconds=19)

    run(plain, full_size=True)

    from PIL import Image, ImageChops, ImageStat

    def bottom(video):
        out = video.parent / f"{video.stem}_bottom.png"
        subprocess.run(
            [find_ffmpeg(), "-y", "-loglevel", "error", "-ss", "4",
             "-i", str(video), "-frames:v", "1",
             "-vf", "crop=1920:200:0:860", str(out)],
            check=True,
        )
        return Image.open(out).convert("L")

    sung = bottom(drive / "Output" / "Episode.mp4")
    quiet = bottom(plain / "Output" / "Episode.mp4")

    difference = ImageStat.Stat(ImageChops.difference(sung, quiet)).mean[0]

    print(f"   bottom of the frame differs by {difference:.1f} "
          "against the same run without lyrics")

    assert difference > 3.0, difference

    tall = drive / "Output" / "Episode_Short.mp4"

    assert tall.exists()
    assert (drive / "Output" / "lyrics_1080x1920.ass").exists(), \
        "the vertical cut got no lyrics of its own"

    print("\n   [OK] burned into both cuts, each at its own size")



def test_the_camera_answers_the_beat(root):

    heading("22  The camera moves with the song, not past it")

    drive = make_input(root / "Pulse", ["Scene01.png", "Scene02.png",
                                        "Scene03.png"], song_seconds=19)

    beat = [n * 0.55 for n in range(1, 34)]

    # The clips are made still on purpose. Anything the model itself
    # moved would be counted as camera movement and this test would
    # pass on the model's motion rather than the camera's.
    STILL_FRAMES[0] = True

    printed, refusal, _ = run(drive, beats=beat)

    assert not refusal, refusal
    assert "cut on the beat" in printed, printed

    # The same episode, cut on a stopwatch instead.
    plain = make_input(root / "NoPulse", ["Scene01.png", "Scene02.png",
                                          "Scene03.png"], song_seconds=19)

    run(plain)

    STILL_FRAMES[0] = False

    from PIL import ImageChops, ImageStat

    def movement(video):
        folder = video.parent / f"{video.stem}_frames"
        folder.mkdir(exist_ok=True)
        subprocess.run(
            [find_ffmpeg(), "-y", "-loglevel", "error", "-i", str(video),
             "-vf", "scale=160:-1,fps=8", f"{folder}/%04d.png"],
            check=True,
        )
        files = sorted(folder.iterdir())
        previous = Image.open(files[0]).convert("L")
        steps = []
        for f in files[1:]:
            current = Image.open(f).convert("L")
            steps.append(ImageStat.Stat(
                ImageChops.difference(previous, current)).mean[0])
            previous = current
        inside = [s for s in steps if s <= 25]
        return sum(inside) / len(inside)

    with_beat = movement(drive / "Output" / "Episode.mp4")
    without = movement(plain / "Output" / "Episode.mp4")

    print(f"   movement with the beat {with_beat:.2f}, "
          f"without it {without:.2f}")

    # The clips are identical; the only difference is the camera being
    # given the beats. A video that measures the same is one where the
    # pulse quietly did nothing.
    assert with_beat > without * 1.15, (with_beat, without)

    print("\n   [OK] the picture answers the music between the cuts")


# ======================================================================

def main():

    if not NOTEBOOK.exists():
        raise SystemExit(f"Notebook not found: {NOTEBOOK}")

    with tempfile.TemporaryDirectory() as temporary:

        root = Path(temporary)

        test_end_to_end(root)
        test_resume(root)
        test_changed_picture_is_not_skipped(root)
        test_refuses_too_few_pictures(root)
        test_the_edit_cuts_it_up(root)
        test_cuts_land_on_the_beat(root)
        test_without_librosa(root)
        test_refuses_broken_picture(root)
        test_settings_follow_the_machine(root)
        test_out_of_memory_is_survived(root)
        test_without_a_song(root)
        test_finds_a_folder_that_moved(root)
        test_says_what_it_can_see(root)
        test_offers_the_choices(root)
        test_checks_before_a_gpu_is_needed(root)
        test_one_picture_on_its_own(root)
        test_the_refusal_offers_the_test(root)
        test_drive_refusing_to_connect(root)
        test_the_machine_picks_the_model(root)
        test_a_small_card_is_sent_away(root)
        test_one_picture_of_him(root)
        test_a_preview_small_enough_to_send(root)
        test_the_helper_wan_needs(root)
        test_it_says_which_notebook_it_is(root)
        test_the_cuts_follow_the_words(root)
        test_a_scene_for_every_line(root)
        test_written_scenes(root)
        test_a_script_wins_over_pictures(root)
        test_the_vertical_cut(root)
        test_the_script_under_any_name(root)
        test_the_words_on_screen(root)
        test_the_camera_answers_the_beat(root)

    print("\nALL ANIMATE NOTEBOOK TESTS PASSED")


if __name__ == "__main__":
    main()
