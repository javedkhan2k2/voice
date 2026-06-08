"""Settings tab — device, engine, output, diagnostics preferences."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voiceconv.app.view_models.settings_vm import SettingsViewModel

_DEVICES = ["auto", "cuda", "cpu"]
_ENGINES = ["mock", "openvoice-v2", "freevc"]
_FORMATS = ["wav", "flac"]
_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


class SettingsView(QWidget):
    def __init__(self, vm: SettingsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = vm
        self._build_ui()
        self._connect_vm()
        self._load_current()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # ── Conversion ──────────────────────────────────────────────────
        conv_box = QGroupBox("Conversion")
        conv_form = QFormLayout(conv_box)
        conv_form.setSpacing(8)

        self._device_combo = QComboBox()
        self._device_combo.addItems(_DEVICES)
        self._device_combo.setAccessibleName("Compute device")
        conv_form.addRow("Device:", self._device_combo)

        engine_row = QWidget()
        engine_layout = QVBoxLayout(engine_row)
        engine_layout.setContentsMargins(0, 0, 0, 0)
        engine_layout.setSpacing(2)
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(_ENGINES)
        self._engine_combo.setAccessibleName("Active conversion engine")
        self._engine_combo.setAccessibleDescription(
            "Engine changes apply on next launch"
        )
        engine_layout.addWidget(self._engine_combo)
        engine_note = QLabel("Engine changes apply on next launch.")
        engine_note.setStyleSheet("color: gray; font-size: 10px;")
        engine_layout.addWidget(engine_note)
        conv_form.addRow("Engine:", engine_row)

        self._format_combo = QComboBox()
        self._format_combo.addItems([f.upper() for f in _FORMATS])
        self._format_combo.setAccessibleName("Output audio format")
        conv_form.addRow("Output format:", self._format_combo)

        self._loudness_cb = QCheckBox("Normalise output loudness")
        self._loudness_cb.setAccessibleName("Normalise output loudness")
        conv_form.addRow("Loudness:", self._loudness_cb)

        root.addWidget(conv_box)

        # ── Storage ─────────────────────────────────────────────────────
        storage_box = QGroupBox("Storage")
        storage_form = QFormLayout(storage_box)
        storage_form.setSpacing(8)

        dir_row = QWidget()
        dir_layout = QHBoxLayout(dir_row)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("(blank = source file's folder)")
        self._dir_edit.setAccessibleName("Output folder path")
        dir_layout.addWidget(self._dir_edit)
        browse_btn = QPushButton("&Browse…")
        browse_btn.setAccessibleName("Browse for output folder")
        browse_btn.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(browse_btn)
        storage_form.addRow("Output folder:", dir_row)

        root.addWidget(storage_box)

        # ── Diagnostics ──────────────────────────────────────────────────
        diag_box = QGroupBox("Diagnostics")
        diag_form = QFormLayout(diag_box)
        diag_form.setSpacing(8)

        self._log_level_combo = QComboBox()
        self._log_level_combo.addItems(_LOG_LEVELS)
        self._log_level_combo.setAccessibleName("Log level")
        diag_form.addRow("Log level:", self._log_level_combo)

        self._export_btn = QPushButton("Export &Diagnostics…")
        self._export_btn.setAccessibleName("Export diagnostics bundle")
        self._export_btn.setToolTip(
            "Save a ZIP of logs and environment info (no audio) for support."
        )
        self._export_btn.clicked.connect(self._export_diagnostics)
        diag_form.addRow("Support bundle:", self._export_btn)

        root.addWidget(diag_box)
        root.addStretch()

    def _connect_vm(self) -> None:
        self._device_combo.currentTextChanged.connect(self._vm.set_device)
        self._engine_combo.currentTextChanged.connect(self._vm.set_active_engine)
        self._format_combo.currentTextChanged.connect(
            lambda t: self._vm.set_output_format(t.lower())
        )
        self._loudness_cb.stateChanged.connect(
            lambda s: self._vm.set_loudness_normalize(bool(s))
        )
        self._dir_edit.editingFinished.connect(
            lambda: self._vm.set_output_dir(self._dir_edit.text().strip())
        )
        self._log_level_combo.currentTextChanged.connect(self._vm.set_log_level)
        self._vm.error.connect(self._on_error)
        self._vm.settings_changed.connect(self._load_current)
        self._vm.export_succeeded.connect(self._on_export_succeeded)

    def _load_current(self) -> None:
        """Populate controls from current vm state without triggering saves."""
        self._block(True)
        try:
            _set_combo(self._device_combo, self._vm.device)
            _set_combo(self._engine_combo, self._vm.active_engine)
            _set_combo(self._format_combo, self._vm.output_format.upper())
            self._loudness_cb.setChecked(self._vm.loudness_normalize)
            if self._dir_edit.text() != self._vm.output_dir:
                self._dir_edit.setText(self._vm.output_dir)
            _set_combo(self._log_level_combo, self._vm.log_level)
        finally:
            self._block(False)

    def _block(self, on: bool) -> None:
        for w in (
            self._device_combo, self._engine_combo, self._format_combo,
            self._loudness_cb, self._log_level_combo,
        ):
            w.blockSignals(on)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self._vm.output_dir or ""
        )
        if path:
            self._vm.set_output_dir(path)
            if self._vm.output_dir == path:  # accepted (not blocked)
                self._dir_edit.setText(path)

    def _export_diagnostics(self) -> None:
        default_name = f"voicebuilder-diagnostics-{datetime.now():%Y%m%d-%H%M%S}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Diagnostics", default_name, "ZIP archives (*.zip)"
        )
        if path:
            self._vm.export_diagnostics(path)

    def _on_export_succeeded(self, path: str) -> None:
        QMessageBox.information(
            self, "Diagnostics", f"Diagnostics bundle saved to:\n{path}"
        )

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Settings", msg)
        self._load_current()  # revert displayed value


def _set_combo(combo: QComboBox, value: str) -> None:
    idx = combo.findText(value, )
    if idx >= 0:
        combo.setCurrentIndex(idx)
