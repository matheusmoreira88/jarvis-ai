"""Propostas revisáveis para o próprio código-fonte do JARVIS."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from platformdirs import user_data_path

from .settings import get_secret

SOURCE_ROOT = Path(__file__).resolve().parent
BACKUP_ROOT = user_data_path("JarvisAI", "Matheus") / "source-backups"


def propose_file_update(path: str, request: str) -> str:
    """Pede ao Gemini uma nova versão de um módulo permitido, sem gravar nada."""
    target = Path(path).resolve()
    if target.suffix != ".py" or not target.is_relative_to(SOURCE_ROOT):
        raise ValueError("Só é permitido propor mudanças em arquivos Python de src/jarvis.")
    if not target.is_file() or target.stat().st_size > 200_000:
        raise ValueError("O arquivo não existe ou é grande demais para uma proposta segura.")
    instruction = request.strip()
    if not instruction or len(instruction) > 4_000:
        raise ValueError("Descreva a mudança em até 4.000 caracteres.")
    key = get_secret("gemini")
    if not key:
        raise RuntimeError("Cadastre a chave Gemini em Configurações.")

    from google import genai
    client = genai.Client(api_key=key)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                "Edite o módulo Python abaixo para atender ao pedido. Retorne somente o "
                "arquivo completo, sem cercas Markdown, explicações ou comandos. Preserve "
                "comportamentos não relacionados e não importe nem execute shell.\n\n"
                f"PEDIDO:\n{instruction}\n\nARQUIVO {target.name}:\n"
                f"{target.read_text(encoding='utf-8')}"
            ),
        )
        proposal = (response.text or "").strip()
        if proposal.startswith("```") or not proposal:
            raise RuntimeError("O Gemini não retornou um arquivo Python completo para revisão.")
        return proposal + "\n"
    finally:
        client.close()


def apply_file_update(path: str, proposed_content: str) -> Path:
    """Faz backup e substitui atomicamente um módulo após a confirmação da interface."""
    target = Path(path).resolve()
    if target.suffix != ".py" or not target.is_relative_to(SOURCE_ROOT):
        raise ValueError("Só é permitido alterar arquivos Python de src/jarvis.")
    if not target.is_file() or len(proposed_content) > 250_000:
        raise ValueError("Arquivo ausente ou proposta grande demais.")
    # Erros de sintaxe são detectados antes de tocar no arquivo original.
    compile(proposed_content, str(target), "exec")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = BACKUP_ROOT / f"{target.stem}-{timestamp}.py.bak"
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(target.read_bytes())
    temporary = target.with_suffix(target.suffix + ".new")
    try:
        temporary.write_text(proposed_content, encoding="utf-8")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return backup
