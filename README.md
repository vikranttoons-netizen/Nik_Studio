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
python tests\test_blender.py
python tests\test_render_pipeline.py
python tests\test_video_pipeline.py
python tests\test_workspace_ui.py
python tests\test_prepare.py
python tests\test_animate_notebook.py
```

None of them need a GPU, and each uses a throwaway project folder, so
they never touch your real episodes.

`test_animate_notebook.py` runs cell 2 of the Colab notebook itself, with
a stand-in for the model and everything else real — the ordering, the
checks, the song split, the frame counts, the stretch, the concat, the
audio, and the stamps that decide whether a clip may be reused. It covers
the second run remaking nothing, a replaced picture not keeping its old
clip, a full card giving a shorter clip instead of dying, and the two
refusals. That notebook runs on a GPU charged by the minute, so a fault
in it is one somebody paid for.

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

## Getting ready before you pay for a GPU

A GPU is charged by the minute, so nothing that can be checked without
one should be discovered halfway through a run:

```powershell
python tools\prepare.py            # check, and change nothing
python tools\prepare.py --copy     # build the Colab folder
```

It gathers your pictures and your song and copies them into the Drive
folder the notebook expects, numbered `Scene01`, `Scene02`, … in order.
Numbers are compared as numbers, so `shot2` lands before `shot10` rather
than after it.

Where it looks, in order:

1. the Drive folder itself, if you have already put pictures in there —
   that is plainly what you meant, and it tidies them where they stand,
   renumbering in place and clearing away the old names
2. otherwise an episode's `Images` and `Audio` folders
3. or wherever `--from` points

It says which one it used, so old renders never get prepared by mistake.

Before copying anything it checks, and refuses to say ready otherwise:

- every picture actually opens, and says so by name if one does not
- the song can be read, and how long it is
- there are enough pictures for the song — three pictures under a
  four minute song would each be slowed to a crawl, and it says how many
  to use instead
- nothing is left in the folder from a longer episode, which the notebook
  would otherwise pick up as extra scenes
- clips already in `Output/Clips` are pointed out, so a changed picture
  is not quietly given its old clip

Tell it where Drive is once, in `nikstudio.local.json`:

```json
{
    "input_folder": "G:\\My Drive\\NikStudio\\Input"
}
```

The notebook repeats every one of these checks on the Colab side before
it loads the model, and stops with `Nothing has been charged for.` rather
than spend a minute of GPU time on a run that cannot work.

## Making an episode

`colab/NikStudio_Animate.ipynb` is the finished job in one notebook: give
it your scenes and a song, and it gives back a cut, mastered, YouTube-
ready MP4 — plus a vertical one for Shorts.

There are two ways in. **Write the scenes**, one to a line:

```
My Drive / NikStudio / Input /
      script.txt
      song.mp3
```

```
# script.txt - one scene a line. A # parks a line without deleting it.
He walks into a sunny flower garden and waves hello, the puppy trotting beside him, the camera does not move
He crouches down and pats the golden puppy, which wags its tail, the kitten watching, the camera does not move
Close up of his face as he laughs, cheeks round, the garden soft behind him, the camera does not move
```

`colab/script_example.txt` is a full one — fourteen scenes for a two
minute song, with the rules for writing them at the top. Copy it into
Drive and edit from there.

Its name barely matters: **any `.txt` in the Input folder is taken as the
script**, preferring one called `script`. Windows hides extensions, so
renaming a file to `script.txt` in Explorer quietly produces
`script.txt.txt`, and Drive is case sensitive, so `Script.txt` is a
different file again. There is no other reason for a `.txt` to be in
there, so all of them work.

`colab/script_prompt.txt` is the brief to hand a language model if you
would rather it wrote the scenes — it encodes every rule below, and its
answer goes straight into `script.txt` unedited.

Do not describe the character or the art style in a line: `CHARACTER`
and `STYLE` at the top of cell 2 are put in front of every one of them,
and that repetition is the only thing keeping him the same boy from shot
to shot.

**The fast model does not read your negative prompt.** `FAST_MODEL =
True` runs LTX 13B distilled at `guidance_scale = 1.0`, which is where
classifier-free guidance stops happening: the negative prompt is not
used at all, and the positive one steers only weakly. That is worth
knowing before spending an afternoon rewording a style — two attempts at
fixing the art style that way barely moved it, because the words were
hardly being read.

The default is Wan 2.2 at `guidance_scale = 5.0`: the style words pull
and the negative prompt is obeyed. The notebook prints which of the two
you are on and what it means.

**`FRAMING` decides whether he is in the shot at all.** The first Wan
clip came back with the boy filling the frame, the top of his head cut
off, and by two seconds he had walked out of the right of the picture
and left an empty meadow. Neither is the model's fault: nothing said
how far away to stand or that he had to stay, so it chose, and a video
model's idea of a shot is whatever its training data did most — which
is close. `FRAMING` sits second in the prompt, straight after the
action, and the faults are named in `NEGATIVE` as well.

The other half of that fix is in the script. A line that says he
*walks into* the meadow gets a model that walks him out again, and the
back half of the clip is grass. Every action has to happen where he
already is, and `colab/script_prompt.txt` says so in the words you hand
to ChatGPT.

**`STYLE` decides whether it looks expensive.** It used to end with
"cheerful children's cartoon", and that is exactly the phrase that
fetched back flat, cheap-looking shading — it is what most of the
training data with that look calls itself. Naming the *craft* rather than
the audience — "3D animated feature film still, Pixar and DreamWorks
quality rendering, subsurface scattering, global illumination, volumetric
sunlight" — is what pulls it towards the render you want, and the flat
look is pushed away in the negative prompt rather than merely left
unasked for. Each line says one thing he does, who else is in the shot, and
whether the camera moves. Anything left out, the model invents — which is
how the puppy melted the first time.

Or **give it pictures** and it animates those:

```
My Drive / NikStudio / Input /
      Scene01.png
      Scene02.png
      Scene03.png
      song.mp3
```

A `script.txt` wins if both are there, and it says so rather than
quietly picking one.

**What you give up by writing them.** A picture is what holds the look
still: with one, the same boy, the same garden and the same puppy carry
from clip to clip. Written scenes have nothing to anchor them, so the
`CHARACTER` and `STYLE` lines at the top of cell 2 do the work instead —
they lead every prompt so the description is word-for-word identical
every time, and the seed is fixed too. It is not the same as a
reference picture, and it will drift between shots. Write the character
once, keep it exact, and change it for nothing.

Names do not matter — pictures are used in order, so number them, and any
one audio file is taken as the song. The result lands in
`My Drive / NikStudio / Output / Episode.mp4`.

`python tools\prepare.py --copy` builds and checks either folder before
you open Colab: it counts the scenes in a script the same way the
notebook does, and carries the script across with the song.

**Drive is optional.** If it will not connect — Colab's sign-in popup is
routinely blocked by third-party cookie settings, and the error it gives
says nothing useful — the notebook says what would fix it and then
carries on without it. It asks you to upload the script, the song and any
pictures straight from your PC, and downloads the finished video back at
the end. The only thing lost is that a session's clips do not survive it,
so a second run generates them again.

**Check on a CPU runtime first.** Colab charges for a GPU from the moment
it connects, whatever you run on it, so the notebook does everything that
does not need one before it asks for one:

1. **Runtime → Change runtime type → CPU**, then run cell 2. It finds
   your files, checks every one, and stops with `this cost nothing`.
2. Only then **Runtime → Change runtime type → L4 GPU**, run cell 1, and
   run cell 2 again.

A wrong folder or a picture that will not open is worth finding out for
free. Pick **L4** rather than A100 — the model is small, and A100 spends
compute units far faster for no better result.

Every shot becomes a short moving clip. Then it is **edited**: cut every
few seconds, every cut landing on a beat of the song, coming back to each
clip more than once from a different camera move. Eleven clips become
forty-odd shots that way. That is how a children's channel is put
together, and it is also what this model needs — nothing is on screen
long enough to drift. The editing costs no GPU at all, so it is rebuilt
from scratch every run.

Each generated clip is saved to Drive as it finishes, so a session that
dies costs you one clip rather than all of them — run it again and it
carries on. Change a line of your script, or a picture, and only that one
is made afresh.

The notebook reads the machine and picks its own settings — which model,
which precision, whether the text encoder has to be squeezed to 8-bit. It
weighs ordinary RAM as well as the card, because the 9GB text encoder is
unpacked in RAM before it ever reaches the GPU, so a big card on a
small-RAM runtime dies just the same. There is nothing to tune.

**How long one picture can hold.** Everything in the picture drifts as
a clip goes on, smallest things first. Over eight seconds the face melted
at two and the whole scene was gone by four; over three, the butterflies
melted at one second and the animals' faces by one and a half. So the
model is only ever asked for **two seconds** on LTX, and the edit cuts
away before there is anything to see. Wan drifts far less, so it is
asked for one take slightly longer than a whole shot instead.

**The edit.** `SHOT_SECONDS` (2.8) is how long one shot holds. One of
the six camera moves is a `hold`; the rest travel 11%. That number has
been wrong twice: 16% was a lurch, and 6% took the whole video down to a
third of the movement it had, because this model barely moves on its own
and the camera was carrying all of it.

**Movement, as a number.** The run ends by printing two of them — the
motion in the finished video and the motion in one clip straight from
the model — because "it is still not right" is not something anyone can
act on and a video is not always something you can send. Every frame is
subtracted from the one before it and what is left is averaged, so a
photograph scores 0. The LTX videos scored between 3 and 10; the
children's channels this is aimed at score 15 to 20. Two numbers rather
than one because they separate the two possible faults, which need
opposite fixes: the model not moving anything, and the edit not doing
enough with what it was given.

**The beat.** The cuts land on the beat, but between cuts nothing was
answering the music — the picture simply sat there. Every beat now gives
the camera a small push that falls away over about a fifth of a second,
so the frame breathes in time. Measured against a still picture: the
camera move alone comes out at 1.81 and with the pulse at 4.26, with the
peaks on the beats. 0.08 strength was jumpy; it is 0.05. Beats come
from `librosa`; without them it falls back to an even grid and says so,
rather than claiming a beat it did not find. Every shot gets a slow
camera move — push in, pan, pull out — cycling, so coming back to a clip
does not read as a repeat. The whole thing is assembled at 1920×1080,
h264 high profile with `+faststart`, and the song is brought to −14 LUFS,
which is what YouTube normalises to; an unmastered upload just sounds
quiet next to a channel that did it.

**The words of the song.** Put a `lyrics.txt` in the Input folder, one
line of the song to a line, and they are drawn on screen — spread across
the song on its beats, so they change with the music rather than on a
stopwatch. Children sing along with them, and it is what every channel in
this corner of YouTube does. It costs no GPU at all.

Any `.txt` whose name starts with `lyric` is the lyric sheet; anything
else is the script, so the two are never confused. The wide video and the
vertical one each get their own, drawn at their own size — burning them
once and shrinking would leave the words half-sized in the Short.

If the lyrics are in Devanagari and no font on the machine can draw it,
they are left off and it says so, with the one line that fixes it.
Rendering empty boxes would be worse than rendering nothing.

A vertical 1080×1920 cut of the first 55 seconds is written alongside it
for Shorts, centre cropped — the character is in the middle of every
shot, so the middle is what to keep. Fitting the whole 16:9 frame into
9:16 against a blurred blow-up of itself was tried and was worse: the
picture fills under a third of the height, so most of the Short was a
huge blurred face with a strip of video through the middle. Turn it off
with `MAKE_SHORT = False`.

**The watermark.** LTX 0.9.8 distilled was trained on captioned video and
stamps a line of garbled caption text along the bottom of everything it
makes. No negative prompt shifts it. The bottom 14% is cut off every clip
and the edit re-frames around what is left.


**Put the action first.** The prompt is the scene line, then the
character, then the style — in that order. It was character-first, and a
clip came back of a boy standing still in an empty field: no puppy, no
flowers, none of what the line asked for. A video model weighs the front
of a prompt hardest, and this one weighs everything weakly, so sixty
words of costume description in front of the one thing that is meant to
happen is throwing it away.

**Name everything that must stay.** Whatever the prompt does not mention
is free to drift, and it will. A prompt describing only the boy left the
puppy, the kitten and the duckling to melt. Say who else is in the shot
and that they stay, and say the camera does not move — without that last
line the frame slowly pushes in on its own.

A picture that has to be on screen longer is not given a longer clip. The
clip is played forwards, then backwards, then forwards again, for as long
as it takes. A sway or a clap reads as continuous that way, the turn is
at the moment the movement reverses where it is least visible, and a
frame is dropped at each seam so nothing is ever held twice.

Roughly: enough shots that **each is seen about four times** across the
song — for a two minute song, a dozen or so. Coming back to a setup is
how television works; coming back eight times is not, and the notebook
says so before it starts.

**Try one picture first.** Set `TEST_ONE_PICTURE = True` at the top of
cell 2 and it makes a single clip from the first picture, ignores the
song, and stops — about two minutes of GPU. Worth doing before every real
run, and certainly before a new character or a new prompt: it tells you
what the model does with your picture instead of letting you find out
eleven clips later.

**One honest limit.** The mouth moves but it is not lip-synced to the
words. Nothing free does real lip-sync yet.

### One picture of Nik, and every scene drawn from him

A model asked for sixteen scenes from words alone gives you sixteen
different boys. The words are all it has to hold him to, and words are
not a face — `CHARACTER` describes him in every prompt and it still is
not the same child twice.

So: put **one** picture of Nik on his own in the Input folder, named so
it starts with `nik`. It stops being a scene and becomes the boy. Each
line of the script is drawn as a still — SDXL with **IP-Adapter**
carrying the reference — and the video is made from that drawing rather
than from the words.

That fixes two things at once. He is the same boy in all sixteen, and
the framing is decided by a model that is good at composing a picture
instead of by one that is good at moving one. The first Wan clip cut
the top of his head off and then walked him out of the frame; a drawn
first frame cannot do either.

Only him. `REFERENCE_NAME` picks out one file and one only — the puppy,
the kitten and the duckling still come from the words in the line,
because a reference of a boy should not be asked to decide what a
duckling looks like. `LIKENESS` (0.6) is how hard it pulls: too low and
he drifts back to being a different boy, too high and every scene comes
back as a copy of the reference whatever the line said. `REFERENCE_NAME
= ""` turns the whole thing off.

The scenes are kept in `Output/Scenes` and stamped like the clips, so a
second run draws nothing again. The drawing model is loaded before the
video model and deleted before it — two seven-gigabyte models on one
card is how a run dies at scene twelve with everything to do over.

Licences: SDXL base is CreativeML Open RAIL++-M, IP-Adapter is Apache
2.0. Both are free to use commercially.

### `QUALITY`, and why size is most of it

One setting, three answers: `"draft"` (832×480, 20 steps), `"good"`
(1024×576, 30 — the default) and `"best"` (1280×704, 30 — what the 5B
was trained at, roughly three times the time of `"good"`).

The finished video is 1080p, so a clip generated at 832×480 is stretched
2.3× to reach it and one at 1024×576 only 1.9×. That stretch is most of
why the finished file has looked softer than the clip it was made from,
and it is also why the upscale in the edit is `lanczos` now rather than
`bicubic` — the earlier comment said a 960-wide clip has no detail for a
sharper filter to find, and at 1024 and 1280 wide there is.

The run also says, after the first clip and only then, how long the rest
will take at that rate. It is measured rather than guessed, and it
arrives while there is still time to switch to `"draft"` instead of
finding out an hour later how long an hour is.

`MOTION` is a third fixed part of every written prompt, alongside
`FRAMING` and `CHARACTER`. The clips measured 3.67 against the 15–20 the
children's channels run at, and the script was not the whole of it: a
video model will animate one arm and leave everything else standing
perfectly still, because nothing asked it not to. It is written as a
description — "smooth lively continuous movement, natural secondary
motion in his hair, his clothes and the grass" — rather than as a
negation, because the last time this notebook told a model to be unlike
a still picture, the face melted at two seconds.

### Repeats are the other half

Sixteen clips across a 125-second song is 45 cuts, so each clip covers
about three cuts in a row. Different camera move each time, same three
seconds of picture — and that reuse is the clearest thing separating
this from the channels it is aimed at, which never show a shot twice.
No code change fixes it: the run now prints the number of scenes that
would remove it entirely, and that number goes in `script.txt`.

### A preview small enough to send

The finished file is 1080p and a couple of hundred megabytes, and most
places will not accept one that size — which meant the only thing that
ever came back was a description, and a description cannot be measured.
Every run also writes `Episode_Preview.mp4`, re-encoded small and
re-encoded smaller again if the first attempt is not under 25MB.

### Which model, and why

**Wan 2.2 TI2V-5B is the default on a card with room for it.** Every
video this notebook made before it was LTX, and the complaint about
every one of them was the same: not enough happens. That is not a
prompting fault better words would have fixed. LTX 13B is built to hold
a picture steady and it is very good at it — ask it for a parade and it
gives you a photograph of one. Wan is trained on movement, is Apache 2.0
with no revenue ceiling attached, and is a third of the size, so it
needs none of the fp8 machinery the LTX 13B did: no component is bigger
than the card, and whole-component offloading is enough.

The notebook still reads the machine — `FORCE_MODEL = "big"` or
`"small"` overrides it — and `FAST_MODEL = True` buys speed back
knowingly.

**A card too small for Wan stops the run** rather than quietly falling
back. A T4 can only run the 2B, which is the model behind every video
that was not lively enough, and an hour spent on it is an hour wasted;
the notebook says to switch to L4 and how, and takes `FORCE_MODEL =
"small"` from anyone who means it. The free check on a CPU runtime is
unaffected — it has no card to judge, so it assumes the one you are
about to turn on.

| | Wan 2.2 TI2V-5B *(default)* | LTX 13B distilled *(`FAST_MODEL`)* | LTX 2B *(small cards)* |
| --- | --- | --- | --- |
| Runs on | a 24GB card, ~30GB RAM | the same | anything, a free T4 included |
| Steps | 30 | **8** — distilled | 50 |
| Guidance | 5.0 — the negative prompt is read | 1.0 — it is not read at all | 3.0 |
| Movement | what it is built for | holds still; that is what it is built for | drifts rather than moves |
| Generated at | 1024×576 (`QUALITY`) | 960×544 | 768×448 |
| Clip length | 3.0s — a whole shot in one take | 2.0s, played forwards and back | 2.0s, played forwards and back |
| Sixteen shots | an hour and a bit at `"good"` | about 12 minutes | — |
| Licence | Apache 2.0 | free under $10M revenue | free under $10M revenue |

Two details that are the model's own instructions rather than choices:
the VAE is kept in **float32** (in bfloat16 it returns blotchy colour),
and the scheduler runs at **`flow_shift = 5.0`**. The size divides by 32
both ways because the VAE compresses 16× in space and the patch size
doubles that again, and `(frames - 1)` divides by 4 rather than LTX's 8.

**The loop was itself part of the problem.** A two-second clip played
forwards, then backwards, then forwards again is a wobble — the parade
walks off and then walks back in. LTX could not be trusted past two
seconds, so there was no choice about it. Wan holds together, so each
shot gets one unbroken clip slightly longer than `SHOT_SECONDS` and the
movement only ever goes one way. The notebook says `clips run forwards
only` when that applies.

The LTX 13B is still loaded the way the diffusers docs prescribe when
you ask for it: 26GB in bfloat16 against a 24GB card, so fp8 layerwise
weight-casting halves the storage and converts back a layer at a time,
and leaf-level group offloading keeps only the piece being computed on
the card.

Others considered and rejected:

| Model | Image to video | Free Colab | Licence |
| ----- | -------------- | ---------- | ------- |
| CogVideoX-5B-I2V | yes | **no — crashes** | free after a free registration |
| Wan 2.2 TI2V-5B | yes | no — wants ~24GB | Apache 2.0 |
| CogVideoX-2B | **no**, text only | yes | Apache 2.0 |

CogVideoX-5B-I2V was tried first, on licence grounds, and it does not
work on a free Colab. The wall is not the GPU: a free Colab has **12.7GB
of ordinary RAM**, and that model needs more than that just to be loaded,
so the session dies before it generates anything. Model size against
system RAM is the constraint that decides this, not VRAM.

A T4 also has no real `bfloat16`, which is the precision these models
want, so on one the notebook falls back to `float16`. It decides that
from the GPU's compute capability rather than from
`torch.cuda.is_bf16_supported()`, which answers `True` on a T4 — torch
emulates bfloat16 in software there instead of refusing, and the
emulation is slow enough to turn a twenty minute run into an afternoon.

## The Blender half

`blender/nik_blender.py` renders the clips from a rigged 3D character
instead of from a video model. Everything after it — the beat cut, the
camera, the song, the encode, the vertical cut — is the pipeline above,
unchanged.

```powershell
pip install bpy
python blender\nik_blender.py template Nik.blend
python blender\nik_blender.py render Nik.blend script.txt Clips\
```

**Why.** A video model cannot hold a character still from one shot to
the next, cannot reliably be told what to do, and cannot lip sync. A
rigged character does all three by construction: it is the same model
every time, the movement is animated rather than guessed, and mouth
shapes can be driven from the song. That is how the channels this is
meant to compete with are actually made — they are 3D animation, not AI.

### What your .blend must contain

Build to this and the tool drives it.

| | |
| --- | --- |
| One armature | the character's rig. Any name. |
| Actions on it | `idle`, `walk`, `wave`, `clap`, `jump`, `sway`, `point`, `crouch`, `nod`, `spin`. Only `idle` is required — it is what plays for a movement you have not animated. |
| Three cameras | `Cam_Wide`, `Cam_Medium`, `Cam_Close` |

Everything else — the set, the lights, the animals — is yours and is
left alone.

`template` writes a .blend shaped exactly like that, with a stand-in body
made of spheres. It is not a character; it is there so the pipeline can
be run today and so there is something to compare against while you
build the real one. Open it, see what is named what, replace the body.

### How a line becomes a shot

The action comes from the **first clause only** — everything up to the
first comma. A script line is written as *what he does, who else is
there, what the background is doing*, and reading the whole line picks
up the wrong verb: "Close up of the puppy barking, Nik stands nearby,
flowers nod in the breeze" was making the boy nod.

Within that clause the **earliest verb wins**, because that is what the
line is about — "he crouches down and holds out one hand" is a crouch,
not a point.

The rig's own action names count too, so adding a `twirl` action to the
.blend makes a line saying "twirls" use it, with no change here.

The camera comes from how the line opens: `Wide shot of` → `Cam_Wide`,
`Close up of` → `Cam_Close`, anything else → `Cam_Medium`.

### Lip sync

Not built yet, and it is the next thing. [Rhubarb Lip
Sync](https://github.com/DanielSWolf/rhubarb-lip-sync) is MIT licensed
and reads an audio file into a list of mouth shapes with timings; the
rig needs a pose for each shape and the tool sets the keys. That is how
this is done in 3D — the AI face models are trained on real faces and
mangle a stylised one.

## Not built yet

Voice has no backend yet, so that stage stays **Not Started** — there is
no spoken narration, only whatever song you supply. An AI video model can
replace the pan-and-zoom stage by implementing the same `generate_video`,
and a music generator can fill the `music` stage — nothing in the UI
would change either time.
