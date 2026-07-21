import importlib


def test_defaults(monkeypatch):
    for key in ("BUSSOLA_LLM_BASE_URL", "BUSSOLA_LLM_MODEL", "BUSSOLA_LLM_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    import bussola.llm.config as cfg

    cfg = importlib.reload(cfg)
    assert cfg.BASE_URL.startswith("http://127.0.0.1")
    assert cfg.MODEL
    assert cfg.TIMEOUT > 0
