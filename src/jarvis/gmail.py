"""Gmail send-only integration using a user-provided OAuth desktop client."""
from __future__ import annotations

import base64
import os
import tempfile
from email.message import EmailMessage
from pathlib import Path
from platformdirs import user_config_path, user_data_path

CONFIG_DIR = user_config_path("JarvisAI", "Matheus")
CLIENT_FILE = CONFIG_DIR / "gmail-oauth-client.json"
TOKEN_FILE = user_data_path("JarvisAI", "Matheus") / "gmail-token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _write_private(path: Path, content: str) -> None:
    """Grava credenciais por substituição atômica e restringe permissões em POSIX."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.parent.chmod(0o700)
    temporary: Path | None = None
    try:
        # NamedTemporaryFile (mkstemp) creates mode 0600 on POSIX from the outset.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        temporary.replace(path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def install_client_file(source: str) -> None:
    import json
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    if "installed" not in data:
        raise ValueError("Escolha um arquivo OAuth do tipo aplicativo para computador.")
    _write_private(CLIENT_FILE, json.dumps(data))


def send_email(to: str, subject: str, body: str) -> None:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if not CLIENT_FILE.exists():
        raise RuntimeError("Importe primeiro as credenciais OAuth de desktop do Google Cloud.")
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            refresh_request = Request()
            try:
                creds.refresh(refresh_request)
            finally:
                refresh_request.session.close()
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        _write_private(TOKEN_FILE, creds.to_json())
    message = EmailMessage()
    message["To"] = to; message["Subject"] = subject
    message.set_content(body)
    payload = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    try:
        service.users().messages().send(userId="me", body={"raw": payload}).execute()
    finally:
        service.close()
