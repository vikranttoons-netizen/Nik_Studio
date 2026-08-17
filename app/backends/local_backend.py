from backends.base_backend import (
    BaseBackend,
    BackendError,
    BackendUnavailable,
)


class LocalBackend(BaseBackend):
    """
    Generates images on this machine with diffusers.

    torch and diffusers are imported lazily inside the methods, so Nik
    Studio still starts and runs on a machine with no GPU and no AI
    packages installed - the backend simply reports itself unavailable.

    The loaded model is kept in memory between scenes. Reloading SDXL for
    every scene would dominate the render time of an episode.
    """

    name = "Local"
    supports = ("image",)

    DEFAULT_MODEL = "stabilityai/sdxl-turbo"

    def __init__(self, episode_folder, settings=None):

        super().__init__(episode_folder, settings)

        self._pipe = None
        self._loaded_model = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def _missing(self):
        """Return the name of the first missing requirement, or None."""

        try:
            import torch  # noqa: F401
        except ImportError:
            return "torch"

        try:
            import diffusers  # noqa: F401
        except ImportError:
            return "diffusers"

        return None

    def is_available(self):
        return self._missing() is None

    def unavailable_reason(self):

        missing = self._missing()

        if not missing:
            return ""

        return (
            f"Local image generation needs the '{missing}' package, which "
            "is not installed.\n\n"
            "Install it with:\n"
            "  pip install torch --index-url "
            "https://download.pytorch.org/whl/cu121\n"
            "  pip install diffusers transformers accelerate safetensors\n\n"
            "Or switch the episode backend to Colab, which generates on a "
            "free cloud GPU instead."
        )

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load(self):

        model = self.setting("model") or self.DEFAULT_MODEL

        if self._pipe is not None and self._loaded_model == model:
            return self._pipe

        import torch
        from diffusers import AutoPipelineForText2Image

        use_gpu = torch.cuda.is_available()

        try:
            pipe = AutoPipelineForText2Image.from_pretrained(
                model,
                torch_dtype=torch.float16 if use_gpu else torch.float32,
                variant="fp16" if use_gpu else None,
            )
        except Exception as error:
            raise BackendUnavailable(
                f"Could not load the model '{model}'.\n\n{error}\n\n"
                "Check the model name, your internet connection, and that "
                "you are logged in to Hugging Face if the model is gated "
                "(huggingface-cli login)."
            ) from error

        pipe = pipe.to("cuda" if use_gpu else "cpu")

        if not use_gpu:
            # A CPU render takes many minutes per image. Allowed, but the
            # user should know why it is slow.
            print(
                "⚠ No CUDA GPU found - generating on CPU. "
                "This will be very slow."
            )

        self._pipe = pipe
        self._loaded_model = model

        return pipe

    def close(self):

        if self._pipe is None:
            return

        self._pipe = None
        self._loaded_model = None

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    def generate_image(self, scene, prompt):

        if not self.is_available():
            raise BackendUnavailable(self.unavailable_reason())

        if not prompt.strip():
            raise BackendError(
                f"{scene.name} has an empty prompt - nothing to generate."
            )

        pipe = self._load()

        width, height = self._resolution()

        steps = int(self.setting("steps", 4))
        guidance = float(self.setting("guidance", 0.0))
        seed = int(self.setting("seed", -1))

        kwargs = {
            "prompt": prompt,
            "num_inference_steps": steps,
            "guidance_scale": guidance,
            "width": width,
            "height": height,
        }

        if seed >= 0:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"

            kwargs["generator"] = torch.Generator(device).manual_seed(seed)

        try:
            image = pipe(**kwargs).images[0]
        except Exception as error:
            raise BackendError(
                f"Image generation failed for {scene.name}: {error}"
            ) from error

        absolute, relative = self.output_path(
            "Images",
            f"{scene.name}.png",
        )

        image.save(absolute)

        return relative

    # ------------------------------------------------------------------

    def _resolution(self):
        """
        Read "1920x1080" style settings, rounded down to a multiple of 8
        because diffusion models require it.
        """

        text = str(self.setting("resolution", "1024x1024")).lower()

        try:
            width, height = (int(v) for v in text.split("x")[:2])
        except (ValueError, TypeError):
            width, height = 1024, 1024

        width = max(256, width - width % 8)
        height = max(256, height - height % 8)

        return width, height
