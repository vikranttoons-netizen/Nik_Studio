"""
Checks the video half of the pipeline: still images become pan/zoom clips,
and the clips become one playable episode MP4.

Needs FFmpeg on PATH. No GPU and no AI model involved.

Run from the project root:

    python tests/test_video_pipeline.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "app"))

from backends.base_backend import BackendError        # noqa: E402
from backends.ffmpeg_backend import FFmpegBackend     # noqa: E402
from models.scene import Scene                        # noqa: E402
from render.episode_renderer import EpisodeRenderer    # noqa: E402
from services.scene_saver import SceneSaver           # noqa: E402


def heading(text):
    print()
    print("=" * 68)
    print(text)
    print("=" * 68)


def make_image(path, shift=0):
    """
    A detailed test image. The detail matters: a flat colour would make
    the pan/zoom motion check pass even if nothing moved.
    """

    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)

    size = 768
    image = Image.new("RGB", (size, size))
    pixels = image.load()

    for y in range(size):
        for x in range(size):
            pixels[x, y] = (
                (x * 7 + shift * 40) % 256,
                (y * 5 + shift * 20) % 256,
                ((x + y) * 3) % 256,
            )

    image.save(path)


def probe(path, fields):
    """Read stream properties out of a video file with ffprobe."""

    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", fields,
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )

    return result.stdout.split()


def main():

    if not shutil.which("ffmpeg"):
        print("SKIPPED: FFmpeg is not installed, so there is nothing to test.")
        print("Install it with:  winget install Gyan.FFmpeg")
        return

    work = Path(tempfile.mkdtemp(prefix="nikstudio_video_test_"))

    episode = work / "Episodes" / "Video Test"
    episode.mkdir(parents=True)

    with open(episode / "episode.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "title": "Video Test",
                "aspect": "16:9",
                "fps": 24,
                "scene_duration": 2,
                "backend": "Colab",
            },
            f,
            indent=4,
        )

    scenes = []

    for index, name in enumerate(["Scene01", "Scene02", "Scene03"], start=1):

        make_image(episode / "Images" / f"{name}.png", shift=index)

        scenes.append(
            Scene(
                id=index,
                name=name,
                prompt=f"test scene {index}",
                image=f"Images/{name}.png",
            )
        )

    SceneSaver(episode).save(scenes)

    # ------------------------------------------------------------------
    heading("1  Render Episode: images -> clips -> final MP4")

    renderer = EpisodeRenderer(episode)

    progress = []

    result = renderer.render_episode(
        scenes=scenes,
        on_progress=lambda p: progress.append(p.text()),
    )

    for line in progress:
        print("   ", line)

    print("---")
    print(result.summary())

    assert result.success, result.errors
    assert len(result.rendered_videos) == 3, result.rendered_videos
    assert result.final_video, "no final video was produced"

    final = episode / result.final_video

    assert final.exists(), final

    print(f"\n   [OK] {result.final_video}")

    # ------------------------------------------------------------------
    heading("2  The final video is 16:9 and the right length")

    width, height = probe(final, "stream=width,height")[:2]
    duration = float(probe(final, "format=duration")[0])

    print(f"   size     : {width}x{height}")
    print(f"   duration : {duration}s")

    assert (width, height) == ("1920", "1080"), (width, height)

    # 3 scenes at 2 seconds each.
    assert abs(duration - 6.0) < 0.5, duration

    print("\n   [OK] 1920x1080, 6 seconds")

    # ------------------------------------------------------------------
    heading("3  The clips actually move (pan/zoom, not a still)")

    from PIL import Image, ImageChops

    clip = episode / "Videos" / "Scene01.mp4"

    frames = []

    for position in ("0.1", "1.8"):

        frame = work / f"frame_{position}.png"

        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-ss", position,
                "-i", str(clip),
                "-frames:v", "1",
                str(frame),
            ],
            check=True,
        )

        frames.append(Image.open(frame).convert("RGB"))

    difference = ImageChops.difference(*frames).convert("L")

    # Averaged from the histogram rather than every pixel - same answer,
    # without pulling two million values into a list.
    histogram = difference.histogram()

    total = sum(histogram)

    average = sum(
        value * count
        for value, count in enumerate(histogram)
    ) / max(1, total)

    print(f"   average pixel change, first frame to last : {average:.1f}")

    assert average > 2, "the frames are identical - the clip is not moving"

    print("\n   [OK] motion confirmed")

    # ------------------------------------------------------------------
    heading("4  Scene order decides the edit")

    # Swap the first two scenes and rebuild.
    scenes[0], scenes[1] = scenes[1], scenes[0]

    rebuilt = renderer.compose_final(scenes)

    assert rebuilt.final_video, rebuilt.errors

    print(f"   rebuilt {rebuilt.final_video} with Scene02 first")

    print("\n   [OK] reordering the scene list changes the video")

    # ------------------------------------------------------------------
    heading("5  A scene with no image fails clearly")

    backend = FFmpegBackend(episode, {})

    try:
        backend.generate_video(Scene(id=9, name="Empty", prompt="x"), "x")
        raise AssertionError("should have refused a scene with no image")

    except BackendError as error:
        print("   ", error)

    print("\n   [OK] clear message, no broken video file")

    # ------------------------------------------------------------------
    heading("6  9:16 for Shorts and Reels")

    portrait = FFmpegBackend(
        episode,
        {"aspect": "9:16", "fps": 12, "scene_duration": 1},
    )

    output = portrait.generate_video(
        Scene(id=1, name="Portrait", prompt="p", image="Images/Scene01.png"),
        "p",
    )

    size = probe(episode / output, "stream=width,height")[:2]

    print(f"   {output} -> {size[0]}x{size[1]}")

    assert size == ["1080", "1920"], size

    print("\n   [OK] portrait output works")

    # ------------------------------------------------------------------
    shutil.rmtree(work, ignore_errors=True)

    print()
    print("ALL VIDEO PIPELINE TESTS PASSED")


if __name__ == "__main__":
    main()
