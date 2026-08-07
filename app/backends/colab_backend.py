from backends.base_backend import BaseBackend


class ColabBackend(BaseBackend):

    def generate_image(self, scene):

        print(f"Generating image for {scene.name}")

        # TODO:
        # Export Job
        # Launch Colab
        # Import Result

    def generate_video(self, scene):

        print(f"Generating video for {scene.name}")