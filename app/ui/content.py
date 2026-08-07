from PySide6.QtWidgets import QStackedWidget

from pages.dashboard import DashboardPage
from pages.episodes import EpisodesPage
from pages.images import ImagesPage
from pages.videos import VideosPage
from pages.export import ExportPage
from pages.settings import SettingsPage
from pages.workspace import WorkspacePage


class Content(QStackedWidget):

    def __init__(self):
        super().__init__()

        # Create Pages
        self.dashboard = DashboardPage()
        self.workspace = WorkspacePage()
        self.episodes = EpisodesPage()
        self.images = ImagesPage()
        self.videos = VideosPage()
        self.export = ExportPage()
        self.settings = SettingsPage()

        # Add Pages
        self.addWidget(self.dashboard)     # Index 0
        self.addWidget(self.workspace)     # Index 1
        self.addWidget(self.episodes)      # Index 2
        self.addWidget(self.images)        # Index 3
        self.addWidget(self.videos)        # Index 4
        self.addWidget(self.export)        # Index 5
        self.addWidget(self.settings)      # Index 6