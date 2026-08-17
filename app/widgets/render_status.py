from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QProgressBar,
)


class RenderStatus(QWidget):
    """
    The thin strip under the toolbar showing what the renderer is doing.

    Hidden until a render starts, so it does not take up space while the
    creator is just editing prompts.
    """

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(10)

        self.bar = QProgressBar()
        self.bar.setFixedWidth(240)
        self.bar.setTextVisible(True)

        self.message = QLabel("")
        self.message.setStyleSheet("color:#CCC;")

        layout.addWidget(self.bar)
        layout.addWidget(self.message, 1)

        self.setVisible(False)

    # ------------------------------------------------------------------

    def begin(self, text="Starting…"):

        self.setVisible(True)

        # 0/0 makes Qt show a busy animation, which is right until the
        # renderer tells us how many steps there are.
        self.bar.setRange(0, 0)
        self.bar.setValue(0)

        self.message.setText(text)

    def update_progress(self, progress):

        if progress.total:
            self.bar.setRange(0, progress.total)
            self.bar.setValue(progress.index)

        self.message.setText(progress.text())

    def end(self, text=""):

        self.bar.setRange(0, 1)
        self.bar.setValue(1)

        self.message.setText(text)

        if not text:
            self.setVisible(False)
