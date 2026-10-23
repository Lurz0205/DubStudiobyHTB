"""Test ASR Whisper model selection in settings and welcome tutorial wizard."""
import os
from pathlib import Path
import pytest
from dubstudio.config import AppConfig
from dubstudio.packaging import is_first_run, mark_first_run_done


def test_packaging_first_run_toggle(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # Initially first run should be True
    assert is_first_run() is True

    # Mark as done
    mark_first_run_done(True)
    assert is_first_run() is False

    # Reset
    mark_first_run_done(False)
    assert is_first_run() is True


def test_whisper_model_env_override(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "large-v3-turbo")
    cfg = AppConfig.load()
    assert cfg.asr.model_size == "large-v3-turbo"

    monkeypatch.setenv("WHISPER_MODEL", "large-v3")
    cfg2 = AppConfig.load()
    assert cfg2.asr.model_size == "large-v3"


def test_api_settings_whisper_model():
    from fastapi.testclient import TestClient
    from dubstudio.api.app import app

    client = TestClient(app)
    # Get settings
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "whisper_model" in data
    assert "available_whisper_models" in data
    assert any(m["id"] == "large-v3" for m in data["available_whisper_models"])
    assert any(m["id"] == "sensevoice-small" for m in data["available_whisper_models"])

    # Update settings with whisper_model
    post_resp = client.post("/api/settings", json={"whisper_model": "sensevoice-small"})
    assert post_resp.status_code == 200
    assert post_resp.json().get("status") in ("saved", "success")


def test_welcome_tutorial_dialog():
    import sys
    from PyQt6.QtWidgets import QApplication
    from ui.dialogs.welcome_tutorial_dialog import WelcomeTutorialDialog

    app = QApplication.instance() or QApplication(sys.argv)
    dlg = WelcomeTutorialDialog()
    assert dlg.windowTitle() != ""
    assert dlg._selected_whisper_model in ("large-v3", "sensevoice-small")
    dlg.close()
