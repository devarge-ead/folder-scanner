"""Main application window and widgets.

Implements the left folder tree (with per-item checkboxes and first-level child
expansion), the right settings panel, the results table and the loading video.
"""

import os
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
)

from . import storage
from .i18n import I18n, LANGUAGES
from .scanner import ScanWorker, _select_scan_roots

# Result table columns.
COL_FOLDER = 0
COL_FILE = 1
COL_COUNT = 2
COL_LOCATIONS = 3

# Tree item data roles.
ROLE_PATH = Qt.UserRole
ROLE_POPULATED = Qt.UserRole + 1

_PRIMARY = "#043c59"


def resource_path(relative: str) -> str:
    """Resolve a path relative to the project root (works when frozen)."""
    base = getattr(sys, "_MEIPASS",
                   os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)


class SettingsDialog(QDialog):
    """Modal dialog for application-level settings (currently the language)."""

    def __init__(self, i18n, on_language_changed, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._on_language_changed = on_language_changed
        self.setModal(True)

        box = QVBoxLayout(self)
        box.setContentsMargins(12, 12, 12, 12)
        box.setSpacing(10)

        self.label_lang = QLabel()
        self.combo_lang = QComboBox()
        for code, name in LANGUAGES.items():
            self.combo_lang.addItem(name, code)
        index = self.combo_lang.findData(i18n.ui_language)
        self.combo_lang.setCurrentIndex(index if index >= 0 else 0)
        self.combo_lang.currentIndexChanged.connect(self._lang_changed)

        row = QHBoxLayout()
        row.addWidget(self.label_lang)
        row.addWidget(self.combo_lang, 1)
        box.addLayout(row)

        close_button = QPushButton()
        close_button.clicked.connect(self.accept)
        box.addWidget(close_button)

        self._apply_texts()

    def _lang_changed(self, _index):
        code = self.combo_lang.currentData()
        if code:
            self._on_language_changed(code)
        self._apply_texts()

    def _apply_texts(self):
        self.setWindowTitle(self._i18n.t("settings"))
        self.label_lang.setText(self._i18n.t("ui_language"))
        # Update the close button text from its child widgets.
        for button in self.findChildren(QPushButton):
            button.setText(self._i18n.t("close_button"))


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.state = storage.load()
        settings = self.state["settings"]
        self.i18n = I18n(settings.get("ui_language", "en"))
        self._worker = None
        self._loading_tree = False
        self._result_count = 0

        self._build_ui()
        self._apply_ui_language()
        self._restore_folders()
        self._restore_settings()
        self.setWindowTitle(self.i18n.t("app_title"))
        self.resize(1080, 720)

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_folder_panel())
        splitter.addWidget(self._build_main_panel())
        splitter.setSizes([260, 820])
        layout.addWidget(splitter)
        self.setCentralWidget(central)

    def _build_folder_panel(self):
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        self.label_folders = QLabel()
        self.label_folders.setStyleSheet(f"font-weight:600; color:{_PRIMARY};")
        vbox.addWidget(self.label_folders)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemChanged.connect(self._on_item_check_changed)
        vbox.addWidget(self.tree, 1)

        buttons = QWidget()
        hbox = QHBoxLayout(buttons)
        self.button_add = QPushButton()
        self.button_remove = QPushButton()
        self.button_settings = QPushButton()
        self.button_add.clicked.connect(self._add_folder)
        self.button_remove.clicked.connect(self._remove_folder)
        self.button_settings.clicked.connect(self._open_settings)
        hbox.addWidget(self.button_add)
        hbox.addWidget(self.button_remove)
        hbox.addStretch()
        hbox.addWidget(self.button_settings)
        vbox.addWidget(buttons)
        return panel

    def _build_main_panel(self):
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        vbox.addWidget(self._build_settings_panel())
        vbox.addWidget(self._build_results_panel(), 1)
        return panel

    def _build_settings_panel(self):
        self.label_settings = QLabel()
        self.label_settings.setStyleSheet(
            f"font-weight:600; color:{_PRIMARY}; font-size:12px;")

        panel = QWidget()
        box = QVBoxLayout(panel)
        box.setContentsMargins(6, 4, 6, 4)
        box.setSpacing(4)
        box.addWidget(self.label_settings)

        # Row 1: search text input.
        row1 = QWidget()
        r1 = QHBoxLayout(row1)
        r1.setSpacing(8)
        r1.addWidget(self._field_label("search_text"))
        self.input_query = QLineEdit()
        self.input_query.setClearButtonEnabled(True)
        self.input_query.setMinimumWidth(160)
        r1.addWidget(self.input_query, 1)
        box.addWidget(row1)

        # Row 2: match method radios, file-type toggles and the fuzzy threshold.
        row2 = QWidget()
        r2 = QHBoxLayout(row2)
        r2.setSpacing(8)
        self.radio_exact = QRadioButton()
        self.radio_fuzzy = QRadioButton()
        self.radio_exact.setChecked(True)
        r2.addWidget(self.radio_exact)
        r2.addWidget(self.radio_fuzzy)
        r2.addWidget(self._field_label("file_types"))
        self.type_boxes = {}
        for key, text_key in (("filename", "ft_filename"), ("word", "ft_word"),
                              ("excel", "ft_excel"), ("pdf", "ft_pdf"),
                              ("txt", "ft_txt")):
            check = QCheckBox()
            check.setText(text_key)
            self.type_boxes[key] = check
            r2.addWidget(check)
        r2.addStretch()
        self.threshold_frame = QWidget()
        th = QHBoxLayout(self.threshold_frame)
        th.setSpacing(6)
        self.label_threshold = QLabel()
        th.addWidget(self.label_threshold)
        self.slider_threshold = QSlider(Qt.Orientation.Horizontal)
        self.slider_threshold.setRange(1, 100)
        self.slider_threshold.setValue(85)
        self.slider_threshold.valueChanged.connect(
            lambda v: self.label_threshold_value.setText(str(v)))
        self.label_threshold_value = QLabel("85")
        self.label_threshold_value.setMinimumWidth(30)
        th.addWidget(self.slider_threshold, 1)
        th.addWidget(self.label_threshold_value)
        self.threshold_frame.setVisible(False)
        r2.addWidget(self.threshold_frame)
        box.addWidget(row2)

        # Row 3: Start/Stop buttons, progress bar and the status message.
        row3 = QWidget()
        r3 = QHBoxLayout(row3)
        r3.setSpacing(8)
        self.button_start = QPushButton()
        self.button_stop = QPushButton()
        self.button_stop.setEnabled(False)
        self.button_start.clicked.connect(self._on_start)
        self.button_stop.clicked.connect(self._on_stop)
        r3.addWidget(self.button_start)
        r3.addWidget(self.button_stop)
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        r3.addWidget(self.progress, 1)
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color:#555;")
        r3.addWidget(self.status_label)
        box.addWidget(row3)

        return panel

    def _field_label(self, key):
        label = QLabel()
        label.setObjectName("fieldLabel")
        label.i18n_key = key
        return label

    def _build_results_panel(self):
        self.label_results = QLabel()
        self.label_results.setStyleSheet(
            f"font-weight:600; color:{_PRIMARY}; font-size:12px;")

        self.results = QTableWidget()
        self.results.setColumnCount(4)
        self.results.setSortingEnabled(True)
        self.results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.verticalHeader().setVisible(False)
        self.results.horizontalHeader().setStretchLastSection(True)
        self.results.setColumnWidth(COL_FOLDER, 140)
        self.results.setColumnWidth(COL_FILE, 220)
        self.results.setColumnWidth(COL_COUNT, 90)
        self.results.setColumnWidth(COL_LOCATIONS, 360)
        self.results.setAlternatingRowColors(True)
        self.results.cellDoubleClicked.connect(self._on_open_result)

        frame = QWidget()
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.addWidget(self.label_results)
        vbox.addWidget(self.results, 1)
        return frame

    # ------------------------------------------------------------------ #
    # Language & settings
    # ------------------------------------------------------------------ #
    def _apply_ui_language(self):
        self.radio_exact.setText(self.i18n.t("exact"))
        self.radio_fuzzy.setText(self.i18n.t("fuzzy"))

        self.label_folders.setText(self.i18n.t("folders"))
        self.button_add.setText(self.i18n.t("add"))
        self.button_remove.setText(self.i18n.t("remove"))
        self.button_settings.setText(self.i18n.t("settings"))
        self.label_settings.setText(self.i18n.t("settings"))
        self.label_threshold.setText(self.i18n.t("threshold"))
        self.button_start.setText(self.i18n.t("start"))
        self.button_stop.setText(self.i18n.t("stop"))
        self.label_results.setText(self.i18n.t("results"))
        self.input_query.setPlaceholderText(self.i18n.t("search_placeholder"))
        self.status_label.setText("")

        # Refresh localized field labels.
        for child in self.findChildren(QLabel):
            if getattr(child, "i18n_key", None):
                child.setText(self.i18n.t(child.i18n_key))

        # Refresh file-type checkbox labels.
        type_keys = {"filename": "ft_filename", "word": "ft_word",
                     "excel": "ft_excel", "pdf": "ft_pdf", "txt": "ft_txt"}
        for key, check in self.type_boxes.items():
            check.setText(self.i18n.t(type_keys[key]))

        # Refresh result table headers (application language).
        self.results.setHorizontalHeaderLabels([
            self.i18n.t("col_folder"), self.i18n.t("col_file"),
            self.i18n.t("col_count"), self.i18n.t("col_locations"),
        ])
        self.setWindowTitle(self.i18n.t("app_title"))

    def _restore_settings(self):
        settings = self.state["settings"]
        method = settings.get("match_method", "exact")
        if method == "fuzzy":
            self.radio_fuzzy.setChecked(True)
        else:
            self.radio_exact.setChecked(True)
        self._update_method_ui()
        self.slider_threshold.setValue(int(settings.get("fuzzy_threshold", 85)))
        file_types = settings.get("file_types", {})
        for key, check in self.type_boxes.items():
            check.setChecked(bool(file_types.get(key, True)))

        self.radio_fuzzy.toggled.connect(self._on_fuzzy_method_toggled)
        for check in self.type_boxes.values():
            check.toggled.connect(self._save_settings)

    def _update_method_ui(self):
        self.threshold_frame.setVisible(self.radio_fuzzy.isChecked())

    def _on_fuzzy_method_toggled(self, checked):
        self._update_method_ui()
        self._save_settings()

    def _method(self):
        return "fuzzy" if self.radio_fuzzy.isChecked() else "exact"

    def _on_ui_lang_changed(self, code):
        self.i18n.ui_language = code
        self._apply_ui_language()
        self._save_settings()

    def _save_settings(self):
        self.state["settings"].update({
            "match_method": self._method(),
            "fuzzy_threshold": self.slider_threshold.value(),
            "file_types": {k: box.isChecked()
                           for k, box in self.type_boxes.items()},
            "ui_language": self.i18n.ui_language,
        })
        storage.save(self.state)

    def _open_settings(self):
        """Open the application settings dialog (language selection)."""
        self._settings_dialog = SettingsDialog(
            self.i18n, self._on_ui_lang_changed, self)
        self._settings_dialog.exec()

    # ------------------------------------------------------------------ #
    # Folder tree
    # ------------------------------------------------------------------ #
    def _restore_folders(self):
        self._loading_tree = True
        for entry in self.state.get("folders", []):
            path = entry.get("path")
            if path and os.path.isdir(path):
                self._add_tree_item(path, bool(entry.get("checked", True)))
        self._loading_tree = False

    def _add_folder(self):
        path = QFileDialog.getExistingDirectory(self, self.i18n.t("select_folder"))
        if not path:
            return
        path = os.path.normpath(path)
        if not os.path.isdir(path):
            return
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            if root.child(i).data(COL_FOLDER, ROLE_PATH) == path:
                return
        self._loading_tree = True
        self._add_tree_item(path, True)
        self._loading_tree = False
        self._upsert_state_folder(path, True)
        self._save_settings()

    def _add_tree_item(self, path, checked, parent=None):
        item = QTreeWidgetItem()
        item.setText(0, os.path.basename(path) or path)
        item.setToolTip(0, os.path.normpath(path))
        item.setData(0, ROLE_PATH, os.path.normpath(path))
        item.setData(1, ROLE_POPULATED, "0")
        flags = item.flags() | Qt.ItemFlag.ItemIsUserCheckable
        item.setFlags(flags)
        item.setCheckState(0, Qt.CheckState.Checked if checked
                           else Qt.CheckState.Unchecked)
        # Show a collapse/expand arrow whenever the folder has subfolders.
        if self._has_subdirs(path):
            item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        else:
            item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    @staticmethod
    def _has_subdirs(path):
        if not os.path.isdir(path):
            return False
        try:
            return any(os.path.isdir(os.path.join(path, name))
                       for name in os.listdir(path))
        except OSError:
            return False

    def _remove_folder(self):
        selected = self.tree.selectedItems()
        if not selected:
            return
        answer = QMessageBox.question(self, self.i18n.t("app_title"),
                                      self.i18n.t("confirm_remove"))
        if answer != QMessageBox.StandardButton.Yes:
            return
        paths = set()
        for item in selected:
            self._collect_paths(item, paths)
            index = self.tree.indexOfTopLevelItem(item)
            if index >= 0:
                self.tree.takeTopLevelItem(index)
            else:
                parent = item.parent()
                if parent is not None:
                    parent.removeChild(item)
        self.state["folders"] = [f for f in self.state["folders"]
                                 if f.get("path") not in paths]
        self._save_settings()

    def _collect_paths(self, item, acc):
        path = item.data(0, ROLE_PATH)
        if path:
            acc.add(path)
        for i in range(item.childCount()):
            self._collect_paths(item.child(i), acc)

    def _upsert_state_folder(self, path, checked):
        path = os.path.normpath(path)
        for entry in self.state["folders"]:
            if entry.get("path") == path:
                entry["checked"] = checked
                return
        self.state["folders"].append({"path": path, "checked": checked})

    def _on_item_expanded(self, item):
        if self._loading_tree:
            return
        path = item.data(0, ROLE_PATH)
        if not path or item.data(1, ROLE_POPULATED) == "1":
            return
        item.setData(1, ROLE_POPULATED, "1")
        if not os.path.isdir(path):
            return
        try:
            names = sorted(os.listdir(path))
        except OSError:
            return
        self._loading_tree = True
        for name in names:
            child_path = os.path.normpath(os.path.join(path, name))
            if os.path.isdir(child_path):
                checked = self._saved_checked(child_path)
                self._add_tree_item(child_path, checked, item)
        self._loading_tree = False

    def _saved_checked(self, path):
        for entry in self.state["folders"]:
            if entry.get("path") == os.path.normpath(path):
                return bool(entry.get("checked", True))
        return True

    def _on_item_check_changed(self, item, column):
        if self._loading_tree or column != 0:
            return
        path = item.data(0, ROLE_PATH)
        if not path:
            return
        checked = item.checkState(0) == Qt.CheckState.Checked
        self._upsert_state_folder(path, checked)
        self._save_settings()

    def _scan_roots(self):
        folders = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._collect_tree_item(root.child(i), folders)
        return folders

    def _collect_tree_item(self, item, acc):
        path = item.data(0, ROLE_PATH)
        if path:
            enabled = item.checkState(0) == Qt.CheckState.Checked
            acc.append((path, enabled))
        for i in range(item.childCount()):
            self._collect_tree_item(item.child(i), acc)

    # ------------------------------------------------------------------ #
    # Scan control & results
    # ------------------------------------------------------------------ #
    def _on_start(self):
        query = self.input_query.text().strip()
        if not query:
            QMessageBox.warning(self, self.i18n.t("app_title"),
                                self.i18n.t("empty_query"))
            return
        scan_roots = _select_scan_roots(self._scan_roots())
        if not scan_roots:
            QMessageBox.warning(self, self.i18n.t("app_title"),
                                self.i18n.t("no_files"))
            return

        method = self._method()
        file_types = {k: box.isChecked() for k, box in self.type_boxes.items()}
        if not any(file_types.values()):
            QMessageBox.warning(self, self.i18n.t("app_title"),
                                self.i18n.t("no_files"))
            return

        self.results.setRowCount(0)
        self._result_count = 0
        self._set_scanning(True)
        self._start_loading()

        self._worker = ScanWorker(
            scan_roots, query, method, self.slider_threshold.value(),
            file_types, self.i18n)
        self._worker.progress.connect(self._on_progress)
        self._worker.result.connect(self._on_result)
        self._worker.canceled.connect(self._on_canceled)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_stop(self):
        if self._worker is not None:
            self._worker.stop()

    def _on_progress(self, current, total):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
            self.status_label.setText(self.i18n.t("scanning"))
        else:
            self.progress.setRange(0, 0)
            self.status_label.setText(self.i18n.t("no_files"))

    def _on_result(self, row):
        row_index = self.results.rowCount()
        self.results.insertRow(row_index)
        folder_item = QTableWidgetItem(row["folder"])
        file_item = QTableWidgetItem(row["file"])
        file_item.setData(Qt.ItemDataRole.UserRole, row["path"])
        count_item = QTableWidgetItem(str(row["count"]))
        loc_item = QTableWidgetItem(row["locations"])
        self.results.setItem(row_index, COL_FOLDER, folder_item)
        self.results.setItem(row_index, COL_FILE, file_item)
        self.results.setItem(row_index, COL_COUNT, count_item)
        self.results.setItem(row_index, COL_LOCATIONS, loc_item)
        self._result_count += row["count"]
        QApplication.processEvents()

    def _on_canceled(self):
        if not self.isVisible():
            return
        self.status_label.setText(self.i18n.t("canceled"))

    def _on_worker_finished(self):
        self._set_scanning(False)
        self._stop_loading()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait()
        self._worker = None
        if self.results.rowCount() == 0:
            self.status_label.setText(self.i18n.t("no_results"))
        else:
            # Auto-fit the columns to their contents (Excel double-click style).
            self.results.resizeColumnsToContents()
            self.status_label.setText(self.i18n.t(
                "done", count=self._result_count, matches=self.results.rowCount()))

    def _set_scanning(self, active):
        self.button_start.setEnabled(not active)
        self.button_stop.setEnabled(active)

    def _on_open_result(self, row, _col):
        if self._worker is not None:
            return
        item = self.results.item(row, COL_FILE)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ------------------------------------------------------------------ #
    # Progress bar
    # ------------------------------------------------------------------ #
    def _start_loading(self):
        """Reset the progress bar to a busy state before scanning begins."""
        self.progress.setRange(0, 0)
        self.progress.setValue(0)

    def _stop_loading(self):
        """Reset the progress bar to a clean idle state after scanning."""
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def closeEvent(self, event):
        self._shutdown_worker()
        self._save_settings()
        super().closeEvent(event)

    def _shutdown_worker(self):
        """Stop and join the scan worker, tolerating keyboard interrupts."""
        worker = self._worker
        if worker is None or not worker.isRunning():
            self._worker = None
            return
        worker.stop()
        try:
            worker.wait(5000)
        except KeyboardInterrupt:
            worker.stop()
        if worker.isRunning():
            # Last resort: force-terminate so the thread never dangles.
            worker.terminate()
            worker.wait(1000)
        self._worker = None