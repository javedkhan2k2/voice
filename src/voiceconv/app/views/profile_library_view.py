"""Profile Library tab — browse, rename, delete voice profiles."""

from __future__ import annotations

import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from voiceconv.app.view_models.profile_library_vm import ProfileLibraryViewModel
from voiceconv.storage.profile import VoiceProfile


def _fmt_ts(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


class ProfileLibraryView(QWidget):
    def __init__(self, vm: ProfileLibraryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = vm
        self._build_ui()
        self._connect_vm()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._vm.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left — profile list
        self._list = QListWidget()
        self._list.setAccessibleName("Voice profiles")
        self._list.setAccessibleDescription("List of saved voice profiles")
        self._list.currentItemChanged.connect(self._on_list_selection)
        splitter.addWidget(self._list)

        # Right — detail panel
        self._detail = QWidget()
        detail_layout = QVBoxLayout(self._detail)
        detail_layout.setContentsMargins(8, 0, 0, 0)

        # Name / Created
        info_form = QFormLayout()
        info_form.setSpacing(6)
        self._name_label = QLabel("")
        self._name_label.setAccessibleName("Profile name")
        self._created_label = QLabel("")
        self._created_label.setAccessibleName("Profile created date")
        info_form.addRow("Name:", self._name_label)
        info_form.addRow("Created:", self._created_label)
        detail_layout.addLayout(info_form)

        # Consent record group
        consent_box = QGroupBox("Consent Record")
        consent_form = QFormLayout(consent_box)
        consent_form.setSpacing(6)
        self._statement_label = QLabel("")
        self._statement_label.setWordWrap(True)
        self._statement_label.setAccessibleName("Consent statement")
        self._affirmed_label = QLabel("")
        self._affirmed_label.setAccessibleName("Consent affirmed date")
        self._affirmed_by_label = QLabel("")
        self._affirmed_by_label.setAccessibleName("Consent affirmed by")
        self._app_version_label = QLabel("")
        self._app_version_label.setAccessibleName("Consent app version")
        consent_form.addRow("Statement:", self._statement_label)
        consent_form.addRow("Affirmed:", self._affirmed_label)
        consent_form.addRow("By:", self._affirmed_by_label)
        consent_form.addRow("App version:", self._app_version_label)
        detail_layout.addWidget(consent_box)

        detail_layout.addStretch()

        # Action buttons
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self._rename_btn = QPushButton("&Rename…")
        self._rename_btn.setAccessibleName("Rename selected profile")
        self._rename_btn.clicked.connect(self._on_rename)
        self._rename_btn.setEnabled(False)
        self._delete_btn = QPushButton("&Delete")
        self._delete_btn.setAccessibleName("Delete selected profile")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        btn_layout.addWidget(self._rename_btn)
        btn_layout.addWidget(self._delete_btn)
        btn_layout.addStretch()
        detail_layout.addWidget(btn_row)

        self._placeholder = QLabel("Select a profile to view details.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Stack: placeholder or detail
        self._stack = QWidget()
        stack_layout = QVBoxLayout(self._stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.addWidget(self._placeholder)
        stack_layout.addWidget(self._detail)
        self._detail.setVisible(False)

        splitter.addWidget(self._stack)
        splitter.setSizes([200, 420])

        root.addWidget(splitter)

    def _connect_vm(self) -> None:
        self._vm.profiles_changed.connect(self._rebuild_list)
        self._vm.selection_changed.connect(self._on_vm_selection)
        self._vm.error.connect(self._on_error)

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _rebuild_list(self) -> None:
        selected_id = (
            self._vm.selected_profile().profile_id
            if self._vm.selected_profile() else None
        )
        self._list.blockSignals(True)
        self._list.clear()
        for profile in self._vm.profiles():
            item = QListWidgetItem(profile.name)
            item.setData(Qt.ItemDataRole.UserRole, profile.profile_id)
            self._list.addItem(item)
            if profile.profile_id == selected_id:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)
        if self._list.currentItem() is None and self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _on_list_selection(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            self._vm.select("")
            return
        profile_id = current.data(Qt.ItemDataRole.UserRole)
        if profile_id:
            self._vm.select(profile_id)

    # ------------------------------------------------------------------
    # Detail panel
    # ------------------------------------------------------------------

    def _on_vm_selection(self, profile_id: str) -> None:
        if not profile_id:
            self._placeholder.setVisible(True)
            self._detail.setVisible(False)
            self._rename_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return

        profile = self._vm.selected_profile()
        if profile is None:
            return
        self._populate_detail(profile)
        self._placeholder.setVisible(False)
        self._detail.setVisible(True)
        self._rename_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)

    def _populate_detail(self, profile: VoiceProfile) -> None:
        self._name_label.setText(profile.name)
        self._created_label.setText(_fmt_ts(profile.created_at))
        self._statement_label.setText(profile.consent.statement)
        self._affirmed_label.setText(_fmt_ts(profile.consent.affirmed_at))
        self._affirmed_by_label.setText(profile.consent.affirmed_by)
        self._app_version_label.setText(profile.consent.app_version or "unknown")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_rename(self) -> None:
        profile = self._vm.selected_profile()
        if profile is None:
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename Profile", "New name:", text=profile.name
        )
        if ok:
            self._vm.rename(profile.profile_id, new_name)

    def _on_delete(self) -> None:
        profile = self._vm.selected_profile()
        if profile is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{profile.name}'?\n"
            "This removes the profile and all its data permanently.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._vm.delete(profile.profile_id)

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Profile Library", msg)
