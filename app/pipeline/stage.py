from dataclasses import dataclass
from datetime import datetime

from pipeline.status import StageStatus


def _now():
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Stage:
    """
    One production step for one scene (image, video, voice, music, final).

    `output` is stored as a path relative to the episode folder so a
    project stays portable when it is zipped and opened on another machine.
    """

    name: str
    status: StageStatus = StageStatus.NOT_STARTED
    output: str = ""
    error: str = ""
    backend: str = ""
    started_at: str = ""
    finished_at: str = ""

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def start(self, backend=""):

        self.status = StageStatus.RUNNING
        self.error = ""
        self.backend = backend or self.backend
        self.started_at = _now()
        self.finished_at = ""

    def complete(self, output=""):

        self.status = StageStatus.COMPLETED
        self.error = ""

        if output:
            self.output = str(output)

        self.finished_at = _now()

    def fail(self, error=""):

        self.status = StageStatus.FAILED
        self.error = str(error)
        self.finished_at = _now()

    def reset(self):

        self.status = StageStatus.NOT_STARTED
        self.output = ""
        self.error = ""
        self.started_at = ""
        self.finished_at = ""

    # ------------------------------------------------------------------

    @property
    def is_completed(self):
        return self.status == StageStatus.COMPLETED

    @property
    def is_failed(self):
        return self.status == StageStatus.FAILED

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, name, data):

        data = data or {}

        return cls(
            name=name,
            status=StageStatus.parse(data.get("status")),
            output=data.get("output", "") or "",
            error=data.get("error", "") or "",
            backend=data.get("backend", "") or "",
            started_at=data.get("started_at", "") or "",
            finished_at=data.get("finished_at", "") or "",
        )

    def to_dict(self):

        return {
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "backend": self.backend,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
