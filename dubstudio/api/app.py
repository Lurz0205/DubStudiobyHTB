"""FastAPI application for DubStudio local web interface."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import add_event_listener, emit_event, remove_event_listener
from dubstudio.jobstate import JobContext
from dubstudio.stages import (
    analyze,
    asr,
    extract_audio,
    fit,
    ingest,
    mix,
    render,
    separate,
    translate,
    tts,
    units,
    voice_assign,
)
from dubstudio.tools.merge import merge_videos

app = FastAPI(title="DubStudio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from dubstudio.logging_setup import setup_app_logging, get_logs_dir
_api_logger = setup_app_logging()

@app.exception_handler(DubError)
async def dub_error_handler(request, exc: DubError):
    log_path = str(get_logs_dir() / "app.log")
    _api_logger.error(f"DubError on {request.url.path}: [{exc.code}] {exc.user_message_vi} | Hint: {exc.hint_vi}")
    return JSONResponse(
        status_code=400,
        content={
            "code": exc.code,
            "message_vi": exc.user_message_vi,
            "hint_vi": exc.hint_vi,
            "log_path": log_path,
        },
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    import traceback
    log_path = str(get_logs_dir() / "app.log")
    tb = traceback.format_exc()
    _api_logger.error(f"Unhandled 500 error on {request.url.path}: {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message_vi": f"Lỗi hệ thống ({type(exc).__name__}): {str(exc)}",
            "hint_vi": "Vui lòng xem chi tiết nguyên nhân trong file nhật ký (log) hoặc thử lại thao tác.",
            "log_path": log_path,
        },
    )


@app.get("/")
@app.get("/api/health")
def healthcheck():
    """Healthcheck endpoint for subprocesses and clients."""
    return {"status": "ok", "app": "DubStudio"}


@app.post("/api/tts/warm")
def warm_tts_worker():
    """Pre-warm TTS worker in background so subsequent synthesis is instant."""
    def _warm():
        try:
            get_tts_worker()
        except Exception:
            pass
    threading.Thread(target=_warm, daemon=True).start()
    return {"status": "warming"}

# Background job queue and active runner tracking
_job_lock = threading.Lock()
_active_job_id: Optional[str] = None
_job_event_queues: Dict[str, List[asyncio.Queue]] = {}

# Persistent TTS Warm Worker process
_tts_worker_proc: Optional[subprocess.Popen] = None
_tts_worker_lock = threading.RLock()
_segments_lock = threading.Lock()


def _quick_rebuild_voice_track(job_id: str) -> None:
    """Fast in-memory voice track assembly using numpy and soundfile in <30ms with anti-overlap."""
    try:
        import numpy as np
        import soundfile as sf
        from dubstudio.paths import resolve_job_workspace
        ws_dir = resolve_job_workspace(job_id)
        seg_file = ws_dir / "segments.json"
        if not seg_file.exists():
            return
        with _segments_lock:
            try:
                data = json.loads(seg_file.read_text(encoding="utf-8"))
            except Exception:
                return
        segments = data.get("segments", [])
        if not segments:
            return
        video_dur = float(data.get("video", {}).get("duration", 0.0) or 0.0)
        sr = 24000
        if not video_dur:
            video_dur = max([s.get("end", 0.0) for s in segments], default=10.0) + 2.0
        total_samples = int(video_dur * sr) + sr
        voice_track = np.zeros(total_samples, dtype=np.float32)

        # Check fit_plan.json first
        fit_plan_file = ws_dir / "fit_plan.json"
        items = []
        if fit_plan_file.exists():
            try:
                raw_fp = json.loads(fit_plan_file.read_text(encoding="utf-8"))
                if isinstance(raw_fp, list):
                    items = raw_fp
            except Exception:
                items = []

        if not items:
            for s in segments:
                if s.get("mute_tts") or s.get("keep_original"):
                    continue
                items.append({
                    "id": s["id"],
                    "start": float(s.get("voice_start", s.get("start", 0.0))),
                    "wav": s.get("tts_file") or f"tts/{s['id']:04d}.wav",
                })

        items.sort(key=lambda x: float(x.get("start", 0.0)))
        for i, it in enumerate(items):
            wav_rel = it.get("wav", "")
            wav_path = ws_dir / wav_rel
            if not wav_path.exists():
                wav_path = ws_dir / "tts" / f"{it.get('id', 0):04d}.wav"
            if not wav_path.exists():
                continue
            try:
                audio_data, file_sr = sf.read(str(wav_path.resolve()))
                if audio_data.ndim > 1:
                    audio_data = audio_data.mean(axis=1)
                if file_sr != sr:
                    target_len = int(len(audio_data) * sr / file_sr)
                    audio_data = np.interp(
                        np.linspace(0, len(audio_data), target_len, endpoint=False),
                        np.arange(len(audio_data)),
                        audio_data,
                    ).astype(np.float32)
                st = float(it.get("start", 0.0))

                # Strict anti-overlap ("chống đè giọng") enforcement
                if i + 1 < len(items):
                    next_st = float(items[i + 1].get("start", st + 1.0))
                    max_allowed_dur = max(0.1, next_st - st + 0.08)
                    curr_dur = len(audio_data) / sr
                    if curr_dur > max_allowed_dur:
                        max_samples = int(max_allowed_dur * sr)
                        audio_data = audio_data[:max_samples]
                        fade_samples = min(int(0.05 * sr), len(audio_data))
                        if fade_samples > 0:
                            audio_data[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)

                start_sample = max(0, int(st * sr))
                end_sample = start_sample + len(audio_data)
                if end_sample > len(voice_track):
                    pad_len = end_sample - len(voice_track) + sr
                    voice_track = np.pad(voice_track, (0, pad_len), "constant")
                voice_track[start_sample:end_sample] += audio_data
            except Exception:
                continue
        peak = np.max(np.abs(voice_track)) if len(voice_track) > 0 else 0.0
        if peak > 0.95:
            voice_track = voice_track * (0.95 / peak)
        out_file = ws_dir / "voice_track.wav"
        sf.write(str(out_file.resolve()), voice_track, sr, subtype="PCM_16")
        out_raw = ws_dir / "voice_raw.wav"
        try:
            sf.write(str(out_raw.resolve()), voice_track, sr, subtype="PCM_16")
        except Exception:
            pass
    except Exception:
        pass


def get_tts_worker() -> subprocess.Popen:
    """Get or start the warm TTS worker process."""
    global _tts_worker_proc
    from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs
    with _tts_worker_lock:
        if _tts_worker_proc is None or _tts_worker_proc.poll() is not None:
            py_exe = str(get_runtime_python().resolve())
            cmd = [py_exe, "-m", "dubstudio.tts.worker_server"]
            _tts_worker_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=get_subprocess_env(),
                **get_subprocess_kwargs(),
            )
            _api_logger.info("Starting warm TTS worker process...")
            ready_data = None
            for _ in range(60):
                line = _tts_worker_proc.stdout.readline()
                if not line:
                    break
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    ready_data = json.loads(line_str)
                    break
                except Exception:
                    continue
            if not ready_data or ready_data.get("status") != "ready":
                err_msg = ready_data.get("error") if ready_data else "No response from worker"
                _tts_worker_proc = None
                _api_logger.error(f"TTS worker failed to initialize: {err_msg}")
                raise RuntimeError(f"TTS worker init error: {err_msg}")
            _api_logger.info("Warm TTS worker process is READY.")
        return _tts_worker_proc


def stop_tts_worker():
    """Terminate and release the warm TTS worker process to free all RAM and VRAM."""
    global _tts_worker_proc
    with _tts_worker_lock:
        if _tts_worker_proc is not None:
            try:
                try:
                    _tts_worker_proc.stdin.write(json.dumps({"cmd": "exit"}) + "\n")
                    _tts_worker_proc.stdin.flush()
                    _tts_worker_proc.wait(timeout=1.0)
                except Exception:
                    _tts_worker_proc.terminate()
            except Exception:
                pass
            _tts_worker_proc = None


@app.post("/api/tts/stop")
def stop_tts_worker_endpoint():
    """Stop the TTS worker and immediately free all RAM & VRAM."""
    stop_tts_worker()
    return {"status": "stopped"}


def broadcast_event(event: Dict[str, Any]) -> None:
    """Callback hooked into dubstudio.events to feed SSE subscribers."""
    global _active_job_id
    if not _active_job_id:
        return
    queues = _job_event_queues.get(_active_job_id, [])
    for q in queues:
        try:
            q.put_nowait(event)
        except Exception:
            pass


add_event_listener(broadcast_event)


# Models
class CreateJobRequest(BaseModel):
    video_path: str
    project_name: Optional[str] = None


class UpdateSegmentRequest(BaseModel):
    vi_text: Optional[str] = None
    tts_text: Optional[str] = None
    voice: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    speed: Optional[float] = None
    voice_start: Optional[float] = None
    sub_slices: Optional[List[Dict[str, Any]]] = None
    cues: Optional[List[Dict[str, Any]]] = None
    mute_tts: Optional[bool] = None
    mute_sub: Optional[bool] = None
    keep_original: Optional[bool] = None


class OrigAudioRange(BaseModel):
    id: int
    start: float
    end: float
    label: Optional[str] = "Âm gốc"


class SaveOrigRangesRequest(BaseModel):
    ranges: List[OrigAudioRange]


class BatchUpdateSegmentsRequest(BaseModel):
    segments: List[Dict[str, Any]]
    rebuild_audio: Optional[bool] = False


class RegenTTSRequest(BaseModel):
    text: Optional[str] = None
    voice: Optional[str] = None
    speed: Optional[float] = 1.0


class CreateSegmentRequest(BaseModel):
    start: float
    end: float
    vi_text: str = ""
    tts_text: Optional[str] = None
    voice: Optional[str] = None
    speaker: Optional[str] = None
    gender: Optional[str] = "female"


class MergeSegmentsRequest(BaseModel):
    seg_ids: List[int]


class BatchDeleteSegmentsRequest(BaseModel):
    seg_ids: List[int]


class SplitSegmentRequest(BaseModel):
    seg_id: int
    part1_text: Optional[str] = None
    part2_text: Optional[str] = None
    parts: Optional[List[str]] = None
    split_time: Optional[float] = None
    part1_src: Optional[str] = None
    part2_src: Optional[str] = None


class SubtitleStyleRequest(BaseModel):
    font_name: str = "Arial"
    font_size: int = 24
    primary_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 2
    box_color: Optional[str] = "rgba(0, 0, 0, 0.6)"
    box_padding: int = 10
    box_radius: int = 6
    box_blur: int = 4
    box_mode: Optional[str] = "full_width"
    box_opacity: Optional[float] = 0.6
    orig_bgm_volume: Optional[float] = 0.80
    bgm_volume: Optional[float] = 0.80
    custom_bgm_path: Optional[str] = None
    custom_bgm_volume: Optional[float] = 0.50
    include_orig_voice: Optional[bool] = False
    orig_voice_volume: Optional[float] = 0.00
    vi_voice_volume: Optional[float] = 1.00
    box_width: Optional[int] = None
    box_height: Optional[int] = None
    box_width_pct: Optional[float] = 85.0
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    text_align: str = "center"
    margin_v: int = 35

    model_config = {"extra": "allow"}



class JobConfigRequest(BaseModel):
    translation_tone: Optional[str] = None
    style: Optional[str] = None
    default_male_voice: Optional[str] = None
    default_female_voice: Optional[str] = None
    detect_gender: Optional[bool] = None
    single_voice_gender: Optional[str] = None
    words_per_line: Optional[int] = None


class SettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    backup_gemini_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    translation_provider: Optional[str] = None
    translation_model: Optional[str] = None
    auto_fallback: Optional[bool] = None
    default_male_voice: Optional[str] = None
    default_female_voice: Optional[str] = None
    whisper_model: Optional[str] = None
    separation_model: Optional[str] = None


class MergeRequest(BaseModel):
    videos: List[str]
    output_name: str = "merged.mp4"
    force_reencode: bool = False


class EditVideoRequest(BaseModel):
    video_path: str
    preview_width: Optional[float] = None
    preview_height: Optional[float] = None
    crop: Optional[Dict[str, Any]] = None
    crop_box: Optional[Dict[str, Any]] = None
    aspect_ratio: Optional[str] = None
    canvas_color: Optional[str] = "000000"
    color_box: Optional[Dict[str, Any]] = None
    color_boxes: Optional[List[Dict[str, Any]]] = None
    image_overlay: Optional[Dict[str, Any]] = None
    subtitles_enabled: Optional[bool] = False
    job_id: Optional[str] = None
    subtitles_path: Optional[str] = None
    output_name: Optional[str] = "edited_video.mp4"


class TrimVideoRequest(BaseModel):
    video_path: str
    start_s: float
    end_s: float
    output_name: Optional[str] = None
    fast_copy: Optional[bool] = True

    model_config = {"extra": "allow"}


# Helper to run pipeline in isolated background worker process
def _run_pipeline_worker(job_id: str, video_path: Path, subtitles_only: bool = False, dub_only: bool = False) -> None:
    global _active_job_id
    try:
        from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs
        py_exe = str(get_runtime_python().resolve())

        cmd = [
            py_exe, "-m", "dubstudio", "run",
            str(video_path.resolve()),
            "--job-id", job_id,
            "--no-render",
        ]
        if subtitles_only:
            cmd.append("--subtitles-only")
        if dub_only:
            cmd.append("--dub-only")

        # Run pipeline in isolated subprocess so VRAM and memory are cleaned up
        # and native CUDA crashes never take down the GUI desktop app.
        env = get_subprocess_env()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            **get_subprocess_kwargs(),
        )

        output_lines = []
        for line in proc.stdout:
            line_str = line.strip()
            if not line_str:
                continue
            output_lines.append(line_str)
            # Check for JSON progress events emitted by dubstudio.events
            if line_str.startswith("{") and line_str.endswith("}"):
                try:
                    evt = json.loads(line_str)
                    if "stage" in evt and "pct" in evt:
                        emit_event(
                            evt["stage"],
                            float(evt["pct"]),
                            evt.get("msg", ""),
                            evt.get("level", "info"),
                        )
                except Exception:
                    pass

        proc.wait()
        if proc.returncode == 0:
            if subtitles_only:
                emit_event("pipeline", 100.0, "Hoàn tất tạo và dịch phụ đề! Bạn có thể kiểm tra trước khi lồng tiếng.")
            else:
                # Generate preview_dubbed.mp4 by stream-copying video and attaching voice_track.wav (no subtitles burned)
                from dubstudio.paths import resolve_job_workspace, resolve_tool
                from dubstudio.packaging import get_subprocess_env, get_subprocess_kwargs
                ws_dir = resolve_job_workspace(job_id)
                voice_track = ws_dir / "voice_track.wav"
                in_vid = ws_dir / "input.mp4"
                prev_vid = ws_dir / "preview_dubbed.mp4"
                if in_vid.exists() and voice_track.exists():
                    ffmpeg_exe = str(resolve_tool("ffmpeg"))
                    remux_cmd = [
                        ffmpeg_exe, "-y",
                        "-i", str(in_vid.resolve()),
                        "-i", str(voice_track.resolve()),
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        str(prev_vid.resolve()),
                    ]
                    subprocess.run(
                        remux_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=get_subprocess_env(),
                        **get_subprocess_kwargs(),
                    )
                emit_event("pipeline", 100.0, "Hoàn tất tạo giọng lồng tiếng (chưa khắc phụ đề)!")
        else:
            err_detail = "Tiến trình lồng tiếng bị gián đoạn hoặc gặp lỗi"
            # Prioritize clean user-facing DubError message and hint if printed by CLI
            found_error = False
            for idx, l in enumerate(output_lines):
                if "❌ Lỗi" in l or "Lỗi [" in l or "STAGE_FAILED" in l:
                    err_detail = l.strip()
                    # Check next lines for hint
                    for next_l in output_lines[idx + 1: idx + 4]:
                        if "💡" in next_l or "Khắc phục" in next_l or "nhật ký" in next_l:
                            err_detail += f" ({next_l.strip()})"
                            break
                    found_error = True
                    break
            if not found_error:
                for l in reversed(output_lines):
                    if not (l.startswith("{") and l.endswith("}")):
                        err_detail = l
                        break
            from dubstudio.paths import get_logs_dir
            logs_dir = get_logs_dir()
            emit_event("pipeline", 0.0, f"Lỗi quy trình: {err_detail} (Xem logs: {logs_dir})", level="error")
    except Exception as e:
        from dubstudio.paths import get_logs_dir
        logs_dir = get_logs_dir()
        emit_event("pipeline", 0.0, f"Lỗi quy trình: {e} (Xem logs: {logs_dir})", level="error")
    finally:
        with _job_lock:
            _active_job_id = None
        # Notify SSE listeners that pipeline has finished
        queues = _job_event_queues.get(job_id, [])
        for q in list(queues):
            try:
                q.put_nowait("[DONE]")
            except Exception:
                pass


# --- API Routes ---

@app.get("/api/jobs")
def list_jobs():
    """List all workspace jobs with their stage statuses and metadata."""
    cfg = AppConfig.load()
    from dubstudio.paths import resolve_job_workspace

    candidate_roots = [cfg.general.workspace_dir]

    jobs = []
    seen_ids = set()
    non_job_dirs = {".cache", ".edge_profile", "components", "__pycache__"}

    for root in candidate_roots:
        if not root.exists():
            continue
        for item in root.iterdir():
            if item.is_dir() and not item.name.startswith(".") and item.name not in non_job_dirs and item.name not in seen_ids:
                seen_ids.add(item.name)
                actual_dir = resolve_job_workspace(item.name)
                state_file = actual_dir / "state.json"
                meta_file = actual_dir / "meta.json"
                probe_file = actual_dir / "probe.json"

                video_name = item.name
                created_at = ""
                if meta_file.exists():
                    try:
                        m = json.loads(meta_file.read_text(encoding="utf-8"))
                        video_name = m.get("video_name", video_name)
                        created_at = m.get("created_at", "")
                    except Exception:
                        pass

                duration = 0.0
                if probe_file.exists():
                    try:
                        p = json.loads(probe_file.read_text(encoding="utf-8"))
                        duration = float(p.get("format", {}).get("duration", 0.0))
                    except Exception:
                        pass

                job_info = {
                    "id": item.name,
                    "video_name": video_name,
                    "created_at": created_at,
                    "duration": duration,
                    "has_state": state_file.exists(),
                    "stages": {},
                    "is_active": (item.name == _active_job_id),
                    "has_video": (cfg.general.out_dir / f"{item.name}_vi.mp4").exists(),
                }
                if state_file.exists():
                    try:
                        state_data = json.loads(state_file.read_text(encoding="utf-8"))
                        job_info["stages"] = state_data.get("stages", {})
                    except Exception:
                        pass
                jobs.append(job_info)
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"jobs": jobs, "active_job_id": _active_job_id}


@app.post("/api/jobs/create")
def create_job(req: CreateJobRequest):
    """Create a new job from a local video path and run ingest stage immediately."""
    video_path = Path(req.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Tệp video không tồn tại")

    cfg = AppConfig.load()
    ws_base = cfg.general.workspace_dir
    ws_base.mkdir(parents=True, exist_ok=True)

    custom_name = (req.project_name or "").strip()
    if custom_name:
        clean_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in custom_name).strip("_")
        base_name = clean_name if clean_name else time.strftime("%d%m%Y")
    else:
        base_name = time.strftime("%d%m%Y")

    candidate = base_name
    idx = 1
    while (ws_base / candidate).exists():
        candidate = f"{base_name}_{idx}"
        idx += 1

    job_id = candidate
    display_name = custom_name if custom_name else candidate

    # Atomic workspace creation using temporary directory to prevent orphaned folders
    tmp_dir = ws_base / f".tmp_{job_id}_{int(time.time() * 1000)}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ws_dir = ws_base / job_id

    try:
        tmp_job = JobContext(workspace_path=tmp_dir, job_id=job_id, input_path=video_path)
        meta = {
            "job_id": job_id,
            "video_name": display_name,
            "video_path": str(video_path.resolve()),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        (tmp_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # Ingest video immediately so probe.json and input.mp4 exist
        ingest.run(tmp_job, cfg, video_path)

        # Atomic move to final workspace location with Windows retry loop
        for attempt in range(5):
            try:
                if ws_dir.exists():
                    shutil.rmtree(ws_dir, ignore_errors=True)
                os.replace(tmp_dir, ws_dir)
                break
            except (OSError, PermissionError):
                if attempt < 4:
                    time.sleep(0.15)
                else:
                    shutil.copytree(tmp_dir, ws_dir, dirs_exist_ok=True)
                    shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as e:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        _api_logger.error(f"Failed to create job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Không thể khởi tạo dự án: {e}")

    return {
        "job_id": job_id,
        "video_name": display_name,
        "video_path": str(video_path.resolve()),
        "workspace": str(ws_dir.resolve()),
    }


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    """Delete job workspace and any rendered output cleanly without leaving leftovers."""
    global _active_job_id
    with _job_lock:
        if _active_job_id == job_id:
            _active_job_id = None

    import gc
    gc.collect()

    cfg = AppConfig.load()
    from dubstudio.paths import get_user_base_dir, get_app_dir, get_workspace_dir
    candidate_roots = [
        cfg.general.workspace_dir,
        get_workspace_dir(),
        get_user_base_dir() / "workspace",
        get_app_dir() / "workspace",
        Path("dist/DubStudio/workspace"),
        Path("workspace"),
    ]
    import stat
    def _onerror(func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    seen_dirs = set()
    for root in candidate_roots:
        try:
            if not root or not Path(root).exists():
                continue
            target = (Path(root) / job_id).resolve()
            if target.exists() and target not in seen_dirs:
                seen_dirs.add(target)
                try:
                    shutil.rmtree(target, onerror=_onerror)
                except Exception:
                    shutil.rmtree(target, ignore_errors=True)
        except Exception:
            pass

    # Clean all associated output files or folders in out_dir
    out_dir = cfg.general.out_dir
    if out_dir.exists():
        job_out_dir = out_dir / job_id
        if job_out_dir.exists() and job_out_dir.is_dir():
            shutil.rmtree(job_out_dir, ignore_errors=True)

        for p in out_dir.glob(f"*{job_id}*"):
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
            except Exception:
                pass

    return {"status": "deleted", "job_id": job_id}


@app.post("/api/jobs/upload")
async def upload_job(file: UploadFile = File(...)):
    """Upload a video file and prepare job."""
    samples_dir = Path("samples")
    samples_dir.mkdir(parents=True, exist_ok=True)
    target_path = samples_dir / file.filename

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    from dubstudio.cli import get_job_id_for_file
    job_id = get_job_id_for_file(target_path)
    return {"job_id": job_id, "filename": file.filename, "video_path": str(target_path.resolve())}


@app.post("/api/jobs/{job_id}/start")
def start_job(job_id: str, req: CreateJobRequest):
    """Start or resume pipeline processing for a job."""
    global _active_job_id
    video_path = Path(req.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Video không tồn tại")

    with _job_lock:
        if _active_job_id is not None:
            raise HTTPException(status_code=409, detail=f"Hệ thống đang bận xử lý job: {_active_job_id}")
        _active_job_id = job_id

    thread = threading.Thread(target=_run_pipeline_worker, args=(job_id, video_path), daemon=True)
    thread.start()
    return {"status": "started", "job_id": job_id}


@app.post("/api/jobs/{job_id}/run")
async def run_job_stream(job_id: str, req: Optional[dict] = None):
    """Run pipeline and stream progress events until complete."""
    cfg = AppConfig.load()
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    video_path = ws_dir / "input.mp4"
    if not video_path.exists():
        # Fallback candidate from workspace
        for cand in [Path("samples") / f"{job_id}.mp4", ws_dir / f"{job_id}.mp4"]:
            if cand.exists():
                video_path = cand
                break

    # Save preferences if provided
    if req:
        conf_file = ws_dir / "job_config.json"
        conf_data = {}
        if conf_file.exists():
            try:
                conf_data = json.loads(conf_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        if req.get("voice_male"):
            conf_data["default_male_voice"] = req["voice_male"]
        if req.get("voice_female"):
            conf_data["default_female_voice"] = req["voice_female"]
        if req.get("style"):
            conf_data["translation_tone"] = req["style"]
            conf_data["style"] = req["style"]
        if "detect_gender" in req:
            conf_data["detect_gender"] = bool(req["detect_gender"])
        if req.get("single_voice_gender"):
            conf_data["single_voice_gender"] = req["single_voice_gender"]
        conf_file.write_text(json.dumps(conf_data, ensure_ascii=False, indent=2), encoding="utf-8")

    global _active_job_id
    with _job_lock:
        if _active_job_id is not None and _active_job_id != job_id:
            raise HTTPException(status_code=409, detail=f"Hệ thống đang bận xử lý job: {_active_job_id}")
        _active_job_id = job_id

    # Queue for streaming
    queue: asyncio.Queue = asyncio.Queue()
    if job_id not in _job_event_queues:
        _job_event_queues[job_id] = []
    _job_event_queues[job_id].append(queue)

    subtitles_only = bool(req.get("subtitles_only", False)) if req else False
    dub_only = bool(req.get("dub_only", False)) if req else False

    # Launch pipeline thread
    t = threading.Thread(target=_run_pipeline_worker, args=(job_id, video_path, subtitles_only, dub_only), daemon=True)
    t.start()

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                if isinstance(data, str) and data == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                if isinstance(data, dict) and (data.get("level") == "error" or (data.get("stage") == "pipeline" and data.get("pct") == 100.0)):
                    yield "data: [DONE]\n\n"
                    break
        except asyncio.CancelledError:
            pass
        finally:
            if job_id in _job_event_queues and queue in _job_event_queues[job_id]:
                _job_event_queues[job_id].remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str):
    """Get metadata for a specific job."""
    cfg = AppConfig.load()
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    if not ws_dir.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ")

    state_file = ws_dir / "state.json"
    stages = {}
    if state_file.exists():
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
            stages = state_data.get("stages", {})
        except Exception:
            pass

    out_video = cfg.general.out_dir / f"{job_id}_vi.mp4"
    orig_video = ws_dir / "input.mp4"

    return {
        "job_id": job_id,
        "video_path": str(out_video.resolve()) if out_video.exists() else (str(orig_video.resolve()) if orig_video.exists() else ""),
        "stages": stages,
        "has_rendered": out_video.exists(),
    }


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    """Server-Sent Events (SSE) streaming progress events for a job."""
    queue: asyncio.Queue = asyncio.Queue()
    if job_id not in _job_event_queues:
        _job_event_queues[job_id] = []
    _job_event_queues[job_id].append(queue)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if job_id in _job_event_queues and queue in _job_event_queues[job_id]:
                _job_event_queues[job_id].remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/segments")
def get_segments(job_id: str):
    """Get all subtitle segments for a job."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    seg_file = ws_dir / "segments.json"
    if not seg_file.exists():
        raw_file = ws_dir / "raw_segments.json"
        if raw_file.exists():
            try:
                data = json.loads(raw_file.read_text(encoding="utf-8"))
                return {"segments": data.get("segments", [])}
            except Exception:
                pass
        return {"segments": []}
    try:
        data = json.loads(seg_file.read_text(encoding="utf-8"))
        return {"segments": data.get("segments", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/jobs/{job_id}/segments/{seg_id}")
def update_segment(job_id: str, seg_id: int, req: UpdateSegmentRequest):
    """Update timing (start/end), vi_text, tts_text, voice, speed, or voice_start of a segment."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    seg_file = ws_dir / "segments.json"
    if not seg_file.exists():
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu segments")

    with _segments_lock:
        data = json.loads(seg_file.read_text(encoding="utf-8"))
        segments = data.get("segments", [])

        target_seg = None
        for s in segments:
            if s["id"] == seg_id:
                target_seg = s
                break

        if not target_seg:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đoạn thoại {seg_id}")

        if req.vi_text is not None:
            from dubstudio.text.vi_normalize import normalize_for_tts
            target_seg["vi_text"] = req.vi_text
            target_seg["tts_text"] = req.tts_text or normalize_for_tts(req.vi_text.replace("\n", " "))
        if req.sub_slices is not None:
            target_seg["sub_slices"] = req.sub_slices
        if req.cues is not None:
            target_seg["cues"] = req.cues
        if req.voice is not None:
            target_seg["voice"] = req.voice
        if req.start is not None:
            target_seg["start"] = round(req.start, 3)
        if req.end is not None:
            target_seg["end"] = round(req.end, 3)
        if req.speed is not None:
            target_seg["speed"] = req.speed
        if req.voice_start is not None:
            target_seg["voice_start"] = round(req.voice_start, 3)
        if req.mute_tts is not None:
            target_seg["mute_tts"] = req.mute_tts
        if req.mute_sub is not None:
            target_seg["mute_sub"] = req.mute_sub
        if req.keep_original is not None:
            target_seg["keep_original"] = req.keep_original

        seg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if req.voice_start is not None:
        _quick_rebuild_voice_track(job_id)

    return {"status": "updated", "segment": target_seg}


@app.post("/api/jobs/{job_id}/segments/batch-update")
def batch_update_segments(job_id: str, req: BatchUpdateSegmentsRequest):
    """Batch update multiple segments in segments.json atomically."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    seg_file = ws_dir / "segments.json"
    if not seg_file.exists():
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu segments")

    from dubstudio.text.vi_normalize import normalize_for_tts

    with _segments_lock:
        data = json.loads(seg_file.read_text(encoding="utf-8"))
        segments = data.get("segments", [])
        seg_map = {s["id"]: s for s in segments}

        updated_count = 0
        for item in req.segments:
            s_id = item.get("id")
            if s_id in seg_map:
                target = seg_map[s_id]
                if "vi_text" in item and item["vi_text"].strip() != target.get("vi_text", "").strip():
                    target["vi_text"] = item["vi_text"]
                    target["tts_text"] = item.get("tts_text") or normalize_for_tts(item["vi_text"].replace("\n", " "))
                if "voice" in item and item["voice"]:
                    target["voice"] = item["voice"]
                if "speed" in item and item["speed"] is not None:
                    target["speed"] = item["speed"]
                if "start" in item:
                    target["start"] = round(float(item["start"]), 3)
                if "end" in item:
                    target["end"] = round(float(item["end"]), 3)
                if "voice_start" in item:
                    target["voice_start"] = round(float(item["voice_start"]), 3)
                if "sub_slices" in item:
                    target["sub_slices"] = item["sub_slices"]
                if "cues" in item:
                    target["cues"] = item["cues"]
                if "mute_tts" in item:
                    target["mute_tts"] = bool(item["mute_tts"])
                if "mute_sub" in item:
                    target["mute_sub"] = bool(item["mute_sub"])
                if "keep_original" in item:
                    target["keep_original"] = bool(item["keep_original"])
                updated_count += 1

        seg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if req.rebuild_audio:
        _quick_rebuild_voice_track(job_id)

    return {"status": "batch_updated", "count": updated_count}


@app.post("/api/jobs/{job_id}/segments")
def create_segment(job_id: str, req: CreateSegmentRequest):
    """Create a new segment in segments.json."""
    cfg = AppConfig.load()
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    ws_dir.mkdir(parents=True, exist_ok=True)
    seg_file = ws_dir / "segments.json"
    if seg_file.exists():
        data = json.loads(seg_file.read_text(encoding="utf-8"))
    else:
        video_dur = 0.0
        probe_file = ws_dir / "probe.json"
        if probe_file.exists():
            try:
                p_data = json.loads(probe_file.read_text(encoding="utf-8"))
                video_dur = float(p_data.get("format", {}).get("duration", 0.0) or 0.0)
            except Exception:
                pass
        data = {
            "schema_version": 2,
            "job_id": job_id,
            "video": {"duration": video_dur},
            "segments": [],
        }
    segments = data.get("segments", [])

    new_id = (max([s["id"] for s in segments], default=0) + 1) if segments else 1
    voice = req.voice or cfg.tts.default_female_voice
    from dubstudio.text.vi_normalize import normalize_for_tts
    tts_text = req.tts_text or (normalize_for_tts(req.vi_text) if req.vi_text else "")

    new_seg = {
        "id": new_id,
        "start": round(req.start, 3),
        "end": round(req.end, 3),
        "src_text": "",
        "zh": "",
        "vi_text": req.vi_text,
        "tts_text": tts_text,
        "voice": voice,
        "speaker": req.speaker,
        "gender": req.gender or "female",
        "speed": 1.0,
        "speech_time": round(max(0.1, req.end - req.start), 3),
        "dur": round(max(0.1, req.end - req.start), 3),
        "tts_file": None,
        "tts_dur": None,
        "fit": None,
        "flags": [],
    }

    segments.append(new_seg)
    segments.sort(key=lambda s: s.get("start", 0))
    data["segments"] = segments

    seg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "created", "segment": new_seg}


@app.delete("/api/jobs/{job_id}/segments/{seg_id}")
def delete_segment(job_id: str, seg_id: int):
    """Delete a segment from segments.json and remove its audio file."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    seg_file = ws_dir / "segments.json"
    if not seg_file.exists():
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu segments")

    data = json.loads(seg_file.read_text(encoding="utf-8"))
    segments = data.get("segments", [])

    found = False
    new_segments = []
    for s in segments:
        if s["id"] == seg_id:
            found = True
        else:
            new_segments.append(s)

    if not found:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đoạn thoại {seg_id}")

    data["segments"] = new_segments
    seg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Remove audio file if exists
    wav_path = ws_dir / "tts" / f"{seg_id:04d}.wav"
    if wav_path.exists():
        try:
            wav_path.unlink()
        except Exception:
            pass

    return {"status": "deleted", "id": seg_id}


@app.post("/api/jobs/{job_id}/segments/batch-delete")
def batch_delete_segments(job_id: str, req: BatchDeleteSegmentsRequest):
    """Delete multiple segments from segments.json and remove their audio files."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    seg_file = ws_dir / "segments.json"
    if not seg_file.exists():
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu segments")

    to_del = set(req.seg_ids)
    with _segments_lock:
        data = json.loads(seg_file.read_text(encoding="utf-8"))
        segments = data.get("segments", [])
        new_segments = [s for s in segments if s.get("id") not in to_del]
        data["segments"] = new_segments
        seg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    tts_dir = ws_dir / "tts"
    if tts_dir.exists():
        for sid in to_del:
            wav_path = tts_dir / f"{sid:04d}.wav"
            if wav_path.exists():
                try:
                    wav_path.unlink()
                except Exception:
                    pass

    return {"status": "batch_deleted", "deleted_count": len(segments) - len(new_segments)}


@app.get("/api/jobs/{job_id}/orig-ranges")
def get_orig_ranges(job_id: str):
    """Get list of original audio passthrough ranges."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    f = ws_dir / "orig_audio_ranges.json"
    if f.exists():
        try:
            return {"ranges": json.loads(f.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return {"ranges": []}


@app.post("/api/jobs/{job_id}/orig-ranges")
def save_orig_ranges(job_id: str, req: SaveOrigRangesRequest):
    """Save original audio passthrough ranges."""
    from dubstudio.paths import resolve_job_workspace
    ws = resolve_job_workspace(job_id)
    ws.mkdir(parents=True, exist_ok=True)
    f = ws / "orig_audio_ranges.json"
    dumped = [r.model_dump() for r in req.ranges]
    f.write_text(json.dumps(dumped, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "saved", "ranges": dumped}


@app.post("/api/jobs/{job_id}/segments/merge")
def merge_segments(job_id: str, req: MergeSegmentsRequest):
    """Merge multiple segments (e.g. 2 adjacent lines) into one."""
    if len(req.seg_ids) < 2:
        raise HTTPException(status_code=400, detail="Cần ít nhất 2 đoạn thoại để gộp")

    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    seg_file = ws_dir / "segments.json"
    if not seg_file.exists():
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu segments")

    data = json.loads(seg_file.read_text(encoding="utf-8"))
    segments = data.get("segments", [])

    target_ids = set(req.seg_ids)
    to_merge = [s for s in segments if s["id"] in target_ids]
    if len(to_merge) < 2:
        raise HTTPException(status_code=400, detail="Không tìm đủ các đoạn cần gộp")

    to_merge.sort(key=lambda s: s.get("start", 0))
    base_seg = to_merge[0]

    # Combine texts and timings
    combined_vi = " ".join(s.get("vi_text", "").strip() for s in to_merge if s.get("vi_text"))
    from dubstudio.text.vi_normalize import normalize_for_tts
    base_seg["vi_text"] = combined_vi
    base_seg["tts_text"] = normalize_for_tts(combined_vi)
    base_seg["start"] = to_merge[0]["start"]
    base_seg["end"] = to_merge[-1]["end"]
    base_seg["dur"] = round(base_seg["end"] - base_seg["start"], 3)
    base_seg["speech_time"] = round(sum(s.get("speech_time", 0) for s in to_merge), 3)
    base_seg["tts_file"] = None
    base_seg["tts_dur"] = None

    other_ids = set(s["id"] for s in to_merge[1:])
    new_segments = [s for s in segments if s["id"] not in other_ids]
    data["segments"] = new_segments

    seg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "merged", "segment": base_seg}


@app.post("/api/jobs/{job_id}/segments/split")
@app.post("/api/jobs/{job_id}/segments/{seg_id}/split")
def split_segment(job_id: str, req: SplitSegmentRequest, seg_id: Optional[int] = None):
    """Split a segment into two segments proportionally by word count."""
    target_id = seg_id if seg_id is not None else req.seg_id
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    seg_file = ws_dir / "segments.json"
    if not seg_file.exists():
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu segments")
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu segments")

    data = json.loads(seg_file.read_text(encoding="utf-8"))
    segments = data.get("segments", [])

    target_idx = None
    for idx, s in enumerate(segments):
        if s["id"] == target_id:
            target_idx = idx
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đoạn thoại #{target_id}")

    orig_seg = segments[target_idx]

    # Support either list of parts or part1_text + part2_text
    if req.parts:
        parts_text = [p.strip() for p in req.parts if p and p.strip()]
    else:
        parts_text = [p.strip() for p in [req.part1_text or "", req.part2_text or ""] if p and p.strip()]

    if len(parts_text) < 2:
        raise HTTPException(status_code=400, detail="Cần ít nhất 2 phần câu sau khi tách")

    t_start = float(orig_seg["start"])
    t_end = float(orig_seg["end"])
    total_dur = max(0.2, t_end - t_start)

    word_counts = [max(1, len(p.split())) for p in parts_text]
    total_words = sum(word_counts)

    # Allocate proportional timestamps
    durations = [total_dur * (wc / total_words) for wc in word_counts]
    allocated_times = []
    curr_t = t_start
    for i, d in enumerate(durations):
        if i == len(durations) - 1:
            allocated_times.append((round(curr_t, 3), round(t_end, 3)))
        else:
            next_t = round(curr_t + d, 3)
            # Ensure safety bounds
            next_t = max(curr_t + 0.1, min(t_end - 0.1 * (len(durations) - 1 - i), next_t))
            allocated_times.append((round(curr_t, 3), round(next_t, 3)))
            curr_t = next_t

    from dubstudio.text.vi_normalize import normalize_for_tts

    # Part 0 updates orig_seg
    orig_seg["vi_text"] = parts_text[0]
    orig_seg["tts_text"] = normalize_for_tts(parts_text[0])
    orig_seg["start"] = allocated_times[0][0]
    orig_seg["end"] = allocated_times[0][1]
    orig_seg["dur"] = round(allocated_times[0][1] - allocated_times[0][0], 3)
    orig_seg["speech_time"] = orig_seg["dur"]
    orig_seg["tts_file"] = None
    orig_seg["tts_dur"] = None
    if req.part1_src is not None:
        orig_seg["src_text"] = req.part1_src
        orig_seg["zh"] = req.part1_src

    # Subsequent parts create new segments
    max_id = max([s["id"] for s in segments], default=0)
    new_segments = []
    for idx, (p_st, p_en) in enumerate(allocated_times[1:], start=1):
        new_id = max_id + idx
        src_text = req.part2_src if (idx == 1 and req.part2_src) else ""
        new_seg = {
            "id": new_id,
            "start": p_st,
            "end": p_en,
            "src_text": src_text,
            "zh": src_text,
            "vi_text": parts_text[idx],
            "tts_text": normalize_for_tts(parts_text[idx]),
            "voice": orig_seg.get("voice") or (cfg.tts.default_male_voice if orig_seg.get("gender") == "male" else cfg.tts.default_female_voice),
            "speaker": orig_seg.get("speaker"),
            "gender": orig_seg.get("gender", "male" if orig_seg.get("voice") == cfg.tts.default_male_voice else "female"),
            "speed": orig_seg.get("speed", 1.0),
            "speech_time": round(p_en - p_st, 3),
            "dur": round(p_en - p_st, 3),
            "tts_file": None,
            "tts_dur": None,
            "fit": None,
            "flags": [],
        }
        new_segments.append(new_seg)

    for offset, ns in enumerate(new_segments):
        segments.insert(target_idx + 1 + offset, ns)

    data["segments"] = segments
    seg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "split", "part1": orig_seg, "part2": new_segments[0], "segments": [orig_seg] + new_segments}



@app.post("/api/jobs/{job_id}/segments/{seg_id}/tts")
def regenerate_segment_tts(job_id: str, seg_id: int, req: Optional[RegenTTSRequest] = None):
    """Regenerate TTS audio specifically for one segment with optional text, voice, and speed."""
    import hashlib
    from dubstudio.text.vi_normalize import normalize_for_tts

    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    seg_file = ws_dir / "segments.json"
    if not seg_file.exists():
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu segments")

    with _segments_lock:
        data = json.loads(seg_file.read_text(encoding="utf-8"))
        target_seg = None
        for s in data.get("segments", []):
            if s["id"] == seg_id:
                target_seg = s
                break

        if not target_seg:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đoạn thoại {seg_id}")

        if req and req.text and req.text.strip():
            target_seg["vi_text"] = req.text.strip()
            target_seg["tts_text"] = normalize_for_tts(req.text.strip())

        tts_text = (target_seg.get("tts_text") or target_seg.get("vi_text") or "").strip()
        if not tts_text:
            raise HTTPException(status_code=400, detail="Không có nội dung thoại để đọc")

        voice_choice = target_seg.get("voice") or (
            cfg.tts.default_male_voice if target_seg.get("gender") == "male" else cfg.tts.default_female_voice
        )
        speed_rate = 1.0

        if req:
            if req.voice:
                voice_choice = req.voice
                target_seg["voice"] = req.voice
            if req.speed:
                speed_rate = float(req.speed)
                target_seg["speed"] = speed_rate

        exp_hash = hashlib.md5(f"{tts_text}|{voice_choice}|{speed_rate:.2f}".encode("utf-8")).hexdigest()[:12]

    tts_dir = ws_dir / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    wav_path = tts_dir / f"{seg_id:04d}.wav"

    import soundfile as sf

    tts_payload = {
        "text": tts_text,
        "voice": voice_choice,
        "speed": float(speed_rate),
        "out": str(wav_path.resolve()),
    }

    # Protect warm worker communication with lock to serialize concurrent requests FIFO
    with _tts_worker_lock:
        used_warm_worker = False
        try:
            worker = get_tts_worker()
            worker.stdin.write(json.dumps(tts_payload, ensure_ascii=False) + "\n")
            worker.stdin.flush()
            resp = None
            for _ in range(40):
                resp_line = worker.stdout.readline()
                if not resp_line:
                    break
                resp_str = resp_line.strip()
                if not resp_str:
                    continue
                try:
                    resp = json.loads(resp_str)
                    break
                except Exception:
                    continue
            if resp and resp.get("status") == "ok":
                used_warm_worker = True
            else:
                err = resp.get("error") if resp else "Empty response"
                raise RuntimeError(f"Worker error: {err}")
        except Exception:
            # Fallback to single_tts subprocess (strictly serialized inside lock)
            from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs
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
                raise HTTPException(status_code=500, detail=f"Lỗi tạo TTS: {res.stderr.strip() or res.stdout.strip()}")

    info = sf.info(str(wav_path))
    dur = round(info.duration, 3)

    with _segments_lock:
        target_seg["tts_dur"] = dur
        target_seg["tts_file"] = f"tts/{seg_id:04d}.wav"
        target_seg["tts_hash"] = exp_hash
        seg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Automatically update voice track so video preview reflects new audio immediately
    _quick_rebuild_voice_track(job_id)

    return {
        "status": "regenerated",
        "tts_dur": dur,
        "tts_hash": exp_hash,
        "tts_file": f"tts/{seg_id:04d}.wav",
        "tts_text": tts_text,
        "voice": voice_choice,
        "speed": speed_rate,
        "audio_url": f"/media/workspace/{job_id}/tts/{seg_id:04d}.wav"
    }



@app.get("/api/jobs/{job_id}/preview-video")
def get_preview_video(job_id: str):
    """Serve the best available video file for preview (preview_dubbed > rendered > input.mp4 > source in meta)."""
    cfg = AppConfig.load()
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)

    # 0. Fast local preview with dubbed audio remuxed (if present)
    prev_dubbed = ws_dir / "preview_dubbed.mp4"
    if prev_dubbed.exists() and prev_dubbed.stat().st_size > 1024:
        return FileResponse(prev_dubbed, media_type="video/mp4")

    # 1. Output rendered video (ONLY for this exact job ID)
    out_rendered = cfg.general.out_dir / f"{job_id}_vi.mp4"
    if out_rendered.exists():
        return FileResponse(out_rendered, media_type="video/mp4")

    # 2. Workspace input.mp4 (the source video of this job)
    ws_input = ws_dir / "input.mp4"
    if ws_input.exists():
        return FileResponse(ws_input, media_type="video/mp4")

    # 3. Check meta.json for original source video path
    meta_file = ws_dir / "meta.json"
    if meta_file.exists():
        try:
            m = json.loads(meta_file.read_text(encoding="utf-8"))
            src = Path(m.get("video_path", ""))
            if src.exists():
                return FileResponse(src, media_type="video/mp4")
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Không tìm thấy tệp video để phát")


@app.get("/api/jobs/{job_id}/style")
def get_subtitle_style(job_id: str):
    """Get saved subtitle style for job."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    style_file = ws_dir / "style.json"
    style_data = {
        "font_name": "Arial",
        "font_size": 26,
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 2,
        "box_color": "rgba(0, 0, 0, 0.6)",
        "box_opacity": 0.6,
        "box_padding": 10,
        "box_radius": 6,
        "box_blur": 4,
        "box_mode": "full_width",
        "box_width": None,
        "box_height": None,
        "box_width_pct": 85.0,
        "pos_x": None,
        "pos_y": None,
        "text_align": "center",
        "margin_v": 35,
        "orig_bgm_volume": 0.80,
        "bgm_volume": 0.80,
        "custom_bgm_path": None,
        "custom_bgm_volume": 0.50,
        "include_orig_voice": False,
        "orig_voice_volume": 0.00,
        "vi_voice_volume": 1.00,
    }
    if style_file.exists():
        try:
            style_data.update(json.loads(style_file.read_text(encoding="utf-8")))
        except Exception:
            pass

    mix_file = ws_dir / "mix_settings.json"
    if mix_file.exists():
        try:
            mix_data = json.loads(mix_file.read_text(encoding="utf-8"))
            for k in (
                "orig_bgm_volume",
                "bgm_volume",
                "custom_bgm_path",
                "custom_bgm_volume",
                "include_orig_voice",
                "orig_voice_volume",
                "vi_voice_volume",
            ):
                if k in mix_data:
                    style_data[k] = mix_data[k]
        except Exception:
            pass

    return style_data


@app.post("/api/jobs/{job_id}/style")
def save_subtitle_style(job_id: str, req: SubtitleStyleRequest):
    """Save custom subtitle style and mix audio settings for job."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    ws_dir.mkdir(parents=True, exist_ok=True)
    style_file = ws_dir / "style.json"
    dumped = req.model_dump()
    style_file.write_text(json.dumps(dumped, ensure_ascii=False, indent=2), encoding="utf-8")

    # Persist mix settings (4 audio tracks)
    mix_file = ws_dir / "mix_settings.json"
    orig_bgm_vol = req.orig_bgm_volume if req.orig_bgm_volume is not None else (req.bgm_volume if req.bgm_volume is not None else 0.80)
    custom_bgm = req.custom_bgm_path if req.custom_bgm_path else None
    custom_bgm_vol = req.custom_bgm_volume if req.custom_bgm_volume is not None else 0.50
    include_orig = bool(req.include_orig_voice) if req.include_orig_voice is not None else False
    orig_vol = req.orig_voice_volume if req.orig_voice_volume is not None else 0.00
    vi_vol = req.vi_voice_volume if req.vi_voice_volume is not None else 1.00

    mix_file.write_text(
        json.dumps(
            {
                "orig_bgm_volume": orig_bgm_vol,
                "bgm_volume": orig_bgm_vol,
                "custom_bgm_path": custom_bgm,
                "custom_bgm_volume": custom_bgm_vol,
                "include_orig_voice": include_orig,
                "orig_voice_volume": orig_vol,
                "vi_voice_volume": vi_vol,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {"status": "saved", "style": dumped}


@app.post("/api/jobs/{job_id}/render")
def render_job_video(job_id: str):
    """Render final dubbed video with styled hard subtitles."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    if not ws_dir.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ")

    video_path = ws_dir / "input.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Không tìm thấy video gốc input.mp4")

    # Invalidate old render stage and mix stage in state.json so it always re-mixes & re-renders with new style/audio
    state_file = ws_dir / "state.json"
    if state_file.exists():
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
            if "stages" in state_data:
                state_data["stages"].pop("render", None)
                state_data["stages"].pop("mix", None)
                state_file.write_text(json.dumps(state_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs
    env = get_subprocess_env()
    py_exe = str(get_runtime_python().resolve())
    sub_kwargs = get_subprocess_kwargs()

    # 1. Ensure fit stage has run so fit_plan.json exists and is up to date
    fit_plan_file = ws_dir / "fit_plan.json"
    seg_file = ws_dir / "segments.json"
    need_fit = (not fit_plan_file.exists()) or (seg_file.exists() and seg_file.stat().st_mtime > fit_plan_file.stat().st_mtime)
    if need_fit:
        fit_cmd = [
            py_exe, "-m", "dubstudio", "stage", "fit",
            str(video_path.resolve()),
            "--job-id", job_id,
        ]
        fit_proc = subprocess.run(fit_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", **sub_kwargs)
        if fit_proc.returncode != 0:
            pass  # Fallback logic in mix.py will build basic fit_plan if fit subprocess had warnings

    # 2. Update audio track with latest mix settings if needed
    mix_cmd = [
        py_exe, "-m", "dubstudio", "stage", "mix",
        str(video_path.resolve()),
        "--job-id", job_id,
        "--force",
    ]
    mix_proc = subprocess.run(mix_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", **sub_kwargs)
    if mix_proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Lỗi hòa âm (mix): {mix_proc.stderr.strip() or mix_proc.stdout.strip()}")

    # 3. Render final video (force render so latest style & audio are always baked in)
    cmd = [
        py_exe, "-m", "dubstudio", "stage", "render",
        str(video_path.resolve()),
        "--job-id", job_id,
        "--force",
    ]
    proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", **sub_kwargs)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Lỗi xuất video: {proc.stderr.strip() or proc.stdout.strip()}")

    # Free all RAM & VRAM on render completion
    stop_tts_worker()

    out_video = cfg.general.out_dir / f"{job_id}_vi.mp4"
    return {
        "status": "rendered",
        "video_path": str(out_video.resolve()) if out_video.exists() else "",
        "filename": f"{job_id}_vi.mp4",
        "out_dir": str(cfg.general.out_dir.resolve()),
    }


@app.post("/api/jobs/{job_id}/config")
def save_job_config(job_id: str, req: JobConfigRequest):
    """Save translation style / tone and voice assignments for job."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    ws_dir.mkdir(parents=True, exist_ok=True)
    conf_file = ws_dir / "job_config.json"
    existing_data = {}
    if conf_file.exists():
        try:
            existing_data = json.loads(conf_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    req_data = {k: v for k, v in req.model_dump().items() if v is not None}
    existing_data.update(req_data)
    if existing_data.get("translation_tone") and not existing_data.get("style"):
        existing_data["style"] = existing_data["translation_tone"]
    elif existing_data.get("style") and not existing_data.get("translation_tone"):
        existing_data["translation_tone"] = existing_data["style"]
    conf_file.write_text(json.dumps(existing_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "saved", "config": existing_data}


VIENEU_VOICES = [
    {"name": "Minh Đức", "gender": "male", "region": "Bắc"},
    {"name": "Hải Đăng", "gender": "male", "region": "Nam"},
    {"name": "Quốc Tuấn", "gender": "male", "region": "Bắc"},
    {"name": "Quang Sơn", "gender": "male", "region": "Trung"},
    {"name": "Thiện Minh", "gender": "male", "region": "Bắc"},
    {"name": "Minh Triết", "gender": "male", "region": "Nam"},
    {"name": "Đức Trí", "gender": "male", "region": "Bắc"},
    {"name": "Thái Sơn", "gender": "male", "region": "Bắc"},
    {"name": "Xuân Vĩnh", "gender": "male", "region": "Bắc"},
    {"name": "Thanh Bình", "gender": "male", "region": "Trung"},
    {"name": "Phạm Tuyên", "gender": "male", "region": "Bắc"},
    {"name": "Thiền Tâm Đức", "gender": "male", "region": "Bắc"},
    {"name": "Adam", "gender": "male", "region": "Bắc"},
    {"name": "Adam bựa", "gender": "male", "region": "Bắc"},
    {"name": "Quỳnh Anh", "gender": "female", "region": "Bắc"},
    {"name": "Mai Anh", "gender": "female", "region": "Bắc"},
    {"name": "Trúc Ly", "gender": "female", "region": "Nam"},
    {"name": "Thùy Dung", "gender": "female", "region": "Bắc"},
    {"name": "Ngọc Huyền", "gender": "female", "region": "Bắc"},
    {"name": "Ngọc Trân", "gender": "female", "region": "Nam"},
    {"name": "Ngọc Linh", "gender": "female", "region": "Bắc"},
    {"name": "Đoan Trang", "gender": "female", "region": "Bắc"},
    {"name": "Thục Đoan", "gender": "female", "region": "Nam"},
    {"name": "Mỹ Duyên", "gender": "female", "region": "Nam"},
    {"name": "Kim Thanh", "gender": "female", "region": "Bắc"},
]


@app.api_route("/api/voices/preview", methods=["GET", "POST"])
def preview_voice_api(voice: str = "Minh Đức"):
    """Generate or retrieve a short 2s audio preview for any selected voice."""
    cfg = AppConfig.load()
    preview_dir = Path("out/voice_previews")
    preview_dir.mkdir(parents=True, exist_ok=True)
    wav_path = preview_dir / f"{voice}.wav"

    if not wav_path.exists():
        sample_text = f"Xin chào, tôi là giọng đọc {voice} của DubStudio."
        tts_payload = {
            "text": sample_text,
            "voice": voice,
            "speed": 1.0,
            "out": str(wav_path.resolve()),
        }
        try:
            worker = get_tts_worker()
            worker.stdin.write(json.dumps(tts_payload, ensure_ascii=False) + "\n")
            worker.stdin.flush()
            resp = None
            for _ in range(15):
                resp_line = worker.stdout.readline()
                if not resp_line:
                    break
                resp_str = resp_line.strip()
                if not resp_str:
                    continue
                try:
                    resp = json.loads(resp_str)
                    break
                except Exception:
                    continue
            if not resp or resp.get("status") != "ok":
                err = resp.get("error") if resp else "Empty response"
                raise RuntimeError(f"Worker error: {err}")
        except Exception:
            cmd = [
                sys.executable, "-m", "dubstudio.tts.single_tts",
                "--text", sample_text,
                "--voice", voice,
                "--speed", "1.0",
                "--out", str(wav_path.resolve()),
            ]
            subprocess.run(cmd, check=True)

    return FileResponse(wav_path, media_type="audio/wav")


@app.get("/api/settings")
def get_settings():
    """Get current configuration (API keys are masked for security)."""
    from dotenv import load_dotenv
    load_dotenv(override=True)

    cfg = AppConfig.load()
    raw_key = os.getenv("GEMINI_API_KEY", "") or cfg.gemini_api_key or ""
    masked_key = (raw_key[:6] + "..." + raw_key[-4:]) if len(raw_key) > 10 else ("*" * len(raw_key))

    backup_key = os.getenv("BACKUP_GEMINI_API_KEY", "") or cfg.backup_gemini_api_key or ""
    masked_backup_key = (backup_key[:6] + "..." + backup_key[-4:]) if len(backup_key) > 10 else ("*" * len(backup_key))

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "") or cfg.openrouter_api_key or ""
    masked_openrouter = (openrouter_key[:6] + "..." + openrouter_key[-4:]) if len(openrouter_key) > 10 else ("*" * len(openrouter_key))

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "") or getattr(cfg, "deepseek_api_key", "") or ""
    masked_deepseek = (deepseek_key[:6] + "..." + deepseek_key[-4:]) if len(deepseek_key) > 10 else ("*" * len(deepseek_key))

    male_voice = os.getenv("DEFAULT_MALE_VOICE", "") or cfg.tts.default_male_voice
    female_voice = os.getenv("DEFAULT_FEMALE_VOICE", "") or cfg.tts.default_female_voice
    trans_model = os.getenv("TRANSLATION_MODEL", "") or cfg.translation.model or "gemini_web"
    trans_provider = os.getenv("TRANSLATION_PROVIDER", "") or getattr(cfg.translation, "provider", "gemini_web")
    auto_fallback = getattr(cfg.translation, "auto_fallback", False)

    available_models = [
        "gemini_web",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.0-flash",
        "gemini-3.0-flash-lite",
    ]

    asr_model = os.getenv("WHISPER_MODEL", "") or os.getenv("ASR_MODEL", "") or cfg.asr.model_size or "large-v3"
    available_asr_models = [
        {"id": "large-v3", "name": "faster-whisper large-v3 (Chính xác cao nhất - Khuyên dùng)", "size": "3.09 GB"},
        {"id": "sensevoice-small", "name": "SenseVoice-Small (Siêu tốc độ - Siêu nhẹ, 12s/10p)", "size": "900 MB"},
    ]

    return {
        "gemini_api_key_masked": masked_key,
        "has_api_key": bool(raw_key),
        "backup_gemini_api_key_masked": masked_backup_key,
        "has_backup_api_key": bool(backup_key),
        "openrouter_api_key_masked": masked_openrouter,
        "has_openrouter_api_key": bool(openrouter_key),
        "deepseek_api_key_masked": masked_deepseek,
        "has_deepseek_api_key": bool(deepseek_key),
        "translation_provider": trans_provider,
        "translation_model": trans_model,
        "whisper_model": asr_model,
        "available_whisper_models": available_asr_models,
        "separation_model": os.getenv("SEPARATION_MODEL") or getattr(getattr(cfg, "separation", None), "model_name", "Kim_Vocal_2.onnx"),
        "auto_fallback": auto_fallback,
        "available_models": available_models,
        "default_male_voice": male_voice,
        "default_female_voice": female_voice,
        "available_voices": VIENEU_VOICES,
    }


@app.post("/api/settings")
def update_settings(req: SettingsRequest):
    """Save updated settings to .env file and environment."""
    from dotenv import load_dotenv

    env_file = Path(".env")
    lines = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    new_lines = []
    keys_updated = set()

    def _replace_or_keep(key: str, val: Optional[str], current_line: str) -> str:
        if current_line.startswith(f"{key}=") and val is not None:
            keys_updated.add(key)
            return f"{key}={val}"
        return current_line

    for line in lines:
        line = _replace_or_keep("GEMINI_API_KEY", req.gemini_api_key, line)
        line = _replace_or_keep("BACKUP_GEMINI_API_KEY", req.backup_gemini_api_key, line)
        line = _replace_or_keep("OPENROUTER_API_KEY", req.openrouter_api_key, line)
        line = _replace_or_keep("DEEPSEEK_API_KEY", req.deepseek_api_key, line)
        line = _replace_or_keep("TRANSLATION_PROVIDER", req.translation_provider, line)
        line = _replace_or_keep("TRANSLATION_MODEL", req.translation_model, line)
        line = _replace_or_keep("AUTO_FALLBACK_MODELS", "true" if req.auto_fallback else ("false" if req.auto_fallback is not None else None), line)
        line = _replace_or_keep("DEFAULT_MALE_VOICE", req.default_male_voice, line)
        line = _replace_or_keep("DEFAULT_FEMALE_VOICE", req.default_female_voice, line)
        line = _replace_or_keep("WHISPER_MODEL", req.whisper_model, line)
        line = _replace_or_keep("SEPARATION_MODEL", req.separation_model, line)
        new_lines.append(line)

    if req.separation_model is not None and "SEPARATION_MODEL" not in keys_updated:
        new_lines.append(f"SEPARATION_MODEL={req.separation_model}")
        os.environ["SEPARATION_MODEL"] = req.separation_model

    if req.gemini_api_key is not None and "GEMINI_API_KEY" not in keys_updated:
        new_lines.append(f"GEMINI_API_KEY={req.gemini_api_key}")
    if req.backup_gemini_api_key is not None and "BACKUP_GEMINI_API_KEY" not in keys_updated:
        new_lines.append(f"BACKUP_GEMINI_API_KEY={req.backup_gemini_api_key}")
    if req.openrouter_api_key is not None and "OPENROUTER_API_KEY" not in keys_updated:
        new_lines.append(f"OPENROUTER_API_KEY={req.openrouter_api_key}")
    if req.deepseek_api_key is not None and "DEEPSEEK_API_KEY" not in keys_updated:
        new_lines.append(f"DEEPSEEK_API_KEY={req.deepseek_api_key}")
    if req.translation_provider is not None and "TRANSLATION_PROVIDER" not in keys_updated:
        new_lines.append(f"TRANSLATION_PROVIDER={req.translation_provider}")
    if req.translation_model is not None and "TRANSLATION_MODEL" not in keys_updated:
        new_lines.append(f"TRANSLATION_MODEL={req.translation_model}")
    if req.auto_fallback is not None and "AUTO_FALLBACK_MODELS" not in keys_updated:
        new_lines.append(f"AUTO_FALLBACK_MODELS={'true' if req.auto_fallback else 'false'}")
    if req.default_male_voice is not None and "DEFAULT_MALE_VOICE" not in keys_updated:
        new_lines.append(f"DEFAULT_MALE_VOICE={req.default_male_voice}")
    if req.default_female_voice is not None and "DEFAULT_FEMALE_VOICE" not in keys_updated:
        new_lines.append(f"DEFAULT_FEMALE_VOICE={req.default_female_voice}")
    if req.whisper_model is not None and "WHISPER_MODEL" not in keys_updated:
        new_lines.append(f"WHISPER_MODEL={req.whisper_model}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # In-process update
    if req.gemini_api_key is not None:
        os.environ["GEMINI_API_KEY"] = req.gemini_api_key
    if req.backup_gemini_api_key is not None:
        os.environ["BACKUP_GEMINI_API_KEY"] = req.backup_gemini_api_key
    if req.openrouter_api_key is not None:
        os.environ["OPENROUTER_API_KEY"] = req.openrouter_api_key
    if req.deepseek_api_key is not None:
        os.environ["DEEPSEEK_API_KEY"] = req.deepseek_api_key
    if req.translation_provider is not None:
        os.environ["TRANSLATION_PROVIDER"] = req.translation_provider
    if req.translation_model is not None:
        os.environ["TRANSLATION_MODEL"] = req.translation_model
    if req.auto_fallback is not None:
        os.environ["AUTO_FALLBACK_MODELS"] = "true" if req.auto_fallback else "false"
    if req.default_male_voice is not None:
        os.environ["DEFAULT_MALE_VOICE"] = req.default_male_voice
    if req.default_female_voice is not None:
        os.environ["DEFAULT_FEMALE_VOICE"] = req.default_female_voice

    # Also update config/default.toml to persist defaults
    cfg_file = Path("config/default.toml")
    if cfg_file.exists():
        try:
            import re
            content = cfg_file.read_text(encoding="utf-8")
            if req.default_male_voice:
                content = re.sub(r'default_male_voice\s*=\s*".*?"', f'default_male_voice = "{req.default_male_voice}"', content)
            if req.default_female_voice:
                content = re.sub(r'default_female_voice\s*=\s*".*?"', f'default_female_voice = "{req.default_female_voice}"', content)
            if req.translation_provider:
                if 'provider = "' in content:
                    content = re.sub(r'provider\s*=\s*".*?"', f'provider = "{req.translation_provider}"', content)
                else:
                    content = re.sub(r'(\[translation\][^\n]*)', f'\\1\nprovider = "{req.translation_provider}"', content)
            if req.translation_model:
                content = re.sub(r'model\s*=\s*".*?"', f'model = "{req.translation_model}"', content)
            cfg_file.write_text(content, encoding="utf-8")
        except Exception:
            pass

    load_dotenv(override=True)

    return {"status": "saved"}


@app.post("/api/settings/test-key")
def test_gemini_key():
    """Verify Gemini API key."""
    cfg = AppConfig.load()
    key = cfg.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=400, detail="Chưa có API key")

    import httpx
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        res = httpx.get(url, timeout=10.0)
        if res.status_code == 200:
            return {"status": "ok", "message": "API key hợp lệ!"}
        return {"status": "error", "message": f"Mã lỗi từ Google: {res.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"Không thể kết nối đến Google: {e}"}


@app.post("/api/logs/clear")
def clear_logs_endpoint():
    """Clear all debug and stage logs to free disk space."""
    from dubstudio.logging_setup import clear_all_logs
    freed = clear_all_logs()
    return {"freed_bytes": freed, "freed_mb": round(freed / (1024 * 1024), 2)}


@app.post("/api/jobs/{job_id}/manual-translate")
def submit_manual_translation(job_id: str, req: dict):
    """Receive user manual translation text or cancellation for job."""
    from dubstudio.paths import resolve_job_workspace
    ws_dir = resolve_job_workspace(job_id)
    if not ws_dir.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy thư mục tác vụ")
    resp_file = ws_dir / "manual_translate_response.json"
    resp_file.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok"}


@app.post("/api/settings/open-browser-cdp")
def open_browser_cdp_endpoint():
    """Launch Chromium browser on port 9222 to connect with Gemini Web."""
    from dubstudio.llm.cdp_gemini import launch_browser_cdp, is_cdp_ready
    ready = launch_browser_cdp(9222)
    return {"status": "ok" if ready else "error", "ready": ready}


@app.get("/api/settings/cdp-status")
def cdp_status_endpoint():
    """Check if Chrome DevTools Protocol port 9222 is active."""
    from dubstudio.llm.cdp_gemini import is_cdp_ready
    return {"ready": is_cdp_ready(9222)}


@app.post("/api/tools/trim-video")
def trim_video_api(req: TrimVideoRequest):
    """Trim a video segment with sub-second accuracy."""
    from dubstudio.tools.trim_video import trim_video
    v_path = Path(req.video_path.strip())
    out_target = None
    if req.output_name:
        out_target = Path("out") / req.output_name
    try:
        res = trim_video(
            video_path=v_path,
            start_s=req.start_s,
            end_s=req.end_s,
            output_path=out_target,
            fast_copy=bool(req.fast_copy),
        )
        return {
            "status": "success",
            "file": res.name,
            "path": str(res.resolve()),
            "start_s": req.start_s,
            "end_s": req.end_s,
            "duration": round(req.end_s - req.start_s, 3),
        }
    except DubError as e:
        raise HTTPException(status_code=400, detail=e.user_message_vi)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tools/merge")
def merge_videos_api(req: MergeRequest):
    """Merge videos using merge_videos tool."""
    video_paths = [Path(v) for v in req.videos]
    out_path = Path("out") / req.output_name
    try:
        res = merge_videos(video_paths=video_paths, output_path=out_path, force_reencode=req.force_reencode)
        return {"status": "success", "merged_file": res.name, "path": str(res.resolve())}
    except DubError as e:
        raise HTTPException(status_code=400, detail=e.user_message_vi)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tools/edit-video")
def edit_video_api(req: EditVideoRequest):
    """Edit video with crop, color box overlay, and image watermark/overlay using ffmpeg."""
    import base64
    import subprocess
    from dubstudio.ffmpeg_utils import probe_file

    v_path = Path(req.video_path.strip())
    if not v_path.exists():
        for prefix in [Path("samples"), Path("out"), Path(".")]:
            cand = prefix / req.video_path.strip()
            if cand.exists():
                v_path = cand
                break

    if not v_path.exists():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tệp video: {req.video_path}")

    try:
        info = probe_file(v_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể đọc thông tin video: {e}")

    real_w, real_h = 1280, 720
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            real_w = int(s.get("width") or 1280)
            real_h = int(s.get("height") or 720)
            break

    pw = req.preview_width or real_w
    ph = req.preview_height or real_h
    scale_x = real_w / max(1.0, pw)
    scale_y = real_h / max(1.0, ph)

    filter_parts = []
    additional_inputs = []
    v_chain = "[0:v]"
    step_idx = 0
    cur_w, cur_h = real_w, real_h

    # 1. Crop (applied first on source video)
    cr = req.crop or req.crop_box
    if cr and cr.get("enabled", True):
        cx = max(0, int(round(float(cr.get("x", 0)) * scale_x)))
        cy = max(0, int(round(float(cr.get("y", 0)) * scale_y)))
        cw = min(real_w - cx, max(4, int(round(float(cr.get("w", cr.get("width", real_w))) * scale_x))))
        ch = min(real_h - cy, max(4, int(round(float(cr.get("h", cr.get("height", real_h))) * scale_y))))
        cw = cw - (cw % 2)
        ch = ch - (ch % 2)
        step_idx += 1
        next_chain = f"[v{step_idx}]"
        filter_parts.append(f"{v_chain}crop={cw}:{ch}:{cx}:{cy}{next_chain}")
        v_chain = next_chain
        cur_w, cur_h = cw, ch

    # 2. Aspect Ratio / Scale Pad (e.g. 9:16 Shorts/TikTok, 16:9, 1:1, 4:5...)
    if req.aspect_ratio and req.aspect_ratio.strip().lower() not in ("original", "gốc", "", "none"):
        r_parts = req.aspect_ratio.strip().split(":")
        if len(r_parts) == 2:
            try:
                rw = float(r_parts[0])
                rh = float(r_parts[1])
                target_ratio = rw / rh
                curr_ratio = cur_w / max(1.0, float(cur_h))
                if curr_ratio > target_ratio:
                    # Video is wider than target ratio -> pad top and bottom
                    pad_w = cur_w
                    pad_h = int(round(cur_w / target_ratio))
                else:
                    # Video is taller than target ratio -> pad left and right
                    pad_h = cur_h
                    pad_w = int(round(cur_h * target_ratio))

                pad_w += pad_w % 2
                pad_h += pad_h % 2
                c_color = (req.canvas_color or "000000").lstrip("#")
                step_idx += 1
                next_chain = f"[v{step_idx}]"
                filter_parts.append(f"{v_chain}pad={pad_w}:{pad_h}:(ow-iw)/2:(oh-ih)/2:color=0x{c_color}{next_chain}")
                v_chain = next_chain
                cur_w, cur_h = pad_w, pad_h
            except Exception:
                pass

    # 3. Multi color / text box overlays (rotatable with text)
    all_boxes = []
    if req.color_boxes:
        all_boxes.extend(req.color_boxes)
    if req.color_box and req.color_box not in all_boxes:
        all_boxes.append(req.color_box)

    active_boxes = [b for b in all_boxes if b.get("enabled", True)]
    if active_boxes:
        import uuid
        from PIL import Image, ImageDraw, ImageFont

        overlay_img = Image.new("RGBA", (cur_w, cur_h), (0, 0, 0, 0))

        def _get_pil_font(font_name: str, font_size: int):
            win_fonts = Path(r"C:\Windows\Fonts")
            candidates = [
                font_name,
                f"{font_name}.ttf",
                str(win_fonts / f"{font_name.lower()}.ttf"),
                str(win_fonts / f"{font_name}.ttf"),
                str(win_fonts / "arial.ttf"),
                str(win_fonts / "segoeui.ttf"),
            ]
            for c in candidates:
                try:
                    return ImageFont.truetype(c, size=font_size)
                except Exception:
                    continue
            return ImageFont.load_default()

        for cb in active_boxes:
            bx = max(0, int(round(float(cb.get("x", 0)) * scale_x)))
            by = max(0, int(round(float(cb.get("y", 0)) * scale_y)))
            bw = max(10, int(round(float(cb.get("w", cb.get("width", 50))) * scale_x)))
            bh = max(10, int(round(float(cb.get("h", cb.get("height", 50))) * scale_y)))
            color_hex = str(cb.get("color", "#000000")).lstrip("#")
            if len(color_hex) == 6:
                cr, cg, cb_val = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            else:
                cr, cg, cb_val = 0, 0, 0
            opacity = float(cb.get("opacity", 0.8))
            ca = max(0, min(255, int(round(opacity * 255))))
            rad = max(0, int(round(float(cb.get("radius", 8)) * scale_x)))
            rot = float(cb.get("rotation", 0.0) or 0.0)

            box_surf = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            b_draw = ImageDraw.Draw(box_surf)
            b_draw.rounded_rectangle([0, 0, bw, bh], radius=rad, fill=(cr, cg, cb_val, ca))

            b_text = str(cb.get("text", "") or "").strip()
            if b_text:
                f_name = cb.get("font_name", "Arial")
                f_size = max(8, int(round(float(cb.get("font_size", 24) or 24) * scale_x)))
                p_font = _get_pil_font(f_name, f_size)
                t_hex = str(cb.get("text_color", "#FFFFFF")).lstrip("#")
                tr, tg, tb = (int(t_hex[0:2], 16), int(t_hex[2:4], 16), int(t_hex[4:6], 16)) if len(t_hex) == 6 else (255, 255, 255)
                o_hex = str(cb.get("text_outline_color", "#000000")).lstrip("#")
                or_c, og, ob = (int(o_hex[0:2], 16), int(o_hex[2:4], 16), int(o_hex[4:6], 16)) if len(o_hex) == 6 else (0, 0, 0)
                o_w = max(0, int(round(float(cb.get("text_outline_width", 2) or 2) * scale_x)))

                b_draw.text(
                    (bw // 2, bh // 2),
                    b_text,
                    font=p_font,
                    fill=(tr, tg, tb, 255),
                    stroke_width=o_w,
                    stroke_fill=(or_c, og, ob, 255) if o_w > 0 else None,
                    anchor="mm",
                    align="center",
                )

            if rot != 0.0:
                rot_surf = box_surf.rotate(-rot, expand=True, resample=Image.Resampling.BICUBIC)
                rw, rh = rot_surf.size
                paste_x = bx + (bw - rw) // 2
                paste_y = by + (bh - rh) // 2
                overlay_img.paste(rot_surf, (paste_x, paste_y), rot_surf)
            else:
                overlay_img.paste(box_surf, (bx, by), box_surf)

        cache_dir = Path("workspace/.cache/edit")
        cache_dir.mkdir(parents=True, exist_ok=True)
        boxes_png = (cache_dir / f"boxes_{uuid.uuid4().hex[:8]}.png").resolve()
        overlay_img.save(str(boxes_png))

        additional_inputs.extend(["-i", str(boxes_png)])
        step_idx += 1
        input_idx = len(additional_inputs) // 2
        next_chain = f"[v{step_idx}]"
        filter_parts.append(f"{v_chain}[{input_idx}:v]overlay=0:0{next_chain}")
        v_chain = next_chain

    # 4. Image overlay (Watermark Logo)
    if req.image_overlay and req.image_overlay.get("enabled", True):
        io = req.image_overlay
        ix = max(0, int(round(float(io.get("x", 0)) * scale_x)))
        iy = max(0, int(round(float(io.get("y", 0)) * scale_y)))
        iw = max(4, int(round(float(io.get("w", io.get("width", 100))) * scale_x)))
        ih = max(4, int(round(float(io.get("h", io.get("height", 100))) * scale_y)))
        iw = iw if iw % 2 == 0 else iw + 1
        ih = ih if ih % 2 == 0 else ih + 1

        img_p = io.get("image_path")
        img_data = io.get("image_data", "")

        target_img_file = None
        if img_p and Path(img_p).exists():
            target_img_file = Path(img_p).resolve()
        elif img_data:
            cache_dir = Path("workspace/.cache/edit")
            cache_dir.mkdir(parents=True, exist_ok=True)
            temp_img = cache_dir / "overlay_temp.png"
            if "," in img_data:
                img_data = img_data.split(",", 1)[1]
            temp_img.write_bytes(base64.b64decode(img_data))
            target_img_file = temp_img.resolve()

        if target_img_file:
            additional_inputs.extend(["-i", str(target_img_file)])
            step_idx += 1
            input_idx = len(additional_inputs) // 2
            filter_parts.append(f"[{input_idx}:v]scale={iw}:{ih}[img_scaled]")
            next_chain = f"[v{step_idx}]"
            filter_parts.append(f"{v_chain}[img_scaled]overlay=x={ix}:y={iy}{next_chain}")
            v_chain = next_chain

    # 5. Vietnamese Subtitles burning (hard-sub from Tab Phụ đề)
    if req.subtitles_enabled:
        cand_ass = []
        if req.subtitles_path and Path(req.subtitles_path).exists():
            cand_ass.append(Path(req.subtitles_path))
        if req.job_id:
            cand_ass.append(Path("workspace") / req.job_id / "subtitles.ass")
            cand_ass.append(Path("out") / f"{req.job_id}_vi.ass")
        if v_path.parent.exists():
            cand_ass.append(v_path.parent / "subtitles.ass")
            cand_ass.append(v_path.parent.parent / "subtitles.ass")

        ass_file = None
        for p in cand_ass:
            if p.exists() and p.stat().st_size > 10:
                ass_file = p
                break

        jid = req.job_id
        if not jid:
            if v_path.parent.parent.name == "workspace":
                jid = v_path.parent.name
            elif v_path.parent.name == "out" and "_vi" in v_path.name:
                jid = v_path.stem.replace("_vi", "")

        if not ass_file and jid:
            seg_f = Path("workspace") / jid / "segments.json"
            if not seg_f.exists():
                seg_f = Path("workspace") / jid / "raw_segments.json"
            if seg_f.exists():
                try:
                    from dubstudio.subtitles.ass import generate_ass_subtitles
                    raw_segs = json.loads(seg_f.read_text(encoding="utf-8"))
                    segs = raw_segs.get("segments", []) if isinstance(raw_segs, dict) else raw_segs
                    sty_f = Path("workspace") / jid / "style.json"
                    sty = json.loads(sty_f.read_text(encoding="utf-8")) if sty_f.exists() else {}
                    gen_ass = Path("workspace") / jid / "subtitles.ass"
                    generate_ass_subtitles(segs, gen_ass, style=sty, video_width=cur_w, video_height=cur_h)
                    if gen_ass.exists():
                        ass_file = gen_ass
                except Exception as e:
                    logger.warning("Could not auto-generate subtitles for %s: %s", jid, e)

        if ass_file:
            temp_sub_dir = Path("workspace/.cache/edit")
            temp_sub_dir.mkdir(parents=True, exist_ok=True)
            temp_ass = temp_sub_dir / f"burn_{int(time.time())}.ass"
            temp_ass.write_text(ass_file.read_text(encoding="utf-8"), encoding="utf-8")
            escaped_ass = str(temp_ass.resolve()).replace("\\", "/").replace(":", r"\:")
            step_idx += 1
            next_chain = f"[v{step_idx}]"
            filter_parts.append(f"{v_chain}subtitles='{escaped_ass}'{next_chain}")
            v_chain = next_chain

    # Audio input mapping: preserve existing audio (contains full mix if preview_dubbed or exported vi.mp4)
    audio_map = ["-map", "0:a?"]
    jid = req.job_id or (v_path.parent.name if v_path.parent.parent.name == "workspace" else None)
    if not jid and v_path.parent.name == "out" and "_vi" in v_path.name:
        jid = v_path.stem.replace("_vi", "")

    if jid and v_path.name == "input.mp4":
        prev_dub = Path("workspace") / jid / "preview_dubbed.mp4"
        if prev_dub.exists() and prev_dub.stat().st_size > 1000:
            additional_inputs.extend(["-i", str(prev_dub.resolve())])
            dub_idx = len(additional_inputs) // 2
            audio_map = ["-map", f"{dub_idx}:a?"]

    out_name = req.output_name or "edited_video.mp4"
    if not out_name.endswith(".mp4"):
        out_name += ".mp4"
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / out_name

    cfg = AppConfig.load()
    encoders = [cfg.render.encoder, "h264_mf", cfg.render.fallback_encoder]
    encoders = list(dict.fromkeys(encoders))

    filter_args = ["-filter_complex", ";".join(filter_parts)] if filter_parts else []
    v_map = ["-map", v_chain] if filter_parts else ["-map", "0:v:0"]

    last_err = ""
    for enc in encoders:
        if enc == "h264_nvenc":
            enc_args = [
                "-c:v", "h264_nvenc",
                "-preset", "p7",
                "-tune", "hq",
                "-rc:v", "vbr",
                "-cq", "18",
                "-b:v", "0",
                "-maxrate", "35M",
                "-bufsize", "60M",
                "-spatial-aq", "1",
                "-temporal-aq", "1",
                "-pix_fmt", "yuv420p",
            ]
        elif enc == "h264_mf":
            enc_args = ["-c:v", "h264_mf", "-b:v", "18M", "-maxrate", "28M", "-bufsize", "36M", "-pix_fmt", "yuv420p"]
        else:
            enc_args = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p"]

        cmd = [
            "ffmpeg", "-y",
            "-i", str(v_path.resolve()),
            *additional_inputs,
            *filter_args,
            *v_map,
            *audio_map,
            "-c:a", "aac",
            "-b:a", "256k",
            *enc_args,
            str(out_file.resolve()),
        ]

        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        if p.returncode == 0:
            stop_tts_worker()
            return {
                "status": "success",
                "file": out_file.name,
                "path": str(out_file.resolve()),
                "url": f"/media/out/{out_file.name}?t={time.time()}",
            }
        last_err = p.stderr[-400:]

    raise HTTPException(status_code=500, detail=f"Lỗi khi xuất video: {last_err}")



# --- Mount static assets & media folders ---
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

workspace_dir = Path("workspace")
workspace_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/workspace", StaticFiles(directory=str(workspace_dir)), name="media_workspace")

out_dir = Path("out")
out_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/out", StaticFiles(directory=str(out_dir)), name="media_out")

samples_dir = Path("samples")
samples_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/samples", StaticFiles(directory=str(samples_dir)), name="media_samples")


@app.get("/")
def index():
    """Serve the single-page application."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"message": "DubStudio API Running. UI not loaded yet."})
