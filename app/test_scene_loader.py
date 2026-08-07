from services.scene_loader import SceneLoader

loader = SceneLoader(r"D:\NikStudio\Episodes\Bath Time Song")

scenes = loader.load()

for scene in scenes:
    print(scene)