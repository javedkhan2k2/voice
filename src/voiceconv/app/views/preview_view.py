"""A/B Preview and Export panel."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voiceconv.app.view_models.preview_vm import PreviewViewModel

_OUTPUT_FILTER = "WAV files (*.wav);;FLAC files (*.flac);;All files (*)"


class PreviewView(QWidget):
    def __init__(self, vm: PreviewViewModel, parent=None) -> None:
        super().__init__(parent)
        self._vm = vm
        self._build_ui()
        self._connect_vm()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._info_label = QLabel("Run a conversion first to enable preview.")
        self._info_label.setWordWrap(True)
        self._info_label.setAccessibleName("Preview source and output paths")
        layout.addWidget(self._info_label)

        # Playback row
        play_row = QWidget()
        play_layout = QHBoxLayout(play_row)
        play_layout.setContentsMargins(0, 0, 0, 0)
        self._play_src_btn = QPushButton("▶  Play &Source")
        self._play_src_btn.setEnabled(False)
        self._play_src_btn.setAccessibleName("Play source audio")
        self._play_src_btn.clicked.connect(self._vm.play_source)
        self._play_out_btn = QPushButton("▶  Play &Output")
        self._play_out_btn.setEnabled(False)
        self._play_out_btn.setAccessibleName("Play converted output audio")
        self._play_out_btn.clicked.connect(self._vm.play_output)
        play_layout.addWidget(self._play_src_btn)
        play_layout.addWidget(self._play_out_btn)
        play_layout.addStretch()
        layout.addWidget(play_row)

        # Export button
        self._export_btn = QPushButton("&Export / Save As…")
        self._export_btn.setEnabled(False)
        self._export_btn.setAccessibleName("Export converted audio")
        self._export_btn.clicked.connect(self._on_export)
        layout.addWidget(self._export_btn)

        layout.addStretch()

    def _connect_vm(self) -> None:
        self._vm.paths_changed.connect(self._on_paths_changed)
        self._vm.error.connect(self._on_error)

    def _on_paths_changed(self) -> None:
        has = self._vm.has_output
        self._play_src_btn.setEnabled(bool(self._vm.source_path))
        self._play_out_btn.setEnabled(has)
        self._export_btn.setEnabled(has)
        if has:
            self._info_label.setText(
                f"Source: {self._vm.source_path}\nOutput: {self._vm.output_path}"
            )

    def _on_export(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Output As", self._vm.output_path, _OUTPUT_FILTER
        )
        if dest:
            self._vm.export_to(dest)

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Preview", msg)
