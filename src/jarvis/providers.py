"""Adaptadores de modelos. O provedor de transcrição é separado do modelo de diálogo."""
from __future__ import annotations

from google import genai
from .settings import get_secret


def ask_gemini(prompt: str, history: list[tuple[str, str]]) -> str:
    key = get_secret("gemini")
    if not key:
        raise RuntimeError("Configure a chave Gemini nas preferências.")
    client = genai.Client(api_key=key)
    contents = [{"role": "model" if role == "assistant" else "user", "parts": [{"text": text}]}
                for role, text in history]
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    response = client.models.generate_content(model="gemini-2.5-flash", contents=contents)
    return response.text or "Não recebi uma resposta em texto."
