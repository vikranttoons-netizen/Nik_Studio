from pathlib import Path

from backends.base_backend import (
    BackendDeferred,
    BackendError,
)

from pipeline.status import StageStatus

from render.render_result import RenderResult


class SceneRenderer:
    """
    Renders the stages of one scene through a backend.

    This is the only place that talks to a backend. It records what
    happened on the scene's pipeline so the work can be resumed, retried
    or reported later.
    """

    # Stages that are driven by the scene's own written prompt.
    PROMPT_STAGES = ("image", "video", "voice")

    def __init__(self, episode_folder, backend, prompt_builder=None):

        self.episode_folder = Path(episode_folder)
        self.backend = backend
        self.prompt_builder = prompt_builder

    # ------------------------------------------------------------------
    # Deciding what still needs rendering
    # ------------------------------------------------------------------

    def is_done(self, scene, stage_name):
        """
        A stage counts as done only if it is marked completed AND its file
        is really on disk. Checking the disk is what makes "render only
        the missing assets" trustworthy - a project can be copied,
        half-synced, or have files deleted by hand.
        """

        stage = scene.pipeline[stage_name]

        if not stage.is_completed or not stage.output:
            return False

        return (self.episode_folder / stage.output).exists()

    # ------------------------------------------------------------------

    def build_prompt(self, scene):

        if self.prompt_builder is None:
            return scene.prompt or ""

        return self.prompt_builder.build(scene)

    def build_negative(self, scene):

        if self.prompt_builder is None:
            return ""

        return self.prompt_builder.build_negative(scene)

    def build_references(self, scene):

        if self.prompt_builder is None:
            return []

        return self.prompt_builder.reference_images(scene)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_stage(self, scene, stage_name, force=False, result=None):
        """
        Render one stage of one scene. Returns a RenderResult describing
        just that stage.
        """

        result = result or RenderResult()

        stage = scene.pipeline[stage_name]

        # Already done - skip it.
        if not force and self.is_done(scene, stage_name):

            result.add_skipped(scene.name, stage_name)

            return result

        # This backend has no implementation for this stage.
        if not self.backend.can(stage_name):

            stage.status = StageStatus.NOT_STARTED

            result.add_error(
                scene.name,
                stage_name,
                f"The {self.backend.name} backend cannot render "
                f"'{stage_name}' yet.",
            )

            return result

        method = getattr(self.backend, f"generate_{stage_name}", None)

        if method is None:

            result.add_error(
                scene.name,
                stage_name,
                f"No generator for stage '{stage_name}'.",
            )

            return result

        # A scene with no prompt of its own is a scene the user has not
        # written yet. Caught here rather than in the backend, because the
        # character sheet and style are appended to every prompt and would
        # otherwise make an empty scene look renderable.
        if stage_name in self.PROMPT_STAGES and not (scene.prompt or "").strip():

            stage.fail("No prompt written for this scene.")

            result.add_error(
                scene.name,
                stage_name,
                "No prompt written for this scene.",
            )

            return result

        prompt = self.build_prompt(scene)

        stage.start(backend=self.backend.name)

        try:
            output = method(
                scene,
                prompt,
                self.build_negative(scene),
                self.build_references(scene),
            )

        except BackendDeferred as deferred:

            # Handed off to a cloud GPU. Not finished, not failed.
            stage.status = StageStatus.WAITING
            stage.error = ""

            result.add_waiting(scene.name, stage_name, str(deferred))

            return result

        except BackendError as error:

            stage.fail(error)

            result.add_error(scene.name, stage_name, error)

            return result

        except Exception as error:
            # A backend should raise BackendError, but a bug in one must
            # not take down the whole episode render.
            stage.fail(f"Unexpected error: {error}")

            result.add_error(scene.name, stage_name, error)

            return result

        if not output:

            stage.fail("The backend returned no output file.")

            result.add_error(
                scene.name,
                stage_name,
                "The backend returned no output file.",
            )

            return result

        # Trust nothing: confirm the file is actually there.
        if not (self.episode_folder / output).exists():

            stage.fail(f"Output file was not created: {output}")

            result.add_error(
                scene.name,
                stage_name,
                f"Output file was not created: {output}",
            )

            return result

        stage.complete(output)

        result.record(stage_name, output)

        return result

    # ------------------------------------------------------------------

    def render(self, scene, stages=("image",), force=False):
        """
        Render several stages of one scene, in order.

        Stops at the first failure, because later stages depend on the
        earlier ones - there is no point generating a video from an image
        that does not exist.
        """

        result = RenderResult()

        for stage_name in stages:

            self.render_stage(
                scene,
                stage_name,
                force=force,
                result=result,
            )

            if not result.success:
                break

            # Waiting on the cloud - do not start dependent stages.
            if any(w["stage"] == stage_name for w in result.waiting):
                break

        return result
