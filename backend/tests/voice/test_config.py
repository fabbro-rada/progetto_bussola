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


def test_voice_unavailable_is_exception():
    assert issubclass(VoiceUnavailable, Exception)


def test_transcription_forbids_extra_fields():
    import pytest
    from pydantic import ValidationError

    Transcription(text="ciao", language="it")
    with pytest.raises(ValidationError):
        Transcription(text="ciao", language="it", speaker="x")
