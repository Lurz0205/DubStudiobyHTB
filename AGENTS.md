# AGENTS.md — dubstudio

Read this file at the start of EVERY session. Then read PROGRESS.md. Do not read ROADMAP.md unless requested. Read nothing else unless needed.

## 1. Product

Personal, local-first Windows desktop tool: Chinese video -> Vietnamese dubbed video (+ Vietnamese subtitles).
Pipeline: local video import -> audio extraction -> vocal/BGM separation -> ASR (Chinese) -> context-aware translation (zh->vi) -> TTS (Vietnamese, local) -> audio-video fit -> mix -> render/export.

- Input: 8-15 min videos and <1 min shorts. Not feature films (do not over-engineer).
- Free and offline, except LLM translation (cheap Gemini / Groq API).
- Single non-expert user on a laptop. Simple, robust, debuggable solutions.
- UX reference: "CofiDub" (Tabs: Lồng tiếng, Ghép video, Tài khoản dịch, Hướng dẫn). Only accepts local video files.
- Clean-room implementation: never copy CofiDub code, assets, or voices.

## 2. Out of scope (do not implement)

- Downloading videos from the Internet (yt-dlp, cookies) — local files only.
- Copyright/duplicate bypass evasion features (random flip, clip trimming).
- Licensing, payments, user accounts, telemetry.
- Automating browser logins to Google/Gemini (API keys only).
- WSL, Docker, or paid services.

## 3. Execution rules (tiny weekly quota — obey strictly)

- R1. NEVER poll or sleep-loop on a running command or background task.
- R2. Command limits:
  (a) One blocking call per command. Never poll or sleep-check.
  (b) Use `.venv\Scripts\python.exe` directly. For long output, redirect to `logs/<name>.log` and show last 20 lines. Use `pip install --progress-bar off`.
  (c) Downloads >500 MB or commands >10 min: print exact command and STOP; owner runs it and replies "done".
  (d) If a command times out or fails, do not retry in a loop (R7). Report and stop.
- R3. No exploratory commands or directory listings unless truly needed. Layout is fixed in Section 5.
- R4. Read only files you must edit. Never re-read a file just written. Never print large files.
- R5. Before multi-file tasks: list files to create/change (one line each) + acceptance check, then WAIT for "OK". Single-file fixes: just do them.
- R6. Dev loops use tiny inputs (`samples/tiny.mp4`, 10 s). Use longer clips only when required.
- R7. Errors: read once, make at most 2 fix attempts, then stop and report cause + hypothesis in <= 5 lines.
- R8. Summaries <= 15 lines. No long reports. Do not recap diffs.
- R9. Ask before adding dependencies (name, reason, size). Prefer existing packages.
- R10. Safety: never run destructive commands outside files created this session. Never touch outside project root. Never log, commit, or echo API keys (.env is gitignored).
- R11. After each working milestone: update PROGRESS.md (<= 30 lines: done / next / open issues).
- R12. Strictly stick to assigned tasks. Do not expand scope.
- R13. UI Icons: NEVER embed Unicode emojis in button labels, tabs, or text. Always use SVG vector icons via `ui/icons.py` (`btn.setIcon(get_icon(name, color))` or `set_button_icon(btn, name, text)`). Button labels must be plain text.
- R14. Packaging & Releases: Quy trình đóng gói và phát hành:
  (1) Sau khi sửa code và kiểm thử xong (`pytest tests/ -q`), dùng `scripts/push_code_to_github.py` để đẩy mã nguồn lên GitHub `main`.
  (2) GitHub Actions (`.github/workflows/build_release.yml`) trên Azure tự động build, package bằng Velopack (`vpk pack --noPortable`), và gắn release (`Setup.exe`, `full.nupkg`, `delta.nupkg`) trực tiếp trên mây. Tuyệt đối không upload file nặng từ máy local qua WiFi chập chờn.
  (3) Packaged mode (`is_packaged() == True`) phải độc lập, không tham chiếu dev `.venv`. Kiểm thử máy người dùng bằng `scripts/sim_user_machine.ps1`. Mọi subprocess chạy ngầm phải dùng `get_subprocess_env()` và `get_subprocess_kwargs()` (`CREATE_NO_WINDOW` / `SW_HIDE`).
  (4) Khóa mốc so sánh Release: Luôn lấy mốc so sánh (audit & delta package) từ bản release chính thức trước đó trên GitHub (`tag_version < CURRENT_VERSION`, ví dụ 1.1.2 khi phát hành 1.1.3), tuyệt đối không so với các bản debug cùng phiên bản. Phải xóa sạch tag/release trùng phiên bản trên GitHub trước khi tải delta để đảm bảo Velopack cắt delta chuẩn 100%.

## 4. Environment (fixed facts)

- Windows 11 Home, PowerShell. Laptop: Intel i5-12450HX, 12 GB RAM, NVIDIA RTX 2050 (4 GB VRAM) + Intel UHD.
- Python 3.11 ONLY: `.venv\Scripts\python.exe`. Never use Python 3.12/3.14.
- ffmpeg installed on PATH with `h264_nvenc` support. Project root = repository root. Package: `dubstudio/`.
- No WSL, no Docker. Support spaces and Vietnamese diacritics in paths.

## 5. Resource budget and architecture

Budget:
- At most ONE heavy model loaded at a time. Run heavy stages (ASR, separation, TTS) in isolated subprocesses so RAM/VRAM is freed on exit.
- VRAM (4 GB): Keep ~0.5 GB for OS. Use int8/fp16 and chunking. Catch CUDA OOM, fallback gracefully, and log.
- RAM (~8 GB usable): Stream media in chunks. Never load full video into memory.

Layout:
```
dubstudio/
  config.py, logging_setup.py, events.py, errors.py, jobstate.py, ffmpeg_utils.py, packaging.py
  stages/        ingest, extract_audio, separate, asr, analyze, translate, tts, fit, mix, render
  tts/           base.py, vieneu.py, worker_server.py
  llm/           base.py, gemini.py, groq.py, prompts/
  subtitles/     ass.py, cue_split.py, sentence_align.py
ui/              app.py, main_window.py, icons.py, pages/, widgets/, dialogs/
config/          default.toml, components.json
scripts/ tests/ models/ workspace/ samples/ out/ .venv/ .env
```
Rules: Stages are `run(job, cfg) -> None`. Type hints, pathlib, UTF-8 everywhere. Code/comments in English; user-facing strings/errors in Vietnamese.

## 6. Data contract

- `workspace/<job_id>/`: `state.json`, `audio/`, `asr.json`, `analysis.json`, `segments.json`, `tts/`, `fit_plan.json`, `voice_track.wav`, `out/`.
- Timing constraints: allowable overlap = 0.10s, speedup [1.0, 1.1x], neutral [0.95, 1.05]. Placement uses absolute source timestamps. Multi-pass rewrite loop for overlaps > 0.10s.

## 7. Technology defaults

1. ASR (zh): faster-whisper `large-v3-turbo`, int8_float16 with VAD.
2. Separation: Demucs `htdemucs` / BS-RoFormer EP 317 (overlap=2).
3. TTS (vi): VieNeu-TTS-v3 Turbo, local ONNX/CUDA, warm persistent worker process.
4. Translation: Groq (Qwen/Llama) + Gemini Flash fallback. Rate-limited, cached by prompt hash.
5. Render: ffmpeg, `h264_nvenc` (fallback `libx264`). Subtitles as ASS via libass.
6. GUI: PyQt6 desktop application with dark theme and vector SVG icons.

## 8. Known Windows pitfalls

- cuBLAS/cuDNN DLLs: load via `os.add_dll_directory` before importing ctranslate2/torch.
- PyTorch must be the CUDA build. Verify with `torch.cuda.is_available()`.
- Set `PYTHONUTF8=1`; open files with `encoding="utf-8"`. Relative paths for ffmpeg `subtitles=` filter.
- Whisper silence hallucination: VAD + no_speech thresholds; drop duplicate phrases.
- Multiprocessing on PyInstaller: always call `freeze_support()` at entry point before any logic.

## 9. Quality bar

- Unit tests on tiny fixtures (`pytest tests/test_x.py -q`). 100% pass before release.
- Audio/sync quality: test with <= 30 s samples in `out/review/`.
- Every user failure is a `DubError` with friendly Vietnamese message and actionable hint. No raw tracebacks.

## 10. Communication

- Talk to the owner in Vietnamese, plain and short. Code stays English.
- Each reply: what changed (<= 5 lines); what owner must run/check; what is needed next.
