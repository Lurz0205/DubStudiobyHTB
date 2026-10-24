"""Unit tests for the updater module, semver parsing, and auto-update flow."""
import pytest
from unittest.mock import patch, MagicMock

from dubstudio.updater import (
    parse_semver,
    check_all_updates,
    repair_and_clean_cache,
    cleanup_update_artifacts,
    verify_file_checksum,
    CURRENT_VERSION,
)


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


def test_cleanup_update_artifacts(tmp_path, monkeypatch):
    # Setup mock Velopack packages directory
    fake_local = tmp_path / "LocalAppData"
    fake_pkg_dir = fake_local / "DubStudio" / "packages"
    fake_pkg_dir.mkdir(parents=True)

    # 1. Obsolete delta package (from 1.1.0) -> must be deleted
    old_delta = fake_pkg_dir / "DubStudio-1.1.0-delta.nupkg"
    old_delta.write_bytes(b"old delta bytes" * 100)

    # 2. Obsolete full package (from 1.1.0) -> must be deleted
    old_full = fake_pkg_dir / "DubStudio-1.1.0-full.nupkg"
    old_full.write_bytes(b"old full bytes" * 100)

    # 3. Current full package -> MUST BE PRESERVED
    curr_clean = CURRENT_VERSION.lstrip("v")
    curr_full = fake_pkg_dir / f"DubStudio-{curr_clean}-full.nupkg"
    curr_full.write_bytes(b"current full bytes" * 100)

    # 4. Index file -> MUST BE PRESERVED
    releases_idx = fake_pkg_dir / "RELEASES"
    releases_idx.write_text("index content", encoding="utf-8")

    # 5. Velopack temp extraction folder -> must be deleted
    temp_extract = fake_pkg_dir / "VelopackTemp_12345"
    temp_extract.mkdir()
    (temp_extract / "temp.dll").write_bytes(b"dummy dll" * 50)

    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    res = cleanup_update_artifacts()
    assert res["status"] == "ok"

    # Verify expectations
    assert not old_delta.exists(), "Old delta must be deleted"
    assert not old_full.exists(), "Old full package must be deleted"
    assert not temp_extract.exists(), "VelopackTemp folder must be deleted"
    assert curr_full.exists(), "Current full package must be preserved"
    assert releases_idx.exists(), "RELEASES index must be preserved"


def test_verify_file_checksum(tmp_path):
    import hashlib
    test_file = tmp_path / "test.nupkg"
    content = b"Hello Velopack Delta Update Verification!"
    test_file.write_bytes(content)

    correct_sha = hashlib.sha256(content).hexdigest()
    assert verify_file_checksum(test_file, expected_sha256=correct_sha, expected_size=len(content))
    assert not verify_file_checksum(test_file, expected_sha256="wrongsha", expected_size=len(content))
    assert not verify_file_checksum(test_file, expected_sha256=correct_sha, expected_size=999999)

