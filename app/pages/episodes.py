import json

from core.project import Project

from PySide6.QtWidgets import (
    QWidget,
    QListWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)


class EpisodesPage(QWidget):

    def __init__(self):
        super().__init__()

        # Root folder containing all episodes
        self.project = Project()
        self.root = self.project.episodes

        # Main Layout
        main_layout = QHBoxLayout(self)

        # -----------------------------
        # LEFT PANEL
        # -----------------------------
        left_layout = QVBoxLayout()

        title = QLabel("Episodes")
        title.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
            color:white;
        """)

        self.list = QListWidget()

        left_layout.addWidget(title)
        left_layout.addWidget(self.list)

        # -----------------------------
        # RIGHT PANEL
        # -----------------------------
        right_layout = QVBoxLayout()

        self.title = QLabel("Title :")
        self.character = QLabel("Character :")
        self.style = QLabel("Style :")
        self.resolution = QLabel("Resolution :")
        self.backend = QLabel("Backend :")

        labels = [
            self.title,
            self.character,
            self.style,
            self.resolution,
            self.backend,
        ]

        for label in labels:
            label.setStyleSheet("""
                font-size:18px;
                color:white;
                padding:6px;
            """)
            right_layout.addWidget(label)

        right_layout.addStretch()

        # -----------------------------
        # ADD PANELS
        # -----------------------------
        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 2)

        # Load all episodes
        self.load_episodes()

        # Detect click
        self.list.currentTextChanged.connect(self.load_episode)

    # ===================================
    # LOAD EPISODE LIST
    # ===================================

    def load_episodes(self):

        self.list.clear()

        if not self.root.exists():
            return

        for folder in sorted(self.root.iterdir()):

            if folder.is_dir():
                self.list.addItem(folder.name)

    # ===================================
    # LOAD SELECTED EPISODE
    # ===================================

    def load_episode(self, episode_name):

        if not episode_name:
            return

        json_file = self.root / episode_name / "episode.json"

        if not json_file.exists():
            return

        with open(json_file, "r", encoding="utf-8-sig") as f:

            data = json.load(f)

        self.title.setText(
            f"Title : {data.get('title','')}"
        )

        self.character.setText(
            f"Character : {data.get('character','')}"
        )

        self.style.setText(
            f"Style : {data.get('style','')}"
        )

        self.resolution.setText(
            f"Resolution : {data.get('resolution','')}"
        )

        self.backend.setText(
            f"Backend : {data.get('backend','')}"
        )