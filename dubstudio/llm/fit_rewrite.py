"""LLM caller for fit_rewrite prompt to adjust length of overflowing/underflowing lines."""
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import emit_event
from dubstudio.text.spoken_cleaner import sanitize_spoken_vietnamese


class FitRewriter:
    def __init__(self, cfg: AppConfig, cache_dir: Optional[Path] = None) -> None:
        raw_prov = getattr(cfg.translation, "provider", None) or os.getenv("TRANSLATION_PROVIDER")
        if raw_prov in ("gemini", "groq", "deepseek", "openrouter", "manual"):
            self.provider = raw_prov
        else:
            self.provider = "gemini_web"

        self.cdp_port = getattr(cfg.translation, "cdp_port", 9222)
        self.api_key = cfg.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.model = cfg.translation.model or "gemini-2.5-flash"
        from dubstudio.paths import get_workspace_dir
        self.cache_dir = cache_dir or (get_workspace_dir() / ".cache" / "llm")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        base_dir = Path(__file__).parent
        self.prompt_template_path = base_dir / "prompts" / "fit_rewrite.md"
        self.cluster_prompt_path = base_dir / "prompts" / "cluster_rewrite.md"

    def _can_use_cdp(self) -> bool:
        from dubstudio.llm.cdp_gemini import is_cdp_ready, find_browser_executable
        return is_cdp_ready(self.cdp_port) or bool(find_browser_executable())

    def rewrite_units(
        self,
        mismatched_units: List[Dict[str, Any]],
        analysis_data: Dict[str, Any],
        pass_idx: int = 1,
        stage_name: str = "fit",
    ) -> List[Dict[str, Any]]:
        """Send all mismatched units in ONE prompt to fit_rewrite.md (two-way length balancing)."""
        if not mismatched_units:
            return []

        can_use_web = (self.provider == "gemini_web" or not self.api_key) and self._can_use_cdp()
        if not self.api_key and not can_use_web:
            emit_event(stage_name, 100.0, "Không có API key hoặc kết nối Gemini Web, bỏ qua viết lại LLM (offline fallback)", level="warning")
            return []

        # Pass-specific urgency directive
        if pass_idx == 1:
            urgency_hdr = (
                "## [LƯỢT 1 - BIÊN KỊCH LỒNG TIẾNG THOÁT Ý & CÂN BẰNG THỜI LƯỢNG THEO SỐ TỪ]:\n"
                "- Đối với câu direction='shorter': Ưu tiên CẤP ĐỘ 1 (Gọt tỉa vi phẫu) nếu words_to_remove <= 4, giữ nguyên 85-90% câu gốc chỉ bớt từ thừa. Nếu words_to_remove >= 5, diễn đạt lại súc tích trong dải [min_words, max_words]. Bắt buộc đếm từ trước khi trả lời và điền tts_word_count.\n"
                "- Đối với câu direction='longer': DỊCH THOÁT Ý ĐẦY ĐỦ, thoáng đạt, tự nhiên để lấp đầy thời lượng nói trên hình (đạt khoảng target_words trong [min_words, max_words]), không bịa sự kiện mới."
            )
        elif pass_idx == 2:
            urgency_hdr = (
                "## [LƯỢT 2 - TINH GỌN VI PHẪU CHUẨN XÁC THEO SỐ TỪ]: Lần trước câu vẫn hơi dài gây đè âm thanh nhẹ vào câu sau! "
                "Hãy bám sát edit_instruction, giữ nguyên khung câu và chỉ cắt bớt đúng số từ mục tiêu, đảm bảo số từ nằm chuẩn trong [min_words, max_words]. "
                "TUYỆT ĐỐI KHÔNG CẮT CỤT CÂU LỦNG CỦNG và KHÔNG ĐƯỢC VIẾT DƯỚI min_words! Nhớ điền tts_word_count."
            )
        else:
            urgency_hdr = (
                f"## [LƯỢT {pass_idx} - CÔ ĐỌNG THOÁT Ý TỐI ƯU]: Tối ưu hóa từ ngữ gãy gọn nhất theo target_words, "
                "câu nói mạch lạc tự nhiên, không cụt lửng, không hở giọng dưới min_words. Nhớ điền tts_word_count."
            )

        def _clean_single_line(s: Any) -> str:
            if not s:
                return ""
            return re.sub(r'\s+', ' ', str(s)).strip()

        # Prepare payload - strictly single-line strings without any \n or extra spaces
        payload_items = []
        for u in mismatched_units:
            prev_str = _clean_single_line(u.get("prev_vi", ""))
            next_str = _clean_single_line(u.get("next_vi", ""))
            ctx = []
            if prev_str:
                ctx.append(f"Liền trước: '{prev_str}'")
            if next_str:
                ctx.append(f"Liền sau: '{next_str}'")
            context_str = " | ".join(ctx) if ctx else "Ngữ cảnh hội thoại"

            tts_clean = _clean_single_line(u.get("tts_text") or u.get("vi_text", ""))
            curr_words = u.get("current_words")
            if curr_words is None:
                curr_words = len(tts_clean.split()) if tts_clean else 0

            tgt_words = u.get("target_words", max(2, curr_words - 1))
            min_w = u.get("min_words", max(2, tgt_words - 1))
            max_w = u.get("max_words", min_w + 2)
            direction = u.get("direction", "shorter")

            words_to_remove = u.get("words_to_remove")
            if words_to_remove is None and direction == "shorter":
                words_to_remove = max(1, curr_words - tgt_words)

            edit_instr = u.get("edit_instruction", "")
            if not edit_instr:
                if direction == "shorter":
                    if words_to_remove is not None and words_to_remove <= 3:
                        edit_instr = f"CHỈ CẦN LƯỢC BỎ ĐÚNG {words_to_remove} TỪ ĐỆM/TỪ THỪA. Giữ nguyên 85-90% câu gốc, TUYỆT ĐỐI KHÔNG tóm tắt hay viết lại toàn bộ câu!"
                    else:
                        edit_instr = f"Viết lại câu súc tích hơn để giảm từ {curr_words} từ xuống đúng khoảng {min_w}-{max_w} từ (mục tiêu {tgt_words} từ). Không được viết ngắn dưới {min_w} từ!"
                else:
                    words_to_add = u.get("words_to_add", max(1, tgt_words - curr_words))
                    edit_instr = f"Mở rộng câu tự nhiên thêm khoảng {words_to_add} từ, tăng từ {curr_words} từ lên khoảng {min_w}-{max_w} từ (mục tiêu {tgt_words} từ). Không bịa thêm sự kiện mới!"

            item_payload = {
                "id": u["id"],
                "zh": _clean_single_line(u.get("zh", "")),
                "vi_text": _clean_single_line(u.get("vi_text", "")),
                "tts_text": tts_clean,
                "current_words": curr_words,
                "target_words": tgt_words,
                "min_words": min_w,
                "max_words": max_w,
                "measured_dur": u.get("measured_dur", 0.0),
                "max_audio_dur": u.get("max_audio_dur", 1.0),
                "direction": direction,
                "edit_instruction": edit_instr,
                "min_chars": u.get("min_chars", max(8, int(u.get("target_chars", 25) * 0.85))),
                "target_chars": u.get("target_chars", 25),
                "max_chars": u.get("max_chars", max(10, int(u.get("target_chars", 25) * 1.10))),
                "context": context_str,
            }
            if direction == "shorter":
                item_payload["words_to_remove"] = words_to_remove
            else:
                item_payload["words_to_add"] = u.get("words_to_add", max(1, tgt_words - curr_words))

            payload_items.append(item_payload)

        content_str = json.dumps(payload_items, ensure_ascii=False, indent=2)
        template_text = ""
        if self.prompt_template_path.exists():
            template_text = self.prompt_template_path.read_text(encoding="utf-8")
        elif self.cluster_prompt_path.exists():
            template_text = self.cluster_prompt_path.read_text(encoding="utf-8")

        filled_prompt = f"{urgency_hdr}\n\n" + template_text.replace(
            "{{analysis_json}}", json.dumps(analysis_data or {}, ensure_ascii=False, indent=2)
        )
        filled_prompt = filled_prompt.replace("{{lines_json}}", content_str)
        filled_prompt = filled_prompt.replace("{{cluster_json}}", content_str)

        mismatched_ids = [u["id"] for u in mismatched_units]
        emit_event(stage_name, 30.0, f"Đang gửi {len(mismatched_units)} câu lệch #{mismatched_ids} (Lượt {pass_idx}) để cân bằng độ dài trong 1 yêu cầu duy nhất...")

        def _normalize_items(raw_items: Any) -> List[Dict[str, Any]]:
            if not raw_items:
                return []
            if isinstance(raw_items, dict):
                raw_items = (
                    raw_items.get("rewritten_segments")
                    or raw_items.get("lines")
                    or raw_items.get("rewritten")
                    or raw_items.get("translations")
                    or raw_items.get("segments")
                    or [raw_items]
                )
            if not isinstance(raw_items, list):
                return []
            out = []
            for it in raw_items:
                if not isinstance(it, dict):
                    continue
                sid = it.get("id")
                if sid is None:
                    continue
                vi_val = it.get("vi_text") or it.get("vi") or it.get("text") or it.get("shortened_vi") or ""
                tts_val = it.get("tts_text") or it.get("tts") or it.get("spoken_text") or vi_val
                word_cnt = it.get("tts_word_count") or it.get("word_count")
                parsed_wc = int(word_cnt) if (word_cnt is not None and str(word_cnt).isdigit()) else len(str(tts_val).split())
                out.append({
                    "id": int(sid),
                    "vi_text": _clean_single_line(sanitize_spoken_vietnamese(str(vi_val).strip())),
                    "tts_text": _clean_single_line(sanitize_spoken_vietnamese(str(tts_val).strip())),
                    "tts_word_count": parsed_wc,
                })
            return out

        try:
            if self.provider == "gemini_web" or (not self.api_key and can_use_web):
                from dubstudio.llm.cdp_gemini import translate_via_cdp
                raw_items = translate_via_cdp(filled_prompt, port=self.cdp_port)
                items = _normalize_items(raw_items)
                if items:
                    return items

            if self.api_key:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": filled_prompt}]}],
                    "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
                }
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    res_json = resp.json()
                    text_content = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    data = json.loads(text_content)
                    items = _normalize_items(data)
                    if items:
                        return items
                else:
                    emit_event(stage_name, 100.0, f"API trả về mã {resp.status_code}, giữ nguyên lời thoại", level="warning")
                    return []
            return []
        except Exception as e:
            emit_event(stage_name, 100.0, f"Lỗi khi viết lại lời thoại: {e}", level="warning")
            return []

    def rewrite_cluster(
        self,
        cluster_segments: List[Dict[str, Any]],
        analysis_data: Dict[str, Any],
        pass_idx: int = 1,
        stage_name: str = "fit",
    ) -> List[Dict[str, Any]]:
        """Rewrite colliding segments in a coherent cluster of surrounding sentences."""
        if not cluster_segments:
            return []

        colliding = [s for s in cluster_segments if s.get("is_colliding")]
        if not colliding:
            return []

        can_use_web = (self.provider == "gemini_web" or not self.api_key) and self._can_use_cdp()
        if not self.api_key and not can_use_web:
            emit_event(stage_name, 100.0, "Không có API key hoặc kết nối Gemini Web, bỏ qua viết lại chùm câu (offline fallback)", level="warning")
            return []

        template_text = ""
        if self.cluster_prompt_path.exists():
            template_text = self.cluster_prompt_path.read_text(encoding="utf-8")
        elif self.prompt_template_path.exists():
            template_text = self.prompt_template_path.read_text(encoding="utf-8")

        # Pass-specific urgency directive
        if pass_idx == 1:
            urgency_hdr = (
                "## [LƯỢT 1 - BIÊN KỊCH THOÁT Ý CHÙM CÂU]: Rút gọn các câu có is_colliding: true bằng cách DỊCH THOÁT Ý CÔ ĐỌNG, "
                "độ dài nằm trong khoảng [min_chars, max_chars] (xấp xỉ target_chars). "
                "TUYỆT ĐỐI KHÔNG CẮT CỤT LỦNG CỦNG và KHÔNG ĐƯỢC VIẾT DƯỚI min_chars để tránh bị hở khoảng lặng quá nhiều so với giọng gốc."
            )
        elif pass_idx == 2:
            urgency_hdr = (
                "## [LƯỢT 2 - TINH GỌN THOÁT Ý CHUẨN XÁC]: Lần trước câu vẫn bị dài và đè âm thanh vào câu sau! "
                "Hãy dùng tài năng biên kịch tìm cách diễn đạt khác thoát ý hơn, cô đọng hơn theo target_chars, "
                "TUYỆT ĐỐI KHÔNG VIẾT DƯỚI min_chars và giữ tính tự nhiên, mạch lạc của cả chùm câu!"
            )
        else:
            urgency_hdr = (
                f"## [LƯỢT {pass_idx} - CÔ ĐỌNG THOÁT Ý TỐI ƯU]: Tối ưu hóa từ ngữ gãy gọn, súc tích nhất theo target_chars, "
                "câu nói mạch lạc tự nhiên, không cụt lửng, không hở giọng dưới min_chars."
            )

        # Format cluster items
        payload_items = []
        for s in cluster_segments:
            t_chars = s.get("target_chars", 0)
            payload_items.append({
                "id": s["id"],
                "zh": s.get("zh") or s.get("src_text", ""),
                "vi_text": s.get("vi_text", ""),
                "tts_text": s.get("tts_text", ""),
                "is_colliding": bool(s.get("is_colliding")),
                "measured_dur": s.get("tts_dur", 0.0),
                "max_audio_dur": s.get("max_audio_dur", 0.0),
                "min_chars": s.get("min_chars", max(8, int(t_chars * 0.85)) if t_chars > 0 else 0),
                "target_chars": t_chars,
                "max_chars": s.get("max_chars", max(10, int(t_chars * 1.10)) if t_chars > 0 else 0),
            })

        cluster_str = json.dumps(payload_items, ensure_ascii=False, indent=2)
        filled_prompt = f"{urgency_hdr}\n\n" + template_text.replace(
            "{{analysis_json}}", json.dumps(analysis_data or {}, ensure_ascii=False, indent=2)
        )
        filled_prompt = filled_prompt.replace("{{cluster_json}}", cluster_str)
        filled_prompt = filled_prompt.replace("{{lines_json}}", cluster_str)

        colliding_ids = [s["id"] for s in colliding]
        emit_event(stage_name, 35.0, f"Đang gửi chùm câu chứa đoạn #{colliding_ids} (Lượt {pass_idx}) để viết lại theo ngữ cảnh...")

        def _normalize_items(raw_items: Any) -> List[Dict[str, Any]]:
            if not raw_items:
                return []
            if isinstance(raw_items, dict):
                raw_items = (
                    raw_items.get("rewritten_segments")
                    or raw_items.get("rewritten")
                    or raw_items.get("translations")
                    or raw_items.get("lines")
                    or raw_items.get("segments")
                    or [raw_items]
                )
            if not isinstance(raw_items, list):
                return []
            out = []
            for it in raw_items:
                if not isinstance(it, dict):
                    continue
                sid = it.get("id")
                if sid is None:
                    continue
                vi_val = it.get("vi_text") or it.get("vi") or it.get("text") or it.get("shortened_vi") or ""
                tts_val = it.get("tts_text") or it.get("tts") or it.get("spoken_text") or vi_val
                out.append({
                    "id": int(sid),
                    "vi_text": sanitize_spoken_vietnamese(str(vi_val).strip()),
                    "tts_text": sanitize_spoken_vietnamese(str(tts_val).strip()),
                })
            return out

        try:
            if self.provider == "gemini_web" or (not self.api_key and can_use_web):
                from dubstudio.llm.cdp_gemini import translate_via_cdp
                raw_items = translate_via_cdp(filled_prompt, port=self.cdp_port)
                items = _normalize_items(raw_items)
                if items:
                    return items

            if self.api_key:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": filled_prompt}]}],
                    "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
                }
                with httpx.Client(timeout=45.0) as client:
                    resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    res_json = resp.json()
                    text_content = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    data = json.loads(text_content)
                    items = _normalize_items(data)
                    if items:
                        return items
        except Exception as e:
            emit_event(stage_name, 35.0, f"Lỗi khi viết lại chùm câu: {e}", level="warning")

        return []
