"""First-run acceptable-use acknowledgement dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from voiceconv.app._guidance import ACCEPTABLE_USE
from voiceconv.app.view_models.first_run_vm import FirstRunViewModel


class FirstRunDialog(QDialog):
    def __init__(self, vm: FirstRunViewModel, parent=None) -> None:
        super().__init__(parent)
        self._vm = vm
        self.setWindowTitle("VoiceBuilder — First-Time Setup")
        self.setMinimumWidth(520)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Device info
        info = self._vm.device_info
        if info["device"] == "cuda":
            device_text = f"GPU detected: {info['note']} ({info['vram_mb']} MB VRAM)"
        else:
            device_text = (
                f"No GPU detected — {info['note']}.\n"
                "Warning: Conversions will run on CPU, which is significantly "
                "slower than GPU. Expect longer processing times."
            )
        device_label = QLabel(device_text)
        device_label.setWordWrap(True)
        layout.addWidget(device_label)

        # Separator label
        layout.addWidget(QLabel("─" * 60))

        # Acceptable-use statement
        use_label = QLabel(ACCEPTABLE_USE)
        use_label.setWordWrap(True)
        use_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(use_label)

        # Checkbox
        self._checkbox = QCheckBox("I understand and accept the above terms")
        self._checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self._checkbox)

        # Buttons
        self._ok_btn = QPushButton("Continue")
        self._ok_btn.setEnabled(False)
        self._ok_btn.clicked.connect(self._on_accept)

        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(self.reject)

        btn_box = QDialogButtonBox()
        btn_box.addButton(self._ok_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton(exit_btn, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(btn_box)

    def _on_checkbox_changed(self, state: int) -> None:
        self._ok_btn.setEnabled(state == Qt.CheckState.Checked.value)

    def _on_accept(self) -> None:
        self._vm.set_acknowledged(True)
        self.accept()
