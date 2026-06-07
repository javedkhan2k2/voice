"""Queue tab — multi-file batch conversion list."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from voiceconv.app.view_models.queue_vm import QueueViewModel
from voiceconv.services.job import Job, JobStatus

_AUDIO_FILTER = "Audio files (*.wav *.flac *.mp3 *.ogg *.m4a);;All files (*)"

_COL_FILE = 0
_COL_STATUS = 1
_COL_PROGRESS = 2
_COL_ELAPSED = 3
_COL_ACTION = 4

_STATUS_COLORS: dict[JobStatus, str] = {
    JobStatus.QUEUED: "#888888",
    JobStatus.RUNNING: "#0070c0",
    JobStatus.DONE: "#107c10",
    JobStatus.CANCELLED: "#ca5010",
    JobStatus.FAILED: "#d13438",
}


class QueueView(QWidget):
    def __init__(self, vm: QueueViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = vm
        self._job_row: dict[str, int] = {}  # job_id → row index
        self._build_ui()
        self._connect_vm()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_elapsed)
        self._timer.start()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Toolbar row
        toolbar = QWidget()
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(0, 0, 0, 0)

        tb_layout.addWidget(QLabel("Profile:"))
        self._profile_combo = QComboBox()
        self._profile_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        tb_layout.addWidget(self._profile_combo)

        self._add_btn = QPushButton("Add Files…")
        self._add_btn.clicked.connect(self._browse_files)
        tb_layout.addWidget(self._add_btn)

        self._clear_btn = QPushButton("Clear Done")
        self._clear_btn.clicked.connect(self._vm.clear_done)
        tb_layout.addWidget(self._clear_btn)

        tb_layout.addStretch()
        root.addWidget(toolbar)

        # Job table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["File", "Status", "Progress", "Elapsed", "Action"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_FILE, QHeaderView.ResizeMode.Stretch
        )
        for col in (_COL_STATUS, _COL_ELAPSED, _COL_ACTION):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_PROGRESS, QHeaderView.ResizeMode.Interactive
        )
        self._table.setColumnWidth(_COL_PROGRESS, 140)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table)

        # Status bar label
        self._status_label = QLabel("")
        root.addWidget(self._status_label)

    def _connect_vm(self) -> None:
        self._vm.jobs_reset.connect(self._rebuild_table)
        self._vm.job_status_changed.connect(self._on_job_status)
        self._vm.job_progress_changed.connect(self._on_job_progress)
        self._vm.error.connect(self._on_error)

    # ------------------------------------------------------------------
    # Profile combo
    # ------------------------------------------------------------------

    def refresh_profiles(self) -> None:
        """Reload profile list from the view-model (called when tab focused)."""
        self._vm.refresh_profiles()
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        for p in self._vm.profiles():
            self._profile_combo.addItem(p.name, userData=p.profile_id)
        if not self._vm.profiles():
            self._profile_combo.addItem("— no profiles yet —", userData=None)
        self._profile_combo.blockSignals(False)
        self._on_profile_selected(self._profile_combo.currentIndex())

    def _on_profile_selected(self, index: int) -> None:
        profile_id = self._profile_combo.itemData(index)
        if profile_id:
            self._vm.set_selected_profile_id(profile_id)

    # ------------------------------------------------------------------
    # File picker
    # ------------------------------------------------------------------

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Source Audio Files", "", _AUDIO_FILTER
        )
        if paths:
            self._vm.add_files(paths)

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def _rebuild_table(self) -> None:
        jobs = self._vm.list_jobs()
        self._table.setRowCount(0)
        self._job_row.clear()
        for job in jobs:
            self._append_row(job)

    def _append_row(self, job: Job) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._job_row[job.job_id] = row

        # File name
        file_item = QTableWidgetItem(job.request.source_path.split("\\")[-1].split("/")[-1])
        file_item.setData(Qt.ItemDataRole.UserRole, job.job_id)
        file_item.setToolTip(job.request.source_path)
        self._table.setItem(row, _COL_FILE, file_item)

        # Status
        self._table.setItem(row, _COL_STATUS, self._make_status_item(job.status))

        # Progress bar
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(job.progress * 100))
        bar.setTextVisible(True)
        self._table.setCellWidget(row, _COL_PROGRESS, bar)

        # Elapsed
        self._table.setItem(row, _COL_ELAPSED, QTableWidgetItem(self._elapsed_str(job)))

        # Action button
        btn = self._make_action_btn(job)
        if btn:
            self._table.setCellWidget(row, _COL_ACTION, btn)
        else:
            self._table.setItem(row, _COL_ACTION, QTableWidgetItem(""))

    def _update_row(self, job_id: str) -> None:
        """Update status, progress, elapsed, and action for one existing row."""
        row = self._job_row.get(job_id)
        if row is None:
            return
        job = self._vm._state.runner.get_job(job_id)
        if job is None:
            return

        self._table.setItem(row, _COL_STATUS, self._make_status_item(job.status))

        bar = self._table.cellWidget(row, _COL_PROGRESS)
        if isinstance(bar, QProgressBar):
            bar.setValue(int(job.progress * 100))

        self._table.setItem(row, _COL_ELAPSED, QTableWidgetItem(self._elapsed_str(job)))

        btn = self._make_action_btn(job)
        if btn:
            self._table.setCellWidget(row, _COL_ACTION, btn)
        else:
            self._table.setItem(row, _COL_ACTION, QTableWidgetItem(""))

    def _make_status_item(self, status: JobStatus) -> QTableWidgetItem:
        item = QTableWidgetItem(status.value.upper())
        item.setForeground(QBrush(QColor(_STATUS_COLORS.get(status, "#000000"))))
        return item

    def _make_action_btn(self, job: Job) -> QPushButton | None:
        if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            btn = QPushButton("Cancel")
            btn.clicked.connect(lambda: self._vm.cancel_job(job.job_id))
            return btn
        if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
            btn = QPushButton("Retry")
            btn.clicked.connect(lambda: self._vm.retry_job(job.job_id))
            return btn
        if job.status == JobStatus.DONE:
            btn = QPushButton("Open Folder")
            btn.clicked.connect(lambda: self._vm.open_output_folder(job.job_id))
            return btn
        return None

    # ------------------------------------------------------------------
    # Elapsed time
    # ------------------------------------------------------------------

    @staticmethod
    def _elapsed_str(job: Job) -> str:
        if job.started_at is None:
            return "—"
        end = job.finished_at if job.finished_at is not None else time.time()
        secs = int(end - job.started_at)
        return f"{secs // 60}:{secs % 60:02d}"

    def _refresh_elapsed(self) -> None:
        for job_id, row in self._job_row.items():
            job = self._vm._state.runner.get_job(job_id)
            if job and job.status == JobStatus.RUNNING:
                self._table.setItem(
                    row, _COL_ELAPSED, QTableWidgetItem(self._elapsed_str(job))
                )

    # ------------------------------------------------------------------
    # VM signal handlers
    # ------------------------------------------------------------------

    def _on_job_status(self, job_id: str, status: object) -> None:
        self._update_row(job_id)

    def _on_job_progress(self, job_id: str, fraction: float) -> None:
        row = self._job_row.get(job_id)
        if row is None:
            return
        bar = self._table.cellWidget(row, _COL_PROGRESS)
        if isinstance(bar, QProgressBar):
            bar.setValue(int(fraction * 100))

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Queue", msg)
