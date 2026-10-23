import os
import sys
import multiprocessing

# 1. CRITICAL: Prevent infinite subprocess window spawning on Windows PyInstaller
multiprocessing.freeze_support()

# 2. Windowed Mode Stream Guards: ensure sys.stdout and sys.stderr are NEVER None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 3. Windows Stream & Encoding Guards

# 4. Check if invoked as CLI worker or Python module (-m <module>)
is_module_invocation = "-m" in sys.argv
cli_args = [a for a in sys.argv[1:] if a not in ("-m", "dubstudio")]
CLI_COMMANDS = (
    "run", "stage", "doctor", "inspect", "merge", "ui", "selftest",
    "--selftest", "-h", "--help", "-v", "--version"
)
is_cli_worker = is_module_invocation or bool(cli_args and cli_args[0] in CLI_COMMANDS)

# 5. CRITICAL: Windows Single-Instance Guard for GUI only
_instance_mutex = None
if not is_cli_worker and os.environ.get("DUBSTUDIO_DISABLE_MUTEX") != "1" and sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    ERROR_ALREADY_EXISTS = 183
    MUTEX_NAME = "Global\\DubStudio_App_Instance_Mutex_HTB"
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    _instance_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        # Check if an existing DubStudio window is visible to bring to front
        hwnd = user32.FindWindowW(None, "DubStudio - Lồng tiếng & Phụ đề tự động")
        found_window = [False]
        if hwnd and user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            found_window[0] = True
        else:
            def _enum_cb(h, _):
                length = user32.GetWindowTextLengthW(h)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(h, buff, length + 1)
                    if "DubStudio" in buff.value and user32.IsWindowVisible(h):
                        user32.ShowWindow(h, 9)  # SW_RESTORE
                        user32.SetForegroundWindow(h)
                        found_window[0] = True
                        return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)

        if found_window[0]:
            sys.exit(0)
        # If no visible window exists (e.g. dead zombie process), continue and launch GUI

from dubstudio.packaging import ensure_runtime_paths
ensure_runtime_paths()

from dubstudio.logging_setup import setup_app_logging
_app_logger = setup_app_logging()

if __name__ == "__main__":
    try:
        if is_module_invocation:
            import runpy
            m_idx = sys.argv.index("-m")
            mod_name = sys.argv[m_idx + 1]
            sys.argv = [sys.argv[0]] + sys.argv[m_idx + 2:]
            runpy.run_module(mod_name, run_name="__main__", alter_sys=True)
        elif is_cli_worker:
            from dubstudio.cli import app
            sys.argv = [sys.argv[0]] + cli_args
            app()
        else:
            from ui.app import main
            main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        _app_logger.error(f"Top-level execution error: {e}", exc_info=True)
        try:
            if sys.stderr and not getattr(sys.stderr, "closed", True):
                traceback.print_exc(file=sys.stderr)
                sys.stderr.flush()
        except Exception:
            pass
        sys.exit(1)
