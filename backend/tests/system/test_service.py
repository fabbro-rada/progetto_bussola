from bussola.system.service import SystemConfig, compute_system_config


def test_assembles_config_and_reflects_reachable_seam():
    up = compute_system_config(llm_reachable=lambda: True)
    down = compute_system_config(llm_reachable=lambda: False)
    assert up.llm_reachable is True
    assert down.llm_reachable is False
    assert up.llm_model  # non-empty (from llm.config.MODEL)
    assert up.languages == ["it", "en", "fr", "es", "ar"]
    assert up.stt_model  # from voice.config.STT_MODEL
    assert up.session_ttl_seconds > 0 and up.max_failed_attempts > 0


def test_tts_voices_marks_arabic_as_unavailable():
    cfg = compute_system_config(llm_reachable=lambda: True)
    assert cfg.tts_voices["it"] is True
    assert cfg.tts_voices["ar"] is False  # §8 Arabic = text fallback
    assert set(cfg.tts_voices) == {"it", "en", "fr", "es", "ar"}


def test_config_carries_no_secret_fields():
    # The DTO is a whitelist: no password/DSN/token field may ever exist.
    fields = set(SystemConfig.model_fields)
    assert not any(k in f for f in fields for k in ("password", "secret", "token", "dsn"))
