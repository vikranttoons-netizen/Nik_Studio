from PySide6.QtCore import QThread

from services.background_worker import BackgroundWorker


class WorkerManager:

    def __init__(self, queue):

        self.thread = QThread()

        self.worker = BackgroundWorker(queue)

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(
            self.worker.run
        )

    def start(self):

        self.thread.start()
        