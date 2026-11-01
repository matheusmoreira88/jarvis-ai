"""Parse natural-language media requests without depending on the interface."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MediaCommand:
    """A small, UI-independent description of what the media player should do."""

    action: str
    query: str = ""
    fullscreen: bool = False
    window: bool = False
    minimized: bool = False


_SEARCH_PREFIXES = (
    "pesquise no youtube", "pesquisa no youtube", "pesquisar no youtube",
    "busque no youtube", "buscar no youtube", "busca no youtube",
    "procure no youtube", "procurar no youtube", "youtube:",
)
_PLAY_PREFIXES = ("toca ", "toque ", "tocar ", "reproduz ", "reproduza ")
_DISPLAY_SUFFIXES = (
    " em tela cheia", " fullscreen", " full screen", " em janela flutuante",
    " em modo janela", " em janela", " minimiza o player", " minimizada", " minimizado",
)


def parse_media_command(prompt: str) -> MediaCommand | None:
    """Translate one Portuguese media request into a deterministic player command."""
    text = prompt.strip()
    lowered = text.casefold()
    if lowered in {"pausar música", "pausar musica", "continuar música", "continuar musica"}:
        return MediaCommand("pause")
    if lowered in {"próxima música", "proxima musica", "próxima da fila", "proxima da fila"}:
        return MediaCommand("next")

    is_search = lowered.startswith(_SEARCH_PREFIXES + _PLAY_PREFIXES)
    if not is_search and any(term in lowered for term in ("tela cheia", "fullscreen", "full screen")):
        return MediaCommand("fullscreen")
    if not is_search and any(term in lowered for term in (
        "minimiza o player", "minimize player", "minimizar player", "minimizada", "minimizado",
    )):
        return MediaCommand("minimize")
    if any(term in lowered for term in (
        "abre em uma janela", "abrir em janela", "janela flutuante", "abre janela",
    )):
        return MediaCommand("window")

    query = None
    for prefix in _SEARCH_PREFIXES:
        if lowered.startswith(prefix):
            query = text[len(prefix):].strip(" :,-")
            break
    if query is None:
        match = re.match(r"^(?:toca|toque|tocar|reproduz|reproduza)\s+(.*)$", text, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            query = re.sub(
                r"^(?:a\s+)?(?:m[uú]sica|som|can[cç][aã]o)(?:\s+(?:de|do|da))?\s*",
                "", query, flags=re.IGNORECASE,
            )
            query = re.sub(r"\s+no\s+youtube$", "", query, flags=re.IGNORECASE).strip()

    if query is None and lowered in {"abrir youtube", "abre youtube", "abrir música", "abrir musica"}:
        query = ""
    if query is None:
        return None

    wants_fullscreen = any(term in lowered for term in ("tela cheia", "fullscreen", "full screen"))
    wants_window = any(term in lowered for term in ("em janela", "janela flutuante", "modo janela"))
    wants_minimized = "minimiz" in lowered
    for suffix in _DISPLAY_SUFFIXES:
        if query.casefold().endswith(suffix):
            query = query[:-len(suffix)].strip()
    return MediaCommand(
        "search", query=query, fullscreen=wants_fullscreen,
        window=wants_window, minimized=wants_minimized,
    )
