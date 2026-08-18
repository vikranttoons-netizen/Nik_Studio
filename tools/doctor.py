"""
Nik Studio — setup check.

Run this when something is not where you expect it:

    python tools\\doctor.py

It reports which project folder Nik Studio is actually using, what it can
see inside it, and what is installed — then names the next thing to do.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "app"))


OK = "[ OK ]"
BAD = "[FAIL]"
WARN = "[WARN]"


def heading(text):
    print()
    print(text)
    print("-" * len(text))


def main():

    problems = []
    advice = []
    finished = []

    # ------------------------------------------------------------------
    heading("Where Nik Studio is looking")

    from core.project import Project

    override = os.environ.get("NIKSTUDIO_ROOT")

    if override:
        print(f"{OK} NIKSTUDIO_ROOT is set")
        print(f"       {override}")
    else:
        print(f"{WARN} NIKSTUDIO_ROOT is not set")
        print("       Using the folder the code lives in.")
        print("       If your episodes are in Google Drive, set it:")
        print('       [Environment]::SetEnvironmentVariable('
              '"NIKSTUDIO_ROOT", "G:\\My Drive\\NikStudio", "User")')
        print("       Then close PowerShell and open a new one.")

    project = Project()

    print(f"\n       project root : {project.root}")
    print(f"       episodes     : {project.episodes}")

    if not project.episodes.exists():
        print(f"\n{BAD} That Episodes folder does not exist.")
        problems.append("The Episodes folder is missing.")
        advice.append(
            f"Create it, or point NIKSTUDIO_ROOT somewhere that has one:\n"
            f"      mkdir \"{project.episodes}\""
        )
        report(problems, advice)
        return

    print(f"{OK} Episodes folder exists")

    # ------------------------------------------------------------------
    heading("Episodes found")

    names = project.episode_names()

    if not names:
        print(f"{BAD} No episode folders inside {project.episodes}")
        problems.append("There are no episodes.")
        advice.append(
            "Copy an episode in, for example:\n"
            f'      xcopy "{PROJECT_ROOT}\\Episodes\\Bath Time Song" '
            f'"{project.episodes}\\Bath Time Song" /E /I'
        )
        report(problems, advice)
        return

    for name in names:
        print(f"{OK} {name}")

    # ------------------------------------------------------------------
    from services.episode_loader import EpisodeLoader
    from services.scene_loader import SceneLoader
    from services.character_manager import CharacterManager
    from services.prompt_builder import PromptBuilder

    characters = CharacterManager(project.characters_file).characters

    for name in names:

        folder = project.episode_path(name)

        heading(f"Episode: {name}")

        config = folder / "episode.json"

        if not config.exists():
            # Rendering still works with defaults, so this is not fatal.
            print(f"{WARN} no episode.json — defaults would be used")
            advice.append(
                f"{name}: has no episode.json, so it cannot choose a "
                "backend or aspect ratio. Copy one from another episode "
                "if you mean to use this folder."
            )
            settings = {}

        else:
            try:
                settings = EpisodeLoader(folder).load()
            except ValueError as error:
                print(f"{BAD} episode.json is not valid JSON: {error}")
                problems.append(f"{name}: episode.json is not valid JSON.")
                advice.append(
                    f"{name}: fix the punctuation in {config} — a missing "
                    "comma or quote will do this."
                )
                continue

        backend = settings.get("backend", "Colab")

        print(f"       backend      : {backend}")
        print(f"       aspect       : {settings.get('aspect', '16:9')}")
        print(f"       model        : {settings.get('model', 'sdxl-turbo')}")

        # --- scenes ---
        scenes = SceneLoader(folder).load()

        if not scenes:
            print(f"{BAD} no scenes (scenes.json missing or empty)")
            problems.append(f"{name}: no scenes.")
            continue

        print(f"{OK} {len(scenes)} scene(s)")

        no_prompt = [s.name for s in scenes if not (s.prompt or "").strip()]

        if no_prompt:
            print(f"{WARN} no prompt written for: {', '.join(no_prompt)}")
            advice.append(
                f"{name}: write a prompt for {', '.join(no_prompt)}, "
                "or those scenes will fail."
            )

        # --- character ---
        character = settings.get("character")

        if character:

            builder = PromptBuilder(settings, characters)

            if builder.find_character(character):
                print(f"{OK} character '{character}' found in characters.json")
            else:
                print(f"{WARN} character '{character}' is NOT in "
                      f"characters.json")
                advice.append(
                    f"{name}: episode.json asks for character "
                    f"'{character}', which does not exist. Prompts will go "
                    "out without the character sheet. Known characters: "
                    + (", ".join(
                        f"{c.id} ({c.name})" for c in characters
                    ) or "none")
                )

        # --- where jobs are exchanged with Colab ---
        #
        # This is the episode folder unless "sync_folder" is set, in which
        # case only jobs and results cross into Google Drive. Reading it
        # from the backend means this cannot disagree with the app.
        jobs_folder = folder / "Jobs"
        results_folder = folder / "Results"

        if str(backend).lower() == "colab":

            from backends.colab_backend import ColabBackend

            colab = ColabBackend(folder, settings)

            jobs_folder = colab.jobs_folder
            results_folder = colab.results_folder

            if settings.get("sync_folder"):
                print(f"{OK} sync folder (shared with Colab)")
                print(f"       {colab.exchange_folder}")

                if not colab.exchange_folder.parent.exists():
                    print(f"{BAD} that folder's parent does not exist")
                    problems.append(
                        f"{name}: sync_folder points somewhere that is not "
                        "there."
                    )
            else:
                print(f"{WARN} no sync_folder set — the whole episode must "
                      "live in Google Drive for Colab to see it")
                advice.append(
                    f"{name}: to keep the project on your local disk, add "
                    'to episode.json:  "sync_folder": '
                    '"G:\\My Drive\\NikStudio\\Exchange"'
                )

        # --- what has been produced ---
        counts = {}

        for label, path, pattern in (
            ("jobs waiting", jobs_folder, "*.json"),
            ("results to import", results_folder, "*.*"),
            ("images", folder / "Images", "*.png"),
            ("clips", folder / "Videos", "*.mp4"),
            ("final videos", folder / "Exports", "*.mp4"),
        ):
            counts[label] = (
                len(list(path.glob(pattern))) if path.exists() else 0
            )

        print()
        for label, count in counts.items():
            print(f"       {label:18}: {count}")

        # --- stage state as the app sees it ---
        done = sum(1 for s in scenes if s.pipeline.image.is_completed)
        waiting = sum(
            1 for s in scenes
            if s.pipeline.image.status.value == "waiting"
        )
        failed = [s for s in scenes if s.pipeline.image.is_failed]

        print()
        print(f"       images done       : {done}/{len(scenes)}")
        print(f"       images waiting    : {waiting}")

        if failed:
            print(f"       images failed     : {len(failed)}")
            for scene in failed:
                print(f"         {scene.name}: {scene.pipeline.image.error}")

        # --- what to do next for this episode ---
        if counts["results to import"]:
            advice.append(
                f"{name}: {counts['results to import']} result(s) are "
                "waiting — press 📥 Import Results in Nik Studio."
            )
        elif waiting:
            advice.append(
                f"{name}: {waiting} job(s) are queued. Run the Colab "
                "notebook, then press 📥 Import Results."
            )
        elif done < len(scenes):
            advice.append(
                f"{name}: press 🚀 RENDER EPISODE to generate the "
                f"{len(scenes) - done} missing image(s)."
            )
        elif not counts["final videos"]:
            advice.append(
                f"{name}: all images are done — press 🚀 RENDER EPISODE "
                "to build the video."
            )
        else:
            # Nothing is outstanding. Say so, and say where the video is,
            # because that is the thing the user actually wants.
            finished.append(name)

            for video in sorted((folder / "Exports").glob("*.mp4")):
                size = video.stat().st_size / (1024 * 1024)
                print()
                print(f"{OK} finished video: {video}")
                print(f"       {size:.1f} MB")

    # ------------------------------------------------------------------
    heading("Installed tools")

    try:
        import PySide6
        print(f"{OK} PySide6 {PySide6.__version__}")
    except ImportError:
        print(f"{BAD} PySide6 is missing")
        problems.append("PySide6 is not installed.")
        advice.append("pip install -r requirements.txt")

    from services.ffmpeg_locator import find_ffmpeg

    ffmpeg = find_ffmpeg()

    if ffmpeg:
        print(f"{OK} ffmpeg")
        print(f"       {ffmpeg}")
    else:
        print(f"{BAD} ffmpeg not found — video stages cannot run")
        problems.append("ffmpeg is missing.")
        advice.append("pip install imageio-ffmpeg")

    try:
        import torch
        print(f"{OK} torch {torch.__version__} "
              f"(CUDA: {torch.cuda.is_available()})")
    except ImportError:
        print(f"{WARN} torch not installed — the Local image backend "
              "cannot run")
        print("       That is fine if you generate on Colab.")

    report(problems, advice, finished)


def report(problems, advice, finished=None):

    heading("Verdict")

    for name in finished or []:
        print(f"{OK} {name} is complete — the video is in its Exports folder.")

    if finished:
        print()

    if problems:
        print("Problems:")
        for item in problems:
            print(f"  - {item}")
        print()

    if advice:
        print("Next step:")
        for item in advice:
            print(f"  - {item}")
    elif not problems:
        print("Everything looks fine.")


if __name__ == "__main__":
    main()
