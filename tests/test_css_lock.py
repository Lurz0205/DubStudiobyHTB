from pathlib import Path
from fastapi.testclient import TestClient
from dubstudio.api.app import app
from start_app_v2 import wait_for_server_ready
import pytest


def test_frontend_dist_inline_css():
    """Verify Lock 1: Compiled frontend dist index.html has inline CSS guarantee."""
    dist_index = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"
    assert dist_index.exists(), f"Frontend dist index.html not found at {dist_index}"
    content = dist_index.read_text(encoding="utf-8")
    assert '<style id="dubstudio-core-css">' in content
    # Ensure compiled CSS payload is substantial (> 20,000 characters)
    assert len(content) > 20000


def test_api_index_cache_headers():
    """Verify Lock 2: API serves index.html with strict no-cache/no-store headers."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    cache_control = resp.headers.get("cache-control", "")
    assert "no-cache" in cache_control
    assert "no-store" in cache_control
    assert "must-revalidate" in cache_control
    assert '<style id="dubstudio-core-css">' in resp.text


def test_wait_for_server_ready_probe(monkeypatch):
    """Verify Lock 2: wait_for_server_ready probe validates body content and status."""
    class FakeResponse:
        def __init__(self, status=200, body=b'<html lang="vi"><style id="dubstudio-core-css">/* huge styles */' + b'a' * 2000 + b'</style></html>'):
            self.status = status
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=1.0: FakeResponse(200))
    ready = wait_for_server_ready("http://127.0.0.1:9999", timeout=2.0)
    assert ready is True

    # Test failure when response is small or missing style
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=1.0: FakeResponse(200, body=b"short"))
    not_ready = wait_for_server_ready("http://127.0.0.1:9999", timeout=0.2)
    assert not_ready is False
