from pathlib import Path


class Project:

    def __init__(self):

        self.root = Path("D:/NikStudio")

        self.episodes = self.root / "Episodes"

        self.outputs = self.root / "Outputs"

        self.assets = self.root / "Assets"

        self.models = self.root / "Models"

    def info(self):

        print("=" * 50)
        print("Nik Studio")
        print("=" * 50)

        print("Root      :", self.root)
        print("Episodes  :", self.episodes)
        print("Outputs   :", self.outputs)
        print("Assets    :", self.assets)
        print("Models    :", self.models)