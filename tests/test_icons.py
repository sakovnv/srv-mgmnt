from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from microfleet.icons import service_icon


def test_service_svg_icons_use_the_full_canvas(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    for name in ("start", "stop", "restart", "status", "edit", "delete"):
        image = service_icon(name, "#ffffff").pixmap(QSize(24, 24)).toImage()
        pixels = [
            (x, y)
            for y in range(image.height())
            for x in range(image.width())
            if image.pixelColor(x, y).alpha() > 20
        ]
        assert pixels, name
        xs, ys = zip(*pixels)
        assert min(xs) < image.width() * 0.4, name
        assert max(xs) > image.width() * 0.6, name
        assert min(ys) < image.height() * 0.4, name
        assert max(ys) > image.height() * 0.6, name
