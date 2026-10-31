"""Parsing of local reminder requests; all dates are stored in the user's local zone."""
from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # February 29 becomes February 28 in a non-leap year.
        return value.replace(year=value.year + years, day=28)


def _unit_delta(value: datetime, amount: int, unit: str) -> datetime:
    unit = unit.lower()
    if unit.startswith("sem"):
        return value + timedelta(weeks=amount)
    if unit.startswith("mes"):
        return _add_months(value, amount)
    if unit.startswith("ano"):
        return _add_years(value, amount)
    return value + timedelta(days=amount)


def parse_reminder_request(text: str, *, now: datetime | None = None) -> dict | None:
    """Recognize common Portuguese dates and lead times, with a five-year limit."""
    now = (now or datetime.now().astimezone()).astimezone()
    normalized = text.casefold().replace("á", "a").replace("ã", "a").replace("â", "a")
    normalized = normalized.replace("é", "e").replace("ê", "e").replace("í", "i")
    normalized = normalized.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    normalized = normalized.replace("ú", "u").replace("ç", "c")
    repeat_rule = None
    for pattern, rule in ((r"\btod[oa]s?\s+os?\s+dias?\b|\btodo\s+dia\b", "daily"),
                          (r"\btoda\s+semana\b", "weekly"),
                          (r"\btodo\s+mes\b", "monthly"),
                          (r"\btodo\s+ano\b", "yearly")):
        if re.search(pattern, normalized):
            repeat_rule = rule
            break

    lead_match = re.search(
        r"\b(\d{1,3})\s*(dia|dias|semana|semanas|mes|meses|ano|anos)\s+antes\b",
        normalized,
    )
    lead_amount = int(lead_match.group(1)) if lead_match else 0
    lead_unit = lead_match.group(2) if lead_match else "dias"

    due: datetime | None = None
    relative = re.search(
        r"\b(?:em|daqui\s+a)\s*(\d{1,4})\s*(dia|dias|semana|semanas|mes|meses|ano|anos)\b",
        normalized,
    )
    if relative:
        due = _unit_delta(now.replace(hour=9, minute=0, second=0, microsecond=0),
                          int(relative.group(1)), relative.group(2))
    elif "depois de amanha" in normalized:
        due = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=2)
    elif re.search(r"\bamanha\b", normalized):
        due = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif re.search(r"\bhoje\b", normalized):
        due = now.replace(hour=9, minute=0, second=0, microsecond=0)

    date_match = re.search(r"\b(?:dia\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b", normalized)
    if date_match:
        day, month = int(date_match.group(1)), int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else now.year
        try:
            candidate = now.replace(year=year, month=month, day=day,
                                    hour=9, minute=0, second=0, microsecond=0)
            if not date_match.group(3) and candidate < now:
                candidate = candidate.replace(year=year + 1)
            due = candidate
        except ValueError:
            return None

    if due is None and repeat_rule:
        due = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if due <= now:
            due += timedelta(days=1)
    if due is None:
        return None

    time_match = re.search(r"\bas\s*(\d{1,2})(?::(\d{2}))?\s*(?:h|horas?)?\b", normalized)
    if time_match:
        hour, minute = int(time_match.group(1)), int(time_match.group(2) or 0)
        if hour > 23 or minute > 59:
            return None
        due = due.replace(hour=hour, minute=minute, second=0, microsecond=0)
    elif due.date() == now.date() and due < now and lead_amount == 0:
        due += timedelta(days=1)

    maximum = _add_years(now, 5)
    if due < now - timedelta(days=1) or due > maximum:
        return None

    remind_at = _unit_delta(due, -lead_amount, lead_unit) if lead_amount else due
    if lead_amount and remind_at > now and due <= now + timedelta(days=1):
        # "One day before, work tomorrow" is a reminder for today at startup.
        remind_at = now.replace(second=0, microsecond=0)

    title = text.strip()
    title = re.sub(r"(?i)^\s*(?:hey\s+)?jarvis[:,]?\s*", "", title)
    title = re.sub(r"(?i)^\s*(?:me\s+)?lemb(?:ra|re)\s+(?:de\s+)?", "", title)
    title = re.sub(r"(?i)^\s*(?:por favor\s+)?", "", title)
    title = re.sub(r"(?i)\b(?:todos?\s+os?\s+dias?|toda\s+semana|todo\s+m[eê]s|todo\s+ano)\b", " ", title)
    title = re.sub(
        r"(?i)\b\d{1,3}\s*(?:dias?|semanas?|mes(?:es)?|anos?)\s+antes\b", " ", title)
    title = re.sub(r"(?i)\b(?:quando\s+voce\s+inicializar|quando\s+iniciar)\b", " ", title)
    title = re.sub(r"(?i)\b(?:pra|para|em)\s+(?:depois\s+de\s+)?amanha\b", " ", title)
    title = re.sub(r"(?i)\bhoje\b|\bamanha\b|\bdepois de amanha\b", " ", title)
    title = re.sub(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{4})?\b", " ", title)
    title = re.sub(r"(?i)\b(?:as?)\s*\d{1,2}(?::\d{2})?\s*(?:h|horas?)?\b", " ", title)
    title = re.sub(r"(?i)\b(?:que\s+)?(?:tem|tenho|vai\s+ter)\b", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" ,.;:-")
    if len(title) < 3:
        title = "Lembrete"

    return {
        "title": title[:180],
        "due_at": due.isoformat(timespec="minutes"),
        "remind_at": remind_at.isoformat(timespec="minutes"),
        "repeat_rule": repeat_rule,
    }
