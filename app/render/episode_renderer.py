from pathlib import Path

from backends.backend_manager import BackendManager

from services.audio_track import find_track, duration, fit_scene_durations
from services.character_manager import CharacterManager
from services.episode_loader import EpisodeLoader
from services.prompt_builder import PromptBuilder
from services.scene_loader import SceneLoader
from services.scene_saver import SceneSaver

from core.project import Project

from render.episode_composer import EpisodeComposer, ComposeError
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

        # A single backend can be forced in (used by the tests); normally
        # each stage gets the backend configured for it.
        self.forced_backend = backend

        self.backend = backend or BackendManager.from_settings(
            self.episode_folder,
            self.settings,
        )

        # Callable returning True when the user asked to stop.
        self.cancelled = cancelled or (lambda: False)

        self.prompt_builder = self.build_prompt_builder()

        self.renderer = SceneRenderer(
            self.episode_folder,
            self.backend,
            self.prompt_builder,
        )

        # Backends already built, so a model is loaded once per render and
        # not once per scene.
        self._backends = {}

    # ------------------------------------------------------------------

    def backend_for(self, stage):
        """The backend that renders `stage`, built once and reused."""

        if self.forced_backend is not None:
            return self.forced_backend

        if stage not in self._backends:

            self._backends[stage] = BackendManager.for_stage(
                stage,
                self.episode_folder,
                self.settings,
            )

        return self._backends[stage]

    def fit_to_song(self, scenes):
        """
        Make the pictures last exactly as long as the song.

        Without this a three scene episode is 12 seconds whatever the
        music does, and the video ends while the song is still going. The
        computed length is written into the backend's settings, so the
        video stage picks it up like any other duration.

        Scenes with their own "duration" in metadata keep it, and turning
        "fit_to_music": false off in episode.json disables this entirely.
        """

        if not scenes:
            return None

        if self.settings.get("fit_to_music") is False:
            return None

        song = find_track(self.episode_folder, self.settings)

        if song is None:
            return None

        seconds = duration(song, self.settings.get("ffmpeg"))

        if not seconds:
            return None

        shares = fit_scene_durations(scenes, seconds)

        if not shares:
            return None

        # Everything that has no per-scene override gets the same share,
        # which is what scene_duration means to the video backend.
        flexible = [
            value for name, value in shares.items()
            if scenes and not self._has_own_duration(scenes, name)
        ]

        if flexible:
            self.settings["scene_duration"] = flexible[0]

            # The backend for the video stage may already exist with the
            # old settings, so rebuild it.
            self._backends.pop("video", None)

        return seconds

    @staticmethod
    def _has_own_duration(scenes, name):

        for scene in scenes:

            if scene.name != name:
                continue

            value = scene.metadata.get("duration")

            try:
                return value is not None and float(value) > 0
            except (ValueError, TypeError):
                return False

        return False

    # ------------------------------------------------------------------

    def renderer_for(self, stage):
        """A SceneRenderer wired to the right backend for this stage."""

        backend = self.backend_for(stage)

        if backend is self.renderer.backend:
            return self.renderer

        return SceneRenderer(
            self.episode_folder,
            backend,
            self.prompt_builder,
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

        project = Project()

        return PromptBuilder(self.settings, characters, project.root)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_episode(
        self,
        scenes=None,
        stages=("image", "video"),
        force=False,
        on_progress=None,
        save=True,
        compose=True,
    ):
        """
        Render `stages` for every scene, then join the clips into the
        final episode video.

        scenes  - the in-memory scenes from the UI, so unsaved prompt
                  edits are used. Loaded from disk when None.
        force   - re-render even stages that are already complete.
        compose - build the final MP4 once the scenes are done.
        """

        if scenes is None:
            scenes = SceneLoader(self.episode_folder).load()

        result = RenderResult()

        if not scenes:

            result.message = "This episode has no scenes yet."

            return result

        # Availability is checked once per stage, not once per scene, so
        # the user gets one clear message instead of one per scene.
        for stage_name in stages:

            backend = self.backend_for(stage_name)

            if backend.is_available():
                continue

            result.success = False
            result.message = f"The {backend.name} backend is not ready."

            result.add_error(
                "-",
                stage_name,
                backend.unavailable_reason(),
            )

            return result

        if "video" in stages:

            song_seconds = self.fit_to_song(scenes)

            if song_seconds:
                self._report(
                    on_progress,
                    stage="video",
                    status="running",
                    message=(
                        f"fitting {len(scenes)} scene(s) to a "
                        f"{song_seconds:.0f}s song"
                    ),
                )

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

                    stage_result = self.renderer_for(stage_name).render_stage(
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

                    # Waiting on a cloud GPU is not a failure, but the
                    # later stages need this one's file. Stop this scene
                    # here and pick it up after Import Results, rather
                    # than reporting "no image yet" as an error.
                    if stage_result.waiting:
                        break

                # Save after each scene so progress survives a crash.
                if save:
                    SceneSaver(self.episode_folder).save(scenes)

        finally:
            # Always release the GPU / loaded models.
            self.close_backends()

            if save:
                SceneSaver(self.episode_folder).save(scenes)

        # Join the clips into one playable episode.
        #
        # Skipped when anything is still waiting on a cloud GPU: those
        # scenes have no clip yet, so composing would fail and report a
        # problem when the truth is simply "not finished yet".
        if (
            compose
            and "video" in stages
            and not result.errors
            and not result.waiting
        ):

            self._report(
                on_progress,
                stage="final",
                status="running",
                message="joining the clips",
                index=total,
                total=total,
            )

            self.compose_final(scenes, result)

        result.message = self._episode_message(result)

        return result

    # ------------------------------------------------------------------

    def close_backends(self):

        for backend in list(self._backends.values()) + [self.backend]:
            try:
                backend.close()
            except Exception:
                # Releasing a model must never break the render result.
                pass

    # ------------------------------------------------------------------

    def compose_final(self, scenes, result=None):
        """Stitch the scene clips into Exports/<Episode>.mp4."""

        result = result or RenderResult()

        composer = EpisodeComposer(self.episode_folder, self.settings)

        try:
            result.final_video = composer.compose(scenes)

        except ComposeError as error:
            result.add_error("-", "final", error)

        return result

    # ------------------------------------------------------------------

    def render_scene(
        self,
        scene,
        scenes=None,
        stages=("image", "video"),
        force=True,
        on_progress=None,
    ):
        """
        Render a single scene. `scenes` is the full list, only needed so
        scenes.json can be written back out complete.

        The final video is not rebuilt here - one scene is usually being
        re-rendered to check it, and re-joining the whole episode each
        time would be slow. Press Render Episode for the final cut.
        """

        result = self.render_episode(
            scenes=[scene],
            stages=stages,
            force=force,
            on_progress=on_progress,
            save=False,
            compose=False,
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

        if result.final_video:
            return f"🎬 Episode ready : {result.final_video}"

        if not result.rendered_count and result.skipped:
            return "Everything was already rendered."

        return "Render complete."
