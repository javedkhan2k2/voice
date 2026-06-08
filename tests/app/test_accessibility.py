"""Accessibility (M6) — screen-reader label coverage for all Phase 1/2 views.

These assert that interactive widgets expose a non-empty ``accessibleName`` so
screen readers announce something meaningful, and that Queue job status is
conveyed by text (never colour alone).  Full keyboard / screen-reader
walkthroughs remain a manual audit step.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from voiceconv.app._app_state import AppState
from voiceconv.app.views.convert_view import ConvertView
from voiceconv.app.views.preview_view import PreviewView
from voiceconv.app.views.profile_library_view import ProfileLibraryView
from voiceconv.app.views.profile_view import ProfileView
from voiceconv.app.views.queue_view import QueueView
from voiceconv.app.views.settings_view import SettingsView
from voiceconv.app.view_models.settings_vm import SettingsViewModel
from voiceconv.inference.engine import ConvertParams, ProfileArtifacts
from voiceconv.services.job import ConversionRequest, Job, JobStatus
from voiceconv.storage.settings import AppSettings, SettingsStore


def _names(*widgets) -> list[str]:
    return [w.accessibleName() for w in widgets]


# ---------------------------------------------------------------------------
# Create Profile
# ---------------------------------------------------------------------------


def test_profile_view_labels(qapp):
    view = ProfileView(MagicMock())
    for name in _names(
        view._ref_edit, view._name_edit, view._consent_cb,
        view._create_btn, view._status_label,
    ):
        assert name


# ---------------------------------------------------------------------------
# Convert
# ---------------------------------------------------------------------------


def test_convert_view_labels(qapp):
    view = ConvertView(MagicMock(), MagicMock())
    for name in _names(
        view._src_edit, view._profile_combo, view._out_edit,
        view._progress_bar, view._convert_btn, view._cancel_btn,
        view._status_label,
    ):
        assert name


def test_convert_buttons_have_distinct_mnemonics(qapp):
    view = ConvertView(MagicMock(), MagicMock())
    # '&C' (Convert) and 'Ca&ncel' must not collide on the same accelerator.
    assert "&" in view._convert_btn.text()
    assert "&" in view._cancel_btn.text()
    conv_key = view._convert_btn.text().split("&")[1][0].lower()
    cancel_key = view._cancel_btn.text().split("&")[1][0].lower()
    assert conv_key != cancel_key


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def test_preview_view_labels(qapp):
    view = PreviewView(MagicMock())
    for name in _names(
        view._play_src_btn, view._play_out_btn, view._export_btn,
        view._info_label,
    ):
        assert name


# ---------------------------------------------------------------------------
# Profile Library
# ---------------------------------------------------------------------------


def test_profile_library_labels(qapp):
    view = ProfileLibraryView(MagicMock())
    for name in _names(
        view._list, view._name_label, view._created_label,
        view._statement_label, view._affirmed_label, view._affirmed_by_label,
        view._rename_btn, view._delete_btn,
    ):
        assert name


# ---------------------------------------------------------------------------
# Queue (static toolbar + per-row widgets)
# ---------------------------------------------------------------------------


def _make_job(path: str, status: JobStatus) -> Job:
    arts = ProfileArtifacts("mock", "0.1", b"e", {})
    req = ConversionRequest(
        path, arts, ConvertParams(target_sample_rate=22050), "out.wav"
    )
    return Job(job_id="j1", request=req, status=status)


def test_queue_toolbar_labels(qapp):
    view = QueueView(MagicMock())
    for name in _names(
        view._profile_combo, view._add_btn, view._clear_btn,
        view._table, view._status_label,
    ):
        assert name


@pytest.mark.parametrize(
    "status",
    [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.DONE, JobStatus.FAILED],
)
def test_queue_action_button_names_include_filename(qapp, status):
    view = QueueView(MagicMock())
    job = _make_job(r"C:\audio\sample_clip.wav", status)
    btn = view._make_action_btn(job)
    if btn is not None:  # DONE/FAILED/QUEUED/RUNNING all produce a button
        assert "sample_clip.wav" in btn.accessibleName()


def test_queue_status_item_conveyed_by_text(qapp):
    """Status must not be colour-only — the cell text carries the meaning."""
    view = QueueView(MagicMock())
    for status in JobStatus:
        item = view._make_status_item(status)
        assert item.text() == status.value.upper()
        assert item.text()  # non-empty regardless of foreground colour


# ---------------------------------------------------------------------------
# Settings (real VM so _load_current populates from AppSettings)
# ---------------------------------------------------------------------------


def test_settings_view_labels(qapp, tmp_path: Path):
    store = SettingsStore(tmp_path / "settings.json")
    runner = MagicMock()
    runner.list_jobs.return_value = []
    state = AppState(
        converter=MagicMock(),
        profile_repo=MagicMock(),
        settings_store=store,
        settings=AppSettings(),
        engine=MagicMock(),
        queue=MagicMock(),
        runner=runner,
        engine_lock=threading.Lock(),
    )
    view = SettingsView(SettingsViewModel(state))
    for name in _names(
        view._device_combo, view._engine_combo, view._format_combo,
        view._loudness_cb, view._dir_edit, view._log_level_combo,
        view._export_btn,
    ):
        assert name
