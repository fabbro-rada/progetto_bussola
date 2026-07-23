from bussola.voice.tts import TextToSpeech

_VOICES = {"it": "it.onnx", "en": "en.onnx"}


class FakeTts:
    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises
        self.calls: list[tuple[str, str]] = []

    def synthesize(self, text: str, voice_model: str) -> bytes:
        self.calls.append((text, voice_model))
        if self._raises:
            raise RuntimeError("tts down")
        return b"WAVDATA"


def test_synthesize_returns_audio_bytes():
    tts = TextToSpeech(engine=FakeTts(), voices=_VOICES)
    assert tts.synthesize("ciao", "it") == b"WAVDATA"


def test_language_without_voice_returns_none():
    # Arabic has no voice by default -> text fallback (None), no engine call
    engine = FakeTts()
    tts = TextToSpeech(engine=engine, voices=_VOICES)
    assert tts.synthesize("مرحبا", "ar") is None
    assert engine.calls == []


def test_engine_failure_returns_none():
    tts = TextToSpeech(engine=FakeTts(raises=True), voices=_VOICES)
    assert tts.synthesize("ciao", "it") is None


def test_selects_voice_model_for_language():
    engine = FakeTts()
    TextToSpeech(engine=engine, voices=_VOICES).synthesize("hello", "en")
    assert engine.calls == [("hello", "en.onnx")]
