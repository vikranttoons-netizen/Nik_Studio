from pathlib import Path


class EpisodeManager:

    def __init__(self, episode_folder):

        self.episode_folder = Path(episode_folder)

    def get_episodes(self):

        episodes = []

        if not self.episode_folder.exists():
            return episodes

        for folder in self.episode_folder.iterdir():

            if folder.is_dir():
                episodes.append(folder.name)

        return sorted(episodes)

    def print_episodes(self):

        print("\nEpisodes Found\n")

        for ep in self.get_episodes():
            print("•", ep)