"""
Drives the real workspace window: open an episode, edit a prompt, Save,
🚀 Render Episode, 📥 Import Results, then reopen the app and check the
state came back.

No GPU needed - it uses the Colab backend and stands in for the GPU by
writing an image where the Colab worker would have written one.

Run from the project root:

    python tests/test_workspace_ui.py
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ----------------------------------------------------------------------
# Build a throwaway project so the real Episodes folder is untouched.
# ----------------------------------------------------------------------

WORK = Path(tempfile.mkdtemp(prefix="nikstudio_ui_test_"))

EPISODE = WORK / "Episodes" / "UI Test Episode"
EPISODE.mkdir(parents=True)

with open(EPISODE / "episode.json", "w", encoding="utf-8") as f:
    json.dump(
        {
            "title": "UI Test",
            "character": "vikrant",
            "style": "Pixar 3D",
            "resolution": "1024x1024",
            "backend": "Colab",
        },
        f,
        indent=4,
    )

with open(EPISODE / "scenes.json", "w", encoding="utf-8") as f:
    json.dump(
        {
            "scenes": [
                {
                    "id": 1,
                    "name": "Scene01",
                    "prompt": "baby in a bathtub",
                    "image": "",
                    "video": "",
                    "status": "pending",
                },
                {
                    "id": 2,
                    "name": "Scene02",
                    "prompt": "baby with a yellow duck",
                    "image": "",
                    "video": "",
                    "status": "pending",
                },
            ]
        },
        f,
        indent=4,
    )

os.environ["NIKSTUDIO_ROOT"] = str(WORK)

# Run without a real screen so this works over a terminal / on a server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.argv = ["nikstudio-test"]

from PySide6.QtCore import QEventLoop, QTimer            # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication(sys.argv)

# The workspace shows a summary dialog after a render. Print it instead of
# blocking the test on a modal window.
QMessageBox.exec = lambda self: print(f"   [dialog] {self.text()}")

from ui.main_window import MainWindow  # noqa: E402


def heading(text):
    print()
    print("=" * 68)
    print(text)
    print("=" * 68)


def make_image(path):

    path.parent.mkdir(parents=True, exist_ok=True)

    from PIL import Image

    Image.new("RGB", (64, 64), (40, 90, 160)).save(path)


def wait_for_render(workspace, timeout_ms=60000):
    """Let the event loop run until the render thread has finished."""

    loop = QEventLoop()

    def check():
        if workspace.task is None or not workspace.task.is_running:
            loop.quit()

    timer = QTimer()
    timer.timeout.connect(check)
    timer.start(50)

    QTimer.singleShot(timeout_ms, loop.quit)

    loop.exec()


def rows(scene_list):
    return [scene_list.item(i).text() for i in range(scene_list.count())]


def main():

    window = MainWindow()
    window.content.setCurrentWidget(window.content.workspace)
    window.show()

    ws = window.content.workspace

    # ------------------------------------------------------------------
    heading("1  The app opens an episode it found on disk")

    print("   picker :", [
        ws.toolbar.episodes.itemText(i)
        for i in range(ws.toolbar.episodes.count())
    ])
    print("   title  :", ws.toolbar.title.text())
    print("   scenes :", rows(ws.scene_list))

    assert ws.scene_list.count() == 2
    assert "UI Test Episode" in ws.toolbar.title.text()

    # ------------------------------------------------------------------
    heading("2  Editing a prompt and pressing Save")

    ws.scene_list.setCurrentRow(0)
    ws.prompt.setPlainText("baby splashing happily in a bubble bath")
    ws.toolbar.save.click()

    saved = json.loads((EPISODE / "scenes.json").read_text("utf-8"))

    print("   scenes.json :", saved["scenes"][0]["prompt"])

    assert saved["scenes"][0]["prompt"] == (
        "baby splashing happily in a bubble bath"
    )

    print("   [OK] prompt saved")

    # ------------------------------------------------------------------
    heading("3  Pressing 🚀 RENDER EPISODE")

    seen = []
    real_update = ws.status.update_progress

    def spy(progress):
        seen.append(progress.text())
        real_update(progress)

    ws.status.update_progress = spy

    ws.toolbar.renderEpisode.click()

    print("   locked while rendering :", not ws.toolbar.save.isEnabled())
    print("   stop button shown      :", ws.toolbar.cancel.isVisible())
    print("   prompt read only       :", ws.prompt.isReadOnly())

    assert not ws.toolbar.save.isEnabled()
    assert ws.toolbar.cancel.isVisible()
    assert ws.prompt.isReadOnly()

    wait_for_render(ws)

    print("   progress:")
    for line in seen:
        print("      ", line)

    assert ws.toolbar.save.isEnabled(), "buttons not re-enabled"
    assert not ws.prompt.isReadOnly()

    jobs = sorted(p.name for p in (EPISODE / "Jobs").glob("*.json"))

    print("   job files :", jobs)
    print("   scenes    :", rows(ws.scene_list))
    print("   panel     :", ws.properties.rows["image"][0].text())

    assert jobs == ["Scene01.json", "Scene02.json"]
    assert "Waiting" in ws.properties.rows["image"][0].text()

    print("   [OK] jobs queued and the UI shows it")

    # ------------------------------------------------------------------
    heading("4  Images come back -> 📥 Import Results")

    make_image(EPISODE / "Results" / "Scene01.png")
    make_image(EPISODE / "Results" / "Scene02.png")

    ws.toolbar.importResults.click()
    wait_for_render(ws)

    print("   status :", ws.status.message.text())
    print("   scenes :", rows(ws.scene_list))
    print("   panel  :", ws.properties.rows["image"][0].text(),
          "|", ws.properties.rows["image"][1].text())

    assert (EPISODE / "Images/Scene01.png").exists()
    assert (EPISODE / "Images/Scene02.png").exists()
    assert "Completed" in ws.properties.rows["image"][0].text()

    pixmap = ws.preview.pixmap()

    assert pixmap is not None and not pixmap.isNull(), (
        "the preview did not update"
    )

    saved = json.loads((EPISODE / "scenes.json").read_text("utf-8"))

    assert saved["scenes"][0]["image"] == "Images/Scene01.png"
    assert saved["scenes"][0]["pipeline"]["image"]["status"] == "completed"

    print("   [OK] imported, preview updated, scenes.json written")

    # ------------------------------------------------------------------
    heading("5  Pressing 🚀 RENDER EPISODE again finishes the episode")

    ws.toolbar.renderEpisode.click()
    wait_for_render(ws)

    status = ws.status.message.text()

    print("   status :", status)

    import shutil as _shutil

    if _shutil.which("ffmpeg"):
        # The images are done, so this pass makes the clips and the MP4.
        assert "episode ready" in status.lower(), status
    else:
        assert "already rendered" in status.lower(), status

    print("   [OK] resumed and carried on to the next stage")

    # ------------------------------------------------------------------
    heading("5b  Scene management: add, move, delete")

    before = ws.scene_list.count()

    ws.scene_list.setCurrentRow(0)
    ws.scene_panel.add.click()

    added = ws.scene_list.current_scene()

    print(f"   added   : {added.name} at row {ws.scene_list.currentRow()}")
    print("   scenes  :", rows(ws.scene_list))

    assert ws.scene_list.count() == before + 1
    # Inserted below the selected scene, not at the end.
    assert ws.scene_list.currentRow() == 1
    # A new scene must not reuse a name, or it looks already rendered.
    assert added.name not in ("Scene01", "Scene02")
    assert added.pipeline.image.status.value == "not_started"

    ws.scene_panel.down.click()

    print(f"   moved   : {added.name} to row {ws.scene_list.currentRow()}")

    assert ws.scene_list.currentRow() == 2
    assert ws.scene_list.scenes[2].name == added.name

    # The edit must be on disk, not just on screen.
    saved = json.loads((EPISODE / "scenes.json").read_text("utf-8"))

    assert [s["name"] for s in saved["scenes"]][2] == added.name

    # Deleting asks first; answer yes.
    QMessageBox.question = lambda *a, **k: QMessageBox.Yes

    ws.scene_panel.delete.click()

    print("   deleted :", added.name)
    print("   scenes  :", rows(ws.scene_list))

    assert ws.scene_list.count() == before

    saved = json.loads((EPISODE / "scenes.json").read_text("utf-8"))

    assert added.name not in [s["name"] for s in saved["scenes"]]

    # The images made earlier must survive a scene-list edit.
    assert (EPISODE / "Images/Scene01.png").exists()

    print("   [OK] add / move / delete work and are saved")

    # ------------------------------------------------------------------
    heading("5c  The final episode MP4")

    import shutil as _shutil

    if not _shutil.which("ffmpeg"):
        print("   SKIPPED: FFmpeg not installed")
    else:
        exports = sorted((EPISODE / "Exports").glob("*.mp4"))

        print("   Videos  :", sorted(
            p.name for p in (EPISODE / "Videos").glob("*.mp4")
        ))
        print("   Exports :", [p.name for p in exports])

        assert exports, "Render Episode produced no final video"

        print("   [OK] episode video built from the UI")

    # ------------------------------------------------------------------
    heading("6  Reopening the app restores the state from disk")

    second = MainWindow()
    ws2 = second.content.workspace

    print("   episode :", ws2.episode_folder.name)
    print("   scenes  :", rows(ws2.scene_list))
    print("   panel   :", ws2.properties.rows["image"][0].text())

    assert ws2.episode_folder.name == "UI Test Episode"
    assert "Completed" in ws2.properties.rows["image"][0].text()

    print("   [OK] project reopened with its render state")

    # ------------------------------------------------------------------
    window.close()
    second.close()

    shutil.rmtree(WORK, ignore_errors=True)

    print()
    print("ALL WORKSPACE UI TESTS PASSED")


if __name__ == "__main__":
    main()
