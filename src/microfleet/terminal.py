from __future__ import annotations

import re

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit


_CSI = re.compile(r"\x1b\[([0-?]*[ -/]*)([@-~])")
_NORMAL = (
    "#11151c", "#e06c75", "#98c379", "#e5c07b",
    "#61afef", "#c678dd", "#56b6c2", "#dce3ee",
)
_BRIGHT = (
    "#626b7a", "#ff8791", "#b4eb89", "#f5d589",
    "#8cbfff", "#dc9cf2", "#7cd7e4", "#ffffff",
)


def _indexed_color(index: int) -> QColor:
    if index < 8:
        return QColor(_NORMAL[index])
    if index < 16:
        return QColor(_BRIGHT[index - 8])
    if index < 232:
        value = index - 16
        levels = (0, 95, 135, 175, 215, 255)
        return QColor(
            levels[value // 36], levels[(value // 6) % 6], levels[value % 6]
        )
    shade = 8 + (index - 232) * 10
    return QColor(shade, shade, shade)


class AnsiTerminalRenderer:
    """Render streamed ANSI SGR text into a read-only Qt text document."""

    def __init__(self) -> None:
        self._pending = ""
        self._pending_cr = False
        self._foreground: QColor | None = None
        self._background: QColor | None = None
        self._bold = False
        self._dim = False
        self._underline = False
        self._inverse = False

    def write(self, widget: QPlainTextEdit, text: str) -> None:
        data = self._pending + text
        self._pending = ""
        cursor = widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        position = 0
        while position < len(data):
            escape = data.find("\x1b", position)
            if escape < 0:
                self._write_text(cursor, data[position:])
                break
            if escape > position:
                self._write_text(cursor, data[position:escape])
            self._flush_carriage_return(cursor)
            if escape + 1 >= len(data):
                self._pending = data[escape:]
                break
            code = data[escape + 1]
            if code == "[":
                match = _CSI.match(data, escape)
                if match is None:
                    self._pending = data[escape:]
                    break
                self._csi(cursor, match.group(1), match.group(2), widget)
                position = match.end()
            elif code == "]":
                bell = data.find("\x07", escape + 2)
                terminator = data.find("\x1b\\", escape + 2)
                choices = [end for end in (bell, terminator) if end >= 0]
                if not choices:
                    self._pending = data[escape:]
                    break
                end = min(choices)
                position = end + (2 if end == terminator else 1)
            elif code in "()%":
                if escape + 2 >= len(data):
                    self._pending = data[escape:]
                    break
                position = escape + 3
            else:
                position = escape + 2
        widget.setTextCursor(cursor)
        widget.ensureCursorVisible()

    def _write_text(self, cursor: QTextCursor, text: str) -> None:
        start = 0
        for index, char in enumerate(text):
            if char not in "\r\n\b\x00\x07":
                continue
            if index > start:
                self._write_run(cursor, text[start:index])
            if char == "\r":
                self._pending_cr = True
            elif char == "\n":
                self._pending_cr = False
                cursor.insertText("\n", self._format())
            elif char == "\b":
                self._flush_carriage_return(cursor)
                cursor.deletePreviousChar()
            start = index + 1
        if start < len(text):
            self._write_run(cursor, text[start:])

    def _write_run(self, cursor: QTextCursor, text: str) -> None:
        self._flush_carriage_return(cursor)
        cursor.insertText(text, self._format())

    def _flush_carriage_return(self, cursor: QTextCursor) -> None:
        if not self._pending_cr:
            return
        self._pending_cr = False
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()

    def _csi(self, cursor: QTextCursor, arguments: str, final: str, widget: QPlainTextEdit) -> None:
        if final == "m":
            self._sgr(arguments)
        elif final == "K":
            mode = arguments or "0"
            if mode in ("0", "2"):
                if mode == "2":
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
        elif final == "J" and arguments in ("2", "3"):
            widget.clear()
            cursor.movePosition(QTextCursor.MoveOperation.End)

    def _sgr(self, arguments: str) -> None:
        values = [int(value) if value.isdigit() else 0 for value in arguments.split(";")]
        index = 0
        while index < len(values):
            code = values[index]
            if code == 0:
                self._foreground = None
                self._background = None
                self._bold = self._dim = self._underline = self._inverse = False
            elif code == 1:
                self._bold = True
            elif code == 2:
                self._dim = True
            elif code == 4:
                self._underline = True
            elif code == 7:
                self._inverse = True
            elif code == 22:
                self._bold = self._dim = False
            elif code == 24:
                self._underline = False
            elif code == 27:
                self._inverse = False
            elif code == 39:
                self._foreground = None
            elif code == 49:
                self._background = None
            elif 30 <= code <= 37:
                self._foreground = _indexed_color(code - 30)
            elif 90 <= code <= 97:
                self._foreground = _indexed_color(code - 90 + 8)
            elif 40 <= code <= 47:
                self._background = _indexed_color(code - 40)
            elif 100 <= code <= 107:
                self._background = _indexed_color(code - 100 + 8)
            elif code in (38, 48) and index + 2 < len(values):
                color = None
                if values[index + 1] == 5:
                    color = _indexed_color(max(0, min(255, values[index + 2])))
                    index += 2
                elif values[index + 1] == 2 and index + 4 < len(values):
                    color = QColor(*[max(0, min(255, value)) for value in values[index + 2:index + 5]])
                    index += 4
                if color is not None:
                    if code == 38:
                        self._foreground = color
                    else:
                        self._background = color
            index += 1

    def _format(self) -> QTextCharFormat:
        foreground = self._foreground or QColor("#c5d0df")
        background = self._background
        if self._inverse:
            foreground, background = background or QColor("#070a0f"), foreground
        if self._dim:
            foreground = foreground.darker(145)
        result = QTextCharFormat()
        result.setForeground(foreground)
        if background is not None:
            result.setBackground(background)
        result.setFontWeight(QFont.Weight.Bold if self._bold else QFont.Weight.Normal)
        result.setFontUnderline(self._underline)
        return result
