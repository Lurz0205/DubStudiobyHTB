"""Centralized path management and external tool resolver for DubStudio."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Optional


def is_packaged() -> bool:
    """Return True if running in packaged mode (PyInstaller/Velopack) or forced."""
    if os.environ.get("DUBSTUDIO_FORCE_PACKAGED") == "1":
        return True
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        return True
    exe_dir = Path(sys.executable).parent
    if (exe_dir / "app.ico").exists() and (exe_dir.parent / "Update.exe").exists():
        return True
    return False


def get_app_dir() -> Path:
    """Return application directory (installation folder or repository root)."""
    if is_packaged():
        # In PyInstaller/Velopack, executable parent is the app installation folder
        return Path(sys.executable).parent.resolve()
    return Path(__file__).resolve().parent.parent


def get_user_base_dir() -> Path:
    """Return %LocalAppData%\\DubStudio isolated user root."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            p = Path(base) / "DubStudio"
            _mkdir_retry(p)
            return p
    fallback = Path.home() / ".dubstudio"
    _mkdir_retry(fallback)
    return fallback


def get_user_data_dir() -> Path:
    """Alias for get_user_base_dir()."""
    return get_user_base_dir()


def _mkdir_retry(p: Path, retries: int = 3, delay: float = 0.2) -> None:
    """Create directory with retry against transient Windows permission/antivirus locks."""
    for i in range(retries):
        try:
            p.mkdir(parents=True, exist_ok=True)
            return
        except Exception:
            if i < retries - 1:
                time.sleep(delay)
            else:
                p.mkdir(parents=True, exist_ok=True)


def get_data_dir() -> Path:
    """Return %LocalAppData%\\DubStudio\\data."""
    d = get_user_base_dir() / "data"
    _mkdir_retry(d)
    return d


def get_models_dir() -> Path:
    """Return %LocalAppData%\\DubStudio\\models (shared between dev and packaged)."""
    d = get_user_base_dir() / "models"
    _mkdir_retry(d)
    return d


def get_logs_dir() -> Path:
    """Return %LocalAppData%\\DubStudio\\logs."""
    d = get_user_base_dir() / "logs"
    _mkdir_retry(d)
    return d


def get_workspace_dir() -> Path:
    """Return job workspace directory (isolated in AppData for packaged, repo root for dev)."""
    if is_packaged():
        d = get_user_base_dir() / "workspace"
    else:
        d = get_app_dir() / "workspace"
    _mkdir_retry(d)
    return d


def get_out_dir() -> Path:
    """Return exported media directory."""
    if is_packaged():
        d = get_user_base_dir() / "out"
    else:
        d = get_app_dir() / "out"
    _mkdir_retry(d)
    return d


def get_bin_dir() -> Path:
    """Return bin directory where external executables (ffmpeg, ffprobe) reside."""
    # 1. Check app_dir / bin
    candidates = [
        get_app_dir() / "bin",
        get_app_dir() / "_internal" / "bin",
        getattr(sys, "_MEIPASS", None) and Path(getattr(sys, "_MEIPASS")) / "bin",
        get_user_base_dir() / "bin",
    ]
    for c in candidates:
        if c and Path(c).is_dir():
            return Path(c).resolve()
    return (get_app_dir() / "bin").resolve()


def resolve_tool(name: str, custom_path: Optional[str] = None) -> str:
    """
    Resolve external tool (ffmpeg, ffprobe) in strict order:
    1. custom_path from config (if provided and valid)
    2. app's bundled bin/ folder (get_bin_dir())
    3. app directory itself
    4. system PATH
    Returns absolute path string if resolved, or name as fallback.
    """
    ext = ".exe" if sys.platform == "win32" and not name.lower().endswith(".exe") else ""
    target_filename = f"{name}{ext}"

    # 1. Custom path from config
    if custom_path:
        cp = Path(custom_path)
        if cp.is_file():
            return str(cp.resolve())
        elif cp.is_dir() and (cp / target_filename).is_file():
            return str((cp / target_filename).resolve())

    # 2. Bundled bin directory
    bin_dir = get_bin_dir()
    bin_tool = bin_dir / target_filename
    if bin_tool.is_file():
        return str(bin_tool.resolve())

    # 3. Direct app installation directory
    app_tool = get_app_dir() / target_filename
    if app_tool.is_file():
        return str(app_tool.resolve())

    # 4. Check _internal directory
    internal_tool = get_app_dir() / "_internal" / target_filename
    if internal_tool.is_file():
        return str(internal_tool.resolve())

    # 5. System PATH via shutil.which
    which_path = shutil.which(name)
    if which_path:
        return str(Path(which_path).resolve())

    # Fallback to name
    return name
