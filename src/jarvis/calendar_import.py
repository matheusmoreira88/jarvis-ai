"""Import simple iCalendar events as local reminders one day beforehand."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _date(value: str, key: str, local_zone) -> datetime:
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").replace(hour=9, tzinfo=local_zone)
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
    for part in key.split(";")[1:]:
        if part.upper().startswith("TZID="):
            zone = part.split("=", 1)[1]
            try:
                return parsed.replace(tzinfo=ZoneInfo(zone))
            except ZoneInfoNotFoundError as exc:
                raise ValueError(f"Fuso horário desconhecido: {zone}") from exc
    return parsed.replace(tzinfo=local_zone)


def import_events(path: str, *, now: datetime | None = None) -> tuple[list[dict], int]:
    """Return future VEVENTs and a count of skipped entries without modifying memory."""
    source = Path(path)
    if source.suffix.lower() != ".ics" or source.stat().st_size > 2_000_000:
        raise ValueError("Escolha um arquivo .ics de até 2 MB.")
    now = now or datetime.now().astimezone()
    local_zone = now.tzinfo
    entries: list[dict] = []
    skipped = 0
    current: dict[str, str] | None = None
    for line in _unfold(source.read_text(encoding="utf-8-sig")):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            try:
                date_key = next(key for key in current if key.startswith("DTSTART"))
                due = _date(current[date_key], date_key, local_zone)
                title = current["SUMMARY"].replace("\\,", ",").replace("\\n", " ").strip()
                if not title or due <= now or len(entries) >= 500:
                    skipped += 1
                else:
                    notify = max(now, due - timedelta(days=1))
                    entries.append({"title": title[:180], "due_at": due.isoformat(),
                                    "remind_at": notify.isoformat()})
            except (KeyError, StopIteration, ValueError):
                skipped += 1
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.upper()] = value
    return entries, skipped
