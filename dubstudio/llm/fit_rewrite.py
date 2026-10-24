"""LLM caller for fit_rewrite prompt to adjust length of overflowing/underflowing lines."""
import hashlib
import json
import os
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
        self.cache_dir = cache_dir or Path("workspace/.cache/llm")
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
                "## [LƯỢT 1 - CÂN BẰNG THOẠI HAI CHIỀU]:\n"
                "- Đối với câu direction='shorter': RÚT GỌN ngắn gọn hơn để số ký tự xấp xỉ hoặc dưới target_chars, loại bỏ từ đệm thừa.\n"
                "- Đối với câu direction='longer': THOÁT Ý diễn đạt đầy đủ và thoáng hơn để câu nói tự nhiên khớp với thời lượng người nói trên hình (target_chars), không dịch cộc lốc nhưng không bịa sự kiện mới."
            )
        elif pass_idx == 2:
            urgency_hdr = (
                "## [LƯỢT 2 - YÊU CẦU RÚT GỌN MẠNH HƠN]: Lần trước câu vẫn bị dài và đè âm thanh vào câu sau! "
                "BẮT BUỘC phải viết ngắn gọn hơn nữa, lược bỏ triệt để từ ngữ rườm rà và từ đệm thừa, giữ số ký tự dưới target_chars!"
            )
        else:
            urgency_hdr = (
                f"## [LƯỢT {pass_idx} - RÚT GỌN TỐI ĐA]: Câu vẫn đang bị đè âm thanh nghiêm trọng! "
                "BẮT BUỘC phải cô đọng tối đa, viết câu siêu ngắn gọn và súc tích nhất có thể nhưng giữ ý chính!"
            )

        # Prepare payload
        payload_items = []
        for u in mismatched_units:
            ctx = []
            if u.get("prev_vi"):
                ctx.append(f"Liền trước: '{u['prev_vi']}'")
            if u.get("next_vi"):
                ctx.append(f"Liền sau: '{u['next_vi']}'")
            context_str = " | ".join(ctx) if ctx else "Ngữ cảnh hội thoại"

            payload_items.append({
                "id": u["id"],
                "zh": u.get("zh", ""),
                "vi_text": u.get("vi_text", ""),
                "tts_text": u.get("tts_text", ""),
                "measured_dur": u.get("measured_dur", 0.0),
                "max_audio_dur": u.get("max_audio_dur", 1.0),
                "direction": u.get("direction", "shorter"),
                "target_chars": u.get("target_chars", 25),
                "context": context_str,
            })

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
            urgency_hdr = "## [LƯỢT 1]: Rút gọn các câu có is_colliding: true để số ký tự xấp xỉ hoặc dưới target_chars."
        elif pass_idx == 2:
            urgency_hdr = (
                "## [LƯỢT 2 - YÊU CẦU RÚT GỌN MẠNH HƠN]: Lần trước câu vẫn bị dài và đè âm thanh vào câu sau! "
                "BẮT BUỘC phải viết ngắn gọn hơn nữa, lược bỏ triệt để từ ngữ rườm rà và từ đệm thừa, giữ số ký tự dưới target_chars!"
            )
        else:
            urgency_hdr = (
                f"## [LƯỢT {pass_idx} - RÚT GỌN TỐI ĐA]: Câu vẫn đang bị đè âm thanh nghiêm trọng! "
                "BẮT BUỘC phải cô đọng tối đa, viết câu siêu ngắn gọn và súc tích nhất có thể nhưng giữ ý chính!"
            )

        # Format cluster items
        payload_items = []
        for s in cluster_segments:
            payload_items.append({
                "id": s["id"],
                "zh": s.get("zh") or s.get("src_text", ""),
                "vi_text": s.get("vi_text", ""),
                "tts_text": s.get("tts_text", ""),
                "is_colliding": bool(s.get("is_colliding")),
                "measured_dur": s.get("tts_dur", 0.0),
                "max_audio_dur": s.get("max_audio_dur", 0.0),
                "target_chars": s.get("target_chars", 0),
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
