from PySide6.QtCore import QObject, Signal, QThread
import time


class BackgroundWorker(QObject):

    started = Signal(str)
    finished = Signal(str)

    def __init__(self, queue):
        super().__init__()

        self.queue = queue

    def run(self):

        while True:

            job = self.queue.next_job()

            if job is None:
                break

            self.started.emit(job.scene_name)

            # Temporary AI simulation
            time.sleep(2)

            self.queue.complete(job)

            self.finished.emit(job.scene_name)