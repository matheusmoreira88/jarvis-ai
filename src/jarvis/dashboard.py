"""Small custom-painted widgets for the JARVIS command-center HUD."""
from __future__ import annotations

import math
import time
from threading import Lock

from PySide6.QtCore import Qt, QThread, Signal, QRectF, QPointF, QVariantAnimation, QBuffer, QIODevice, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QRadialGradient, QBrush
from PySide6.QtWidgets import QWidget, QSizePolicy


class CoreOrb(QWidget):
    """Paint the central status indicator without a fixed bitmap or decorative text label."""
    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.version = version
        self.state = "ready"
        self.phase = 0.0
        self.motion_enabled = True
        self.setMinimumSize(165, 165)
        self.setMaximumSize(270, 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    def set_state(self, state: str):
        if state != self.state:
            self.state = state
            self.update()

    def set_motion_enabled(self, enabled: bool):
        self.motion_enabled = bool(enabled)
        self.update()

    def _tick(self):
        if self.motion_enabled and self.isVisible():
            self.phase = (self.phase + 0.018) % (2 * math.pi)
            self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) * 0.40
        active = self.state in {"listening", "thinking", "speaking", "observing"}
        pulse = math.sin(self.phase) if self.motion_enabled and active else 0.0
        glow = QRadialGradient(center, radius * 1.28)
        glow.setColorAt(0.0, QColor(24, 186, 221, 78 + int(12 * pulse)))
        glow.setColorAt(0.64, QColor(9, 74, 103, 58))
        glow.setColorAt(1.0, QColor(4, 14, 27, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, radius * 1.28, radius * 1.28)
        painter.setBrush(QColor("#071927"))
        painter.setPen(QPen(QColor("#18455e"), 1))
        painter.drawEllipse(center, radius * 0.87, radius * 0.87)
        for index, fraction in enumerate((0.72, 0.90, 1.05)):
            color = QColor("#42e4f5") if index == 1 else QColor("#245d76")
            painter.setPen(QPen(color, 1.5 if index == 1 else 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius * fraction, radius * fraction)
        for index in range(36):
            angle = index * (2 * math.pi / 36) + (self.phase * 0.13 if self.motion_enabled else 0)
            inner = radius * (0.96 if index % 3 else 0.91)
            outer = radius * 1.02
            painter.setPen(QPen(QColor("#58dbe9" if index % 3 == 0 else "#2a718c"), 1))
            painter.drawLine(QPointF(center.x() + math.cos(angle) * inner,
                                     center.y() + math.sin(angle) * inner),
                             QPointF(center.x() + math.cos(angle) * outer,
                                     center.y() + math.sin(angle) * outer))
        painter.setPen(QColor("#e7fcff"))
        font = self.font(); font.setPixelSize(max(17, int(radius * 0.22))); font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(center.x() - radius, center.y() - 33,
                                radius * 2, 27), Qt.AlignmentFlag.AlignCenter, "J A R V I S")
        painter.setPen(QColor("#63d9ea"))
        font.setPixelSize(10); font.setBold(False); painter.setFont(font)
        label = {"ready": "PRONTO", "listening": "OUVINDO", "thinking": "PENSANDO",
                 "speaking": "FALANDO", "observing": "OBSERVANDO"}.get(self.state, self.state.upper())
        painter.drawText(QRectF(center.x() - radius, center.y() + 2,
                                radius * 2, 20), Qt.AlignmentFlag.AlignCenter, label)
        painter.setPen(QColor("#729aaf"))
        painter.drawText(QRectF(center.x() - radius, center.y() + 24,
                                radius * 2, 20), Qt.AlignmentFlag.AlignCenter,
                         f"AI CORE  ·  v{self.version}")


class DonutGauge(QWidget):
    """A compact CPU/RAM/disk gauge with a live numeric reading."""
    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self.caption = caption
        self.value = 0
        self.setMinimumSize(88, 112)

    def set_value(self, value: float):
        value = max(0, min(100, int(round(value))))
        if value != self.value:
            self.value = value
            self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width() - 18, 88)
        x = (self.width() - side) / 2
        y = 4
        ring = QRectF(x, y, side, side)
        painter.setPen(QPen(QColor("#1a3345"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(ring, 0, 360 * 16)
        painter.setPen(QPen(QColor("#35d5eb"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(ring, 90 * 16, -int(self.value * 3.6 * 16))
        painter.setPen(QColor("#e7f6ff"))
        painter.setFont(self.font())
        painter.drawText(ring, Qt.AlignmentFlag.AlignCenter, f"{self.value}%")
        painter.setPen(QColor("#8098aa"))
        painter.drawText(QRectF(0, y + side + 10, self.width(), 22),
                         Qt.AlignmentFlag.AlignHCenter, self.caption.upper())


class MemoryBrain(QWidget):
    """Neural memory map; the 0–100 fill is a visual milestone, not a storage cap."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.count = 0
        self.display_count = 0.0
        self._fill_animation = None
        self.motion_enabled = True
        self.setMinimumSize(180, 155)

    def set_motion_enabled(self, enabled: bool):
        self.motion_enabled = bool(enabled)
        if not enabled and self._fill_animation:
            self._fill_animation.stop()
            self.display_count = float(self.count)
            self.update()

    def set_memory_count(self, count: int):
        count = max(0, int(count))
        if count == self.count:
            return
        self.count = count
        if not self.motion_enabled:
            self.display_count = float(count)
            self.update()
            return
        if self._fill_animation:
            self._fill_animation.stop()
            self._fill_animation.deleteLater()
        animation = QVariantAnimation(self)
        animation.setDuration(650)
        animation.setStartValue(self.display_count)
        animation.setEndValue(float(self.count))
        animation.valueChanged.connect(self._animate_fill)
        self._fill_animation = animation
        animation.start()

    def _animate_fill(self, value):
        self.display_count = float(value)
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = min((self.width() - 26) / 220, (self.height() - 32) / 156)
        ox = (self.width() - 220 * scale) / 2
        oy = 8
        transform = painter.transform()
        painter.translate(ox, oy)
        painter.scale(scale, scale)

        outline = QPainterPath()
        outline.moveTo(110, 27)
        outline.cubicTo(88, 2, 55, 10, 51, 34)
        outline.cubicTo(23, 25, 8, 52, 24, 72)
        outline.cubicTo(5, 91, 22, 119, 47, 118)
        outline.cubicTo(51, 145, 81, 151, 104, 130)
        outline.lineTo(110, 135)
        outline.cubicTo(134, 151, 165, 144, 170, 119)
        outline.cubicTo(198, 120, 215, 92, 196, 72)
        outline.cubicTo(212, 50, 195, 26, 169, 34)
        outline.cubicTo(163, 10, 132, 2, 110, 27)
        outline.closeSubpath()

        fill = min(1.0, self.display_count / 100.0)
        glow = QRadialGradient(QPointF(110, 80), 120)
        glow.setColorAt(0.0, QColor(36, 210, 235, int(35 + 130 * fill)))
        glow.setColorAt(1.0, QColor(9, 28, 43, 220))
        painter.fillPath(outline, QBrush(glow))
        painter.setPen(QPen(QColor("#38cddd"), 2))
        painter.drawPath(outline)

        # Neural links form a brain-like atlas, with more nodes illuminated as memories grow.
        nodes = [
            (47, 51), (70, 37), (91, 50), (57, 72), (84, 73), (48, 96), (77, 103),
            (91, 123), (132, 43), (153, 52), (173, 69), (135, 74), (160, 89),
            (139, 104), (170, 112), (126, 126), (110, 37), (110, 59), (110, 82),
            (110, 105), (110, 128),
        ]
        links = [(0,1),(1,2),(0,3),(2,4),(3,4),(3,5),(4,6),(5,6),(6,7),
                 (8,9),(9,10),(8,11),(10,12),(11,12),(11,13),(12,14),(13,14),
                 (13,15),(1,16),(2,17),(4,18),(6,19),(7,20),(8,16),(11,17),
                 (13,19),(15,20),(16,17),(17,18),(18,19),(19,20)]
        active_links = int(len(links) * fill)
        painter.setPen(QPen(QColor(52, 221, 238, 35 + int(150 * fill)), 1.2))
        for left, right in links[:active_links]:
            painter.drawLine(QPointF(*nodes[left]), QPointF(*nodes[right]))
        active_nodes = max(2, int(len(nodes) * fill))
        for index, (nx, ny) in enumerate(nodes):
            color = QColor("#51f3ef") if index < active_nodes else QColor("#385869")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(nx, ny), 2.6 if index < active_nodes else 1.7,
                                2.6 if index < active_nodes else 1.7)
        painter.setTransform(transform)


class ScreenFrameStore:
    """Share a recent local frame with the HUD and the slower Gemini stream."""
    def __init__(self):
        self._lock = Lock()
        self._frame = None

    def publish(self, frame: QImage):
        with self._lock:
            self._frame = frame

    def jpeg(self) -> bytes | None:
        with self._lock:
            frame = self._frame
        if frame is None:
            return None
        result = QBuffer()
        result.open(QIODevice.OpenModeFlag.WriteOnly)
        frame.save(result, "JPEG", 72)
        return bytes(result.data())


class ScreenPreviewWorker(QThread):
    """Streams a private local screen preview to the HUD at a smooth cadence."""
    frame = Signal(QImage)
    failed = Signal(str)

    def __init__(self, frame_store: ScreenFrameStore | None = None):
        super().__init__()
        self._active = True
        self.frame_store = frame_store

    def run(self):
        try:
            from mss import mss
            from .vision import selected_monitor
            with mss() as capture:
                monitor = selected_monitor(capture)
                last_cloud_frame = 0.0
                while self._active:
                    started = time.monotonic()
                    shot = capture.grab(monitor)
                    image = QImage(shot.rgb, shot.width, shot.height, shot.width * 3,
                                   QImage.Format.Format_RGB888).copy()
                    if image.isNull():
                        raise RuntimeError("Não foi possível desenhar a prévia da tela.")
                    if self.frame_store is not None and started - last_cloud_frame >= 0.9:
                        self.frame_store.publish(image.scaled(
                            1280, 720, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.FastTransformation))
                        last_cloud_frame = started
                    self.frame.emit(image.scaled(
                        350, 188, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation))
                    self.msleep(max(1, int(100 - (time.monotonic() - started) * 1000)))
        except Exception as exc:
            self.failed.emit(str(exc))

    def stop(self):
        self._active = False
