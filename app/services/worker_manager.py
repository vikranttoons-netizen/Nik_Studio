from PySide6.QtCore import QObject, QThread, Signal

from services.background_worker import RenderWorker


class RenderTask(QObject):
    """
    Owns the thread a render runs on.

    Keep a reference to the task for as long as it runs - if Python
    garbage collects the QThread mid render, the app crashes.
    """

    progress = Signal(object)     # RenderProgress
    finished = Signal(object)     # RenderResult

    def __init__(
        self,
        episode_folder,
        scenes,
        stages=("image",),
        force=False,
        job=RenderWorker.RENDER,
        parent=None,
    ):

        super().__init__(parent)

        self.thread = QThread()

        self.worker = RenderWorker(
            episode_folder,
            scenes,
            stages=stages,
            force=force,
            job=job,
        )

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.progress.connect(self.progress)
        self.worker.finished.connect(self._on_finished)

    # ------------------------------------------------------------------

    def start(self):
        self.thread.start()

    def cancel(self):
        self.worker.cancel()

    @property
    def is_running(self):
        return self.thread.isRunning()

    # ------------------------------------------------------------------

    def _on_finished(self, result):

        self.thread.quit()
        self.thread.wait()

        self.finished.emit(result)


# The old name, in case anything still refers to it.
WorkerManager = RenderTask
