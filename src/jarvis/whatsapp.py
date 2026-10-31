"""WhatsApp Web bridge with an encrypted local contact allowlist."""
from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from .settings import get_secret, save_secret


def contacts() -> list[dict[str, str]]:
    try:
        raw = json.loads(get_secret("whatsapp_contacts") or "[]")
        return [c for c in raw if isinstance(c, dict) and c.get("name") and c.get("phone")]
    except (TypeError, ValueError):
        return []


def save_contacts(items: list[dict[str, str]]) -> None:
    normalized = []
    for item in items:
        name = str(item.get("name", "")).strip()[:80]
        phone = re.sub(r"\D", "", str(item.get("phone", "")))
        if name and 8 <= len(phone) <= 15:
            normalized.append({"name": name, "phone": phone})
    save_secret("whatsapp_contacts", json.dumps(normalized, ensure_ascii=False))


def draft_url(phone: str, message: str) -> str:
    number = re.sub(r"\D", "", phone)
    if not (8 <= len(number) <= 15):
        raise ValueError("O telefone precisa estar em formato internacional com DDI.")
    return "https://web.whatsapp.com/send?" + urlencode({"phone": number, "text": message})
