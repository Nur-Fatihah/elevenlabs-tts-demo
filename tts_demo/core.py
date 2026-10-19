"""Core logic for the Malaysia voice gateway.

Everything that talks to ElevenLabs lives here, so the CLI and the web
service stay thin. Each function does one job and can be tested with a fake
client (see tests/test_core.py).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv

# The four main languages used in Malaysia, keyed by ISO 639-1 code.
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ms": "Malay",
    "zh": "Mandarin Chinese",
    "ta": "Tamil",
}

# Flash v2.5 is ElevenLabs' low-latency multilingual model and accepts a
# language_code. We still confirm support at runtime instead of trusting this.
DEFAULT_MODEL_ID = "eleven_flash_v2_5"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


class GatewayError(Exception):
    """An error safe to show to the caller (no secrets, no stack trace)."""


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    language: str
    voice_id: str
    model_id: str = DEFAULT_MODEL_ID
    output_format: str = DEFAULT_OUTPUT_FORMAT

    def cache_key(self) -> str:
        """Same text + voice + model + language + format → same audio file."""
        raw = "|".join([self.text, self.language, self.voice_id, self.model_id, self.output_format])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def make_client():
    """Build an ElevenLabs client from ELEVENLABS_API_KEY (read from .env)."""
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise GatewayError("ELEVENLABS_API_KEY is not set. Copy .env.example to .env and add your key.")
    from elevenlabs.client import ElevenLabs  # imported here so tests need no key

    return ElevenLabs(api_key=api_key)


def validate_text(text: str, max_chars: int = 1000) -> str:
    text = (text or "").strip()
    if not text:
        raise GatewayError("Text is empty.")
    if len(text) > max_chars:
        raise GatewayError(f"Text is {len(text)} characters; this demo caps requests at {max_chars}.")
    return text


def model_languages(client, model_id: str) -> set[str]:
    """Ask ElevenLabs which language codes a model supports."""
    for model in client.models.list():
        if model.model_id == model_id:
            return {lang.language_id for lang in (model.languages or [])}
    raise GatewayError(f"Model '{model_id}' is not available on this account.")


def check_language(client, language: str, model_id: str) -> None:
    if language not in SUPPORTED_LANGUAGES:
        raise GatewayError(f"Language '{language}' is not one of: {', '.join(SUPPORTED_LANGUAGES)}.")
    supported = model_languages(client, model_id)
    if language not in supported:
        raise GatewayError(f"Model '{model_id}' does not list '{language}'. It supports: {', '.join(sorted(supported))}.")


def list_voices(client, language: str | None = None, limit: int = 10) -> list[dict]:
    """Return a short list of voices, optionally filtered by language."""
    response = client.voices.search(page_size=limit, language=language) if language else client.voices.search(page_size=limit)
    return [{"voice_id": v.voice_id, "name": v.name, "category": getattr(v, "category", None)} for v in response.voices]


def default_voice_id(client) -> str:
    """Use VOICE_ID from .env if set, otherwise the first voice on the account."""
    configured = os.getenv("VOICE_ID")
    if configured:
        return configured
    voices = list_voices(client, limit=1)
    if not voices:
        raise GatewayError("No voices found on this account.")
    return voices[0]["voice_id"]


def synthesize(client, request: SpeechRequest, use_cache: bool = True) -> tuple[bytes, bool]:
    """Generate speech, or return it from the local cache.

    Returns (audio_bytes, served_from_cache). Caching matters to customers:
    a repeated prompt (an IVR greeting, a product announcement) should not be
    paid for twice.
    """
    cache_file = CACHE_DIR / f"{request.cache_key()}.mp3"
    if use_cache and cache_file.exists():
        return cache_file.read_bytes(), True

    chunks = client.text_to_speech.convert(
        request.voice_id,
        text=request.text,
        model_id=request.model_id,
        language_code=request.language,
        output_format=request.output_format,
    )
    audio = b"".join(chunks)
    if use_cache:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_file.write_bytes(audio)
    return audio, False


def stream_speech(client, request: SpeechRequest) -> Iterator[bytes]:
    """Yield audio chunks as ElevenLabs produces them (lower time-to-first-sound)."""
    yield from client.text_to_speech.stream(
        request.voice_id,
        text=request.text,
        model_id=request.model_id,
        language_code=request.language,
        output_format=request.output_format,
    )
