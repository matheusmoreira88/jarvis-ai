"""Opt-in detector for two sharp claps; audio is processed locally and discarded."""
from __future__ import annotations

import time
import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal


class ClapWorker(QThread):
    double_clap = Signal()
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._active = False
        self._last_clap = 0.0
        self._last_peak = 0.0

    def run(self):
        self._active = True
        try:
            with sd.InputStream(samplerate=16000, channels=1, blocksize=512,
                                dtype="float32", callback=self._audio_callback):
                while self._active:
                    time.sleep(0.05)
        except Exception as exc:
            self.error.emit(str(exc))

    def _audio_callback(self, indata, frames, timing, status):
        del frames, timing, status
        samples = indata[:, 0]
        peak = float(np.max(np.abs(samples)))
        rms = float(np.sqrt(np.mean(samples * samples)))
        now = time.monotonic()
        sharp_transient = peak > 0.55 and rms > 0.035 and peak > rms * 5.0
        if sharp_transient and now - self._last_peak > 0.12:
            gap = now - self._last_clap
            if 0.18 <= gap <= 0.85:
                self._last_clap = 0.0
                self.double_clap.emit()
            else:
                self._last_clap = now
            self._last_peak = now

    def stop(self):
        self._active = False
