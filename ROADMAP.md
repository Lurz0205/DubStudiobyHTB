# ROADMAP.md — dubstudio

Rules: obey AGENTS.md. Read ONLY the section of the current phase. At the start of a phase: list files you will touch + acceptance check, wait for "OK" (R5). Heavy commands are run by the owner (R2). Finish a phase by committing, updating PROGRESS.md, and stopping (R12).
Owner clips: samples/clip_1min.mp4 and samples/clip_10min.mp4 (real Chinese speech). samples/tiny.mp4 (10 s) is for dev loops.

## PHASE 0 — Bootstrap

Goal: a clean, reproducible environment and an empty but well-organized skeleton.
Agent tasks (no installs, no downloads):
- Create the layout from AGENTS.md section 5 (empty modules with one-line docstrings only), .gitignore (models/ workspace/ samples/ out/ .venv/ .env __pycache__/), .env.example (GEMINI_API_KEY=), config/default.toml (placeholders), PROGRESS.md, DECISIONS.md, short Vietnamese README.md (setup steps).
- requirements.txt with ONLY light packages: typer, pydantic, pydantic-settings, rich, pytest, psutil, nvidia-ml-py, numpy, soundfile, python-dotenv, httpx, tqdm. Heavy packages are added in the phase that needs them (R9).
- scripts/check_env.py: prints Python version (must be 3.11), torch version + torch.cuda.is_available() + GPU name, ffmpeg version, h264_nvenc availability, nvidia-smi summary, free disk space (warn if < 15 GB), RAM total/free. One-line OK/FAIL per item.
- scripts/make_tiny_clip.ps1: cuts a 10 s clip from a given input into samples/tiny.mp4.
Then print these commands for the owner (R2):
1. `py -3.11 -m venv .venv` and `.venv\Scripts\Activate.ps1`
2. Install PyTorch CUDA build: command copied from pytorch.org selector (Pip, Windows, CUDA), with `--default-timeout=120 --retries 10`.
3. `pip install -r requirements.txt`
4. `python scripts/check_env.py`
Acceptance: check_env shows Python 3.11, torch CUDA True with "RTX 2050", ffmpeg OK, NVENC OK (or a clear note), disk >= 15 GB. Owner pastes the output; agent fixes only what failed.

## PHASE 1 — Core library (no AI models yet)

Goal: the plumbing every stage will use.
- config.py (+ default.toml, per-job overrides), logging_setup.py, events.py, errors.py (DubError with Vietnamese messages), jobstate.py (hash-based resume), ffmpeg_utils.py (probe, extract_audio, cut, safe path handling), models/manager.py (resumable download, progress events, size check), cli.py with `doctor`, `run`, `stage`.
- Stages `ingest` (copy/link input into the job workspace, probe it) and `extract_audio` (16 kHz mono wav).
- Tests: jobstate resume/skip, DubError formatting, ffmpeg_utils on samples/tiny.mp4, path with spaces and Vietnamese characters.
Acceptance: `pytest tests -q` passes; `python -m dubstudio stage extract_audio samples/tiny.mp4` creates workspace/<job>/state.json and audio/orig.wav; running it again prints "skipped (up to date)".

## PHASE 2 — Benchmarks and decisions

Goal: choose models with numbers from THIS laptop. Agent writes scripts (ask before installing deps, R9); the owner runs them (R2).
- scripts/hwprofile.py: samples GPU memory with pynvml every 0.5 s plus RAM with psutil, because torch.cuda.max_memory_allocated misses CTranslate2, ONNX Runtime and NVENC.
- bench_asr.py: faster-whisper large-v3-turbo (int8_float16) vs SenseVoice on clip_1min and clip_10min -> SRT. Print first 10 lines of each transcript.
- bench_separate.py: Demucs htdemucs chunked on clip_1min (and 10 min).
- bench_tts.py: VieNeu-TTS-v2, the same 5 Vietnamese sentences with ALL preset voices -> out/tts/<voice>_<n>.wav; per-sentence generation time; CPU, and GPU if supported. Print the voice list (gender/accent). Also measure characters-per-second per voice (needed later for length budgets).
- bench_render.py: h264_nvenc vs libx264 on clip_1min.
- Every script ends with one compact table: tool | clip length | wall time | peak RAM | peak VRAM.
Acceptance: bench/RESULTS.md with the tables. Owner listens to the voices and reports favorites. Agent records in DECISIONS.md: ASR choice, separation choice, default male/female voices, chars-per-second per voice.

## PHASE 3 — End-to-end MVP

Goal: one command turns a Chinese video into a Vietnamese dubbed video.
Stages: ingest -> extract_audio -> separate (flag) -> asr -> translate (basic prompt) -> tts -> fit (simple: place at segment start, speed up <= 1.2x, else let it run into the following gap) -> mix (voice over BGM; if no separation, lower original audio heavily and warn that Chinese speech remains) -> render. Outputs: out/<name>_vi.mp4 and out/<name>_vi.srt.
- CLI: `python -m dubstudio run samples\clip_1min.mp4`.
- Each heavy stage in its own subprocess; psutil logs peak RAM per stage.
Acceptance: clip_1min completes; SRT timestamps within 0.3 s of ASR; no audio clipping; then clip_10min completes with peak RAM < 9 GB and VRAM < 3.6 GB; kill the process mid-run and rerun => resumes from the unfinished stage. Owner gives a listening verdict.

## PHASE 4 — Translation quality & Dubbing Units

Goal: natural Vietnamese with consistent names, pronouns (xưng hô) and speakable text.
- `units` stage (runs after asr, before translate):
  - Xây "đơn vị lồng tiếng" bằng cách gộp 2–3 segment kề nhau khi: khoảng nghỉ giữa chúng <= 0.6 s, cùng người nói (hoặc chưa biết), tổng độ dài <= 10 s.
  - Không bao giờ gộp qua khoảng nghỉ > 0.8 s hoặc khi đổi người nói.
  - Mỗi unit có: id, start, end, parts (id các segment gốc), speech_time (tổng thời lượng các từ),
    dur = min(end - start, speech_time + 0.5 * tổng khoảng nghỉ bên trong) + phần mượn khoảng lặng phía sau = min(khoảng lặng sau - 0.15, 0.4).
  - Ngân sách ký tự: cps lấy từ DECISIONS.md theo giọng đang dùng (đo ở Phase 2);
    min_chars = 0.9 * dur * cps, target_chars = dur * cps, max_chars = 1.15 * dur * cps (đếm cả khoảng trắng và dấu câu).
  - Dịch bằng prompts/translate.md theo unit. Phụ đề: mỗi unit một khối, tối đa 2 dòng ngắt cân đối.
- `analyze` stage: ONE LLM call over the whole transcript -> analysis.json (genre, setting, characters with gender, honorific scheme, glossary). Owner-editable.
- `translate`: batches of ~25 lines with +-5 lines of context, glossary, strict JSON (id-keyed). Each line gets a character budget = slot duration x chars-per-second of the chosen voice. Outputs `vi_text` and `tts_text`.
- text/vi_normalize.py: rule-based normalizer for numbers, dates, units, percentages, currencies, acronyms -> spoken Vietnamese ("3.5kg" -> "ba phẩy năm ki-lô-gam"). Tests with >= 30 cases.
- Post-checks: empty lines, leftover Chinese characters, overflow vs budget; retry only failed ids. Review file the owner can edit (segments.json / review.srt) and rerun from `tts`.
Acceptance: normalizer tests pass; reruns cost 0 API calls (cache); owner reads a 20-line sample and approves.

## PHASE 5 — Multi-speaker voices

Goal: different characters get different, consistent voices. Short videos default to one narrator voice.
- Gender per segment: median F0 (librosa pyin or parselmouth) with a configurable threshold, combined with the character genders from analysis.json.
- Optional speaker clustering with lightweight embeddings (evaluate resemblyzer / speechbrain ECAPA / ONNX; ask before adding, R9). Must stay optional.
- speaker -> voice mapping using preset voices (male/female, North/South); overrides in voices.json; optional zero-shot cloning from an owner-provided 3-5 s reference wav.
Acceptance: on a 2-speaker sample, the owner confirms >= 90% of 20 checked lines have the right gender; the same speaker keeps the same voice throughout; a 30 s review sample is written to out/review/.

## PHASE 6 — Voice-to-picture fit (vòng lặp khép kín dựa trên số đo thật)

Goal: Vietnamese lines fit their time slots without sounding rushed or drifting.
Thuật toán đo kiểm vòng khép kín dựa trên số đo thật:
1. Tạo giọng từng unit, đo `tts_dur` thật, tính tỉ lệ `s = tts_dur / dur`.
2. `0.95 <= s <= 1.05`: giữ nguyên (vùng an toàn).
3. `0.9 <= s <= 1.2`: co giãn thời gian giữ nguyên cao độ theo hệ số `s` (pitch-preserving atempo/rubberband).
4. Ngoài `[0.9; 1.2]`: gom TẤT CẢ unit lệch vào MỘT yêu cầu `prompts/fit_rewrite.md` (kèm `tts_dur` đo thật, `dur`, hướng shorter/longer, `target_chars` tính từ tốc độ đọc đo được của chính clip đó), rồi tạo giọng lại chỉ các unit này. Tối đa 2 vòng lặp.
5. Sau 2 vòng:
   - Nếu `s > 1.2`: tăng tốc tối đa 1.2x và cho tràn vào khoảng lặng phía sau nếu còn, không thì gắn cờ `overflow`.
   - Nếu `s < 0.9`: làm chậm tối thiểu 0.9x và chấp nhận còn khoảng lặng.
6. Chế độ làm chậm hình video (stretch mode) vẫn là tùy chọn, mặc định tắt.
Tests: golden table >= 15 cases (overlapping segments, zero gap, very long line, first/last segment, huge overflow).
Acceptance: asserts: no overlapping voice clips, zero drift at the end; owner verdict on three 30 s review clips in both modes.

## PHASE 7 — Mix, render, subtitles, hard-sub tools

- Voice track assembled in chunks into one wav (int16, 24 kHz), then ONE ffmpeg mix: BGM ducking (sidechaincompress), loudnorm (~ -16 LUFS), true-peak limiter.
- Render: NVENC with libx264 fallback; aspect modes 16:9 / 9:16 / 1:1 (blurred-background or crop, configurable).
- ASS subtitles: font, size, colors, outline, position, background box; fonts must render Vietnamese diacritics correctly (test it).
- Blur box (x, y, w, h) over original hard subtitles; logo overlay (png, position, size, opacity).
- Optional OCR of hard-coded Chinese subtitles (RapidOCR on a cropped region at 2-4 fps, dedupe) as an alternative/validation for ASR.
Acceptance: tests for ASS generation; a 1-min render with all features on; owner confirms diacritics and blur look right.

## PHASE 8 — Merge tools (Đã loại bỏ tải video trực tuyến)

- Merge tool: nối và ghép nhiều tệp video với stream copy khi codec khớp, tự động mã hóa lại khi cần.
- Tính năng tải video (yt-dlp, cookies) đã được gỡ bỏ hoàn toàn; ứng dụng chỉ nhận file video cục bộ từ máy người dùng.
Acceptance: ghép nối các đoạn video ngắn hoạt động ổn định; luồng nhập file cục bộ mượt mà.

## PHASE 9 — UI (one tab per conversation to save quota)

- FastAPI + PyQt6 UI ứng dụng desktop / web app local.
- Tabs: Dự án (nhập file video cục bộ), Lồng tiếng (preview player, timeline), Phụ đề, Ghép video (Merge), Cài đặt hệ thống (Tài khoản dịch, cấu hình). (Đã loại bỏ tab Tải xuống).
- Per-line editor: edit vi_text, regenerate one line's audio, preview it. Resume banner. Queue runs one heavy job at a time.
Acceptance: full pipeline from the UI on clip_1min; kill the backend mid-run and resume from the UI.

## PHASE 10 — Hardening and packaging

- Simulate and fix: missing cuDNN, CUDA OOM, API 429, disk full, bad cookies, corrupted video, Vietnamese/space paths. Each gives a Vietnamese message with a next step.
- "Export diagnostics" zip (logs, env summary, NO keys). First-run model download screen with progress. `start.bat`. Vietnamese user guide in README.
- Optional: Tauri packaging.
Acceptance: setup from a fresh clone works by following README only; every simulated failure shows a helpful Vietnamese message.
