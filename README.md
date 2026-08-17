# 🎬 Nik Studio

AI-powered desktop application for creating animated videos.

## Current Version

v0.2.0

## Running it

```powershell
pip install -r requirements.txt
python NikStudio.py
```

Nik Studio works out which folder it lives in, so it runs from anywhere.
To keep your episodes somewhere else, set `NIKSTUDIO_ROOT`:

```powershell
$env:NIKSTUDIO_ROOT = "D:\NikStudio"
python NikStudio.py
```

## Rendering an episode

1. Open **Workspace** and pick an episode from the dropdown.
2. Click a scene and write its prompt. Press **💾 Save**.
3. Press **🚀 RENDER EPISODE**.

What happens next depends on the `backend` in the episode's
`episode.json`:

| Backend | What it does |
| ------- | ------------ |
| `Local` | Generates on this PC with diffusers. Needs an NVIDIA GPU plus `torch` and `diffusers` (see `requirements.txt`). |
| `Colab` | Writes a job file per scene into the episode's `Jobs/` folder for a free cloud GPU to pick up. |

### Rendering on a free Colab GPU

1. Put your `Episodes` folder in Google Drive.
2. Open a Colab notebook, set **Runtime → Change runtime type → GPU**.
3. Run `!pip install -q diffusers transformers accelerate safetensors`.
4. Paste in `colab/nik_studio_worker.py`, set `EPISODE` to your episode
   folder in Drive, and run it.
5. Back in Nik Studio, press **📥 Import Results**. The images land in
   `Images/` and the previews update.

Rendering is resumable. Pressing **🚀 RENDER EPISODE** again only renders
what is still missing, and it checks that each file is really on disk
rather than trusting the saved status.

## Testing

```powershell
python tests\test_render_pipeline.py
python tests\test_workspace_ui.py
```

Neither test needs a GPU, and both use a throwaway project folder, so
they never touch your real episodes.

## Features

- Episode management with an episode picker
- Prompt editor with character sheets injected into every prompt
- Image generation — local GPU or free Colab GPU
- Render one scene or a whole episode, resumable
- Production panel showing the real state of every stage
- Export

## Not built yet

Video, voice, music and the FFmpeg final cut are modelled in the pipeline
but have no backend yet, so those stages stay **Not Started**. Buttons for
them are deliberately absent rather than present and dead.
