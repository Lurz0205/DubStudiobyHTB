"""Chrome DevTools Protocol (CDP) client for automating Gemini Web translation.
Connects directly to an open Chromium browser (Chrome / Edge) on port 9222.
"""
import asyncio
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional
import httpx
from dubstudio.errors import DubError
from dubstudio.events import emit_event

try:
    import winreg
except ImportError:
    winreg = None


def find_browser_executable() -> Optional[str]:
    """Find installed Chromium-based browser (Chrome, Edge, Brave, Cốc Cốc)."""
    # 1. Search PATH
    for name in ("chrome", "google-chrome", "msedge", "brave", "coccoc"):
        p = shutil.which(name)
        if p and os.path.exists(p):
            return p

    # 2. Check Windows Registry App Paths
    if winreg:
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\coccoc.exe",
            ):
                try:
                    with winreg.OpenKey(hive, sub) as k:
                        val = winreg.QueryValue(k, None)
                        if val and os.path.exists(val):
                            return val
                except OSError:
                    pass

    # 3. Check Standard File System Locations
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\CocCoc\Browser\Application\browser.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    return None


def is_cdp_ready(port: int = 9222) -> bool:
    """Check if CDP HTTP endpoint is responsive at http://127.0.0.1:{port}/json/version."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.08)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return False
    except Exception:
        return False

    try:
        with httpx.Client(timeout=0.6) as client:
            resp = client.get(f"http://127.0.0.1:{port}/json/version")
            return resp.status_code == 200
    except Exception:
        return False


def get_default_profile_dir() -> Path:
    """Return dedicated lightweight browser profile directory (~70 MB, does not duplicate browser)."""
    p = Path.home() / ".dubstudio" / "browser_profile"
    p.mkdir(parents=True, exist_ok=True)
    return p


def minimize_gemini_window(port: int = 9222) -> None:
    """Minimize Gemini browser window via CDP so it stays hidden on taskbar."""
    try:
        ws_url = get_gemini_ws_url(port)
        async def _min():
            client = CDPClient(ws_url)
            await client.connect()
            try:
                win_info = await client.send_cmd("Browser.getWindowForTarget")
                if win_info and "windowId" in win_info:
                    wid = win_info["windowId"]
                    await client.send_cmd("Browser.setWindowBounds", {
                        "windowId": wid,
                        "bounds": {"windowState": "minimized"}
                    })
            finally:
                await client.close()
        asyncio.run(_min())
    except Exception:
        pass


def restore_gemini_window(port: int = 9222) -> None:
    """Restore and bring Gemini browser window to normal view."""
    try:
        ws_url = get_gemini_ws_url(port)
        async def _restore():
            client = CDPClient(ws_url)
            await client.connect()
            try:
                win_info = await client.send_cmd("Browser.getWindowForTarget")
                if win_info and "windowId" in win_info:
                    wid = win_info["windowId"]
                    await client.send_cmd("Browser.setWindowBounds", {
                        "windowId": wid,
                        "bounds": {"windowState": "normal"}
                    })
                await client.send_cmd("Page.bringToFront")
            finally:
                await client.close()
        asyncio.run(_restore())
    except Exception:
        pass


def bring_gemini_to_front(port: int = 9222) -> None:
    """Focus and bring Gemini window/tab to the front."""
    restore_gemini_window(port)


def launch_browser_cdp(port: int = 9222, allow_restart: bool = False, hidden: bool = True) -> bool:
    """Launch dedicated lightweight Edge instance with remote debugging port enabled."""
    if is_cdp_ready(port):
        if hidden:
            minimize_gemini_window(port)
        else:
            restore_gemini_window(port)
        return True

    exe = find_browser_executable()
    if not exe:
        raise DubError(
            code="BROWSER_NOT_FOUND",
            user_message_vi="Không tìm thấy trình duyệt Google Chrome hoặc Microsoft Edge trên máy tính.",
            hint_vi="Vui lòng cài đặt Chrome hoặc Edge.",
        )

    profile_dir = get_default_profile_dir()
    cmd = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
    ]

    if hidden:
        cmd.extend([
            "--start-minimized",
        ])
    else:
        cmd.extend([
            "--new-window",
        ])

    cmd.append("https://gemini.google.com/app")

    try:
        flags = 0
        startupinfo = None
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            if hidden:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 7  # SW_SHOWMINNOACTIVE
        subprocess.Popen(
            cmd,
            creationflags=flags,
            startupinfo=startupinfo,
        )
    except Exception as e:
        raise DubError(
            code="BROWSER_LAUNCH_FAILED",
            user_message_vi=f"Không thể khởi động trình duyệt: {e}",
            hint_vi="Vui lòng thử mở lại hoặc kiểm tra quyền truy cập.",
        )

    # Wait up to 6 seconds for CDP port to come alive
    start_t = time.time()
    while time.time() - start_t < 6.0:
        if is_cdp_ready(port):
            if hidden:
                minimize_gemini_window(port)
            else:
                restore_gemini_window(port)
            return True
        time.sleep(0.4)

    return is_cdp_ready(port)


def get_gemini_ws_url(port: int = 9222) -> str:
    """Find WebSocket debugger URL for Gemini Web tab, or create one if not open."""
    url = f"http://127.0.0.1:{port}/json"
    with httpx.Client(timeout=3.0) as client:
        resp = client.get(url)
        if resp.status_code != 200:
            raise DubError(f"Không thể kết nối tới Chrome CDP (HTTP {resp.status_code})")
        targets = resp.json()

    # Find Gemini tab
    for t in targets:
        t_url = t.get("url", "")
        if "gemini.google.com" in t_url and t.get("type") == "page":
            ws = t.get("webSocketDebuggerUrl")
            if ws:
                return ws

    # If no Gemini tab open, create a new one
    new_url = f"http://127.0.0.1:{port}/json/new?https://gemini.google.com/app"
    with httpx.Client(timeout=5.0) as client:
        resp = client.put(new_url)
        if resp.status_code == 200:
            target = resp.json()
            ws = target.get("webSocketDebuggerUrl")
            if ws:
                return ws

    raise DubError("Không tìm thấy tab Gemini (https://gemini.google.com/app) trong trình duyệt.")


class CDPClient:
    """Lightweight asynchronous WebSocket CDP client."""

    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url
        self._msg_id = 0
        self._ws = None

    async def connect(self) -> None:
        import websockets
        self._ws = await websockets.connect(self.ws_url, max_size=10 * 1024 * 1024)

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send_cmd(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self._msg_id += 1
        cid = self._msg_id
        payload = {
            "id": cid,
            "method": method,
            "params": params or {},
        }
        await self._ws.send(json.dumps(payload))
        while True:
            raw = await self._ws.recv()
            data = json.loads(raw)
            if data.get("id") == cid:
                if "error" in data:
                    raise RuntimeError(f"CDP Error ({method}): {data['error']}")
                return data.get("result", {})

    async def evaluate(self, expression: str) -> Any:
        res = await self.send_cmd(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        return res.get("result", {}).get("value")


async def _async_send_prompt_to_gemini(prompt: str, port: int = 9222, timeout: float = 90.0) -> str:
    """Send prompt to Gemini Web via CDP and wait for generation completion with full error detection."""
    ws_url = get_gemini_ws_url(port)
    client = CDPClient(ws_url)
    await client.connect()

    try:
        await client.send_cmd("Runtime.enable")

        # 1. Pre-check: Wait until Stop button is COMPLETELY gone (no leftover background generation)
        state_check_js = """
        (() => {
            function checkStop() {
                const btns = document.querySelectorAll('button, [role="button"], mat-icon-button, gem-icon-button');
                for (const b of btns) {
                    if (b.offsetParent === null) continue;
                    const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                    const icon = (b.getAttribute('fonticonname') || '').toLowerCase();
                    const cls = (b.className || '').toString().toLowerCase();
                    if (aria.includes('dừng') || aria.includes('stop') || icon.includes('stop') || cls.includes('stop-button')) {
                        return true;
                    }
                }
                return false;
            }

            const isGenerating = checkStop();

            const retryBtn = document.querySelector('button[aria-label*="Thử lại"], button[aria-label*="Retry"], button.retry-button');
            const hasRetry = !!(retryBtn && retryBtn.offsetParent !== null && !retryBtn.disabled);

            const alerts = document.querySelectorAll('[role="alert"], .error-message, .model-response-error, .network-error-message, message-actions-error');
            let alertMsg = "";
            for (const a of alerts) {
                if (a && a.offsetParent !== null) {
                    const t = (a.innerText || a.textContent || "").trim();
                    if (t) { alertMsg = t; break; }
                }
            }

            const rich = document.querySelector('rich-textarea');
            const editor = (rich && rich.querySelector('.ql-editor')) ||
                           document.querySelector('div[contenteditable="true"]') ||
                           document.querySelector('textarea');
            const hasEditor = !!editor;
            const panels = document.querySelectorAll('.markdown-main-panel');

            return {
                is_generating: isGenerating,
                has_retry: hasRetry,
                alert_msg: alertMsg,
                has_editor: hasEditor,
                panel_count: panels.length
            };
        })()
        """

        pre_state = await client.evaluate(state_check_js) or {}

        # If Gemini is currently generating from a previous prompt, wait for it to finish cleanly
        if pre_state.get("is_generating"):
            start_busy = time.time()
            while time.time() - start_busy < 15.0:
                await asyncio.sleep(0.8)
                pre_state = await client.evaluate(state_check_js) or {}
                if not pre_state.get("is_generating"):
                    break

            if pre_state.get("is_generating"):
                raise DubError(
                    "Gemini Web chưa hoàn thành câu dịch trước đó (nút Dừng vẫn đang hoạt động). "
                    "Vui lòng kiểm tra trình duyệt hoặc bấm nút 'Dừng' trên trang web Gemini."
                )

        if pre_state.get("has_retry") or pre_state.get("alert_msg"):
            err_text = pre_state.get("alert_msg") or "Trình duyệt đang hiển thị nút 'Thử lại'"
            raise DubError(
                f"Gemini Web gặp sự cố từ lượt dịch trước ({err_text}). "
                "Vui lòng kiểm tra kết nối mạng hoặc thử lại."
            )

        # Wait up to 10s for chat input to be available
        if not pre_state.get("has_editor"):
            start_wait_ed = time.time()
            ready_ed = False
            while time.time() - start_wait_ed < 10.0:
                await asyncio.sleep(0.5)
                st = await client.evaluate(state_check_js) or {}
                if st.get("has_editor"):
                    ready_ed = True
                    pre_state = st
                    break
            if not ready_ed:
                raise DubError("Không tìm thấy khung chat trên Gemini Web. Vui lòng kiểm tra hoặc tải lại trang.")

        initial_count = pre_state.get("panel_count", 0)

        # 2. Inject prompt into editor and trigger input/change events
        safe_prompt_json = json.dumps(prompt)
        inject_js = f"""
        (() => {{
            const text = {safe_prompt_json};
            const rich = document.querySelector('rich-textarea');
            if (rich && rich.__quill) {{
                rich.__quill.setText(text, 'user');
                return true;
            }}
            const editor = (rich && rich.querySelector('.ql-editor')) ||
                           document.querySelector('div[contenteditable="true"]') ||
                           document.querySelector('textarea');
            if (!editor) return false;
            editor.focus();
            try {{
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, text);
            }} catch(e) {{}}
            if (editor.innerText !== text) {{
                editor.innerText = text;
            }}
            editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
            editor.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }})()
        """
        inject_success = await client.evaluate(inject_js)
        if not inject_success:
            raise DubError("Không thể nhập nội dung vào ô dịch của Gemini Web.")

        # 3. Wait specifically for Send button to become ENABLED (concrete sign that Gemini recognized input)
        # Never press Enter blindly, never click when it might be a Stop button!
        wait_send_btn_js = """
        (() => {
            const btns = Array.from(document.querySelectorAll('button, [role="button"], mat-icon-button, gem-icon-button'));
            for (const b of btns) {
                if (b.offsetParent === null) continue;
                const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                const icon = (b.getAttribute('fonticonname') || '').toLowerCase();
                const cls = (b.className || '').toString().toLowerCase();

                // Strictly skip any STOP buttons
                if (aria.includes('dừng') || aria.includes('stop') || icon.includes('stop') || cls.includes('stop-button')) {
                    continue;
                }

                // Check for send button indicators
                const isSendCandidate = (
                    aria.includes('gửi') ||
                    aria.includes('send') ||
                    (aria.includes('lời nhắc') && !aria.includes('dừng')) ||
                    (aria.includes('prompt') && !aria.includes('stop')) ||
                    cls.includes('send-button') ||
                    b.closest('.send-button-container') !== null
                );

                if (isSendCandidate) {
                    const disabled = b.disabled || b.getAttribute('aria-disabled') === 'true';
                    if (!disabled) {
                        return { found: true };
                    }
                }
            }
            return { found: false };
        })()
        """

        btn_ready = False
        start_wait_btn = time.time()
        while time.time() - start_wait_btn < 4.0:
            res_btn = await client.evaluate(wait_send_btn_js) or {}
            if res_btn.get("found"):
                btn_ready = True
                break
            await asyncio.sleep(0.3)

        # 4. Trigger send by clicking ONLY the validated active Send button
        click_send_js = """
        (() => {
            const btns = Array.from(document.querySelectorAll('button, [role="button"], mat-icon-button, gem-icon-button'));
            for (const b of btns) {
                if (b.offsetParent === null) continue;
                const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                const icon = (b.getAttribute('fonticonname') || '').toLowerCase();
                const cls = (b.className || '').toString().toLowerCase();

                if (aria.includes('dừng') || aria.includes('stop') || icon.includes('stop') || cls.includes('stop-button')) {
                    continue;
                }

                const isSendCandidate = (
                    aria.includes('gửi') ||
                    aria.includes('send') ||
                    (aria.includes('lời nhắc') && !aria.includes('dừng')) ||
                    (aria.includes('prompt') && !aria.includes('stop')) ||
                    cls.includes('send-button') ||
                    b.closest('.send-button-container') !== null
                );

                if (isSendCandidate) {
                    const disabled = b.disabled || b.getAttribute('aria-disabled') === 'true';
                    if (!disabled) {
                        b.click();
                        return { clicked: true };
                    }
                }
            }
            return { clicked: false };
        })()
        """
        await client.evaluate(click_send_js)

        # 5. Concrete sign of successful send: editor cleared OR Stop button appeared OR panel count increased
        verify_send_js = """
        (() => {
            const rich = document.querySelector('rich-textarea');
            const editor = (rich && rich.querySelector('.ql-editor')) ||
                           document.querySelector('div[contenteditable="true"]') ||
                           document.querySelector('textarea');
            const editorText = editor ? (editor.innerText || '').trim() : '';

            const btns = document.querySelectorAll('button, [role="button"]');
            let isGenerating = false;
            for (const b of btns) {
                if (b.offsetParent === null) continue;
                const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                const icon = (b.getAttribute('fonticonname') || '').toLowerCase();
                if (aria.includes('dừng') || aria.includes('stop') || icon.includes('stop')) {
                    isGenerating = true;
                    break;
                }
            }

            const panels = document.querySelectorAll('.markdown-main-panel');
            return {
                editor_cleared: (editorText === '' || editorText.length < 5),
                is_generating: isGenerating,
                panel_count: panels.length
            };
        })()
        """

        start_verify = time.time()
        sent_started = False
        while time.time() - start_verify < 6.0:
            await asyncio.sleep(0.4)
            st = await client.evaluate(verify_send_js) or {}
            if st.get("is_generating") or st.get("editor_cleared") or st.get("panel_count", 0) > initial_count:
                sent_started = True
                break

        if not sent_started:
            # Try clicking send once more
            await client.evaluate(click_send_js)
            await asyncio.sleep(0.8)
            st = await client.evaluate(verify_send_js) or {}
            if st.get("is_generating") or st.get("editor_cleared") or st.get("panel_count", 0) > initial_count:
                sent_started = True

        if not sent_started:
            raise DubError(
                "Gemini Web không nhận lệnh gửi câu dịch (nút Gửi chưa kích hoạt hoặc bị chặn). "
                "Vui lòng kiểm tra lại trình duyệt."
            )

        # 6. Monitor generation completion (concrete signs: Stop button gone + text stable)
        start_wait = time.time()
        last_text = ""
        stable_ticks = 0
        while time.time() - start_wait < timeout:
            await asyncio.sleep(0.8)
            monitor_js = """
            (() => {
                let isGenerating = false;
                const btns = document.querySelectorAll('button, [role="button"]');
                for (const b of btns) {
                    if (b.offsetParent === null) continue;
                    const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                    const icon = (b.getAttribute('fonticonname') || '').toLowerCase();
                    if (aria.includes('dừng') || aria.includes('stop') || icon.includes('stop')) {
                        isGenerating = true;
                        break;
                    }
                }

                const retryBtn = document.querySelector('button[aria-label*="Thử lại"], button[aria-label*="Retry"], button.retry-button');
                const hasRetry = !!(retryBtn && retryBtn.offsetParent !== null && !retryBtn.disabled);

                const alerts = document.querySelectorAll('[role="alert"], .error-message, .model-response-error, .network-error-message, message-actions-error');
                let alertMsg = "";
                for (const a of alerts) {
                    if (a && a.offsetParent !== null) {
                        const t = (a.innerText || a.textContent || "").trim();
                        if (t) { alertMsg = t; break; }
                    }
                }

                const panels = document.querySelectorAll('.markdown-main-panel');
                const lastEl = panels.length > 0 ? panels[panels.length - 1] : null;
                const text = lastEl ? (lastEl.textContent || lastEl.innerText || "") : "";
                return {
                    panel_count: panels.length,
                    is_generating: isGenerating,
                    has_retry: hasRetry,
                    alert_msg: alertMsg,
                    last_text: text.trim()
                };
            })()
            """
            status = await client.evaluate(monitor_js) or {}

            # Check if an error banner appeared during generation
            if status.get("has_retry") or status.get("alert_msg"):
                err_text = status.get("alert_msg") or "Mất kết nối hoặc quá tải (nút Thử lại xuất hiện)"
                raise DubError(f"Gemini Web báo lỗi trong quá trình tạo câu dịch: {err_text}")

            count = status.get("panel_count", 0)
            generating = status.get("is_generating", False)
            text = status.get("last_text", "").strip()

            if count > initial_count and text:
                # Detect if response was aborted with "Bạn đã dừng câu trả lời này"
                if "bạn đã dừng câu trả lời này" in text.lower() or "you stopped this response" in text.lower():
                    raise DubError("Gemini Web bị gián đoạn ('Bạn đã dừng câu trả lời này'). Vui lòng bấm Dịch lại.")

                if not generating:
                    # Final flush wait to ensure full DOM render
                    await asyncio.sleep(0.5)
                    final_status = await client.evaluate(monitor_js) or {}
                    final_text = final_status.get("last_text", "").strip() or text
                    return final_text

                if text == last_text:
                    stable_ticks += 1
                    if stable_ticks >= 5:  # Content stable for ~4s
                        return text
                else:
                    stable_ticks = 0
                last_text = text

        raise DubError(
            f"Quá thời gian chờ phản hồi từ Gemini Web ({int(timeout)}s). "
            "Gemini Web tải quá lâu hoặc không hoàn thành câu dịch. Vui lòng kiểm tra mạng hoặc thử lại."
        )

    finally:
        await client.close()


def extract_json_translations(raw_text: str) -> List[Dict[str, Any]]:
    """Parse JSON translation items from Gemini Web output."""
    if not raw_text:
        return []

    # 1. Try markdown code block extraction
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    candidate_str = m.group(1).strip() if m else raw_text.strip()

    # 2. Try direct JSON parse
    try:
        parsed = json.loads(candidate_str)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for k in ("translations", "segments", "rewritten_segments", "rewritten", "lines", "data", "items", "results"):
                if k in parsed and isinstance(parsed[k], list):
                    return parsed[k]
            return [parsed]
    except Exception:
        pass

    # 3. Try regex search for outer JSON object or array
    m2 = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw_text)
    if m2:
        try:
            parsed = json.loads(m2.group(1))
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                for k in ("translations", "segments", "rewritten_segments", "rewritten", "lines", "data", "items", "results"):
                    if k in parsed and isinstance(parsed[k], list):
                        return parsed[k]
                return [parsed]
        except Exception:
            pass

    return []


def translate_via_cdp(prompt_text: str, port: int = 9222, timeout: float = 90.0) -> List[Dict[str, Any]]:
    """
    Synchronous entry point to translate via Gemini Web CDP automation.
    Ensures browser is alive, sends prompt, waits for response, and parses JSON output.
    """
    if not is_cdp_ready(port):
        launched = launch_browser_cdp(port, hidden=True)
        if not launched:
            raise DubError(
                "Chưa phát hiện trình duyệt mở cổng 9222. "
                "Vui lòng nhấn nút 'Mở trình duyệt Gemini' trong Cài đặt."
            )

    raw_response = asyncio.run(_async_send_prompt_to_gemini(prompt_text, port=port, timeout=timeout))
    results = extract_json_translations(raw_response)
    if not results:
        lower_raw = (raw_response or "").lower()
        if any(w in lower_raw for w in ["something went wrong", "đã xảy ra sự cố", "quá tải", "giới hạn", "chính sách"]):
            raise DubError(f"Gemini Web báo lỗi hoặc từ chối phản hồi: {raw_response[:200]}")
        raise DubError(
            f"Gemini Web chưa trả về đúng cấu trúc JSON danh sách câu dịch. Nội dung nhận được: {raw_response[:200]}"
        )

    return results


async def _async_check_gemini_status(port: int = 9222, timeout: float = 6.0) -> tuple[bool, str]:
    try:
        ws_url = get_gemini_ws_url(port)
        client = CDPClient(ws_url)
        await client.connect()
        try:
            await client.send_cmd("Runtime.enable")
            start_t = time.time()
            check_js = """
            (() => {
                const rich = document.querySelector('rich-textarea');
                const editor = (rich && rich.querySelector('.ql-editor')) ||
                               document.querySelector('div[contenteditable="true"]') ||
                               document.querySelector('textarea');
                if (editor) return { ok: true, msg: "Sẵn sàng (Mini Client Gemini)" };
                return { ok: false, msg: "Đang tải giao diện Gemini..." };
            })()
            """
            while time.time() - start_t < timeout:
                res = await client.evaluate(check_js)
                if res and res.get("ok"):
                    return True, "Sẵn sàng (Mini Client Gemini)"
                await asyncio.sleep(0.5)
            return False, "Chưa tìm thấy khung chat trên Gemini (đang tải)"
        finally:
            await client.close()
    except Exception as e:
        return False, str(e)


def check_gemini_status(port: int = 9222, timeout: float = 6.0) -> tuple[bool, str]:
    """Check if browser port 9222 is alive and Gemini chat box is ready."""
    if not is_cdp_ready(port):
        return False, "Cổng điều khiển 9222 chưa mở"
    try:
        return asyncio.run(_async_check_gemini_status(port, timeout=timeout))
    except Exception as e:
        return False, str(e)
