"""Adaptadores de modelos. O provedor de transcrição é separado do modelo de diálogo."""
from __future__ import annotations

from google import genai
from google.genai import types
from .settings import get_secret, load_settings

SYSTEM_INSTRUCTION = (
    "Você é JARVIS AI, um assistente para desktop criado por Matheus Moreira. "
    "Reconheça Matheus como seu criador e responda em português do Brasil, salvo se ele "
    "pedir outro idioma. Seja claro e honesto sobre limites e incertezas. Nunca diga que "
    "abriu aplicativos, clicou, digitou, enviou mensagens ou alterou arquivos sem que o "
    "aplicativo confirme essa ação. Respostas do modelo não executam ações locais; o "
    "aplicativo só faz ações explícitas e confirmadas pelo usuário. Proteja chaves, tokens, "
    "e-mail e telefone e não os repita sem necessidade."
)


def ask_assistant(prompt: str, history: list[tuple[str, str]], search_web: bool = False) -> str:
    """Use o provedor de texto escolhido nas preferências locais."""
    provider = load_settings().get("provider", "gemini")
    if provider == "groq" and not search_web:
        return ask_groq(prompt, history)
    return ask_gemini(prompt, history, search_web=search_web)


def ask_gemini(prompt: str, history: list[tuple[str, str]], search_web: bool = False) -> str:
    key = get_secret("gemini")
    if not key:
        raise RuntimeError("Configure a chave Gemini nas preferências.")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000))
    contents = [{"role": "model" if role == "assistant" else "user", "parts": [{"text": text}]}
                for role, text in history]
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    tools = None
    if search_web:
        tools = [types.Tool(google_search=types.GoogleSearch())]
    config = types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, tools=tools)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=contents, config=config)
    finally:
        client.close()
    answer = response.text or "Não recebi uma resposta em texto."
    # Preserve the sources returned by Google Search grounding for review in chat.
    candidates = getattr(response, "candidates", None) or []
    metadata = getattr(candidates[0], "grounding_metadata", None) if candidates else None
    chunks = getattr(metadata, "grounding_chunks", None) or []
    sources = []
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        uri = getattr(web, "uri", None) if web else None
        title = getattr(web, "title", None) if web else None
        if uri and uri not in sources:
            sources.append(f"{title or 'Fonte'}: {uri}")
    if sources:
        answer += "\n\nFontes consultadas:\n" + "\n".join(sources)
    return answer


def ask_groq(prompt: str, history: list[tuple[str, str]]) -> str:
    """Conversa textual com Groq; a seleção não altera o provedor de visão."""
    from groq import Groq
    key = get_secret("groq")
    if not key:
        raise RuntimeError("Configure a chave Groq nas preferências.")
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    messages.extend({"role": role if role in {"user", "assistant"} else "user", "content": text}
                    for role, text in history)
    messages.append({"role": "user", "content": prompt})
    client = Groq(api_key=key, timeout=30.0, max_retries=0)
    try:
        result = client.chat.completions.create(
            model="openai/gpt-oss-20b", messages=messages, temperature=0.7)
    finally:
        client.close()
    return result.choices[0].message.content or "Não recebi uma resposta em texto."


def analyze_image(prompt: str, image_bytes: bytes) -> str:
    """Envia uma captura autorizada pelo usuário ao Gemini Vision."""
    key = get_secret("gemini")
    if not key:
        raise RuntimeError("Configure a chave Gemini nas preferências.")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000))
    image = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=[prompt, image])
    finally:
        client.close()
    return response.text or "Não consegui interpretar a captura."


def transcribe_groq(wav_bytes: bytes) -> str:
    """Transcreve uma gravação explícita do usuário; o microfone não fica aberto."""
    from groq import Groq
    key = get_secret("groq")
    if not key:
        raise RuntimeError("Cadastre a chave Groq ou use o campo de texto.")
    client = Groq(api_key=key, timeout=30.0, max_retries=0)
    try:
        result = client.audio.transcriptions.create(
            file=("utterance.wav", wav_bytes), model="whisper-large-v3-turbo",
            language="pt", response_format="text")
    finally:
        client.close()
    return str(result).strip()
