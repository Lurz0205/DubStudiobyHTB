import hashlib
import os
from pathlib import Path
import sys
from typing import List, Optional
import typer
from rich.console import Console

# Windows UTF-8 console output setup (AGENTS.md Section 8)
os.environ["PYTHONUTF8"] = "1"
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.jobstate import JobContext
from dubstudio.stages import analyze, asr, extract_audio, fit, ingest, mix, render, separate, translate, tts, units, voice_assign

app = typer.Typer(help="dubstudio: Chuyển đổi và lồng tiếng video Trung - Việt")
console = Console(legacy_windows=False)


def get_job_id_for_file(file_path: Path) -> str:
    """Derive deterministic job ID based on stem and path hash."""
    clean_stem = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in file_path.stem)
    path_hash = hashlib.md5(str(file_path.resolve()).encode("utf-8")).hexdigest()[:6]
    return f"{clean_stem}_{path_hash}"


def _run_stage_subprocess(stage_name: str, video_path: Path, job_id: str):
    """Run heavy AI model stages (Demucs, ASR, TTS) in isolated subprocesses to free VRAM/RAM on exit."""
    import subprocess
    import time
    from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs
    from dubstudio.paths import get_logs_dir
    from dubstudio.errors import DubError

    stage_log_dir = get_logs_dir() / "stages"
    stage_log_dir.mkdir(parents=True, exist_ok=True)
    stage_log_file = stage_log_dir / f"{stage_name}_{job_id}.log"

    cmd = [
        str(get_runtime_python().resolve()), "-m", "dubstudio", "stage", stage_name,
        str(video_path.resolve()),
        "--job-id", job_id,
    ]
    env = get_subprocess_env()

    output_lines: list[str] = []
    with open(stage_log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n==================== [STAGE START: {stage_name}] {time.strftime('%Y-%m-%d %H:%M:%S')} ====================\n")
        lf.write(f"Command: {' '.join(cmd)}\n")
        lf.flush()

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

        for line in proc.stdout:
            try:
                sys.stdout.write(line)
                sys.stdout.flush()
            except Exception:
                pass
            lf.write(line)
            lf.flush()
            line_str = line.strip()
            if line_str:
                output_lines.append(line_str)

        proc.wait()
        lf.write(f"==================== [STAGE END: exit code {proc.returncode}] ====================\n")

    if proc.returncode != 0:
        err_msg = ""
        # Search backwards for actionable error messages
        for l in reversed(output_lines):
            if any(k in l for k in ("❌", "DubError", "Error:", "Exception:", "Lỗi")):
                err_msg = l
                break
        if not err_msg and output_lines:
            err_msg = output_lines[-1]
        raise DubError(
            code="STAGE_FAILED",
            message_vi=f"Giai đoạn '{stage_name}' thất bại (Mã thoát {proc.returncode}): {err_msg}",
            hint_vi=f"Xem nhật ký chi tiết tại: {stage_log_file.resolve()}",
        )


@app.command("selftest")
def selftest(
    json_output: bool = typer.Option(False, "--json", help="Xuất kết quả định dạng JSON"),
):
    """Tự kiểm tra toàn diện hệ thống: Python, FFmpeg, FFprobe, GPU, thư mục dữ liệu."""
    import json
    import subprocess
    from dubstudio.paths import (
        is_packaged, get_app_dir, get_user_base_dir, get_models_dir,
        get_workspace_dir, get_logs_dir, get_bin_dir, resolve_tool
    )

    results = {
        "status": "ok",
        "packaged": is_packaged(),
        "python": str(sys.executable),
        "app_dir": str(get_app_dir()),
        "user_base_dir": str(get_user_base_dir()),
        "models_dir": str(get_models_dir()),
        "workspace_dir": str(get_workspace_dir()),
        "logs_dir": str(get_logs_dir()),
        "bin_dir": str(get_bin_dir()),
        "ffmpeg": None,
        "ffprobe": None,
        "cuda_available": False,
        "errors": [],
    }

    # 1. Test FFmpeg
    try:
        ffmpeg_bin = resolve_tool("ffmpeg")
        proc = subprocess.run([str(ffmpeg_bin), "-version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            first_line = proc.stdout.splitlines()[0] if proc.stdout else ""
            results["ffmpeg"] = {"path": str(ffmpeg_bin), "version": first_line}
        else:
            results["status"] = "error"
            results["errors"].append(f"ffmpeg exit code {proc.returncode}")
    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"ffmpeg không khả dụng: {e}")

    # 2. Test FFprobe
    try:
        ffprobe_bin = resolve_tool("ffprobe")
        proc = subprocess.run([str(ffprobe_bin), "-version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            first_line = proc.stdout.splitlines()[0] if proc.stdout else ""
            results["ffprobe"] = {"path": str(ffprobe_bin), "version": first_line}
        else:
            results["status"] = "error"
            results["errors"].append(f"ffprobe exit code {proc.returncode}")
    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"ffprobe không khả dụng: {e}")

    # 3. Test CUDA
    try:
        import torch
        results["cuda_available"] = bool(torch.cuda.is_available())
        if results["cuda_available"]:
            results["gpu_name"] = torch.cuda.get_device_name(0)
    except Exception:
        results["cuda_available"] = False

    if json_output:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        status_color = "green" if results["status"] == "ok" else "red"
        console.print(f"[bold {status_color}]DubStudio Selftest: {results['status'].upper()}[/bold {status_color}]")
        console.print(f"  • Chế độ: {'Packaged' if results['packaged'] else 'Dev/Repo'}")
        console.print(f"  • Python: {results['python']}")
        console.print(f"  • FFmpeg: {results['ffmpeg']}")
        console.print(f"  • FFprobe: {results['ffprobe']}")
        console.print(f"  • CUDA/GPU: {results.get('gpu_name', 'Không tìm thấy / CPU')}")
        console.print(f"  • Logs: {results['logs_dir']}")
        if results["errors"]:
            console.print(f"[bold red]Lỗi phát hiện:[/bold red]")
            for err in results["errors"]:
                console.print(f"  ❌ {err}")

    if results["status"] != "ok":
        raise typer.Exit(code=1)


@app.command()
def doctor():
    """Kiểm tra môi trường hoạt động của dubstudio."""
    from scripts.check_env import main as run_check
    run_check()


@app.command()
def stage(
    stage_name: str = typer.Argument(..., help="Tên stage cần chạy"),
    video_path: Path = typer.Argument(..., help="Đường dẫn tới tệp video nguồn"),
    job_id: Optional[str] = typer.Option(None, "--job-id", "-j", help="Mã định danh job tùy chọn"),
    force: bool = typer.Option(False, "--force", "-f", help="Bắt buộc chạy lại stage mà không dùng cache"),
):
    """Chạy đơn lẻ một giai đoạn trong quy trình."""
    if not video_path.exists():
        console.print(f"[bold red]❌ Tệp không tồn tại:[/bold red] {video_path}")
        raise typer.Exit(code=1)

    cfg = AppConfig.load()
    if not job_id:
        job_id = get_job_id_for_file(video_path)
    from dubstudio.paths import resolve_job_workspace
    workspace_path = resolve_job_workspace(job_id)
    job = JobContext(workspace_path=workspace_path, job_id=job_id, input_path=video_path)

    try:
        orig_wav = job.workspace / "audio" / "orig.wav"
        vocals_wav = job.workspace / "audio" / "vocals.wav"

        if stage_name == "ingest":
            ingest.run(job, cfg, video_path)
        elif stage_name == "extract_audio":
            extract_audio.run(job, cfg, video_path)
        elif stage_name == "separate":
            separate.run(job, cfg, orig_wav)
        elif stage_name == "asr":
            asr_input = vocals_wav if vocals_wav.exists() else orig_wav
            asr.run(job, cfg, asr_input)
        elif stage_name == "units":
            units.run(job, cfg)
        elif stage_name == "analyze":
            analyze.run(job, cfg)
        elif stage_name == "voice_assign":
            voice_assign.run(job, cfg)
        elif stage_name == "translate":
            translate.run(job, cfg)
        elif stage_name == "tts":
            tts.run(job, cfg)
        elif stage_name == "fit":
            fit.run(job, cfg)
        elif stage_name == "mix":
            mix.run(job, cfg, force=force)
        elif stage_name == "render":
            render.run(job, cfg, video_path, force=force)
        else:
            console.print(f"[bold red]Stage '{stage_name}' không hợp lệ.[/bold red]")
            raise typer.Exit(code=1)
    except DubError as e:
        console.print(f"[bold red]{e.format_user()}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Lỗi không xác định:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def run(
    video_path: Path = typer.Argument(..., help="Đường dẫn tới video cần xử lý"),
    job_id: Optional[str] = typer.Option(None, "--job-id", "-j", help="Mã định danh job tùy chọn"),
    skip_separate: bool = typer.Option(False, "--no-separate", help="Bỏ qua bước tách nhạc nền (chạy nhanh hơn)"),
    no_render: bool = typer.Option(False, "--no-render", help="Dừng lại sau bước mix âm thanh, không khắc phụ đề vào video"),
    subtitles_only: bool = typer.Option(False, "--subtitles-only", help="Chỉ tạo phụ đề và dịch thuật (dừng trước khi lồng tiếng)"),
    dub_only: bool = typer.Option(False, "--dub-only", help="Chỉ tạo giọng lồng tiếng từ bảng phụ đề hiện có (TTS -> Fit -> Mix)"),
):
    """Chạy toàn bộ hoặc từng phần quy trình lồng tiếng cho video."""
    if not video_path.exists():
        console.print(f"[bold red]❌ Tệp không tồn tại:[/bold red] {video_path}")
        raise typer.Exit(code=1)

    cfg = AppConfig.load()
    if not job_id:
        job_id = get_job_id_for_file(video_path)
    from dubstudio.paths import resolve_job_workspace
    workspace_path = resolve_job_workspace(job_id)
    job = JobContext(workspace_path=workspace_path, job_id=job_id, input_path=video_path)

    console.print(f"[bold cyan]🚀 Bắt đầu xử lý:[/bold cyan] {video_path.name} (Job: {job_id})")

    try:
        if not dub_only:
            # 1. Ingest
            ingest.run(job, cfg, video_path)

            # 2. Extract audio
            extract_audio.run(job, cfg, video_path)
            orig_wav = job.workspace / "audio" / "orig.wav"

            # 3. Separation (Vocals / BGM) - Heavy GPU stage
            if not skip_separate:
                _run_stage_subprocess("separate", video_path, job_id)
            asr_input = orig_wav

            # 4. ASR (faster-whisper) - Heavy GPU stage
            _run_stage_subprocess("asr", video_path, job_id)

            # 5. Units (Build dubbing units)
            units.run(job, cfg)

            # 6. Analyze (Context, characters, glossary)
            analyze.run(job, cfg)

            # 7. Translate (Gemini - context translation & contextual gender tagging)
            translate.run(job, cfg)

            # 8. Voice Assign (Assign voices based on contextual gender & settings)
            voice_assign.run(job, cfg)

            if subtitles_only:
                try:
                    from dubstudio.llm.cdp_gemini import close_gemini_tabs
                    close_gemini_tabs(getattr(cfg.translation, "cdp_port", 9222))
                except Exception:
                    pass
                console.print(f"\n[bold green]🎉 Tạo và dịch phụ đề hoàn tất! Bạn có thể kiểm tra, tìm kiếm/thay thế trên bảng trước khi bấm tạo giọng lồng tiếng.[/bold green]")
                return
        # In dub-only mode, we directly preserve the exact segment voices edited by the user on the table.
        if dub_only:
            seg_file = job.workspace / "segments.json"
            if not seg_file.exists():
                raise DubError(
                    "FILE_NOT_FOUND",
                    "Chưa có tệp dữ liệu phụ đề segments.json để tạo lồng tiếng.",
                    hint="Vui lòng chạy bước '1. Tạo phụ đề' trước khi tạo lồng tiếng.",
                )

        # 9. TTS (VieNeu-TTS) - Heavy GPU stage
        _run_stage_subprocess("tts", video_path, job_id)

        # 10. Fit
        fit.run(job, cfg)

        # 11. Mix
        mix.run(job, cfg)

        try:
            from dubstudio.llm.cdp_gemini import close_gemini_tabs
            close_gemini_tabs(getattr(cfg.translation, "cdp_port", 9222))
        except Exception:
            pass

        # 12. Render (chỉ chạy nếu không có cờ --no-render)
        if not no_render:
            render.run(job, cfg, video_path)
            out_name = video_path.stem
            console.print(f"\n[bold green]🎉 Hoàn tất thành công![/bold green]")
            console.print(f"👉 Video: [yellow]out/{out_name}_vi.mp4[/yellow]")
            console.print(f"👉 Phụ đề: [yellow]out/{out_name}_vi.srt[/yellow]")
        else:
            console.print(f"\n[bold green]🎉 Tạo giọng lồng tiếng hoàn tất (chưa khắc phụ đề)![/bold green]")


    except DubError as e:
        console.print(f"[bold red]{e.format_user()}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Lỗi ngoài dự kiến:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("merge")
def merge_cmd(
    videos: List[Path] = typer.Argument(..., help="Danh sách các video cần ghép (ít nhất 2 tệp)"),
    output: Path = typer.Option(Path("out/merged.mp4"), "--out", "-o", help="Đường dẫn video kết quả"),
    reencode: bool = typer.Option(False, "--reencode", help="Bắt buộc mã hóa lại toàn bộ thay vì ghép nhanh (stream copy)"),
):
    """Ghép nối nhiều tệp video thành một video duy nhất."""
    from dubstudio.tools.merge import merge_videos
    try:
        res = merge_videos(video_paths=videos, output_path=output, force_reencode=reencode)
        console.print(f"[bold green]🎉 Ghép video thành công:[/bold green] [yellow]{res}[/yellow]")
    except DubError as e:
        console.print(f"[bold red]{e.format_user()}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Lỗi ngoài dự kiến:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("ui")
def ui_cmd(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Địa chỉ host máy chủ"),
    port: int = typer.Option(8000, "--port", "-p", help="Cổng chạy máy chủ"),
    no_open: bool = typer.Option(False, "--no-open", help="Không tự động mở trình duyệt"),
):
    """Khởi chạy giao diện web DubStudio trên trình duyệt."""
    import threading
    import time
    import webbrowser
    import uvicorn

    url = f"http://{host}:{port}"
    console.print(f"[bold green]🚀 Đang khởi chạy giao diện DubStudio tại:[/bold green] [yellow]{url}[/yellow]")

    if not no_open:
        def open_browser():
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    from dubstudio.api.app import app as fastapi_app
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


def main():
    app()


if __name__ == "__main__":
    main()


