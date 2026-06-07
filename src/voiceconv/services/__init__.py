"""Application/services layer: job queue, profiles, consent, settings, orchestration. Runs headless.

Public API (imported by app/ and tests):
  job.py          — JobStatus, ConversionRequest, Job
  queue.py        — JobQueue
  runner.py       — QueueRunner
  _repository.py  — JobRepository ABC, JsonFileJobRepository
  _pcm_loader.py  — PcmLoader protocol, StdlibWavLoader
"""

from voiceconv.services._pcm_loader import PcmLoader, StdlibWavLoader
from voiceconv.services._repository import JobRepository, JsonFileJobRepository
from voiceconv.services.job import ConversionRequest, Job, JobStatus
from voiceconv.services.queue import JobQueue
from voiceconv.services.runner import QueueRunner

__all__ = [
    "ConversionRequest",
    "Job",
    "JobQueue",
    "JobRepository",
    "JobStatus",
    "JsonFileJobRepository",
    "PcmLoader",
    "QueueRunner",
    "StdlibWavLoader",
]
