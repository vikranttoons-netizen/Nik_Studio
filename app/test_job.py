from services.job_creator import JobCreator
from models.scene import Scene

scene = Scene(
    id="Scene01",
    name="Scene01",
    prompt="""
A happy Indian baby playing in bathtub,
Pixar style,
high quality
""",
    image="",
    video="",
    status="waiting"
)

creator = JobCreator(r"D:\NikStudio\Episodes\Bath Time Song")

creator.create_image_job(scene)

print("✅ Test Completed")