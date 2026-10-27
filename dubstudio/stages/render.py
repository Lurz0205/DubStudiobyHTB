"""Stage: render. Produces final dubbed MP4 video and Vietnamese SRT subtitles."""
import json
from pathlib import Path
import subprocess
from typing import Optional
from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash


def format_srt_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def rasterize_color_boxes(boxes: list, width: int, height: int, out_png: Path) -> bool:
    """Rasterize active color/text boxes onto a transparent PNG matching video dimensions."""
    active_boxes = [b for b in boxes if b.get("enabled", True)]
    if not active_boxes:
        return False

    from PIL import Image, ImageDraw, ImageFont

    overlay_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

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
        is_pct = cb.get("is_percent", True)
        if is_pct:
            bx = int(round(float(cb.get("x", 0)) / 100.0 * width))
            by = int(round(float(cb.get("y", 0)) / 100.0 * height))
            bw = max(10, int(round(float(cb.get("w", cb.get("width", 20))) / 100.0 * width)))
            bh = max(10, int(round(float(cb.get("h", cb.get("height", 8))) / 100.0 * height)))
        else:
            bx = int(round(float(cb.get("x", 0))))
            by = int(round(float(cb.get("y", 0))))
            bw = max(10, int(round(float(cb.get("w", cb.get("width", 50))))))
            bh = max(10, int(round(float(cb.get("h", cb.get("height", 50))))))

        color_hex = str(cb.get("color", "#000000")).lstrip("#")
        if len(color_hex) == 6:
            cr, cg, cb_val = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
        else:
            cr, cg, cb_val = 0, 0, 0
        opacity = float(cb.get("opacity", 0.8))
        ca = max(0, min(255, int(round(opacity * 255))))
        rad = max(0, int(round(float(cb.get("radius", 6)))))
        rot = float(cb.get("rotation", 0.0) or 0.0)

        box_surf = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(box_surf)
        b_draw.rounded_rectangle([0, 0, bw, bh], radius=rad, fill=(cr, cg, cb_val, ca))

        b_text = str(cb.get("text", "") or "").strip()
        if b_text:
            f_name = cb.get("font_name", "Arial")
            f_size = max(8, int(round(float(cb.get("font_size", 24) or 24))))
            p_font = _get_pil_font(f_name, f_size)
            t_hex = str(cb.get("text_color", "#FFFFFF")).lstrip("#")
            tr, tg, tb = (int(t_hex[0:2], 16), int(t_hex[2:4], 16), int(t_hex[4:6], 16)) if len(t_hex) == 6 else (255, 255, 255)
            o_hex = str(cb.get("text_outline_color", "#000000")).lstrip("#")
            or_c, og, ob = (int(o_hex[0:2], 16), int(o_hex[2:4], 16), int(o_hex[4:6], 16)) if len(o_hex) == 6 else (0, 0, 0)
            o_w = max(0, int(round(float(cb.get("text_outline_width", 2) or 2))))

            align_choice = str(cb.get("text_align", "center")).lower()
            if "left" in align_choice or "trái" in align_choice:
                tx, anchor, align = 12, "lm", "left"
            elif "right" in align_choice or "phải" in align_choice:
                tx, anchor, align = bw - 12, "rm", "right"
            else:
                tx, anchor, align = bw // 2, "mm", "center"

            b_draw.text(
                (tx, bh // 2),
                b_text,
                font=p_font,
                fill=(tr, tg, tb, 255),
                stroke_width=o_w,
                stroke_fill=(or_c, og, ob, 255) if o_w > 0 else None,
                anchor=anchor,
                align=align,
            )

        if rot != 0.0:
            rot_surf = box_surf.rotate(-rot, expand=True, resample=Image.Resampling.BICUBIC)
            rw, rh = rot_surf.size
            paste_x = bx + (bw - rw) // 2
            paste_y = by + (bh - rh) // 2
            overlay_img.paste(rot_surf, (paste_x, paste_y), rot_surf)
        else:
            overlay_img.paste(box_surf, (bx, by), box_surf)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    overlay_img.save(out_png, "PNG")
    return True


def generate_srt(segments_file: Path, srt_path: Path) -> None:
    """Generate Vietnamese SRT subtitle file with proportional 10-15 word display slices."""
    from dubstudio.subtitles.ass import get_segment_slices
    if not segments_file.exists():
        srt_path.write_text("", encoding="utf-8")
        return
    try:
        with open(segments_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        srt_path.write_text("", encoding="utf-8")
        return

    srt_idx = 1
    with open(srt_path, "w", encoding="utf-8") as f:
        for seg in data.get("segments", []):
            slices = get_segment_slices(seg)
            for sl in slices:
                start_str = format_srt_time(sl["start"])
                end_str = format_srt_time(sl["end"])
                f.write(f"{srt_idx}\n{start_str} --> {end_str}\n{sl['text']}\n\n")
                srt_idx += 1


def run(job: JobContext, cfg: AppConfig, input_video: Optional[Path] = None, force: bool = False) -> None:
    stage_name = "render"
    emit_event(stage_name, 0.0, "Bắt đầu xuất video thành phẩm")

    if input_video is None:
        input_video = job.input_path or (job.workspace / "input.mp4")
    input_video = Path(input_video).resolve()

    mixed_track = job.workspace / "mixed.wav"
    voice_track = job.workspace / "voice_track.wav"
    audio_track = mixed_track if (mixed_track.exists() and mixed_track.stat().st_size > 500) else voice_track
    style_file = job.workspace / "style.json"
    segments_file = job.workspace / "segments.json"
    mix_settings_file = job.workspace / "mix_settings.json"

    # Compute combined hash of audio_track + style.json + segments.json + mix_settings.json so changes to subtitles/style/audio always re-render
    import hashlib
    h = hashlib.sha256()
    if audio_track.exists():
        h.update(audio_track.read_bytes())
    if style_file.exists():
        h.update(style_file.read_bytes())
    if segments_file.exists():
        h.update(segments_file.read_bytes())
    if mix_settings_file.exists():
        h.update(mix_settings_file.read_bytes())
    input_hash = h.hexdigest()[:16]

    if not force and job.is_stage_done(stage_name, input_hash):
        emit_event(stage_name, 100.0, "Giai đoạn render đã hoàn thành (bỏ qua)")
        return

    job.start_stage(stage_name, input_hash)

    out_dir = cfg.general.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    base_name = job.job_id
    final_video = out_dir / f"{base_name}_vi.mp4"
    final_srt = out_dir / f"{base_name}_vi.srt"

    # 1. Sinh phụ đề SRT và ASS
    segments_file = job.workspace / "segments.json"
    generate_srt(segments_file, final_srt)

    final_ass = out_dir / f"{base_name}_vi.ass"
    from dubstudio.subtitles.ass import generate_ass_subtitles
    from dubstudio.ffmpeg_utils import probe_file
    seg_items = []
    if segments_file.exists():
        try:
            with open(segments_file, "r", encoding="utf-8") as f:
                seg_items = json.load(f).get("segments", [])
        except Exception:
            pass

    # Load custom subtitle styling from style.json or global preset
    style_data = None
    preset_file = Path("config") / "subtitle_preset.json"
    if style_file.exists():
        try:
            style_data = json.loads(style_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    elif preset_file.exists():
        try:
            style_data = json.loads(preset_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Probe actual video dimensions to ensure 1:1 pixel coordinate matching in ASS
    vid_w = 1280
    vid_h = 720
    try:
        info = probe_file(input_video)
        for s in info.get("streams", []):
            if s.get("codec_type") == "video":
                vid_w = int(s.get("width") or 1280)
                vid_h = int(s.get("height") or 720)
                break
    except Exception:
        pass

    generate_ass_subtitles(
        seg_items,
        final_ass,
        style=style_data,
        video_width=vid_w,
        video_height=vid_h,
    )

    # Copy ASS into workspace with relative name to avoid Windows C:\ escape bugs (AGENTS.md Section 8)
    local_ass = job.workspace / "subtitles.ass"
    local_ass.write_text(final_ass.read_text(encoding="utf-8"), encoding="utf-8")

    # 2. Render video: thay thế audio gốc bằng voice_track.wav và nhúng cứng (hard-sub) phụ đề ASS
    # Using relative path for subtitles filter executed with cwd=job.workspace to avoid Windows C:\ escape bugs (AGENTS.md Section 8)
    # Prioritize GPU hardware encoders: NVENC -> Intel QuickSync (h264_qsv) -> Windows MediaFoundation (h264_mf) -> CPU (libx264)
    encoders_to_try = [cfg.render.encoder, "h264_qsv", "h264_mf", cfg.render.fallback_encoder]
    # Deduplicate while preserving order
    encoders_to_try = list(dict.fromkeys(encoders_to_try))

    last_error_tail = ""
    for encoder in encoders_to_try:
        if encoder == "h264_nvenc":
            # Maximum-quality NVENC with two-pass fullres, VBR, and Adaptive Quantization
            target_cq = str(min(18, cfg.render.crf))
            rate_args = [
                "-preset", "p7",
                "-tune", "hq",
                "-rc:v", "vbr",
                "-cq", target_cq,
                "-b:v", "0",
                "-maxrate", "35M",
                "-bufsize", "60M",
                "-spatial-aq", "1",
                "-temporal-aq", "1",
                "-rc-lookahead", "32",
                "-multipass", "fullres",
                "-pix_fmt", "yuv420p",
            ]
        elif encoder == "h264_qsv":
            # Intel QuickSync hardware GPU encoder: fast, pristine quality, 0% CPU strain
            rate_args = [
                "-global_quality", str(min(18, cfg.render.crf)),
                "-look_ahead", "1",
            ]
        elif encoder == "h264_mf":
            # Windows MediaFoundation GPU hardware encoder with high bitrate for razor-sharp quality
            rate_args = [
                "-b:v", "18M",
                "-maxrate", "28M",
                "-bufsize", "36M",
                "-pix_fmt", "yuv420p",
            ]
        else:
            # High quality CPU fallback (libx264)
            rate_args = [
                "-preset", "slow",
                "-crf", str(min(18, cfg.render.crf)),
                "-pix_fmt", "yuv420p",
            ]

        has_audio = audio_track.exists() and audio_track.stat().st_size > 500
        from dubstudio.paths import resolve_tool
        from dubstudio.packaging import get_subprocess_env, safe_subprocess_run
        cmd = [
            resolve_tool("ffmpeg"), "-y",
            "-i", str(input_video.resolve()),
        ]
        if has_audio:
            cmd.extend(["-i", str(audio_track.resolve())])

        # Build video filter chain: Subtitle burning and/or Aspect ratio expansion
        vf_filters = []
        burn_subs = True
        if style_data and "burn_subtitles" in style_data:
            burn_subs = bool(style_data["burn_subtitles"])

        if burn_subs and local_ass.exists() and len(seg_items) > 0:
            vf_filters.append("subtitles=subtitles.ass")

        ar_setting = (style_data or {}).get("aspect_ratio", "")
        if ar_setting and str(ar_setting).lower() not in ("original", "gốc", "none", ""):
            try:
                parts = str(ar_setting).split(":")
                if len(parts) == 2:
                    rw, rh = float(parts[0]), float(parts[1])
                    target_ratio = rw / rh
                    curr_ratio = vid_w / max(1.0, float(vid_h))
                    if abs(curr_ratio - target_ratio) > 0.02:
                        if curr_ratio > target_ratio:
                            pad_w = vid_w
                            pad_h = int(round(vid_w / target_ratio))
                        else:
                            pad_h = vid_h
                            pad_w = int(round(vid_h * target_ratio))
                        pad_w += pad_w % 2
                        pad_h += pad_h % 2
                        c_color = (style_data or {}).get("canvas_color", "000000").lstrip("#")
                        vf_filters.append(f"pad={pad_w}:{pad_h}:(ow-iw)/2:(oh-ih)/2:color=0x{c_color}")
            except Exception:
                pass

        # Multi color / text box overlays (rotatable with text)
        all_boxes = []
        if style_data:
            if style_data.get("color_boxes") and isinstance(style_data["color_boxes"], list):
                all_boxes.extend(style_data["color_boxes"])
            if style_data.get("color_box") and isinstance(style_data["color_box"], dict):
                all_boxes.append(style_data["color_box"])

        boxes_png = job.workspace / "boxes_overlay.png"
        has_boxes = False
        if all_boxes:
            try:
                has_boxes = rasterize_color_boxes(all_boxes, vid_w, vid_h, boxes_png)
            except Exception as e:
                print(f"Rasterize color boxes warning: {e}")

        logo_info = (style_data or {}).get("logo") or (style_data or {}).get("image_overlay")
        logo_path = Path(logo_info.get("path") or logo_info.get("image_path", "")) if logo_info else None
        has_logo = bool(logo_path and logo_path.exists())

        input_counter = 2 if has_audio else 1
        boxes_idx = None
        if has_boxes:
            boxes_idx = input_counter
            cmd.extend(["-i", str(boxes_png.resolve())])
            input_counter += 1

        logo_idx = None
        if has_logo:
            logo_idx = input_counter
            cmd.extend(["-i", str(logo_path.resolve())])
            input_counter += 1

        if has_boxes or has_logo:
            base_v = ",".join(vf_filters) if vf_filters else "null"
            cur_v = "[v_base]"
            fc_steps = [f"[0:v]{base_v}{cur_v}"]

            if has_boxes and boxes_idx is not None:
                next_v = "[v_boxes]"
                fc_steps.append(f"{cur_v}[{boxes_idx}:v]overlay=0:0{next_v}")
                cur_v = next_v

            if has_logo and logo_idx is not None:
                pos_choice = str((logo_info or {}).get("position", "top-right")).lower()
                margin = int((logo_info or {}).get("margin", 20))
                scale_pct = float((logo_info or {}).get("scale_pct", 15)) / 100.0
                lw = max(32, int(round(vid_w * scale_pct)))
                lw += lw % 2

                if "top-left" in pos_choice or "trái trên" in pos_choice:
                    ox, oy = f"{margin}", f"{margin}"
                elif "bottom-left" in pos_choice or "trái dưới" in pos_choice:
                    ox, oy = f"{margin}", f"H-h-{margin}"
                elif "bottom-right" in pos_choice or "phải dưới" in pos_choice:
                    ox, oy = f"W-w-{margin}", f"H-h-{margin}"
                else:  # top-right
                    ox, oy = f"W-w-{margin}", f"{margin}"

                fc_steps.append(f"[{logo_idx}:v]scale={lw}:-1[v_logo_scaled]")
                next_v = "[vout]"
                fc_steps.append(f"{cur_v}[v_logo_scaled]overlay={ox}:{oy}{next_v}")
                cur_v = next_v

            cmd.extend(["-filter_complex", ";".join(fc_steps), "-map", cur_v])
        else:
            if vf_filters:
                cmd.extend(["-vf", ",".join(vf_filters)])
            cmd.extend(["-map", "0:v:0"])

        cmd.extend([
            "-map", "1:a:0" if has_audio else "0:a:0?",
            "-c:v", encoder,
            *rate_args,
            "-c:a", "aac",
            "-b:a", "256k",
            "-ar", "48000",
            "-ac", "2",
            str(final_video.resolve()),
        ])

        emit_event(stage_name, 50.0, f"Đang kết xuất video và khắc phụ đề ASS ({encoder})...")

        proc = safe_subprocess_run(
            cmd,
            cwd=str(job.workspace.resolve()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=get_subprocess_env(),
        )

        if proc.returncode == 0:
            try:
                import shutil
                ws_out = job.workspace / "out" / "final.mp4"
                ws_out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(final_video, ws_out)
            except Exception:
                pass
            break
        else:
            last_error_tail = "\n".join(proc.stderr.splitlines()[-10:])
    else:
        raise DubError(
            code="RENDER_FAILED",
            user_message_vi="Lỗi khi xuất video thành phẩm.",
            hint_vi="Kiểm tra lại không gian đĩa trống hoặc codec video đầu vào.",
            details={"stderr": last_error_tail},
        )

    emit_event(stage_name, 100.0, f"Xuất video thành công: {final_video.name}")
    job.finish_stage(stage_name, [str(final_video), str(final_srt)])
