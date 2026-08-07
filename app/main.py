from core.project import Project
from core.episode_manager import EpisodeManager


def main():

    studio = Project()

    studio.info()

    manager = EpisodeManager(studio.episodes)

    manager.print_episodes()


if __name__ == "__main__":

    main()