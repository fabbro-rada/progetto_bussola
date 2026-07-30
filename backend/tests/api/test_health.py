from fastapi.testclient import TestClient

from bussola.api.app import create_app


def test_health_is_public_and_ok():
    # No auth, no DB: liveness only. Must work even with Postgres down.
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
