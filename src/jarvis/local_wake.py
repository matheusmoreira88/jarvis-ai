"""Optional offline Jarvis prefilter using a small Portuguese Vosk model."""
from __future__ import annotations

import io
import json
import tempfile
import urllib.request
import wave
import zipfile
from pathlib import Path

from platformdirs import user_data_path

MODEL_NAME = "vosk-model-small-pt-0.3"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_ROOT = user_data_path("JarvisAI", "Matheus") / "speech-models"


def _valid_model(path: Path) -> bool:
    # Vosk aceita tanto o layout atual quanto o layout antigo do modelo pt-0.3.
    return ((path / "am" / "final.mdl").is_file()
            and (path / "conf" / "model.conf").is_file()) or (
                (path / "final.mdl").is_file()
                and (path / "mfcc.conf").is_file())


def ensure_model() -> Path:
    """Download only the official model once, with size and path checks."""
    destination = MODEL_ROOT / MODEL_NAME
    if _valid_model(destination):
        return destination
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jarvis-model-", dir=MODEL_ROOT) as folder:
        archive = Path(folder) / "model.zip"
        with urllib.request.urlopen(MODEL_URL, timeout=45) as response, archive.open("wb") as output:
            received = 0
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > 65_000_000:
                    raise RuntimeError("O modelo de voz excedeu o tamanho esperado.")
                output.write(chunk)
        with zipfile.ZipFile(archive) as package:
            members = package.infolist()
            if sum(member.file_size for member in members) > 250_000_000:
                raise RuntimeError("O modelo extraído excedeu o tamanho esperado.")
            for member in members:
                path = Path(member.filename)
                if (path.is_absolute() or ".." in path.parts or not path.parts
                        or path.parts[0] != MODEL_NAME):
                    raise RuntimeError("O pacote do modelo contém um caminho inválido.")
            package.extractall(folder)
        extracted = Path(folder) / MODEL_NAME
        if not _valid_model(extracted):
            raise RuntimeError("O pacote do modelo local está incompleto.")
        # A tentativa anterior pode ter sido interrompida depois da extração.
        # Só removemos esta pasta conhecida do modelo antes de instalar a cópia nova.
        if destination.exists():
            import shutil
            shutil.rmtree(destination)
        extracted.rename(destination)
    return destination


class LocalJarvisFilter:
    """Return True only when the local recognition begins with the wake name."""
    def __init__(self):
        from vosk import Model, SetLogLevel
        SetLogLevel(-1)
        self.model = Model(str(ensure_model()))

    def heard_jarvis(self, wav_bytes: bytes) -> bool:
        from vosk import KaldiRecognizer
        with wave.open(io.BytesIO(wav_bytes), "rb") as source:
            if source.getframerate() != 16_000 or source.getnchannels() != 1:
                return False
            try:
                recognizer = KaldiRecognizer(
                    self.model, 16_000, json.dumps(["jarvis", "[unk]"]))
            except Exception:
                recognizer = KaldiRecognizer(self.model, 16_000)
            heard: list[str] = []
            while chunk := source.readframes(4_000):
                if recognizer.AcceptWaveform(chunk):
                    heard.append(json.loads(recognizer.Result()).get("text", ""))
            heard.append(json.loads(recognizer.FinalResult()).get("text", ""))
            result = " ".join(heard)
        return result.casefold().strip().startswith("jarvis")
