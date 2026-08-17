import re


class PromptBuilder:
    """
    Turns a scene into the final text sent to the image model.

    The scene prompt on its own is not enough to keep a character looking
    the same across an episode, so the character sheet and the episode
    style are appended to every prompt. This is the first step towards
    real character consistency - reference images and LoRAs come later.
    """

    def __init__(self, episode_settings=None, characters=None):

        self.episode_settings = dict(episode_settings or {})

        # {lookup key -> Character}, keyed by both id and name so a
        # project can refer to a character either way.
        self.characters = {}

        for character in characters or []:

            if character.id:
                self.characters[character.id.strip().lower()] = character

            if character.name:
                self.characters[character.name.strip().lower()] = character

    # ------------------------------------------------------------------

    def find_character(self, key):

        if not key:
            return None

        return self.characters.get(str(key).strip().lower())

    # ------------------------------------------------------------------

    def scene_characters(self, scene):
        """
        Which characters appear in this scene: whatever the scene lists,
        falling back to the episode's main character.
        """

        keys = list(scene.characters or [])

        if not keys:
            main = self.episode_settings.get("character")

            if main:
                keys = [main]

        return keys

    # ------------------------------------------------------------------

    def build(self, scene):

        parts = []

        if scene.prompt:
            parts.append(scene.prompt.strip())

        for key in self.scene_characters(scene):

            character = self.find_character(key)

            if character:
                parts.append(character.build_prompt())
            else:
                # Character sheet not found - still name them, so the
                # prompt is never silently missing the main character.
                parts.append(str(key))

        style = self.episode_settings.get("style")

        if style:
            parts.append(style)

        return ", ".join(self._dedupe(parts))

    # ------------------------------------------------------------------

    @staticmethod
    def _dedupe(parts):
        """
        Drop repeated fragments.

        The episode style and a character's style usually overlap ("Pixar
        3D" and "Pixar 3D animation, cinematic lighting"), and repeating
        tokens in a prompt just dilutes the rest of it.
        """

        keep = []
        seen = []

        for part in parts:

            for fragment in str(part).split(","):

                fragment = fragment.strip()

                if not fragment:
                    continue

                key = fragment.lower()

                # Skip a fragment already covered by one we kept, so
                # "Pixar 3D" is dropped when "Pixar 3D animation" is
                # already in the prompt.
                if any(PromptBuilder._covers(other, key) for other in seen):
                    continue

                seen.append(key)
                keep.append(fragment)

        return keep

    @staticmethod
    def _covers(haystack, needle):
        """True when `needle` appears inside `haystack` as whole words."""

        if needle == haystack:
            return True

        return re.search(
            rf"\b{re.escape(needle)}\b",
            haystack,
        ) is not None
