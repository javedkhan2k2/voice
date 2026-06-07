"""Top-level application window."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from voiceconv.app._app_state import AppState
from voiceconv.app.view_models.convert_vm import ConvertViewModel
from voiceconv.app.view_models.first_run_vm import FirstRunViewModel
from voiceconv.app.view_models.preview_vm import PreviewViewModel
from voiceconv.app.view_models.profile_vm import ProfileViewModel
from voiceconv.app.views.convert_view import ConvertView
from voiceconv.app.views.first_run_dialog import FirstRunDialog
from voiceconv.app.views.preview_view import PreviewView
from voiceconv.app.views.profile_view import ProfileView


class MainWindow(QMainWindow):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self.setWindowTitle("VoiceBuilder")
        self.resize(700, 480)

        self._first_run_vm = FirstRunViewModel(state.settings, state.settings_store)
        self._profile_vm = ProfileViewModel(state)
        self._convert_vm = ConvertViewModel(state)
        self._preview_vm = PreviewViewModel()

        self._tabs = QTabWidget()
        self._profile_view = ProfileView(self._profile_vm)
        self._convert_view = ConvertView(state, self._convert_vm)
        self._preview_view = PreviewView(self._preview_vm)

        self._tabs.addTab(self._profile_view, "Create Profile")
        self._tabs.addTab(self._convert_view, "Convert")
        self._tabs.addTab(self._preview_view, "Preview && Export")
        self.setCentralWidget(self._tabs)

        # Refresh profiles when Convert tab is focused
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Wire conversion → preview tab
        self._convert_vm.conversion_done.connect(self._on_conversion_done)

        # Show first-run dialog if needed
        if self._first_run_vm.needs_first_run:
            self._show_first_run()

    def _show_first_run(self) -> None:
        dlg = FirstRunDialog(self._first_run_vm, self)
        if dlg.exec() != FirstRunDialog.DialogCode.Accepted:
            QApplication.quit()

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:  # Convert tab
            self._convert_view.refresh_profiles()

    def _on_conversion_done(self, output_path: str) -> None:
        self._preview_vm.set_paths(self._convert_vm.source_path, output_path)
        self._tabs.setCurrentIndex(2)  # Preview tab
