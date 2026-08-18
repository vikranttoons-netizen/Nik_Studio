import re


class PromptBuilder:
    """
    Turns a scene into the final text sent to the image model.

    The scene prompt on its own is not enough to keep a character looking
    the same across an episode, so the character sheet and the episode
    style are appended to every prompt. This is the first step towards
    real character consistency - reference images and LoRAs come later.
    """

    # Used when episode.json does not set its own negative_prompt.
    # Aimed at the two failures this pipeline actually hits: duplicate
    # subjects, and a photographic look where animation was asked for.
    DEFAULT_NEGATIVE = (
        "two babies, twins, duplicate person, extra person, crowd, "
        "extra limbs, extra fingers, deformed hands, disfigured, "
        "photo, photorealistic, realistic skin pores, "
        "blurry, low quality, text, watermark, signature"
    )

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
        """
        Assemble the prompt, style first.

        Order matters. Image models weight the opening of a prompt most
        heavily, so a style tacked on the end - which is what this used to
        do - gets largely ignored and the result comes out photographic.
        Leading with it is what makes the style stick.

            <style>, <what happens in the scene>, <who is in it>
        """

        styles = []
        subjects = []

        for key in self.scene_characters(scene):

            character = self.find_character(key)

            if character is None:
                # No sheet for this name; still mention them.
                subjects.append(str(key))
                continue

            if character.style_prompt():
                styles.append(character.style_prompt())

            if character.build_prompt():
                subjects.append(character.build_prompt())

        episode_style = self.episode_settings.get("style")

        if episode_style:
            styles.append(episode_style)

        parts = []

        parts.extend(styles)

        if scene.prompt:
            parts.append(scene.prompt.strip())

        parts.extend(subjects)

        return ", ".join(self._dedupe(parts))

    # ------------------------------------------------------------------

    def build_negative(self, scene=None):
        """
        What the image must not contain.

        A negative prompt is the reliable way to stop the two most common
        failures here: a second child appearing, and a photographic look
        when the episode asked for animation.

        Note it only has an effect when guidance is above 1. Distilled
        models such as SDXL-Turbo run at guidance 0 and ignore it, which
        is a reason to use the full SDXL model for stylised work.
        """

        negative = self.episode_settings.get("negative_prompt")

        if negative is not None:
            return str(negative)

        return self.DEFAULT_NEGATIVE

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
