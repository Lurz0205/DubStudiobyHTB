"""Google Gemini API translation client with cascade failover, rate limiting, and prompt caching."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Optional
import httpx
from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import emit_event


def build_prompt(
    batch_units: List[Dict[str, Any]],
    all_units: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
    style: Optional[str] = None,
    story_so_far: Optional[str] = None,
    task_type: str = "translate",
) -> tuple[str, str]:
    """
    Construct concise translation prompt focused on natural spoken dialogue
    and clean JSON output (glossary table omitted as instructed).
    """
    context = context or {}
    genre = context.get("genre", "")
    summary = context.get("summary") or context.get("topic") or ""
    characters = context.get("characters", [])
    tone = context.get("tone", "")

    # Analysis context
    analysis_lines = []
    if genre:
        analysis_lines.append(f"- Thể loại: {genre}")
    if summary:
        analysis_lines.append(f"- Tóm tắt nội dung: {summary}")
    if tone:
        analysis_lines.append(f"- Giọng điệu/Phong cách: {tone}")
    if characters:
        char_strs = [f"{c.get('name', '')} ({c.get('role', '')})" for c in characters if isinstance(c, dict)]
        if char_strs:
            analysis_lines.append(f"- Nhân vật: {', '.join(char_strs)}")
    analysis_block = "\n".join(analysis_lines) if analysis_lines else ""

    story_block = story_so_far or summary or ""

    first_id = batch_units[0]["id"] if batch_units else None
    first_idx = 0
    if first_id is not None and all_units:
        for idx, u in enumerate(all_units):
            if u.get("id") == first_id:
                first_idx = idx
                break

    last_id = batch_units[-1]["id"] if batch_units else None
    last_idx = len(all_units) - 1 if all_units else 0
    if last_id is not None and all_units:
        for idx, u in enumerate(all_units):
            if u.get("id") == last_id:
                last_idx = idx
                break

    num_prev = min(5, first_idx)
    num_next = min(5, max(0, len(all_units) - 1 - last_idx))

    # If total surrounding < 5 and more units are available, expand
    total_surrounding = num_prev + num_next
    if total_surrounding < 5 and all_units:
        needed = 5 - total_surrounding
        extra_next = min(needed, max(0, len(all_units) - 1 - last_idx - num_next))
        num_next += extra_next
        needed = 5 - (num_prev + num_next)
        extra_prev = min(needed, max(0, first_idx - num_prev))
        num_prev += extra_prev

    prev_units = all_units[first_idx - num_prev:first_idx] if num_prev > 0 else []
    next_units = all_units[last_idx + 1:last_idx + 1 + num_next] if num_next > 0 else []

    prev_entries = []
    for pu in prev_units:
        p_id = pu.get("id")
        p_vi = pu.get("vi_text") or pu.get("tts_text") or pu.get("vi") or ""
        p_zh = pu.get("zh") or pu.get("src_text") or ""
        if p_vi and p_zh:
            prev_entries.append(f"#{p_id}: {p_vi} (Gốc: {p_zh})")
        elif p_vi:
            prev_entries.append(f"#{p_id}: {p_vi}")
        elif p_zh:
            prev_entries.append(f"#{p_id} (ZH): {p_zh}")
    prev_block = "\n".join(prev_entries) if prev_entries else "Không có (bắt đầu đoạn hội thoại)."

    next_entries = []
    for nu in next_units:
        n_id = nu.get("id")
        n_zh = nu.get("zh") or nu.get("src_text") or ""
        if n_zh:
            next_entries.append(f"#{n_id} (ZH): {n_zh}")
    next_block = "\n".join(next_entries) if next_entries else ""

    task_note = ""
    if task_type == "retry":
        task_note = "\nLƯU Ý: Đây là yêu cầu DỊCH BÙ cho các ID chưa hoàn thành. Hãy đảm bảo trả về đầy đủ các ID được yêu cầu.\n"
    elif task_type == "polish":
        task_note = "\nLƯU Ý: Đây là yêu cầu DỊCH LẠI để liền mạch câu thoại. Dịch trọn vẹn không để đứt vế.\n"
    elif task_type == "split":
        task_note = "\nLƯU Ý: Đây là khối chia nhỏ để tránh timeout. Dịch chuẩn xác các ID trong danh sách.\n"

    sections = [
        f"Bạn là biên kịch lồng tiếng video chuyên nghiệp. Dịch lời thoại tiếng Trung sang tiếng Việt tự nhiên cho người đọc lồng tiếng (TTS).\nVăn phong: Lời nói tự nhiên, gần gũi, đời thường ({style or 'Tự nhiên, đời thường'}).{task_note}"
    ]

    if analysis_block:
        sections.append(f"## Bối cảnh phân tích (Analysis):\n{analysis_block}")
    if story_block:
        sections.append(f"## Tóm tắt diễn biến (Story so far):\n{story_block}")

    sections.append(f"## Các đơn vị liền trước đã dịch (prev_lines - tối đa 5 câu, để nối mạch xưng hô, KHÔNG dịch lại):\n{prev_block}")
    if next_block:
        sections.append(f"## Các đơn vị kế tiếp (next_lines - tối đa 5 câu, CHỈ ĐỂ HIỂU NGỮ CẢNH, TUYỆT ĐỐI KHÔNG DỊCH):\n{next_block}")

    sections.append("""## NGUYÊN TẮC DỊCH BẮT BUỘC:
1. ƯU TIÊN SỐ 1 - TỰ NHIÊN, DỄ HIỂU, ĐỜI THƯỜNG: Dịch thành câu thoại tự nhiên, mượt mà như người Việt trò chuyện hàng ngày. Tuyệt đối tránh văn dịch thô cứng, gượng gạo, tối nghĩa hoặc nặng mùi Hán-Việt. Người xem nghe là hiểu ngay ý chính và cảm xúc của nhân vật.
2. XỬ LÝ LỜI THOẠI NÓI NHANH, DÀY CHỮ: Với các đoạn tiếng Trung nói nhanh, dày đặc từ ngữ: HÃY DỊCH THOÁT Ý, GÃY GỌN, CÔ ĐỌNG. Lược bỏ các chi tiết vụn vặt hoặc từ ngữ rườm rà, tập trung truyền tải đúng nội dung cốt lõi và sắc thái nhân vật; tuyệt đối không nhồi nhét từng chữ Hán khiến câu dịch bị trúc trắc, khó hiểu.
3. NHỊP ĐIỆU LỒNG TIẾNG VỪA VẶN: Câu dịch có độ dài vừa vặn với nhịp hình và thời lượng `dur_sec`, không mở đầu hoặc kết thúc bằng dấu '...', không để lửng câu, không dông dài thừa thãi khiến giọng đọc bị dồn ép.

ĐỊNH DẠNG ĐẦU RA:
Chỉ trả về DUY NHẤT một JSON object có dạng:
{"translations": [{"id": 1, "vi": "lời thoại tiếng Việt"}]}""")

    system_instruction = "\n\n".join(sections)

    payload_items = []
    for item in batch_units:
        dur = float(item.get("dur") or item.get("dur_sec") or 0.0)
        p_item = {
            "id": item["id"],
            "zh": item.get("zh") or item.get("src_text", ""),
        }
        if dur > 0:
            p_item["dur_sec"] = round(dur, 2)
        payload_items.append(p_item)

    content_str = json.dumps(payload_items, ensure_ascii=False, indent=2)
    return system_instruction, content_str


class GeminiTranslator:
    def __init__(self, cfg: AppConfig, cache_dir: Optional[Path] = None) -> None:
        # Determine primary provider: default is gemini_web, but respect explicit config
        raw_prov = getattr(cfg.translation, "provider", None) or os.getenv("TRANSLATION_PROVIDER")
        if raw_prov == "manual":
            self.provider = "manual"
        elif raw_prov == "gemini_web":
            self.provider = "gemini_web"
        elif cfg.translation.model and "gemini" in str(cfg.translation.model).lower() and cfg.translation.model != "gemini_web":
            self.provider = "gemini"
        elif raw_prov in ("deepseek", "openrouter"):
            self.provider = raw_prov
        else:
            self.provider = "gemini_web"

        self.api_key = cfg.gemini_api_key or os.getenv("GEMINI_API_KEY")

        if self.provider not in ("gemini_web", "manual") and not self.api_key:
            raise DubError(
                code="API_KEY_MISSING",
                user_message_vi="Chưa cấu hình GEMINI_API_KEY trong tệp .env hoặc mục Cài đặt.",
                hint_vi="Thêm dòng GEMINI_API_KEY=... vào tệp .env ở thư mục gốc hoặc dùng chế độ Gemini Web / Tự dịch thủ công.",
            )

        self.model = cfg.translation.model or "gemini-2.5-flash"

        self.fallback_models = getattr(cfg.translation, "fallback_models", [])
        self.auto_fallback = getattr(cfg.translation, "auto_fallback", False)
        self.backup_api_key = getattr(cfg.translation, "backup_gemini_api_key", None) or cfg.backup_gemini_api_key or os.getenv("BACKUP_GEMINI_API_KEY")
        self.deepseek_api_key = getattr(cfg.translation, "deepseek_api_key", None) or cfg.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
        self.deepseek_model = getattr(cfg.translation, "deepseek_model", "deepseek-chat")
        self.openrouter_api_key = getattr(cfg.translation, "openrouter_api_key", None) or cfg.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.openrouter_model = getattr(cfg.translation, "openrouter_model", "google/gemini-2.0-flash-exp:free")
        self.cdp_port = getattr(cfg.translation, "cdp_port", 9222)

        self.chunk_lines = 10
        from dubstudio.paths import get_workspace_dir
        self.cache_dir = cache_dir or (get_workspace_dir() / ".cache" / "llm")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.provider == "gemini_web":
            self.min_interval = 1.5
        else:
            self.min_interval = max(3.0, 60.0 / max(1, cfg.translation.rate_limit_rpm))
        self._last_call = 0.0

    def _wait_rate_limit(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()

    def _build_cascade(self) -> List[Dict[str, Any]]:
        """Construct the prioritized cascade: respects primary provider and falls back cleanly."""
        candidates: List[Dict[str, Any]] = []

        # 0. Gemini Web via CDP
        if self.provider == "gemini_web":
            candidates.append({"type": "gemini_web", "model": "gemini_web", "key": "", "desc": "Gemini Web (Trình duyệt)"})
            if not self.auto_fallback:
                return candidates

        # 1. Gemini cascade (Primary or Fallback)
        if self.api_key:
            gem_model = self.model if "gemini" in self.model else "gemini-2.5-flash"
            candidates.append({"type": "gemini", "model": gem_model, "key": self.api_key, "desc": f"Gemini {gem_model}"})
            if self.backup_api_key and self.backup_api_key != self.api_key:
                candidates.append({"type": "gemini", "model": gem_model, "key": self.backup_api_key, "desc": f"Gemini {gem_model} (Backup Key)"})
            if self.auto_fallback:
                for fb_model in self.fallback_models:
                    candidates.append({"type": "gemini", "model": fb_model, "key": self.api_key, "desc": f"Gemini {fb_model} (Fallback)"})

        # 2. Fallback to OpenRouter if configured
        if self.openrouter_api_key:
            candidates.append({"type": "openrouter", "model": self.openrouter_model, "key": self.openrouter_api_key, "desc": f"OpenRouter ({self.openrouter_model})"})

        # 3. Fallback to DeepSeek if configured
        if self.deepseek_api_key:
            candidates.append({"type": "deepseek", "model": self.deepseek_model, "key": self.deepseek_api_key, "desc": f"DeepSeek ({self.deepseek_model})"})

        return candidates

    def _call_gemini(self, model: str, api_key: str, system_instruction: str, content_str: str) -> List[Dict[str, Any]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"{system_instruction}\n\nDữ liệu cần dịch:\n{content_str}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json",
            }
        }
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(url, json=payload)

        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:250]}")

        res_json = resp.json()
        text_content = res_json["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text_content)

    def _call_openrouter(self, model: str, api_key: str, system_instruction: str, content_str: str) -> List[Dict[str, Any]]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://dubstudio.local",
            "X-Title": "DubStudio Video Dubbing",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Dữ liệu cần dịch:\n{content_str}"},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:250]}")

        res_json = resp.json()
        raw_text = res_json["choices"][0]["message"]["content"]
        # Handle cases where model wraps array in an object like {"translations": [...]} or raw array
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            for k in ("translations", "segments", "data", "items"):
                if k in parsed and isinstance(parsed[k], list):
                    return parsed[k]
        return [parsed]

    def _call_gemini_web(self, system_instruction: str, content_str: str) -> List[Dict[str, Any]]:
        from dubstudio.llm.cdp_gemini import translate_via_cdp
        full_prompt = f"{system_instruction}\n\nDữ liệu cần dịch:\n{content_str}"
        return translate_via_cdp(full_prompt, port=getattr(self, "cdp_port", 9222))

    def _call_deepseek(self, model: str, api_key: str, system_instruction: str, content_str: str) -> List[Dict[str, Any]]:
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Dữ liệu cần dịch:\n{content_str}"},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            raise RuntimeError(f"DeepSeek HTTP {resp.status_code}: {resp.text[:250]}")

        res_json = resp.json()
        raw_text = res_json["choices"][0]["message"]["content"]
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            for k in ("translations", "segments", "data", "items"):
                if k in parsed and isinstance(parsed[k], list):
                    return parsed[k]
        return [parsed]

    def _call_gemini_web(self, system_instruction: str, content_str: str) -> List[Dict[str, Any]]:
        from dubstudio.llm.cdp_gemini import translate_via_cdp
        full_prompt = f"{system_instruction}\n\nDữ liệu cần dịch:\n{content_str}"
        return translate_via_cdp(full_prompt, port=getattr(self, "cdp_port", 9222))

    def _translate_batch(
        self,
        batch_items: List[Dict[str, Any]],
        system_instruction: str,
        stage_name: str,
        current_idx: int,
        total_items: int,
        style: Optional[str] = None,
        content_str: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if content_str is None:
            content_str = json.dumps(batch_items, ensure_ascii=False)
        prompt_hash = hashlib.sha256((self.model + ":" + (style or "") + ":" + system_instruction + ":" + content_str).encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{prompt_hash}.json"

        if cache_file.exists():
            try:
                cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                from dubstudio.text.spoken_cleaner import is_translation_contaminated, sanitize_spoken_vietnamese
                is_dirty = any(is_translation_contaminated(str(item.get("vi") or item.get("vi_text") or "")) for item in cached_data)
                if not is_dirty:
                    for item in cached_data:
                        if "vi" in item and isinstance(item["vi"], str):
                            item["vi"] = sanitize_spoken_vietnamese(item["vi"])
                        if "vi_text" in item and isinstance(item["vi_text"], str):
                            item["vi_text"] = sanitize_spoken_vietnamese(item["vi_text"])
                        if "tts_text" in item and isinstance(item["tts_text"], str):
                            item["tts_text"] = sanitize_spoken_vietnamese(item["tts_text"])
                    return cached_data
                else:
                    cache_file.unlink(missing_ok=True)
            except Exception:
                pass

        cascade = self._build_cascade()
        last_error = None

        pct = (current_idx / max(1, total_items)) * 100.0

        for cand_idx, cand in enumerate(cascade):
            cand_type = cand["type"]
            cand_model = cand["model"]
            cand_desc = cand["desc"]
            cand_key = cand["key"]

            max_attempts = 4 if cand_type == "gemini" else 2

            for attempt in range(1, max_attempts + 1):
                self._wait_rate_limit()
                try:
                    emit_event(
                        stage_name,
                        pct,
                        f"Đang dịch câu {current_idx}/{total_items} qua {cand_desc} (lần {attempt})...",
                    )

                    if cand_type == "gemini_web":
                        translated_items = self._call_gemini_web(system_instruction, content_str)
                    elif cand_type == "gemini":
                        translated_items = self._call_gemini(cand_model, cand_key, system_instruction, content_str)
                    elif cand_type == "deepseek":
                        translated_items = self._call_deepseek(cand_model, cand_key, system_instruction, content_str)
                    elif cand_type == "openrouter":
                        translated_items = self._call_openrouter(cand_model, cand_key, system_instruction, content_str)
                    else:
                        continue

                    # Sanitize and humanize spoken text
                    from dubstudio.text.spoken_cleaner import sanitize_spoken_vietnamese
                    for item in translated_items:
                        if "vi" in item and isinstance(item["vi"], str):
                            item["vi"] = sanitize_spoken_vietnamese(item["vi"])
                        if "vi_text" in item and isinstance(item["vi_text"], str):
                            item["vi_text"] = sanitize_spoken_vietnamese(item["vi_text"])
                        if "tts_text" in item and isinstance(item["tts_text"], str):
                            item["tts_text"] = sanitize_spoken_vietnamese(item["tts_text"])

                    # Successfully translated
                    cache_file.write_text(json.dumps(translated_items, ensure_ascii=False, indent=2), encoding="utf-8")
                    return translated_items

                except Exception as e:
                    last_error = e
                    err_str = str(e)

                    # Handle 402 Insufficient Balance (DeepSeek)
                    if "402" in err_str or "Insufficient Balance" in err_str:
                        emit_event(
                            stage_name,
                            pct,
                            "⚠️ DeepSeek: Tài khoản đã hết số dư (vui lòng nạp tiền vào tài khoản DeepSeek).",
                            level="warning",
                        )
                        break

                    # Handle 404 No endpoints (OpenRouter)
                    if "404" in err_str or "No endpoints found" in err_str:
                        emit_event(
                            stage_name,
                            pct,
                            f"⚠️ OpenRouter: Mô hình {cand_model} hiện không khả dụng (HTTP 404).",
                            level="warning",
                        )
                        break

                    # Check for rate-limiting or server overload (429 / 503)
                    is_rate_limit = (
                        "429" in err_str
                        or "503" in err_str
                        or "RESOURCE_EXHAUSTED" in err_str
                        or "overloaded" in err_str.lower()
                        or "rate limit" in err_str.lower()
                    )
                    if is_rate_limit and attempt < max_attempts:
                        # Automatically adapt chunk lines downward to stay within token per minute limits
                        if hasattr(self, "chunk_lines") and self.chunk_lines > 3:
                            self.chunk_lines = max(3, self.chunk_lines // 2)

                        # Extract exact wait seconds from retry-after header or error message
                        wait_match = (
                            re.search(r"retry-after=([0-9\.]+)", err_str)
                            or re.search(r"try again in ([0-9\.]+)s", err_str)
                        )
                        if wait_match:
                            wait_s = float(wait_match.group(1)) + 1.2
                        else:
                            wait_s = max(8.0, attempt * 6.0)

                        provider_name = "Google Gemini" if cand_type == "gemini" else cand_type.upper()
                        emit_event(
                            stage_name,
                            pct,
                            f"⚠️ {provider_name} đạt giới hạn tốc độ (HTTP 429). Đang chờ {int(wait_s)}s để gửi lại (lần {attempt}/{max_attempts})...",
                            level="warning",
                        )
                        time.sleep(wait_s)
                    else:
                        time.sleep(2.0 * attempt)

            # If this candidate failed all attempts, inform user of failover to next model
            if cand_idx + 1 < len(cascade):
                next_cand = cascade[cand_idx + 1]
                emit_event(
                    stage_name,
                    pct,
                    f"⚠️ {cand_desc} bị bận/lỗi. Chuyển sang mô hình dự phòng: {next_cand['desc']}...",
                    level="warning",
                )

        if isinstance(last_error, DubError):
            raise last_error
        raise DubError(
            code="TRANSLATION_FAILED",
            user_message_vi=f"Không thể hoàn thành dịch thuật qua mô hình {self.model}: {str(last_error)[:200]}",
            hint_vi="Vui lòng kiểm tra lại phương thức dịch hoặc đổi sang API trong mục Cài đặt.",
            details={"error": str(last_error)},
        )

    def _preflight_check(self, stage_name: str) -> None:
        """Lightweight 1-token preflight check to ensure the model/key is active before starting batches."""
        emit_event(stage_name, 0.0, "Đang kiểm tra kết nối API dịch thuật (preflight test)...")
        cascade = self._build_cascade()
        for cand in cascade:
            cand_type = cand["type"]
            cand_model = cand["model"]
            cand_key = cand["key"]
            try:
                if cand_type == "gemini_web":
                    from dubstudio.llm.cdp_gemini import is_cdp_ready, launch_browser_cdp
                    port = getattr(self, "cdp_port", 9222)
                    if not is_cdp_ready(port):
                        emit_event(stage_name, 0.0, "Đang kết nối trình duyệt Gemini Web qua cổng 9222...")
                        launch_browser_cdp(port, allow_restart=True, hidden=True)
                    emit_event(stage_name, 0.0, f"✓ Kết nối {cand['desc']} sẵn sàng")
                    return
                elif cand_type == "gemini":
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cand_model}:generateContent?key={cand_key}"
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(url, json={"contents": [{"parts": [{"text": "1"}]}]})
                    if resp.status_code == 200:
                        emit_event(stage_name, 0.0, f"✓ Kết nối API sẵn sàng ({cand['desc']})")
                        self.model = cand_model
                        return
                elif cand_type == "deepseek":
                    url = "https://api.deepseek.com/chat/completions"
                    headers = {"Authorization": f"Bearer {cand_key}", "Content-Type": "application/json"}
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(url, headers=headers, json={"model": cand_model, "messages": [{"role": "user", "content": "1"}]})
                    if resp.status_code == 200:
                        emit_event(stage_name, 0.0, f"✓ Kết nối API sẵn sàng ({cand['desc']})")
                        return
                elif cand_type == "openrouter":
                    url = "https://openrouter.ai/api/v1/chat/completions"
                    headers = {"Authorization": f"Bearer {cand_key}", "Content-Type": "application/json"}
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(url, headers=headers, json={"model": cand_model, "messages": [{"role": "user", "content": "1"}]})
                    if resp.status_code == 200:
                        emit_event(stage_name, 0.0, f"✓ Kết nối API sẵn sàng ({cand['desc']})")
                        return
            except Exception:
                continue

    def translate_segments(
        self,
        segments: List[Dict[str, Any]],
        stage_name: str = "translate",
        style: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        on_batch_done: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Translate segments from Chinese to Vietnamese using Gemini Flash API with cascade fallback and live disk saving."""
        if not segments:
            return []

        # Check existing translations to resume seamlessly without repeating work
        untranslated = [
            s for s in segments
            if not (s.get("vi_text") and str(s.get("vi_text")).strip())
        ]

        if not untranslated:
            emit_event(stage_name, 100.0, f"Toàn bộ {len(segments)} câu đã được dịch sẵn (bỏ qua API)")
            return clean_dangling_conjunctions(segments)

        total_needed = len(untranslated)
        emit_event(stage_name, 0.0, f"Cần dịch {total_needed}/{len(segments)} câu (đã có {len(segments) - total_needed} câu hoàn thành trước đó)")

        # Run preflight connectivity test before batch translation
        self._preflight_check(stage_name)

        summary = (context.get("summary") or context.get("topic") or "") if context else ""

        # Safe dynamic batch size to strictly stay within free tier TPM limits
        self.chunk_lines = getattr(self, "chunk_lines", 10)
        all_translated: List[Dict[str, Any]] = []

        i = 0
        while i < total_needed:
            cur_chunk = max(3, getattr(self, "chunk_lines", 10))
            batch = untranslated[i:i + cur_chunk]
            system_instruction, content_str = build_prompt(
                batch_units=batch,
                all_units=segments,
                context=context,
                style=style,
                story_so_far=summary,
                task_type="translate",
            )

            try:
                res = self._translate_batch(
                    batch,
                    system_instruction,
                    stage_name,
                    current_idx=min(i + len(batch), total_needed),
                    total_items=total_needed,
                    style=style,
                    content_str=content_str,
                )
            except Exception as batch_err:
                if len(batch) > 1:
                    mid = len(batch) // 2
                    batch_a = batch[:mid]
                    batch_b = batch[mid:]
                    emit_event(
                        stage_name,
                        min(100.0, ((i + len(batch)) / max(1, total_needed)) * 100.0),
                        f"⚠️ Mẻ dịch gặp sự cố ({batch_err}). Đang chia đôi khối {len(batch_a)} và {len(batch_b)} câu...",
                        level="warning",
                    )
                    inst_a, cont_a = build_prompt(batch_a, segments, context=context, style=style, story_so_far=summary, task_type="split")
                    res_a = self._translate_batch(
                        batch_a,
                        inst_a,
                        stage_name,
                        current_idx=min(i + len(batch_a), total_needed),
                        total_items=total_needed,
                        style=style,
                        content_str=cont_a,
                    )
                    inst_b, cont_b = build_prompt(batch_b, segments, context=context, style=style, story_so_far=summary, task_type="split")
                    res_b = self._translate_batch(
                        batch_b,
                        inst_b,
                        stage_name,
                        current_idx=min(i + len(batch), total_needed),
                        total_items=total_needed,
                        style=style,
                        content_str=cont_b,
                    )
                    res = res_a + res_b
                else:
                    raise batch_err

            # Audit in-batch: verify all requested IDs received a non-empty translation
            res_ids = {r["id"] for r in res if "id" in r and (r.get("vi") or r.get("vi_text"))}
            missing_in_batch = [item for item in batch if item["id"] not in res_ids]
            if missing_in_batch:
                emit_event(
                    stage_name,
                    min(100.0, ((i + len(batch)) / max(1, total_needed)) * 100.0),
                    f"⚠️ Phát hiện {len(missing_in_batch)} câu bị bỏ sót ID trong mẻ. Đang dịch bù lại ngay...",
                    level="info",
                )
                try:
                    retry_inst, retry_cont = build_prompt(
                        batch_units=missing_in_batch,
                        all_units=segments,
                        context=context,
                        style=style,
                        story_so_far=summary,
                        task_type="retry",
                    )
                    retry_res = self._translate_batch(
                        missing_in_batch,
                        retry_inst,
                        stage_name,
                        current_idx=min(i + len(batch), total_needed),
                        total_items=total_needed,
                        style=style,
                        content_str=retry_cont,
                    )
                    res.extend(retry_res)
                except Exception as retry_err:
                    emit_event(stage_name, 0.0, f"Dịch bù mẻ gặp lỗi: {retry_err}", level="warning")

            all_translated.extend(res)
            i += len(batch)

            # Progressively update segments and persist to disk after EACH batch
            self._merge_translations(segments, res)
            if on_batch_done:
                try:
                    on_batch_done(segments)
                except Exception:
                    pass

        # Final audit: verify 100% of segments have a non-empty, non-Chinese Vietnamese translation
        still_missing = []
        for s in segments:
            vi = str(s.get("vi_text") or "").strip()
            src = str(s.get("src_text") or s.get("zh") or "").strip()
            if not vi or (src and vi == src):
                still_missing.append(s)

        if still_missing:
            emit_event(
                stage_name,
                95.0,
                f"Kiểm toán cuối: Phát hiện {len(still_missing)} câu chưa có bản dịch tiếng Việt. Đang dịch bù bổ sung...",
                level="info",
            )
            try:
                audit_inst, audit_cont = build_prompt(
                    batch_units=still_missing,
                    all_units=segments,
                    context=context,
                    style=style,
                    story_so_far=summary,
                    task_type="retry",
                )
                audit_res = self._translate_batch(
                    still_missing,
                    audit_inst,
                    stage_name,
                    current_idx=total_needed,
                    total_items=total_needed,
                    style=style,
                    content_str=audit_cont,
                )
                self._merge_translations(segments, audit_res)
                if on_batch_done:
                    on_batch_done(segments)
            except Exception as e:
                emit_event(stage_name, 95.0, f"Lỗi dịch bù câu cuối: {e}", level="warning")

        return clean_dangling_conjunctions(segments)

    def _merge_translations(
        self, segments: List[Dict[str, Any]], translated_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        trans_map = {}
        for item in translated_items:
            if "id" in item:
                vi_val = str(item.get("vi") or item.get("vi_text") or "").strip()
                clauses_val = item.get("vi_clauses")
                if not vi_val and clauses_val and isinstance(clauses_val, list):
                    vi_val = " ".join(str(c).strip() for c in clauses_val if str(c).strip()).strip()
                tts_val = str(item.get("tts_text") or vi_val).strip()
                gender_val = str(item.get("gender") or "").strip().lower()
                trans_map[item["id"]] = (vi_val, tts_val, clauses_val, gender_val)

        for s in segments:
            if s["id"] in trans_map:
                vi_text, tts_text, clauses_val, gender_val = trans_map[s["id"]]
                if vi_text:
                    s["vi_text"] = vi_text
                    s["tts_text"] = tts_text
                elif not s.get("vi_text") and clauses_val and isinstance(clauses_val, list):
                    joined = " ".join(str(c).strip() for c in clauses_val if str(c).strip()).strip()
                    if joined:
                        s["vi_text"] = joined
                        s["tts_text"] = joined
                if clauses_val and isinstance(clauses_val, list):
                    s["vi_clauses"] = clauses_val
                if gender_val in ("male", "female") and not s.get("user_edited"):
                    s["gender"] = gender_val

        clean_dangling_conjunctions(segments)
        return segments


DANGLING_CONJUNCTION_PATTERN = re.compile(
    r"(?P<punct>[?!.,;:])?\s*(?P<word>từ đó|cho nên|bởi vì|do đó|trong khi|ngoài ra|từ|và|nhưng|vì|do|nếu|khi|để|hoặc|hay|với|tại|bởi|cho|như|mà|sẽ|hãy|đang|muốn|cần)\s*(?P<dots>\.{2,4}|…)?$",
    re.IGNORECASE,
)


def clean_dangling_conjunctions(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect trailing prepositions/conjunctions at the end of segment i (e.g. '... chưa? Từ...')
    and move them to the start of segment i+1 to prevent awkward pauses and broken sentences.
    """
    from dubstudio.text.spoken_cleaner import sanitize_spoken_vietnamese

    if len(segments) < 2:
        for s in segments:
            for field in ("vi_text", "tts_text"):
                if field in s and s[field]:
                    s[field] = sanitize_spoken_vietnamese(s[field])
        return segments

    for i in range(len(segments) - 1):
        s_curr = segments[i]
        s_next = segments[i + 1]

        for field in ("vi_text", "tts_text"):
            curr_text = (s_curr.get(field) or "").strip()
            next_text = (s_next.get(field) or "").strip()
            if not curr_text or not next_text:
                continue

            m = DANGLING_CONJUNCTION_PATTERN.search(curr_text)
            if not m:
                continue

            punct = m.group("punct")
            word = m.group("word")

            # Cut off the dangling conjunction from curr_text
            cleaned_curr = curr_text[:m.start()].strip()
            if punct and punct in ("?", "!", "."):
                cleaned_curr += punct
            elif not cleaned_curr.endswith((".", "!", "?")):
                cleaned_curr += "."

            cap_word = word[0].upper() + word[1:].lower()
            words_next = next_text.split()
            if words_next:
                first_w = words_next[0]
                if first_w.isalpha() and first_w[0].isupper() and (len(first_w) == 1 or first_w[1:].islower()):
                    words_next[0] = first_w[0].lower() + first_w[1:]
                    next_text = " ".join(words_next)

            cleaned_next = f"{cap_word} {next_text}"

            s_curr[field] = sanitize_spoken_vietnamese(cleaned_curr)
            s_next[field] = sanitize_spoken_vietnamese(cleaned_next)

    for s in segments:
        for field in ("vi_text", "tts_text"):
            if field in s and s[field]:
                s[field] = sanitize_spoken_vietnamese(s[field])

    return segments

