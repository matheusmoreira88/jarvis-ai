"""Captura de tela acionada explicitamente pelo usuário."""
from __future__ import annotations

from io import BytesIO
from mss import mss
from PIL import Image
from .settings import load_settings


def selected_monitor(capture, monitor_index: int | None = None):
    """Choose a connected display, falling back to the primary display."""
    index = monitor_index if monitor_index is not None else load_settings().get("screen_monitor", 1)
    if not isinstance(index, int) or index < 1 or index >= len(capture.monitors):
        index = 1
    return capture.monitors[index]


def capture_primary_screen(monitor_index: int | None = None) -> bytes:
    with mss() as capture:
        shot = capture.grab(selected_monitor(capture, monitor_index))
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        stream = BytesIO()
        image.save(stream, format="PNG", optimize=True)
        return stream.getvalue()


def capture_primary_screen_jpeg(monitor_index: int | None = None) -> bytes:
    """Capture a compact JPEG for the live vision API's limited frame rate."""
    with mss() as capture:
        shot = capture.grab(selected_monitor(capture, monitor_index))
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        image.thumbnail((1280, 720), Image.Resampling.LANCZOS)
        stream = BytesIO()
        image.save(stream, format="JPEG", quality=72, optimize=True)
        return stream.getvalue()
