"""Convert panel — source picker, profile selector, progress bar, cancel."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QWidget,
)

from voiceconv.app._app_state import AppState
from voiceconv.app.view_models.convert_vm import ConvertViewModel
from voiceconv.storage.profile import VoiceProfile

_AUDIO_FILTER = "Audio files (*.wav *.flac *.mp3 *.ogg *.m4a);;All files (*)"
_OUTPUT_FILTER = "WAV files (*.wav);;FLAC files (*.flac);;All files (*)"


class ConvertView(QWidget):
    def __init__(self, state: AppState, vm: ConvertViewModel, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._vm = vm
        self._profiles: list[VoiceProfile] = []
        self._build_ui()
        self._connect_vm()

    def _build_ui(self) -> None:
        form = QFormLayout(self)
        form.setSpacing(10)

        # Source file
        src_row = QWidget()
        src_layout = QHBoxLayout(src_row)
        src_layout.setContentsMargins(0, 0, 0, 0)
        self._src_edit = QLineEdit()
        self._src_edit.setPlaceholderText("Path to source speech file…")
        self._src_edit.setReadOnly(True)
        src_browse = QPushButton("Browse…")
        src_browse.clicked.connect(self._browse_source)
        src_layout.addWidget(self._src_edit)
        src_layout.addWidget(src_browse)
        form.addRow("Source file:", src_row)

        # Profile selector
        self._profile_combo = QComboBox()
        self._profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        form.addRow("Voice profile:", self._profile_combo)

        # Output path
        out_row = QWidget()
        out_layout = QHBoxLayout(out_row)
        out_layout.setContentsMargins(0, 0, 0, 0)
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Output file path…")
        self._out_edit.textChanged.connect(self._vm.set_output_path)
        out_browse = QPushButton("Browse…")
        out_browse.clicked.connect(self._browse_output)
        out_layout.addWidget(self._out_edit)
        out_layout.addWidget(out_browse)
        form.addRow("Output file:", out_row)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        form.addRow("Progress:", self._progress_bar)

        # Buttons row
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self._convert_btn = QPushButton("Convert")
        self._convert_btn.clicked.connect(self._vm.start_convert)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._vm.cancel)
        self._cancel_btn.setVisible(False)
        btn_layout.addWidget(self._convert_btn)
        btn_layout.addWidget(self._cancel_btn)
        btn_layout.addStretch()
        form.addRow("", btn_row)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        form.addRow("", self._status_label)

    def _connect_vm(self) -> None:
        self._vm.output_path_changed.connect(self._on_output_path_changed)
        self._vm.progress_changed.connect(self._on_progress)
        self._vm.is_running_changed.connect(self._on_running_changed)
        self._vm.error.connect(self._on_error)

    def refresh_profiles(self) -> None:
        self._profiles = self._state.profile_repo.list_all()
        self._profile_combo.clear()
        for p in self._profiles:
            self._profile_combo.addItem(p.name)
        if not self._profiles:
            self._profile_combo.addItem("— no profiles yet —")
        self._on_profile_selected(self._profile_combo.currentIndex())

    def _browse_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Source Audio", "", _AUDIO_FILTER)
        if path:
            self._src_edit.setText(path)
            self._vm.set_source_path(path)

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Output As", self._vm.output_path, _OUTPUT_FILTER)
        if path:
            self._out_edit.setText(path)
            self._vm.set_output_path(path)

    def _on_profile_selected(self, index: int) -> None:
        if 0 <= index < len(self._profiles):
            self._vm.set_profile_artifacts(self._profiles[index].artifacts)
        else:
            self._vm.set_profile_artifacts(None)

    def _on_output_path_changed(self, path: str) -> None:
        if self._out_edit.text() != path:
            self._out_edit.setText(path)

    def _on_progress(self, value: float) -> None:
        self._progress_bar.setValue(int(value * 100))

    def _on_running_changed(self, running: bool) -> None:
        self._convert_btn.setEnabled(not running)
        self._cancel_btn.setVisible(running)
        self._status_label.setText("Converting…" if running else "")

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Convert", msg)
