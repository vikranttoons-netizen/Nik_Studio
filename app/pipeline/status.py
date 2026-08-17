from enum import Enum


class StageStatus(str, Enum):
    """
    Status of a single production stage.

    Inherits from str so it can be written straight into JSON and
    compared against plain strings coming from older project files.
    """

    NOT_STARTED = "not_started"
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def parse(cls, value):
        """
        Turn whatever is in the JSON file into a StageStatus.
        Unknown / missing values become NOT_STARTED instead of crashing.
        """

        if isinstance(value, cls):
            return value

        if not value:
            return cls.NOT_STARTED

        text = str(value).strip().lower()

        for status in cls:
            if status.value == text:
                return status

        # Tolerate a few older spellings that exist in saved projects.
        legacy = {
            "pending": cls.NOT_STARTED,
            "done": cls.COMPLETED,
            "complete": cls.COMPLETED,
            "error": cls.FAILED,
            "in_progress": cls.RUNNING,
        }

        return legacy.get(text, cls.NOT_STARTED)

    # ------------------------------------------------------------------

    def icon(self):

        return {
            StageStatus.NOT_STARTED: "⚪",
            StageStatus.WAITING: "⚪",
            StageStatus.RUNNING: "🟡",
            StageStatus.COMPLETED: "🟢",
            StageStatus.FAILED: "🔴",
        }[self]

    def label(self):

        return self.value.replace("_", " ").title()
