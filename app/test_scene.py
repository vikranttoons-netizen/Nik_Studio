from services.scene_service import SceneService

service = SceneService(r"D:\NikStudio\Episodes\Bath Time Song")

print("Images")

for img in service.get_images():
    print(img.name)

print()

print("Videos")

for vid in service.get_videos():
    print(vid.name)