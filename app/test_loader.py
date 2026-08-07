from services.episode_loader import EpisodeLoader


loader = EpisodeLoader(r"D:\NikStudio\Episodes\Bath Time Song")

episode = loader.load()

print("=" * 40)

for key, value in episode.items():
    print(f"{key:12} : {value}")