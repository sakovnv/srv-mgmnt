APP_STYLESHEET = r"""
* {
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: #dce3ee;
}
QMainWindow, QDialog, QWidget#root { background: #0b0f16; }
QWidget#sidebar { background: #0e141d; border-right: 1px solid #1d2735; }
QWidget#consolePanel { background: #0a0e14; border-left: 1px solid #1d2735; }
QLabel#brand { font-size: 19px; font-weight: 700; color: #f4f7fb; }
QLabel#eyebrow { color: #6f8096; font-size: 10px; font-weight: 700; }
QLabel#pageTitle { color: #f6f8fc; font-size: 22px; font-weight: 700; }
QLabel#muted, QLabel[muted="true"] { color: #7f8fa5; }
QLabel#sectionTitle { color: #aab6c6; font-size: 11px; font-weight: 700; }
QLabel#statusOnline { color: #4adea2; font-weight: 600; }
QLabel#statusOffline { color: #ef7187; font-weight: 600; }
QLabel#statusConnecting { color: #f7c66b; font-weight: 600; }
QPushButton {
    background: #161f2b; border: 1px solid #273548; border-radius: 7px;
    padding: 7px 12px; color: #d9e1ec;
}
QPushButton:hover { background: #1d2938; border-color: #3b4c63; }
QPushButton:pressed { background: #111923; }
QPushButton#primary { background: #4d6bfe; border-color: #5d78ff; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #5b76ff; }
QPushButton#danger { color: #ff8fa3; }
QPushButton#ghost { background: transparent; border-color: transparent; padding: 5px 8px; }
QPushButton#ghost:hover { background: #192230; border-color: #273548; }
QPushButton#serviceStart, QPushButton#serviceStop, QPushButton#serviceRestart,
QPushButton#serviceStatus, QPushButton#serviceEdit, QPushButton#serviceDelete {
    border-radius: 7px; padding: 0; min-width: 27px; min-height: 26px;
}
QPushButton#serviceStart { background: #13281f; border-color: #285a43; }
QPushButton#serviceStart:hover { background: #1b3d2e; border-color: #58d9a5; }
QPushButton#serviceStop { background: #2d1a23; border-color: #613041; }
QPushButton#serviceStop:hover { background: #482431; border-color: #ef8294; }
QPushButton#serviceRestart { background: #1b2440; border-color: #394b84; }
QPushButton#serviceRestart:hover { background: #29365d; border-color: #8fa6ff; }
QPushButton#serviceStatus { background: #2b271b; border-color: #5b4b2c; }
QPushButton#serviceStatus:hover { background: #413920; border-color: #f0c979; }
QPushButton#serviceEdit { background: #1b2532; border-color: #334459; }
QPushButton#serviceEdit:hover { background: #27364a; border-color: #a8b9d0; }
QPushButton#serviceDelete { background: #241a22; border-color: #4d2e3b; }
QPushButton#serviceDelete:hover { background: #3b2330; border-color: #ef8294; }
QPushButton#serviceStart:pressed, QPushButton#serviceStop:pressed,
QPushButton#serviceRestart:pressed, QPushButton#serviceStatus:pressed,
QPushButton#serviceEdit:pressed, QPushButton#serviceDelete:pressed { background: #0f151d; }
QListWidget {
    background: transparent; border: none; outline: none; padding: 2px;
}
QListWidget::item { border-radius: 8px; padding: 10px 9px; margin: 2px 0; color: #aab6c6; }
QListWidget::item:selected { background: #19243b; color: #eef3ff; }
QListWidget::item:hover:!selected { background: #141c27; }
QTableWidget {
    background: #0f151e; alternate-background-color: #111923; border: 1px solid #202b3a;
    border-radius: 9px; gridline-color: #1b2532; outline: none;
}
QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #192330; }
QTableWidget::item:selected { background: #1b2942; color: #f3f6fb; }
QHeaderView::section {
    background: #121a25; color: #73849a; border: none; border-bottom: 1px solid #253143;
    padding: 7px; font-size: 10px; font-weight: 700;
}
QPlainTextEdit#terminal {
    background: #070a0f; color: #c5d0df; border: 1px solid #1d2836; border-radius: 8px;
    font-family: "Cascadia Mono", "Consolas", monospace; font-size: 12px; padding: 9px;
    selection-background-color: #3653b7;
}
QLineEdit, QSpinBox, QTextEdit, QComboBox {
    background: #111821; border: 1px solid #263346; border-radius: 7px; padding: 7px 9px;
    color: #e1e7ef; selection-background-color: #4564df;
}
QLineEdit:focus, QSpinBox:focus, QTextEdit:focus, QComboBox:focus { border-color: #5872e8; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #131b26; border: 1px solid #29374a; selection-background-color: #263858; }
QDialog { background: #0e141d; }
QDialog QLabel { color: #aeb9c8; }
QSplitter::handle { background: #273548; }
QSplitter::handle:hover { background: #5872e8; }
QScrollBar:vertical { background: #0b1017; width: 9px; margin: 0; }
QScrollBar::handle:vertical { background: #2c3a4d; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #202b3b; color: white; border: 1px solid #394a62; padding: 5px; }
"""
