"""Microphone input (speech -> text) and speaker output (text -> voice)."""
import asyncio
import logging
import os
import re
import sys
import tempfile
import threading
import time
from array import array

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import speech_recognition as sr

from .settings import settings

log = logging.getLogger("fro.voice")
_BANGLA = re.compile(r"[ঀ-৿]")


def _rms_level(data: bytes) -> float:
    """0..1 loudness of a 16-bit mono audio chunk."""
    try:
        samples = array("h")
        samples.frombytes(data[: len(data) // 2 * 2])
        samples = samples[::6]
        if not samples:
            return 0.0
        mean_sq = sum(s * s for s in samples) / len(samples)
        return min(1.0, (mean_sq ** 0.5) / 5000.0)
    except Exception:
        return 0.0


class Listener:
    """Keeps the microphone open and turns speech into text with Google's free recognizer."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.7
        self.recognizer.dynamic_energy_threshold = True
        self.mic = None
        self.source = None
        self.ok = False
        self._level_cb = None

    def open(self) -> bool:
        try:
            self.mic = sr.Microphone()
            self.source = self.mic.__enter__()
            original_read = self.source.stream.read

            def read(size):
                data = original_read(size)
                cb = self._level_cb
                if cb is not None:
                    cb(_rms_level(data))
                return data

            self.source.stream.read = read
            self.recognizer.adjust_for_ambient_noise(self.source, duration=1)
            self.ok = True
        except Exception as e:  # no PyAudio, no microphone, permission denied ...
            log.warning("Microphone not available: %s", e)
            self.ok = False
        return self.ok

    def close(self):
        try:
            if self.mic is not None:
                self.mic.__exit__(None, None, None)
        except Exception:
            pass
        self.ok = False

    def flush(self):
        """Throw away audio that piled up while Fro was speaking, so it never hears itself."""
        try:
            stream = self.source.stream.pyaudio_stream
            n = stream.get_read_available()
            if n:
                stream.read(n, exception_on_overflow=False)
        except Exception:
            pass

    def listen(self, timeout=1.0, phrase_limit=10, level_cb=None) -> str:
        if not self.ok:
            time.sleep(0.5)
            return ""
        self._level_cb = level_cb
        try:
            audio = self.recognizer.listen(self.source, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return ""
        except Exception as e:
            log.warning("Listening failed (%s), reopening the microphone", e)
            self.close()
            time.sleep(1)
            self.open()
            return ""
        finally:
            self._level_cb = None
        try:
            return self.recognizer.recognize_google(audio, language=settings.get("language")).strip()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            log.warning("Speech service unreachable (no internet?)")
            return ""


_CHIME = None


def _chime_wav() -> bytes:
    """Two soft rising tones as an in-memory WAV file."""
    global _CHIME
    if _CHIME is None:
        import io
        import math
        import struct
        import wave

        rate = 22050
        frames = bytearray()
        for freq, dur in ((880.0, 0.07), (1318.5, 0.11)):
            n = int(rate * dur)
            for i in range(n):
                env = min(1.0, i / (rate * 0.008)) * (1.0 - i / n) ** 1.5
                frames += struct.pack("<h", int(9000 * env * math.sin(2 * math.pi * freq * i / rate)))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(frames))
        _CHIME = buf.getvalue()
    return _CHIME


def clean_for_speech(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class Speaker:
    """Natural voice with edge-tts (needs internet), offline Windows voice as a fallback."""

    ENV_FPS = 30

    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.level_cb = None  # called with 0..1 loudness of Fro's own voice while it speaks

    def chime(self):
        """Soft 'I'm listening' blip, like Siri."""
        if sys.platform != "win32" or not settings.get("chime"):
            return
        try:
            import winsound

            winsound.PlaySound(_chime_wav(), winsound.SND_MEMORY)
        except Exception:
            pass

    def _envelope(self, pygame, path):
        """Loudness of the audio file over time, so the ring can move with the real voice."""
        try:
            freq, size, channels = pygame.mixer.get_init()
            if abs(size) != 16:
                return None
            raw = pygame.mixer.Sound(path).get_raw()
            samples = array("h")
            samples.frombytes(raw[: len(raw) // 2 * 2])
            step = max(1, int(freq * channels / self.ENV_FPS))
            levels = []
            for i in range(0, len(samples), step):
                chunk = samples[i:i + step:4]
                if not chunk:
                    break
                rms = (sum(s * s for s in chunk) / len(chunk)) ** 0.5
                levels.append(min(1.0, (rms / 6500.0) ** 0.7))
            return levels
        except Exception:
            return None

    def stop(self):
        self._stop.set()
        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def speak(self, text: str):
        text = clean_for_speech(text)
        if not text:
            return
        with self._lock:
            self._stop.clear()
            if not self._speak_online(text):
                self._speak_offline(text)

    def _speak_online(self, text) -> bool:
        path = None
        try:
            import edge_tts
            import pygame

            voice = settings.get("tts_voice_bn") if _BANGLA.search(text) else settings.get("tts_voice")
            fd, path = tempfile.mkstemp(suffix=".mp3", prefix="fro_")
            os.close(fd)
            asyncio.run(edge_tts.Communicate(text, voice).save(path))
            if self._stop.is_set():
                return True
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            env = self._envelope(pygame, path) if self.level_cb else None
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and not self._stop.is_set():
                if env and self.level_cb:
                    pos = pygame.mixer.music.get_pos()
                    if pos >= 0:
                        self.level_cb(env[min(len(env) - 1, int(pos * self.ENV_FPS / 1000))])
                time.sleep(0.025)
            if self.level_cb:
                self.level_cb(0.0)
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            return True
        except Exception as e:
            log.info("Online voice unavailable (%s), using the offline voice", e)
            return False
        finally:
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _speak_offline(self, text):
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            log.warning("Offline voice failed: %s", e)
