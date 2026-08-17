"""
Checks the render layer end to end, without needing a GPU.

It uses the Colab backend, whose whole job is the handoff through a
shared folder, and stands in for the GPU by dropping an image where the
Colab worker would have written one. That exercises every step Nik Studio
is responsible for: queueing jobs, importing results, resuming, and
failing cleanly.

Run from the project root:

    python tests/test_render_pipeline.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "app"))

from models.scene import Scene                      # noqa: E402
from render.episode_renderer import EpisodeRenderer  # noqa: E402
from services.scene_loader import SceneLoader        # noqa: E402
from services.scene_saver import SceneSaver          # noqa: E402


def make_image(path):
    """Write a small PNG, standing in for what the GPU would return."""

    path.parent.mkdir(parents=True, exist_ok=True)

    from PIL import Image

    Image.new("RGB", (64, 64), (40, 90, 160)).save(path)


def heading(text):
    print()
    print("=" * 68)
    print(text)
    print("=" * 68)


def main():

    work = Path(tempfile.mkdtemp(prefix="nikstudio_render_test_"))

    episode = work / "Episodes" / "Test Episode"
    episode.mkdir(parents=True)

    with open(episode / "episode.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "title": "Test Episode",
                "character": "vikrant",
                "style": "Pixar 3D",
                "resolution": "1024x1024",
                "backend": "Colab",
            },
            f,
            indent=4,
        )

    scenes = [
        Scene(id=1, name="Scene01", prompt="baby splashing in a bathtub"),
        Scene(id=2, name="Scene02", prompt="baby plays with a yellow duck"),
        Scene(id=3, name="Scene03", prompt=""),   # no prompt written yet
    ]

    SceneSaver(episode).save(scenes)

    renderer = EpisodeRenderer(episode)

    # ------------------------------------------------------------------
    heading("1  Render Episode queues the jobs")

    progress = []

    result = renderer.render_episode(
        scenes=scenes,
        on_progress=lambda p: progress.append(p.text()),
    )

    for line in progress:
        print("   ", line)

    print("---")
    print(result.summary())

    jobs = sorted(p.name for p in (episode / "Jobs").glob("*.json"))

    assert jobs == ["Scene01.json", "Scene02.json"], jobs
    assert len(result.waiting) == 2, result.waiting
    assert len(result.errors) == 1, result.errors
    assert scenes[0].pipeline.image.status.value == "waiting"
    assert scenes[2].pipeline.image.status.value == "failed"

    job = json.loads((episode / "Jobs/Scene01.json").read_text("utf-8"))

    # The prompt must carry the scene text, the character sheet and the
    # episode style - that is what keeps a character consistent.
    assert "bathtub" in job["prompt"]
    assert "Pixar 3D" in job["prompt"]

    # Style tokens must not be repeated.
    assert job["prompt"].lower().count("pixar 3d") == 1, job["prompt"]

    assert SceneLoader(episode).load()[0].pipeline.image.status.value == (
        "waiting"
    )

    print("\n   [OK] jobs queued, empty prompt rejected, state saved")

    # ------------------------------------------------------------------
    heading("2  A finished image comes back and is imported")

    make_image(episode / "Results" / "Scene01.png")

    collected = renderer.collect_results(scenes)

    print(collected.summary())

    assert (episode / "Images/Scene01.png").exists()
    assert not (episode / "Results/Scene01.png").exists(), "inbox not cleared"
    assert not (episode / "Jobs/Scene01.json").exists(), "job not retired"
    assert scenes[0].pipeline.image.status.value == "completed"
    assert scenes[0].image == "Images/Scene01.png"

    print("\n   [OK] imported into Images/, stage completed")

    # ------------------------------------------------------------------
    heading("3  Rendering again skips work that is already done")

    result = renderer.render_episode(scenes=scenes)

    print(result.summary())

    assert len(result.skipped) == 1, result.skipped
    assert result.skipped[0]["scene"] == "Scene01"

    print("\n   [OK] finished scene skipped")

    # ------------------------------------------------------------------
    heading("4  A stage whose file has vanished is rendered again")

    (episode / "Images/Scene01.png").unlink()

    result = renderer.render_episode(scenes=scenes)

    print(result.summary())

    assert not result.skipped, "a missing file must not count as done"
    assert any(w["scene"] == "Scene01" for w in result.waiting)

    print("\n   [OK] disk is checked, not just the saved status")

    # ------------------------------------------------------------------
    heading("5  The local backend explains itself when it cannot run")

    settings = json.loads((episode / "episode.json").read_text("utf-8"))
    settings["backend"] = "Local"

    result = EpisodeRenderer(episode, settings=settings).render_episode(
        scenes=scenes,
        force=True,
    )

    print(result.summary())

    if result.success:
        print("\n   [OK] torch and diffusers are installed, images generated")
    else:
        assert "torch" in result.errors[0]["error"] or (
            "diffusers" in result.errors[0]["error"]
        )
        print("\n   [OK] clear message instead of a crash")

    # ------------------------------------------------------------------
    shutil.rmtree(work, ignore_errors=True)

    print()
    print("ALL RENDER PIPELINE TESTS PASSED")


if __name__ == "__main__":
    main()
