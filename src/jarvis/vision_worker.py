"""Gemini Live screen stream, independent of the HUD."""
from __future__ import annotations
from PySide6.QtCore import QThread, Signal
from .vision import capture_primary_screen_jpeg

class LiveVisionWorker(QThread):
    """Transmite quadros da tela à Gemini Live enquanto a visão estiver ativa."""
    observation = Signal(str)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._active = True

    def run(self):
        try:
            import asyncio
            from google import genai
            from google.genai import types
            from .providers import SYSTEM_INSTRUCTION
            from .settings import get_secret

            asyncio.run(self._stream(genai, types, get_secret("gemini")))
        except Exception as exc:
            self.failed.emit(str(exc))

    async def _stream(self, genai, types, api_key: str | None):
        """Envia imagens pela sessão Live e renova a sessão antes do limite de duração."""
        import asyncio
        import sounddevice as sd

        if not api_key:
            raise RuntimeError("Configure a chave Gemini para usar visão contínua.")
        client = genai.Client(api_key=api_key)
        audio_output = None
        audio_error_reported = False
        try:
            while self._active:
                async with client.aio.live.connect(
                    model="gemini-3.8-live",
                    config={
                        "response_modalities": ["AUDIO"],
                        "output_audio_transcription": {},
                        "system_instruction": SYSTEM_INSTRUCTION,
                    },
                ) as session:
                    async def receive_updates():
                        nonlocal audio_output, audio_error_reported
                        async for message in session.receive():
                            if not self._active:
                                break
                            content = getattr(message, "server_content", None)
                            transcript = getattr(content, "output_transcription", None) if content else None
                            text = getattr(transcript, "text", "").strip() if transcript else ""
                            if text:
                                self.observation.emit(text)
                            model_turn = getattr(content, "model_turn", None) if content else None
                            for part in (getattr(model_turn, "parts", ()) if model_turn else ()):
                                audio = getattr(part, "inline_data", None)
                                data = getattr(audio, "data", None) if audio else None
                                if data and audio_output is not False:
                                    try:
                                        if audio_output is None:
                                            audio_output = sd.RawOutputStream(
                                                samplerate=24_000, channels=1, dtype="int16")
                                            audio_output.start()
                                        # Este worker já roda fora da UI; a escrita bloqueante não congela o HUD.
                                        audio_output.write(data)
                                    except Exception as exc:
                                        if audio_output is not None:
                                            try:
                                                audio_output.stop()
                                            except Exception:
                                                pass
                                            try:
                                                audio_output.close()
                                            except Exception:
                                                pass
                                        audio_output = False
                                        if not audio_error_reported:
                                            self.failed.emit(
                                                f"Não foi possível reproduzir a voz da Gemini Live: {exc}")
                                            audio_error_reported = True

                    receiver = asyncio.create_task(receive_updates())
                    try:
                        # A Live API aceita até um quadro de vídeo por segundo.
                        for frame_number in range(110):
                            if not self._active or receiver.done():
                                break
                            await session.send_realtime_input(video=types.Blob(
                                data=capture_primary_screen_jpeg(), mime_type="image/jpeg"))
                            # Vídeo sozinho não inicia uma resposta: peça uma leitura após cinco quadros.
                            if frame_number % 5 == 4:
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
            try:
                if audio_output not in (None, False):
                    try:
                        audio_output.stop()
                    finally:
                        audio_output.close()
            finally:
                await client.aio.aclose()

    def stop(self):
        self._active = False


