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

        if use_gpu and self.setting("low_vram"):
            # Keeps most of the model in system RAM and moves pieces onto
            # the GPU as needed. Slower, but it lets a card with 6-8GB
            # run SDXL instead of failing with "out of memory".
            pipe.enable_model_cpu_offload()

            try:
                pipe.enable_vae_slicing()
            except AttributeError:
                pass

            print("ℹ low_vram is on - slower, but uses much less VRAM.")

        else:
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

    def generate_image(self, scene, prompt, negative=""):

        if not self.is_available():
            raise BackendUnavailable(self.unavailable_reason())

        if not prompt.strip():
            raise BackendError(
                f"{scene.name} has an empty prompt - nothing to generate."
            )

        pipe = self._load()

        width, height = self.image_size()

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

        # A negative prompt only does anything when classifier free
        # guidance is on. Distilled models such as SDXL-Turbo run at
        # guidance 0 and would raise if it were passed.
        if negative and guidance > 1:
            kwargs["negative_prompt"] = negative

        if seed >= 0:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"

            kwargs["generator"] = torch.Generator(device).manual_seed(seed)

        try:
            image = pipe(**kwargs).images[0]

        except Exception as error:

            text = str(error).lower()

            # Running out of VRAM is by far the most common local failure,
            # and the raw message does not say what to do about it.
            if "out of memory" in text or "cuda error" in text:
                raise BackendError(
                    f"{scene.name}: the GPU ran out of memory at "
                    f"{width}x{height}.\n\n"
                    "Fix it in the episode's episode.json, either:\n"
                    '  "low_vram": true          (slower, much less VRAM)\n'
                    '  "image_size": "1024x576"  (smaller images)\n\n'
                    "Or switch to the Colab backend to use a cloud GPU."
                ) from error

            raise BackendError(
                f"Image generation failed for {scene.name}: {error}"
            ) from error

        absolute, relative = self.output_path(
            "Images",
            f"{scene.name}.png",
        )

        image.save(absolute)

        return relative

