"""Background QThread workers for all long-running API operations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from PyQt6.QtCore import QThread, pyqtSignal


import os


_SHARED_SESSION: Optional[requests.Session] = None

def get_shared_session() -> requests.Session:
    """Return shared requests Session with trust_env=False to bypass Windows Registry proxy inspection."""
    global _SHARED_SESSION
    if _SHARED_SESSION is None:
        s = requests.Session()
        s.trust_env = False
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=1)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        _SHARED_SESSION = s
    return _SHARED_SESSION


def get_base_url() -> str:
    """Return local API base URL using active dynamic port."""
    from dubstudio.config import get_api_base_url
    return get_api_base_url()


def _request_with_retry(method: str, path: str, data: Optional[dict] = None, timeout: int = 60) -> Any:
    """Robust HTTP request wrapper with exponential backoff and friendly Windows error handling."""
    url = f"{get_base_url()}{path}"
    session = get_shared_session()
    max_attempts = 10
    last_err = None
    for attempt in range(max_attempts):
        try:
            if method == "GET":
                r = session.get(url, timeout=timeout)
            elif method == "POST":
                r = session.post(url, json=data or {}, timeout=timeout)
            elif method == "PUT":
                r = session.put(url, json=data or {}, timeout=timeout)
            elif method == "DELETE":
                r = session.delete(url, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if r.status_code in (500, 502, 503, 504) and attempt < 3:
                import time
                time.sleep(0.25 * (attempt + 1))
                continue

            if r.status_code >= 400:
                try:
                    err_data = r.json()
                    msg = err_data.get("detail") or err_data.get("message")
                    if msg:
                        raise RuntimeError(msg)
                except Exception as ex:
                    if isinstance(ex, RuntimeError):
                        raise
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout) as ex:
            last_err = ex
            if attempt < max_attempts - 1:
                import time
                time.sleep(0.15 * (attempt + 1))
            else:
                raise RuntimeError(
                    f"Không thể kết nối đến dịch vụ nền DubStudio ({get_base_url()}). "
                    "Hệ thống đang bận hoặc đang khởi động, vui lòng thử lại sau giây lát."
                ) from ex
        except Exception:
            raise
    if last_err:
        raise last_err


def _get(path: str, timeout: int = 15) -> Any:
    return _request_with_retry("GET", path, timeout=timeout)


def _post(path: str, data: Optional[dict] = None, timeout: int = 60) -> Any:
    return _request_with_retry("POST", path, data=data, timeout=timeout)


def _put(path: str, data: Optional[dict] = None, timeout: int = 60) -> Any:
    return _request_with_retry("PUT", path, data=data, timeout=timeout)


def _delete(path: str, timeout: int = 15) -> Any:
    return _request_with_retry("DELETE", path, timeout=timeout)


class CreateJobWorker(QThread):
    """Create a new dubbing job from a video file path and optional custom project name."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, video_path: str, project_name: str = ""):
        super().__init__()
        self.video_path = video_path
        self.project_name = project_name

    def run(self):
        try:
            payload = {"video_path": self.video_path}
            if self.project_name:
                payload["project_name"] = self.project_name
            result = _post("/api/jobs/create", payload)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class RunPipelineWorker(QThread):
    """Run the full pipeline for a job (non-blocking — uses SSE on server side)."""
    progress = pyqtSignal(dict)   # {stage, pct, msg}
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, job_id: str, voice_male: str = "", voice_female: str = "",
                 style: str = "", subtitle_style: Optional[dict] = None,
                 detect_gender: bool = False, single_voice_gender: str = "male",
                 subtitles_only: bool = False, dub_only: bool = False):
        super().__init__()
        self.job_id = job_id
        self.voice_male = voice_male
        self.voice_female = voice_female
        self.style = style
        self.subtitle_style = subtitle_style or {}
        self.detect_gender = detect_gender
        self.single_voice_gender = single_voice_gender
        self.subtitles_only = subtitles_only
        self.dub_only = dub_only

    def run(self):
        try:
            payload: dict = {
                "detect_gender": self.detect_gender,
                "single_voice_gender": self.single_voice_gender,
                "subtitles_only": self.subtitles_only,
                "dub_only": self.dub_only,
            }
            if self.voice_male:
                payload["voice_male"] = self.voice_male
            if self.voice_female:
                payload["voice_female"] = self.voice_female
            if self.style:
                payload["style"] = self.style
            if self.subtitle_style:
                payload["subtitle_style"] = self.subtitle_style

            # Stream SSE events
            url = f"{get_base_url()}/api/jobs/{self.job_id}/run"
            with requests.post(url, json=payload, stream=True, timeout=1800) as resp:
                resp.raise_for_status()
                for raw_line in resp.iter_lines():
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8", errors="replace")
                    if line.startswith("data:"):
                        payload_str = line[5:].strip()
                        if payload_str == "[DONE]":
                            break
                        try:
                            evt = json.loads(payload_str)
                            if evt.get("level") == "error":
                                self.error.emit(evt.get("msg", "Lỗi không xác định"))
                                return
                            self.progress.emit(evt)
                        except json.JSONDecodeError:
                            pass

            # Fetch final result
            result = _get(f"/api/jobs/{self.job_id}")
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LoadJobWorker(QThread):
    """Load job details + segments."""
    finished = pyqtSignal(dict, list)  # job, segments
    error = pyqtSignal(str)

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def run(self):
        try:
            job = _get(f"/api/jobs/{self.job_id}")
            segs_data = _get(f"/api/jobs/{self.job_id}/segments")
            segs = segs_data.get("segments", []) if isinstance(segs_data, dict) else (segs_data if isinstance(segs_data, list) else [])
            self.finished.emit(job, segs)
        except Exception as e:
            self.error.emit(str(e))


class ListJobsWorker(QThread):
    """List all jobs."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            data = _get("/api/jobs")
            jobs = data.get("jobs", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            self.finished.emit(jobs)
        except Exception as e:
            self.error.emit(str(e))


class DeleteJobWorker(QThread):
    """Delete a job workspace and output."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def run(self):
        try:
            r = requests.delete(f"{get_base_url()}/api/jobs/{self.job_id}", timeout=15)
            r.raise_for_status()
            self.finished.emit(self.job_id)
        except Exception as e:
            self.error.emit(str(e))


class WarmTTSWorker(QThread):
    """Background trigger to pre-warm TTS worker in VRAM."""
    def run(self):
        try:
            _post("/api/tts/warm", {}, timeout=10)
        except Exception:
            pass


class StopTTSWorker(QThread):
    """Tell backend to terminate the warm TTS worker and free all RAM/VRAM."""
    def run(self):
        try:
            _post("/api/tts/stop", {}, timeout=5)
        except Exception:
            pass


class RegenTTSWorker(QThread):
    """Regenerate TTS audio for a single segment."""
    finished = pyqtSignal(int, dict)   # seg_idx, result
    error = pyqtSignal(int, str)

    def __init__(self, job_id: str, seg_idx: int, voice: str, speed: float = 1.0, text: str = ""):
        super().__init__()
        self.job_id = job_id
        self.seg_idx = seg_idx
        self.voice = voice
        self.speed = speed
        self.text = text

    def run(self):
        try:
            payload = {"voice": self.voice, "speed": self.speed}
            if self.text:
                payload["text"] = self.text
            result = _post(
                f"/api/jobs/{self.job_id}/segments/{self.seg_idx}/tts",
                payload,
                timeout=120,
            )
            self.finished.emit(self.seg_idx, result)
        except Exception as e:
            self.error.emit(self.seg_idx, str(e))


class BatchUpdateSegmentsWorker(QThread):
    """Batch update multiple segments atomically."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, job_id: str, segments: list, rebuild_audio: bool = False):
        super().__init__()
        self.job_id = job_id
        self.segments = segments
        self.rebuild_audio = rebuild_audio

    def run(self):
        try:
            result = _post(
                f"/api/jobs/{self.job_id}/segments/batch-update",
                {"segments": self.segments, "rebuild_audio": self.rebuild_audio},
                timeout=30,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class UpdateSegmentWorker(QThread):
    """Update segment text/timing/voice."""
    finished = pyqtSignal(int, dict)
    error = pyqtSignal(int, str)

    def __init__(self, job_id: str, seg_idx: int, payload: dict):
        super().__init__()
        self.job_id = job_id
        self.seg_idx = seg_idx
        self.payload = payload

    def run(self):
        try:
            result = _put(
                f"/api/jobs/{self.job_id}/segments/{self.seg_idx}",
                self.payload,
                timeout=30,
            )
            self.finished.emit(self.seg_idx, result)
        except Exception as e:
            self.error.emit(self.seg_idx, str(e))


class LoadSettingsWorker(QThread):
    """Load settings from API."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            data = _get("/api/settings")
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class SaveSettingsWorker(QThread):
    """Save settings via API."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, payload: dict):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            result = _post("/api/settings", self.payload)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MergeVideosWorker(QThread):
    """Merge multiple videos via API."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, videos: list, output_name: str, force_reencode: bool = False):
        super().__init__()
        self.videos = videos
        self.output_name = output_name
        self.force_reencode = force_reencode

    def run(self):
        try:
            result = _post("/api/tools/merge", {
                "videos": self.videos,
                "output_name": self.output_name,
                "force_reencode": self.force_reencode,
            }, timeout=600)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class RenderVideoWorker(QThread):
    """Trigger final video rendering with styled hard subtitles."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def run(self):
        try:
            res = _post(f"/api/jobs/{self.job_id}/render", {}, timeout=600)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class CreateSegmentWorker(QThread):
    """Add a new segment to job."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, job_id: str, payload: dict):
        super().__init__()
        self.job_id = job_id
        self.payload = payload

    def run(self):
        try:
            res = _post(f"/api/jobs/{self.job_id}/segments", self.payload)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class DeleteSegmentWorker(QThread):
    """Delete a segment from job."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, job_id: str, seg_id: int):
        super().__init__()
        self.job_id = job_id
        self.seg_id = seg_id

    def run(self):
        try:
            res = _delete(f"/api/jobs/{self.job_id}/segments/{self.seg_id}")
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class BatchDeleteSegmentsWorker(QThread):
    """Batch delete multiple segments from job."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, job_id: str, seg_ids: list):
        super().__init__()
        self.job_id = job_id
        self.seg_ids = seg_ids

    def run(self):
        try:
            res = _post(f"/api/jobs/{self.job_id}/segments/batch-delete", {"seg_ids": self.seg_ids})
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class MergeSegmentsWorker(QThread):
    """Merge multiple segments in job."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, job_id: str, seg_ids: list):
        super().__init__()
        self.job_id = job_id
        self.seg_ids = seg_ids

    def run(self):
        try:
            res = _post(f"/api/jobs/{self.job_id}/segments/merge", {"seg_ids": self.seg_ids})
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class SplitSegmentWorker(QThread):
    """Split a segment into two or more parts proportionally via API."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        job_id: str,
        seg_id: int,
        part1_text: str = "",
        part2_text: str = "",
        split_time: Optional[float] = None,
        parts: Optional[list] = None,
    ):
        super().__init__()
        self.job_id = job_id
        self.seg_id = seg_id
        self.part1_text = part1_text
        self.part2_text = part2_text
        self.split_time = split_time
        self.parts = parts

    def run(self):
        try:
            if self.parts and len(self.parts) >= 2:
                payload = {
                    "seg_id": self.seg_id,
                    "parts": self.parts,
                }
            else:
                payload = {
                    "seg_id": self.seg_id,
                    "part1_text": self.part1_text,
                    "part2_text": self.part2_text,
                }
                if self.split_time is not None:
                    payload["split_time"] = self.split_time
            res = _post(f"/api/jobs/{self.job_id}/segments/split", payload)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class EditVideoWorker(QThread):
    """Process video editing (Crop, Color Box Overlay, Image/Logo Overlay) via API."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, payload: dict):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            res = _post("/api/tools/edit-video", self.payload, timeout=600)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class TrimVideoWorker(QThread):
    """Trim video segment via API in background thread."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, payload: dict):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            res = _post("/api/tools/trim-video", self.payload, timeout=300)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class CheckCDPWorker(QThread):
    """Check CDP port responsiveness in background thread."""
    status_checked = pyqtSignal(bool)

    def run(self):
        try:
            from dubstudio.llm.cdp_gemini import is_cdp_ready
            ready = is_cdp_ready(9222)
            self.status_checked.emit(ready)
        except Exception:
            self.status_checked.emit(False)


class LaunchBrowserCDPWorker(QThread):
    """Launch or focus Gemini browser window in background thread."""
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, hidden: bool = False):
        super().__init__()
        self.hidden = hidden

    def run(self):
        try:
            from dubstudio.llm.cdp_gemini import launch_browser_cdp, is_cdp_ready
            ready = launch_browser_cdp(9222, hidden=self.hidden)
            self.finished.emit(ready and is_cdp_ready(9222))
        except Exception as e:
            self.error.emit(str(e))


class DownloadComponentWorker(QThread):
    """Download AI models or components in background thread with progress feedback."""
    progress = pyqtSignal(str, int, int, int)  # pkg_id, pct, downloaded, total
    finished = pyqtSignal(str, bool, str)       # pkg_id, ok, msg
    error = pyqtSignal(str, str)                # pkg_id, err_msg

    def __init__(self, pkg: dict):
        super().__init__()
        self.pkg = pkg
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        pkg_id = self.pkg.get("id", "unknown")
        try:
            from dubstudio.components import download_component_file
            def _cb(pct, down, tot):
                self.progress.emit(pkg_id, pct, down, tot)

            ok = download_component_file(self.pkg, progress_cb=_cb, cancel_flag=lambda: self._cancelled)
            if ok:
                self.finished.emit(pkg_id, True, f"Tải gói '{self.pkg.get('name')}' thành công!")
            else:
                self.finished.emit(pkg_id, False, "Tiến trình tải bị hủy.")
        except Exception as e:
            self.error.emit(pkg_id, str(e))


class StartupCheckWorker(QThread):
    """Scan physical components on disk, sync installed.json, and check for updates."""
    finished = pyqtSignal(dict)

    def run(self):
        try:
            from dubstudio.updater import check_all_updates
            res = check_all_updates()
            self.finished.emit(res)
        except Exception:
            self.finished.emit({})



