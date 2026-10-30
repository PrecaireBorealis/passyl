"""Sarvam Saaras v4 (STT) and Bulbul v3 (TTS). Any failure returns an error → browser speech fallback (spec 13)."""
import subprocess

import httpx

from ..config import OFFLINE_MODE, env

TIMEOUT = 6
STT_URL = "https://api.sarvam.ai/speech-to-text"
TTS_URL = "https://api.sarvam.ai/text-to-speech"


def _key() -> str:
    return env("SARVAM_API_KEY")


def to_wav(raw: bytes) -> bytes:
    """webm/ogg from MediaRecorder → 16 kHz mono wav (ffmpeg)."""
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1"],
                       input=raw, capture_output=True, timeout=10)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[:200])
    return p.stdout


def stt(raw: bytes, content_type: str) -> dict:
    if OFFLINE_MODE or not _key():
        return {"transcript": "", "error": "offline or no SARVAM_API_KEY"}
    try:
        wav = raw if "wav" in content_type else to_wav(raw)
        r = httpx.post(STT_URL, headers={"api-subscription-key": _key()}, timeout=TIMEOUT,
                       files={"file": ("audio.wav", wav, "audio/wav")},
                       data={"model": env("SARVAM_STT_MODEL", "saaras:v4"), "language_code": "unknown"})
        r.raise_for_status()
        js = r.json()
        return {"transcript": js.get("transcript", ""), "language_code": js.get("language_code"),
                "model": env("SARVAM_STT_MODEL", "saaras:v4")}
    except Exception as e:  # network, auth, ffmpeg: the browser fallback takes over
        return {"transcript": "", "error": str(e)}


def tts(text: str, lang: str) -> dict:
    if OFFLINE_MODE or not _key() or not text:
        return {"audio_b64": None, "error": "offline or no SARVAM_API_KEY"}
    words = text.split()
    text = " ".join(words[:60])  # voice replies stay ≤ 60 words; the full card is on screen
    try:
        r = httpx.post(TTS_URL, headers={"api-subscription-key": _key()}, timeout=TIMEOUT,
                       json={"text": text, "target_language_code": "en-IN" if lang == "en" else "hi-IN",
                             "model": env("SARVAM_TTS_MODEL", "bulbul:v3"), "speaker": env("SARVAM_TTS_SPEAKER", "priya"),
                             "pace": 1.05, "speech_sample_rate": 22050})
        r.raise_for_status()
        return {"audio_b64": r.json()["audios"][0]}
    except Exception as e:
        return {"audio_b64": None, "error": str(e)}
