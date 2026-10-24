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


def get_resource_dir() -> Path:
    """Return directory where bundled assets (config, ui, _internal) are located."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    exe_internal = Path(sys.executable).parent / "_internal"
    if exe_internal.exists():
        return exe_internal.resolve()
    return get_app_dir()


def migrate_legacy_user_data(legacy_dir: Optional[Path] = None, target_dir: Optional[Path] = None) -> None:
    """
    Safely migrate legacy user data (%LocalAppData%\\DubStudio) to (%LocalAppData%\\DubStudioData).
    Ensures user models (1.5GB+), logs, and configs are never wiped or conflicted with Velopack installation binaries.
    """
    if legacy_dir is None or target_dir is None:
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA")
            if base:
                legacy_dir = Path(base) / "DubStudio"
                target_dir = Path(base) / "DubStudioData"
        if legacy_dir is None or target_dir is None:
            legacy_dir = Path.home() / ".dubstudio"
            target_dir = Path.home() / ".dubstudio_data"

    try:
        if not legacy_dir.exists() or legacy_dir.resolve() == target_dir.resolve():
            return
    except Exception:
        return

    items_to_migrate = [
        "models",
        "components",
        "workspace",
        "logs",
        "out",
        "runtime",
        "data",
        "cache",
        "installed.json",
        ".first_run_done",
        "config.toml",
    ]

    _mkdir_retry(target_dir)

    for item_name in items_to_migrate:
        src = legacy_dir / item_name
        dst = target_dir / item_name
        if not src.exists():
            continue
        try:
            if not dst.exists():
                shutil.move(str(src), str(dst))
            elif src.is_dir() and dst.is_dir():
                for sub in list(src.rglob("*")):
                    if sub.is_file():
                        rel = sub.relative_to(src)
                        target_file = dst / rel
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        if not target_file.exists():
                            try:
                                shutil.move(str(sub), str(target_file))
                            except Exception:
                                pass
                        else:
                            try:
                                sub.unlink()
                            except Exception:
                                pass
                try:
                    shutil.rmtree(str(src), ignore_errors=True)
                except Exception:
                    pass
            elif src.is_file():
                try:
                    src.unlink()
                except Exception:
                    pass
        except Exception:
            pass

    # Clean legacy folder ONLY if it has NO Velopack metadata
    velopack_markers = ["current", "packages", "Update.exe", "sq.version", "app.ico", "DubStudio.exe"]
    has_velopack = any((legacy_dir / m).exists() for m in velopack_markers)
    if not has_velopack:
        try:
            remaining = [p for p in legacy_dir.iterdir() if p.name not in (".", "..")]
            if not remaining:
                legacy_dir.rmdir()
        except Exception:
            pass


def get_user_base_dir() -> Path:
    """Return %LocalAppData%\\DubStudioData isolated user root."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            target = Path(base) / "DubStudioData"
            _mkdir_retry(target)
            migrate_legacy_user_data(Path(base) / "DubStudio", target)
            return target
    fallback = Path.home() / ".dubstudio_data"
    _mkdir_retry(fallback)
    migrate_legacy_user_data(Path.home() / ".dubstudio", fallback)
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
    """Return job workspace directory (strictly isolated between dev and packaged)."""
    if os.environ.get("DUBSTUDIO_WORKSPACE_DIR"):
        d = Path(os.environ["DUBSTUDIO_WORKSPACE_DIR"])
        _mkdir_retry(d)
        return d.resolve()

    if is_packaged():
        d = get_user_base_dir() / "workspace"
    else:
        d = get_app_dir() / "workspace"
    _mkdir_retry(d)
    return d.resolve()


def get_out_dir() -> Path:
    """Return exported media directory."""
    if os.environ.get("DUBSTUDIO_OUT_DIR"):
        d = Path(os.environ["DUBSTUDIO_OUT_DIR"])
        _mkdir_retry(d)
        return d.resolve()

    if is_packaged():
        d = get_user_base_dir() / "out"
    else:
        d = get_app_dir() / "out"
    _mkdir_retry(d)
    return d.resolve()


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


def resolve_job_workspace(job_id: str) -> Path:
    """
    Resolve the directory containing a job.
    Strictly prioritizes the current active workspace directory (get_workspace_dir()).
    Falls back to alternate locations only if the active workspace has no files.
    """
    if not job_id:
        return get_workspace_dir()

    # 0. Active workspace has top priority
    active_ws = get_workspace_dir() / job_id
    if active_ws.exists():
        for k in ("segments.json", "state.json", "input.mp4", "units.json", "meta.json"):
            if (active_ws / k).exists():
                return active_ws.resolve()

    candidates = [
        get_workspace_dir() / job_id,
        get_user_base_dir() / "workspace" / job_id,
        get_app_dir() / "workspace" / job_id,
        Path.cwd() / "workspace" / job_id,
        Path("dist/DubStudio/workspace") / job_id,
        Path("workspace") / job_id,
    ]
    unique_candidates = []
    seen = set()
    for c in candidates:
        try:
            r = c.resolve()
            if r not in seen:
                seen.add(r)
                unique_candidates.append(c)
        except Exception:
            pass

    # 1. Prefer directory that contains segments.json (sorted by freshest mtime)
    seg_candidates = [
        c for c in unique_candidates
        if c.exists() and (c / "segments.json").exists()
    ]
    if seg_candidates:
        try:
            seg_candidates.sort(key=lambda c: (c / "segments.json").stat().st_mtime, reverse=True)
            return seg_candidates[0].resolve()
        except Exception:
            return seg_candidates[0].resolve()

    # 2. Check for intermediate outputs
    for k in ("units.json", "raw_segments.json", "state.json", "input.mp4", "meta.json"):
        for c in unique_candidates:
            try:
                if c.exists() and (c / k).exists():
                    return c.resolve()
            except Exception:
                pass

    # 3. Check any existing directory
    for c in unique_candidates:
        try:
            if c.exists() and c.is_dir():
                return c.resolve()
        except Exception:
            pass

    # 4. Fallback to default centralized workspace
    fallback = get_workspace_dir() / job_id
    _mkdir_retry(fallback)
    return fallback.resolve()


def resolve_job_file(job_id: str, filename: str) -> Path:
    """Resolve a specific file inside a job's workspace."""
    ws = resolve_job_workspace(job_id)
    return ws / filename

