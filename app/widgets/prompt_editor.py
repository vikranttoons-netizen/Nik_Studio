from PySide6.QtWidgets import QTextEdit


class PromptEditor(QTextEdit):

    def __init__(self):
        super().__init__()

        self.current_scene = None

        self.setPlaceholderText(
            "Select a scene..."
        )

    def show_scene(self, scene):

        self.current_scene = scene

        self.setPlainText(scene.prompt)