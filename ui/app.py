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


def find_available_port(start_port: int = 8765) -> int:
    """Find an available localhost port, testing socket binding with SO_REUSEADDR."""
    for p in range(start_port, start_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
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


def main():
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

    # Choose available port dynamically (fallback from 8765 if blocked)
    port = find_available_port(8765)
    os.environ["DUBSTUDIO_API_PORT"] = str(port)

    # 1. Start FastAPI server thread if not already healthy
    if not is_api_healthy(port):
        print(f"[DubStudio] Starting background API service (FastAPI) on port {port}...")
        cfg = uvicorn.Config(
            "dubstudio.api.app:app",
            host="127.0.0.1",
            port=port,
            log_level="error",
            log_config=None,
            access_log=False,
        )
        def _run_server():
            import asyncio
            loop = None
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                srv = uvicorn.Server(cfg)
                loop.run_until_complete(srv.serve())
            except Exception as e:
                print(f"[DubStudio] Background API notice: {e}")
            finally:
                if loop and not loop.is_closed():
                    try:
                        loop.close()
                    except Exception:
                        pass

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
                    up_dlg.exec()
            except Exception:
                pass
        QTimer.singleShot(2000, _check_bg_status)

    # Install GUI Freeze Watchdog (records exact stack trace if Main Thread freezes > 0.5s)
    def start_gui_freeze_watchdog(threshold_sec=0.5):
        from dubstudio.paths import get_logs_dir
        log_file = get_logs_dir() / "gui_freeze_dump.log"
        main_thread_id = threading.main_thread().ident
        last_heartbeat = [time.perf_counter()]

        from PyQt6.QtCore import QTimer
        w_timer = QTimer()
        w_timer.setInterval(100)
        w_timer.timeout.connect(lambda: last_heartbeat.__setitem__(0, time.perf_counter()))
        w_timer.start()

        def watchdog_loop():
            import traceback
            while True:
                time.sleep(0.2)
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

    _freeze_watchdog_timer = start_gui_freeze_watchdog(threshold_sec=0.5)

    print("[DubStudio] Ready!")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
