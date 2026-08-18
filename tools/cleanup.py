"""
Nik Studio — free up disk space.

    python tools\\cleanup.py            show what could go, delete nothing
    python tools\\cleanup.py --delete   actually delete it

Only regenerated work is ever offered: the scene clips, the finished
video, exported zips, and job files that have already been answered.

Your prompts, your images and your character references are never
touched. Images are the expensive part - they cost GPU time - so they
stay. Clips and the final video are rebuilt from them in seconds by
pressing 🚀 RENDER EPISODE.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "app"))


# What may be deleted, and why it is safe.
DISPOSABLE = (
    ("Videos", "*.mp4", "scene clips, rebuilt from the images"),
    ("Exports", "*.mp4", "the finished video, rebuilt from the clips"),
    ("Exports", "clips.txt", "leftover list file"),
    (".", "Episode.zip", "export archive, rebuilt by Export"),
)


def human(size):

    for unit in ("B", "KB", "MB", "GB"):

        if size < 1024:
            return f"{size:.0f}{unit}"

        size /= 1024

    return f"{size:.1f}TB"


def find_disposable(episode):
    """Files that can go, as (path, size, reason)."""

    found = []

    for folder, pattern, reason in DISPOSABLE:

        directory = episode if folder == "." else episode / folder

        if not directory.exists():
            continue

        for path in sorted(directory.glob(pattern)):

            if path.is_file():
                found.append((path, path.stat().st_size, reason))

    return found


def find_stale_jobs(episode, settings):
    """
    Job files whose image already came back.

    Normally the app retires these on import. One left behind means Colab
    would generate it again for nothing.
    """

    from backends.colab_backend import ColabBackend

    backend = ColabBackend(episode, settings)

    jobs = backend.jobs_folder

    if not jobs.exists():
        return []

    stale = []

    for job_file in sorted(jobs.glob("*.json")):

        image = episode / "Images" / f"{job_file.stem}.png"

        if image.exists() and image.stat().st_size > 0:
            stale.append(
                (job_file, job_file.stat().st_size, "already generated")
            )

    return stale


def keep_summary(episode):
    """What is being kept, so it is obvious nothing valuable is at risk."""

    kept = []

    for folder, pattern, label in (
        ("Images", "*.png", "images"),
        ("Audio", "*", "audio"),
    ):
        directory = episode / folder

        if not directory.exists():
            continue

        files = [p for p in directory.glob(pattern) if p.is_file()]

        if files:
            total = sum(p.stat().st_size for p in files)
            kept.append(f"{len(files)} {label} ({human(total)})")

    return kept


def main():

    delete = "--delete" in sys.argv

    from core.project import Project
    from services.episode_loader import EpisodeLoader

    project = Project()

    print(f"Project: {project.root}\n")

    if not project.episodes.exists():
        print("No Episodes folder.")
        return

    grand_total = 0
    everything = []

    for name in project.episode_names():

        episode = project.episode_path(name)

        try:
            settings = EpisodeLoader(episode).load()
        except (FileNotFoundError, ValueError):
            settings = {}

        items = find_disposable(episode) + find_stale_jobs(episode, settings)

        print(f"{name}")

        kept = keep_summary(episode)

        if kept:
            print(f"   keeping : {', '.join(kept)}")

        if not items:
            print("   nothing to clean up\n")
            continue

        total = sum(size for _, size, _ in items)
        grand_total += total

        by_reason = {}

        for path, size, reason in items:
            entry = by_reason.setdefault(reason, [0, 0])
            entry[0] += 1
            entry[1] += size

        for reason, (count, size) in by_reason.items():
            print(f"   {count:3} x {reason:45} {human(size):>8}")

        print(f"   {'':3}   {'':45} {human(total):>8}\n")

        everything.extend(items)

    if not everything:
        print("Nothing to clean up.")
        return

    print(f"Total that could be freed: {human(grand_total)}")

    if not delete:
        print("\nNothing was deleted. To delete it:")
        print("    python tools\\cleanup.py --delete")
        return

    removed = 0

    for path, size, _ in everything:
        try:
            path.unlink()
            removed += size
        except OSError as error:
            print(f"could not delete {path}: {error}")

    print(f"\nFreed {human(removed)}.")
    print("Press 🚀 RENDER EPISODE to rebuild the video when you need it.")


if __name__ == "__main__":
    main()
