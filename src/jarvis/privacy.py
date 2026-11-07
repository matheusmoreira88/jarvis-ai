"""Central privacy-profile policy used by voice, memory, vision and control."""
from __future__ import annotations


VALID_PROFILES = {"balanced", "restricted", "connected"}


def normalized_profile(settings: dict) -> str:
    profile = settings.get("privacy_profile", "balanced")
    return profile if profile in VALID_PROFILES else "balanced"


def computer_control_allowed(settings: dict) -> bool:
    return (normalized_profile(settings) != "restricted"
            and bool(settings.get("computer_control_enabled", True)))


def memory_sharing_allowed(settings: dict) -> bool:
    return (normalized_profile(settings) != "restricted"
            and bool(settings.get("share_long_term_memory", True)))


def live_vision_allowed(settings: dict) -> bool:
    return normalized_profile(settings) != "restricted"

