"""Registra e remove o início automático por usuário."""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

APP_ID = "JarvisAI"


def set_enabled(enabled: bool) -> None:
    os_name = platform.system()
    if os_name == "Windows":
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            if enabled:
                pythonw = Path(sys.executable).with_name("pythonw.exe")
                executable = str(pythonw if pythonw.exists() else sys.executable)
                winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ,
                                  f'"{executable}" -m jarvis --background')
            else:
                try: winreg.DeleteValue(key, APP_ID)
                except FileNotFoundError: pass
        return
    if os_name == "Linux":
        entry = Path.home() / ".config" / "autostart" / "jarvis-ai.desktop"
        if enabled:
            entry.parent.mkdir(parents=True, exist_ok=True)
            python_path = sys.executable.replace("\\", "\\\\").replace('"', '\\"')
            entry.write_text("[Desktop Entry]\nType=Application\nName=JARVIS AI\n"
                             f'Exec="{python_path}" -m jarvis --background\n'
                             "X-GNOME-Autostart-enabled=true\n", encoding="utf-8")
        else: entry.unlink(missing_ok=True)
        return
    raise NotImplementedError("O início automático ainda não está disponível neste sistema.")
