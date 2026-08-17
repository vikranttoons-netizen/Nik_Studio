from pathlib import Path

from backends.backend_manager import BackendManager

from services.character_manager import CharacterManager
from services.episode_loader import EpisodeLoader
from services.prompt_builder import PromptBuilder
from services.scene_loader import SceneLoader
from services.scene_saver import SceneSaver

from core.project import Project

from render.render_result import RenderResult, RenderProgress
from render.scene_renderer import SceneRenderer


class EpisodeRenderer:
    """
    Renders a whole episode. This is what the 🚀 Render Episode button
    calls.

    Two things make it safe to interrupt:

      * every scene is saved to scenes.json as soon as it finishes, so
        closing the app mid render never loses completed work
      * stages that are already done are skipped, so pressing the button
        again picks up exactly where it left off
    """

    def __init__(
        self,
        episode_folder,
        backend=None,
        settings=None,
        cancelled=None,
    ):

        self.episode_folder = Path(episode_folder)

        self.settings = settings if settings is not None else self.load_settings()

        self.backend = backend or BackendManager.from_settings(
            self.episode_folder,
            self.settings,
        )

        # Callable returning True when the user asked to stop.
        self.cancelled = cancelled or (lambda: False)

        self.renderer = SceneRenderer(
            self.episode_folder,
            self.backend,
            self.build_prompt_builder(),
        )

    # ------------------------------------------------------------------
    # Set up
    # ------------------------------------------------------------------

    def load_settings(self):

        try:
            return EpisodeLoader(self.episode_folder).load()
        except (FileNotFoundError, ValueError):
            # An episode without episode.json can still be rendered with
            # defaults.
            return {}

    def build_prompt_builder(self):

        characters = []

        try:
            characters = CharacterManager(
                Project().characters_file
            ).characters
        except (OSError, ValueError):
            # Character sheets are an enhancement, not a requirement.
            characters = []

        return PromptBuilder(self.settings, characters)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_episode(
        self,
        scenes=None,
        stages=("image",),
        force=False,
        on_progress=None,
        save=True,
    ):
        """
        Render `stages` for every scene.

        scenes  - the in-memory scenes from the UI, so unsaved prompt
                  edits are used. Loaded from disk when None.
        force   - re-render even stages that are already complete.
        """

        if scenes is None:
            scenes = SceneLoader(self.episode_folder).load()

        result = RenderResult()

        if not scenes:

            result.message = "This episode has no scenes yet."

            return result

        # Availability is checked once, not once per scene, so the user
        # gets one clear message instead of one per scene.
        if not self.backend.is_available():

            result.success = False
            result.message = (
                f"The {self.backend.name} backend is not ready."
            )

            result.add_error(
                "-",
                stages[0] if stages else "image",
                self.backend.unavailable_reason(),
            )

            return result

        total = len(scenes) * len(stages)
        step = 0

        try:
            for scene in scenes:

                if self.cancelled():

                    result.message = "Render cancelled."

                    return result

                for stage_name in stages:

                    step += 1

                    self._report(
                        on_progress,
                        scene=scene.name,
                        stage=stage_name,
                        status="running",
                        message="rendering",
                        index=step,
                        total=total,
                    )

                    stage_result = self.renderer.render_stage(
                        scene,
                        stage_name,
                        force=force,
                    )

                    result.merge(stage_result)

                    self._report(
                        on_progress,
                        scene=scene.name,
                        stage=stage_name,
                        status=scene.pipeline[stage_name].status.value,
                        message=self._stage_message(
                            scene,
                            stage_name,
                            stage_result,
                        ),
                        index=step,
                        total=total,
                    )

                    # A failed stage stops this scene, not the episode.
                    # One bad prompt should not block the other scenes.
                    if stage_result.errors:
                        break

                # Save after each scene so progress survives a crash.
                if save:
                    SceneSaver(self.episode_folder).save(scenes)

        finally:
            # Always release the GPU / loaded model.
            self.backend.close()

            if save:
                SceneSaver(self.episode_folder).save(scenes)

        result.message = self._episode_message(result)

        return result

    # ------------------------------------------------------------------

    def render_scene(
        self,
        scene,
        scenes=None,
        stages=("image",),
        force=True,
        on_progress=None,
    ):
        """
        Render a single scene. `scenes` is the full list, only needed so
        scenes.json can be written back out complete.
        """

        result = self.render_episode(
            scenes=[scene],
            stages=stages,
            force=force,
            on_progress=on_progress,
            save=False,
        )

        SceneSaver(self.episode_folder).save(
            scenes if scenes is not None else [scene]
        )

        return result

    # ------------------------------------------------------------------
    # Collecting cloud results
    # ------------------------------------------------------------------

    def collect_results(self, scenes, stage_name="image", save=True):
        """
        Pull in finished files from an asynchronous backend (Colab) and
        mark those stages completed.
        """

        result = RenderResult()

        collect = getattr(self.backend, "collect_results", None)

        if collect is None:

            result.message = (
                f"The {self.backend.name} backend has nothing to collect."
            )

            return result

        collected = collect(scenes)

        by_name = {scene.name: scene for scene in scenes}

        for name, output in collected.items():

            scene = by_name.get(name)

            if scene is None:
                continue

            scene.pipeline[stage_name].complete(output)

            result.record(stage_name, output)

        if save and collected:
            SceneSaver(self.episode_folder).save(scenes)

        if collected:
            result.message = f"Imported {len(collected)} new file(s)."
        else:
            result.message = "No new results yet."

        return result

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def _report(self, on_progress, **kwargs):

        if on_progress is None:
            return

        on_progress(RenderProgress(**kwargs))

    def _stage_message(self, scene, stage_name, stage_result):

        if stage_result.errors:
            return stage_result.errors[-1]["error"]

        if stage_result.waiting:
            return "queued for the cloud GPU"

        if stage_result.skipped:
            return "already done, skipped"

        return scene.pipeline[stage_name].output or "done"

    def _episode_message(self, result):

        if result.errors:
            return "Render finished with errors."

        if result.waiting and not result.rendered_count:
            return (
                f"{len(result.waiting)} job(s) sent to "
                f"{self.backend.name}. Run the worker, then press "
                "Import Results."
            )

        if result.waiting:
            return "Render partly finished - some jobs are still running."

        if not result.rendered_count and result.skipped:
            return "Everything was already rendered."

        return "Render complete."
