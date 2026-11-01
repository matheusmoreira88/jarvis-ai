"""Verified GitHub release downloads for the Windows desktop installer."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from platformdirs import user_data_path
from PySide6.QtCore import QThread, Signal

RELEASE_API = "https://api.github.com/repos/matheusmoreira88/jarvis-ai/releases/latest"
UPDATE_DIR = user_data_path("JarvisAI", "Matheus") / "updates"


def _read_url(url: str, *, timeout: int = 30) -> bytes:
    host = (urlparse(url).hostname or "").casefold()
    allowed = ("github.com", "api.github.com", "objects.githubusercontent.com")
    if not any(host == item or host.endswith("." + item) for item in allowed):
        raise RuntimeError("A atualização apontou para um servidor não autorizado.")
    request = Request(url, headers={"User-Agent": "JARVIS-AI-Desktop"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def latest_release() -> dict:
    """Return normalized release metadata and the installer/checksum asset URLs."""
    release = json.loads(_read_url(RELEASE_API, timeout=12).decode("utf-8"))
    assets = release.get("assets") or []
    installer = next((item for item in assets
                      if str(item.get("name", "")).lower().endswith(".exe")), None)
    checksum = next((item for item in assets
                     if str(item.get("name", "")).lower().endswith(".exe.sha256")), None)
    return {
        "tag": str(release.get("tag_name", "")),
        "page_url": str(release.get("html_url", "")),
        "notes": str(release.get("body", "")),
        "installer_url": str((installer or {}).get("browser_download_url", "")),
        "checksum_url": str((checksum or {}).get("browser_download_url", "")),
        "installer_name": str((installer or {}).get("name", "")),
    }


def download_verified_installer(installer_url: str, checksum_url: str,
                                installer_name: str) -> Path:
    """Download an installer and reject it unless its published SHA-256 matches."""
    if not installer_url or not checksum_url or not installer_name.lower().endswith(".exe"):
        raise RuntimeError("A release não contém instalador e checksum compatíveis.")
    checksum_text = _read_url(checksum_url, timeout=20).decode("ascii", errors="strict")
    match = re.search(r"\b([a-fA-F0-9]{64})\b", checksum_text)
    if not match:
        raise RuntimeError("O arquivo de checksum da release é inválido.")
    expected = match.group(1).casefold()
    payload = _read_url(installer_url, timeout=180)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise RuntimeError("O instalador baixado falhou na verificação SHA-256 e foi descartado.")
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPDATE_DIR / Path(installer_name).name
    temporary = destination.with_suffix(destination.suffix + ".download")
    try:
        temporary.write_bytes(payload)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


class UpdateWorker(QThread):
    """Check the public release endpoint without blocking the interface."""
    latest = Signal(dict)
    failed = Signal(str)

    def run(self):
        try:
            self.latest.emit(latest_release())
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateDownloadWorker(QThread):
    """Download and validate a selected release outside the GUI thread."""
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, metadata: dict):
        super().__init__()
        self.metadata = metadata

    def run(self):
        try:
            path = download_verified_installer(
                self.metadata.get("installer_url", ""),
                self.metadata.get("checksum_url", ""),
                self.metadata.get("installer_name", ""),
            )
            self.completed.emit(str(path))
        except Exception as exc:
            self.failed.emit(str(exc))
