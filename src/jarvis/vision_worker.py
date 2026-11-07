"""Gemini Live screen stream, independent of the HUD."""
from __future__ import annotations
from PySide6.QtCore import QThread, Signal
from .vision import capture_primary_screen_jpeg
from .models import GEMINI_LIVE_VISION_MODEL
from .usage import record as record_api_usage

class LiveVisionWorker(QThread):
    """Transmite quadros da tela à Gemini Live enquanto a visão estiver ativa."""
    observation = Signal(str)
    failed = Signal(str)

    def __init__(self, frame_source=None):
        super().__init__()
        self._active = True
        self.frame_source = frame_source

    def run(self):
        try:
            import asyncio
            from google import genai
            from google.genai import types
            from .instructions import system_prompt
            from .settings import get_secret

            asyncio.run(self._stream(genai, types, get_secret("gemini")))
        except Exception as exc:
            self.failed.emit(str(exc))

    async def _stream(self, genai, types, api_key: str | None):
        """Envia imagens pela sessão Live e renova a sessão antes do limite de duração."""
        import asyncio
        import hashlib
        if not api_key:
            raise RuntimeError("Configure a chave Gemini para usar visão contínua.")
        client = genai.Client(api_key=api_key)
        frames_sent = 0
        last_digest = None
        unchanged_frames = 0
        try:
            while self._active:
                async with client.aio.live.connect(
                    model=GEMINI_LIVE_VISION_MODEL,
                    config={
                        # A visão contínua é silenciosa. O TTS só deve falar
                        # quando o usuário pedir uma resposta, nunca por causa
                        # de uma observação automática da tela.
                        "response_modalities": ["TEXT"],
                        "system_instruction": system_prompt(),
                    },
                ) as session:
                    async def receive_updates():
                        async for message in session.receive():
                            if not self._active:
                                break
                            content = getattr(message, "server_content", None)
                            transcript = getattr(content, "output_transcription", None) if content else None
                            text = getattr(transcript, "text", "").strip() if transcript else ""
                            if not text and content:
                                model_turn = getattr(content, "model_turn", None)
                                for part in (getattr(model_turn, "parts", ()) if model_turn else ()):
                                    candidate = getattr(part, "text", "") or ""
                                    if candidate.strip():
                                        text += candidate
                            if text:
                                self.observation.emit(text.strip())

                    receiver = asyncio.create_task(receive_updates())
                    try:
                        # A Live API aceita até um quadro de vídeo por segundo.
                        for frame_number in range(110):
                            if not self._active or receiver.done():
                                break
                            frame = self.frame_source() if self.frame_source else None
                            if frame is None:
                                frame = capture_primary_screen_jpeg()
                            digest = hashlib.blake2b(frame, digest_size=8).digest()
                            changed = digest != last_digest
                            unchanged_frames = 0 if changed else unchanged_frames + 1
                            # Imagens idênticas não precisam consumir cota a cada segundo.
                            # Um quadro de manutenção a cada 10 s mantém a sessão contextual.
                            if changed or unchanged_frames >= 10:
                                await session.send_realtime_input(video=types.Blob(
                                    data=frame, mime_type="image/jpeg"))
                                frames_sent += 1
                                last_digest = digest
                                unchanged_frames = 0
                            # Vídeo sozinho não inicia uma resposta: peça uma leitura após cinco quadros.
                            if frames_sent and frames_sent % 5 == 0 and (changed or unchanged_frames == 0):
                                await session.send_realtime_input(text=(
                                    "Analise as imagens recentes da tela. Em português, informe "
                                    "somente mudanças importantes ou algo que pareça exigir ajuda. "
                                    "Não execute ações no computador."
                                ))
                            await asyncio.sleep(1)
                    finally:
                        receiver.cancel()
                        try:
                            await receiver
                        except asyncio.CancelledError:
                            pass
                if self._active:
                    await asyncio.sleep(0.2)
        finally:
            record_api_usage("live_vision_frames", frames_sent)
            await client.aio.aclose()

    def stop(self):
        self._active = False


