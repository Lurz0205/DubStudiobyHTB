"""Hot-patch loader and dynamic module override system for DubStudio.

Enables applying lightweight Python patches (< 1MB) without touching Velopack's
current/_internal/ directory, bypassing PyInstaller's PyiFrozenImporter.
"""
from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Optional, Sequence

logger = logging.getLogger(__name__)


class HotpatchMetaPathFinder(importlib.abc.MetaPathFinder):
    """Custom MetaPathFinder placed before PyiFrozenImporter in sys.meta_path.

    Intercepts imports for 'dubstudio' and 'ui' packages to load patched .py/.pyc
    files from the hotpatch directory if present.
    """

    def __init__(self, hotpatch_root: Path):
        self.hotpatch_root = hotpatch_root.resolve()

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]] = None,
        target: Optional[object] = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        # Only intercept dubstudio.* and ui.* namespaces
        if not (
            fullname == "dubstudio"
            or fullname.startswith("dubstudio.")
            or fullname == "ui"
            or fullname.startswith("ui.")
        ):
            return None

        # Resolve path within hotpatch directory
        parts = fullname.split(".")
        rel_path = Path(*parts)
        candidate_file = self.hotpatch_root / f"{rel_path}.py"
        candidate_pkg = self.hotpatch_root / rel_path / "__init__.py"

        if candidate_file.is_file():
            loader = importlib.machinery.SourceFileLoader(fullname, str(candidate_file))
            return importlib.util.spec_from_file_location(
                fullname, candidate_file, loader=loader
            )
        elif candidate_pkg.is_file():
            loader = importlib.machinery.SourceFileLoader(fullname, str(candidate_pkg))
            spec = importlib.util.spec_from_file_location(
                fullname,
                candidate_pkg,
                loader=loader,
                submodule_search_locations=[str(candidate_pkg.parent)],
            )
            return spec

        return None


def get_hotpatch_base_dir() -> Path:
    """Return root directory for all hotpatches (%LocalAppData%\\DubStudioData\\hotpatch)."""
    from dubstudio.paths import get_user_data_dir
    p = get_user_data_dir() / "hotpatch"
    p.mkdir(parents=True, exist_ok=True)
    return p


def verify_patch_manifest(patch_dir: Path, expected_version: str) -> bool:
    """Verify integrity of patch_manifest.json against file contents and version."""
    manifest_file = patch_dir / "patch_manifest.json"
    if not manifest_file.exists():
        return False

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if manifest.get("base_version") != expected_version:
            return False

        files = manifest.get("files", {})
        for rel_str, exp_sha256 in files.items():
            f_path = patch_dir / rel_str
            if not f_path.is_file():
                return False
            actual_sha = hashlib.sha256(f_path.read_bytes()).hexdigest()
            if actual_sha.lower() != exp_sha256.lower():
                return False
        return True
    except Exception as e:
        logger.warning(f"Failed to verify hotpatch manifest: {e}")
        return False


def apply_hotpatches() -> Optional[Path]:
    """Inspect and activate valid hot-patch for the current application version.

    Cleans up stale hotpatches from prior versions.
    Installs HotpatchMetaPathFinder at index 0 of sys.meta_path and sys.path.
    """
    try:
        from dubstudio.updater import CURRENT_VERSION
        app_version = CURRENT_VERSION
    except Exception:
        app_version = "1.1.3"

    root = get_hotpatch_base_dir()

    # 1. Clean up stale patches from previous versions
    if root.exists():
        for item in root.iterdir():
            if item.is_dir() and item.name != app_version:
                try:
                    shutil.rmtree(item, ignore_errors=True)
                except Exception:
                    pass

    # 2. Check current version hotpatch
    ver_patch_dir = root / app_version
    if not ver_patch_dir.is_dir():
        return None

    if not verify_patch_manifest(ver_patch_dir, app_version):
        logger.warning(f"Hotpatch at {ver_patch_dir} failed integrity check, discarding.")
        try:
            shutil.rmtree(ver_patch_dir, ignore_errors=True)
        except Exception:
            pass
        return None

    # 3. Register hotpatch in sys.path and sys.meta_path
    patch_dir_str = str(ver_patch_dir.resolve())
    if patch_dir_str not in sys.path:
        sys.path.insert(0, patch_dir_str)

    # Check if finder is already installed
    for finder in sys.meta_path:
        if isinstance(finder, HotpatchMetaPathFinder):
            return ver_patch_dir

    finder = HotpatchMetaPathFinder(ver_patch_dir)
    sys.meta_path.insert(0, finder)
    logger.info(f"Active Hotpatch applied for DubStudio v{app_version} from {ver_patch_dir}")
    return ver_patch_dir
