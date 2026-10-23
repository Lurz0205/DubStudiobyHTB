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
        self.provider = getattr(cfg.translation, "provider", None) or os.getenv("TRANSLATION_PROVIDER")
        self.cdp_port = getattr(cfg.translation, "cdp_port", 9222)
        self.api_key = cfg.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.model = cfg.translation.model or "gemini-2.5-flash"
        self.cache_dir = cache_dir or Path("workspace/.cache/llm")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_template_path = Path("dubstudio/llm/prompts/fit_rewrite.md")
        self.cluster_prompt_path = Path("dubstudio/llm/prompts/cluster_rewrite.md")

    def _can_use_cdp(self) -> bool:
        from dubstudio.llm.cdp_gemini import is_cdp_ready
        return is_cdp_ready(self.cdp_port)

    def rewrite_units(
        self,
        mismatched_units: List[Dict[str, Any]],
        analysis_data: Dict[str, Any],
        stage_name: str = "fit_rewrite",
    ) -> List[Dict[str, Any]]:
        """Send all mismatched units in ONE prompt to fit_rewrite.md."""
        if not mismatched_units:
            return []

        can_use_web = (self.provider == "gemini_web" or not self.api_key) and self._can_use_cdp()
        if not self.api_key and not can_use_web:
            emit_event(stage_name, 100.0, "Không có API key hoặc kết nối Gemini Web, bỏ qua viết lại LLM (offline fallback)", level="warning")
            return mismatched_units

        # Prepare payload
        payload_items = []
        for u in mismatched_units:
            payload_items.append({
                "id": u["id"],
                "zh": u.get("zh", ""),
                "vi_text": u.get("vi_text", ""),
                "tts_text": u.get("tts_text", ""),
                "measured_dur": u.get("tts_dur", 0.0),
                "dur": u.get("dur", 1.0),
                "direction": u.get("direction", "shorter"),
                "target_chars": u.get("target_chars", 20),
                "min_chars": u.get("min_chars", 15),
                "max_chars": u.get("max_chars", 30),
                "prev_lines": u.get("prev_lines", []),
                "next_lines": u.get("next_lines", []),
                "prev_vi": u.get("prev_vi", ""),
                "next_vi": u.get("next_vi", ""),
            })

        content_str = json.dumps(payload_items, ensure_ascii=False, indent=2)
        prompt_hash = hashlib.sha256((self.model + ":rewrite:" + content_str).encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{prompt_hash}.json"

        if cache_file.exists():
            emit_event(stage_name, 100.0, "Sử dụng bản viết lại từ cache")
            return json.loads(cache_file.read_text(encoding="utf-8"))

        template_text = self.prompt_template_path.read_text(encoding="utf-8")
        filled_prompt = template_text.replace("{{analysis_json}}", json.dumps(analysis_data, ensure_ascii=False, indent=2))
        filled_prompt = filled_prompt.replace("{{lines_json}}", content_str)

        try:
            emit_event(stage_name, 50.0, f"Đang gửi {len(mismatched_units)} đơn vị lệch để viết lại khớp thời lượng...")

            if self.provider == "gemini_web" or (not self.api_key and can_use_web):
                from dubstudio.llm.cdp_gemini import translate_via_cdp
                lines = translate_via_cdp(filled_prompt, port=self.cdp_port)
                if lines:
                    for l in lines:
                        if "vi_text" in l:
                            l["vi_text"] = sanitize_spoken_vietnamese(l["vi_text"])
                        if "tts_text" in l:
                            l["tts_text"] = sanitize_spoken_vietnamese(l["tts_text"])
                    cache_file.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding="utf-8")
                    return lines

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
                    lines = data.get("lines", []) or data.get("rewritten_segments", [])
                    for l in lines:
                        if "vi_text" in l:
                            l["vi_text"] = sanitize_spoken_vietnamese(l["vi_text"])
                        if "tts_text" in l:
                            l["tts_text"] = sanitize_spoken_vietnamese(l["tts_text"])
                    cache_file.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding="utf-8")
                    return lines
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
        filled_prompt = template_text.replace("{{analysis_json}}", json.dumps(analysis_data or {}, ensure_ascii=False, indent=2))
        filled_prompt = filled_prompt.replace("{{cluster_json}}", cluster_str)
        filled_prompt = filled_prompt.replace("{{lines_json}}", cluster_str)

        colliding_ids = [s["id"] for s in colliding]
        emit_event(stage_name, 35.0, f"Đang gửi chùm câu chứa đoạn #{colliding_ids} để viết lại theo ngữ cảnh...")

        try:
            if self.provider == "gemini_web" or (not self.api_key and can_use_web):
                from dubstudio.llm.cdp_gemini import translate_via_cdp
                items = translate_via_cdp(filled_prompt, port=self.cdp_port)
                if items:
                    for it in items:
                        if "vi_text" in it:
                            it["vi_text"] = sanitize_spoken_vietnamese(it["vi_text"])
                        if "tts_text" in it:
                            it["tts_text"] = sanitize_spoken_vietnamese(it["tts_text"])
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
                    items = (
                        data.get("rewritten_segments")
                        or data.get("rewritten")
                        or data.get("lines")
                        or (data if isinstance(data, list) else [])
                    )
                    if items:
                        for it in items:
                            if "vi_text" in it:
                                it["vi_text"] = sanitize_spoken_vietnamese(it["vi_text"])
                            if "tts_text" in it:
                                it["tts_text"] = sanitize_spoken_vietnamese(it["tts_text"])
                        return items
        except Exception as e:
            emit_event(stage_name, 35.0, f"Lỗi khi viết lại chùm câu: {e}", level="warning")

        return []
