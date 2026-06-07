"""Headless unit tests for QueueViewModel."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication

from voiceconv.app._app_state import AppState
from voiceconv.app._queue_bridge import QueueBridge
from voiceconv.app.view_models.queue_vm import QueueViewModel
from voiceconv.inference.engine import ConvertParams, ProfileArtifacts
from voiceconv.services.job import Job, JobStatus, ConversionRequest
from voiceconv.storage.profile import (
    ConsentRecord,
    JsonFileProfileRepository,
    VoiceProfile,
)
from voiceconv.storage.settings import AppSettings, SettingsStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_artifacts() -> ProfileArtifacts:
    return ProfileArtifacts("mock", "0.1", b"emb", {})


def _make_profile(name: str = "Alice") -> VoiceProfile:
    consent = ConsentRecord.create()
    return VoiceProfile.create(name, _make_artifacts(), consent)


def _make_state(tmp_path: Path, profile: VoiceProfile | None = None) -> AppState:
    repo = JsonFileProfileRepository(tmp_path / "profiles")
    if profile:
        repo.save(profile)

    store = SettingsStore(tmp_path / "settings.json")
    settings = AppSettings()
    engine = MagicMock()
    runner = MagicMock()
    runner.list_jobs.return_value = []
    runner.get_job.return_value = None

    return AppState(
        converter=MagicMock(),
        profile_repo=repo,
        settings_store=store,
        settings=settings,
        engine=engine,
        queue=MagicMock(),
        runner=runner,
        engine_lock=threading.Lock(),
    )


def _make_vm(state: AppState, bridge: QueueBridge | None = None) -> QueueViewModel:
    return QueueViewModel(state, bridge or QueueBridge())


def _pump() -> None:
    for _ in range(10):
        QCoreApplication.processEvents()


# ---------------------------------------------------------------------------
# add_files
# ---------------------------------------------------------------------------


def test_add_files_no_profile_emits_error(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = _make_vm(state)
    # no profile selected
    errors: list[str] = []
    vm.error.connect(errors.append)
    vm.add_files([str(tmp_path / "a.wav")])
    assert errors, "expected error when no profile is selected"
    assert "profile" in errors[0].lower()


def test_add_files_submits_one_request_per_file(qapp, tmp_path):
    profile = _make_profile()
    state = _make_state(tmp_path, profile)
    vm = _make_vm(state)
    vm.refresh_profiles()
    vm.set_selected_profile_id(profile.profile_id)

    paths = [str(tmp_path / f"{i}.wav") for i in range(3)]
    vm.add_files(paths)

    assert state.runner.submit.call_count == 3


def test_add_files_uses_loaded_artifacts(qapp, tmp_path):
    profile = _make_profile()
    state = _make_state(tmp_path, profile)
    vm = _make_vm(state)
    vm.refresh_profiles()
    vm.set_selected_profile_id(profile.profile_id)

    vm.add_files([str(tmp_path / "src.wav")])

    submitted: ConversionRequest = state.runner.submit.call_args[0][0]
    assert submitted.profile == profile.artifacts


def test_add_files_suggests_output_path_contains_converted(qapp, tmp_path):
    profile = _make_profile()
    state = _make_state(tmp_path, profile)
    vm = _make_vm(state)
    vm.refresh_profiles()
    vm.set_selected_profile_id(profile.profile_id)

    vm.add_files([str(tmp_path / "speech.wav")])

    submitted: ConversionRequest = state.runner.submit.call_args[0][0]
    assert "speech_converted" in submitted.output_path


def test_add_files_emits_jobs_reset(qapp, tmp_path):
    profile = _make_profile()
    state = _make_state(tmp_path, profile)
    vm = _make_vm(state)
    vm.refresh_profiles()
    vm.set_selected_profile_id(profile.profile_id)

    resets: list[None] = []
    vm.jobs_reset.connect(lambda: resets.append(None))

    vm.add_files([str(tmp_path / "x.wav")])
    assert resets


# ---------------------------------------------------------------------------
# cancel / retry
# ---------------------------------------------------------------------------


def test_cancel_delegates_to_runner(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = _make_vm(state)
    vm.cancel_job("abc123")
    state.runner.cancel.assert_called_once_with("abc123")


def test_retry_delegates_to_runner(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = _make_vm(state)
    vm.retry_job("abc123")
    state.runner.retry.assert_called_once_with("abc123")


def test_retry_emits_error_on_value_error(qapp, tmp_path):
    state = _make_state(tmp_path)
    state.runner.retry.side_effect = ValueError("not retryable")
    vm = _make_vm(state)

    errors: list[str] = []
    vm.error.connect(errors.append)
    vm.retry_job("bad_id")

    assert errors


# ---------------------------------------------------------------------------
# clear_done
# ---------------------------------------------------------------------------


def _make_job(status: JobStatus, job_id: str = "j1") -> Job:
    arts = _make_artifacts()
    request = ConversionRequest("src.wav", arts, ConvertParams(target_sample_rate=22050), "out.wav")
    job = Job(job_id=job_id, request=request, status=status)
    return job


def test_clear_done_hides_done_jobs(qapp, tmp_path):
    done_job = _make_job(JobStatus.DONE, "done1")
    state = _make_state(tmp_path)
    state.runner.list_jobs.return_value = [done_job]

    vm = _make_vm(state)
    vm.clear_done()

    assert done_job.job_id not in [j.job_id for j in vm.list_jobs()]


def test_clear_done_preserves_non_done_jobs(qapp, tmp_path):
    queued = _make_job(JobStatus.QUEUED, "q1")
    failed = _make_job(JobStatus.FAILED, "f1")
    done = _make_job(JobStatus.DONE, "d1")
    state = _make_state(tmp_path)
    state.runner.list_jobs.return_value = [queued, failed, done]

    vm = _make_vm(state)
    vm.clear_done()

    remaining_ids = {j.job_id for j in vm.list_jobs()}
    assert "q1" in remaining_ids
    assert "f1" in remaining_ids
    assert "d1" not in remaining_ids


def test_clear_done_emits_jobs_reset(qapp, tmp_path):
    state = _make_state(tmp_path)
    state.runner.list_jobs.return_value = [_make_job(JobStatus.DONE)]
    vm = _make_vm(state)

    resets: list[None] = []
    vm.jobs_reset.connect(lambda: resets.append(None))
    vm.clear_done()

    assert resets


# ---------------------------------------------------------------------------
# Bridge signal forwarding
# ---------------------------------------------------------------------------


def test_bridge_status_signal_forwarded_to_vm(qapp, tmp_path):
    bridge = QueueBridge()
    state = _make_state(tmp_path)
    vm = _make_vm(state, bridge)

    received: list[tuple] = []
    vm.job_status_changed.connect(lambda jid, s: received.append((jid, s)))

    bridge.status_changed.emit("job1", JobStatus.RUNNING)
    _pump()

    assert ("job1", JobStatus.RUNNING) in received


def test_bridge_progress_signal_forwarded_to_vm(qapp, tmp_path):
    bridge = QueueBridge()
    state = _make_state(tmp_path)
    vm = _make_vm(state, bridge)

    received: list[tuple] = []
    vm.job_progress_changed.connect(lambda jid, f: received.append((jid, f)))

    bridge.progress_changed.emit("job2", 0.5)
    _pump()

    assert ("job2", 0.5) in received
