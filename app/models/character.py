from dataclasses import dataclass, field


@dataclass
class Character:
    """
    A reusable character definition.

    The whole point of this class is build_prompt() : it turns the
    character sheet into a consistent block of text that gets injected
    into every scene prompt, so the same character looks the same in
    every generated image.
    """

    id: str
    name: str

    description: str = ""
    age: str = ""
    gender: str = ""
    appearance: str = ""
    clothes: str = ""
    hairstyle: str = ""
    expression: str = ""
    style: str = ""

    reference_image: str = ""
    voice: str = ""
    lora: str = ""

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    # Every field that lives in characters.json, in prompt order.
    FIELDS = (
        "id",
        "name",
        "description",
        "age",
        "gender",
        "appearance",
        "clothes",
        "hairstyle",
        "expression",
        "style",
        "reference_image",
        "voice",
        "lora",
    )

    @classmethod
    def from_dict(cls, data):

        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            age=data.get("age", ""),
            gender=data.get("gender", ""),
            appearance=data.get("appearance", ""),
            clothes=data.get("clothes", ""),
            hairstyle=data.get("hairstyle", ""),
            expression=data.get("expression", ""),
            style=data.get("style", ""),
            reference_image=data.get("reference_image", ""),
            voice=data.get("voice", ""),
            lora=data.get("lora", ""),
        )

    def to_dict(self):

        return {
            name: getattr(self, name)
            for name in self.FIELDS
        }

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    # Parts of the character sheet that describe how it looks.
    PROMPT_FIELDS = (
        "description",
        "age",
        "gender",
        "appearance",
        "hairstyle",
        "clothes",
        "expression",
        "style",
    )

    def build_prompt(self):
        """
        Return the character description used inside image prompts.
        Empty fields are skipped so the prompt never contains blanks.
        """

        parts = [self.name]

        for name in self.PROMPT_FIELDS:

            value = getattr(self, name, "")

            if value:
                parts.append(value)

        return ", ".join(parts)
