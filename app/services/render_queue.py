from dataclasses import dataclass
from enum import Enum


class JobStatus(Enum):
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RenderJob:
    scene_name: str
    job_type: str
    status: JobStatus = JobStatus.WAITING


class RenderQueue:

    def __init__(self):
        self.jobs = []

    # ----------------------------

    def add_job(self, scene_name, job_type="image"):

        job = RenderJob(
            scene_name=scene_name,
            job_type=job_type
        )

        self.jobs.append(job)

        print(f"➕ Added {scene_name}")

    # ----------------------------

    def next_job(self):

        for job in self.jobs:

            if job.status == JobStatus.WAITING:

                job.status = JobStatus.RUNNING

                return job

        return None

    # ----------------------------

    def complete(self, job):

        job.status = JobStatus.COMPLETED

        print(f"✅ {job.scene_name} Completed")

    # ----------------------------

    def fail(self, job):

        job.status = JobStatus.FAILED

        print(f"❌ {job.scene_name} Failed")

    # ----------------------------

    def waiting_jobs(self):

        return [
            j for j in self.jobs
            if j.status == JobStatus.WAITING
        ]

    # ----------------------------

    def running_jobs(self):

        return [
            j for j in self.jobs
            if j.status == JobStatus.RUNNING
        ]

    # ----------------------------

    def completed_jobs(self):

        return [
            j for j in self.jobs
            if j.status == JobStatus.COMPLETED
        ]