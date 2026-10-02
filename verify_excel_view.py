"""Ad-hoc verification for the Excel Quick View window.

Not part of the shipped application: run manually with
``python verify_excel_view.py``.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src import excel_view  # noqa: E402
from src.i18n import I18n  # noqa: E402


def _make_book(path):
    """A workbook with two matching sheets, one empty sheet and noise rows."""
    from openpyxl import Workbook

    book = Workbook()
    first = book.active
    first.title = "Musteriler"
    first.append(["Musteri No", "Ad", "Sehir"])       # header row (row 1)
    first.append(["1001", "Ahmet", "Ankara"])         # no match
    first.append(["1002", "needle Ayse", "Izmir"])    # match -> row 3
    first.append(["1003", "Mehmet", "needle Bursa"])  # match -> row 4
    first.append(["1004", "Zeynep", "Istanbul"])      # no match

    second = book.create_sheet("Stok")
    second.append(["Kod", "Urun", "Adet"])        # header row (row 1)
    second.append(["S1", "Kalem", "5"])           # no match
    second.append(["S2", "needle Defter", "12"])  # match -> row 3

    # A sheet without any match must never appear in the Quick View.
    third = book.create_sheet("Bos")
    third.append(["A", "B", "C"])
    third.append(["x", "y", "z"])

    book.save(path)
    return path


def test_load_matches_filters_sheets_and_rows():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_book(os.path.join(tmp, "book.xlsx"))
        sheets = excel_view.load_matches(path, "needle", "exact", 85)

        # Only the two sheets that contain a match are returned.
        assert set(sheets) == {"Musteriler", "Stok"}, list(sheets)

        first = sheets["Musteriler"]
        # Excel's first row is used as the column titles (no A/B/C letters).
        assert first["headers"] == ["Musteri No", "Ad", "Sehir"], \
            first["headers"]
        # Only the two matching rows, with their real Excel row numbers.
        assert [r["row"] for r in first["rows"]] == [3, 4], first["rows"]
        assert first["rows"][0]["values"] == ["1002", "needle Ayse", "Izmir"]
        assert first["rows"][0]["hits"] == [1], first["rows"][0]
        assert first["rows"][1]["hits"] == [2], first["rows"][1]

        second = sheets["Stok"]
        assert [r["row"] for r in second["rows"]] == [3], second["rows"]
    print("PASS  only matching sheets/rows are returned with the header row")


def test_quick_view_shows_only_matching_sheets():
    QApplication.instance() or QApplication(sys.argv)
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_book(os.path.join(tmp, "book.xlsx"))
        dialog = excel_view.ExcelQuickView(path, "needle", "exact", 85,
                                           I18n("tr"))
        try:
            assert dialog.sheet_names == ["Musteriler", "Stok"], \
                dialog.sheet_names
            # Tabs sit at the bottom, like Excel's sheet bar.
            from PySide6.QtWidgets import QTabWidget
            assert dialog.tabs.tabPosition() == QTabWidget.TabPosition.South

            table = dialog.tabs.widget(0).table
            # Row-number column plus the three header columns.
            assert table.columnCount() == 4, table.columnCount()
            assert table.horizontalHeaderItem(0).text() == "#"
            assert table.horizontalHeaderItem(1).text() == "Musteri No"
            assert table.rowCount() == 2, table.rowCount()
            assert table.item(0, 0).text() == "3"
            # The matched cell carries the highlight brush and bold text.
            assert table.item(0, 2).font().bold()
            # A non-matching cell in a matched row is not highlighted.
            assert not table.item(0, 3).font().bold()
        finally:
            dialog.close()
    print("PASS  Quick View lists only matching sheets and highlights hits")



def test_geometry_is_90_percent_and_centred():
    QApplication.instance() or QApplication(sys.argv)
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_book(os.path.join(tmp, "book.xlsx"))
        dialog = excel_view.ExcelQuickView(path, "needle", "exact", 85,
                                           I18n("en"))
        try:
            dialog.show()
            screen = dialog.screen() or QApplication.primaryScreen()
            available = screen.availableGeometry()
            geometry = dialog.frameGeometry()
            # 90% of the screen, within a small tolerance for window frames.
            assert abs(geometry.width() - int(available.width() * 0.9)) <= 6, \
                (geometry.width(), available.width())
            assert abs(geometry.height() - int(available.height() * 0.9)) <= 6, \
                (geometry.height(), available.height())
            # Fully inside the available screen area (never off-screen).
            assert available.contains(geometry), (geometry, available)
            # Centred horizontally.
            assert abs(geometry.center().x() - available.center().x()) <= 6
        finally:
            dialog.close()
    print("PASS  Quick View fills 90% of the screen and stays centred")


def test_open_result_asks_for_excel_and_keeps_other_types():
    from src import storage
    from src.gui import MainWindow

    QApplication.instance() or QApplication(sys.argv)

    calls = []
    original = QDesktopServices.openUrl
    QDesktopServices.openUrl = staticmethod(lambda url: calls.append(url))

    # Record whether the Quick View path was taken.
    opened = []

    try:
        with tempfile.TemporaryDirectory() as tmp:
            storage.STORAGE_PATH = os.path.join(tmp, "storage.json")
            path = _make_book(os.path.join(tmp, "book.xlsx"))
            txt_path = os.path.join(tmp, "notes.txt")
            with open(txt_path, "w", encoding="utf-8") as handle:
                handle.write("needle here\n")

            window = MainWindow()
            window._last_query = "needle"
            window._last_method = "exact"
            window._last_threshold = 85
            window._open_quick_view = lambda p: opened.append(p)

            window._on_result({"folder": "f", "file": "book.xlsx",
                               "path": path, "count": 1,
                               "locations": "Musteriler!B3"})
            window._on_result({"folder": "f", "file": "notes.txt",
                               "path": txt_path, "count": 1,
                               "locations": "Line 1"})

            # Excel row answered with "Excel'de Ac": opened externally.
            window._ask_open_choice = lambda p: "excel"
            window._on_open_result(0, 0)
            assert opened == [], "Quick View must not open when Excel was chosen"
            assert len(calls) == 1, calls
            assert os.path.samefile(calls[0].toLocalFile(), path), calls

            # Excel row answered with Quick View: no external open.
            window._ask_open_choice = lambda p: "quick_view"
            window._on_open_result(0, 0)
            assert opened == [path], opened
            assert len(calls) == 1, calls

            # A dismissed question leaves the file untouched.
            window._ask_open_choice = lambda p: None
            window._on_open_result(0, 0)
            assert len(calls) == 1 and opened == [path], (calls, opened)

            # Non-Excel rows open directly, without any question.
            asked = []
            window._ask_open_choice = lambda p: asked.append(p) or None
            window._on_open_result(1, 0)
            assert asked == [], "no question for non-Excel files"
            assert len(calls) == 2, calls
            assert os.path.samefile(calls[1].toLocalFile(), txt_path), calls

            window.close()
    finally:
        QDesktopServices.openUrl = original
    print("PASS  Excel double-click asks, other formats open directly")


if __name__ == "__main__":
    test_load_matches_filters_sheets_and_rows()
    test_quick_view_shows_only_matching_sheets()
    test_geometry_is_90_percent_and_centred()
    test_open_result_asks_for_excel_and_keeps_other_types()
    print("ALL CHECKS PASSED")
