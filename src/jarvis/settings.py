"""Preferências locais; segredos ficam no cofre do sistema, nunca em texto puro."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from platformdirs import user_config_path

APP_NAME = "JarvisAI"
CONFIG_DIR = user_config_path(APP_NAME, "Matheus")
CONFIG_FILE = CONFIG_DIR / "settings.json"


def load_settings() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(values: dict) -> None:
    """Salva preferências sem deixar um JSON meio escrito após uma interrupção."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(CONFIG_DIR, 0o700)

    # O arquivo temporário fica ao lado do definitivo para que a troca seja atômica.
    descriptor, temp_name = tempfile.mkstemp(prefix=".settings-", dir=CONFIG_DIR)
    temp_file = Path(temp_name)
    try:
        if os.name == "posix":
            os.chmod(temp_file, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(values, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_file, CONFIG_FILE)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temp_file.unlink(missing_ok=True)
        raise


def save_secret(name: str, value: str) -> None:
    import keyring
    if not value.strip():
        try:
            keyring.delete_password(APP_NAME, name)
        except keyring.errors.PasswordDeleteError:
            pass
    else:
        keyring.set_password(APP_NAME, name, value.strip())


def get_secret(name: str) -> str | None:
    import keyring
    return keyring.get_password(APP_NAME, name)
