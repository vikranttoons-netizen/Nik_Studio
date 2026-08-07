from services.character_manager import CharacterManager

manager = CharacterManager(
    r"D:\NikStudio\app\data\characters.json"
)

print(manager.names())

vikrant = manager.find("vikrant")

print(vikrant.build_prompt())