"""Top-level application window."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from voiceconv.app._app_state import AppState
from voiceconv.app._queue_bridge import QueueBridge
from voiceconv.app.view_models.convert_vm import ConvertViewModel
from voiceconv.app.view_models.first_run_vm import FirstRunViewModel
from voiceconv.app.view_models.preview_vm import PreviewViewModel
from voiceconv.app.view_models.profile_vm import ProfileViewModel
from voiceconv.app.view_models.queue_vm import QueueViewModel
from voiceconv.app.views.convert_view import ConvertView
from voiceconv.app.views.first_run_dialog import FirstRunDialog
from voiceconv.app.views.preview_view import PreviewView
from voiceconv.app.views.profile_view import ProfileView
from voiceconv.app.views.queue_view import QueueView
from voiceconv.platform_support.device import detect_device

_TAB_PROFILE = 0
_TAB_CONVERT = 1
_TAB_PREVIEW = 2
_TAB_QUEUE   = 3


class MainWindow(QMainWindow):
    def __init__(self, state: AppState, bridge: QueueBridge) -> None:
        super().__init__()
        self._state = state
        self.setWindowTitle("VoiceBuilder")
        self.resize(800, 540)

        self._first_run_vm = FirstRunViewModel(state.settings, state.settings_store)
        self._profile_vm = ProfileViewModel(state)
        self._convert_vm = ConvertViewModel(state)
        self._preview_vm = PreviewViewModel()
        self._queue_vm = QueueViewModel(state, bridge)

        self._tabs = QTabWidget()
        self._profile_view = ProfileView(self._profile_vm)
        self._convert_view = ConvertView(state, self._convert_vm)
        self._preview_view = PreviewView(self._preview_vm)
        self._queue_view = QueueView(self._queue_vm)

        self._tabs.addTab(self._profile_view, "Create Profile")
        self._tabs.addTab(self._convert_view, "Convert")
        self._tabs.addTab(self._preview_view, "Preview && Export")
        self._tabs.addTab(self._queue_view, "Queue")
        self.setCentralWidget(self._tabs)

        # Status bar — device info shown once at startup
        info = detect_device()
        if info["device"] == "cuda":
            status_text = f"GPU: {info['note']}  ({info['vram_mb']} MB VRAM)"
        else:
            status_text = f"Device: CPU — {info['note']}"
        self.statusBar().showMessage(status_text)

        # Tab focus hooks
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Wire conversion → preview tab
        self._convert_vm.conversion_done.connect(self._on_conversion_done)

        # Disable Convert button while queue runner is busy
        bridge.runner_busy_changed.connect(self._convert_vm.set_engine_busy)

        # Show first-run dialog if needed
        if self._first_run_vm.needs_first_run:
            self._show_first_run()

    def _show_first_run(self) -> None:
        dlg = FirstRunDialog(self._first_run_vm, self)
        if dlg.exec() != FirstRunDialog.DialogCode.Accepted:
            QApplication.quit()

    def _on_tab_changed(self, index: int) -> None:
        if index == _TAB_CONVERT:
            self._convert_view.refresh_profiles()
        elif index == _TAB_QUEUE:
            self._queue_view.refresh_profiles()

    def _on_conversion_done(self, output_path: str) -> None:
        self._preview_vm.set_paths(self._convert_vm.source_path, output_path)
        self._tabs.setCurrentIndex(_TAB_PREVIEW)
