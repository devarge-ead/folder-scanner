"""Application entry point for the built executable."""

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .gui import MainWindow, resource_path

APP_STYLESHEET = """
QPushButton {
    background-color: #043c59;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
}
QPushButton:hover { background-color: #0e5470; }
QPushButton:pressed { background-color: #032f45; }
QPushButton:disabled { background-color: #8ba8b8; }
QLabel#fieldLabel {
    font-weight: 600;
    color: #043c59;
}
QHeaderView::section {
    background-color: #e6eef2;
    color: #043c59;
    padding: 4px 8px;
    border: none;
    border-right: 1px solid #d0dde3;
}
"""


def main() -> int:
    import signal

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    icon_path = resource_path("assets/app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    def _handle_sigint(*_args):
        # Close the window (stops the scan worker cleanly) then quit the loop.
        window.close()
        app.quit()

    try:
        signal.signal(signal.SIGINT, _handle_sigint)
    except (ValueError, OSError):
        # Signal handling requires the main thread; ignore on unsupported setups.
        pass

    try:
        return app.exec()
    except KeyboardInterrupt:
        window.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())