"""Auto-update checker and troubleshooting/repair utilities for DubStudio."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from dubstudio.components import check_for_component_updates
from dubstudio.packaging import is_packaged, get_user_data_dir

GITHUB_REPO = "Lurz0205/DubStudiobyHTB"
CURRENT_VERSION = "1.1.0"


def check_github_releases(timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """Check latest release on GitHub repository."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        resp = requests.get(url, timeout=timeout, headers={"Accept": "application/vnd.github.v3+json"})
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def check_all_updates() -> Dict[str, Any]:
    """Check both GitHub app version updates and modular components updates."""
    result: Dict[str, Any] = {
        "has_app_update": False,
        "latest_version": CURRENT_VERSION,
        "current_version": CURRENT_VERSION,
        "release_notes": "",
        "download_url": "",
        "component_updates": [],
        "missing_components": [],
    }

    # 1. GitHub app version
    gh_data = check_github_releases()
    if gh_data:
        tag = gh_data.get("tag_name", "").lstrip("v")
        if tag and tag > CURRENT_VERSION:
            result["has_app_update"] = True
            result["latest_version"] = tag
            result["release_notes"] = gh_data.get("body", "")
            result["download_url"] = gh_data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")

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
        # Determine currently selected ASR model from config / env
        import os
        from dubstudio.config import AppConfig
        try:
            cfg = AppConfig.load()
            chosen_asr = os.getenv("WHISPER_MODEL", "") or os.getenv("ASR_MODEL", "") or cfg.asr.model_size or "sensevoice-small"
        except Exception:
            chosen_asr = "sensevoice-small"

        active_asr_pkg = "sensevoice_small" if "sensevoice" in str(chosen_asr).lower() else "whisper_large_v3"

        for pkg in manifest.get("packages", []):
            pkg_id = pkg["id"]
            # ASR packages: ONLY require the one actively chosen for work
            if pkg.get("category") == "asr":
                if pkg_id == active_asr_pkg:
                    ready, _ = is_component_ready(pkg_id)
                    if not ready:
                        result["missing_components"].append(pkg)
            elif pkg.get("category") in ("separate", "tts", "runtime") or pkg.get("required"):
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
