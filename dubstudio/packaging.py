"""Packaging detection, runtime path resolution, and isolated user directory routing."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys


def is_first_run() -> bool:
    """Check if the user is running DubStudio for the first time."""
    marker = get_user_data_dir() / ".first_run_done"
    return not marker.exists()


def mark_first_run_done(done: bool = True) -> None:
    """Mark first-run tutorial wizard as completed or reset."""
    marker = get_user_data_dir() / ".first_run_done"
    if done:
        try:
            marker.write_text("1", encoding="utf-8")
        except Exception:
            pass
    else:
        if marker.exists():
            try:
                marker.unlink()
            except Exception:
                pass


def is_packaged() -> bool:
    """
    Check if application is running in packaged/installed mode.
    Returns True when installed via Velopack/PyInstaller or when simulated with DUBSTUDIO_FORCE_PACKAGED=1.
    In local dev mode, returns False to disable data package downloads and update checks.
    """
    if os.environ.get("DUBSTUDIO_FORCE_PACKAGED") == "1":
        return True

    # PyInstaller frozen or Velopack execution
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        return True

    # Check for Velopack deployment markers in parent directories
    exe_dir = Path(sys.executable).parent
    if (exe_dir / "app.ico").exists() and (exe_dir.parent / "Update.exe").exists():
        return True

    return False


def get_user_data_dir() -> Path:
    """
    Return isolated user data directory outside application installation folder
    (%LocalAppData%\\DubStudio).
    Prevents user data, models, and heavy runtime packs from being overwritten during delta updates.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            p = Path(base) / "DubStudio"
            p.mkdir(parents=True, exist_ok=True)
            return p

    fallback = Path.home() / ".dubstudio"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_models_dir(default_dir: Path | None = None) -> Path:
    """Return models directory depending on packaged vs dev mode."""
    if is_packaged():
        p = get_user_data_dir() / "models"
        p.mkdir(parents=True, exist_ok=True)
        return p
    return default_dir or Path("models")


def get_runtime_python() -> Path:
    """
    Return Python executable to run heavy AI model subprocesses.
    In packaged mode:
      1. Returns %LocalAppData%\\DubStudio\\runtime\\python.exe if present.
      2. Otherwise returns sys.executable (the self-contained DubStudio.exe).
      Never searches for external .venv to avoid dev/packaged environment collisions.
    In dev mode (start.bat):
      Prefers local .venv\\Scripts\\python.exe if present nearby.
    """
    heavy_py = get_user_data_dir() / "runtime" / "python.exe"
    if heavy_py.exists():
        return heavy_py

    candidates = [
        Path(".venv/Scripts/python.exe"),
        Path(sys.executable).parent / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable).parent.parent / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable).parent.parent.parent / ".venv" / "Scripts" / "python.exe",
    ]
    for cand in candidates:
        if cand.exists():
            return cand.resolve()

    return Path(sys.executable)


def get_subprocess_env() -> dict[str, str]:
    """
    Construct environment dictionary for subprocess workers (run, stage, worker_server).
    Ensures:
    1. PYTHONUTF8=1, PYTHONIOENCODING=utf-8
    2. PYTHONPATH includes project root (dev) or _internal (packaged),
       plus %LocalAppData%\\DubStudio\\runtime\\site-packages.
    3. PATH includes bin directory (ffmpeg) and CUDA DLLs.
    4. HF_HOME and TORCH_HOME point to centralized models directory.
    """
    from dubstudio.paths import get_bin_dir, get_models_dir

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Route caches to centralized AppData models dir only if they exist on disk,
    # otherwise preserve user's default ~/.cache where models are physically located.
    models_root = get_models_dir()
    if (models_root / "hf").exists():
        env["HF_HOME"] = str((models_root / "hf").resolve())
    elif os.environ.get("HF_HOME"):
        env["HF_HOME"] = os.environ["HF_HOME"]

    if (models_root / "torch").exists():
        env["TORCH_HOME"] = str((models_root / "torch").resolve())

    # Prepend bundled bin/ directory (ffmpeg, ffprobe) to PATH
    bin_dir = get_bin_dir()
    existing_path = env.get("PATH", "")
    if bin_dir.exists():
        env["PATH"] = str(bin_dir.resolve()) + os.pathsep + existing_path

    paths_to_add: list[str] = []
    if is_packaged():
        internal_dir = getattr(sys, "_MEIPASS", None)
        if not internal_dir:
            internal_dir = str(Path(sys.executable).parent / "_internal")
        paths_to_add.append(str(internal_dir))
    else:
        root_dir = Path(__file__).resolve().parent.parent
        paths_to_add.append(str(root_dir))

    runtime_site = get_user_data_dir() / "runtime" / "site-packages"
    if runtime_site.exists():
        paths_to_add.append(str(runtime_site.resolve()))
    else:
        for cand in [Path(".venv/Lib/site-packages"), Path(sys.executable).parent.parent / ".venv/Lib/site-packages"]:
            if cand.exists():
                paths_to_add.append(str(cand.resolve()))
                break

    existing_pythonpath = env.get("PYTHONPATH", "")
    new_pythonpath = os.pathsep.join(paths_to_add + ([existing_pythonpath] if existing_pythonpath else []))
    env["PYTHONPATH"] = new_pythonpath

    if is_packaged():
        env["DUBSTUDIO_FORCE_PACKAGED"] = "1"
        from dubstudio.paths import get_workspace_dir
        env["DUBSTUDIO_WORKSPACE_DIR"] = str(get_workspace_dir().resolve())

    return env


def get_subprocess_kwargs() -> dict:
    """Return standard kwargs for hidden background subprocesses on Windows (no console/window flashing)."""
    kwargs: dict = {}
    if sys.platform == "win32":
        import subprocess
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        kwargs["stdin"] = subprocess.DEVNULL
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
    return kwargs


def safe_subprocess_popen(cmd: list[str], **kwargs) -> subprocess.Popen:
    """Launch a subprocess safely with Windows Job Object attachment and hidden window flags."""
    sub_kwargs = get_subprocess_kwargs()
    sub_kwargs.update(kwargs)
    proc = subprocess.Popen(cmd, **sub_kwargs)
    try:
        from dubstudio.win_job import assign_process_to_job
        assign_process_to_job(proc)
    except Exception:
        pass
    return proc


def safe_subprocess_run(cmd: list[str], check: bool = False, **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess to completion with Windows Job Object attachment and hidden window flags."""
    sub_kwargs = get_subprocess_kwargs()
    sub_kwargs.update(kwargs)
    proc = subprocess.Popen(cmd, **sub_kwargs)
    try:
        from dubstudio.win_job import assign_process_to_job
        assign_process_to_job(proc)
    except Exception:
        pass
    stdout, stderr = proc.communicate()
    retcode = proc.poll()
    if check and retcode != 0:
        raise subprocess.CalledProcessError(retcode, cmd, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(cmd, retcode, stdout, stderr)


def ensure_runtime_paths() -> None:
    """
    Ensure isolated runtime packages in %LocalAppData%\\DubStudio\\runtime\\site-packages
    are accessible in sys.path and DLL search directories.
    Enables lightweight app layer to load modular components dynamically without pip.
    """
    if not is_packaged():
        return

    runtime_site = get_user_data_dir() / "runtime" / "site-packages"
    if runtime_site.exists():
        site_str = str(runtime_site.resolve())
        if site_str not in sys.path:
            sys.path.insert(0, site_str)

    # Register DLL directories for CUDA / ONNX / ctranslate2 if present
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        dll_candidates = [
            runtime_site / "torch" / "lib",
            runtime_site / "ctranslate2",
            runtime_site / "onnxruntime" / "capi",
            runtime_site / "nvidia" / "cublas" / "bin",
            runtime_site / "nvidia" / "cudnn" / "bin",
            runtime_site / "nvidia" / "cuda_runtime" / "bin",
        ]
        for dll_dir in dll_candidates:
            if dll_dir.exists():
                try:
                    os.add_dll_directory(str(dll_dir))
                except Exception:
                    pass


def get_velopack_updater() -> Optional[Path]:
    """Return path to Velopack Update.exe if installed on system."""
    if not is_packaged():
        return None
    exe = Path(sys.executable)
    candidates = [
        exe.parent.parent / "Update.exe",
        exe.parent / "Update.exe",
        get_user_data_dir().parent / "DubStudio" / "Update.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def trigger_app_update(update_url: str) -> bool:
    """
    Trigger Velopack Update.exe in background to check and apply delta patch from URL.
    Does not block the application.
    """
    updater = get_velopack_updater()
    if not updater or not update_url:
        return False
    try:
        import subprocess
        subprocess.Popen(
            [str(updater), "--update", update_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False
