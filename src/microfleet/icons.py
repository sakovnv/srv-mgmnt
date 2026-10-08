"""Small SVG icons rendered in memory for the service table."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_SHAPES = {
    "start": '<path d="M8 5.5 18.5 12 8 18.5V5.5Z" fill="{color}" stroke="none"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2" fill="{color}" stroke="none"/>',
    "restart": '<path d="M20 11a8 8 0 1 0 .2 3"/><path d="M20 4v7h-7"/>',
    "status": '<circle cx="12" cy="12" r="9"/><path d="M12 10.5v5"/><path d="M12 7.5h.01"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L9 17l-4 1 1-4L16.5 3.5Z"/>',
    "delete": '<path d="M3.5 6h17"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/><path d="M10 10v6M14 10v6"/>',
}


def service_icon(name: str, color: str) -> QIcon:
    """Render an icon at 2x so it stays crisp on high-DPI displays."""
    shape = _SHAPES[name].format(color=color)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.9" '
        'stroke-linecap="round" stroke-linejoin="round">{shape}</svg>'
    ).format(color=color, shape=shape)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError(f"Invalid SVG icon: {name}")
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, 48, 48))
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
