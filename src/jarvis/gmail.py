"""Gmail send-only integration using a user-provided OAuth desktop client."""
from __future__ import annotations

import base64
from email.message import EmailMessage
from pathlib import Path
from platformdirs import user_config_path, user_data_path

CONFIG_DIR = user_config_path("JarvisAI", "Matheus")
CLIENT_FILE = CONFIG_DIR / "gmail-oauth-client.json"
TOKEN_FILE = user_data_path("JarvisAI", "Matheus") / "gmail-token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def install_client_file(source: str) -> None:
    import json
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    if "installed" not in data:
        raise ValueError("Escolha um arquivo OAuth do tipo aplicativo para computador.")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CLIENT_FILE.write_text(json.dumps(data), encoding="utf-8")


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
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    message = EmailMessage()
    message["To"] = to; message["Subject"] = subject
    message.set_content(body)
    payload = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    service.users().messages().send(userId="me", body={"raw": payload}).execute()
