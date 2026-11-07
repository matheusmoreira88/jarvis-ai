"""Histórico de conversa local em SQLite, fora da pasta do repositório."""
from __future__ import annotations

import sqlite3
import os
import re
import threading
from datetime import datetime
from contextlib import closing, contextmanager
from pathlib import Path
from platformdirs import user_data_path

DB_FILE = user_data_path("JarvisAI", "Matheus") / "memory.sqlite3"
_initialized: set[str] = set()
_schema_lock = threading.Lock()
REQUIRED_TABLES = {"messages", "long_term_memory", "reminders"}
MAX_BACKUP_SIZE_BYTES = 512 * 1024 * 1024


def _initialize(db: sqlite3.Connection) -> None:
    """Create/migrate the schema once per database, rather than on every query."""
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=3000")
    db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, role TEXT, body TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS long_term_memory ("
        "id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS reminders ("
        "id INTEGER PRIMARY KEY, title TEXT NOT NULL, due_at TEXT NOT NULL, "
        "notify_at TEXT NOT NULL, notified_at TEXT, created_at TEXT NOT NULL, "
        "repeat_rule TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS action_audit ("
        "id INTEGER PRIMARY KEY, kind TEXT NOT NULL, outcome TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    if "repeat_rule" not in {row[1] for row in db.execute("PRAGMA table_info(reminders)")}:
        db.execute("ALTER TABLE reminders ADD COLUMN repeat_rule TEXT")
    db.execute("CREATE INDEX IF NOT EXISTS reminders_due_idx ON reminders(notify_at) WHERE notified_at IS NULL")
    db.execute("CREATE INDEX IF NOT EXISTS memory_created_idx ON long_term_memory(created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS reminders_created_idx ON reminders(created_at)")
    # FTS stores an index of the user's notes. The source of truth remains the table above.
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(title, body, content='long_term_memory', content_rowid='id')")
    db.executescript("""
        CREATE TRIGGER IF NOT EXISTS memory_search_insert AFTER INSERT ON long_term_memory BEGIN
            INSERT INTO memory_search(rowid, title, body) VALUES (new.id, new.title, new.body);
        END;
        CREATE TRIGGER IF NOT EXISTS memory_search_update AFTER UPDATE ON long_term_memory BEGIN
            INSERT INTO memory_search(memory_search, rowid, title, body)
            VALUES ('delete', old.id, old.title, old.body);
            INSERT INTO memory_search(rowid, title, body) VALUES (new.id, new.title, new.body);
        END;
        CREATE TRIGGER IF NOT EXISTS memory_search_delete AFTER DELETE ON long_term_memory BEGIN
            INSERT INTO memory_search(memory_search, rowid, title, body)
            VALUES ('delete', old.id, old.title, old.body);
        END;
    """)
    # Existing installations already have memories; rebuild once during migration.
    if db.execute("SELECT COUNT(*) FROM memory_search").fetchone()[0] != db.execute(
            "SELECT COUNT(*) FROM long_term_memory").fetchone()[0]:
        db.execute("INSERT INTO memory_search(memory_search) VALUES ('rebuild')")
    db.commit()


def _connect():
    # O histórico pode guardar detalhes pessoais; no Unix, só a conta atual deve lê-lo.
    DB_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(DB_FILE.parent, 0o700)
    db = sqlite3.connect(DB_FILE, timeout=3)
    try:
        if os.name == "posix":
            os.chmod(DB_FILE, 0o600)
        identity = str(DB_FILE.resolve())
        if identity not in _initialized:
            with _schema_lock:
                if identity not in _initialized:
                    _initialize(db)
                    _initialized.add(identity)
        db.execute("PRAGMA busy_timeout=3000")
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


def audit_action(kind: str, outcome: str) -> None:
    """Record a privacy-safe local action result without prompts, paths or message text."""
    from datetime import datetime, timezone
    safe_kind = re.sub(r"[^a-z0-9_.-]", "_", kind.casefold())[:64] or "unknown"
    safe_outcome = outcome if outcome in {"success", "cancelled", "failed"} else "failed"
    with _connection() as db:
        db.execute(
            "INSERT INTO action_audit(kind, outcome, created_at) VALUES (?, ?, ?)",
            (safe_kind, safe_outcome,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def action_audit_count() -> int:
    with _connection() as db:
        return int(db.execute("SELECT COUNT(*) FROM action_audit").fetchone()[0])


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


def export_database(destination: str | Path) -> Path:
    """Create a consistent SQLite backup even while WAL mode is enabled."""
    target = Path(destination).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with _connection() as source, closing(sqlite3.connect(target)) as output:
        source.backup(output)
    return target


def import_database(source: str | Path) -> Path | None:
    """Validate and atomically restore a memory backup, preserving the old database."""
    incoming = Path(source).resolve()
    if not incoming.is_file() or incoming == DB_FILE.resolve():
        raise ValueError("Escolha um arquivo de backup SQLite diferente do banco atual.")
    # Evita importar acidentalmente um arquivo gigantesco para a memória local.
    if incoming.stat().st_size > MAX_BACKUP_SIZE_BYTES:
        raise ValueError("O backup excede o limite seguro de 512 MB.")
    with closing(sqlite3.connect(
            f"file:{incoming.as_posix()}?mode=ro", uri=True)) as candidate:
        tables = {row[0] for row in candidate.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not REQUIRED_TABLES.issubset(tables):
            raise ValueError("O arquivo não é um backup de memória válido do JARVIS.")
    backup = None
    if DB_FILE.exists():
        backup_dir = DB_FILE.parent / "memory-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = export_database(backup_dir / f"memory-before-import-{stamp}.sqlite3")
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = DB_FILE.with_suffix(".importing")
    try:
        with closing(sqlite3.connect(
                f"file:{incoming.as_posix()}?mode=ro", uri=True)) as candidate, \
             closing(sqlite3.connect(temporary)) as output:
            candidate.backup(output)
        for suffix in ("-wal", "-shm"):
            Path(str(DB_FILE) + suffix).unlink(missing_ok=True)
        temporary.replace(DB_FILE)
        _initialized.discard(str(DB_FILE.resolve()))
        with _connection():
            pass
    finally:
        temporary.unlink(missing_ok=True)
    return backup


def save_memory(title: str, body: str) -> int:
    """Store a user-requested fact indefinitely until the user removes it."""
    from datetime import datetime
    with _connection() as db:
        cursor = db.execute(
            "INSERT INTO long_term_memory(title, body, created_at) VALUES (?, ?, ?)",
            (title.strip() or body[:100], body.strip(), datetime.now().astimezone().isoformat()),
        )
        return int(cursor.lastrowid)


def save_reminder(title: str, due_at: str, notify_at: str,
                  repeat_rule: str | None = None) -> int:
    """Store a dated reminder in UTC so DST and timezone offsets compare correctly."""
    from datetime import datetime, timezone

    def utc_stamp(value: str) -> str:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")

    if repeat_rule not in {None, "daily", "weekly", "monthly", "yearly"}:
        raise ValueError("Recorrência inválida.")

    with _connection() as db:
        cursor = db.execute(
            "INSERT INTO reminders(title, due_at, notify_at, created_at, repeat_rule) "
            "VALUES (?, ?, ?, ?, ?)",
            (title.strip(), utc_stamp(due_at), utc_stamp(notify_at),
             datetime.now(timezone.utc).isoformat(timespec="seconds"), repeat_rule),
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


def mark_reminders_notified(ids: list[int], now: str | None = None) -> None:
    """Mark displayed alerts and schedule the next occurrence of recurring ones."""
    from datetime import datetime, timezone, timedelta
    from .reminders import _add_months, _add_years
    if not ids:
        return
    current = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    stamp = current.isoformat(timespec="seconds")
    placeholders = ",".join("?" for _ in ids)
    with _connection() as db:
        recurring = db.execute(
            f"SELECT title, due_at, notify_at, repeat_rule FROM reminders "
            f"WHERE id IN ({placeholders}) AND notified_at IS NULL AND repeat_rule IS NOT NULL",
            ids,
        ).fetchall()
        db.execute(
            f"UPDATE reminders SET notified_at = ? WHERE id IN ({placeholders}) "
            "AND notified_at IS NULL",
            (stamp, *ids),
        )
        for title, due_stamp, notify_stamp, repeat_rule in recurring:
            due = datetime.fromisoformat(due_stamp)
            advance = {
                "daily": lambda value: value + timedelta(days=1),
                "weekly": lambda value: value + timedelta(weeks=1),
                "monthly": lambda value: _add_months(value, 1),
                "yearly": lambda value: _add_years(value, 1),
            }.get(repeat_rule)
            if advance is None:
                continue
            lead = due - datetime.fromisoformat(notify_stamp)
            due = advance(due)
            # Skip expired cycles after a long period with the app closed.
            for _ in range(4000):
                if due - lead > current:
                    break
                due = advance(due)
            else:
                continue
            db.execute(
                "INSERT INTO reminders(title, due_at, notify_at, created_at, repeat_rule) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, due.isoformat(timespec="seconds"),
                 (due - lead).isoformat(timespec="seconds"), stamp, repeat_rule),
            )


def saved_items(*, query: str = "", limit: int = 100, offset: int = 0) -> list[tuple[str, int, str, str]]:
    """List permanent memories and reminders for the user's memory manager."""
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    pattern = f"%{query.strip()}%"
    with _connection() as db:
        return db.execute(
            "SELECT kind, id, title, detail FROM ("
            "SELECT 'memory' AS kind, id, title, body AS detail, created_at "
            "FROM long_term_memory WHERE title LIKE ? OR body LIKE ? "
            "UNION ALL "
            "SELECT 'reminder' AS kind, id, title, due_at AS detail, created_at "
            "FROM reminders WHERE title LIKE ?) "
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (pattern, pattern, pattern, limit, offset),
        ).fetchall()


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


def context_for_ai(query: str = "", limit: int = 12) -> list[str]:
    """Retrieve relevant old notes and a few recent ones within a bounded context."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connection() as db:
        terms = re.findall(r"\w{3,}", query.casefold(), re.UNICODE)
        terms = list(dict.fromkeys(terms))[:8]
        relevant = []
        if terms:
            expression = " OR ".join('"' + term.replace('"', '') + '"' for term in terms)
            relevant = db.execute(
                "SELECT m.id, m.title, m.body FROM memory_search s "
                "JOIN long_term_memory m ON m.id = s.rowid "
                "WHERE memory_search MATCH ? ORDER BY bm25(memory_search) LIMIT ?",
                (expression, limit),
            ).fetchall()
        recent = db.execute(
            "SELECT id, title, body FROM long_term_memory ORDER BY id DESC LIMIT ?",
            (min(limit, 3),),
        ).fetchall()
        reminders = db.execute(
            "SELECT title, due_at FROM reminders WHERE due_at >= ? "
            "ORDER BY due_at LIMIT ?",
            (now, limit),
        ).fetchall()
    notes = list(dict((row[0], row) for row in relevant + recent).values())[:limit]
    result = [f"Lembrança permanente — {title[:120]}: {body[:650]}"
              for _id, title, body in notes]
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
