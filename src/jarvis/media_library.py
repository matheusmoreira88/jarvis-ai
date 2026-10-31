"""Small persistent list of media searches/URLs; playback stays in the HUD."""
from __future__ import annotations

from .settings import load_settings, save_settings


def favorites() -> list[str]:
    values = load_settings().get("media_favorites", [])
    return [str(value) for value in values if isinstance(value, str)][:100]


def add_favorite(value: str) -> None:
    value = value.strip()[:500]
    if not value:
        raise ValueError("Informe uma música, busca ou URL.")
    settings = load_settings()
    values = favorites()
    if value not in values:
        values.insert(0, value)
    save_settings({**settings, "media_favorites": values[:100]})


def queue() -> list[str]:
    values = load_settings().get("media_queue", [])
    return [str(value) for value in values if isinstance(value, str)][:100]


def enqueue(value: str) -> int:
    value = value.strip()[:500]
    if not value:
        raise ValueError("Informe uma música, busca ou URL.")
    settings = load_settings()
    values = queue()
    values.append(value)
    save_settings({**settings, "media_queue": values[:100]})
    return len(values)


def dequeue() -> str | None:
    settings = load_settings()
    values = queue()
    if not values:
        return None
    value = values.pop(0)
    save_settings({**settings, "media_queue": values})
    return value
