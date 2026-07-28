from bussola.voice import config
from bussola.voice.errors import VoiceUnavailable
from bussola.voice.models import Transcription


def test_stt_defaults_are_cpu_int8():
    assert config.STT_DEVICE == "cpu"
    assert config.STT_COMPUTE_TYPE == "int8"
    assert config.STT_MODEL  # non-empty


def test_piper_voices_cover_four_languages_without_arabic():
    assert set(config.PIPER_VOICES) == {"it", "en", "fr", "es"}
    assert "ar" not in config.PIPER_VOICES  # Arabic TTS falls back to text by default


def test_english_voice_is_permissive_ljspeech_not_lessac():
    # §3: en_US-lessac ships under a research-only (non-permissive) licence.
    # The English voice must be the public-domain, trained-from-scratch
    # ljspeech voice (verified 2026-07-28, STATO_TECNICO §14). lessac must
    # never come back as the default.
    assert config.PIPER_VOICES["en"] == "en_US-ljspeech-medium.onnx"
    assert "lessac" not in config.PIPER_VOICES["en"]


def test_voice_unavailable_is_exception():
    assert issubclass(VoiceUnavailable, Exception)


def test_transcription_forbids_extra_fields():
    import pytest
    from pydantic import ValidationError

    Transcription(text="ciao", language="it")
    with pytest.raises(ValidationError):
        Transcription(text="ciao", language="it", speaker="x")
