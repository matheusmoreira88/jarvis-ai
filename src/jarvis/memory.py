"""Histórico de conversa local em SQLite, fora da pasta do repositório."""
from __future__ import annotations

import sqlite3
import os
from contextlib import contextmanager
from platformdirs import user_data_path

DB_FILE = user_data_path("JarvisAI", "Matheus") / "memory.sqlite3"


def _connect():
    # O histórico pode guardar detalhes pessoais; no Unix, só a conta atual deve lê-lo.
    DB_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(DB_FILE.parent, 0o700)
    db = sqlite3.connect(DB_FILE)
    try:
        if os.name == "posix":
            os.chmod(DB_FILE, 0o600)
        db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, role TEXT, body TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        return db
    except Exception:
        db.close()
        raise


@contextmanager
def _connection():
    """Fecha o arquivo SQLite em toda operação, inclusive quando há erro."""
    db = _connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def add(role: str, body: str) -> None:
    with _connection() as db:
        db.execute("INSERT INTO messages(role, body) VALUES (?, ?)", (role, body))


def recent(limit: int = 20) -> list[tuple[str, str]]:
    with _connection() as db:
        rows = db.execute("SELECT role, body FROM messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return list(reversed(rows))


def history_page(*, before_id: int | None = None, limit: int = 50) -> list[tuple[int, str, str]]:
    """Lê a conversa mais recente (ou uma página anterior) sem abrir outra sessão."""
    with _connection() as db:
        if before_id is None:
            rows = db.execute(
                "SELECT id, role, body FROM messages ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, role, body FROM messages WHERE id < ? ORDER BY id DESC LIMIT ?",
                (before_id, limit),
            ).fetchall()
    return list(reversed(rows))


def context_recent(limit: int = 20) -> list[tuple[str, str]]:
    """Retorna só turnos de conversa; comandos locais privados nunca vão aos provedores."""
    with _connection() as db:
        rows = db.execute(
            "SELECT role, body FROM messages WHERE role IN ('user', 'assistant') "
            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return list(reversed(rows))


def clear() -> None:
    """Remove all saved messages without deleting the SQLite database itself."""
    with _connection() as db:
        db.execute("DELETE FROM messages")
