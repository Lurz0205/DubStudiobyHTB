"""Diagnostic sync report script for dubstudio jobs."""
import json
from pathlib import Path
import statistics
import sys

# Windows UTF-8 stdout
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "clip_1min"
    matching_dirs = list(Path("workspace").glob(f"{target}*"))
    if not matching_dirs:
        print(f"Không tìm thấy job workspace cho: {target}")
        return

    job_dir = matching_dirs[0]
    seg_file = job_dir / "segments.json"
    plan_file = job_dir / "fit_plan.json"

    if not seg_file.exists():
        print(f"Không tìm thấy segments.json tại {job_dir}")
        return

    data = json.loads(seg_file.read_text(encoding="utf-8"))
    segments = data.get("segments", [])

    plan_map = {}
    if plan_file.exists():
        plan_list = json.loads(plan_file.read_text(encoding="utf-8"))
        plan_map = {item["id"]: item for item in plan_list}

    print(f"=== BÁO CÁO ĐỒNG BỘ KHỚP TIẾNG-HÌNH (Job: {job_dir.name}) ===")
    print("id | src_start | src_end | slot_len | zh_chars | vi_chars | speech_time | coverage | tts_dur | fill | rate")

    coverages = []
    fill_outliers = 0
    total_segments = len(segments)

    for s in segments[:15]:
        sid = s["id"]
        st = s["start"]
        en = s["end"]
        slot_len = max(0.01, round(en - st, 3))
        zh_chars = len(s.get("src_text", ""))
        vi_chars = len(s.get("vi_text", ""))

        # speech_time: sum of word durations if present, else fallback to slot_len
        sp_time = s.get("speech_time")
        if sp_time is None:
            sp_time = slot_len
        sp_time = max(0.01, round(sp_time, 3))

        coverage = round(sp_time / slot_len, 3)
        coverages.append(coverage)

        tdur = s.get("tts_dur") or 0.0
        fill = round(tdur / sp_time, 3) if sp_time > 0 else 0.0

        if fill < 0.7 or fill > 1.2:
            fill_outliers += 1

        rate = plan_map.get(sid, {}).get("fit", {}).get("rate", 1.0) or 1.0

        print(f"{sid} | {st:.2f}s | {en:.2f}s | {slot_len:.2f}s | {zh_chars} | {vi_chars} | {sp_time:.2f}s | {coverage:.2f} | {tdur:.2f}s | {fill:.2f} | {rate:.2f}x")

    # Full stats over all segments
    all_coverages = []
    all_fill_outliers = 0
    for s in segments:
        sl = max(0.01, round(s["end"] - s["start"], 3))
        sp = s.get("speech_time") or sl
        cov = sp / sl
        all_coverages.append(cov)
        td = s.get("tts_dur") or 0.0
        fl = td / sp if sp > 0 else 0.0
        if fl < 0.7 or fl > 1.2:
            all_fill_outliers += 1

    median_cov = statistics.median(all_coverages) if all_coverages else 0.0

    print("---")
    print(f"Tổng số segment: {total_segments}")
    print(f"Coverage trung vị (speech_time / slot_len): {median_cov:.2f}")
    print(f"Số segment có fill < 0.7 hoặc fill > 1.2: {all_fill_outliers}/{total_segments}")


if __name__ == "__main__":
    main()
