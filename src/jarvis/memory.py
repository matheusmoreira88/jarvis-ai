"""Histórico de conversa local em SQLite, fora da pasta do repositório."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from platformdirs import user_data_path

DB_FILE = user_data_path("JarvisAI", "Matheus") / "memory.sqlite3"


def _connect():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_FILE)
    db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, role TEXT, body TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    return db


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
