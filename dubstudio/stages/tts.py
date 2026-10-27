"""Stage: tts. Synthesizes Vietnamese speech using VieNeu-TTS in a separate process."""
import json
from pathlib import Path
import soundfile as sf
from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash


def run(job: JobContext, cfg: AppConfig) -> None:
    stage_name = "tts"
    emit_event(stage_name, 0.0, "Bắt đầu tổng hợp giọng đọc tiếng Việt (TTS)")

    segments_file = job.workspace / "segments.json"
    input_hash = compute_file_hash(segments_file)

    if job.is_stage_done(stage_name, input_hash):
        emit_event(stage_name, 100.0, "Giai đoạn TTS đã hoàn thành (bỏ qua)")
        return

    job.start_stage(stage_name, input_hash)

    with open(segments_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    tts_dir = job.workspace / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)

    conf_file = job.workspace / "job_config.json"
    conf = {}
    if conf_file.exists():
        try:
            conf = json.loads(conf_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    from dubstudio.tts.base import clean_voice_name, MALE_VOICES, FEMALE_VOICES

    male_voice = clean_voice_name(conf.get("default_male_voice") or conf.get("voice_male") or cfg.tts.default_male_voice, "Minh Đức")
    female_voice = clean_voice_name(conf.get("default_female_voice") or conf.get("voice_female") or cfg.tts.default_female_voice, "Quỳnh Anh")
    detect_gender = bool(conf.get("detect_gender", False))
    single_choice = conf.get("single_voice_gender", "male")
    single_voice_override = conf.get("single_voice")
    if single_voice_override:
        fallback_single_voice = clean_voice_name(single_voice_override, male_voice)
    else:
        fallback_single_voice = female_voice if single_choice == "female" else male_voice

    import hashlib

    def _calc_seg_hash(text: str, voice: str, speed: float) -> str:
        s = f"{text.strip()}|{voice.strip()}|{float(speed):.2f}"
        return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]

    # Evaluate which segments are needed and which are already clean vs dirty
    needed_segs = []
    dirty_segs = []
    for s in segments:
        if s.get("mute_tts") or s.get("muted_tts"):
            continue
        txt = (s.get("tts_text") or s.get("vi_text", "") or s.get("text", "")).strip()
        if not txt:
            continue
        # If user explicitly customized this segment's voice in sentence editor, preserve it
        if s.get("user_edited_voice") or s.get("voice_custom"):
            v_choice = clean_voice_name(s.get("voice") or fallback_single_voice, fallback_single_voice)
        else:
            if detect_gender:
                v_choice = male_voice if s.get("gender") == "male" else female_voice
            else:
                v_choice = fallback_single_voice
        v_choice = clean_voice_name(v_choice, fallback_single_voice)

        # Invalidate old TTS cache if voice changed from previous assignment
        old_voice = clean_voice_name(s.get("voice", ""), "")
        if old_voice and old_voice != v_choice:
            s["tts_hash"] = None
            s.pop("tts_file", None)
            s.pop("tts_dur", None)
            s["has_tts"] = False
            wav_file = tts_dir / f"{s['id']:04d}.wav"
            if wav_file.exists():
                try:
                    wav_file.unlink(missing_ok=True)
                except Exception:
                    pass

        s["voice"] = v_choice
        sp = float(s.get("speed", 1.0) or 1.0)
        expected_hash = _calc_seg_hash(txt, v_choice, sp)
        wav_file = tts_dir / f"{s['id']:04d}.wav"

        needed_segs.append(s)
        # Check if wav exists, is valid, and matches the content hash (either explicit speed or base 1.0)
        is_clean = (
            wav_file.exists()
            and wav_file.stat().st_size > 500
            and bool(s.get("tts_hash"))
            and (
                s.get("tts_hash") == expected_hash
                or s.get("tts_hash") == _calc_seg_hash(txt, v_choice, 1.0)
            )
        )
        if not is_clean:
            dirty_segs.append((s, txt, v_choice, sp, expected_hash))

    if len(needed_segs) > 0 and len(dirty_segs) == 0:
        outputs = []
        for s in needed_segs:
            w_name = f"{s['id']:04d}.wav"
            s["tts_file"] = f"tts/{w_name}"
            if not s.get("tts_dur"):
                try:
                    s["tts_dur"] = round(sf.info(str(tts_dir / w_name)).duration, 3)
                except Exception:
                    pass
            outputs.append(f"tts/{w_name}")
        with open(segments_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        outputs.append("segments.json")
        emit_event(stage_name, 100.0, "Toàn bộ âm thanh TTS đã khớp với phụ đề mới nhất (bỏ qua mô hình)")
        job.finish_stage(stage_name, outputs)
        return

    emit_event(stage_name, 5.0, f"Phát hiện {len(dirty_segs)}/{len(needed_segs)} câu cần tạo mới hoặc cập nhật âm thanh...")

    from dubstudio.components import is_component_ready
    ready, _ = is_component_ready("vieneu_tts_voices")
    if not ready:
        raise DubError(
            code="MODEL_NOT_FOUND",
            user_message_vi="Mô hình giọng đọc VieNeu-TTS v3 chưa được tải xong (hoặc đang tải dở dang).",
            hint_vi="Vui lòng chuyển sang tab 'Cài đặt' -> mục 'Quản lý Gói mô hình AI' để tải mô hình VieNeu-TTS trước khi tạo lồng tiếng.",
        )

    import os
    import site
    import sys

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

    if sys.platform == "win32":
        for p in site.getsitepackages():
            cublas_dir = Path(p) / "nvidia" / "cublas" / "bin"
            cudnn_dir = Path(p) / "nvidia" / "cudnn" / "bin"
            if cublas_dir.exists():
                try:
                    os.add_dll_directory(str(cublas_dir))
                except Exception:
                    pass
            if cudnn_dir.exists():
                try:
                    os.add_dll_directory(str(cudnn_dir))
                except Exception:
                    pass

    outputs = []
    total_dirty = len(dirty_segs)
    dirty_dict = {s["id"]: (txt, v_choice, sp, exp_hash) for (s, txt, v_choice, sp, exp_hash) in dirty_segs}
    done_dirty_count = 0

    # Load Vieneu directly in this isolated stage subprocess
    try:
        from vieneu import Vieneu
        from dubstudio.tts.base import resolve_vieneu_dirs

        backbone_dir, moss_dir = resolve_vieneu_dirs()

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        try:
            engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cuda")
        except Exception:
            engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cpu", backend="pytorch")
    except Exception as e:
        raise DubError(
            code="TTS_INIT_FAILED",
            user_message_vi="Không thể khởi tạo mô hình TTS VieNeu-TTS.",
            hint_vi="Kiểm tra cài đặt thư viện 'vieneu' và 'transformers'.",
            details={"error": str(e)},
        )

    for idx, seg in enumerate(needed_segs, 1):
        seg_id = seg["id"]
        wav_name = f"{seg_id:04d}.wav"
        wav_path = tts_dir / wav_name

        if seg_id not in dirty_dict:
            # Segment is already clean
            seg["tts_file"] = f"tts/{wav_name}"
            if not seg.get("tts_dur"):
                try:
                    seg["tts_dur"] = round(sf.info(str(wav_path)).duration, 3)
                except Exception:
                    pass
            outputs.append(f"tts/{wav_name}")
            continue

        text, voice_choice, speed, exp_hash = dirty_dict[seg_id]
        voice_choice = clean_voice_name(voice_choice, male_voice)
        seg["voice"] = voice_choice
        seg["speed"] = speed

        try:
            try:
                audio = engine.infer(text, voice=voice_choice)
            except Exception:
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
                engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cpu", backend="pytorch")
                audio = engine.infer(text, voice=voice_choice)

            if abs(speed - 1.0) > 0.02:
                import tempfile
                from dubstudio.stages.fit import time_stretch_audio
                with tempfile.NamedTemporaryFile("wb", suffix=".wav", delete=False) as tmp:
                    raw_wav = Path(tmp.name)
                try:
                    engine.save(audio, str(raw_wav.resolve()))
                    time_stretch_audio(raw_wav, wav_path, rate=speed)
                finally:
                    raw_wav.unlink(missing_ok=True)
            else:
                engine.save(audio, str(wav_path.resolve()))

            info = sf.info(str(wav_path))

            seg["tts_file"] = f"tts/{wav_name}"
            seg["tts_dur"] = round(info.duration, 3)
            seg["tts_hash"] = exp_hash
            outputs.append(f"tts/{wav_name}")

            done_dirty_count += 1
            pct = (done_dirty_count / total_dirty * 100.0) if total_dirty > 0 else 100.0
            emit_event(stage_name, pct, f"Đang tạo audio đoạn {done_dirty_count}/{total_dirty} (#{seg_id} - {voice_choice})")

            # Persist segments.json periodically
            if done_dirty_count % 5 == 0 or done_dirty_count == total_dirty:
                with open(segments_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            emit_event(stage_name, (done_dirty_count / max(1, total_dirty) * 100.0), f"Cảnh báo lỗi TTS đoạn {seg['id']}: {e}", level="warning")

    # Update segments.json with duration & filenames
    with open(segments_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    outputs.append("segments.json")
    emit_event(stage_name, 100.0, "Tổng hợp âm thanh lồng tiếng hoàn tất")
    job.finish_stage(stage_name, outputs)
