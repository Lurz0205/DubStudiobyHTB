"""Stage: analyze. Performs global video context analysis (genre, setting, characters, glossary)."""
import json
from pathlib import Path
from dubstudio.config import AppConfig
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash


def run(job: JobContext, cfg: AppConfig) -> None:
    stage_name = "analyze"
    emit_event(stage_name, 0.0, "Bắt đầu phân tích bối cảnh toàn bộ video (analyze)")

    units_file = job.workspace / "units.json"
    if not units_file.exists():
        units_file = job.workspace / "segments.json"

    analysis_file = job.workspace / "analysis.json"
    input_hash = compute_file_hash(units_file)
    if job.is_stage_done(stage_name, input_hash) or (analysis_file.exists() and analysis_file.stat().st_size > 10):
        emit_event(stage_name, 100.0, "Giai đoạn analyze đã hoàn thành (bỏ qua)")
        job.finish_stage(stage_name, ["analysis.json"])
        return

    job.start_stage(stage_name, input_hash)

    # Build full transcript text
    with open(units_file, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    items = file_data if isinstance(file_data, list) else file_data.get("segments", [])
    full_zh_lines = [
        str(u.get("zh") or u.get("src_text") or "").strip()
        for u in items
        if str(u.get("zh") or u.get("src_text") or "").strip()
    ]
    full_zh_text = "\n".join(full_zh_lines)[:12000]

    # Provide safe default analysis schema
    analysis_data = {
        "genre": "khoa học / đời sống / khám phá",
        "summary": "Video thuyết minh giải thích hiện tượng và đời sống thực tế.",
        "default_address": "tôi - các bạn",
        "characters": [
            {"id": "narrator", "name": "Người dẫn chuyện", "gender": "female", "role": "thuyết minh"}
        ],
        "tone": "tự nhiên, thân mật, cuốn hút, đời thường",
        "glossary": [],
    }

    # Attempt AI global context analysis if Gemini is available
    import os
    api_key = cfg.gemini_api_key or os.getenv("GEMINI_API_KEY")

    if api_key and full_zh_text:
        try:
            emit_event(stage_name, 30.0, "Đang phân tích tổng thể chủ đề, xưng hô và thuật ngữ video bằng AI...")
            import httpx
            prompt = (
                "Bạn là chuyên gia phân tích kịch bản video phim Trung - Việt xuất sắc.\n"
                "Hãy đọc toàn bộ lời thoại tiếng Trung dưới đây của video và phân tích tổng quan để phục vụ dịch thuật & lồng tiếng:\n"
                "1. genre: thể loại/chủ đề chính (ví dụ: khoa học, thí nghiệm, chế tạo, ẩm thực, v.v.).\n"
                "2. summary: tóm tắt nội dung chính trong 2-3 câu ngắn gọn.\n"
                "3. default_address: chỉ dùng cặp đại từ nhân xưng thông dụng (ví dụ: 'tôi - các bạn' hoặc 'mình - mọi người'). TUYỆT ĐỐI KHÔNG dùng tên riêng, biệt danh hoặc tên kênh (cấm tuyệt đối 'Tinh Hà', 'Bilibili'...). \n"
                "4. tone: tông giọng diễn đạt phù hợp nhất (ví dụ: 'hào hứng, giải thích khoa học đời thường, dễ hiểu').\n"
                "5. glossary: mảng gồm tối đa 20 thuật ngữ khoa học, chuyên ngành, vật liệu hoặc tên riêng xuất hiện trong video dịch chuẩn sang tiếng Việt: [{\"zh\": \"...\", \"vi\": \"...\"}].\n\n"
                f"LỜI THOẠI TOÀN BỘ VIDEO:\n{full_zh_text}\n\n"
                "Chỉ trả về duy nhất JSON hợp lệ theo định dạng:\n"
                "{\n"
                '  "genre": "...",\n'
                '  "summary": "...",\n'
                '  "default_address": "...",\n'
                '  "tone": "...",\n'
                '  "glossary": [{"zh": "...", "vi": "..."}]\n'
                "}"
            )
            raw_text = None
            if api_key:
                model = cfg.translation.model if "gemini" in cfg.translation.model else "gemini-2.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
                }
                with httpx.Client(timeout=45.0) as client:
                    resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

            if raw_text:
                parsed = json.loads(raw_text)
                if isinstance(parsed, dict):
                    analysis_data.update(parsed)
        except Exception:
            pass

    # Sanitize default_address
    addr = str(analysis_data.get("default_address", "")).replace("-", " ").strip()
    for bad in ["Tinh Hà", "Bilibili", "Douyin", "Kênh", "Channel"]:
        addr = addr.replace(bad, "").strip()
    if not addr or len(addr) < 2:
        addr = "tôi - các bạn"
    analysis_data["default_address"] = addr

    analysis_file = job.workspace / "analysis.json"
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis_data, f, ensure_ascii=False, indent=2)

    emit_event(stage_name, 100.0, f"Phân tích bối cảnh hoàn tất ({analysis_data.get('genre', 'chủ đề chung')})")
    job.finish_stage(stage_name, ["analysis.json"])
