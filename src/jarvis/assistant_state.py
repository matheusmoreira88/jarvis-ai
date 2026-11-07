"""Single source of truth for the assistant lifecycle shown by the HUD."""
from __future__ import annotations

from enum import Enum


class AssistantState(str, Enum):
    READY = "ready"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    OBSERVING = "observing"
    ERROR = "error"
    STOPPED = "stopped"


ORB_STATE = {
    AssistantState.READY: "ready",
    AssistantState.LISTENING: "listening",
    AssistantState.TRANSCRIBING: "thinking",
    AssistantState.THINKING: "thinking",
    AssistantState.SPEAKING: "speaking",
    AssistantState.OBSERVING: "observing",
    AssistantState.ERROR: "ready",
    AssistantState.STOPPED: "ready",
}


def set_window_state(window, state: AssistantState | str, status: str | None = None) -> None:
    """Update lifecycle, reactor and optional status label through one function."""
    normalized = state if isinstance(state, AssistantState) else AssistantState(state)
    window.assistant_state = normalized
    reactor = getattr(window, "core_orb", None)
    if reactor is not None:
        reactor.set_state(ORB_STATE[normalized])
    if status is not None and getattr(window, "status", None) is not None:
        window.status.setText(status)

