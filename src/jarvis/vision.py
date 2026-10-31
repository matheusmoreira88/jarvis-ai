"""Captura de tela acionada explicitamente pelo usuário."""
from __future__ import annotations

from io import BytesIO
from mss import mss
from PIL import Image


def capture_primary_screen() -> bytes:
    with mss() as capture:
        shot = capture.grab(capture.monitors[1])
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        stream = BytesIO()
        image.save(stream, format="PNG", optimize=True)
        return stream.getvalue()


def capture_primary_screen_jpeg() -> bytes:
    """Capture a compact JPEG for the live vision API's limited frame rate."""
    with mss() as capture:
        shot = capture.grab(capture.monitors[1])
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        image.thumbnail((1280, 720), Image.Resampling.LANCZOS)
        stream = BytesIO()
        image.save(stream, format="JPEG", quality=72, optimize=True)
        return stream.getvalue()
