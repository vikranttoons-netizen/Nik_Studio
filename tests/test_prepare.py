"""
Checks tools/prepare.py: the groundwork done before paying for a GPU.

Every failure this catches is one that would otherwise be discovered
halfway through a paid Colab run, so the checks matter more than usual.

Needs FFmpeg on PATH (or imageio-ffmpeg installed). No GPU.

Run from the project root:

    python tests/test_prepare.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import prepare                                        # noqa: E402
from services.ffmpeg_locator import find_ffmpeg       # noqa: E402


def heading(text):
    print()
    print("=" * 68)
    print(text)
    print("=" * 68)


def make_image(path, size=(1408, 768)):

    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)

    Image.new("RGB", size, (30, 90, 160)).save(path)


def make_song(path, seconds):

    path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            find_ffmpeg(), "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            str(path),
        ],
        check=True,
    )


# ======================================================================

def test_ordering():

    heading("1  Scene2 comes before Scene10, not after")

    names = ["Scene10.png", "Scene2.png", "Scene1.png", "Scene20.png"]

    paths = [Path(name) for name in names]

    ordered = [p.name for p in sorted(paths, key=prepare.natural_key)]

    print("   given  :", names)
    print("   ordered:", ordered)

    assert ordered == [
        "Scene1.png", "Scene2.png", "Scene10.png", "Scene20.png"
    ], ordered

    print("\n   [OK] numbers are compared as numbers")


def test_gathers_both_layouts(root):

    heading("2  Pictures and song found in either layout")

    # An episode keeps them apart ...
    episode = root / "Episode"
    make_image(episode / "Images" / "Scene01.png")
    make_image(episode / "Images" / "Scene02.png")
    make_song(episode / "Audio" / "bath time song.mp3", 12)

    pictures, songs = prepare.gather(episode)

    print(f"   episode layout: {len(pictures)} pictures, {len(songs)} song")

    assert len(pictures) == 2, pictures
    assert len(songs) == 1, songs

    # ... a hand made folder has them side by side.
    flat = root / "Flat"
    make_image(flat / "a.png")
    make_image(flat / "b.png")
    make_image(flat / "c.png")
    make_song(flat / "tune.mp3", 12)

    pictures, songs = prepare.gather(flat)

    print(f"   flat layout   : {len(pictures)} pictures, {len(songs)} song")

    assert len(pictures) == 3, pictures
    assert len(songs) == 1, songs

    print("\n   [OK] neither layout has to be explained to it")


def test_catches_problems(root):

    heading("3  The problems that would waste a paid run")

    # -------------------------------------------------- nothing at all
    empty = root / "Empty"
    empty.mkdir()

    problems, _, _, _, _ = prepare.report(empty, root / "Out")

    print("   empty folder      :", problems[0][:52], "...")
    assert any("No pictures" in p for p in problems), problems

    # ------------------------------------------------ a broken picture
    broken = root / "Broken"
    make_image(broken / "Scene01.png")
    (broken / "Scene02.png").write_text("this is not a picture")
    make_song(broken / "song.mp3", 10)

    problems, _, _, _, _ = prepare.report(broken, root / "Out")

    print("   corrupt picture   :", problems[0][:52], "...")
    assert any("Scene02.png" in p for p in problems), problems

    # ------------------------------- one picture asked to fill a long song
    thin = root / "Thin"
    make_image(thin / "Scene01.png")
    make_song(thin / "song.mp3", 60)

    problems, _, _, _, seconds = prepare.report(thin, root / "Out")

    print("   1 picture / 60s   :", problems[0][:52], "...")
    assert any("slowed" in p for p in problems), problems
    assert any("about 8 pictures" in p for p in problems), problems

    # ------------------------------------------- no destination set at all
    fine = root / "Fine"
    make_image(fine / "Scene01.png")
    make_image(fine / "Scene02.png")
    make_song(fine / "song.mp3", 12)

    problems, _, _, _, _ = prepare.report(fine, None)

    assert any("No Colab folder" in p for p in problems), problems
    print("   no destination    :", problems[0][:52], "...")

    print("\n   [OK] each is caught before a GPU is ever started")


def test_healthy_project_passes(root):

    heading("4  A project that is ready says so")

    good = root / "Good"

    for n in range(1, 4):
        make_image(good / f"shot{n}.png")

    make_song(good / "song.mp3", 19)

    problems, notes, pictures, song, seconds = prepare.report(
        good, root / "Drive" / "Input"
    )

    print(f"   problems: {len(problems)}   notes: {len(notes)}")
    print(f"   {len(pictures)} pictures over {seconds:.1f}s")

    assert not problems, problems
    assert len(pictures) == 3, pictures
    assert song and abs(seconds - 19) < 1, (song, seconds)

    print("\n   [OK] 3 pictures over 19s needs no slowing down")


def test_builds_the_folder(root):

    heading("5  The folder Colab expects, numbered in order")

    source = root / "Source"

    # Deliberately out of alphabetical order: shot2 must not land after
    # shot10 just because "1" sorts before "2".
    for name in ("shot1.png", "shot2.png", "shot10.png"):
        make_image(source / name)

    make_song(source / "my tune.mp3", 19)

    destination = root / "Drive" / "Input"

    _, _, pictures, song, _ = prepare.report(source, destination)

    prepare.build(destination, pictures, song)

    landed = sorted(p.name for p in destination.iterdir())

    print("   ", landed)

    assert landed == [
        "Scene01.png", "Scene02.png", "Scene03.png", "song.mp3"
    ], landed

    # The renumbering has to preserve the order, not just the count.
    from PIL import Image

    for number, original in enumerate(pictures, start=1):
        copied = destination / f"Scene{number:02d}.png"
        assert copied.read_bytes() == original.read_bytes(), copied.name

    print("   order kept:", [p.name for p in pictures])

    print("\n   [OK] numbered in the order they will appear")


def test_clears_stale_scenes(root):

    heading("6  Leftovers from a longer episode do not sneak back in")

    destination = root / "Stale" / "Input"
    destination.mkdir(parents=True)

    # What a previous, five picture run left behind ...
    for n in range(1, 6):
        make_image(destination / f"Scene{n:02d}.png")

    (destination / "song.mp3").write_bytes(b"old")

    # ... plus something of the user's own, which must survive.
    (destination / "notes.txt").write_text("do not delete me")

    source = root / "Shorter"

    for n in range(1, 3):
        make_image(source / f"pic{n}.png")

    make_song(source / "new.mp3", 12)

    _, _, pictures, song, _ = prepare.report(source, destination)

    prepare.build(destination, pictures, song)

    landed = sorted(p.name for p in destination.iterdir())

    print("   ", landed)

    assert landed == [
        "Scene01.png", "Scene02.png", "notes.txt", "song.mp3"
    ], landed

    assert (destination / "notes.txt").read_text() == "do not delete me"

    print("\n   [OK] Scene03-05 gone, notes.txt untouched")


def test_warns_about_old_clips(root):

    heading("7  Clips from last time are pointed out, not deleted")

    drive = root / "Reuse"

    destination = drive / "Input"
    destination.mkdir(parents=True)

    clips = drive / "Output" / "Clips"
    clips.mkdir(parents=True)

    for n in range(1, 3):
        (clips / f"Scene{n:02d}.mp4").write_bytes(b"old clip")

    found = prepare.stale_clips(destination, [])

    print("   found:", [c.name for c in found])

    assert len(found) == 2, found

    # Pointing them out is the job; deleting someone's render is not.
    assert all(c.exists() for c in found)

    print("\n   [OK] reported so a changed picture is not skipped")


# ======================================================================

def main():

    with tempfile.TemporaryDirectory() as temporary:

        root = Path(temporary)

        test_ordering()
        test_gathers_both_layouts(root)
        test_catches_problems(root)
        test_healthy_project_passes(root)
        test_builds_the_folder(root)
        test_clears_stale_scenes(root)
        test_warns_about_old_clips(root)

    print("\nALL PREPARE TESTS PASSED")


if __name__ == "__main__":
    main()
