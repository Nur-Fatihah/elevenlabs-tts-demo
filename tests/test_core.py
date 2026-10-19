"""Tests that run without an API key, using a fake ElevenLabs client."""

from types import SimpleNamespace

import pytest

from tts_demo import core
from tts_demo.core import GatewayError, SpeechRequest


class FakeClient:
    """Stands in for ElevenLabs(); records how many times audio was generated."""

    def __init__(self, languages=("en", "ms", "zh")):
        self.calls = 0
        lang_objs = [SimpleNamespace(language_id=code) for code in languages]
        self.models = SimpleNamespace(list=lambda: [SimpleNamespace(model_id=core.DEFAULT_MODEL_ID, languages=lang_objs)])
        self.text_to_speech = SimpleNamespace(convert=self._convert)

    def _convert(self, voice_id, **kwargs):
        self.calls += 1
        return iter([b"fake-", b"audio"])


def test_cache_key_changes_with_language():
    a = SpeechRequest(text="Hello", language="en", voice_id="v1")
    b = SpeechRequest(text="Hello", language="ms", voice_id="v1")
    assert a.cache_key() != b.cache_key()


def test_validate_text_rejects_empty_and_long():
    with pytest.raises(GatewayError):
        core.validate_text("   ")
    with pytest.raises(GatewayError):
        core.validate_text("x" * 1001)


def test_check_language_uses_model_list():
    client = FakeClient(languages=("en", "ms"))
    core.check_language(client, "ms", core.DEFAULT_MODEL_ID)  # supported: no error
    with pytest.raises(GatewayError):
        core.check_language(client, "ta", core.DEFAULT_MODEL_ID)  # Malaysian, but model doesn't list it
    with pytest.raises(GatewayError):
        core.check_language(client, "fr", core.DEFAULT_MODEL_ID)  # not in our supported set


def test_synthesize_caches_second_call(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    client = FakeClient()
    request = SpeechRequest(text="Selamat pagi", language="ms", voice_id="v1")

    audio1, cached1 = core.synthesize(client, request)
    audio2, cached2 = core.synthesize(client, request)

    assert audio1 == audio2 == b"fake-audio"
    assert (cached1, cached2) == (False, True)
    assert client.calls == 1  # the second request never reached ElevenLabs
