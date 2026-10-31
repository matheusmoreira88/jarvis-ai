"""Preferências locais; segredos ficam no cofre do sistema, nunca em texto puro."""
from __future__ import annotations

import json
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
    """Grava só preferências pessoais e contato; permissões ficam restritas ao usuário."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")


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
