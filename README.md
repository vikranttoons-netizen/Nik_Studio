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

Each still becomes a clip with a moving camera, and the clips are joined
into one playable MP4 in the episode's `Exports` folder. Consecutive
scenes move differently — zoom in, pan right, zoom out, pan left — so
the episode does not read as one repeated effect. Turn it up or down
with `motion`, or pin one shot with `"move": "pan_left"` in that
scene's `metadata`.

This is camera movement over a still picture, not animation: the
character does not move. Animating the character needs a video model,
which is not built yet — see **Not built yet** below.

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
common. You do not have to move the project there — name a `sync_folder`
and only job files go up and finished images come down.

Put it in `nikstudio.local.json` at the project root. That file is not in
git, so a path that only exists on your machine never collides with an
update:

```json
{
    "sync_folder": "G:\\My Drive\\NikStudio\\Exchange"
}
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

To make everything again — after changing the style, the model, or the
character reference — press **↻** beside it. It asks first, then renders
every scene regardless of what is already done.

## Episode settings

Everything below is optional and lives in the episode's `episode.json`.
Anything machine specific — `sync_folder`, `ffmpeg`, `low_vram` — is
better placed in `nikstudio.local.json` at the project root, which is
not in git and overrides `episode.json`:

| Setting          | Default     | What it does |
| ---------------- | ----------- | ------------ |
| `backend`        | `Colab`     | Where images are generated: `Local` or `Colab` |
| `aspect`         | `16:9`      | `16:9`, `9:16`, `1:1`, or `1920x1080` |
| `fps`            | `24`        | Frames per second of the output |
| `scene_duration` | `4`         | Seconds each scene is on screen |
| `motion`         | `lively`    | Camera movement: `none`, `gentle`, `lively`, `strong` |
| `image_size`     | from `aspect` | Size images are generated at, e.g. `1024x576` |
| `low_vram`       | `false`     | For a 6–8GB GPU: slower, far less VRAM |
| `model`          | `sdxl-turbo`| Image model |
| `style`          | —           | Leads every prompt, so it actually takes effect |
| `negative_prompt`| duplicates, photo look | What the image must not contain (needs `guidance` > 1) |
| `steps`          | `4`         | Denoising steps: 4 for turbo models, ~30 for full SDXL |
| `guidance`       | `0`         | 0 for turbo models, ~7 for full SDXL |
| `character`      | —           | Character sheet injected into every prompt |
| `use_reference`  | `true`      | Send the character picture at all. Turn off if IP-Adapter misbehaves |
| `reference_strength` | `0.5`   | How strongly a character's reference picture steers the image |
| `music`          | `Audio/*`   | The song. Found automatically in the episode's `Audio` folder |
| `fit_to_music`   | `true`      | Stretch the scenes so the video is as long as the song |
| `sync_folder`    | —           | Folder shared with Colab, so the project can stay on a local disk |
| `ffmpeg`         | —           | Full path to `ffmpeg.exe` if it isn't on PATH |

**Getting the style you asked for.** `sdxl-turbo` is fast (about 2 seconds
an image) but runs at `guidance` 0, where it ignores the negative prompt
and tends towards photorealism whatever style you name. For stylised work
use the full model — `"model": "sdxl", "steps": 30, "guidance": 7` — which
is slower (~20s an image on a free T4) but actually follows the style and
the negative prompt.

To hold one shot longer than the rest, put `"duration": 8` in that
scene's `metadata` in `scenes.json`.

`resolution` is the size of the finished **video** only. Images are
generated near 1024px to match what SDXL-class models are trained on —
asking a diffusion model for 1920x1080 is slow, hungry, and composes
badly — and the video stage scales them up to full HD.

## Adding the song

Drop an audio file into the episode's `Audio` folder:

```
Episodes\Bath Time Song\Audio\bath time song.mp3
```

Press 🚀 RENDER EPISODE and it is mixed into the final MP4, and the scenes
are stretched so the pictures last exactly as long as the song — three
scenes over a 19 second song become 6.3 seconds each, instead of the video
ending while the music plays on.

A scene with its own `"duration"` in `metadata` keeps it, and the rest
share what is left. Set `"fit_to_music": false` to keep fixed durations
and let the audio simply stop with `-shortest`.

Nik Studio does not write the song. Bring one from wherever you like — a
service such as Suno, your own recording, or a licensed track. There is no
free open model that sings nursery rhymes well; the ones that generate
music (MusicGen and friends) do instrumentals, and their vocals are
mumbled.

## Keeping a character the same

A written description only gets a character roughly right, and every
render drifts a little. Point the character sheet at a picture of them
instead:

```json
"reference_image": "Characters/nik.png"
```

The path is relative to the project folder. That picture is sent with
every job and applied through IP-Adapter, so the same face carries across
scenes. `reference_strength` (default `0.5`) controls how hard it pulls —
raise it towards 0.8 for a closer likeness, lower it if scenes start
looking like copies of the reference.

Write the sheet to match the picture. A sheet saying "10 month old, blue
romper" alongside a reference of a toddler in a yellow t-shirt pulls the
model in two directions at once.

## Keeping the disk and the GPU tidy

```powershell
python tools\cleanup.py            # show what could go
python tools\cleanup.py --delete   # delete it
```

Only work that can be regenerated is ever offered: scene clips, the
finished video, export archives, and job files whose image already came
back. Your prompts, images and character references are never touched —
images cost GPU time, so they stay, while clips and the final video are
rebuilt in seconds by pressing 🚀 RENDER EPISODE.

On the Colab side the worker loads the model once for the whole run,
prints how much VRAM is left after each image, and hands the GPU back
when it finishes.

## Everything here is free

Nothing in this pipeline needs a paid account, and nothing used is
licensed non-commercially:

| Part | Tool | Licence |
| ---- | ---- | ------- |
| Images | SDXL on a free Colab T4 | open, commercial use allowed |
| Character likeness | IP-Adapter | Apache 2.0 |
| Video and audio muxing | FFmpeg | LGPL |
| Music | YouTube Audio Library, or your own recording | free, cleared for monetisation |

Two things to be careful of if you monetise: **MusicGen** weights are
CC-BY-NC, so its output is not for commercial use, and AI song services
generally reserve commercial rights for paid plans. Recording the rhyme
yourself, or using the YouTube Audio Library, avoids both.

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
- Final episode MP4 in 16:9, 9:16 or 1:1, with the song mixed in
- Render one scene or a whole episode, resumable
- Production panel showing the real state of every stage
- Export

## Trying a real video model

Pan and zoom moves the camera, not the child. Making the child actually
move needs an image-to-video model, and before any of that is built into
Nik Studio there is one question worth answering first: does a free Colab
GPU animate *your* character well enough to be worth it?

`colab/NikStudio_Video_Test.ipynb` answers it. Open it in Colab, set
**Runtime → Change runtime type → T4 GPU**, upload one finished image,
and run the four cells. It makes a single three second clip and plays it
back. It writes nothing into your project.

Cell 3 takes 10–20 minutes, because the model is far too big for a free
T4 and has to be streamed through the card a piece at a time.

Which model, and why:

| Model | Image to video | Free T4 | Licence |
| ----- | -------------- | ------- | ------- |
| **CogVideoX-5B-I2V** | yes | yes, streamed | commercial use free after a free registration; the clips it makes are yours |
| Wan 2.2 TI2V-5B | yes | no — wants ~24GB | Apache 2.0, nothing to sign |
| Wan 2.2 I2V-A14B | yes | no — 14B | Apache 2.0 |
| CogVideoX-2B | **no**, text only | yes | Apache 2.0 |

CogVideoX-5B-I2V is the only one of those that both does image-to-video
and fits, so it is what the test uses. Its licence is not Apache — it
allows commercial use free of charge, but asks you to register first, and
caps free use at a million visits a month. Wan 2.2 is the cleaner licence
and the better model, and is what this should move to on a rented GPU or
a 24GB card at home.

One honest warning: a T4 cannot do `bfloat16`, which is the precision
this model wants, so the test falls back to `float16`. If the clip comes
back washed out or streaky, that is the card, not the prompt.

## Not built yet

Voice has no backend yet, so that stage stays **Not Started** — there is
no spoken narration, only whatever song you supply. An AI video model can
replace the pan-and-zoom stage by implementing the same `generate_video`,
and a music generator can fill the `music` stage — nothing in the UI
would change either time.
