"""Unit tests for the updater module, semver parsing, and auto-update flow."""
import pytest
from unittest.mock import patch, MagicMock

from dubstudio.updater import parse_semver, check_all_updates, repair_and_clean_cache, CURRENT_VERSION


def test_parse_semver():
    assert parse_semver("1.0.0") == (1, 0, 0)
    assert parse_semver("v1.1.1") == (1, 1, 1)
    assert parse_semver("v1.10.2") == (1, 10, 2)
    assert parse_semver("1.2") == (1, 2, 0)
    assert parse_semver("") == (0, 0, 0)

    # Comparison tests
    assert parse_semver("1.10.0") > parse_semver("1.9.0")
    assert parse_semver("v1.1.2") > parse_semver("1.1.1")
    assert not (parse_semver("1.1.1") > parse_semver("v1.1.1"))
    assert parse_semver("2.0.0") > parse_semver("1.99.99")


def test_check_all_updates_mocked_has_update():
    fake_gh = {
        "tag_name": "v9.9.9",
        "body": "Fixed critical bugs and improved updater",
        "html_url": "https://github.com/Lurz0205/DubStudiobyHTB/releases/tag/v9.9.9",
        "assets": [
            {
                "name": "DubStudio-win-Setup.exe",
                "browser_download_url": "https://github.com/Lurz0205/DubStudiobyHTB/releases/download/v9.9.9/DubStudio-win-Setup.exe",
                "size": 140000000,
            }
        ],
    }

    with patch("dubstudio.updater.check_github_releases", return_value=fake_gh):
        res = check_all_updates()
        assert res["success"] is True
        assert res["has_app_update"] is True
        assert res["latest_version"] == "9.9.9"
        assert res["setup_asset_url"].endswith("Setup.exe")
        assert res["setup_asset_size"] == 140000000
        assert "critical bugs" in res["release_notes"]


def test_check_all_updates_mocked_up_to_date():
    fake_gh = {
        "tag_name": f"v{CURRENT_VERSION}",
        "body": "Current version notes",
        "html_url": "https://github.com/Lurz0205/DubStudiobyHTB/releases",
        "assets": [],
    }

    with patch("dubstudio.updater.check_github_releases", return_value=fake_gh):
        res = check_all_updates()
        assert res["success"] is True
        assert res["has_app_update"] is False
        assert res["latest_version"] == CURRENT_VERSION


def test_check_all_updates_network_failure():
    with patch("dubstudio.updater.check_github_releases", return_value=None):
        res = check_all_updates()
        assert res["success"] is False
        assert res["has_app_update"] is False
        assert res["network_error"] is not None


def test_repair_and_clean_cache():
    res = repair_and_clean_cache()
    assert res["status"] == "ok"
    assert "freed_mb" in res
    assert isinstance(res["cleaned_items"], list)
