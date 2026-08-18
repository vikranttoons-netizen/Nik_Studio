# 🎬 Nik Studio

AI-powered desktop application for creating animated videos.

## Current Version

v0.3.0

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
2. Build your scene list with **➕ / 🗑 / ▲ / ▼**. The order of the list is
   the order of the final video.
3. Click a scene and write its prompt. Press **💾 Save**.
4. Press **🚀 RENDER EPISODE**.

That runs the whole pipeline:

```
prompts -> Images/SceneNN.png -> Videos/SceneNN.mp4 -> Exports/<Episode>.mp4
```

Each still becomes a clip with a slow pan and zoom, and the clips are
joined into one playable MP4 in the episode's `Exports` folder.

**FFmpeg is required** for the video stages, and `pip install -r
requirements.txt` already brings a copy of it, so there is usually nothing
to do. A system-wide FFmpeg is used in preference to that copy if you have
one — `winget install Gyan.FFmpeg`, or set `"ffmpeg"` in `episode.json` to
its full path.

Which image backend runs depends on `backend` in the episode's
`episode.json`:

| Backend | What it does |
| ------- | ------------ |
| `Local` | Generates on this PC with diffusers. Needs an NVIDIA GPU plus `torch` and `diffusers` (see `requirements.txt`). |
| `Colab` | Writes a job file per scene into the episode's `Jobs/` folder for a free cloud GPU to pick up. |

### Rendering on a free Colab GPU

Colab can only see Google Drive, so the two sides need one folder in
common. You do not have to move the project there — add `sync_folder` to
`episode.json` and only job files go up and finished images come down:

```json
"sync_folder": "G:\\My Drive\\NikStudio\\Exchange"
```

Everything else — images, clips, the final video — stays on your local
disk. (Leave `sync_folder` out only if the whole episode already lives in
Drive.)

1. Create that folder in Google Drive.
2. Open a Colab notebook, set **Runtime → Change runtime type → GPU**.
3. Run `!pip install -q diffusers transformers accelerate safetensors`.
4. Open `colab/NikStudio_Colab.ipynb`, set `EPISODE` to the episode's
   folder inside your sync folder, and run the cells.
5. Back in Nik Studio, press **📥 Import Results**. The images land in
   `Images/` and the previews update.

Rendering is resumable. Pressing **🚀 RENDER EPISODE** again only renders
what is still missing, and it checks that each file is really on disk
rather than trusting the saved status.

## Episode settings

Everything below is optional and lives in the episode's `episode.json`:

| Setting          | Default     | What it does |
| ---------------- | ----------- | ------------ |
| `backend`        | `Colab`     | Where images are generated: `Local` or `Colab` |
| `aspect`         | `16:9`      | `16:9`, `9:16`, `1:1`, or `1920x1080` |
| `fps`            | `24`        | Frames per second of the output |
| `scene_duration` | `4`         | Seconds each scene is on screen |
| `image_size`     | from `aspect` | Size images are generated at, e.g. `1024x576` |
| `low_vram`       | `false`     | For a 6–8GB GPU: slower, far less VRAM |
| `model`          | `sdxl-turbo`| Image model |
| `style`          | —           | Appended to every prompt |
| `character`      | —           | Character sheet injected into every prompt |
| `sync_folder`    | —           | Folder shared with Colab, so the project can stay on a local disk |
| `ffmpeg`         | —           | Full path to `ffmpeg.exe` if it isn't on PATH |

To hold one shot longer than the rest, put `"duration": 8` in that
scene's `metadata` in `scenes.json`.

`resolution` is the size of the finished **video** only. Images are
generated near 1024px to match what SDXL-class models are trained on —
asking a diffusion model for 1920x1080 is slow, hungry, and composes
badly — and the video stage scales them up to full HD.

## Something not where you expect it?

```powershell
python tools\doctor.py
```

It prints which project folder Nik Studio is really using, the episodes and
scenes it can see, how many jobs/images/clips exist, whether the character
in `episode.json` actually exists, what is installed — and then names the
next thing to do.

## Testing

```powershell
python tests\test_render_pipeline.py
python tests\test_video_pipeline.py
python tests\test_workspace_ui.py
```

None of them need a GPU, and each uses a throwaway project folder, so
they never touch your real episodes.

## Features

- Episode management with an episode picker
- Add, delete and reorder scenes
- Prompt editor with character sheets injected into every prompt
- Image generation — local GPU or free Colab GPU
- Video from stills with pan and zoom, via FFmpeg
- Final episode MP4 in 16:9, 9:16 or 1:1
- Render one scene or a whole episode, resumable
- Production panel showing the real state of every stage
- Export

## Not built yet

Voice and music are modelled in the pipeline but have no backend yet, so
those stages stay **Not Started**, and the final MP4 has no sound. An AI
video model (WAN, LTX) can replace the pan-and-zoom stage later by
implementing the same `generate_video` — nothing in the UI would change.
