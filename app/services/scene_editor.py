import re

from models.scene import Scene


class SceneEditor:
    """
    Adding, removing and reordering the scenes of an episode.

    Order matters: the scene list is the order the clips are stitched
    together in the final video, so moving a scene up or down changes the
    edit.

    Every method works on the list in memory and returns the row that
    should be selected afterwards. Saving stays the caller's job, so a
    mistake can be undone by simply not saving.
    """

    NAME_PATTERN = re.compile(r"^Scene(\d+)$")

    def __init__(self, scenes):
        self.scenes = scenes

    # ------------------------------------------------------------------
    # Naming
    # ------------------------------------------------------------------

    def next_name(self):
        """
        The next free SceneNN name.

        Names are the key for output files (Images/Scene03.png), so a new
        scene must never reuse the name of an existing one - that would
        make it look already rendered.
        """

        used = set()

        for scene in self.scenes:

            match = self.NAME_PATTERN.match(scene.name or "")

            if match:
                used.add(int(match.group(1)))

        number = 1

        while number in used:
            number += 1

        return f"Scene{number:02d}"

    def next_id(self):

        numbers = [
            scene.id
            for scene in self.scenes
            if isinstance(scene.id, int)
        ]

        return max(numbers, default=0) + 1

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def add(self, after=None, prompt=""):
        """
        Insert a new empty scene. `after` is the row to insert below;
        None appends to the end.
        """

        scene = Scene(
            id=self.next_id(),
            name=self.next_name(),
            prompt=prompt,
        )

        if after is None or after < 0 or after >= len(self.scenes):
            self.scenes.append(scene)
            return len(self.scenes) - 1

        position = after + 1

        self.scenes.insert(position, scene)

        return position

    # ------------------------------------------------------------------

    def delete(self, row):
        """
        Remove a scene from the episode.

        Any images or clips it already produced are deliberately left on
        disk. Deleting generated work as a side effect of a list edit
        would be far too easy to do by accident.
        """

        if row < 0 or row >= len(self.scenes):
            return row

        self.scenes.pop(row)

        if not self.scenes:
            return -1

        # Select the scene that took its place, or the new last one.
        return min(row, len(self.scenes) - 1)

    # ------------------------------------------------------------------

    def move(self, row, offset):
        """Move a scene up (offset -1) or down (offset +1)."""

        target = row + offset

        if row < 0 or row >= len(self.scenes):
            return row

        if target < 0 or target >= len(self.scenes):
            return row

        self.scenes[row], self.scenes[target] = (
            self.scenes[target],
            self.scenes[row],
        )

        return target

    def move_up(self, row):
        return self.move(row, -1)

    def move_down(self, row):
        return self.move(row, 1)

    # ------------------------------------------------------------------

    def renumber_ids(self):
        """
        Make the ids match the running order again.

        Names are left alone on purpose - they are tied to the files
        already generated for each scene.
        """

        for index, scene in enumerate(self.scenes, start=1):
            scene.id = index
