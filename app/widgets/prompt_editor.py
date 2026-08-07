from PySide6.QtWidgets import QTextEdit


class PromptEditor(QTextEdit):

    def __init__(self):
        super().__init__()

        self.current_scene = None

        self.setPlaceholderText("Write your prompt here...")

    def show_scene(self, scene):

        self.current_scene = scene

        self.setPlainText(scene.prompt)

    def save_scene(self):

        if self.current_scene is None:
            return

        self.current_scene.prompt = self.toPlainText()