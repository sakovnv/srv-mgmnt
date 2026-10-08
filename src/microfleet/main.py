from __future__ import annotations

import sys
import sqlite3

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from .main_window import MainWindow
from .styles import APP_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MicroFleet")
    app.setOrganizationName("MicroFleet")
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0b0f16"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#dce3ee"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0f151e"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#dce3ee"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#161f2b"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#dce3ee"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#4d6bfe"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(APP_STYLESHEET)
    try:
        window = MainWindow()
    except (OSError, sqlite3.DatabaseError) as exc:
        QMessageBox.critical(
            None, "Не удалось открыть настройки MicroFleet",
            f"Проверьте права на папку config/users рядом с приложением.\n\n{exc}",
        )
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
