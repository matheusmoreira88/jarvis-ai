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
        db.execute(
            "CREATE TABLE IF NOT EXISTS long_term_memory ("
            "id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS reminders ("
            "id INTEGER PRIMARY KEY, title TEXT NOT NULL, due_at TEXT NOT NULL, "
            "notify_at TEXT NOT NULL, notified_at TEXT, created_at TEXT NOT NULL)"
        )
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


def save_memory(title: str, body: str) -> int:
    """Store a user-requested fact indefinitely until the user removes it."""
    from datetime import datetime
    with _connection() as db:
        cursor = db.execute(
            "INSERT INTO long_term_memory(title, body, created_at) VALUES (?, ?, ?)",
            (title.strip() or body[:100], body.strip(), datetime.now().astimezone().isoformat()),
        )
        return int(cursor.lastrowid)


def save_reminder(title: str, due_at: str, notify_at: str) -> int:
    """Store a dated reminder in UTC so DST and timezone offsets compare correctly."""
    from datetime import datetime, timezone

    def utc_stamp(value: str) -> str:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")

    with _connection() as db:
        cursor = db.execute(
            "INSERT INTO reminders(title, due_at, notify_at, created_at) VALUES (?, ?, ?, ?)",
            (title.strip(), utc_stamp(due_at), utc_stamp(notify_at),
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        return int(cursor.lastrowid)


def due_reminders(now: str | None = None) -> list[tuple[int, str, str]]:
    """Return one-shot reminders whose alert time has arrived and was not shown yet."""
    from datetime import datetime, timezone
    stamp = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connection() as db:
        rows = db.execute(
            "SELECT id, title, due_at FROM reminders "
            "WHERE notified_at IS NULL AND notify_at <= ? ORDER BY notify_at, id",
            (stamp,),
        ).fetchall()
    return rows


def mark_reminders_notified(ids: list[int]) -> None:
    """Mark alerts before showing them so a restart cannot duplicate the same notification."""
    from datetime import datetime, timezone
    if not ids:
        return
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    placeholders = ",".join("?" for _ in ids)
    with _connection() as db:
        db.execute(
            f"UPDATE reminders SET notified_at = ? WHERE id IN ({placeholders})",
            (stamp, *ids),
        )


def saved_items() -> list[tuple[str, int, str, str]]:
    """List permanent memories and reminders for the user's memory manager."""
    with _connection() as db:
        notes = db.execute(
            "SELECT id, title, body FROM long_term_memory ORDER BY id DESC"
        ).fetchall()
        reminders = db.execute(
            "SELECT id, title, due_at FROM reminders ORDER BY due_at DESC, id DESC"
        ).fetchall()
    items = [
        ("memory", row_id, title, body)
        for row_id, title, body in notes
    ]
    items.extend(
        ("reminder", row_id, title, due_at)
        for row_id, title, due_at in reminders
    )
    return items


def delete_saved_item(kind: str, item_id: int) -> None:
    """Delete a selected personal note or reminder; table names are fixed here."""
    table = {"memory": "long_term_memory", "reminder": "reminders"}.get(kind)
    if table is None:
        raise ValueError("Tipo de memória inválido.")
    with _connection() as db:
        db.execute(f"DELETE FROM {table} WHERE id = ?", (int(item_id),))


def clear_long_term_memory() -> None:
    """Remove only explicit memories and reminders, leaving conversation history intact."""
    with _connection() as db:
        db.execute("DELETE FROM long_term_memory")
        db.execute("DELETE FROM reminders")


def long_term_count() -> int:
    with _connection() as db:
        notes = db.execute("SELECT COUNT(*) FROM long_term_memory").fetchone()[0]
        reminders = db.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
    return int(notes + reminders)


def context_for_ai(limit: int = 12) -> list[str]:
    """Return a small dated context block for the selected cloud model."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connection() as db:
        notes = db.execute(
            "SELECT title, body FROM long_term_memory ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        reminders = db.execute(
            "SELECT title, due_at FROM reminders WHERE due_at >= ? "
            "ORDER BY due_at LIMIT ?",
            (now, limit),
        ).fetchall()
    result = [f"Lembrança permanente — {title}: {body}" for title, body in reversed(notes)]
    result.extend(
        f"Lembrete futuro — {title}, vence em {due_at}"
        for title, due_at in reminders
    )
    return result


def pending_reminder_count() -> int:
    """Count reminders that are still upcoming and have not been notified."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connection() as db:
        count = db.execute(
            "SELECT COUNT(*) FROM reminders WHERE due_at > ? AND notified_at IS NULL",
            (now,),
        ).fetchone()[0]
    return int(count)
