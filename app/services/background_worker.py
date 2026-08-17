from PySide6.QtCore import QObject, Signal, Slot

from render.episode_renderer import EpisodeRenderer
from render.render_result import RenderResult


class RenderWorker(QObject):
    """
    Runs a render off the UI thread.

    Generating an image takes seconds to minutes, so doing it on the UI
    thread would freeze the whole window. This object is moved onto a
    QThread and reports back with signals.

    (This file used to hold a placeholder worker that just slept for two
    seconds per scene. It now drives the real renderer.)
    """

    progress = Signal(object)     # RenderProgress
    finished = Signal(object)     # RenderResult

    # What the worker was asked to do.
    RENDER = "render"
    COLLECT = "collect"

    def __init__(
        self,
        episode_folder,
        scenes,
        stages=("image",),
        force=False,
        job=RENDER,
    ):

        super().__init__()

        self.episode_folder = episode_folder
        self.scenes = scenes
        self.stages = tuple(stages)
        self.force = force
        self.job = job

        self._cancelled = False

    # ------------------------------------------------------------------

    def cancel(self):
        """
        Ask the render to stop. Checked between scenes, so the scene being
        generated right now still finishes - killing a model mid
        generation would leave a corrupt file behind.
        """

        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled

    # ------------------------------------------------------------------

    @Slot()
    def run(self):

        try:
            renderer = EpisodeRenderer(
                self.episode_folder,
                cancelled=self.is_cancelled,
            )

            if self.job == self.COLLECT:
                result = renderer.collect_results(self.scenes)
            else:
                result = renderer.render_episode(
                    scenes=self.scenes,
                    stages=self.stages,
                    force=self.force,
                    on_progress=self.progress.emit,
                )

        except Exception as error:
            # Anything unexpected becomes a reported failure rather than a
            # silently dead thread.
            result = RenderResult(
                success=False,
                message="The render could not start.",
            )

            result.add_error("-", self.stages[0] if self.stages else "-", error)

        self.finished.emit(result)


# The old name, in case anything still refers to it.
BackgroundWorker = RenderWorker
