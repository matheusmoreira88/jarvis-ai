"""Privacy-safe support report for GitHub Issues."""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, memory
from .local_wake import MODEL_NAME, MODEL_ROOT, _valid_model
from .settings import get_secret, load_settings

SAFE_SETTING_KEYS = (
    "hands_free_enabled", "live_vision_enabled", "reduce_motion",
    "share_long_term_memory", "clap_enabled", "screen_monitor",
    "activation_mode", "provider", "setup_completed",
)


def build_report() -> dict:
    """Collect useful state without paths, credentials, contacts, or user content."""
    settings = load_settings()
    safe_settings = {key: settings.get(key) for key in SAFE_SETTING_KEYS if key in settings}
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "jarvis_version": __version__,
        "packaged": bool(getattr(sys, "frozen", False)),
        "python_version": platform.python_version(),
        "operating_system": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "settings": safe_settings,
        "configured": {
            "gemini_key": bool(get_secret("gemini")),
            "gmail_oauth_client": False,
            "personal_email": bool(get_secret("user_email")),
            "personal_phone": bool(get_secret("user_phone")),
        },
        "counts": {
            "quick_actions": len(settings.get("quick_actions", [])),
            "routines": len(settings.get("routines", [])),
            "memories": 0,
        },
        "voice_model": {
            "name": MODEL_NAME,
            "installed": _valid_model(MODEL_ROOT / MODEL_NAME),
        },
        "database": {"exists": memory.DB_FILE.exists(), "size_bytes": 0},
    }
    try:
        from .gmail import CLIENT_FILE
        report["configured"]["gmail_oauth_client"] = CLIENT_FILE.exists()
    except Exception:
        pass
    try:
        report["counts"]["memories"] = memory.long_term_count()
        if memory.DB_FILE.exists():
            report["database"]["size_bytes"] = memory.DB_FILE.stat().st_size
    except Exception as exc:
        report["database"]["status"] = f"unavailable: {type(exc).__name__}"
    try:
        import PySide6
        report["pyside_version"] = PySide6.__version__
    except Exception:
        report["pyside_version"] = "unavailable"
    return report


def export_report(destination: str | Path) -> Path:
    target = Path(destination).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_report(), ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return target
