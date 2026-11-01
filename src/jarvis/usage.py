"""Local daily Gemini request counters; no telemetry leaves the computer."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import date

from platformdirs import user_config_path

USAGE_FILE = user_config_path("JarvisAI", "Matheus") / "api-usage.json"
_lock = threading.Lock()


def _today() -> str:
    return date.today().isoformat()


def _load() -> dict:
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"date": _today(), "categories": {}}
    if data.get("date") != _today() or not isinstance(data.get("categories"), dict):
        return {"date": _today(), "categories": {}}
    return data


def record(category: str, amount: int = 1) -> None:
    """Record attempted API work locally using an atomic daily counter."""
    if amount <= 0:
        return
    safe_category = "".join(ch for ch in category if ch.isalnum() or ch == "_")[:40]
    if not safe_category:
        return
    with _lock:
        data = _load()
        categories = data["categories"]
        categories[safe_category] = int(categories.get(safe_category, 0)) + int(amount)
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".api-usage-", dir=USAGE_FILE.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, USAGE_FILE)
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(name)
            except OSError:
                pass


def today() -> dict:
    with _lock:
        data = _load()
    categories = {key: int(value) for key, value in data["categories"].items()}
    return {"date": data["date"], "categories": categories,
            "total": sum(categories.values())}
