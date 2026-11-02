"""Stable model identifiers used by every Gemini integration.

Keeping these values in one small module makes provider migrations explicit and
prevents voice, vision, and self-modification from silently drifting apart.
"""

GEMINI_ASSISTANT_MODEL = "gemini-3.5-flash-lite"
GEMINI_TRANSCRIPTION_MODEL = GEMINI_ASSISTANT_MODEL
GEMINI_VISION_MODEL = GEMINI_ASSISTANT_MODEL
GEMINI_CODE_MODEL = "gemini-3.8-flash"
GEMINI_LIVE_VISION_MODEL = "gemini-3.8-live"
