"""Ad-hoc verification for the multi-line locations cell.

Not part of the shipped application: run manually with
``python verify_locations.py``.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.i18n import I18n  # noqa: E402
from src.scanner import ScanWorker, _MAX_LOCATIONS  # noqa: E402


def _worker(language, roots=()):
    return ScanWorker(list(roots), "x", "exact", 85,
                      {"filename": True, "word": False, "excel": False,
                       "pdf": False, "txt": True}, I18n(language))


def test_max_locations_is_ten():
    assert _MAX_LOCATIONS == 10, _MAX_LOCATIONS
    print("PASS  at most 10 locations are listed per file")


def test_formats_one_location_per_line():
    worker = _worker("en")
    locations = ["In file name", "Page 3", "Line 12"]
    assert worker._format_locations(locations) == \
        "In file name\nPage 3\nLine 12"
    print("PASS  locations are separated by new lines")


def test_caps_at_ten_and_reports_the_rest():
    worker = _worker("en")
    locations = [f"Page {i}" for i in range(1, 13)]  # 12 matches
    text = worker._format_locations(locations)
    lines = text.split("\n")
    assert len(lines) == 11, lines
    assert lines[:10] == [f"Page {i}" for i in range(1, 11)], lines
    assert lines[10] == "+2 more", lines

    # Exactly ten matches: no extra summary line.
    assert worker._format_locations(locations[:10]) == \
        "\n".join(locations[:10])

    # The summary line follows the language of the interface.
    turkish = _worker("tr")._format_locations(locations)
    assert turkish.split("\n")[-1] == "+2 daha", turkish
    print("PASS  10 locations + '+N more' line when there are more")


def test_scan_reports_multiline_locations():
    """A real scan must produce multi-line, capped location cells."""
    from src import storage
    from src.gui import MainWindow, ROLE_PATH

    app = QApplication.instance() or QApplication(sys.argv)

    with tempfile.TemporaryDirectory() as tmp:
        storage.STORAGE_PATH = os.path.join(tmp, "storage.json")

        folder = os.path.join(tmp, "reports")
        os.makedirs(folder)
        # 15 matching lines -> 15 locations, capped at 10 + summary.
        with open(os.path.join(folder, "many_hits.txt"), "w",
                  encoding="utf-8") as handle:
            handle.write("\n".join(f"needle line {i}" for i in range(1, 16)))

        window = MainWindow()
        window._loading_tree = True
        window._add_tree_item(folder, True)
        window._loading_tree = False

        rows = []
        worker = ScanWorker([os.path.normpath(folder)], "needle", "exact", 85,
                            {"filename": True, "word": False, "excel": False,
                             "pdf": False, "txt": True}, I18n("en"))
        worker.result.connect(rows.append)
        worker.run()

        assert len(rows) == 1, rows
        row = rows[0]
        assert row["count"] == 15, row["count"]
        lines = row["locations"].split("\n")
        assert len(lines) == 11, lines
        assert lines[10] == "+5 more", lines

        # The table row must show the multi-line text and grow with it.
        window._on_result(row)
        item = window.results.item(0, 3)
        assert item is not None
        assert item.text() == row["locations"], item.text()

        single = window.results.sizeHintForRow(0)
        window._on_result(dict(row, locations="Line 1", count=1))
        assert single > window.results.sizeHintForRow(1), single

        delegate = window.results.itemDelegateForColumn(3)
        assert delegate is not None, "no delegate set for the locations column"

        storage.save(window.state)
        window.close()

    print("PASS  results table wraps and grows with the location list")


if __name__ == "__main__":
    test_max_locations_is_ten()
    test_formats_one_location_per_line()
    test_caps_at_ten_and_reports_the_rest()
    test_scan_reports_multiline_locations()
    print("ALL CHECKS PASSED")
