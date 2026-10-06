from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from microfleet.terminal import AnsiTerminalRenderer


def test_ansi_colors_survive_split_ssh_packets(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    widget = QPlainTextEdit()
    renderer = AnsiTerminalRenderer()
    renderer.write(widget, "plain \x1b[3")
    renderer.write(widget, "2mgreen\x1b[0m normal")
    assert widget.toPlainText() == "plain green normal"
    cursor = QTextCursor(widget.document())
    cursor.setPosition(7)
    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
    assert cursor.charFormat().foreground().color().name() == "#98c379"
    cursor.setPosition(13)
    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
    assert cursor.charFormat().foreground().color().name() == "#c5d0df"


def test_truecolor_and_256_color(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    widget = QPlainTextEdit()
    renderer = AnsiTerminalRenderer()
    renderer.write(widget, "\x1b[38;2;12;34;56mT\x1b[38;5;196mR")
    assert widget.toPlainText() == "TR"
    cursor = QTextCursor(widget.document())
    cursor.setPosition(0)
    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
    assert cursor.charFormat().foreground().color().name() == "#0c2238"
    cursor.setPosition(1)
    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
    assert cursor.charFormat().foreground().color().name() == "#ff0000"
