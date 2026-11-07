"""Small offline check used against both source and the packaged executable."""
from __future__ import annotations


def run_smoke_test() -> None:
    # Import the subsystems most likely to be omitted or broken by packaging.
    from . import memory  # noqa: F401
    from . import providers  # noqa: F401
    from . import tts  # noqa: F401
    from . import vision  # noqa: F401
    from . import computer  # noqa: F401
    from .assistant_state import AssistantState

    if AssistantState.READY.value != "ready":
        raise RuntimeError("Invalid assistant lifecycle configuration")

