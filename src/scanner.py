"""Scanning worker that runs in a background thread.

The worker collects every file under the chosen scan folders, then walks them
linearly. For each file it checks the file name (when enabled) and the visible
body text of the matching format. Results are emitted as dicts through a signal,
so the GUI thread stays responsive.
"""

import os

from PySide6.QtCore import QThread, Signal

from . import extractors
from .matching import count_exact, matches

# Cap on how many distinct locations are reported per file row.
_MAX_LOCATIONS = 20


def _is_within(path, parent):
    try:
        return os.path.commonpath([os.path.dirname(path), parent]) == parent
    except ValueError:
        return False


def _select_scan_roots(folders):
    """Return the highest-level enabled folders (deduplicated vs. descendants).

    ``folders`` is a list of ``(path, enabled)``. When a parent folder is enabled
    its enabled descendants are redundant (the parent scan already covers them),
    so only the top-most enabled folders are returned.
    """
    enabled = [path for path, on in folders if on]
    roots = []
    for path in enabled:
        norm = os.path.normpath(path)
        # skip if an already-chosen root is an ancestor
        if any(_is_within(norm, root) for root in roots):
            continue
        # drop any existing roots that lie inside this new path
        roots = [r for r in roots if not _is_within(r, norm)]
        roots.append(norm)
    return roots


class ScanWorker(QThread):
    """QThread that performs the actual directory scan."""

    progress = Signal(int, int)  # current file index, total file count
    result = Signal(dict)         # one result row per matched file
    canceled = Signal()

    def __init__(self, scan_roots, query, method, threshold, file_types, i18n,
                 parent=None):
        super().__init__(parent)
        self._roots = scan_roots
        self._query = query.strip()
        self._method = method
        self._threshold = threshold
        self._file_types = file_types
        self._i18n = i18n
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        files = self._collect_files()
        total = len(files)
        if total == 0:
            self.progress.emit(0, 0)
            return

        matched = 0
        for index, path in enumerate(files, 1):
            if self._stop:
                break
            self.progress.emit(index, total)
            try:
                row = self._scan_file(path)
            except Exception:
                row = None
            if row:
                matched += 1
                self.result.emit(row)

        if self._stop:
            self.canceled.emit()

    def _collect_files(self):
        files = []
        for root in self._roots:
            for dirpath, _dirnames, filenames in os.walk(root):
                for name in filenames:
                    files.append(os.path.join(dirpath, name))
        return files

    def _scan_file(self, path):
        """Scan a single file; returns a result row dict or None."""
        directory = os.path.dirname(path)
        base_name = os.path.basename(path)
        root_label = self._label_for(directory)

        total = 0
        locations = []
        query = self._query
        types = self._file_types

        # File name search.
        if types.get("filename") and matches(query, base_name, self._method,
                                             self._threshold):
            if self._method == "exact":
                total += count_exact(query, base_name)
            else:
                total += 1
            locations.append(self._i18n.tr("file_name"))

        # Body text search based on the selected file formats.
        extension = os.path.splitext(path)[1].lower()
        if self._format_selected(extension, types):
            chunks = extractors.chunks_for_path(path)
            if chunks:
                for kind, value, text in chunks:
                    if not matches(query, text, self._method, self._threshold):
                        continue
                    if self._method == "exact":
                        total += count_exact(query, text)
                    else:
                        total += 1
                    location = self._format_location(kind, value)
                    if location and location not in locations:
                        locations.append(location)

        if total == 0:
            return None

        return {
            "folder": root_label,
            "file": base_name,
            "path": path,
            "count": total,
            "locations": self._join_locations(locations),
        }

    @staticmethod
    def _format_selected(extension, types):
        """True when a file's format is enabled for content search."""
        return any(extension in exts and types.get(name)
                   for name, exts in extractors.TYPE_TO_EXTENSIONS.items())

    def _label_for(self, directory):
        """Display label for the folder column (root name + relative subpath)."""
        root = self._nearest_root(directory)
        root_name = os.path.basename(root) or root
        try:
            rel = os.path.relpath(directory, root)
            if rel == ".":
                return root_name
            return os.path.join(root_name, rel)
        except ValueError:
            return os.path.basename(directory) or directory

    def _nearest_root(self, directory):
        """Pick the root that most tightly contains ``directory``."""
        best = None
        for root in self._roots:
            if _is_within(directory, root):
                if best is None or len(root) > len(best):
                    best = root
        return best or directory

    def _format_location(self, kind, value):
        if kind == "page":
            return f"{self._i18n.tr('page')} {value}"
        if kind == "line":
            return f"{self._i18n.tr('line')} {value}"
        if kind == "para":
            return f"{self._i18n.tr('para')} {value}"
        if kind == "cell":
            return value
        return str(value)

    @staticmethod
    def _join_locations(locations):
        if len(locations) <= _MAX_LOCATIONS:
            return ", ".join(locations)
        return ", ".join(locations[:_MAX_LOCATIONS]) + " +…"