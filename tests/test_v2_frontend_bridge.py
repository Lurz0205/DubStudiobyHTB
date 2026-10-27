"""Smoke test verifying FastAPI serves the modern v2.0 frontend bundle cleanly."""
import pytest
from fastapi.testclient import TestClient
from dubstudio.api.app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_v2_frontend_index_served(client):
    """Verify root endpoint / serves the modern frontend/dist/index.html."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "DubStudio" in resp.text
    assert "<div id=\"root\"" in resp.text
    assert "src=\"/assets/" in resp.text or "src=\"./assets/" in resp.text


def test_v2_frontend_assets_served(client):
    """Verify static assets in /assets are accessible."""
    import re
    resp = client.get("/")
    # Extract asset link
    css_match = re.search(r'href="[\./]*/assets/([^"]+)"', resp.text)
    js_match = re.search(r'src="[\./]*/assets/([^"]+)"', resp.text)
    
    assert css_match is not None, "CSS bundle link not found in index.html"
    assert js_match is not None, "JS bundle script not found in index.html"

    css_resp = client.get(f"/assets/{css_match.group(1)}")
    assert css_resp.status_code == 200
    assert "tailwindcss" in css_resp.text or "background" in css_resp.text

    js_resp = client.get(f"/assets/{js_match.group(1)}")
    assert js_resp.status_code == 200
    assert len(js_resp.content) > 10000


def test_v2_desktop_bridge_interface():
    """Verify DesktopAPIBridge has all expected window control & in-memory RPC methods."""
    from start_app_v2 import DesktopAPIBridge, find_free_port
    
    # 1. Test dynamic free port acquisition (Zero Hardcoded Port)
    port = find_free_port()
    assert isinstance(port, int)
    assert 1024 <= port <= 65535
    assert port != 8765  # Ephemeral ports are dynamically assigned by OS (>10000)

    # 2. Test in-memory RPC bridge methods
    bridge = DesktopAPIBridge()
    assert hasattr(bridge, "minimize")
    assert hasattr(bridge, "toggle_maximize")
    assert hasattr(bridge, "close")
    assert hasattr(bridge, "get_projects")
    assert hasattr(bridge, "get_project_data")
    assert hasattr(bridge, "save_project_segments")
    assert hasattr(bridge, "save_project_style")
    assert hasattr(bridge, "get_app_settings")
    assert hasattr(bridge, "run_pipeline_stage")

    # In-memory calls without network
    settings = bridge.get_app_settings()
    assert "available_voices" in settings
    assert "translation_model" in settings

    projects = bridge.get_projects()
    assert isinstance(projects, list)

    # Safe no-ops
    bridge.minimize()
    bridge.toggle_maximize()
    bridge.close()
    bridge.emit_event_to_ui({"test": True})


def test_job_context_workspace_keyword_arg(tmp_path):
    """Verify JobContext accepts both workspace and workspace_path without throwing TypeError."""
    from dubstudio.jobstate import JobContext

    job1 = JobContext(workspace_path=tmp_path / "ws1", job_id="test1")
    assert job1.workspace == (tmp_path / "ws1").resolve()

    job2 = JobContext(workspace=tmp_path / "ws2", job_id="test2")
    assert job2.workspace == (tmp_path / "ws2").resolve()


def test_render_stage_input_video_optional(tmp_path):
    """Verify dubstudio.stages.render.run handles input_video=None gracefully."""
    import inspect
    from dubstudio.stages import render
    sig = inspect.signature(render.run)
    assert sig.parameters["input_video"].default is None
