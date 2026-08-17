from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QGridLayout,
)

from pipeline.pipeline import STAGES


class PropertiesPanel(QWidget):
    """
    The production panel: what is actually done for the selected scene.

    Every row is read straight off the scene's pipeline, so this can never
    show progress that did not really happen.
    """

    LABELS = {
        "image": "Image",
        "video": "Video",
        "voice": "Voice",
        "music": "Music",
        "final": "Final",
    }

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.name = QLabel("No scene selected")

        self.name.setStyleSheet("""
            font-size:17px;
            font-weight:bold;
            padding-bottom:4px;
        """)

        layout.addWidget(self.name)

        # ------------------------------------------------------ prompt row

        self.prompt_state = QLabel("—")
        self.prompt_state.setStyleSheet("color:#BBB;")

        prompt_row = QGridLayout()
        prompt_row.setContentsMargins(0, 0, 0, 6)

        prompt_label = QLabel("Prompt")
        prompt_label.setStyleSheet("color:#999;")

        prompt_row.addWidget(prompt_label, 0, 0)
        prompt_row.addWidget(self.prompt_state, 0, 1)
        prompt_row.setColumnStretch(1, 1)

        layout.addLayout(prompt_row)

        # ------------------------------------------------------ stage rows

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setVerticalSpacing(6)

        self.rows = {}

        for row, stage in enumerate(STAGES):

            label = QLabel(self.LABELS[stage])
            label.setStyleSheet("color:#999;")

            status = QLabel("⚪ Not Started")
            detail = QLabel("")

            detail.setStyleSheet("color:#777; font-size:12px;")
            detail.setWordWrap(True)

            grid.addWidget(label, row, 0)
            grid.addWidget(status, row, 1)
            grid.addWidget(detail, row, 2)

            self.rows[stage] = (status, detail)

        grid.setColumnStretch(2, 1)

        layout.addLayout(grid)
        layout.addStretch()

    # ------------------------------------------------------------------

    def clear(self):

        self.name.setText("No scene selected")
        self.prompt_state.setText("—")

        for status, detail in self.rows.values():
            status.setText("⚪ Not Started")
            detail.setText("")

    # ------------------------------------------------------------------

    def show_scene(self, scene):

        if scene is None:
            self.clear()
            return

        self.name.setText(f"{scene.name}  ·  {scene.status}")

        if (scene.prompt or "").strip():
            self.prompt_state.setText("✅ written")
        else:
            self.prompt_state.setText("⚠ empty")

        for stage in STAGES:

            status_label, detail_label = self.rows[stage]

            stage_state = scene.pipeline[stage]

            status_label.setText(
                f"{stage_state.status.icon()} {stage_state.status.label()}"
            )

            # Show the error when something failed, otherwise the file it
            # produced. Both are more useful than the status alone.
            if stage_state.is_failed and stage_state.error:
                detail_label.setText(stage_state.error)
                detail_label.setStyleSheet(
                    "color:#E06C75; font-size:12px;"
                )
            else:
                detail_label.setText(stage_state.output)
                detail_label.setStyleSheet(
                    "color:#777; font-size:12px;"
                )
