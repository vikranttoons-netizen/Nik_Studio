"""
Nik Studio - Colab GPU worker
=============================

This is the other half of the Colab backend. Nik Studio writes job files,
this script generates the images, and Nik Studio imports the results.

    Nik Studio          Google Drive              Colab (this script)
    -----------------------------------------------------------------
    Render Episode  ->  Jobs/Scene01.json     ->  picks up the job
                                                  generates the image
    Import Results  <-  Results/Scene01.png   <-  saves the result

How to use it
-------------
1. Put your Nik Studio Episodes folder in Google Drive.
2. Open a new Colab notebook and choose  Runtime > Change runtime type >
   GPU  (a free T4 is enough).
3. In the first cell, install the packages:

       !pip install -q diffusers transformers accelerate safetensors

4. Paste this whole file into the second cell.
5. Set EPISODE below to your episode folder in Drive.
6. Run the cell. Leave it running while you render.

In Nik Studio: press 🚀 Render Episode to queue the jobs, wait for this
script to report them done, then press 📥 Import Results.
"""

import json
import time
from pathlib import Path

# ----------------------------------------------------------------------
# SETTINGS
# ----------------------------------------------------------------------

# The folder Nik Studio and Colab share. In the notebook the previous cell
# finds this for you and sets it, so there is usually nothing to change
# here - globals() is checked first precisely so that value is not
# overwritten when this cell runs.
EPISODE = globals().get("EPISODE") or (
    "/content/drive/MyDrive/NikStudio/Exchange/Bath Time Song"
)

# How long to keep watching for new jobs, in minutes.
# Set to 0 to process the jobs that exist right now and then stop.
WATCH_MINUTES = 60

# How often to look for new jobs, in seconds.
POLL_SECONDS = 10


# ----------------------------------------------------------------------

def mount_drive():
    """Mount Google Drive. Does nothing when run outside Colab."""

    try:
        from google.colab import drive
    except ImportError:
        print("Not running in Colab - skipping Drive mount.")
        return

    if Path("/content/drive").exists():
        print("Drive already mounted.")
        return

    drive.mount("/content/drive")


# ----------------------------------------------------------------------

class Worker:

    def __init__(self, episode):

        self.episode = Path(episode)
        self.jobs = self.episode / "Jobs"
        self.results = self.episode / "Results"

        self.pipe = None
        self.loaded_model = None
        self.has_adapter = False

    # ------------------------------------------------------------------

    def check_folders(self):

        if not self.episode.exists():
            raise SystemExit(
                f"Folder not found:\n  {self.episode}\n\n"
                "Run the previous cell again - it lists the folders that "
                "have jobs waiting and sets this one for you.\n"
                "If you are running this script on its own, edit EPISODE "
                "at the top."
            )

        self.jobs.mkdir(parents=True, exist_ok=True)
        self.results.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------

    def report_gpu(self):

        import torch

        print("Torch Version  :", torch.__version__)
        print("CUDA Available :", torch.cuda.is_available())

        if torch.cuda.is_available():
            print("GPU            :", torch.cuda.get_device_name(0))
            print("VRAM           :", self.vram_report())
        else:
            print(
                "\n⚠ No GPU. In Colab choose "
                "Runtime > Change runtime type > GPU, then run again."
            )

    # ------------------------------------------------------------------

    def load_model(self, model, with_reference=False):
        """
        Load the model once and reuse it for every job.

        `with_reference` also loads IP-Adapter, which lets a picture of the
        character steer the generation. A written description alone only
        gets a character roughly right; the picture is what keeps the same
        face from scene to scene.
        """

        if (
            self.pipe is not None
            and self.loaded_model == model
            and self.has_adapter == with_reference
        ):
            return self.pipe

        import gc

        import torch
        from diffusers import AutoPipelineForText2Image

        # Let go of the previous pipeline BEFORE building a new one.
        # Without this the old model is still on the card while the new
        # one loads, which needs twice the memory and fails on a T4.
        self.release()

        print(f"\nLoading model : {model}")

        use_gpu = torch.cuda.is_available()

        pipe = AutoPipelineForText2Image.from_pretrained(
            model,
            torch_dtype=torch.float16 if use_gpu else torch.float32,
            variant="fp16" if use_gpu else None,
        )

        # IP-Adapter is loaded before the model is placed, because CPU
        # offload has to be the last thing set up.
        if with_reference:
            try:
                pipe.load_ip_adapter(
                    "h94/IP-Adapter",
                    subfolder="sdxl_models",
                    weight_name="ip-adapter_sdxl.bin",
                )
                print("IP-Adapter loaded - using your character reference.")
            except Exception as error:
                print(f"⚠ Could not load IP-Adapter: {error}")
                print("  Carrying on with the text description only.")
                with_reference = False

        if use_gpu and self.low_vram():
            # SDXL plus IP-Adapter's image encoder does not comfortably
            # fit a 16GB T4. Offloading keeps most of the model in system
            # RAM and moves each piece onto the card as it is needed:
            # slower per image, but it finishes instead of running out.
            pipe.enable_model_cpu_offload()
            print("Low VRAM mode - slower, but it fits.")
        else:
            pipe = pipe.to("cuda" if use_gpu else "cpu")

        # Both cut the peak memory of the decode step and cost almost
        # nothing in speed.
        for method in ("enable_vae_slicing", "enable_attention_slicing"):
            try:
                getattr(pipe, method)()
            except (AttributeError, TypeError):
                pass

        self.pipe = pipe
        self.loaded_model = model
        self.has_adapter = with_reference

        print("Model ready.\n")

        return pipe

    # ------------------------------------------------------------------

    def vram_report(self):
        """Free and total VRAM, so memory trouble is visible early."""

        import torch

        if not torch.cuda.is_available():
            return "no GPU"

        free, total = torch.cuda.mem_get_info()

        gb = 1024 ** 3

        return f"{free / gb:.1f}GB free of {total / gb:.1f}GB"

    def low_vram(self):
        """
        True when the card is too small to hold the whole model.

        A free Colab T4 has about 15GB, which SDXL and IP-Adapter together
        overrun. Anything from 24GB up runs them outright.
        """

        import torch

        if not torch.cuda.is_available():
            return False

        total = torch.cuda.get_device_properties(0).total_memory

        return total < 20 * 1024 ** 3

    def release(self):
        """Give the card its memory back."""

        if self.pipe is None:
            return

        import gc

        import torch

        self.pipe = None
        self.loaded_model = None
        self.has_adapter = False

        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ------------------------------------------------------------------

    def pending_jobs(self):
        """
        Job files that still need doing.

        A job whose result file already exists is skipped, so re-running
        this script never regenerates work that is already finished.
        """

        pending = []

        for job_file in sorted(self.jobs.glob("*.json")):

            try:
                job = json.loads(job_file.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as error:
                print(f"⚠ Skipping unreadable job {job_file.name}: {error}")
                continue

            output = self.episode / job.get(
                "output",
                f"Results/{job.get('scene', job_file.stem)}.png",
            )

            if output.exists() and output.stat().st_size > 0:
                continue

            pending.append((job_file, job))

        return pending

    # ------------------------------------------------------------------

    def run_job(self, job_file, job):

        scene = job.get("scene", job_file.stem)
        prompt = job.get("prompt", "")

        if not prompt.strip():
            print(f"⚠ {scene}: job has no prompt, skipping.")
            return False

        model = job.get("model") or "stabilityai/sdxl-turbo"

        # Nik Studio may write a short name; expand it to a real repo id.
        if "/" not in model:
            model = {
                "sdxl-turbo": "stabilityai/sdxl-turbo",
                "sdxl": "stabilityai/stable-diffusion-xl-base-1.0",
                "flux": "black-forest-labs/FLUX.1-schnell",
            }.get(model, model)

        # Character reference pictures, if the job carries any.
        references = []

        for name in job.get("reference_images", []) or []:

            path = self.episode / name

            if path.exists():
                references.append(path)
            else:
                print(f"⚠ reference not found, skipping: {name}")

        pipe = self.load_model(model, with_reference=bool(references))

        print(f"🎨 {scene} : {prompt[:70]}...")

        guidance = float(job.get("guidance", 0.0))

        kwargs = {
            "prompt": prompt,
            "num_inference_steps": int(job.get("steps", 4)),
            "guidance_scale": guidance,
            "width": int(job.get("width", 1024)),
            "height": int(job.get("height", 1024)),
        }

        # A negative prompt needs classifier free guidance to do anything.
        # Distilled models such as SDXL-Turbo run at guidance 0, where it
        # is ignored at best and an error at worst.
        negative = job.get("negative_prompt", "")

        if negative and guidance > 1:
            kwargs["negative_prompt"] = negative

        if references and self.has_adapter:

            from PIL import Image

            images = [Image.open(p).convert("RGB") for p in references]

            kwargs["ip_adapter_image"] = (
                images[0] if len(images) == 1 else images
            )

            pipe.set_ip_adapter_scale(
                float(job.get("reference_strength", 0.6))
            )

            print(f"   using {len(images)} character reference(s)")

        seed = int(job.get("seed", -1))

        if seed >= 0:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            kwargs["generator"] = torch.Generator(device).manual_seed(seed)

        started = time.time()

        image = pipe(**kwargs).images[0]

        output = self.episode / job.get("output", f"Results/{scene}.png")
        output.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temporary name first, then rename. Nik Studio watches
        # this folder, and must never pick up a half written image.
        temp = output.with_suffix(output.suffix + ".part")

        # PIL picks the format from the file extension, and this temporary
        # name ends in ".part", so the format has to be named outright.
        image_format = {
            ".png": "PNG",
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".webp": "WEBP",
        }.get(output.suffix.lower(), "PNG")

        image.save(temp, format=image_format)
        temp.replace(output)

        print(
            f"✅ {scene} done in {time.time() - started:.1f}s "
            f"-> {output.relative_to(self.episode)}"
        )
        print(f"   VRAM: {self.vram_report()}")

        return True

    # ------------------------------------------------------------------

    def run(self, watch_minutes=WATCH_MINUTES, poll_seconds=POLL_SECONDS):

        print(f"Folder : {self.episode}")

        self.check_folders()
        self.report_gpu()

        print(f"\nWatching : {self.jobs}")

        deadline = time.time() + watch_minutes * 60
        done = 0

        # A job that fails is not retried on the next pass. Without this
        # the watch loop regenerates the same broken job every few
        # seconds, burning GPU time for nothing.
        failed = set()

        while True:

            jobs = [
                (f, j) for f, j in self.pending_jobs()
                if f.name not in failed
            ]

            for job_file, job in jobs:

                try:
                    if self.run_job(job_file, job):
                        done += 1

                except Exception as error:
                    print(f"❌ {job_file.stem} failed: {error}")
                    print("   not retrying it in this run")
                    failed.add(job_file.name)

                    # An out of memory failure leaves the card in a bad
                    # state; clear it so the next job starts clean.
                    if "out of memory" in str(error).lower():
                        self.release()
                        print("   released the GPU before the next job")

            if time.time() >= deadline:
                break

            if not jobs:
                print("… waiting for jobs", end="\r")

            time.sleep(poll_seconds)

        # The notebook often stays open afterwards. Holding several GB of
        # a free GPU for nothing is rude to the next cell and to Colab.
        self.release()

        print(f"\nFinished. {done} image(s) generated.")
        print(f"GPU released. {self.vram_report()}")

        if failed:
            print(f"{len(failed)} job(s) failed: "
                  + ", ".join(sorted(f.replace('.json', '') for f in failed)))

        if done:
            print("Now press 📥 Import Results in Nik Studio.")


# ----------------------------------------------------------------------

if __name__ == "__main__":

    mount_drive()

    Worker(EPISODE).run()
