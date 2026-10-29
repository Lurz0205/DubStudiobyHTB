"""DubStudio v2.0.0 — Modern Studio Desktop Shell (PyWebView + React/Tailwind).

Features:
- Zero Hardcoded Ports: Uses dynamic ephemeral port allocation (bind 127.0.0.1:0) for media streaming.
- Direct In-Memory DesktopAPIBridge: High-performance, memory-direct RPC between React and Python.
- Process & Thread Isolation: Heavy AI stages run in isolated background threads pushing progress via CustomEvent.
- Native Studio Window: Frameless, dark theme (#070B14), context menu disabled, smooth window controls.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Multiprocessing freeze support for Windows
if __name__ == "__main__":
    multiprocessing.freeze_support()

# Windows asyncio Proactor WinError 10054 Suppression
if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost
        def _safe_call_connection_lost(self, exc):
            try:
                _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError) as e:
                if getattr(e, "winerror", None) != 10054 and not isinstance(e, ConnectionResetError):
                    raise
        _ProactorBasePipeTransport._call_connection_lost = _safe_call_connection_lost
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows UTF-8 Stream Guards
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

# Check if invoked as CLI worker or Python module (-m <module>)
is_module_invocation = "-m" in sys.argv
cli_args = [a for a in sys.argv[1:] if a not in ("-m", "dubstudio")]
CLI_COMMANDS = (
    "run", "stage", "doctor", "inspect", "merge", "ui", "selftest",
    "--selftest", "-h", "--help", "-v", "--version"
)
is_testing = "pytest" in sys.modules or any("pytest" in a for a in sys.argv)
is_cli_worker = is_module_invocation or bool(cli_args and cli_args[0] in CLI_COMMANDS) or "-c" in sys.argv or is_testing or (__name__ != "__main__")

# Windows Single-Instance Guard for GUI only
_instance_mutex = None
if not is_cli_worker and os.environ.get("DUBSTUDIO_DISABLE_MUTEX") != "1" and sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    ERROR_ALREADY_EXISTS = 183
    ERROR_ACCESS_DENIED = 5
    MUTEX_NAME = "Local\\DubStudio_App_Instance_Mutex_HTB_v2"
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    _instance_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_err = kernel32.GetLastError()
    if last_err in (ERROR_ALREADY_EXISTS, ERROR_ACCESS_DENIED) or _instance_mutex == 0:
        exact_title = "DubStudio 2.0"
        hwnd = user32.FindWindowW(None, exact_title)
        if hwnd and user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
        sys.exit(0)

# Hotpatches & Runtime paths
try:
    from dubstudio.hotpatch import apply_hotpatches
    apply_hotpatches()
except Exception:
    pass

from dubstudio.packaging import ensure_runtime_paths
ensure_runtime_paths()

# Initialize Windows configuration & CUDA DLLs if available
if sys.platform == "win32":
    try:
        from dubstudio.config import AppConfig
        AppConfig.load()
    except Exception:
        pass


def find_free_port() -> int:
    """Acquire an OS-assigned ephemeral free port on loopback interface."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


class DesktopAPIBridge:
    """
    Direct in-memory native bridge exposed to JavaScript (window.pywebview.api).
    Provides instant RPC without external HTTP overhead.
    """

    def __init__(self):
        self._window = None
        self._is_maximized = False
        self._active_workers: Dict[str, threading.Thread] = {}
        self._port = 0

    def set_window(self, window):
        self._window = window

    def set_port(self, port: int):
        self._port = port

    # --- 1. Native Window Controls & File Dialogs ---

    def minimize(self):
        if self._window:
            self._window.minimize()

    def toggle_maximize(self):
        if self._window:
            if self._is_maximized:
                self._window.restore()
                self._is_maximized = False
            else:
                self._window.maximize()
                self._is_maximized = True

    def close(self):
        if self._window:
            self._window.destroy()

    def open_video_dialog(self) -> Optional[str]:
        """Open Windows native file dialog to choose a video file."""
        import webview
        if not self._window:
            return None
        file_types = ('Video Files (*.mp4;*.mkv;*.mov;*.webm;*.avi;*.ts)', 'All Files (*.*)')
        dialog_type = getattr(getattr(webview, 'FileDialog', None), 'OPEN', getattr(webview, 'OPEN_DIALOG', 10))
        res = self._window.create_file_dialog(
            dialog_type,
            allow_multiple=False,
            file_types=file_types
        )
        if res and len(res) > 0:
            return res[0]
        return None

    def open_folder_dialog(self, default_dir: str = "") -> Optional[str]:
        """Open Windows native folder selection dialog."""
        import webview
        if not self._window:
            return None
        dialog_type = getattr(getattr(webview, 'FileDialog', None), 'FOLDER', getattr(webview, 'FOLDER_DIALOG', 20))
        res = self._window.create_file_dialog(
            dialog_type,
            directory=default_dir or ""
        )
        if res and len(res) > 0:
            return res[0]
        return None

    def open_image_dialog(self) -> Optional[str]:
        """Open Windows native file dialog to select an image file (PNG, JPG, WebP)."""
        import webview
        if not self._window:
            return None
        file_types = ('Image Files (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.svg)', 'All files (*.*)')
        dialog_type = getattr(getattr(webview, 'FileDialog', None), 'OPEN', getattr(webview, 'OPEN_DIALOG', 10))
        res = self._window.create_file_dialog(
            dialog_type,
            allow_multiple=False,
            file_types=file_types
        )
        if res and len(res) > 0:
            return res[0]
        return None

    def open_multiple_videos_dialog(self) -> List[str]:
        """Open Windows native file dialog to choose multiple video files."""
        import webview
        if not self._window:
            return []
        file_types = ('Video Files (*.mp4;*.mkv;*.mov;*.webm;*.avi;*.ts)', 'All Files (*.*)')
        dialog_type = getattr(getattr(webview, 'FileDialog', None), 'OPEN', getattr(webview, 'OPEN_DIALOG', 10))
        res = self._window.create_file_dialog(
            dialog_type,
            allow_multiple=True,
            file_types=file_types
        )
        if res and len(res) > 0:
            return list(res)
        return []

    def probe_video_info(self, video_path: str) -> Dict[str, Any]:
        """Probe video duration, dimensions, framerate and audio profile."""
        from dubstudio.ffmpeg_utils import probe_file
        from dubstudio.tools.merge import extract_media_profile
        p = Path(video_path)
        if not p.exists():
            return {"status": "error", "message": "File không tồn tại"}
        try:
            info = probe_file(p)
            v_prof, a_prof = extract_media_profile(info)
            dur = float(info.get("format", {}).get("duration", 0.0) or 0.0)
            return {
                "status": "success",
                "duration": dur,
                "video": v_prof,
                "audio": a_prof,
                "filename": p.name,
                "filepath": str(p.resolve()),
                "filesize": p.stat().st_size,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def trim_video(
        self,
        video_path: str,
        start_s: float,
        end_s: float,
        output_name: str = "",
        fast_copy: bool = True
    ) -> Dict[str, Any]:
        """Trim video segment with sub-second precision."""
        from dubstudio.tools.trim_video import trim_video
        from dubstudio.paths import get_out_dir
        try:
            out_dir = get_out_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            out_p = (out_dir / output_name) if output_name else None
            res = trim_video(
                video_path=video_path,
                start_s=start_s,
                end_s=end_s,
                output_path=out_p,
                fast_copy=fast_copy
            )
            return {
                "status": "success",
                "output_path": str(res.resolve()),
                "filename": res.name,
                "filesize": res.stat().st_size,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def merge_videos(
        self,
        video_paths: List[str],
        output_name: str = "merged_video.mp4",
        force_reencode: bool = False
    ) -> Dict[str, Any]:
        """Merge / concat multiple video files."""
        from dubstudio.tools.merge import merge_videos
        from dubstudio.paths import get_out_dir
        try:
            paths = [Path(p) for p in video_paths]
            out_dir = get_out_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            out_p = out_dir / (output_name or "merged_video.mp4")
            res = merge_videos(
                video_paths=paths,
                output_path=out_p,
                force_reencode=force_reencode
            )
            return {
                "status": "success",
                "output_path": str(res.resolve()),
                "filename": res.name,
                "filesize": res.stat().st_size,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def preview_voice(self, voice: str) -> Dict[str, Any]:
        """Generate or retrieve a voice sample preview file for Settings."""
        from dubstudio.paths import get_out_dir
        import urllib.parse
        import shutil
        preview_dir = get_out_dir() / "voice_previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        wav_path = preview_dir / f"{voice}.wav"

        # Check pre-bundled locations first to guarantee 0ms instant playback
        if not wav_path.exists() or wav_path.stat().st_size < 1024:
            candidates = [
                Path("out/voice_previews") / f"{voice}.wav",
                Path(__file__).resolve().parent / "out" / "voice_previews" / f"{voice}.wav",
                Path(__file__).resolve().parent / "dubstudio" / "resources" / "voice_previews" / f"{voice}.wav",
                Path(sys.executable).resolve().parent / "out" / "voice_previews" / f"{voice}.wav",
                Path(sys.executable).resolve().parent / "_internal" / "out" / "voice_previews" / f"{voice}.wav",
                Path(sys.executable).resolve().parent / "_internal" / "dubstudio" / "resources" / "voice_previews" / f"{voice}.wav",
            ]
            for cand in candidates:
                if cand.exists() and cand.stat().st_size >= 1024:
                    try:
                        shutil.copy2(cand, wav_path)
                        break
                    except Exception:
                        wav_path = cand
                        break

        if not wav_path.exists() or wav_path.stat().st_size < 1024:
            sample_text = f"Xin chào, đây là giọng đọc {voice} của DubStudio."
            from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs
            import subprocess
            cmd = [
                str(get_runtime_python().resolve()), "-m", "dubstudio.tts.single_tts",
                "--text", sample_text,
                "--voice", voice,
                "--speed", "1.0",
                "--out", str(wav_path.resolve()),
            ]
            try:
                subprocess.run(cmd, check=True, env=get_subprocess_env(), **get_subprocess_kwargs())
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {
            "status": "success",
            "audio_url": f"/api/local-file?path={urllib.parse.quote(str(wav_path.resolve()))}",
            "file_path": str(wav_path.resolve()),
        }

    # --- 2. In-Memory Project & Workspace Management ---

    def create_project(self, video_path: str, title: str = "") -> Dict[str, Any]:
        """Initialize a new project from a selected video file."""
        from dubstudio.paths import get_workspace_dir
        import shutil
        import re
        v_p = Path(video_path)
        if not v_p.exists():
            return {"status": "error", "message": "Tệp video không tồn tại"}

        clean_name = re.sub(r'[^\w\-_]', '_', v_p.stem)
        job_id = f"{clean_name}_{int(time.time())}"
        ws = get_workspace_dir() / job_id
        ws.mkdir(parents=True, exist_ok=True)

        target_input = ws / "input.mp4"
        try:
            shutil.copy2(v_p, target_input)
        except Exception as e:
            return {"status": "error", "message": f"Không thể sao chép video: {e}"}

        app_settings = self.get_app_settings()
        from dubstudio.tts.base import clean_voice_name
        def_male = clean_voice_name(app_settings.get("default_male_voice"), "Minh Đức")
        def_female = clean_voice_name(app_settings.get("default_female_voice"), "Quỳnh Anh")

        job_cfg = {
            "job_id": job_id,
            "title": title or v_p.stem,
            "source_video": str(v_p.resolve()),
            "created_at": time.time(),
            "default_male_voice": def_male,
            "default_female_voice": def_female,
            "voice_male": def_male,
            "voice_female": def_female,
            "single_voice_gender": "male",
            "single_voice": def_male,
            "translation_tone": app_settings.get("translation_tone", "Tự nhiên, đời thường"),
        }
        (ws / "job_config.json").write_text(json.dumps(job_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "success", "job_id": job_id, "title": job_cfg["title"]}

    def get_projects(self) -> List[Dict[str, Any]]:
        """List all available projects directly from workspace with step progress."""
        from dubstudio.paths import get_workspace_dir
        ws = get_workspace_dir()
        projects = []
        if not ws.exists():
            return projects

        non_job_dirs = {".cache", ".edge_profile", "components", "__pycache__"}
        for p in ws.iterdir():
            if p.is_dir() and not p.name.startswith(".") and p.name not in non_job_dirs:
                has_video = (p / "input.mp4").exists()
                job_cfg_file = p / "job_config.json"
                seg_file = p / "segments.json"
                has_subtitles = False
                if seg_file.exists():
                    try:
                        s_data = json.loads(seg_file.read_text(encoding="utf-8"))
                        segs = s_data.get("segments", []) if isinstance(s_data, dict) else s_data
                        has_subtitles = bool(isinstance(segs, list) and len(segs) > 0)
                    except Exception:
                        has_subtitles = False
                has_state = (p / "state.json").exists()
                if not has_video and not job_cfg_file.exists() and not has_subtitles and not has_state:
                    # Skip completely empty zombie folders
                    continue

                title = p.name
                if job_cfg_file.exists():
                    try:
                        cfg_data = json.loads(job_cfg_file.read_text(encoding="utf-8"))
                        title = cfg_data.get("title", p.name)
                    except Exception:
                        pass
                
                mtime = p.stat().st_mtime
                has_dub = (p / "voice_track.wav").exists() or (p / "voice_raw.wav").exists()
                has_export = (p / "out" / "final.mp4").exists()

                step = 1
                if has_subtitles:
                    step = 2
                if has_dub:
                    step = 3
                if has_export:
                    step = 4

                projects.append({
                    "id": p.name,
                    "title": title,
                    "modified_time": mtime,
                    "has_video": has_video,
                    "has_subtitles": has_subtitles,
                    "has_dub": has_dub,
                    "has_export": has_export,
                    "step": step,
                })

        projects.sort(key=lambda x: x["modified_time"], reverse=True)
        return projects

    def delete_project(self, job_id: str) -> Dict[str, Any]:
        """Safely delete project workspace folder and associated export files."""
        from dubstudio.paths import resolve_job_workspace, get_out_dir
        import shutil
        import stat
        ws = resolve_job_workspace(job_id)
        project_title = ""

        if ws.exists():
            cfg_p = ws / "job_config.json"
            if cfg_p.exists():
                try:
                    c_data = json.loads(cfg_p.read_text(encoding="utf-8"))
                    project_title = str(c_data.get("title", "")).strip()
                except Exception:
                    pass

            def on_rm_error(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass

            for attempt in range(5):
                try:
                    shutil.rmtree(ws, onerror=on_rm_error)
                    if not ws.exists():
                        break
                except Exception:
                    time.sleep(0.05 * (attempt + 1))

        if ws.exists():
            return {"status": "error", "message": "Không thể xóa hoàn toàn thư mục dự án do Windows đang khóa tệp."}

        # Clean up any leftover files in output directory matching job_id or project_title
        out_dirs = [get_out_dir()]
        try:
            s_file = Path("config") / "app_settings.json"
            if s_file.exists():
                s_data = json.loads(s_file.read_text(encoding="utf-8"))
                if s_data.get("out_dir"):
                    out_dirs.append(Path(s_data["out_dir"]))
        except Exception:
            pass

        for od in out_dirs:
            if not od.exists():
                continue
            for f in list(od.glob(f"{job_id}*")):
                try:
                    if f.is_file():
                        f.unlink()
                except Exception:
                    pass
            if project_title and project_title != "default":
                for ext in [".mp4", ".srt", ".ass", ".wav"]:
                    f = od / f"{project_title}{ext}"
                    if f.exists() and f.is_file():
                        try:
                            f.unlink()
                        except Exception:
                            pass

        return {"status": "success"}

    def rename_project(self, job_id: str, new_title: str) -> Dict[str, Any]:
        """Rename project title in metadata."""
        from dubstudio.paths import resolve_job_workspace
        ws = resolve_job_workspace(job_id)
        if ws.exists():
            cfg_file = ws / "job_config.json"
            c_data = {}
            if cfg_file.exists():
                try:
                    c_data = json.loads(cfg_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            c_data["title"] = new_title.strip()
            cfg_file.write_text(json.dumps(c_data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"status": "success"}
        return {"status": "error", "message": "Dự án không tồn tại"}

    def get_project_data(self, job_id: str) -> Dict[str, Any]:
        """Fetch all metadata, cues, and mix settings for a project directly in memory."""
        from dubstudio.paths import resolve_job_workspace
        ws = resolve_job_workspace(job_id)
        if not ws.exists():
            return {"error": "Project not found"}

        job_cfg_file = ws / "job_config.json"
        job_cfg = {}
        if job_cfg_file.exists():
            try:
                job_cfg = json.loads(job_cfg_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        has_preview_dubbed = (ws / "preview_dubbed.mp4").exists() and (ws / "preview_dubbed.mp4").stat().st_size > 1024
        has_input_video = (ws / "input.mp4").exists()
        
        preview_video_url = None
        if has_preview_dubbed:
            preview_video_url = f"/media/workspace/{job_id}/preview_dubbed.mp4?t={int(time.time())}"
        elif has_input_video:
            preview_video_url = f"/media/workspace/{job_id}/input.mp4"

        from dubstudio.tts.base import clean_voice_name
        app_settings = self.get_app_settings()
        def_male = clean_voice_name(app_settings.get("default_male_voice"), "Minh Đức")
        def_female = clean_voice_name(app_settings.get("default_female_voice"), "Quỳnh Anh")

        voice_male = clean_voice_name(job_cfg.get("default_male_voice") or job_cfg.get("voice_male") or def_male, def_male)
        voice_female = clean_voice_name(job_cfg.get("default_female_voice") or job_cfg.get("voice_female") or def_female, def_female)
        single_gender = job_cfg.get("single_voice_gender", "male")
        single_voice = clean_voice_name(job_cfg.get("single_voice") or (voice_female if single_gender == "female" else voice_male), voice_male)

        # Self-heal job_config.json if it contained outdated or tagged voice strings
        if (
            job_cfg.get("default_male_voice") != voice_male or
            job_cfg.get("default_female_voice") != voice_female or
            job_cfg.get("single_voice") != single_voice
        ):
            job_cfg["default_male_voice"] = voice_male
            job_cfg["voice_male"] = voice_male
            job_cfg["default_female_voice"] = voice_female
            job_cfg["voice_female"] = voice_female
            job_cfg["single_voice"] = single_voice
            job_cfg["single_voice_gender"] = single_gender
            try:
                job_cfg_file.write_text(json.dumps(job_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        result = {
            "id": job_id,
            "title": job_cfg.get("title", job_id),
            "segments": [],
            "style": {},
            "config": {
                "words_per_line": job_cfg.get("words_per_line", 6),
                "translation_tone": job_cfg.get("translation_tone", job_cfg.get("style", app_settings.get("translation_tone", "Tự nhiên, đời thường"))),
                "detect_gender": job_cfg.get("detect_gender", False),
                "single_voice_gender": single_gender,
                "single_voice": single_voice,
                "voice_male": voice_male,
                "voice_female": voice_female,
                "default_male_voice": voice_male,
                "default_female_voice": voice_female,
            },
            "has_input_video": has_input_video,
            "has_preview_dubbed": has_preview_dubbed,
            "preview_video_url": preview_video_url,
            "has_raw_voice": (ws / "voice_raw.wav").exists() or (ws / "voice_track.wav").exists(),
            "has_bgm": (ws / "audio" / "bgm.wav").exists(),
            "has_vocals": (ws / "audio" / "vocals.wav").exists() or (ws / "audio" / "orig.wav").exists(),
            "voice_url": (
                f"/media/workspace/{job_id}/voice_raw.wav?t={int(time.time() * 1000)}"
                if (ws / "voice_raw.wav").exists()
                else (
                    f"/media/workspace/{job_id}/voice_track.wav?t={int(time.time() * 1000)}"
                    if (ws / "voice_track.wav").exists()
                    else None
                )
            ),
            "bgm_url": (
                f"/media/workspace/{job_id}/audio/bgm.wav?t={int(time.time() * 1000)}"
                if (ws / "audio" / "bgm.wav").exists()
                else None
            ),
            "vocals_url": (
                f"/media/workspace/{job_id}/audio/vocals.wav?t={int(time.time() * 1000)}"
                if (ws / "audio" / "vocals.wav").exists()
                else (
                    f"/media/workspace/{job_id}/audio/orig.wav?t={int(time.time() * 1000)}"
                    if (ws / "audio" / "orig.wav").exists()
                    else None
                )
            ),
            "media_base_url": f"/media/workspace/{job_id}",
        }

        # Resilient video duration calculation
        video_dur = 0.0
        probe_f = ws / "probe.json"
        if probe_f.exists():
            try:
                p_data = json.loads(probe_f.read_text(encoding="utf-8"))
                video_dur = float(p_data.get("format", {}).get("duration", 0.0) or 0.0)
            except Exception:
                pass
        if video_dur <= 0.0 and (ws / "segments.json").exists():
            try:
                seg_f = json.loads((ws / "segments.json").read_text(encoding="utf-8"))
                video_dur = float(seg_f.get("video", {}).get("duration", 0.0) or 0.0)
            except Exception:
                pass
        if video_dur <= 0.0 and (ws / "input.mp4").exists():
            try:
                from dubstudio.ffmpeg_utils import probe_media
                p_info = probe_media(ws / "input.mp4")
                video_dur = float(p_info.get("format", {}).get("duration", 0.0) or 0.0)
            except Exception:
                pass
        result["duration"] = round(video_dur, 2)

        # Segments (Multi-source resilient loader: segments.json -> units.json -> raw_segments.json -> asr.json)
        raw_segments = []
        seg_p = ws / "segments.json"
        units_p = ws / "units.json"
        raw_p = ws / "raw_segments.json"
        asr_p = ws / "asr.json"

        def _extract_items(data_obj):
            if isinstance(data_obj, dict):
                return data_obj.get("segments", [])
            elif isinstance(data_obj, list):
                return data_obj
            return []

        if seg_p.exists():
            try:
                parsed = json.loads(seg_p.read_text(encoding="utf-8"))
                raw_segments = _extract_items(parsed)
            except Exception:
                raw_segments = []

        # Resilient fallback 1: units.json (units often hold the primary translated cues)
        if not raw_segments and units_p.exists():
            try:
                parsed = json.loads(units_p.read_text(encoding="utf-8"))
                raw_segments = _extract_items(parsed)
            except Exception:
                pass

        # Resilient fallback 2: raw_segments.json
        if not raw_segments and raw_p.exists():
            try:
                parsed = json.loads(raw_p.read_text(encoding="utf-8"))
                raw_segments = _extract_items(parsed)
            except Exception:
                pass

        # Resilient fallback 3: asr.json
        if not raw_segments and asr_p.exists():
            try:
                parsed = json.loads(asr_p.read_text(encoding="utf-8"))
                raw_segments = _extract_items(parsed)
            except Exception:
                pass

        if raw_segments:
            tts_dir = ws / "tts"
            for idx, s in enumerate(raw_segments):
                if not isinstance(s, dict):
                    continue
                # Ensure unique id
                if "id" not in s or s["id"] is None:
                    s["id"] = idx + 1
                txt = (s.get("vi_text") or s.get("text") or "").strip()
                s["text"] = txt
                s["vi_text"] = txt
                if "orig" not in s and "zh" in s:
                    s["orig"] = s["zh"]
                elif "orig" not in s and "text" in s and not txt:
                    s["orig"] = s["text"]
                if s.get("voice"):
                    s["voice"] = clean_voice_name(s["voice"], voice_male)
                sid = s.get("id")
                if sid is not None and (tts_dir / f"{int(sid):04d}.wav").exists():
                    s["has_tts"] = True
                    s["tts_file"] = f"tts/{int(sid):04d}.wav"
                    if not s.get("tts_dur"):
                        try:
                            import soundfile as sf
                            info = sf.info(str(tts_dir / f"{int(sid):04d}.wav"))
                            s["tts_dur"] = round(info.duration, 3)
                        except Exception:
                            pass
            result["segments"] = raw_segments

            # Auto self-heal segments.json if it was empty/missing but recovered from fallbacks
            if not seg_p.exists() or seg_p.stat().st_size < 10:
                try:
                    atomic_write_json(seg_p, {
                        "version": "1.0",
                        "video": job_cfg.get("video", "input.mp4"),
                        "segments": raw_segments,
                        "translation_style": job_cfg.get("style", "Tự nhiên, đời thường"),
                    })
                except Exception:
                    pass

        # Subtitle Style (Full typography, box styling, colors)
        style_p = ws / "style.json"
        if style_p.exists():
            try:
                result["style"].update(json.loads(style_p.read_text(encoding="utf-8")))
            except Exception:
                pass

        # Mix Settings (Volumes and audio channels)
        mix_p = ws / "mix_settings.json"
        if mix_p.exists():
            try:
                mix_vals = json.loads(mix_p.read_text(encoding="utf-8"))
                result["style"].update(mix_vals)
            except Exception:
                pass

        return result

    def auto_split_cues(self, job_id: str, words_per_line: int = 6) -> Dict[str, Any]:
        """Auto-split subtitle sentences according to estimated word count rule."""
        from dubstudio.paths import resolve_job_workspace
        from dubstudio.subtitles.cue_split import auto_split_all_units
        from dubstudio.jobstate import atomic_write_json
        ws = resolve_job_workspace(job_id)
        seg_p = ws / "segments.json"
        if not seg_p.exists():
            return {"status": "error", "message": "Chưa có phụ đề trong tác vụ"}
        try:
            full_data = json.loads(seg_p.read_text(encoding="utf-8"))
            segments = full_data.get("segments", []) if isinstance(full_data, dict) else full_data
            analysis_file = ws / "analysis.json"
            analysis_data = {}
            if analysis_file.exists():
                try:
                    analysis_data = json.loads(analysis_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            updated = auto_split_all_units(segments, target_n=words_per_line, analysis=analysis_data, force=True)

            # Sync vi_text and text with cues for every segment
            for seg in updated:
                cues = seg.get("cues")
                if cues and isinstance(cues, list) and len(cues) > 1:
                    new_vi = "\n".join(c.get("text", "").strip() for c in cues if c.get("text", "").strip())
                    seg["vi_text"] = new_vi
                    seg["text"] = new_vi
                else:
                    seg["text"] = seg.get("vi_text") or seg.get("text") or ""
                seg["orig"] = seg.get("zh") or seg.get("orig") or seg.get("src_text") or ""
                from dubstudio.text.vi_normalize import normalize_for_tts
                raw_t = seg.get("vi_text") or seg.get("text") or ""
                seg["tts_text"] = normalize_for_tts(raw_t.replace("\n", " "))

            if isinstance(full_data, dict):
                full_data["segments"] = updated
                atomic_write_json(seg_p, full_data)
            else:
                atomic_write_json(seg_p, {"segments": updated})

            units_file = ws / "units.json"
            if units_file.exists():
                try:
                    units_file.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass

            cfg_file = ws / "job_config.json"
            if cfg_file.exists():
                try:
                    c = json.loads(cfg_file.read_text(encoding="utf-8"))
                    c["words_per_line"] = words_per_line
                    cfg_file.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass

            frontend_cues = []
            for idx, s in enumerate(updated):
                cue = dict(s)
                cue["id"] = s.get("id") or idx + 1
                cue["start"] = s.get("start", 0)
                cue["end"] = s.get("end", 0)
                cue["text"] = s.get("text") or s.get("vi_text") or ""
                cue["orig"] = s.get("orig") or s.get("zh") or ""
                cue["voice"] = s.get("voice") or "Minh Đức"
                cue["speed"] = s.get("speed", 1.0)
                cue["cues"] = s.get("cues")
                if s.get("tts_file") or (s.get("tts_dur") and s.get("tts_dur") > 0) or s.get("has_tts"):
                    cue["has_tts"] = True
                frontend_cues.append(cue)
            return {"status": "success", "segments": frontend_cues}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def run_pipeline(self, job_id: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute AI Pipeline (subtitles_only, dub_only, or full) in background thread."""
        opts = options or {}
        subtitles_only = bool(opts.get("subtitles_only", False))
        dub_only = bool(opts.get("dub_only", False))
        words_per_line = int(opts.get("words_per_line", 6))

        from dubstudio.paths import resolve_job_workspace
        ws = resolve_job_workspace(job_id)
        if not ws.exists():
            return {"status": "error", "message": "Tác vụ không tồn tại"}

        # Save config preferences
        cfg_file = ws / "job_config.json"
        cfg_data = {}
        if cfg_file.exists():
            try:
                cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        if "style" in opts:
            cfg_data["translation_tone"] = opts["style"]
            cfg_data["style"] = opts["style"]
        if "detect_gender" in opts:
            cfg_data["detect_gender"] = bool(opts["detect_gender"])
        if "single_voice_gender" in opts:
            cfg_data["single_voice_gender"] = opts["single_voice_gender"]
        from dubstudio.tts.base import clean_voice_name
        if "single_voice" in opts and opts["single_voice"]:
            cfg_data["single_voice"] = clean_voice_name(opts["single_voice"], "Minh Đức")
        if "voice_male" in opts and opts["voice_male"]:
            clean_m = clean_voice_name(opts["voice_male"], "Minh Đức")
            cfg_data["default_male_voice"] = clean_m
            cfg_data["voice_male"] = clean_m
        if "voice_female" in opts and opts["voice_female"]:
            clean_f = clean_voice_name(opts["voice_female"], "Quỳnh Anh")
            cfg_data["default_female_voice"] = clean_f
            cfg_data["voice_female"] = clean_f
        cfg_data["words_per_line"] = words_per_line
        cfg_file.write_text(json.dumps(cfg_data, ensure_ascii=False, indent=2), encoding="utf-8")

        video_path = ws / "input.mp4"
        if not video_path.exists():
            return {"status": "error", "message": "Không tìm thấy file video input.mp4"}

        def worker():
            from dubstudio.events import add_event_listener, remove_event_listener
            from dubstudio.api.app import _run_pipeline_worker

            def on_pipe_event(ev):
                if isinstance(ev, dict):
                    stg = str(ev.get("stage", "pipeline"))
                    pct = float(ev.get("pct", ev.get("progress", 0.0)) or 0.0)
                    msg = str(ev.get("msg", ev.get("message", "")))
                    lvl = str(ev.get("level", "info"))
                else:
                    stg = str(getattr(ev, "stage", "pipeline"))
                    pct = float(getattr(ev, "progress", getattr(ev, "pct", 0.0)) or 0.0)
                    msg = str(getattr(ev, "message", getattr(ev, "msg", "")))
                    lvl = str(getattr(ev, "level", "info"))

                overall_pct = pct
                if subtitles_only:
                    if stg == "ingest":
                        overall_pct = 2.0 + (pct / 100.0) * 3.0
                    elif stg == "extract_audio":
                        overall_pct = 5.0 + (pct / 100.0) * 5.0
                    elif stg == "separate":
                        overall_pct = 10.0 + (pct / 100.0) * 40.0
                    elif stg == "asr":
                        overall_pct = 50.0 + (pct / 100.0) * 30.0
                    elif stg in ("analyze", "translate"):
                        overall_pct = 80.0 + (pct / 100.0) * 18.0
                    elif stg == "pipeline":
                        overall_pct = pct
                elif dub_only:
                    if stg == "tts":
                        overall_pct = 5.0 + (pct / 100.0) * 65.0
                    elif stg == "fit":
                        overall_pct = 70.0 + (pct / 100.0) * 15.0
                    elif stg == "mix":
                        overall_pct = 85.0 + (pct / 100.0) * 13.0
                    elif stg == "pipeline":
                        overall_pct = pct

                evt_dict = {
                    "stage": stg,
                    "progress": min(99.0, max(5.0, round(overall_pct, 1))),
                    "message": msg or f"Đang xử lý {stg}...",
                    "level": lvl,
                    "job_id": job_id,
                }
                ev_data = ev.get("data") if isinstance(ev, dict) else getattr(ev, "data", None)
                if ev_data:
                    evt_dict["data"] = ev_data
                self.emit_event_to_ui(evt_dict)

            add_event_listener(on_pipe_event)
            try:
                action_name = "Tạo phụ đề" if subtitles_only else ("Tạo lồng tiếng" if dub_only else "Xử lý AI")
                self.emit_event_to_ui({
                    "stage": "init",
                    "progress": 5.0,
                    "message": f"Đang khởi động {action_name}...",
                    "level": "info",
                    "job_id": job_id,
                })
                _run_pipeline_worker(job_id, video_path, subtitles_only=subtitles_only, dub_only=dub_only)

                # If subtitles_only, auto split cues
                if subtitles_only:
                    try:
                        self.auto_split_cues(job_id, words_per_line=words_per_line)
                    except Exception:
                        pass

                # Cleanly close Gemini browser tab after subtitle translation / fit completion
                try:
                    from dubstudio.llm.cdp_gemini import close_gemini_tabs
                    close_gemini_tabs(9222)
                except Exception:
                    pass

                self.emit_event_to_ui({
                    "stage": "done",
                    "progress": 100.0,
                    "message": f"Hoàn tất {action_name}!",
                    "level": "success",
                    "job_id": job_id,
                })
            except Exception as e:
                self.emit_event_to_ui({
                    "stage": "error",
                    "progress": 0.0,
                    "message": f"Lỗi: {str(e)}",
                    "level": "error",
                    "job_id": job_id,
                })
            finally:
                remove_event_listener(on_pipe_event)

        th = threading.Thread(target=worker, daemon=True)
        th.start()
        return {"status": "started", "job_id": job_id}

    def submit_manual_translation(self, job_id: str, text: str, cancelled: bool = False) -> Dict[str, Any]:
        """Deliver user's manual translated text into workspace for translate.py to resume."""
        from dubstudio.paths import resolve_job_workspace
        ws = resolve_job_workspace(job_id)
        if not ws.exists():
            return {"status": "error", "message": "Job not found"}
        resp_file = ws / "manual_translate_response.json"
        data = {
            "text": text.strip(),
            "cancelled": bool(cancelled),
            "timestamp": time.time(),
        }
        resp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "success"}

    def get_manual_translate_prompt(self, job_id: str) -> Dict[str, Any]:
        """Retrieve current manual translation prompt text if present."""
        from dubstudio.paths import resolve_job_workspace
        ws = resolve_job_workspace(job_id)
        prompt_file = ws / "manual_translate_prompt.txt"
        if prompt_file.exists():
            return {
                "status": "success",
                "prompt": prompt_file.read_text(encoding="utf-8"),
            }
        return {"status": "error", "message": "Prompt not found"}

    def open_file_path(self, path: str) -> Dict[str, Any]:
        """Open a video or media file with default system application."""
        p = Path(path)
        if p.exists() and sys.platform == "win32":
            try:
                os.startfile(str(p.resolve()))
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Tệp không tồn tại"}

    def open_folder_path(self, path: str) -> Dict[str, Any]:
        """Open containing folder in Windows Explorer."""
        p = Path(path)
        target = p if p.is_dir() else p.parent
        if target.exists() and sys.platform == "win32":
            import subprocess
            subprocess.run(["explorer", str(target.resolve())], check=False)
            return {"status": "success"}
        return {"status": "error", "message": "Thư mục không tồn tại"}


    def save_project_segments(self, job_id: str, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save edited segments directly to disk without network delay."""
        from dubstudio.paths import resolve_job_workspace
        from dubstudio.jobstate import atomic_write_json
        ws = resolve_job_workspace(job_id)
        if not ws.exists():
            return {"status": "error", "message": "Project not found"}

        seg_p = ws / "segments.json"
        full_data = {}
        if seg_p.exists():
            try:
                full_data = json.loads(seg_p.read_text(encoding="utf-8"))
            except Exception:
                full_data = {}

        # Index existing segments on disk to accurately detect text changes
        existing_disk_by_id = {}
        if isinstance(full_data, dict) and "segments" in full_data and isinstance(full_data["segments"], list):
            for old_s in full_data["segments"]:
                if isinstance(old_s, dict) and "id" in old_s:
                    existing_disk_by_id[old_s["id"]] = old_s

        tts_dir = ws / "tts"
        disk_segments = []
        for s in segments:
            item = dict(s)
            seg_id = item.get("id")
            old_on_disk = existing_disk_by_id.get(seg_id, {})

            # Primary text synchronization:
            # 'text' is the primary editing field in UI. If 'text' is supplied, use it; else fallback.
            raw_text = item.get("text")
            if raw_text is None:
                raw_text = item.get("vi_text", "")
            new_text = str(raw_text).strip()

            old_text_on_disk = str(old_on_disk.get("text") or old_on_disk.get("vi_text") or old_on_disk.get("tts_text") or "").strip()

            # Detect if text, voice, or speed actually changed from disk
            text_changed = bool(old_text_on_disk and new_text != old_text_on_disk)
            old_voice_on_disk = str(old_on_disk.get("voice") or "").strip()
            new_voice = str(item.get("voice") or "").strip()
            voice_changed = bool(old_voice_on_disk and new_voice and new_voice != old_voice_on_disk)

            old_speed = float(old_on_disk.get("speed") or 1.0)
            new_speed = float(item.get("speed") or 1.0)
            speed_changed = abs(old_speed - new_speed) > 0.01

            content_changed = text_changed or voice_changed or speed_changed

            from dubstudio.text.vi_normalize import normalize_for_tts
            item["text"] = new_text
            item["vi_text"] = new_text
            item["tts_text"] = normalize_for_tts(new_text.replace("\n", " "))
            if new_voice:
                item["voice"] = new_voice

            # Synchronize mute flags across mute_sub/muted_sub and mute_tts/muted_tts
            if "mute_sub" in item or "muted_sub" in item:
                m_sub = bool(item.get("mute_sub", item.get("muted_sub", False)))
                item["mute_sub"] = m_sub
                item["muted_sub"] = m_sub
            if "mute_tts" in item or "muted_tts" in item:
                m_tts = bool(item.get("mute_tts", item.get("muted_tts", False)))
                item["mute_tts"] = m_tts
                item["muted_tts"] = m_tts

            # Invalidate TTS artifacts ONLY if content (text, voice, speed) was genuinely modified!
            old_st = float(old_on_disk.get("start", item.get("start", 0.0)))
            old_en = float(old_on_disk.get("end", item.get("end", old_st + 1.0)))
            st_val = float(item.get("start", old_st))
            en_val = float(item.get("end", old_en))
            time_changed = abs(st_val - old_st) > 0.01 or abs(en_val - old_en) > 0.01

            # Tự động cân chỉnh lại thời gian hiển thị giữa các phần tách nhỏ (cues/sub_slices) khi đổi thời lượng câu
            if time_changed or text_changed:
                existing_cues = item.get("cues") or old_on_disk.get("cues")
                lines = [l.strip() for l in new_text.split("\n") if l.strip()]
                if not text_changed and time_changed and existing_cues and isinstance(existing_cues, list) and len(existing_cues) == len(lines) and len(lines) > 1:
                    old_dur = max(0.05, old_en - old_st)
                    new_dur = max(0.05, en_val - st_val)
                    scaled_cues = []
                    for sc in existing_cues:
                        sc_st = float(sc.get("start", old_st))
                        sc_en = float(sc.get("end", old_en))
                        rel_st = max(0.0, min(1.0, (sc_st - old_st) / old_dur))
                        rel_en = max(0.0, min(1.0, (sc_en - old_st) / old_dur))
                        scaled_cues.append({
                            "text": sc.get("text", ""),
                            "start": round(st_val + rel_st * new_dur, 3),
                            "end": round(st_val + rel_en * new_dur, 3),
                        })
                    item["cues"] = scaled_cues
                    item["sub_slices"] = list(scaled_cues)
                elif text_changed or (len(lines) > 1 and not existing_cues):
                    try:
                        from dubstudio.subtitles.cue_split import split_sentence_cues
                        fresh_cues = split_sentence_cues(new_text, st_val, en_val)
                        if fresh_cues:
                            item["cues"] = fresh_cues
                            item["sub_slices"] = [{"text": c["text"], "start": c["start"], "end": c["end"]} for c in fresh_cues]
                    except Exception:
                        pass

            if content_changed:
                item["tts_hash"] = None
                item.pop("tts_file", None)
                item.pop("tts_dur", None)
                item["has_tts"] = False
                if seg_id is not None and tts_dir.exists():
                    try:
                        old_wav = tts_dir / f"{int(seg_id):04d}.wav"
                        if old_wav.exists():
                            old_wav.unlink(missing_ok=True)
                    except Exception:
                        pass
            else:
                # Content did NOT change: preserve existing TTS artifacts from disk / old_on_disk!
                if not item.get("tts_hash") and old_on_disk.get("tts_hash"):
                    item["tts_hash"] = old_on_disk.get("tts_hash")
                if not item.get("tts_file") and old_on_disk.get("tts_file"):
                    item["tts_file"] = old_on_disk.get("tts_file")
                if not item.get("tts_dur") and old_on_disk.get("tts_dur"):
                    item["tts_dur"] = old_on_disk.get("tts_dur")
                if "has_tts" not in item and old_on_disk.get("has_tts") is not None:
                    item["has_tts"] = old_on_disk.get("has_tts")
                if "voice_dur" not in item and old_on_disk.get("voice_dur"):
                    item["voice_dur"] = old_on_disk.get("voice_dur")
                if "voice_start" not in item and old_on_disk.get("voice_start"):
                    item["voice_start"] = old_on_disk.get("voice_start")
                if "fit" not in item and old_on_disk.get("fit"):
                    item["fit"] = old_on_disk.get("fit")
                if "fit_rate" not in item and old_on_disk.get("fit_rate"):
                    item["fit_rate"] = old_on_disk.get("fit_rate")

                # If the WAV exists on disk, guarantee has_tts and tts_file are set!
                if seg_id is not None and tts_dir.exists():
                    wav_p = tts_dir / f"{int(seg_id):04d}.wav"
                    if wav_p.exists() and wav_p.stat().st_size > 500:
                        item["has_tts"] = True
                        item["tts_file"] = f"tts/{int(seg_id):04d}.wav"
                        if not item.get("tts_dur") and old_on_disk.get("tts_dur"):
                            item["tts_dur"] = old_on_disk.get("tts_dur")

            if "orig" in item and "zh" not in item:
                item["zh"] = item["orig"]
            if "zh" in item and "orig" not in item:
                item["orig"] = item["zh"]
            disk_segments.append(item)

        # Safety safeguard: Do NOT wipe out valid segments on disk with an empty array
        # caused by initial component mount or state race condition!
        if not disk_segments and len(existing_disk_by_id) > 0:
            return {"status": "ignored", "message": "Prevented accidental wipe of existing segments with empty list"}

        # Automatic safety backup
        if seg_p.exists() and seg_p.stat().st_size > 50:
            try:
                shutil.copy2(seg_p, ws / "segments.json.bak")
            except Exception:
                pass

        if isinstance(full_data, dict) and "segments" in full_data:
            full_data["segments"] = disk_segments
            atomic_write_json(seg_p, full_data)
        else:
            atomic_write_json(seg_p, {"segments": disk_segments})

        units_file = ws / "units.json"
        if units_file.exists():
            try:
                units_file.write_text(json.dumps(disk_segments, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        # Clean up TTS wav and fit_plan for any deleted segments
        current_ids = {s.get("id") for s in disk_segments if s.get("id") is not None}
        tts_dir = ws / "tts"
        if tts_dir.exists():
            for w in tts_dir.glob("*.wav"):
                try:
                    wid = int(w.stem)
                    if wid not in current_ids:
                        w.unlink(missing_ok=True)
                except Exception:
                    pass

        fit_plan_file = ws / "fit_plan.json"
        if fit_plan_file.exists():
            try:
                fp = json.loads(fit_plan_file.read_text(encoding="utf-8"))
                if isinstance(fp, list):
                    updated_fp = [item for item in fp if item.get("id") in current_ids]
                    atomic_write_json(fit_plan_file, updated_fp)
            except Exception:
                pass

        # Rebuild voice track immediately so deleted cues stop playing
        if (ws / "voice_track.wav").exists():
            from dubstudio.api.app import _quick_rebuild_voice_track
            try:
                _quick_rebuild_voice_track(job_id)
            except Exception:
                pass

        return {"status": "success"}

    def save_project_style(self, job_id: str, style_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save audio mixer volumes and subtitle typography style settings."""
        from dubstudio.paths import resolve_job_workspace
        from dubstudio.jobstate import atomic_write_json
        ws = resolve_job_workspace(job_id)
        if not ws.exists():
            return {"status": "error", "message": "Project not found"}

        # 1. Subtitle style persistence (style.json)
        style_p = ws / "style.json"
        current_style = {}
        if style_p.exists():
            try:
                current_style = json.loads(style_p.read_text(encoding="utf-8"))
            except Exception:
                pass
        current_style.update(style_data)
        atomic_write_json(style_p, current_style)

        # 2. Audio mix persistence (mix_settings.json)
        mix_p = ws / "mix_settings.json"
        current_mix = {}
        if mix_p.exists():
            try:
                current_mix = json.loads(mix_p.read_text(encoding="utf-8"))
            except Exception:
                pass
        for k in ("voice_volume", "vi_voice_volume", "bgm_volume", "orig_bgm_volume", "orig_voice_volume", "include_orig_voice", "keep_original_ranges"):
            if k in style_data:
                current_mix[k] = style_data[k]
        if current_mix:
            atomic_write_json(mix_p, current_mix)

        return {"status": "success", "style": current_style}

    def save_project_config(self, job_id: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save project configuration options (voices, tone, gender mode, words per line)."""
        from dubstudio.paths import resolve_job_workspace
        from dubstudio.tts.base import clean_voice_name
        ws = resolve_job_workspace(job_id)
        if not ws.exists():
            return {"status": "error", "message": "Project not found"}
        cfg_file = ws / "job_config.json"
        cfg_data = {}
        if cfg_file.exists():
            try:
                cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        if "words_per_line" in config_data:
            cfg_data["words_per_line"] = int(config_data["words_per_line"])
        if "translation_tone" in config_data:
            cfg_data["translation_tone"] = config_data["translation_tone"]
            cfg_data["style"] = config_data["translation_tone"]
        if "detect_gender" in config_data:
            cfg_data["detect_gender"] = bool(config_data["detect_gender"])
        if "single_voice_gender" in config_data:
            cfg_data["single_voice_gender"] = config_data["single_voice_gender"]
        if "single_voice" in config_data and config_data["single_voice"]:
            cfg_data["single_voice"] = clean_voice_name(config_data["single_voice"], "Minh Đức")
        if "voice_male" in config_data and config_data["voice_male"]:
            clean_m = clean_voice_name(config_data["voice_male"], "Minh Đức")
            cfg_data["default_male_voice"] = clean_m
            cfg_data["voice_male"] = clean_m
        if "voice_female" in config_data and config_data["voice_female"]:
            clean_f = clean_voice_name(config_data["voice_female"], "Quỳnh Anh")
            cfg_data["default_female_voice"] = clean_f
            cfg_data["voice_female"] = clean_f
        cfg_file.write_text(json.dumps(cfg_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "success"}

    def synthesize_single_segment(self, job_id: str, seg_id: int, text: Optional[str] = None, speed: Optional[float] = None, voice: Optional[str] = None) -> Dict[str, Any]:
        """Synthesize a single segment TTS with selected voice and tempo."""
        from dubstudio.paths import resolve_job_workspace
        from dubstudio.jobstate import atomic_write_json
        from dubstudio.config import AppConfig
        import subprocess
        import soundfile as sf
        from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs

        ws = resolve_job_workspace(job_id)
        if not ws.exists():
            return {"status": "error", "message": "Project not found"}
        seg_file = ws / "segments.json"
        if not seg_file.exists():
            return {"status": "error", "message": "Segments not found"}
        
        try:
            data = json.loads(seg_file.read_text(encoding="utf-8"))
        except Exception as e:
            return {"status": "error", "message": f"Read segments failed: {e}"}

        target_seg = None
        for s in data.get("segments", []):
            if s.get("id") == seg_id:
                target_seg = s
                break
        if not target_seg:
            return {"status": "error", "message": f"Segment {seg_id} not found"}

        from dubstudio.text.vi_normalize import normalize_for_tts
        if text is not None:
            clean_txt = text.strip()
            target_seg["vi_text"] = clean_txt
            target_seg["text"] = clean_txt
            target_seg["tts_text"] = normalize_for_tts(clean_txt.replace("\n", " "))
            try:
                from dubstudio.subtitles.cue_split import split_sentence_cues
                st_val = float(target_seg.get("start", 0.0))
                en_val = float(target_seg.get("end", st_val + 1.0))
                fresh_cues = split_sentence_cues(clean_txt, st_val, en_val)
                if fresh_cues:
                    target_seg["cues"] = fresh_cues
                    target_seg["sub_slices"] = [{"text": c["text"], "start": c["start"], "end": c["end"]} for c in fresh_cues]
            except Exception:
                pass

        raw_tts = (target_seg.get("tts_text") or target_seg.get("vi_text") or target_seg.get("text") or "").strip()
        tts_text = normalize_for_tts(raw_tts.replace("\n", " "))
        target_seg["tts_text"] = tts_text
        if not tts_text:
            return {"status": "error", "message": "Không có nội dung thoại"}

        cfg = AppConfig.load()
        voice_choice = voice or target_seg.get("voice") or (
            cfg.tts.default_male_voice if target_seg.get("gender") == "male" else cfg.tts.default_female_voice
        )
        speed_rate = float(speed or target_seg.get("speed") or 1.0)
        target_seg["voice"] = voice_choice
        target_seg["speed"] = speed_rate
        if voice:
            target_seg["user_edited_voice"] = True

        tts_dir = ws / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)
        wav_path = tts_dir / f"{seg_id:04d}.wav"

        cmd = [
            str(get_runtime_python().resolve()), "-m", "dubstudio.tts.single_tts",
            "--text", tts_text,
            "--voice", voice_choice,
            "--speed", str(speed_rate),
            "--out", str(wav_path.resolve()),
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=get_subprocess_env(),
            **get_subprocess_kwargs(),
        )
        if res.returncode != 0:
            return {"status": "error", "message": f"TTS synthesis failed: {res.stderr.strip() or res.stdout.strip()}"}

        dur = 0.0
        if wav_path.exists():
            try:
                info = sf.info(str(wav_path))
                dur = round(info.duration, 3)
                target_seg["tts_dur"] = dur
                target_seg["voice_dur"] = dur
                target_seg["tts_file"] = f"tts/{seg_id:04d}.wav"
                target_seg["has_tts"] = True
                import hashlib
                target_seg["tts_hash"] = hashlib.md5(f"{tts_text}|{voice_choice}|{speed_rate:.2f}".encode("utf-8")).hexdigest()[:12]
            except Exception:
                pass

        atomic_write_json(seg_file, data)

        # Quick rebuild of voice track so preview reflects updated audio
        try:
            from dubstudio.api.app import _quick_rebuild_voice_track
            _quick_rebuild_voice_track(job_id)
        except Exception:
            pass

        return {
            "status": "success",
            "seg_id": seg_id,
            "tts_dur": dur,
            "voice": voice_choice,
            "speed": speed_rate,
            "audio_url": f"/media/workspace/{job_id}/tts/{seg_id:04d}.wav?t={int(time.time())}",
        }

    # --- 3. App Settings, AI Engines & Component Manager ---

    def is_first_run(self) -> bool:
        """Check if the user is running DubStudio for the first time."""
        from dubstudio.packaging import is_first_run
        return is_first_run()

    def mark_first_run_done(self, done: bool = True) -> Dict[str, Any]:
        """Mark first-run tutorial wizard as completed or reset."""
        from dubstudio.packaging import mark_first_run_done
        mark_first_run_done(done)
        return {"status": "success"}

    def get_app_settings(self) -> Dict[str, Any]:
        """Retrieve real application settings, translation method, default voices."""
        from dubstudio.config import AppConfig
        from dubstudio.paths import get_out_dir
        from dubstudio.tts.base import clean_voice_name, MALE_VOICES, FEMALE_VOICES

        cfg = AppConfig.load()
        s_file = Path("config") / "app_settings.json"
        s_data = {}
        if s_file.exists():
            try:
                s_data = json.loads(s_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        trans_provider = s_data.get("translation_provider") or os.getenv("TRANSLATION_PROVIDER") or getattr(getattr(cfg, "translation", None), "provider", "gemini_web") or "gemini_web"
        def_male = clean_voice_name(s_data.get("default_male_voice") or os.getenv("DEFAULT_MALE_VOICE") or getattr(getattr(cfg, "tts", None), "default_male_voice", "Minh Đức"), "Minh Đức")
        def_female = clean_voice_name(s_data.get("default_female_voice") or os.getenv("DEFAULT_FEMALE_VOICE") or getattr(getattr(cfg, "tts", None), "default_female_voice", "Quỳnh Anh"), "Quỳnh Anh")
        whisper_m = s_data.get("whisper_model") or os.getenv("WHISPER_MODEL") or getattr(getattr(cfg, "asr", None), "model_size", "sensevoice-small") or "sensevoice-small"
        sep_m = s_data.get("separation_model") or os.getenv("SEPARATION_MODEL") or getattr(getattr(cfg, "separation", None), "model_name", "Kim_Vocal_2.onnx") or "Kim_Vocal_2.onnx"
        tone = s_data.get("translation_tone") or getattr(getattr(cfg, "translation", None), "style", "Tự nhiên, đời thường") or "Tự nhiên, đời thường"

        male_list = sorted(list(MALE_VOICES))
        female_list = sorted(list(FEMALE_VOICES))

        return {
            "translation_provider": trans_provider,
            "translation_model": "Gemini 2.5 Flash / Web",
            "translation_tone": tone,
            "default_male_voice": def_male,
            "default_female_voice": def_female,
            "whisper_model": whisper_m,
            "separation_model": sep_m,
            "out_dir": str(get_out_dir().resolve()),
            "male_voices": male_list,
            "female_voices": female_list,
            "available_voices": male_list + female_list,
            "all_voices": male_list + female_list,
        }

    def save_app_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Save updated application configuration to .env and system config."""
        try:
            from dubstudio.paths import get_env_file, set_custom_out_dir
            from dubstudio.tts.base import clean_voice_name

            if "translation_provider" in settings:
                os.environ["TRANSLATION_PROVIDER"] = str(settings["translation_provider"])
            if "default_male_voice" in settings:
                clean_m = clean_voice_name(settings["default_male_voice"], "Minh Đức")
                os.environ["DEFAULT_MALE_VOICE"] = clean_m
                settings["default_male_voice"] = clean_m
            if "default_female_voice" in settings:
                clean_f = clean_voice_name(settings["default_female_voice"], "Quỳnh Anh")
                os.environ["DEFAULT_FEMALE_VOICE"] = clean_f
                settings["default_female_voice"] = clean_f
            if "whisper_model" in settings:
                os.environ["WHISPER_MODEL"] = str(settings["whisper_model"])
            if "separation_model" in settings:
                os.environ["SEPARATION_MODEL"] = str(settings["separation_model"])
            if "out_dir" in settings and settings["out_dir"]:
                try:
                    set_custom_out_dir(Path(settings["out_dir"]))
                except Exception:
                    pass
                os.environ["DUBSTUDIO_OUT_DIR"] = str(settings["out_dir"])

            # Persist to config/app_settings.json
            try:
                s_file = Path("config") / "app_settings.json"
                s_file.parent.mkdir(parents=True, exist_ok=True)
                current_s = {}
                if s_file.exists():
                    try:
                        current_s = json.loads(s_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                current_s.update(settings)
                s_file.write_text(json.dumps(current_s, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

            # Persist to .env
            env_p = get_env_file()
            try:
                lines = env_p.read_text(encoding="utf-8").splitlines() if env_p.exists() else []
                new_lines = []
                keys_seen = set()
                keys_to_write = {
                    "TRANSLATION_PROVIDER": settings.get("translation_provider"),
                    "DEFAULT_MALE_VOICE": settings.get("default_male_voice"),
                    "DEFAULT_FEMALE_VOICE": settings.get("default_female_voice"),
                    "WHISPER_MODEL": settings.get("whisper_model"),
                    "SEPARATION_MODEL": settings.get("separation_model"),
                    "DUBSTUDIO_OUT_DIR": settings.get("out_dir"),
                }
                for line in lines:
                    matched_key = None
                    for k in keys_to_write:
                        if line.startswith(f"{k}="):
                            matched_key = k
                            break
                    if matched_key:
                        val = keys_to_write[matched_key]
                        if val is not None:
                            new_lines.append(f"{matched_key}={val}")
                            keys_seen.add(matched_key)
                    else:
                        new_lines.append(line)

                for k, val in keys_to_write.items():
                    if val is not None and k not in keys_seen:
                        new_lines.append(f"{k}={val}")

                env_p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            except Exception:
                pass

            return {"status": "success", "message": "Đã lưu cài đặt thành công!"}
        except Exception as e:
            return {"status": "success", "message": f"Cài đặt đã lưu (ghi chú: {str(e)})"}

    def launch_gemini_browser(self) -> Dict[str, Any]:
        """Launch dedicated Chromium/Edge browser to Gemini Web via remote debugging CDP."""
        try:
            from dubstudio.llm.cdp_gemini import launch_browser_cdp, bring_gemini_to_front, is_cdp_ready
            if is_cdp_ready(9222):
                bring_gemini_to_front(9222)
            else:
                launch_browser_cdp(port=9222, allow_restart=True, hidden=False)
            return {"status": "success", "message": "Đã mở trình duyệt Gemini Web"}
        except Exception as e:
            return {"status": "error", "message": f"Không thể mở trình duyệt: {str(e)}"}

    def check_gemini_browser_status(self) -> Dict[str, Any]:
        """Check if Gemini Web CDP session is alive and ready."""
        try:
            from dubstudio.llm.cdp_gemini import check_gemini_status
            ready, msg = check_gemini_status(port=9222)
            return {"ready": ready, "message": msg}
        except Exception as e:
            return {"ready": False, "message": str(e)}

    def get_gpu_info(self) -> Dict[str, Any]:
        """Query GPU hardware info (NVIDIA / Intel / AMD / CPU) and driver status."""
        try:
            from dubstudio.gpu_check import inspect_gpu_and_driver, GPUStatus
            res = inspect_gpu_and_driver()
            status = res.get("status")
            return {
                "status": "success",
                "gpu_status": status,
                "card_name": res.get("card_name") or "Không có card NVIDIA rời",
                "driver_version": res.get("driver_version") or "N/A",
                "min_driver_required": res.get("min_driver_required") or "528.33",
                "vram_gb": round(float(res.get("vram_gb", 0)), 1),
                "is_cuda_ready": status == GPUStatus.OK_CUDA,
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "card_name": "CPU Mode", "is_cuda_ready": False}

    def export_diagnostic_bundle(self) -> Dict[str, Any]:
        """Export comprehensive diagnostic logs zip file."""
        try:
            from dubstudio.diagnostics import export_diagnostic_bundle
            from dubstudio.paths import get_out_dir
            target_zip = get_out_dir() / f"DubStudio_Diagnostics_{int(time.time())}.zip"
            zip_path = export_diagnostic_bundle(target_zip)
            return {
                "status": "success",
                "path": str(zip_path.resolve()),
                "message": f"Đã xuất tệp chẩn đoán lỗi tại:\n{zip_path.resolve()}"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_app_version(self) -> str:
        """Return the current DubStudio version string."""
        from dubstudio.version import APP_VERSION
        return APP_VERSION

    def check_for_updates(self) -> Dict[str, Any]:
        """Check GitHub for newer releases using Velopack/Release manifest."""
        try:
            from dubstudio.updater import check_all_updates
            from dubstudio.version import APP_VERSION
            res = check_all_updates(timeout=4.0)
            return {
                "has_update": bool(res.get("has_app_update")),
                "current_version": res.get("current_version", APP_VERSION),
                "latest_version": res.get("latest_version", APP_VERSION),
                "release_notes": res.get("release_notes", ""),
                "download_url": res.get("download_url", ""),
                "setup_asset_url": res.get("setup_asset_url", ""),
            }
        except Exception as e:
            return {"has_update": False, "error": str(e)}

    def get_components_status(self) -> List[Dict[str, Any]]:
        """Check installed AI components."""
        try:
            from dubstudio.components import fetch_components_manifest, is_component_ready
            manifest = fetch_components_manifest()
            pkgs = manifest.get("packages", [])
            res = []
            for p in pkgs:
                ready, details = is_component_ready(p["id"])
                res.append({
                    "id": p["id"],
                    "name": p.get("name", p["id"]),
                    "category": p.get("category", "other"),
                    "size_mb": round(p.get("size_bytes", 0) / (1024 * 1024), 1),
                    "ready": ready,
                    "status_text": details,
                    "description": p.get("changelog_vi", ""),
                })
            return res
        except Exception:
            return []

    def download_component(self, pkg_id: str) -> Dict[str, Any]:
        """Download and install a component in background thread with live UI events."""
        from dubstudio.components import fetch_components_manifest, download_component_file
        manifest = fetch_components_manifest()
        target_pkg = None
        for p in manifest.get("packages", []):
            if p["id"] == pkg_id:
                target_pkg = p
                break
        if not target_pkg:
            return {"status": "error", "message": f"Không tìm thấy gói '{pkg_id}'"}

        def worker():
            try:
                def on_progress(pct, cur_b, tot_b):
                    self.emit_event_to_ui({
                        "type": "component_download_progress",
                        "pkg_id": pkg_id,
                        "percent": pct,
                        "downloaded_mb": round(cur_b / (1024 * 1024), 1),
                        "total_mb": round(tot_b / (1024 * 1024), 1),
                        "status": "downloading"
                    })

                ok = download_component_file(target_pkg, progress_cb=on_progress)
                if ok:
                    self.emit_event_to_ui({
                        "type": "component_download_done",
                        "pkg_id": pkg_id,
                        "status": "success",
                        "message": f"Đã tải và cài đặt thành công {target_pkg.get('name', pkg_id)}"
                    })
                else:
                    self.emit_event_to_ui({
                        "type": "component_download_done",
                        "pkg_id": pkg_id,
                        "status": "error",
                        "message": "Quá trình tải thất bại hoặc bị hủy"
                    })
            except Exception as e:
                self.emit_event_to_ui({
                    "type": "component_download_done",
                    "pkg_id": pkg_id,
                    "status": "error",
                    "message": str(e)
                })

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return {"status": "success", "message": f"Bắt đầu tải {target_pkg.get('name', pkg_id)}"}

    def export_project_video(self, job_id: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute full video rendering and export in background thread."""
        from dubstudio.events import add_event_listener, remove_event_listener

        def worker():
            from dubstudio.jobstate import JobContext, atomic_write_json
            from dubstudio.config import AppConfig
            from dubstudio.paths import resolve_job_workspace, get_out_dir
            import shutil

            def on_event(ev):
                self.emit_event_to_ui({
                    "stage": "render",
                    "progress": getattr(ev, "progress", 0.0),
                    "message": getattr(ev, "message", "Đang xuất video..."),
                    "level": getattr(ev, "level", "info"),
                    "job_id": job_id,
                })

            add_event_listener(on_event)
            try:
                ws = resolve_job_workspace(job_id)
                job = JobContext(workspace_path=ws, job_id=job_id)
                cfg = AppConfig.load()

                opts = options or {}
                if not (ws / "segments.json").exists():
                    (ws / "segments.json").write_text(json.dumps({"segments": []}, ensure_ascii=False, indent=2), encoding="utf-8")

                # 1. Update export options in style.json & mix_settings.json
                style_file = ws / "style.json"
                cur_style = {}
                if style_file.exists():
                    try:
                        cur_style = json.loads(style_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                
                if "subtitle_style" in opts and isinstance(opts["subtitle_style"], dict):
                    cur_style.update(opts["subtitle_style"])
                if "aspect_ratio" in opts:
                    cur_style["aspect_ratio"] = opts["aspect_ratio"]
                if "canvas_color" in opts:
                    cur_style["canvas_color"] = opts["canvas_color"]
                if "burn_subtitles" in opts:
                    cur_style["burn_subtitles"] = bool(opts["burn_subtitles"])
                if "logo" in opts and opts["logo"]:
                    cur_style["logo"] = opts["logo"]
                if "color_boxes" in opts:
                    cur_style["color_boxes"] = opts["color_boxes"]
                if "color_box" in opts:
                    cur_style["color_box"] = opts["color_box"]
                atomic_write_json(style_file, cur_style)

                # Mix settings (voice and bgm levels 0 - 200%)
                mix_file = ws / "mix_settings.json"
                cur_mix = {}
                if mix_file.exists():
                    try:
                        cur_mix = json.loads(mix_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                
                v_vol = float(opts.get("voice_volume", 100)) / 100.0
                b_vol = float(opts.get("bgm_volume", 100)) / 100.0
                cur_mix["vi_voice_volume"] = v_vol
                cur_mix["bgm_volume"] = b_vol
                cur_mix["orig_bgm_volume"] = b_vol
                if "orig_voice_volume" in opts:
                    raw_ov = float(opts.get("orig_voice_volume", 0))
                    ov_vol = (raw_ov / 100.0) if raw_ov > 1.0 else raw_ov
                    ov_vol = max(0.0, min(1.0, ov_vol))
                    cur_mix["orig_voice_volume"] = ov_vol
                    cur_mix["include_orig_voice"] = bool(ov_vol > 0.005)
                if "custom_bgm_path" in opts:
                    cur_mix["custom_bgm_path"] = opts["custom_bgm_path"]
                    cur_mix["custom_bgm_volume"] = float(opts.get("custom_bgm_volume", 50)) / 100.0
                atomic_write_json(mix_file, cur_mix)

                # 2. Re-mix audio if requested volume or voice track exists or keep_orig ranges exist
                should_remix = (
                    (ws / "audio" / "bgm.wav").exists()
                    or (ws / "voice_raw.wav").exists()
                    or (ws / "voice_track.wav").exists()
                    or (ws / "fit_plan.json").exists()
                    or bool(opts.get("custom_bgm_path"))
                    or bool(cur_mix.get("keep_original_ranges"))
                )
                if should_remix:
                    from dubstudio.stages import mix
                    try:
                        mix.run(job, cfg, force=True)
                    except Exception as e:
                        print(f"Mix warning during export: {e}")

                # 3. Render video with hardsub & aspect ratio
                from dubstudio.stages import render
                in_vid = ws / "input.mp4"
                render.run(job, cfg, input_video=in_vid, force=True)

                # 4. Target export directory and filename
                t_title = opts.get("title", "").strip()
                if not t_title:
                    job_cfg_file = ws / "job_config.json"
                    if job_cfg_file.exists():
                        try:
                            c_data = json.loads(job_cfg_file.read_text(encoding="utf-8"))
                            t_title = c_data.get("title", "")
                        except Exception:
                            pass
                out_name = f"{t_title or job_id}.mp4"
                if not out_name.endswith(".mp4"):
                    out_name += ".mp4"

                target_directory = get_out_dir()
                if opts.get("target_dir") and Path(opts["target_dir"]).exists():
                    target_directory = Path(opts["target_dir"])

                final_target = target_directory / out_name
                ws_out = ws / "out" / "final.mp4"
                if ws_out.exists():
                    shutil.copy2(ws_out, final_target)

                # Clean up duplicate raw job-id files in output directory if a custom title was used
                if final_target.name != f"{job_id}_vi.mp4":
                    for raw_f in [
                        target_directory / f"{job_id}_vi.mp4",
                        target_directory / f"{job_id}_vi.ass",
                        target_directory / f"{job_id}_vi.srt",
                        get_out_dir() / f"{job_id}_vi.mp4",
                        get_out_dir() / f"{job_id}_vi.ass",
                        get_out_dir() / f"{job_id}_vi.srt",
                    ]:
                        if raw_f.exists() and raw_f != final_target:
                            try:
                                raw_f.unlink()
                            except Exception:
                                pass

                self.emit_event_to_ui({
                    "stage": "render",
                    "progress": 100.0,
                    "message": f"Xuất video thành công: {final_target.name}",
                    "level": "success",
                    "job_id": job_id,
                    "out_path": str(final_target.resolve()),
                })
            except Exception as e:
                self.emit_event_to_ui({
                    "stage": "render",
                    "progress": 0.0,
                    "message": f"Lỗi xuất video: {str(e)}",
                    "level": "error",
                    "job_id": job_id,
                })
            finally:
                remove_event_listener(on_event)

        th = threading.Thread(target=worker, daemon=True)
        th.start()
        return {"status": "started", "job_id": job_id}

    def submit_manual_translation(self, job_id: str, text: str, cancelled: bool = False) -> Dict[str, Any]:
        """Deliver user's manual translated text into workspace for translate.py to resume."""
        from dubstudio.paths import resolve_job_workspace
        ws = resolve_job_workspace(job_id)
        if not ws.exists():
            return {"status": "error", "message": "Job not found"}
        resp_file = ws / "manual_translate_response.json"
        data = {
            "text": text.strip(),
            "cancelled": bool(cancelled),
            "timestamp": time.time(),
        }
        resp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "success"}

    def get_manual_translate_prompt(self, job_id: str) -> Dict[str, Any]:
        """Retrieve current manual translation prompt text if present."""
        from dubstudio.paths import resolve_job_workspace
        ws = resolve_job_workspace(job_id)
        prompt_file = ws / "manual_translate_prompt.txt"
        if prompt_file.exists():
            return {
                "status": "success",
                "prompt": prompt_file.read_text(encoding="utf-8"),
            }
        return {"status": "error", "message": "Prompt not found"}

    # --- 4. Isolated Pipeline Execution & Real-Time Event Dispatch ---

    def emit_event_to_ui(self, event_data: Dict[str, Any]):
        """Push real-time progress events directly to React via CustomEvent."""
        if not self._window:
            return
        try:
            payload_json = json.dumps(event_data, ensure_ascii=False)
            self._window.evaluate_js(
                f"window.dispatchEvent(new CustomEvent('dubstudio-event', {{ detail: {payload_json} }}));"
            )
        except Exception:
            pass

    def run_pipeline_stage(self, job_id: str, stage_name: str) -> Dict[str, Any]:
        """Run heavy processing stages in an isolated background thread."""
        from dubstudio.events import add_event_listener, remove_event_listener

        def worker():
            from dubstudio.jobstate import JobContext
            from dubstudio.config import AppConfig
            from dubstudio.paths import resolve_job_workspace

            def on_event(ev):
                self.emit_event_to_ui({
                    "stage": getattr(ev, "stage", stage_name),
                    "progress": getattr(ev, "progress", 0.0),
                    "message": getattr(ev, "message", ""),
                    "level": getattr(ev, "level", "info"),
                    "job_id": job_id,
                })

            add_event_listener(on_event)
            try:
                ws = resolve_job_workspace(job_id)
                job = JobContext(workspace_path=ws, job_id=job_id)
                cfg = AppConfig.load()

                if stage_name == "asr":
                    from dubstudio.stages import asr
                    asr.run(job, cfg)
                elif stage_name == "translate":
                    from dubstudio.stages import translate
                    translate.run(job, cfg)
                elif stage_name == "tts":
                    from dubstudio.stages import tts
                    tts.run(job, cfg)
                elif stage_name == "mix":
                    from dubstudio.stages import mix
                    mix.run(job, cfg)
                elif stage_name == "render":
                    from dubstudio.stages import render
                    render.run(job, cfg)
            except Exception as e:
                self.emit_event_to_ui({
                    "stage": stage_name,
                    "progress": 0.0,
                    "message": f"Lỗi thực thi: {str(e)}",
                    "level": "error",
                    "job_id": job_id,
                })
            finally:
                remove_event_listener(on_event)

        th = threading.Thread(target=worker, daemon=True)
        th.start()
        return {"status": "started", "stage": stage_name, "job_id": job_id}


def run_fastapi_server(port: int):
    """Run uvicorn media & static server on dynamically allocated port."""
    import sys
    if sys.platform == "win32":
        import asyncio
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    import uvicorn
    from dubstudio.api.app import app
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def wait_for_server_ready(base_url: str, timeout: float = 15.0) -> bool:
    """Active Health + Asset Readiness Probe: wait until FastAPI responds 200 OK
    with inlined core CSS in index.html before launching pywebview."""
    import urllib.request
    start = time.time()
    probe_url = base_url.rstrip("/") + "/"
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(
                probe_url,
                headers={
                    "Cache-Control": "no-cache, no-store",
                    "User-Agent": "DubStudio-Startup-Probe/2.0",
                },
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    # Ensure full index.html with inlined CSS is ready
                    if len(body) > 1000 and ('id="dubstudio-core-css"' in body or "<html" in body.lower()):
                        return True
        except Exception:
            pass
        time.sleep(0.08)
    return False


def main():
    # 1. Acquire dynamic free port from Windows OS (Zero Hardcoded Port)
    dynamic_port = find_free_port()
    local_url = f"http://127.0.0.1:{dynamic_port}/"
    print(f"[DubStudio 2.0] Dynamic Ephemeral Port allocated: {dynamic_port}")

    # 2. Start lightweight FastAPI media & static server in daemon thread
    server_thread = threading.Thread(
        target=run_fastapi_server,
        args=(dynamic_port,),
        daemon=True,
    )
    server_thread.start()

    # 3. Wait for local server and full CSS-inlined index.html readiness
    if not wait_for_server_ready(local_url, timeout=15.0):
        print(f"[DubStudio 2.0] Warning: Server readiness probe timed out after 15s. Launching window anyway.")

    # 4. Initialize PyWebView Desktop window with Direct In-Memory Bridge
    import webview

    # Enable native drag regions on Windows
    webview.settings['DRAG_REGION_SELECTOR'] = '.pywebview-drag-region, .app-drag'
    webview.settings['DRAG_REGION_DIRECT_TARGET_ONLY'] = False

    bridge = DesktopAPIBridge()
    bridge.set_port(dynamic_port)

    window = webview.create_window(
        title="DubStudio 2.0",
        url=local_url,
        js_api=bridge,
        width=1280,
        height=800,
        min_size=(1024, 680),
        frameless=True,
        easy_drag=False,
        background_color="#121214",
    )
    bridge.set_window(window)

    def on_loaded():
        # Enforce studio look: disable context menu and inject port metadata
        try:
            window.evaluate_js(
                f"""
                window.__DUBSTUDIO_PORT__ = {dynamic_port};
                window.addEventListener('contextmenu', function(e) {{
                    e.preventDefault();
                }}, false);
                """
            )
        except Exception:
            pass

    window.events.loaded += on_loaded

    # Start PyWebView with Microsoft Edge WebView2 engine
    webview.start(
        debug=False,
        http_server=False,
    )

    # Clean exit
    os._exit(0)


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
            mapped_args = ["selftest" if a == "--selftest" else a for a in cli_args]
            sys.argv = [sys.argv[0]] + mapped_args
            app()
        else:
            main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        try:
            if sys.stderr and not getattr(sys.stderr, "closed", True):
                traceback.print_exc(file=sys.stderr)
                sys.stderr.flush()
        except Exception:
            pass
        sys.exit(1)
