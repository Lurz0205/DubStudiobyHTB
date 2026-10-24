"""Auto-update checker and troubleshooting/repair utilities for DubStudio."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests

from dubstudio.components import check_for_component_updates
from dubstudio.packaging import is_packaged, get_user_data_dir
from dubstudio.version import APP_VERSION

GITHUB_REPO = "Lurz0205/DubStudiobyHTB"
CURRENT_VERSION = APP_VERSION


def parse_semver(v: str) -> Tuple[int, ...]:
    """Parse semver string (e.g. 'v1.1.1', '1.10.0') into tuple of integers."""
    if not v:
        return (0, 0, 0)
    clean = str(v).strip().lstrip("v").split("+")[0].split("-")[0]
    nums = [int(x) for x in re.findall(r"\d+", clean)]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def check_github_releases(timeout: float = 6.0) -> Optional[Dict[str, Any]]:
    """Check latest release on GitHub repository."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"DubStudio-Updater/{CURRENT_VERSION}",
            },
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def verify_file_checksum(
    file_path: Path,
    expected_sha256: Optional[str] = None,
    expected_size: Optional[int] = None,
) -> bool:
    """Verify that a downloaded package or installer matches expected byte size and SHA-256 hash."""
    if not file_path.is_file():
        return False
    if expected_size and expected_size > 0:
        actual_size = file_path.stat().st_size
        if actual_size != expected_size:
            return False
    if expected_sha256:
        import hashlib
        actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual_sha.lower() != expected_sha256.strip().lower():
            return False
    return True


def check_all_updates(timeout: float = 6.0) -> Dict[str, Any]:
    """Check both GitHub app version updates and modular components updates."""
    result: Dict[str, Any] = {
        "success": False,
        "has_app_update": False,
        "latest_version": CURRENT_VERSION,
        "current_version": CURRENT_VERSION,
        "release_notes": "",
        "download_url": f"https://github.com/{GITHUB_REPO}/releases",
        "setup_asset_url": "",
        "setup_asset_size": 0,
        "setup_asset_sha256": "",
        "component_updates": [],
        "missing_components": [],
        "network_error": None,
    }

    # 1. GitHub app version
    try:
        gh_data = check_github_releases(timeout=timeout)
        if gh_data:
            result["success"] = True
            tag = gh_data.get("tag_name", "").lstrip("v")
            if tag:
                result["latest_version"] = tag
                if parse_semver(tag) > parse_semver(CURRENT_VERSION):
                    result["has_app_update"] = True
                result["release_notes"] = gh_data.get("body", "") or ""
                result["download_url"] = gh_data.get("html_url", result["download_url"])

                # Find Setup.exe installer asset
                for asset in gh_data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith("setup.exe") or ("setup" in name and name.endswith(".exe")):
                        result["setup_asset_url"] = asset.get("browser_download_url", "")
                        result["setup_asset_size"] = int(asset.get("size", 0))
                        break
        else:
            result["network_error"] = "Không thể lấy thông tin phiên bản từ máy chủ GitHub (hết thời gian chờ hoặc không có mạng)."
    except Exception as e:
        result["network_error"] = str(e)

    # 2. Components
    try:
        from dubstudio.components import (
            sync_installed_components,
            check_for_component_updates,
            fetch_components_manifest,
            is_component_ready,
        )
        sync_installed_components()
        comp_updates = check_for_component_updates()
        result["component_updates"] = comp_updates or []

        manifest = fetch_components_manifest()
        # Determine currently selected ASR and Separation models from config / env
        from dubstudio.config import AppConfig
        try:
            cfg = AppConfig.load()
            chosen_asr = os.getenv("WHISPER_MODEL", "") or os.getenv("ASR_MODEL", "") or cfg.asr.model_size or "sensevoice-small"
            chosen_sep = os.getenv("SEPARATION_MODEL", "") or getattr(getattr(cfg, "separation", None), "model_name", "Kim_Vocal_2.onnx")
        except Exception:
            chosen_asr = os.getenv("WHISPER_MODEL", "sensevoice-small")
            chosen_sep = os.getenv("SEPARATION_MODEL", "Kim_Vocal_2.onnx")

        active_asr_pkg = "sensevoice_small" if "sensevoice" in str(chosen_asr).lower() else "whisper_large_v3"
        active_sep_pkg = "bs_roformer" if "roformer" in str(chosen_sep).lower() else "kim_vocal_2"

        for pkg in manifest.get("packages", []):
            pkg_id = pkg["id"]
            cat = pkg.get("category")
            # 1. ASR packages: ONLY require the one actively chosen for work
            if cat == "asr":
                if pkg_id == active_asr_pkg:
                    ready, _ = is_component_ready(pkg_id)
                    if not ready:
                        result["missing_components"].append(pkg)
            # 2. Separation packages: ONLY require the one actively chosen for work
            elif cat == "separate":
                if pkg_id == active_sep_pkg:
                    ready, _ = is_component_ready(pkg_id)
                    if not ready:
                        result["missing_components"].append(pkg)
            # 3. Global required packages (TTS, PyTorch, FFmpeg)
            elif cat in ("tts", "runtime") or pkg.get("required"):
                ready, _ = is_component_ready(pkg_id)
                if not ready:
                    result["missing_components"].append(pkg)
    except Exception:
        pass

    return result



def repair_and_clean_cache() -> Dict[str, Any]:
    """
    Safely clean temporary cache files without touching user projects or media.
    Cleans:
      - workspace/.cache/ (LLM prompt caches)
      - AppData Local temp/cache
      - Python __pycache__ and build temp files
    """
    cleaned_items: List[str] = []
    freed_bytes: int = 0

    # 1. Workspace cache
    ws_cache = Path("workspace/.cache")
    if ws_cache.exists():
        try:
            for p in ws_cache.rglob("*"):
                if p.is_file():
                    freed_bytes += p.stat().st_size
            shutil.rmtree(ws_cache, ignore_errors=True)
            cleaned_items.append("Bộ nhớ đệm dịch thuật LLM (workspace/.cache)")
        except Exception:
            pass

    # 2. PyCache
    try:
        for pyc in Path(".").rglob("__pycache__"):
            if ".venv" not in str(pyc):
                shutil.rmtree(pyc, ignore_errors=True)
        cleaned_items.append("Bộ nhớ đệm mã nguồn Python (__pycache__)")
    except Exception:
        pass

    # 3. User data cache
    user_data = get_user_data_dir()
    cache_dir = user_data / "cache"
    if cache_dir.exists():
        try:
            shutil.rmtree(cache_dir, ignore_errors=True)
            cleaned_items.append(f"Bộ nhớ đệm người dùng ({cache_dir})")
        except Exception:
            pass

    return {
        "status": "ok",
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "cleaned_items": cleaned_items,
    }


def cleanup_update_artifacts() -> Dict[str, Any]:
    """
    Zero-Leftover Garbage Collector: automatically clean leftover update packages,
    temporary installers, and obsolete hotpatches.
    
    1. Cleans %LocalAppData%\\DubStudio\\packages\\:
       Keeps ONLY the .nupkg of CURRENT_VERSION and index files (RELEASES).
       Deletes older *-delta.nupkg, *-full.nupkg, and VelopackTemp* folders.
    2. Cleans %Temp% and %LocalAppData%\\DubStudioData\\updates\\:
       Deletes DubStudio-win-Setup*.exe, *.tmp, *.part.
    3. Cleans %LocalAppData%\\DubStudioData\\hotpatch\\:
       Deletes any patch folders for older versions (< CURRENT_VERSION).
    """
    freed_bytes: int = 0
    removed_files: List[str] = []
    
    # 1. Clean %LocalAppData%\\DubStudio\\packages
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            pkg_dir = Path(local_app) / "DubStudio" / "packages"
            if pkg_dir.exists():
                curr_clean = CURRENT_VERSION.lstrip("v")
                for item in list(pkg_dir.iterdir()):
                    name = item.name.lower()
                    if item.is_dir():
                        if name.startswith("velopacktemp") or name.endswith(".tmp"):
                            try:
                                for f in item.rglob("*"):
                                    if f.is_file():
                                        freed_bytes += f.stat().st_size
                                shutil.rmtree(item, ignore_errors=True)
                                removed_files.append(item.name)
                            except Exception:
                                pass
                    elif item.is_file():
                        # Keep index files
                        if name in ("releases", "releases.win.json", "releases.json"):
                            continue
                        # Keep current version full package for future delta updates
                        if curr_clean in name and "full" in name:
                            continue
                        # Delete older full packages and all obsolete delta packages
                        try:
                            freed_bytes += item.stat().st_size
                            item.unlink()
                            removed_files.append(item.name)
                        except Exception:
                            pass

    # 2. Clean %Temp% and %LocalAppData%\\DubStudioData\\updates
    import tempfile
    temp_dirs = [
        Path(tempfile.gettempdir()),
        Path(tempfile.gettempdir()) / "DubStudio_Update",
        get_user_data_dir() / "updates",
    ]
    for t_dir in temp_dirs:
        if not t_dir.exists():
            continue
        try:
            for item in list(t_dir.glob("DubStudio*Setup*.exe*")) + list(t_dir.glob("*.part")) + list(t_dir.glob("*.tmp")):
                if item.is_file():
                    try:
                        freed_bytes += item.stat().st_size
                        item.unlink()
                        removed_files.append(item.name)
                    except Exception:
                        pass
        except Exception:
            pass

    # 3. Clean %LocalAppData%\\DubStudioData\\hotpatch
    hotpatch_dir = get_user_data_dir() / "hotpatch"
    if hotpatch_dir.exists():
        curr_tuple = parse_semver(CURRENT_VERSION)
        for sub in list(hotpatch_dir.iterdir()):
            if sub.is_dir():
                sub_ver = sub.name.lstrip("v")
                if parse_semver(sub_ver) < curr_tuple:
                    try:
                        for f in sub.rglob("*"):
                            if f.is_file():
                                freed_bytes += f.stat().st_size
                        shutil.rmtree(sub, ignore_errors=True)
                        removed_files.append(f"hotpatch/{sub.name}")
                    except Exception:
                        pass

    return {
        "status": "ok",
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "removed_files": removed_files,
    }
