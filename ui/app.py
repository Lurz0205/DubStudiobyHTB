"""Desktop app bootstrap and entry point."""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QSlider,
    QSpinBox,
)

from ui.main_window import MainWindow


class IgnoreWheelFilter(QObject):
    """Event filter that blocks mouse wheel scrolling on interactive widgets to prevent accidental value changes."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if isinstance(obj, (QComboBox, QSlider, QSpinBox, QDoubleSpinBox)):
                event.ignore()
                return True
        return super().eventFilter(obj, event)


def find_available_port(start_port: int = 8765, max_attempts: int = 30) -> int:
    """Find an available localhost port, testing socket binding with SO_EXCLUSIVEADDRUSE on Windows."""
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    try:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    except OSError:
                        pass
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    # Fallback to ephemeral port assigned by Windows kernel
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]
    except OSError:
        return start_port


def is_api_healthy(port: int = 8765) -> bool:
    """Check whether the local FastAPI service is fully online and healthy."""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/health",
            headers={"User-Agent": "DubStudio"}
        )
        with urllib.request.urlopen(req, timeout=0.6) as resp:
            return resp.status == 200
    except Exception:
        return False


def setup_global_exception_handler():
    """Install global sys.excepthook to prevent silent crash and log tracebacks to app.log."""
    def _handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        import logging
        import traceback
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logging.error(f"Unhandled Exception in GUI thread:\n{tb_str}")
        print(f"[Unhandled Exception] {tb_str}", file=sys.stderr)

        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                box = QMessageBox()
                box.setIcon(QMessageBox.Icon.Critical)
                box.setWindowTitle("DubStudio - Thông báo sự cố")
                box.setText("Đã xảy ra lỗi không mong muốn trong ứng dụng.")
                box.setInformativeText(str(exc_value))
                box.setDetailedText(tb_str)
                box.exec()
        except Exception:
            pass

    sys.excepthook = _handle_exception


def main():
    # Install global exception hook immediately
    setup_global_exception_handler()

    # Initialize Windows Job Object with KILL_ON_JOB_CLOSE (Kernel-level process tree isolation)
    try:
        from dubstudio.win_job import init_job_object
        init_job_object()
    except Exception as e:
        print(f"[DubStudio] Job Object initialization notice: {e}")

    # Force UTF-8 stdout on Windows console (or devnull if windowed)
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    else:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("[DubStudio] Starting application...")

    # Clean up any leftover staging/part files from previous interrupted downloads
    try:
        from dubstudio.components import cleanup_dangling_staging_files
        cleanup_dangling_staging_files()
    except Exception as e:
        print(f"[DubStudio] Staging cleanup notice: {e}")

    # Set WindowsSelectorEventLoopPolicy on Windows to prevent ProactorEventLoop WinError 10013 socketpair crash
    if sys.platform == "win32":
        import asyncio
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    # Start FastAPI server thread (with automatic port conflict fallback)
    port = find_available_port(8765)
    os.environ["DUBSTUDIO_API_PORT"] = str(port)

    if not is_api_healthy(port):
        print(f"[DubStudio] Starting background API service (FastAPI) on port {port}...")
        loop_factory = "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto"
        cfg = uvicorn.Config(
            "dubstudio.api.app:app",
            host="127.0.0.1",
            port=port,
            loop=loop_factory,
            log_level="error",
            log_config=None,
            access_log=False,
        )
        def _run_server():
            try:
                srv = uvicorn.Server(cfg)
                srv.run()
            except Exception as e:
                print(f"[DubStudio] Background API notice: {e}")

        server_thread = threading.Thread(target=_run_server, daemon=True)
        server_thread.start()

    # Wait until server is actively responding to health requests before opening GUI
    t0 = time.time()
    while (time.time() - t0) < 12.0:
        if is_api_healthy(port):
            print(f"[DubStudio] API service ready in {time.time() - t0:.2f}s (port {port})")
            break
        time.sleep(0.1)
    else:
        print(f"[DubStudio] Warning: API service took longer than 12s to respond on port {port}.")

    # Trigger background auto-update check via Velopack Update.exe if packaged
    def _check_auto_update():
        try:
            from dubstudio.config import AppConfig
            from dubstudio.packaging import is_packaged, trigger_app_update
            if is_packaged():
                cfg = AppConfig.load()
                feed = getattr(cfg.components, "components_feed_url", None)
                if feed:
                    trigger_app_update(feed)
        except Exception:
            pass

    threading.Thread(target=_check_auto_update, daemon=True).start()

    print("[DubStudio] Opening GUI...")

    # 2. Start Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("DubStudio")

    # Install global wheel filter to prevent accidental slider/combo changes on scroll
    wheel_filter = IgnoreWheelFilter(app)
    app.installEventFilter(wheel_filter)

    # 3. Create & Show MainWindow
    win = MainWindow()
    win.show()
    win.raise_()
    win.activateWindow()

    # First-run Onboarding Tutorial & Model Setup
    from dubstudio.packaging import is_first_run
    if is_first_run():
        from ui.dialogs.welcome_tutorial_dialog import WelcomeTutorialDialog
        tut_dlg = WelcomeTutorialDialog(win)
        tut_dlg.exec()

    # In packaged mode only: check GPU hardware and component updates asynchronously in background
    from dubstudio.packaging import is_packaged
    if is_packaged():
        from PyQt6.QtCore import QTimer
        def _check_bg_status():
            try:
                from ui.dialogs.gpu_prompt import check_and_prompt_gpu_if_packaged
                check_and_prompt_gpu_if_packaged(win)

                from dubstudio.components import check_for_component_updates
                from ui.dialogs.component_update_dialog import ComponentUpdateDialog
                updates = check_for_component_updates()
                if updates:
                    up_dlg = ComponentUpdateDialog(updates[0], parent=win)
                    dlg_res = up_dlg.exec()
                    if dlg_res == 1 or getattr(up_dlg, "user_agreed", False):
                        win._btn_settings.setChecked(True)
                        win._on_nav_clicked(4)
                        pkg = updates[0].get("package", {})
                        pkg_id = pkg.get("id")
                        if pkg_id and hasattr(win, "_settings_page"):
                            from PyQt6.QtCore import QTimer
                            QTimer.singleShot(250, lambda pid=pkg_id: win._settings_page._trigger_download_by_pkg_id(pid))
            except Exception:
                pass
        QTimer.singleShot(2000, _check_bg_status)

    # Install GUI Freeze Watchdog (records exact stack trace if Main Thread freezes > 1.2s, 0% CPU at idle)
    def start_gui_freeze_watchdog(threshold_sec=1.2):
        from dubstudio.paths import get_logs_dir
        log_file = get_logs_dir() / "gui_freeze_dump.log"
        main_thread_id = threading.main_thread().ident
        last_heartbeat = [time.perf_counter()]

        from PyQt6.QtCore import QTimer
        w_timer = QTimer()
        w_timer.setInterval(250)
        w_timer.timeout.connect(lambda: last_heartbeat.__setitem__(0, time.perf_counter()))
        w_timer.start()

        def watchdog_loop():
            import traceback
            while True:
                time.sleep(0.3)
                elapsed = time.perf_counter() - last_heartbeat[0]
                if elapsed > threshold_sec:
                    frames = sys._current_frames()
                    main_frame = frames.get(main_thread_id)
                    if main_frame:
                        stack_str = "".join(traceback.format_stack(main_frame))
                        try:
                            with open(log_file, "a", encoding="utf-8") as f:
                                f.write(f"\n=== PHAT HIEN DO GUI ({elapsed:.2f}s) [{time.strftime('%Y-%m-%d %H:%M:%S')}] ===\n")
                                f.write(stack_str)
                        except Exception:
                            pass
                    time.sleep(1.0)

        t = threading.Thread(target=watchdog_loop, daemon=True)
        t.start()
        return w_timer

    _freeze_watchdog_timer = start_gui_freeze_watchdog(threshold_sec=1.2)

    print("[DubStudio] Ready!")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
