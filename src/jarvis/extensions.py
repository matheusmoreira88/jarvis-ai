"""Extensões declarativas: novos atalhos sem executar código de terceiros."""
from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_data_path

EXTENSIONS_DIR = user_data_path("JarvisAI", "Matheus") / "extensions"
ALLOWED_COMMAND_PREFIXES = (
    "abrir ", "abrir aplicativo:", "abrir conversa", "abrir mídia",
    "abrir painel", "toca ", "toque ", "reproduza ", "pausar",
    "próxima", "proxima", "tela cheia", "sair da tela cheia", "minimiza",
)


def _valid_command(command: str) -> bool:
    normalized = command.strip().casefold()
    if normalized.startswith("abrir exe:"):
        return False
    return bool(normalized) and normalized.startswith(ALLOWED_COMMAND_PREFIXES)


def load_extensions(directory: Path | None = None) -> tuple[list[dict], list[str]]:
    """Carrega manifestos JSON limitados a frases e comandos já aceitos pelo JARVIS."""
    root = directory or EXTENSIONS_DIR
    root.mkdir(parents=True, exist_ok=True)
    actions: list[dict] = []
    errors: list[str] = []
    for manifest in sorted(root.glob("*.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("enabled", True) is False:
                continue
            name = str(data.get("name") or manifest.stem).strip()[:80]
            entries = data.get("actions", [])
            if not isinstance(entries, list) or len(entries) > 50:
                raise ValueError("a lista actions deve conter no máximo 50 itens")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("cada ação deve ser um objeto")
                phrase = str(entry.get("phrase", "")).strip()[:160]
                command = str(entry.get("command", "")).strip()[:500]
                if not phrase or not _valid_command(command):
                    raise ValueError("frase vazia ou comando fora da lista segura")
                actions.append({"extension": name, "phrase": phrase, "command": command})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{manifest.name}: {exc}")
    return actions, errors


def create_example(directory: Path | None = None) -> Path:
    """Cria um exemplo editável sem substituir um manifesto já existente."""
    root = directory or EXTENSIONS_DIR
    root.mkdir(parents=True, exist_ok=True)
    destination = root / "exemplo.json"
    if not destination.exists():
        destination.write_text(json.dumps({
            "name": "Meus atalhos",
            "enabled": True,
            "actions": [
                {"phrase": "abrir meu navegador", "command": "abrir aplicativo: navegador"}
            ],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination
