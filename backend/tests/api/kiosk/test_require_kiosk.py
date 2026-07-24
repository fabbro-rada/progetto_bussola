from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from bussola.api.kiosk import config, deps


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/probe")
    def probe(_: None = Depends(deps.require_kiosk)) -> dict:
        return {"ok": True}

    return TestClient(app)


def test_missing_token_is_401(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", "secret-kiosk")
    assert _client().get("/probe").status_code == 401


def test_wrong_token_is_401(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", "secret-kiosk")
    assert _client().get("/probe", headers={"X-Kiosk-Token": "wrong"}).status_code == 401


def test_correct_token_passes(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", "secret-kiosk")
    r = _client().get("/probe", headers={"X-Kiosk-Token": "secret-kiosk"})
    assert r.status_code == 200


def test_unconfigured_token_is_401(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", "")  # not configured -> deny
    assert _client().get("/probe", headers={"X-Kiosk-Token": ""}).status_code == 401


def test_non_ascii_token_is_401_not_500(monkeypatch):
    # secrets.compare_digest on `str` requires ASCII-only operands and raises
    # TypeError for non-ASCII input; a crafted header must 401, not 500.
    # The header value is passed as raw UTF-8 bytes: httpx's TestClient
    # rejects a non-ASCII `str` header value client-side (it would never
    # reach the app), so bytes are needed to exercise the real wire format.
    monkeypatch.setattr(config, "KIOSK_TOKEN", "secret-kiosk")
    r = _client().get("/probe", headers={"X-Kiosk-Token": "tökén-nön-ascii".encode("utf-8")})
    assert r.status_code == 401
