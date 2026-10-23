"""Schema version migration helpers for configuration and job workspace states."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

CURRENT_SCHEMA_VERSION = 2


def migrate_config_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate config dictionary to CURRENT_SCHEMA_VERSION.
    Ensures legacy keys (like yt-dlp/downloader) are ignored and required keys exist.
    """
    version = data.get("schema_version", 1)

    if version < 2:
        # V1 -> V2: remove downloader sections, ensure translation provider defaults to gemini_web
        if "downloader" in data:
            data.pop("downloader", None)
        if "translation" in data and isinstance(data["translation"], dict):
            if "provider" not in data["translation"]:
                data["translation"]["provider"] = "gemini_web"
            if "model" not in data["translation"] or not data["translation"]["model"]:
                data["translation"]["model"] = "gemini_web"
        data["schema_version"] = 2

    return data


def migrate_job_state(workspace_dir: Path) -> bool:
    """
    Migrate workspace/<job_id> state files to CURRENT_SCHEMA_VERSION.
    Keeps legacy jobs fully functional and openable in new app versions.
    """
    state_file = workspace_dir / "state.json"
    segments_file = workspace_dir / "segments.json"

    changed = False

    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            cur_ver = state_data.get("schema_version", 1)
            if cur_ver < 2:
                # Migrate V1 -> V2:
                # Remove deprecated downloader stages from status
                if "stages" in state_data and isinstance(state_data["stages"], dict):
                    state_data["stages"].pop("download", None)
                state_data["schema_version"] = 2
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump(state_data, f, ensure_ascii=False, indent=2)
                changed = True
        except Exception:
            pass

    if segments_file.exists():
        try:
            with open(segments_file, "r", encoding="utf-8") as f:
                seg_data = json.load(f)

            cur_ver = seg_data.get("schema_version", 1)
            if cur_ver < 2:
                # Ensure each segment has necessary V2 fields (cues, sub_slices, voice)
                segs = seg_data.get("segments", [])
                for s in segs:
                    if "cues" not in s:
                        s["cues"] = []
                    if "sub_slices" not in s:
                        s["sub_slices"] = []
                seg_data["schema_version"] = 2
                with open(segments_file, "w", encoding="utf-8") as f:
                    json.dump(seg_data, f, ensure_ascii=False, indent=2)
                changed = True
        except Exception:
            pass

    return changed
