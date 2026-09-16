"""Ad-hoc verification for the folder checkbox / flat-panel behaviour.

Not part of the shipped application: run manually with ``python verify_checkboxes.py``.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt  # noqa: E402

from src.scanner import _select_scan_roots  # noqa: E402


def test_select_scan_roots_only_checked():
    # Unchecked folders are dropped entirely.
    assert _select_scan_roots([("C:\\a", False), ("C:\\b", True)]) == ["C:\\b"]
    assert _select_scan_roots([("C:\\a", True), ("C:\\b", False)]) == ["C:\\a"]
    assert _select_scan_roots([("C:\\a", False), ("C:\\b", False)]) == []
    # A checked child of an unchecked parent is still scanned.
    assert _select_scan_roots(
        [("C:\\a", False), ("C:\\a\\b", True)]) == ["C:\\a\\b"]
    # A checked parent absorbs its checked descendant (no double scan).
    assert _select_scan_roots(
        [("C:\\a", True), ("C:\\a\\b", True)]) == ["C:\\a"]
    # Unchecked descendants never leak into the scan even under a checked parent
    # when they are the only checked path.
    assert _select_scan_roots(
        [("C:\\a", False), ("C:\\a\\b", False), ("C:\\d", True)]) == ["C:\\d"]
    print("PASS  _select_scan_roots only returns ticked folders")


def test_gui_flat_panel():
    """The real MainWindow must expose a flat list and scan only ticked rows."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from src import storage
    from src.gui import MainWindow, ROLE_PATH

    app = QApplication.instance() or QApplication(sys.argv)

    with tempfile.TemporaryDirectory() as tmp:
        # Never touch the user's real storage.json during verification.
        storage.STORAGE_PATH = os.path.join(tmp, "storage.json")

        parent = os.path.join(tmp, "parent")
        child = os.path.join(parent, "child")
        other = os.path.join(tmp, "other")
        for path in (child, other):
            os.makedirs(path)

        window = MainWindow()
        # Seed the panel with unchecked folders (as a legacy storage.json would).
        window._loading_tree = True
        window._add_tree_item(parent, False)
        window._add_tree_item(other, False)
        window._loading_tree = False

        # 1. Flat panel: expanding must not reveal subfolders.
        window.tree.expandAll()
        root = window.tree.invisibleRootItem()
        assert root.childCount() == 2, root.childCount()
        for i in range(root.childCount()):
            assert root.child(i).childCount() == 0
        assert not window.tree.rootIsDecorated()
        assert not window.tree.itemsExpandable()

        # 2. Nothing ticked -> nothing to scan.
        assert _select_scan_roots(window._scan_roots()) == []

        # 3. Tick only "other" -> only "other" is scanned.
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, ROLE_PATH) == os.path.normpath(other):
                item.setCheckState(0, Qt.CheckState.Checked)
        roots = _select_scan_roots(window._scan_roots())
        assert roots == [os.path.normpath(other)], roots

        # 4. Tick the parent too -> the child stays out (parent covers it).
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, ROLE_PATH) == os.path.normpath(parent):
                item.setCheckState(0, Qt.CheckState.Checked)
        roots = _select_scan_roots(window._scan_roots())
        assert sorted(roots) == sorted([os.path.normpath(parent),
                                        os.path.normpath(other)]), roots

        # 5. Unticking everything again must clear the scan set.
        for i in range(root.childCount()):
            root.child(i).setCheckState(0, Qt.CheckState.Unchecked)
        assert _select_scan_roots(window._scan_roots()) == []

        storage.save(window.state)
        window.close()

    print("PASS  flat panel + only-ticked-folders scanning")


def test_end_to_end_scan_respects_checkboxes():
    """A real ScanWorker must only report files from ticked folders."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from src import storage
    from src.gui import MainWindow, ROLE_PATH
    from src.i18n import I18n
    from src.scanner import ScanWorker

    app = QApplication.instance() or QApplication(sys.argv)

    with tempfile.TemporaryDirectory() as tmp:
        storage.STORAGE_PATH = os.path.join(tmp, "storage.json")

        wanted = os.path.join(tmp, "wanted")
        skipped = os.path.join(tmp, "skipped")
        for path in (wanted, skipped):
            os.makedirs(path)
        # The needle lives in both folders; only "wanted" is ticked.
        for path in (wanted, skipped):
            with open(os.path.join(path, "needle_report.txt"), "w",
                      encoding="utf-8") as handle:
                handle.write("ACME-4711 payment confirmation")

        window = MainWindow()
        window._loading_tree = True
        window._add_tree_item(wanted, True)
        window._add_tree_item(skipped, False)
        window._loading_tree = False

        roots = _select_scan_roots(window._scan_roots())
        assert roots == [os.path.normpath(wanted)], roots

        worker = ScanWorker(roots, "ACME-4711", "exact", 85,
                            {"filename": True, "word": False, "excel": False,
                             "pdf": False, "txt": True}, I18n("en"))
        rows = []
        worker.result.connect(rows.append)
        worker.run()  # run inline instead of starting a thread

        assert len(rows) == 1, rows
        assert rows[0]["path"] == os.path.join(wanted, "needle_report.txt")

        # Now tick the skipped folder too: both folders must be scanned.
        for i in range(window.tree.invisibleRootItem().childCount()):
            item = window.tree.invisibleRootItem().child(i)
            if item.data(0, ROLE_PATH) == os.path.normpath(skipped):
                item.setCheckState(0, Qt.CheckState.Checked)
        roots = _select_scan_roots(window._scan_roots())
        assert sorted(roots) == sorted([os.path.normpath(wanted),
                                        os.path.normpath(skipped)]), roots

        worker = ScanWorker(roots, "ACME-4711", "exact", 85,
                            {"filename": True, "word": False, "excel": False,
                             "pdf": False, "txt": True}, I18n("en"))
        rows = []
        worker.result.connect(rows.append)
        worker.run()
        assert len(rows) == 2, rows
        assert {r["path"] for r in rows} == {
            os.path.join(wanted, "needle_report.txt"),
            os.path.join(skipped, "needle_report.txt"),
        }

        storage.save(window.state)
        window.close()

    print("PASS  end-to-end scan skips unticked folders")


if __name__ == "__main__":
    test_select_scan_roots_only_checked()
    test_gui_flat_panel()
    test_end_to_end_scan_respects_checkboxes()
    print("ALL CHECKS PASSED")
