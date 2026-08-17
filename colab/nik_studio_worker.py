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
# SETTINGS - change this to your episode folder in Google Drive
# ----------------------------------------------------------------------

EPISODE = "/content/drive/MyDrive/NikStudio/Episodes/Bath Time Song"

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

    # ------------------------------------------------------------------

    def check_folders(self):

        if not self.episode.exists():
            raise SystemExit(
                f"Episode folder not found:\n  {self.episode}\n\n"
                "Check the EPISODE setting at the top of this script, and "
                "that Google Drive is mounted."
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
        else:
            print(
                "\n⚠ No GPU. In Colab choose "
                "Runtime > Change runtime type > GPU, then run again."
            )

    # ------------------------------------------------------------------

    def load_model(self, model):
        """Load the model once and reuse it for every job."""

        if self.pipe is not None and self.loaded_model == model:
            return self.pipe

        import torch
        from diffusers import AutoPipelineForText2Image

        print(f"\nLoading model : {model}")

        use_gpu = torch.cuda.is_available()

        pipe = AutoPipelineForText2Image.from_pretrained(
            model,
            torch_dtype=torch.float16 if use_gpu else torch.float32,
            variant="fp16" if use_gpu else None,
        )

        pipe = pipe.to("cuda" if use_gpu else "cpu")

        self.pipe = pipe
        self.loaded_model = model

        print("Model ready.\n")

        return pipe

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

        pipe = self.load_model(model)

        print(f"🎨 {scene} : {prompt[:70]}...")

        kwargs = {
            "prompt": prompt,
            "num_inference_steps": int(job.get("steps", 4)),
            "guidance_scale": float(job.get("guidance", 0.0)),
            "width": int(job.get("width", 1024)),
            "height": int(job.get("height", 1024)),
        }

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

        image.save(temp)
        temp.replace(output)

        print(
            f"✅ {scene} done in {time.time() - started:.1f}s "
            f"-> {output.relative_to(self.episode)}"
        )

        return True

    # ------------------------------------------------------------------

    def run(self, watch_minutes=WATCH_MINUTES, poll_seconds=POLL_SECONDS):

        self.check_folders()
        self.report_gpu()

        print(f"\nWatching : {self.jobs}")

        deadline = time.time() + watch_minutes * 60
        done = 0

        while True:

            jobs = self.pending_jobs()

            for job_file, job in jobs:

                try:
                    if self.run_job(job_file, job):
                        done += 1

                except Exception as error:
                    print(f"❌ {job_file.stem} failed: {error}")

            if time.time() >= deadline:
                break

            if not jobs:
                print("… waiting for jobs", end="\r")

            time.sleep(poll_seconds)

        print(f"\nFinished. {done} image(s) generated.")
        print("Now press 📥 Import Results in Nik Studio.")


# ----------------------------------------------------------------------

if __name__ == "__main__":

    mount_drive()

    Worker(EPISODE).run()
