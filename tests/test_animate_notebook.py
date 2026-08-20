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

FAIL_FIRST_CALL = [False]

HAS_GPU = [True]

MOUNT_FAILS = [False]


class StandInPipeline:
    """
    Answers the calls the notebook makes on the real pipeline, and
    records what it was asked for so the test can check it.
    """

    def __init__(self):
        self.transformer = types.SimpleNamespace(to=lambda device: None)
        self.vae = types.SimpleNamespace(
            to=lambda device: None,
            enable_tiling=lambda: None,
        )

    def to(self, device):
        return self

    def __call__(self, **asked):

        CALLS.append(asked)

        if FAIL_FIRST_CALL[0] and len(CALLS) == 1:
            raise OutOfMemory("pretending the card is full")

        width, height = asked["width"], asked["height"]

        frames = [
            Image.new("RGB", (width, height), (number * 3 % 255, 80, 160))
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

    diffusers = types.ModuleType("diffusers")
    diffusers.LTXImageToVideoPipeline = types.SimpleNamespace(
        from_pretrained=lambda model, **kw: StandInPipeline()
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
    sys.modules["transformers"] = transformers

    display = types.ModuleType("IPython.display")
    display.Video = lambda *a, **kw: "<video>"
    display.display = lambda *a, **kw: None
    package = types.ModuleType("IPython")
    package.display = display
    sys.modules["IPython"] = package
    sys.modules["IPython.display"] = display

    builtins.display = lambda *a, **kw: None

    psutil = types.ModuleType("psutil")
    psutil.virtual_memory = lambda: types.SimpleNamespace(total=ram * 1e9)
    sys.modules["psutil"] = psutil

    if MOUNT_FAILS[0]:

        class MessageError(Exception):
            pass

        def refuse(*a, **kw):
            raise MessageError("credential propagation was unsuccessful")

        colab = types.ModuleType("google.colab")
        colab.drive = types.SimpleNamespace(mount=refuse)
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
        mounted=None, gpu=True, test_one=False, mount_fails=False):
    """
    Run the notebook against a folder. Returns (printed, refusal, calls)
    where refusal is the message it stopped with, or "".

    `mounted` stands in for /content/drive/MyDrive, so what happens when
    the folder is not where it was expected can be tested too.
    """

    CALLS.clear()

    FAIL_FIRST_CALL[0] = out_of_memory

    HAS_GPU[0] = gpu

    MOUNT_FAILS[0] = mount_fails

    install_stand_ins(vram, ram, capability)

    source = cell_two().replace(
        'FOLDER = DRIVE + "/NikStudio"',
        f"FOLDER = {str(drive)!r}",
    ).replace(
        'DRIVE = "/content/drive/MyDrive"',
        f"DRIVE = {str(mounted or '/content/drive/MyDrive')!r}",
    ).replace(
        "TEST_ONE_PICTURE = False",
        f"TEST_ONE_PICTURE = {test_one}",
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
    assert order == ["shot1.png", "shot2.png", "shot10.png"], order
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
    assert "Scene02.png: picture or prompt changed" in printed

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
    assert "about 8 pictures" in refusal, refusal

    print("\n   [OK] refused, and said how many pictures it needs")


def test_long_holds_are_filled_by_looping(root):

    heading("4b  A long hold loops a short clip, it does not stretch one")

    # 11 pictures over a two minute song: 11.4s each. The model is still
    # only asked for three seconds - what it can hold - and the rest is
    # filled forwards and back. This is the real case that prompted it.
    drive = make_input(
        root / "Long",
        [f"Scene{n:02d}.png" for n in range(1, 12)],
        song_seconds=125,
    )

    printed, refusal, calls = run(drive)

    assert not refusal, refusal

    # The model must never be asked for a long clip, whatever the slot.
    asked = {call["num_frames"] for call in calls}

    print(f"   frames asked for: {asked}  (never more, whatever the slot)")

    assert asked == {49}, asked

    print("  ", [line.strip() for line in printed.splitlines()
                 if "back and forth" in line][0][:76], "...")

    assert "back and forth" in printed, printed

    final = drive / "Output" / "Episode.mp4"

    length = float(probe(final, "format=duration")[0])
    size = probe(final, "stream=width,height")

    print(f"   {len(calls)} clips -> {length:.1f}s at {size[0]}x{size[1]} "
          "against a 125s song")

    assert abs(length - 125) < 1.5, length
    assert size[:2] == ["1280", "720"], size

    print("\n   [OK] short clips, looped, and the song still fits")


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

    heading("6  The card decides the precision - not the video size")

    drive = make_input(root / "Tiers", ["Scene01.png", "Scene02.png",
                                        "Scene03.png"])

    for label, vram, ram, capability, precision, quantised in [
        ("A100, plenty of RAM", 40, 83, 8, "bfloat16", False),
        ("L4, small RAM      ", 24, 12.7, 8, "bfloat16", True),
        ("T4                 ", 15.6, 12.7, 7, "float16", True),
    ]:
        printed, refusal, calls = run(drive, vram, ram, capability)

        assert not refusal, refusal

        assert precision in printed, printed
        assert ("text encoder in 8-bit" in printed) is quantised, printed

        # The size the model is asked for is set by what it was trained
        # on, and a bigger card is not a reason to push it past that -
        # 1024x576 is where the picture came apart.
        assert "Generated at: 768x448" in printed, printed
        assert all(call["width"] == 768 and call["height"] == 448
                   for call in calls), calls

        print(f"   {label}: 768x448, {precision}"
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
    assert calls[0]["num_frames"] == 49, calls
    assert "back and forth" not in printed, printed

    final = drive / "Output" / "Episode.mp4"

    length = float(probe(final, "format=duration")[0])
    streams = probe(final, "stream=codec_type")

    print(f"   {length:.1f}s, streams {streams}")

    assert abs(length - 49 / 24) < 0.3, length
    assert "audio" not in streams, "the song was laid over a test clip"

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

    heading("15  Drive refusing to sign in is explained, not dumped")

    drive = make_input(root / "NoDrive", ["Scene01.png", "Scene02.png"])

    # The folder is not where it looks, so it has to mount - and the
    # mount fails the way Colab fails when the browser blocks the popup.
    _, refusal, calls = run(
        root / "Missing" / "NikStudio",
        mounted=root / "NotMounted",
        mount_fails=True,
    )

    print("  ", refusal.strip().splitlines()[0])
    print("  ", refusal.strip().splitlines()[6].strip()[:66], "...")

    assert calls == [], calls
    assert "would not connect" in refusal, refusal
    assert "third-party cookies" in refusal, refusal
    assert "not a problem with your files" in refusal, refusal
    assert "Traceback" not in refusal

    print("\n   [OK] says what to do, and that nothing was lost")


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
        test_long_holds_are_filled_by_looping(root)
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

    print("\nALL ANIMATE NOTEBOOK TESTS PASSED")


if __name__ == "__main__":
    main()
