"""Create Profile panel."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from voiceconv.app.view_models.profile_vm import ProfileViewModel

_AUDIO_FILTER = "Audio files (*.wav *.flac *.mp3 *.ogg *.m4a);;All files (*)"


class ProfileView(QWidget):
    def __init__(self, vm: ProfileViewModel, parent=None) -> None:
        super().__init__(parent)
        self._vm = vm
        self._build_ui()
        self._connect_vm()

    def _build_ui(self) -> None:
        form = QFormLayout(self)
        form.setSpacing(10)

        # Reference file picker
        ref_row = QWidget()
        ref_layout = QHBoxLayout(ref_row)
        ref_layout.setContentsMargins(0, 0, 0, 0)
        self._ref_edit = QLineEdit()
        self._ref_edit.setPlaceholderText("Path to reference audio clip…")
        self._ref_edit.setReadOnly(True)
        self._ref_edit.setAccessibleName("Reference clip path")
        ref_browse = QPushButton("&Browse…")
        ref_browse.setAccessibleName("Browse for reference clip")
        ref_browse.clicked.connect(self._browse_reference)
        ref_layout.addWidget(self._ref_edit)
        ref_layout.addWidget(ref_browse)
        form.addRow("Reference clip:", ref_row)

        # Profile name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Alice")
        self._name_edit.setAccessibleName("Profile name")
        self._name_edit.textChanged.connect(self._vm.set_name)
        form.addRow("Profile name:", self._name_edit)

        # Consent checkbox
        self._consent_cb = QCheckBox(
            "I confirm I own or have explicit permission to use this voice,\n"
            "and accept full responsibility for any use of the generated output."
        )
        self._consent_cb.setAccessibleName("Consent affirmation")
        self._consent_cb.stateChanged.connect(
            lambda s: self._vm.set_consent_affirmed(bool(s))
        )
        form.addRow("", self._consent_cb)

        # Create button
        self._create_btn = QPushButton("Create &Profile")
        self._create_btn.setAccessibleName("Create voice profile")
        self._create_btn.clicked.connect(self._vm.create_profile)
        form.addRow("", self._create_btn)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setAccessibleName("Profile creation status")
        form.addRow("", self._status_label)

    def _connect_vm(self) -> None:
        self._vm.is_busy_changed.connect(self._on_busy_changed)
        self._vm.profile_saved.connect(self._on_profile_saved)
        self._vm.error.connect(self._on_error)

    def _browse_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Reference Clip", "", _AUDIO_FILTER)
        if path:
            self._ref_edit.setText(path)
            self._vm.set_reference_path(path)

    def _on_busy_changed(self, busy: bool) -> None:
        self._create_btn.setEnabled(not busy)
        self._status_label.setText("Processing reference clip…" if busy else "")

    def _on_profile_saved(self, profile_id: str) -> None:
        self._status_label.setText(f"Profile saved (id: {profile_id[:8]}…)")
        self._name_edit.clear()
        self._ref_edit.clear()
        self._consent_cb.setChecked(False)

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Create Profile", msg)
