from PySide6.QtWidgets import QStackedWidget

from pages.dashboard import DashboardPage
from pages.episodes import EpisodesPage
from pages.images import ImagesPage
from pages.videos import VideosPage
from pages.export import ExportPage
from pages.settings import SettingsPage


class Content(QStackedWidget):

    def __init__(self):
        super().__init__()

        self.dashboard = DashboardPage()
        self.episodes = EpisodesPage()
        self.images = ImagesPage()
        self.videos = VideosPage()
        self.export = ExportPage()
        self.settings = SettingsPage()

        self.addWidget(self.dashboard)   # index 0
        self.addWidget(self.episodes)    # index 1
        self.addWidget(self.images)      # index 2
        self.addWidget(self.videos)      # index 3
        self.addWidget(self.export)      # index 4
        self.addWidget(self.settings)    # index 5