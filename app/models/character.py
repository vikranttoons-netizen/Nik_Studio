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

    def build_prompt(self):
        """
        Describe the character as ONE subject.

        This used to be a plain comma separated list of the sheet's
        fields: "Nik, cute baby, 10 month old, Indian baby boy, round
        face, ...". An image model reads each of those noun phrases as a
        separate thing to draw, which is how a prompt for one baby ends
        up producing two.

        Writing it as a single phrase - "a 10 month old Indian baby boy
        with a round face, ... wearing a blue romper" - keeps it to one
        subject.

        The style is deliberately left out; it belongs at the front of
        the prompt, not buried at the end. See style_prompt().
        """

        subject = " ".join(
            part for part in (self.age, self.gender) if part
        ) or self.description

        if not subject:
            return ""

        phrase = f"a {subject}" if subject[0].isalnum() else subject

        details = [
            value
            for value in (self.appearance, self.hairstyle)
            if value
        ]

        if details:
            phrase += " with " + ", ".join(details)

        if self.clothes:
            phrase += f", wearing {self.clothes}"

        if self.expression:
            phrase += f", {self.expression}"

        return phrase

    def style_prompt(self):
        """The look, which goes at the front of the prompt."""

        return self.style or ""
