# AGENTS.md — dubstudio

Read this file at start of EVERY session. Then read PROGRESS.md. Do not read ROADMAP.md unless requested. Read nothing else unless needed.

## 1. Product

Local-first Windows desktop tool: Chinese video -> Vietnamese dubbed video (+ subtitles).
Pipeline: local video import -> audio extract -> vocal/BGM separation -> ASR (zh) -> context-aware translation (zh->vi) -> TTS (vi, local) -> fit -> mix -> render/export.

- Input: 8-15 min videos and <1 min shorts. Not feature films (do not over-engineer).
- Free and offline, except LLM translation (Edge CDP Gemini Web / cheap Gemini Flash & Groq API).
- Single non-expert user on a laptop. Simple, robust, debuggable solutions.
- UX reference: "CofiDub" (Tabs: Dubbing, Merge video, Translation account, Guide). Only accepts local video files.
- Clean-room implementation: never copy CofiDub code, assets, or voices.

## 2. Out of scope (do not implement)

- Downloading videos from Internet (yt-dlp, cookies) — local files only.
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
- R13. UI Icons: NEVER embed Unicode emojis in button labels, tabs, or UI text. Always use SVG vector icons. Button labels must be plain text.
- R14. Packaging & Releases: Release and packaging workflow:
  (1) Mandatory Tests & Notes: Run full `pytest tests/ -q` (100% pass required). Update `RELEASE_NOTES.md`. Never use vague commit messages like "Update source tree snapshot"; write explicit messages detailing core changes (e.g., `Release v2.0.1: Subtitle Burn Fix, Slider Sync`). Current release commit must head Section 3 of `RELEASE_AUDIT.md`.
  (2) Release Comparison Baseline (`tag < CURRENT_VERSION`): Always use previous official GitHub release as audit baseline and delta package source (e.g., `v2.0.1` compares against `v2.0.0`). When overwriting identical version, purge conflicting remote release/tag on GitHub before audit so Velopack downloads true previous baseline for accurate delta diffs.
  (3) Cloud CI/CD & Sync New Files Relative to Previous Release: Strictly adhere to SYNCHRONIZING ONLY NEW/MODIFIED FILES RELATIVE TO PREVIOUS RELEASE. Script `.venv\Scripts\python.exe scripts/push_code_to_github.py --tag vX.X.X` diffs local tree against previous GitHub release: uploads only modified/added blobs, reuses identical file SHAs for minimal transfer, and purges local-deleted files from git tree. GitHub Actions (`.github/workflows/build_release.yml`) builds, packages via Velopack (`vpk pack --noPortable`), and attaches release assets (`Setup.exe`, `full.nupkg`, `delta.nupkg`) in cloud. Never upload heavy binaries locally over WiFi.
  (4) Packaged Mode (`is_packaged() == True`): Must run standalone without dev `.venv`. Test user machine simulation via `scripts/sim_user_machine.ps1`. All background subprocesses must use `get_subprocess_env()` and `get_subprocess_kwargs()` (`CREATE_NO_WINDOW` / `SW_HIDE`).

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
  config.py, logging_setup.py, events.py, errors.py, jobstate.py, ffmpeg_utils.py, packaging.py, paths.py
  stages/        ingest, extract_audio, separate, asr, analyze, translate, tts, fit, mix, render
  tts/           base.py, vieneu.py, worker_server.py
  llm/           base.py, cdp_gemini.py, fit_rewrite.py, gemini.py, groq.py, prompts/
  subtitles/     ass.py, cue_split.py, sentence_align.py
  text/          vi_normalize.py
frontend/        React UI (dist/ embedded via pywebview, inline CSS bundle)
config/          default.toml, components.json
scripts/ tests/ models/ workspace/ samples/ out/ .venv/ .env
start_app.py     Entry point: DesktopAPIBridge + FastAPI background server + PyWebView
```
Rules: Stages are `run(job, cfg) -> None`. Type hints, pathlib, UTF-8 everywhere. Code/comments in English; user-facing strings/errors in Vietnamese.

## 6. Data contract

- `workspace/<job_id>/`: `state.json`, `input.mp4`, `audio/orig.wav`, `audio/bgm.wav`, `audio/vocals.wav`, `asr.json`, `analysis.json`, `segments.json`, `tts/`, `fit_plan.json`, `voice_track.wav`, `voice_raw.wav`, `mixed.wav`, `out/`.
- Timing constraints: `ALLOWABLE_OVERLAP = 0.25s`, `MAX_SILENCE_SHIFT = 0.25s`. Speedup range [1.0, 1.18x], neutral zone [0.95, 1.05]. Placement uses absolute source timestamps. Syllable-based fit rewrite (`tts_words`, `wps`, 1.04x compression).

## 7. Technology defaults

1. ASR (zh): FunASR `SenseVoice-Small` (merge_vad=False) as default; `faster-whisper large-v3-turbo` with VAD & `reconnect_dangling_asr_segments` fallback.
2. Separation: Demucs `htdemucs` / BS-RoFormer EP 317 (overlap=2).
3. TTS (vi): VieNeu-TTS-v3 Turbo, local ONNX/CUDA, warm persistent worker process.
4. Translation: Edge CDP Gemini Web automation (with refusal rescue & automatic tab closing) + Gemini Flash API / Groq fallback + manual prompt fallback.
5. Render: ffmpeg, `h264_nvenc` (fallback `libx264`). Subtitles as ASS via libass using Windows Native GDI font metrics (100% PyQt6-free).
6. GUI: PyWebView desktop application with React frontend, dark theme, inline CSS watchdog, and SVG vector icons.

## 8. Known Windows pitfalls

- cuBLAS/cuDNN DLLs: load via `os.add_dll_directory` before importing ctranslate2/torch.
- PyTorch must be CUDA build. Verify with `torch.cuda.is_available()`.
- Set `PYTHONUTF8=1`; open files with `encoding="utf-8"`. Relative paths for ffmpeg `subtitles=` filter.
- Whisper/ASR splitting: use `reconnect_dangling_asr_segments` to prevent cutting sentences mid-thought on VAD pause or commas.
- Edge CDP automation: port 9222, launch with `--disable-session-crashed-bubble`, close tabs via `/json/close/{id}` upon completion.
- Subtitle font measurement: use `ctypes.windll.gdi32` (Windows Native GDI); do NOT add PyQt6/Qt dependencies.
- Multiprocessing on PyInstaller: call `freeze_support()` at entry point before any logic.

## 9. Quality bar

- Unit tests on tiny fixtures (`pytest tests/test_x.py -q`). 100% pass before release.
- Audio/sync quality: test with <= 30 s samples in `out/review/`.
- Every user failure is a `DubError` with friendly Vietnamese message and actionable hint. No raw tracebacks.

## 10. Communication

- Talk to owner in Vietnamese, plain and short. Code stays English.
- Each reply: what changed (<= 5 lines); what owner must run/check; what is needed next.
