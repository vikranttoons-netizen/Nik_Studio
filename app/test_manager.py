from managers.project_manager import ProjectManager
from models.scene import Scene

scene = Scene(
    id="1",
    name="Scene01",
    prompt="Cute baby in bathtub, Pixar style",
    image="",
    video="",
    status="waiting"
)

manager = ProjectManager(
    r"D:\NikStudio\Episodes\Bath Time Song"
)

manager.create_image_job(scene)

print("✅ Project Manager Working")