"""Interactive dialog for user to copy Chinese translation prompt to external AI and paste translated response."""
from __future__ import annotations

import json
from typing import Optional
import requests

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ui.icons import get_icon


class ManualTranslateDialog(QDialog):
    """Dialog allowing user to translate Chinese video subtitles via external AI (ChatGPT, Claude, Gemini Web)."""

    def __init__(self, prompt_text: str, job_id: str, total_items: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DubStudio — Tự dịch qua AI bên ngoài (ChatGPT / Claude / Gemini)")
        self.resize(780, 680)
        self.setMinimumSize(640, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._prompt_text = prompt_text
        self._job_id = job_id
        self._total_items = total_items
        self._submitted = False

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Header Banner
        header = QLabel(
            "<b>Dịch thủ công qua AI bên ngoài</b><br>"
            "<span style='color: #94a3b8; font-size: 12px;'>"
            "Sao chép Prompt bên dưới, dán vào ChatGPT, Claude hoặc Gemini Web. Sau khi AI dịch xong, hãy sao chép toàn bộ câu trả lời và dán vào ô kết quả."
            "</span>"
        )
        header.setWordWrap(True)
        header.setStyleSheet("QLabel { font-size: 15px; color: #f8fafc; }")
        layout.addWidget(header)

        # 2. Step 1: Prompt Box
        lbl_step1 = QLabel(f"<b>Bước 1:</b> Sao chép Prompt tiếng Trung ({self._total_items or 'tất cả'} câu)")
        lbl_step1.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")
        layout.addWidget(lbl_step1)

        self._txt_prompt = QTextEdit()
        self._txt_prompt.setReadOnly(True)
        self._txt_prompt.setPlainText(self._prompt_text)
        self._txt_prompt.setFixedHeight(160)
        self._txt_prompt.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #cbd5e1;
                font-family: Consolas, monospace;
                font-size: 12px;
                padding: 8px;
            }
        """)
        layout.addWidget(self._txt_prompt)

        # Copy & Quick Links Row
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self._btn_copy = QPushButton("  Sao chép toàn bộ Prompt")
        self._btn_copy.setIcon(get_icon("copy", "#ffffff", "#ffffff", 14))
        self._btn_copy.setFixedHeight(34)
        self._btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self._btn_copy.clicked.connect(self._copy_prompt)
        action_row.addWidget(self._btn_copy)

        btn_gemini = QPushButton("  Mở Gemini Web")
        btn_gemini.setIcon(get_icon("globe", "#38bdf8", "#38bdf8", 13))
        btn_gemini.setFixedHeight(34)
        btn_gemini.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://gemini.google.com/app")))
        action_row.addWidget(btn_gemini)

        btn_chatgpt = QPushButton("  Mở ChatGPT")
        btn_chatgpt.setIcon(get_icon("globe", "#10b981", "#10b981", 13))
        btn_chatgpt.setFixedHeight(34)
        btn_chatgpt.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://chatgpt.com")))
        action_row.addWidget(btn_chatgpt)

        btn_claude = QPushButton("  Mở Claude")
        btn_claude.setIcon(get_icon("globe", "#f59e0b", "#f59e0b", 13))
        btn_claude.setFixedHeight(34)
        btn_claude.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://claude.ai")))
        action_row.addWidget(btn_claude)

        action_row.addStretch()
        layout.addLayout(action_row)

        # 3. Step 2: Response Box
        lbl_step2 = QLabel("<b>Bước 2:</b> Dán toàn bộ câu trả lời của AI vào đây")
        lbl_step2.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-top: 8px;")
        layout.addWidget(lbl_step2)

        self._txt_response = QTextEdit()
        self._txt_response.setPlaceholderText(
            "Nhấp chuột phải chọn 'Dán' hoặc bấm phím Ctrl + V câu trả lời của AI vào đây...\n"
            "(Hỗ trợ mọi định dạng: danh sách [1] câu 1, 1. câu 1, hoặc định dạng JSON)"
        )
        self._txt_response.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                font-family: Consolas, monospace;
                font-size: 12px;
                padding: 10px;
            }
            QTextEdit:focus {
                border: 1px solid #38bdf8;
            }
        """)
        layout.addWidget(self._txt_response, 1)

        # 4. Bottom Controls (Confirm / Cancel)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self._lbl_hint = QLabel("💡 Lưu ý: Càng giữ nguyên đánh số [1], [2]... thì độ khớp phụ đề càng chính xác 100%.")
        self._lbl_hint.setStyleSheet("color: #64748b; font-size: 12px;")
        bottom_row.addWidget(self._lbl_hint)
        bottom_row.addStretch()

        btn_cancel = QPushButton("  Hủy bỏ")
        btn_cancel.setFixedHeight(36)
        btn_cancel.clicked.connect(self._on_cancel)
        bottom_row.addWidget(btn_cancel)

        self._btn_submit = QPushButton("  ✓ Xác nhận bản dịch & Tiếp tục")
        self._btn_submit.setFixedHeight(36)
        self._btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self._btn_submit.clicked.connect(self._on_submit)
        bottom_row.addWidget(self._btn_submit)

        layout.addLayout(bottom_row)

    def _copy_prompt(self):
        """Copy prompt text to system clipboard with visual feedback."""
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self._prompt_text)
            self._btn_copy.setText("  ✓ Đã sao chép vào Clipboard!")
            self._btn_copy.setStyleSheet("""
                QPushButton {
                    background-color: #059669;
                    color: #ffffff;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 0 16px;
                }
            """)
            QTimer.singleShot(2500, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self._btn_copy.setText("  Sao chép toàn bộ Prompt")
        self._btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)

    def _on_submit(self):
        text = self._txt_response.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Chưa có nội dung", "Vui lòng dán câu trả lời dịch của AI vào ô Bước 2 trước khi bấm xác nhận!")
            return

        self._submitted = True
        try:
            r = requests.post(
                f"http://127.0.0.1:8765/api/jobs/{self._job_id}/manual-translate",
                json={"text": text, "cancelled": False},
                timeout=10,
            )
            r.raise_for_status()
        except Exception as e:
            # Fallback to direct workspace file writing
            try:
                from pathlib import Path
                ws_f = Path("workspace") / self._job_id / "manual_translate_response.json"
                ws_f.write_text(json.dumps({"text": text, "cancelled": False}, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        self.accept()

    def _on_cancel(self):
        self._notify_cancellation()
        self.reject()

    def closeEvent(self, event):
        if not self._submitted:
            self._notify_cancellation()
        super().closeEvent(event)

    def _notify_cancellation(self):
        try:
            requests.post(
                f"http://127.0.0.1:8765/api/jobs/{self._job_id}/manual-translate",
                json={"cancelled": True},
                timeout=5,
            )
        except Exception:
            try:
                from pathlib import Path
                ws_f = Path("workspace") / self._job_id / "manual_translate_response.json"
                ws_f.write_text(json.dumps({"cancelled": True}, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
