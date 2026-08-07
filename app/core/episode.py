from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Episode:

    title: str

    path: Path

    character: str = "Nik"

    style: str = "Pixar"

    resolution: str = "1920x1080"

    fps: int = 24

    backend: str = "Local"

    image_folder: Path = field(init=False)

    video_folder: Path = field(init=False)

    audio_folder: Path = field(init=False)

    export_folder: Path = field(init=False)

    def __post_init__(self):

        self.image_folder = self.path / "Images"

        self.video_folder = self.path / "Videos"

        self.audio_folder = self.path / "Audio"

        self.export_folder = self.path / "Exports"