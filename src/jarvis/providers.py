"""Adaptadores de modelos. O provedor de transcrição é separado do modelo de diálogo."""
from __future__ import annotations

from google import genai
from google.genai import types
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


def analyze_image(prompt: str, image_bytes: bytes) -> str:
    """Envia uma captura sob demanda ao Gemini Vision, nunca em loop automático."""
    key = get_secret("gemini")
    if not key:
        raise RuntimeError("Configure a chave Gemini nas preferências.")
    client = genai.Client(api_key=key)
    image = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=[prompt, image])
    return response.text or "Não consegui interpretar a captura."


def transcribe_groq(wav_bytes: bytes) -> str:
    """Transcreve uma gravação explícita do usuário; o microfone não fica aberto."""
    from groq import Groq
    key = get_secret("groq")
    if not key:
        raise RuntimeError("Cadastre a chave Groq ou use o campo de texto.")
    client = Groq(api_key=key)
    result = client.audio.transcriptions.create(
        file=("utterance.wav", wav_bytes), model="whisper-large-v3-turbo",
        language="pt", response_format="text")
    return str(result).strip()
