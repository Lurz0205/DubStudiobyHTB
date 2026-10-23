"""Logging setup supporting UTF-8 console output, rotating app.log, and per-stage logs."""
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import sys
from typing import Optional


def get_logs_dir() -> Path:
    """Return %LocalAppData%\\DubStudio\\logs directory."""
    from dubstudio.packaging import get_user_data_dir
    d = get_user_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup_logger(
    name: str = "dubstudio",
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Configure logger with UTF-8 StreamHandler and optional file output."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicating handlers if already configured
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (stderr so it doesn't collide with stdout JSON events)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


_app_logging_initialized = False


def setup_app_logging() -> logging.Logger:
    """
    Initialize root and dubstudio rotating logger at %LocalAppData%\\DubStudio\\logs\\app.log.
    Records full startup diagnostics on first initialization.
    """
    global _app_logging_initialized
    root_logger = logging.getLogger()
    dub_logger = logging.getLogger("dubstudio")

    if not _app_logging_initialized:
        root_logger.setLevel(logging.INFO)
        log_dir = get_logs_dir()
        app_log_path = log_dir / "app.log"

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Rotating file handler (5MB, 3 backups, UTF-8)
        try:
            rfh = RotatingFileHandler(
                app_log_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            rfh.setFormatter(formatter)
            root_logger.addHandler(rfh)
        except Exception:
            pass

        # StreamHandler to stderr if stdout/stderr exist
        if sys.stderr is not None and hasattr(sys.stderr, "write"):
            sh = logging.StreamHandler(sys.stderr)
            sh.setFormatter(formatter)
            root_logger.addHandler(sh)

        _app_logging_initialized = True

        # Prune old logs to prevent disk bloat (cap total log directory at 10 MB)
        clean_old_logs(max_total_mb=10.0, max_age_days=3)

        # Log comprehensive startup diagnostics
        _log_startup_diagnostics(dub_logger)

    return dub_logger


def clean_old_logs(max_total_mb: float = 10.0, max_age_days: int = 3) -> None:
    """Auto-prune old log files to prevent logs from expanding excessively."""
    import time
    try:
        logs_dir = get_logs_dir()
        if not logs_dir.exists():
            return

        now = time.time()
        cutoff = now - (max_age_days * 86400)
        all_logs: list[Path] = []

        for p in logs_dir.rglob("*.log*"):
            if p.is_file():
                try:
                    if p.stat().st_mtime < cutoff and p.name != "app.log":
                        p.unlink()
                        continue
                except Exception:
                    pass
                all_logs.append(p)

        total_bytes = sum(p.stat().st_size for p in all_logs if p.exists())
        limit_bytes = int(max_total_mb * 1024 * 1024)
        if total_bytes > limit_bytes:
            all_logs.sort(key=lambda x: x.stat().st_mtime)
            for p in all_logs:
                if p.name == "app.log":
                    continue
                try:
                    total_bytes -= p.stat().st_size
                    p.unlink()
                    if total_bytes <= limit_bytes:
                        break
                except Exception:
                    pass
    except Exception:
        pass


def clear_all_logs() -> int:
    """Clear all stage and application logs immediately. Returns freed bytes."""
    freed = 0
    try:
        logs_dir = get_logs_dir()
        if not logs_dir.exists():
            return 0
        for p in list(logs_dir.rglob("*.log*")):
            if p.is_file():
                try:
                    sz = p.stat().st_size
                    if p.name == "app.log":
                        with open(p, "w", encoding="utf-8") as f:
                            f.write("")
                    else:
                        p.unlink()
                    freed += sz
                except Exception:
                    pass
    except Exception:
        pass
    return freed


def _log_startup_diagnostics(logger: logging.Logger) -> None:
    """Log environment, paths, tools, and components for immediate troubleshooting."""
    from dubstudio.version import get_version_info
    from dubstudio.packaging import is_packaged, get_user_data_dir, get_models_dir, get_runtime_python

    ver_info = get_version_info()
    app_version = ver_info.get("version", "unknown")
    commit_hash = ver_info.get("commit", "unknown")
    packaged_mode = is_packaged()

    app_dir = Path(sys.executable).parent if packaged_mode else Path(__file__).resolve().parent.parent
    data_dir = get_user_data_dir()
    models_dir = get_models_dir()
    logs_dir = get_logs_dir()
    runtime_py = get_runtime_python()

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    logger.info("=" * 65)
    logger.info(f"DubStudio v{app_version} (Commit: {commit_hash}) - Logging Initialized")
    logger.info(f"is_packaged: {packaged_mode} | sys.executable: {sys.executable}")
    logger.info(f"cwd: {os.getcwd()} | app_dir: {app_dir}")
    logger.info(f"data_dir: {data_dir} | models_dir: {models_dir} | logs_dir: {logs_dir}")
    logger.info(f"runtime_python: {runtime_py} (exists: {runtime_py.exists()})")
    logger.info(f"ffmpeg found: {ffmpeg_path} | ffprobe found: {ffprobe_path}")
    logger.info(f"PYTHONUTF8: {os.environ.get('PYTHONUTF8')} | HF_HOME: {os.environ.get('HF_HOME')}")
    logger.info(f"PATH: {os.environ.get('PATH')}")

    # Check component availability
    try:
        from dubstudio.components import sync_installed_components
        status = sync_installed_components()
        logger.info(f"Installed components: {list(status.keys())}")
    except Exception as e:
        logger.warning(f"Could not inspect component status: {e}")

    logger.info("=" * 65)


def get_stage_logger(stage_name: str, job_id: Optional[str] = None) -> logging.Logger:
    """Create or retrieve logger writing to a specific stage log file."""
    logger_name = f"dubstudio.stage.{stage_name}"
    logger = logging.getLogger(logger_name)

    log_dir = get_logs_dir() / "stages"
    log_dir.mkdir(parents=True, exist_ok=True)
    stage_log_path = log_dir / f"{stage_name}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Avoid duplicate file handlers
    has_stage_file = any(
        isinstance(h, (logging.FileHandler, RotatingFileHandler)) and getattr(h, "baseFilename", "").endswith(f"{stage_name}.log")
        for h in logger.handlers
    )
    if not has_stage_file:
        try:
            rfh = RotatingFileHandler(
                stage_log_path,
                maxBytes=2 * 1024 * 1024,
                backupCount=2,
                encoding="utf-8",
            )
            rfh.setFormatter(formatter)
            logger.addHandler(rfh)
        except Exception:
            pass

    return logger
