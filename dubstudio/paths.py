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


def _merge_move_dir(src_dir: Path, dst_dir: Path) -> None:
    """
    Safely merge-move all files from src_dir into dst_dir file-by-file.
    1. Prevents FileExistsError by creating subdirectories on demand rather than moving whole tree.
    2. Compares file sizes: if src_file is larger or dst_file is missing, writes src into dst.
       If dst_file already has equal or larger size, safely deletes redundant src duplicate.
    3. Recursively removes empty source directories after migration to eliminate disk bloat.
    """
    if not src_dir.exists() or not src_dir.is_dir():
        return
    try:
        if src_dir.resolve() == dst_dir.resolve():
            return
    except Exception:
        return

    dst_dir.mkdir(parents=True, exist_ok=True)

    for root, dirs, files in os.walk(str(src_dir)):
        root_path = Path(root)
        try:
            rel_root = root_path.relative_to(src_dir)
        except Exception:
            continue
        target_root = dst_dir / rel_root
        target_root.mkdir(parents=True, exist_ok=True)

        for filename in files:
            src_file = root_path / filename
            dst_file = target_root / filename

            try:
                if not dst_file.exists():
                    shutil.move(str(src_file), str(dst_file))
                else:
                    src_size = src_file.stat().st_size
                    dst_size = dst_file.stat().st_size
                    if src_size > dst_size:
                        temp_dst = dst_file.with_name(f"{dst_file.name}.tmp_{int(time.time()*1000)}")
                        shutil.move(str(src_file), str(temp_dst))
                        dst_file.unlink(missing_ok=True)
                        temp_dst.replace(dst_file)
                    else:
                        src_file.unlink(missing_ok=True)
            except Exception:
                pass

    # Clean up empty source directories from bottom up
    try:
        for root, dirs, files in os.walk(str(src_dir), topdown=False):
            p = Path(root)
            try:
                if p.exists() and not any(p.iterdir()):
                    p.rmdir()
            except Exception:
                pass
    except Exception:
        pass


def _rebind_config_paths(target_dir: Path, legacy_bases: list[Path]) -> None:
    """
    Rewrite absolute paths in config/state files pointing to legacy directories
    (e.g. ...\\DubStudio\\models\\...) so they point to %LocalAppData%\\DubStudioData.
    """
    target_str = str(target_dir.resolve())
    target_str_fwd = target_str.replace("\\", "/")

    files_to_check = [
        target_dir / "components" / "installed.json",
        target_dir / "installed.json",
        target_dir / "config.toml",
        target_dir / "settings.json",
        target_dir / "components_state.json",
    ]

    for cfg_file in files_to_check:
        if not cfg_file.exists() or not cfg_file.is_file():
            continue
        try:
            content = cfg_file.read_text(encoding="utf-8")
            original_content = content

            for leg in legacy_bases:
                leg_str = str(leg.resolve())
                leg_str_fwd = leg_str.replace("\\", "/")

                for sub in ("models", "components", "runtime", "workspace", "data", "cache", "logs", "out"):
                    content = content.replace(f"{leg_str}\\{sub}", f"{target_str}\\{sub}")
                    content = content.replace(f"{leg_str_fwd}/{sub}", f"{target_str_fwd}/{sub}")
                    leg_esc = leg_str.replace("\\", "\\\\")
                    target_esc = target_str.replace("\\", "\\\\")
                    content = content.replace(f"{leg_esc}\\\\{sub}", f"{target_esc}\\\\{sub}")

            if content != original_content:
                cfg_file.write_text(content, encoding="utf-8")
        except Exception:
            pass


_IS_MIGRATING = False
_MIGRATION_DONE = False


def migrate_legacy_user_data(legacy_dir: Optional[Path] = None, target_dir: Optional[Path] = None) -> None:
    """
    Safely migrate legacy user data (%LocalAppData%\\DubStudio, current\\models, etc.)
    to (%LocalAppData%\\DubStudioData).
    Ensures user models (1.5GB+), logs, and configs are never wiped or duplicated.
    File-by-file merge-move prevents FileExistsError and rebinds configuration paths.
    """
    global _IS_MIGRATING, _MIGRATION_DONE
    if _IS_MIGRATING:
        return
    if legacy_dir is None and _MIGRATION_DONE:
        return

    _IS_MIGRATING = True
    try:
        default_mode = (legacy_dir is None or target_dir is None)
        if default_mode:
            if sys.platform == "win32":
                base = os.environ.get("LOCALAPPDATA")
                if base:
                    target_dir = Path(base) / "DubStudioData"
            if target_dir is None:
                target_dir = Path.home() / ".dubstudio_data"

        _mkdir_retry(target_dir)

        legacy_sources: list[Path] = []
        if legacy_dir is not None:
            legacy_sources.append(legacy_dir)
        else:
            if sys.platform == "win32":
                base = os.environ.get("LOCALAPPDATA")
                if base:
                    legacy_sources.append(Path(base) / "DubStudio")
                    legacy_sources.append(Path(base) / "DubStudio" / "current")
            else:
                legacy_sources.append(Path.home() / ".dubstudio")

            if is_packaged():
                app_dir = get_app_dir()
                try:
                    if app_dir.resolve() != target_dir.resolve():
                        legacy_sources.append(app_dir)
                except Exception:
                    pass

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
            "settings.json",
            "components_state.json",
        ]

        for src_base in legacy_sources:
            try:
                if not src_base.exists() or src_base.resolve() == target_dir.resolve():
                    continue
            except Exception:
                continue

            for item_name in items_to_migrate:
                src = src_base / item_name
                if not src.exists():
                    continue

                dst = target_dir / item_name
                if item_name == "installed.json" and (target_dir / "components").exists():
                    dst = target_dir / "components" / "installed.json"

                try:
                    if src.is_dir():
                        _merge_move_dir(src, dst)
                    elif src.is_file():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        if not dst.exists():
                            shutil.move(str(src), str(dst))
                        else:
                            src_size = src.stat().st_size
                            dst_size = dst.stat().st_size
                            if src_size > dst_size:
                                temp_dst = dst.with_name(f"{dst.name}.tmp_{int(time.time()*1000)}")
                                shutil.move(str(src), str(temp_dst))
                                dst.unlink(missing_ok=True)
                                temp_dst.replace(dst)
                            else:
                                src.unlink(missing_ok=True)
                except Exception:
                    pass

            # Clean legacy folder ONLY if it has NO Velopack metadata and no active files
            velopack_markers = ["current", "packages", "Update.exe", "sq.version", "app.ico", "DubStudio.exe"]
            has_velopack = any((src_base / m).exists() for m in velopack_markers)
            if not has_velopack:
                try:
                    remaining = [p for p in src_base.iterdir() if p.name not in (".", "..")]
                    if not remaining:
                        src_base.rmdir()
                except Exception:
                    pass

        # Rebind legacy paths in configuration and installed component records
        _rebind_config_paths(target_dir, legacy_sources)

        if default_mode:
            _MIGRATION_DONE = True
            # Sync installed components registry if components module is loaded
            try:
                import sys
                if "dubstudio.components" in sys.modules:
                    from dubstudio.components import sync_installed_components
                    sync_installed_components()
            except Exception:
                pass
    finally:
        _IS_MIGRATING = False


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
    """Return %LocalAppData%\\DubStudioData\\models (shared between dev and packaged)."""
    d = get_user_base_dir() / "models"
    _mkdir_retry(d)
    return d


def get_model_search_paths() -> list[Path]:
    """
    Return ordered list of directories to search for AI models:
    1. Primary user models: %LocalAppData%\\DubStudioData\\models
    2. Legacy AppData models: %LocalAppData%\\DubStudio\\models
    3. Legacy packaged app models: %LocalAppData%\\DubStudio\\current\\models
    4. Application/repo models: get_app_dir() / models
    5. Current working directory: ./models
    """
    candidates = [
        get_models_dir(),
    ]
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            candidates.append(Path(base) / "DubStudio" / "models")
            candidates.append(Path(base) / "DubStudio" / "current" / "models")
    else:
        candidates.append(Path.home() / ".dubstudio" / "models")

    candidates.append(get_app_dir() / "models")
    candidates.append(Path.cwd() / "models")
    candidates.append(Path("models").resolve())

    unique: list[Path] = [get_models_dir()]
    seen = {get_models_dir().resolve()}
    for c in candidates:
        try:
            r = c.resolve()
            if r not in seen and r.exists() and r.is_dir():
                seen.add(r)
                unique.append(r)
        except Exception:
            pass
    return unique


def find_model_file(subpath: str | Path) -> Optional[Path]:
    """Search for a model file across all candidate model directories."""
    sub = Path(subpath)
    for base in get_model_search_paths():
        cand = base / sub
        if cand.is_file():
            return cand.resolve()
    return None


def find_model_dir(subpath: str | Path) -> Optional[Path]:
    """Search for a model directory across all candidate model directories."""
    sub = Path(subpath)
    for base in get_model_search_paths():
        cand = base / sub
        if cand.is_dir():
            return cand.resolve()
    return None


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
    out_env = os.environ.get("DUBSTUDIO_OUT_DIR", "").strip()
    if out_env:
        # Discard stale pytest temp directories if app is running normally
        if "pytest" in out_env.lower() and not any("pytest" in str(arg).lower() for arg in sys.argv):
            out_env = ""

    if out_env:
        d = Path(out_env)
        _mkdir_retry(d)
        return d.resolve()

    if is_packaged():
        # Standard user-accessible directory on Windows: ~/Videos/DubStudio
        try:
            user_videos = Path.home() / "Videos"
            if user_videos.exists() or sys.platform == "win32":
                d = user_videos / "DubStudio"
            else:
                d = get_user_base_dir() / "out"
        except Exception:
            d = get_user_base_dir() / "out"
    else:
        d = get_app_dir() / "out"
    _mkdir_retry(d)
    return d.resolve()


def get_env_file() -> Path:
    """Return .env path: %LocalAppData%\\DubStudioData\\.env in packaged mode, or repo .env in dev."""
    if is_packaged():
        target = get_user_base_dir() / ".env"
        if not target.exists() and (get_app_dir() / ".env").exists():
            try:
                shutil.copy2(get_app_dir() / ".env", target)
            except Exception:
                pass
        return target
    return get_app_dir() / ".env"


def open_in_file_manager(target: str | Path) -> None:
    """
    Open system file explorer at the target file or directory.
    On Windows:
    - If target is an existing file, opens Explorer and selects/highlights the file.
    - If target is a directory, opens that directory.
    """
    try:
        p = Path(target).resolve()
        if not p.exists() and p.parent.exists():
            p = p.parent

        if sys.platform == "win32":
            import subprocess
            if p.is_file():
                subprocess.Popen(f'explorer /select,"{p}"', shell=True)
            else:
                os.startfile(str(p))
        elif sys.platform == "darwin":
            import subprocess
            cmd = ["open", "-R", str(p)] if p.is_file() else ["open", str(p)]
            subprocess.Popen(cmd)
        else:
            import subprocess
            folder = str(p.parent if p.is_file() else p)
            subprocess.Popen(["xdg-open", folder])
    except Exception:
        try:
            if sys.platform == "win32":
                os.startfile(str(Path(target).resolve().parent))
        except Exception:
            pass


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

