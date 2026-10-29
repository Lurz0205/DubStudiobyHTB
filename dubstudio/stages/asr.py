"""Stage: asr. Transcribes Chinese audio using faster-whisper large-v3-turbo."""
import json
import os
import re
from pathlib import Path
import site
import sys
from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash


def reconnect_dangling_asr_segments(segments: list[dict], max_combined_dur: float = 9.5) -> list[dict]:
    """
    Merges adjacent ASR segments that were unnaturally split mid-sentence by VAD or ASR punctuation.
    Fixes mid-sentence breaks like '当然现在它' + '也在经历' -> '当然现在它也在经历'.
    """
    if not segments or len(segments) <= 1:
        return segments

    terminal_punct = set("。！？!?…\n")
    continuation_starters = (
        "也", "在", "了", "着", "过", "的", "地", "得",
        "而", "且", "并且", "但是", "所以", "因为", "而且", "然而", "不过",
        "把", "被", "让", "叫", "给", "跟", "和", "与", "同",
        "会", "能", "可以", "要", "想", "是", "就", "才", "又", "还", "都",
        "个", "次", "只", "条", "件", "倍", "万", "千", "百", "点", "秒", "分",
        "它", "他们", "它们", "这个", "那个", "这些", "那些",
    )
    dangling_enders = (
        "现在", "目前", "我们", "他们", "大家", "直接", "因为", "所以",
        "如果", "但是", "而且", "比较", "非常", "特别", "这个", "那个",
        "一种", "一些", "大", "会", "能", "想", "要", "在", "跟", "和",
    )

    merged: list[dict] = []
    curr = dict(segments[0])

    for nxt in segments[1:]:
        c_st = float(curr["start"])
        c_en = float(curr["end"])
        n_st = float(nxt["start"])
        n_en = float(nxt["end"])
        gap = round(n_st - c_en, 3)
        combined_dur = round(n_en - c_st, 3)

        c_txt = str(curr.get("src_text") or "").strip()
        n_txt = str(nxt.get("src_text") or "").strip()

        c_clean = re.sub(r'[，。！？、；…!?,;.\s]', '', c_txt)
        n_clean = re.sub(r'[，。！？、；…!?,;.\s]', '', n_txt)

        c_last_char = c_txt[-1] if c_txt else ""
        c_has_terminal = c_last_char in terminal_punct

        is_short_fragment = (c_en - c_st < 2.2 or len(c_clean) <= 6) and not c_has_terminal
        next_is_continuation = any(n_clean.startswith(w) for w in continuation_starters)
        curr_is_dangling = (
            any(c_clean.endswith(w) for w in dangling_enders)
            or (c_last_char in "，,、;；…—-" or not c_has_terminal)
        )
        next_is_tiny = (n_en - n_st < 1.5 or len(n_clean) <= 4)

        should_merge = (
            gap <= 1.1
            and combined_dur <= max_combined_dur
            and (
                (is_short_fragment and (next_is_continuation or gap <= 0.45 or curr_is_dangling))
                or (next_is_continuation and gap <= 0.6)
                or (curr_is_dangling and next_is_continuation)
                or (next_is_tiny and gap <= 0.45)
            )
        )

        if should_merge:
            c_txt_clean = c_txt.rstrip("，,、;；。…")
            joined_txt = f"{c_txt_clean}{n_txt}"
            curr["end"] = n_en
            curr["src_text"] = joined_txt
            curr["speech_time"] = round(curr.get("speech_time", 0.0) + nxt.get("speech_time", 0.0), 3)
            if "words" in curr and "words" in nxt:
                curr["words"] = curr["words"] + nxt["words"]
        else:
            merged.append(curr)
            curr = dict(nxt)

    merged.append(curr)

    for idx, item in enumerate(merged, start=1):
        item["id"] = idx

    return merged


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
            from dubstudio.components import is_component_ready
            ready, status_msg = is_component_ready("sensevoice_small")
            if not ready:
                raise DubError(
                    code="MODEL_NOT_FOUND",
                    user_message_vi="Mô hình nhận diện SenseVoice-Small chưa được tải xong (hoặc đang tải dở dang).",
                    hint_vi="Vui lòng chuyển sang tab 'Cài đặt' -> mục 'Quản lý Gói mô hình AI' để tải hoàn tất mô hình SenseVoice-Small trước khi tạo phụ đề.",
                )

            emit_event(stage_name, 10.0, f"Khởi tạo SenseVoice-Small ({device})...")
            from funasr import AutoModel
            from funasr.utils.postprocess_utils import rich_transcription_postprocess

            from dubstudio.paths import get_models_dir, get_app_dir, get_model_search_paths
            models_root = get_models_dir()
            candidates = []
            for b in get_model_search_paths():
                candidates.append(b / "SenseVoiceSmall")
            candidates.extend([
                Path("models/SenseVoiceSmall"),
                get_app_dir() / "models" / "SenseVoiceSmall",
                Path(sys.executable).parent / "models" / "SenseVoiceSmall",
                Path(sys.executable).parent.parent / "models" / "SenseVoiceSmall",
            ])
            model_dir = next(
                (c for c in candidates if (c / "model.pt").is_file() and (c / "model.pt").stat().st_size > 100 * 1024 * 1024),
                None
            )
            vad_kwargs = {
                "max_single_segment_time": 6000,
                "max_end_silence_time": 400,
                "speech_noise_thres": 0.6,
            }
            if not model_dir:
                raise DubError(
                    code="MODEL_NOT_FOUND",
                    user_message_vi="Không tìm thấy tệp trọng số SenseVoice-Small (model.pt > 100MB) cục bộ trên máy.",
                    hint_vi="Vui lòng chuyển sang tab Cài đặt để tải lại gói SenseVoice-Small.",
                )

            # Locate BPE model file
            bpe_file = None
            for bpe_cand in [
                model_dir / "chn_jpn_yue_eng_ko_spectok.bpe.model",
                model_dir / "bpe.model",
            ]:
                if bpe_cand.is_file():
                    bpe_file = bpe_cand
                    break

            bpe_std = model_dir / "bpe.model"
            if not bpe_std.is_file() and bpe_file and bpe_file.is_file():
                try:
                    import shutil
                    shutil.copyfile(bpe_file, bpe_std)
                except Exception:
                    pass

            # Locate local VAD model if available
            vad_candidates = [
                models_root / "fsmn-vad",
                get_app_dir() / "models" / "fsmn-vad",
                Path("models/fsmn-vad"),
                Path.home() / ".cache" / "modelscope" / "models" / "iic--speech_fsmn_vad_zh-cn-16k-common-pytorch" / "snapshots" / "master",
            ]
            vad_target = "fsmn-vad"
            for vc in vad_candidates:
                if vc.is_dir() and (vc / "model.pt").is_file():
                    vad_target = str(vc.resolve())
                    break

            model_kwargs = {
                "model": str(model_dir.resolve()),
                "vad_model": vad_target,
                "vad_kwargs": vad_kwargs,
                "device": device if device == "cpu" else "cuda:0",
                "disable_update": True,
            }
            if bpe_file and bpe_file.is_file():
                model_kwargs["tokenizer_conf"] = {"bpemodel": str(bpe_file.resolve())}

            try:
                asr_model = AutoModel(**model_kwargs)
            except Exception as e_model:
                if device != "cpu":
                    emit_event(stage_name, 15.0, "CUDA gặp sự cố, tự động chuyển SenseVoice sang CPU...")
                    model_kwargs["device"] = "cpu"
                    asr_model = AutoModel(**model_kwargs)
                else:
                    raise e_model

            emit_event(stage_name, 40.0, "Đang bóc tách phân đoạn thoại tiếng Trung qua SenseVoice...")
            res = asr_model.generate(
                input=str(input_audio.resolve()),
                cache={},
                language="zh",
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
            from dubstudio.paths import get_models_dir, get_model_search_paths
            models_root = get_models_dir()
            model_size = cfg.asr.model_size
            local_candidates = []
            for b in get_model_search_paths():
                local_candidates.append(b / f"models--Systran--faster-whisper-{model_size}")
                local_candidates.append(b / f"faster-whisper-{model_size}")
                local_candidates.append(b / model_size)
            local_candidates.extend([
                Path(f"models/models--Systran--faster-whisper-{model_size}"),
                Path(f"models/{model_size}"),
            ])
            from dubstudio.components import is_component_ready
            ready, _ = is_component_ready("whisper_large_v3")
            if not ready:
                raise DubError(
                    code="MODEL_NOT_FOUND",
                    user_message_vi=f"Mô hình faster-whisper '{model_size}' chưa được tải xong (hoặc đang tải dở dang).",
                    hint_vi="Vui lòng chuyển sang tab 'Cài đặt' -> mục 'Quản lý Gói mô hình AI' để tải mô hình faster-whisper.",
                )

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
            # 1. Terminal punctuation (。, ！, ？, !, ?) splits if curr_dur >= 1.2s
            # 2. Clause punctuation (，, 、, ；) only splits if curr_dur >= 3.5s and gap >= 0.25s
            # 3. Silence gap >= split_silence_gap_s (0.55s) and curr_dur >= 2.5s
            # 4. Maximum segment length <= max_segment_duration_s (8.0s)
            split_gap = max(0.5, cfg.asr.split_silence_gap_s)
            max_dur = cfg.asr.max_segment_duration_s
            terminal_punct = set("。！？!?…\n")
            clause_punct = set("，、；,;")

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
                prev_has_terminal = any(ch in terminal_punct for ch in prev_w["word"])
                prev_has_clause = any(ch in clause_punct for ch in prev_w["word"])

                should_split = (
                    (prev_has_terminal and curr_dur >= 1.2)
                    or (prev_has_clause and curr_dur >= 3.5 and gap >= 0.25)
                    or (gap >= split_gap and curr_dur >= 2.5)
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

        # Merge any dangling fragments or mid-sentence breaks produced by VAD/ASR
        refined_segments = reconnect_dangling_asr_segments(refined_segments)

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
