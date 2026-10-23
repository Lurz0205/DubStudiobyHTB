"""Stage: asr. Transcribes Chinese audio using faster-whisper large-v3-turbo."""
import json
import os
from pathlib import Path
import site
import sys
from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash


def _setup_cuda_dlls():
    if sys.platform == "win32":
        for p in site.getsitepackages():
            cublas_dir = Path(p) / "nvidia" / "cublas" / "bin"
            cudnn_dir = Path(p) / "nvidia" / "cudnn" / "bin"
            if cublas_dir.exists():
                os.add_dll_directory(str(cublas_dir))
            if cudnn_dir.exists():
                os.add_dll_directory(str(cudnn_dir))


def run(job: JobContext, cfg: AppConfig, input_audio: Path) -> None:
    stage_name = "asr"
    emit_event(stage_name, 0.0, "Bắt đầu nhận dạng giọng nói tiếng Trung (ASR)")

    asr_file = job.workspace / "asr.json"
    segments_file = job.workspace / "segments.json"
    has_valid_segments = False
    if asr_file.exists() and segments_file.exists():
        try:
            with open(segments_file, "r", encoding="utf-8") as sf:
                s_data = json.load(sf)
                if len(s_data.get("segments", [])) > 0:
                    has_valid_segments = True
        except Exception:
            pass

    input_hash = compute_file_hash(input_audio)
    if job.is_stage_done(stage_name, input_hash) or has_valid_segments:
        emit_event(stage_name, 100.0, "Giai đoạn ASR đã hoàn thành trước đó (bỏ qua)")
        job.finish_stage(stage_name, ["asr.json", "segments.json"])
        return

    job.start_stage(stage_name, input_hash)
    from dubstudio.packaging import ensure_runtime_paths
    ensure_runtime_paths()
    _setup_cuda_dlls()

    try:
        import torch
        from dubstudio.ffmpeg_utils import probe_file

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "int8_float16" if device == "cuda" else "int8"
        model_choice = str(cfg.asr.model_size or "large-v3").lower().strip()

        if "sensevoice" in model_choice:
            emit_event(stage_name, 10.0, f"Khởi tạo SenseVoice-Small ({device})...")
            from funasr import AutoModel
            from funasr.utils.postprocess_utils import rich_transcription_postprocess

            from dubstudio.paths import get_models_dir, get_app_dir
            models_root = get_models_dir()
            candidates = [
                models_root / "SenseVoiceSmall",
                Path("models/SenseVoiceSmall"),
                get_app_dir() / "models" / "SenseVoiceSmall",
                Path(sys.executable).parent / "models" / "SenseVoiceSmall",
                Path(sys.executable).parent.parent / "models" / "SenseVoiceSmall",
            ]
            model_dir = next((c for c in candidates if c.exists()), None)
            vad_kwargs = {
                "max_single_segment_time": 6000,
                "max_end_silence_time": 400,
                "speech_noise_thres": 0.6,
            }
            if not model_dir:
                raise DubError(
                    code="MODEL_NOT_FOUND",
                    user_message_vi="Không tìm thấy mô hình SenseVoiceSmall cục bộ trên máy.",
                    hint_vi="Vui lòng đặt thư mục SenseVoiceSmall vào thư mục models/ hoặc kiểm tra lại đường dẫn trong Cài đặt.",
                )

            asr_model = AutoModel(
                model=str(model_dir.resolve()),
                vad_model="fsmn-vad",
                vad_kwargs=vad_kwargs,
                device=device if device == "cpu" else "cuda:0",
                disable_update=True,
            )

            emit_event(stage_name, 40.0, "Đang bóc tách phân đoạn thoại tiếng Trung qua SenseVoice...")
            res = asr_model.generate(
                input=str(input_audio.resolve()),
                cache={},
                language="zn",
                use_itn=True,
                batch_size_s=60,
                merge_vad=False,
                sentence_timestamp=True,
            )

            refined_segments = []
            if res and isinstance(res, list):
                item = res[0]
                sentence_info = item.get("sentence_info") or []
                for sent in sentence_info:
                    raw_txt = rich_transcription_postprocess(sent.get("text", "")).strip()
                    if not raw_txt or raw_txt in ("。", "，", "？", "！", ".", "…", ","):
                        continue
                    st = round(float(sent.get("start", 0)) / 1000.0, 3)
                    en = round(float(sent.get("end", 0)) / 1000.0, 3)
                    if en <= st:
                        continue
                    sp_time = round(en - st, 3)
                    words_list = [{"word": raw_txt, "start": st, "end": en, "probability": 1.0}]
                    refined_segments.append({
                        "id": len(refined_segments) + 1,
                        "start": st,
                        "end": en,
                        "src_text": raw_txt,
                        "speech_time": sp_time,
                        "words": words_list,
                        "vi_text": "",
                        "tts_text": "",
                        "speaker": None,
                        "gender": "unknown",
                        "voice": None,
                        "tts_file": None,
                        "tts_dur": None,
                        "fit": None,
                        "flags": [],
                    })

            try:
                probe_info = probe_file(input_audio)
                total_duration = float(probe_info.get("format", {}).get("duration") or probe_info.get("duration", 0.0))
            except Exception:
                total_duration = 0.0

            if total_duration <= 0.0:
                try:
                    import soundfile as sf
                    total_duration = round(float(sf.info(str(input_audio.resolve())).duration), 2)
                except Exception:
                    total_duration = refined_segments[-1]["end"] if refined_segments else 0.0

        else:
            from faster_whisper import WhisperModel
            from dubstudio.paths import get_models_dir
            models_root = get_models_dir()
            model_size = cfg.asr.model_size
            local_candidates = [
                models_root / f"models--Systran--faster-whisper-{model_size}",
                models_root / f"faster-whisper-{model_size}",
                models_root / model_size,
                Path(f"models/models--Systran--faster-whisper-{model_size}"),
                Path(f"models/{model_size}"),
            ]
            whisper_target = cfg.asr.model_size
            for cand in local_candidates:
                if cand.exists() and cand.is_dir():
                    try:
                        if any(cand.iterdir()):
                            whisper_target = str(cand.resolve())
                            break
                    except Exception:
                        pass

            emit_event(stage_name, 10.0, f"Khởi tạo faster-whisper ({device})...")
            try:
                model = WhisperModel(
                    whisper_target,
                    device=device,
                    compute_type=compute_type,
                    download_root=str(models_root.resolve()),
                    local_files_only=True,
                )
            except Exception as ex:
                raise DubError(
                    code="MODEL_NOT_FOUND",
                    user_message_vi=f"Không tìm thấy mô hình faster-whisper '{model_size}' cục bộ trên máy.",
                    hint_vi="Vui lòng kiểm tra lại thư mục models/ hoặc đường dẫn mô hình.",
                    details={"error": str(ex)},
                ) from ex

            emit_event(stage_name, 40.0, "Đang trích xuất phụ đề tiếng Trung với word timestamps...")
            segments_gen, info = model.transcribe(
                str(input_audio.resolve()),
                language="zh",
                initial_prompt="以下是普通话的句子，请用简体中文输出标点符号。",
                condition_on_previous_text=False,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=cfg.asr.vad_min_silence_duration_ms),
            )

            raw_words = []
            for s in segments_gen:
                if s.words:
                    for w in s.words:
                        word_text = w.word.strip()
                        if word_text:
                            raw_words.append({
                                "word": word_text,
                                "start": round(w.start, 3),
                                "end": round(w.end, 3),
                                "probability": round(w.probability, 3),
                            })
                else:
                    # Fallback if no word timestamps for a short segment
                    raw_words.append({
                        "word": s.text.strip(),
                        "start": round(s.start, 3),
                        "end": round(s.end, 3),
                        "probability": 1.0,
                    })

            # Split words into refined segments:
            # 1. Gap between words >= split_silence_gap_s (0.35s)
            # 2. Punctuation (，, 。, ！, ？, 、, ；)
            # 3. Maximum segment length <= max_segment_duration_s (8.0s)
            split_gap = cfg.asr.split_silence_gap_s
            max_dur = cfg.asr.max_segment_duration_s
            punct_set = set("，。！？、；…!?,;.")

            refined_segments = []
            current_words = []

            def flush_segment(words_list):
                if not words_list:
                    return
                st = words_list[0]["start"]
                en = words_list[-1]["end"]
                txt = "".join(w["word"] for w in words_list).strip()
                sp_time = round(sum(w["end"] - w["start"] for w in words_list), 3)
                refined_segments.append({
                    "id": len(refined_segments) + 1,
                    "start": st,
                    "end": en,
                    "src_text": txt,
                    "speech_time": sp_time,
                    "words": words_list,
                    "vi_text": "",
                    "tts_text": "",
                    "speaker": None,
                    "gender": "unknown",
                    "voice": None,
                    "tts_file": None,
                    "tts_dur": None,
                    "fit": None,
                    "flags": [],
                })

            for i, w in enumerate(raw_words):
                if not current_words:
                    current_words.append(w)
                    continue

                prev_w = current_words[-1]
                gap = w["start"] - prev_w["end"]
                curr_dur = w["end"] - current_words[0]["start"]
                prev_has_punct = any(ch in punct_set for ch in prev_w["word"])

                should_split = (
                    prev_has_punct
                    or gap >= split_gap
                    or (curr_dur >= max_dur and gap >= 0.15)
                    or curr_dur >= (max_dur * 1.3)
                )

                if should_split:
                    flush_segment(current_words)
                    current_words = [w]
                else:
                    current_words.append(w)

            if current_words:
                flush_segment(current_words)

            total_duration = round(info.duration, 2)

        # Save asr.json with full word details
        from dubstudio.jobstate import atomic_write_json
        asr_file = job.workspace / "asr.json"
        atomic_write_json(asr_file, refined_segments, indent=2)

        # Initialize segments.json conforming to Data Contract
        segments_data = {
            "version": 1,
            "video": {"duration": total_duration},
            "segments": refined_segments,
        }
        segments_file = job.workspace / "segments.json"
        atomic_write_json(segments_file, segments_data, indent=2)

        emit_event(stage_name, 100.0, f"Nhận dạng hoàn tất: {len(refined_segments)} đoạn thoại")
        job.finish_stage(stage_name, ["asr.json", "segments.json"])

    except Exception as e:
        job.fail_stage(stage_name, str(e))
        raise DubError(
            code="ASR_FAILED",
            user_message_vi="Lỗi trong quá trình nhận dạng giọng nói ASR.",
            hint_vi="Kiểm tra driver card đồ họa hoặc chuyển compute_type sang CPU.",
            details={"error": str(e)},
        )
    finally:
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
