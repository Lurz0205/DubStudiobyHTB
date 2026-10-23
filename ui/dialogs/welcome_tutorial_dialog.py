"""Welcome and Setup Tutorial Dialog for first-time users.

Provides an intuitive step-by-step onboarding walkthrough and side-by-side
model comparison (faster-whisper large-v3 vs large-v3-turbo) to help users
configure the optimal settings for their hardware.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dubstudio.packaging import mark_first_run_done
from ui.icons import get_icon, get_pixmap
from ui.theme import COLORS


class WelcomeTutorialDialog(QDialog):
    """Modern onboarding wizard with Whisper model comparison and AI setup."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Chào mừng bạn đến với DubStudio — Hướng dẫn & Thiết lập ban đầu")
        self.setModal(True)

        self._selected_whisper_model = "sensevoice-small"
        self._selected_provider = "gemini_web"

        self._setup_ui()

        # Adjust dynamically to screen geometry to prevent overflow on small screens / high scaling
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            dlg_w = max(580, min(700, int(avail.width() * 0.86)))
            dlg_h = max(420, min(510, int(avail.height() * 0.82)))
            self.resize(dlg_w, dlg_h)
            self.move(
                avail.x() + max(0, (avail.width() - dlg_w) // 2),
                avail.y() + max(0, (avail.height() - dlg_h) // 2),
            )
        else:
            self.resize(680, 480)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # ─── Top Brand Header ───
        header_box = QFrame()
        header_box.setStyleSheet(
            f"background-color: {COLORS['surface_raised']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 6px 12px;"
        )
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(4, 2, 4, 2)
        h_layout.setSpacing(10)

        lbl_logo = QLabel()
        lbl_logo.setPixmap(get_pixmap("brand", "#38bdf8", 20))
        h_layout.addWidget(lbl_logo)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        lbl_app_name = QLabel("DubStudio — Trình lồng tiếng & Chỉnh sửa Video AI")
        lbl_app_name.setStyleSheet(f"font-size: 13.5px; font-weight: 700; color: {COLORS['accent']};")
        title_col.addWidget(lbl_app_name)

        self._lbl_step_indicator = QLabel("Bước 1 / 3: Giới thiệu quy trình lồng tiếng")
        self._lbl_step_indicator.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        title_col.addWidget(self._lbl_step_indicator)
        h_layout.addLayout(title_col)
        h_layout.addStretch(1)

        root.addWidget(header_box)

        # ─── Stacked Wizard Pages ───
        self._stack = QStackedWidget()
        self._stack.addWidget(self._wrap_scroll(self._create_step1_overview()))
        self._stack.addWidget(self._wrap_scroll(self._create_step2_whisper_comparison()))
        self._stack.addWidget(self._wrap_scroll(self._create_step3_translation_setup()))
        root.addWidget(self._stack, 1)

        # ─── Bottom Navigation Bar ───
        nav_box = QHBoxLayout()
        nav_box.setSpacing(10)

        self._chk_dont_show = QCheckBox("Không tự động hiện lại khi mở ứng dụng")
        self._chk_dont_show.setChecked(True)
        self._chk_dont_show.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px;")
        nav_box.addWidget(self._chk_dont_show)

        nav_box.addStretch(1)

        self._btn_prev = QPushButton("  Quay lại")
        self._btn_prev.setIcon(get_icon("chevron-left", "#6b7280", "#6b7280", 14))
        self._btn_prev.setIconSize(QSize(14, 14))
        self._btn_prev.setFixedSize(150, 36)
        self._btn_prev.setStyleSheet(
            f"QPushButton {{"
            f"  font-size: 12px; font-weight: 500; border: 1px solid {COLORS['border']}; border-radius: 6px; background-color: {COLORS['surface_raised']}; color: #f1f3f7;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {COLORS['border']};"
            f"}}"
            f"QPushButton:disabled {{"
            f"  background-color: transparent; border-color: #232832; color: #555e6d;"
            f"}}"
        )
        self._btn_prev.setEnabled(False)
        self._btn_prev.clicked.connect(self._on_prev_step)
        nav_box.addWidget(self._btn_prev)

        self._btn_next = QPushButton("  Tiếp tục")
        self._btn_next.setIcon(get_icon("chevron-right", "#ffffff", "#ffffff", 14))
        self._btn_next.setIconSize(QSize(14, 14))
        self._btn_next.setObjectName("primary")
        self._btn_next.setFixedSize(150, 36)
        self._btn_next.setStyleSheet(
            f"QPushButton {{"
            f"  font-size: 12px; font-weight: 600; border: none; border-radius: 6px; background-color: {COLORS['accent']}; color: #ffffff;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {COLORS['accent_hover']};"
            f"}}"
        )
        self._btn_next.clicked.connect(self._on_next_step)
        nav_box.addWidget(self._btn_next)

        root.addLayout(nav_box)

    def _wrap_scroll(self, content_widget: QWidget) -> QWidget:
        """Wrap step content inside a seamless scroll area to prevent window overflow."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setWidget(content_widget)
        return scroll

    def _create_step1_overview(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        lbl_title = QLabel("Quy trình lồng tiếng tự động 1-Click")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f3f7;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "DubStudio được thiết kế chuyên biệt để tự động hóa trọn gói quá trình dịch thuật và thuyết minh "
            "video tiếng Trung sang tiếng Việt với chất lượng giọng đọc tự nhiên và thời gian đồng bộ chuẩn xác:"
        )
        lbl_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; line-height: 1.4;")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        steps_grid = QVBoxLayout()
        steps_grid.setSpacing(6)

        steps_data = [
            ("1. Nhận diện giọng nói (ASR)", "Tự động nghe, bóc băng và phân đoạn từng câu nói tiếng Trung bằng mô hình Whisper chính xác cao."),
            ("2. Dịch thuật theo ngữ cảnh", "AI dịch thuật linh hoạt (Gemini Web hoặc Tự dịch thủ công) chuyển ngữ sang câu văn thuần Việt tự nhiên, phù hợp tốc độ nói."),
            ("3. Tạo giọng đọc AI (VieNeu-TTS)", "Công nghệ thuyết minh AI tiếng Việt chất lượng cao chạy offline hoàn toàn trên máy bạn, hỗ trợ giọng Nam và Nữ."),
            ("4. Tự động khớp âm & Xuất video", "Hệ thống tự cân chỉnh tempo, chống đè giọng và khắc phụ đề 2 ngôn ngữ lên video hoàn chỉnh."),
        ]

        for s_title, s_detail in steps_data:
            card = QFrame()
            card.setStyleSheet(
                f"background-color: {COLORS['surface_raised']}; "
                f"border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 8px 12px;"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(2, 2, 2, 2)
            c_lay.setSpacing(2)
            st = QLabel(s_title)
            st.setStyleSheet(f"color: {COLORS['accent']}; font-weight: 600; font-size: 12px;")
            sd = QLabel(s_detail)
            sd.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
            sd.setWordWrap(True)
            c_lay.addWidget(st)
            c_lay.addWidget(sd)
            steps_grid.addWidget(card)

        layout.addLayout(steps_grid)
        layout.addStretch(1)
        return w

    def _create_step2_whisper_comparison(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        lbl_title = QLabel("Lựa chọn Mô hình Nhận dạng Giọng nói Tiếng Trung (ASR)")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f3f7;")
        layout.addWidget(lbl_title)

        lbl_guide = QLabel(
            "Mô hình nhận dạng (ASR) quyết định độ chính xác khi bóc tách câu thoại từ video gốc. "
            "Dưới đây là thông tin so sánh chi tiết giúp bạn chọn mô hình phù hợp với nhu cầu:"
        )
        lbl_guide.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px; line-height: 1.4;")
        lbl_guide.setWordWrap(True)
        layout.addWidget(lbl_guide)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)

        self._btn_group_whisper = QButtonGroup(self)

        # ── Card 1: SenseVoice-Small (Khuyên dùng mặc định) ──
        self._c1 = QFrame()
        self._c1.setObjectName("bento_card")
        self._c1.setCursor(Qt.CursorShape.PointingHandCursor)
        v1 = QVBoxLayout(self._c1)
        v1.setContentsMargins(12, 10, 12, 10)
        v1.setSpacing(6)

        self._rb_turbo = QRadioButton("  SenseVoice-Small (Khuyên dùng mặc định)")
        self._rb_turbo.setChecked(True)
        self._btn_group_whisper.addButton(self._rb_turbo, 0)
        v1.addWidget(self._rb_turbo)

        turbo_info = QLabel(
            "<b>Dung lượng:</b> ~900 MB<br><br>"
            "<b>Ưu điểm nổi bật:</b><br>"
            "• Tốc độ nhận diện siêu nhanh, tốn ít tài nguyên máy.<br>"
            "• Khả năng tách câu thoại tự nhiên và mượt mà.<br><br>"
            "<b>Khuyên dùng:</b> Thích hợp cho các video dài và cần tốc độ xử lý nhanh."
        )
        turbo_info.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; line-height: 1.4;")
        turbo_info.setWordWrap(True)
        v1.addWidget(turbo_info)
        v1.addStretch(1)

        cards_row.addWidget(self._c1, 1)

        # ── Card 2: faster-whisper large-v3 (Chuẩn xác tối đa) ──
        self._c2 = QFrame()
        self._c2.setObjectName("bento_card")
        self._c2.setCursor(Qt.CursorShape.PointingHandCursor)
        v2 = QVBoxLayout(self._c2)
        v2.setContentsMargins(12, 10, 12, 10)
        v2.setSpacing(6)

        self._rb_v3 = QRadioButton("  faster-whisper large-v3 (Chuẩn xác tối đa)")
        self._btn_group_whisper.addButton(self._rb_v3, 1)
        v2.addWidget(self._rb_v3)

        v3_info = QLabel(
            "<b>Dung lượng:</b> ~3.09 GB<br><br>"
            "<b>Ưu điểm nổi bật:</b><br>"
            "• Độ chính xác bóc băng tối đa, xử lý tốt âm thanh nhiều tạp âm.<br>"
            "• Phân đoạn câu chuẩn chỉnh theo từng câu thoại ngắn.<br><br>"
            "<b>Khuyên dùng:</b> Video ngắn hoặc video có chất lượng âm thanh phức tạp, yêu cầu cấu hình máy tốt."
        )
        v3_info.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px; line-height: 1.4;")
        v3_info.setWordWrap(True)
        v2.addWidget(v3_info)
        v2.addStretch(1)

        cards_row.addWidget(self._c2, 1)

        # Click card body to select
        self._c1.mousePressEvent = lambda e: self._rb_turbo.setChecked(True)
        self._c2.mousePressEvent = lambda e: self._rb_v3.setChecked(True)

        self._rb_turbo.toggled.connect(self._sync_whisper_card_styles)
        self._rb_v3.toggled.connect(self._sync_whisper_card_styles)
        self._sync_whisper_card_styles()

        layout.addLayout(cards_row)
        layout.addStretch(1)
        return w

    def _sync_whisper_card_styles(self):
        if not hasattr(self, "_c1") or not hasattr(self, "_c2"):
            return
        is_turbo = self._rb_turbo.isChecked()
        active_style = (
            f"QFrame#bento_card {{"
            f"  background-color: #0d2238;"
            f"  border: 2px solid {COLORS['accent']};"
            f"  border-radius: 8px;"
            f"}}"
            "QLabel { border: none; background: transparent; }"
            "QRadioButton { border: none; background: transparent; }"
        )
        inactive_style = (
            f"QFrame#bento_card {{"
            f"  background-color: {COLORS['surface_raised']};"
            f"  border: 1px solid {COLORS['border']};"
            f"  border-radius: 8px;"
            f"}}"
            "QLabel { border: none; background: transparent; }"
            "QRadioButton { border: none; background: transparent; }"
        )

        self._c1.setStyleSheet(active_style if is_turbo else inactive_style)
        self._c2.setStyleSheet(inactive_style if is_turbo else active_style)

        if is_turbo:
            self._rb_turbo.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['accent']}; border: none; background: transparent;")
            self._rb_v3.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_secondary']}; border: none; background: transparent;")
        else:
            self._rb_turbo.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_secondary']}; border: none; background: transparent;")
            self._rb_v3.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['accent']}; border: none; background: transparent;")

    def _create_step3_translation_setup(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        lbl_title = QLabel("Lựa chọn Phương thức Dịch thuật AI")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f3f7;")
        layout.addWidget(lbl_title)

        lbl_guide = QLabel(
            "Bạn có thể chọn phương thức dịch thuật phù hợp dưới đây. "
            "Cài đặt này có thể linh hoạt chuyển đổi bất cứ lúc nào trong trang 'Cài đặt hệ thống':"
        )
        lbl_guide.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px; line-height: 1.4;")
        lbl_guide.setWordWrap(True)
        layout.addWidget(lbl_guide)

        self._btn_group_trans = QButtonGroup(self)

        # Option A: Gemini Web
        self._box_gemini = QFrame()
        self._box_gemini.setObjectName("trans_card")
        self._box_gemini.setCursor(Qt.CursorShape.PointingHandCursor)
        bg_lay = QVBoxLayout(self._box_gemini)
        bg_lay.setContentsMargins(12, 10, 12, 10)
        bg_lay.setSpacing(4)
        self._rb_gemini = QRadioButton("  Gemini Web (Trình duyệt độc lập — Miễn phí hoàn toàn không cần API Key)")
        self._rb_gemini.setChecked(True)
        self._btn_group_trans.addButton(self._rb_gemini, 0)
        bg_lay.addWidget(self._rb_gemini)
        lbl_g_desc = QLabel(
            "• Tự động mở cửa sổ trình duyệt Gemini nhỏ gọn trong nền để dịch thuật tự động.<br>"
            "• Miễn phí 100%, không giới hạn lượt dùng và không cần nhập mã API Key phức tạp."
        )
        lbl_g_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; line-height: 1.4;")
        bg_lay.addWidget(lbl_g_desc)
        layout.addWidget(self._box_gemini)

        # Option B: Manual translation via external AI
        self._box_manual = QFrame()
        self._box_manual.setObjectName("trans_card")
        self._box_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        bq_lay = QVBoxLayout(self._box_manual)
        bq_lay.setContentsMargins(12, 10, 12, 10)
        bq_lay.setSpacing(4)
        self._rb_manual = QRadioButton("  Tự dịch thủ công (ChatGPT, Claude, Gemini Web bên ngoài)")
        self._btn_group_trans.addButton(self._rb_manual, 1)
        bq_lay.addWidget(self._rb_manual)
        lbl_q_desc = QLabel(
            "• Sau khi trích xuất phụ đề Trung, ứng dụng sẽ cung cấp prompt để bạn copy sang AI dịch.<br>"
            "• Bạn chỉ cần dán kết quả dịch vào cửa sổ của DubStudio để tiếp tục tạo giọng đọc."
        )
        lbl_q_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; line-height: 1.4;")
        bq_lay.addWidget(lbl_q_desc)
        layout.addWidget(self._box_manual)

        # Click card body to select
        self._box_gemini.mousePressEvent = lambda e: self._rb_gemini.setChecked(True)
        self._box_manual.mousePressEvent = lambda e: self._rb_manual.setChecked(True)

        self._rb_gemini.toggled.connect(self._sync_trans_card_styles)
        self._rb_manual.toggled.connect(self._sync_trans_card_styles)
        self._sync_trans_card_styles()

        layout.addStretch(1)
        return w

    def _sync_trans_card_styles(self):
        if not hasattr(self, "_box_gemini") or not hasattr(self, "_box_manual"):
            return
        is_gemini = self._rb_gemini.isChecked()
        active_style = (
            f"QFrame#trans_card {{"
            f"  background-color: #0d2238;"
            f"  border: 2px solid {COLORS['accent']};"
            f"  border-radius: 8px;"
            f"}}"
            "QLabel { border: none; background: transparent; }"
            "QRadioButton { border: none; background: transparent; }"
        )
        inactive_style = (
            f"QFrame#trans_card {{"
            f"  background-color: {COLORS['surface_raised']};"
            f"  border: 1px solid {COLORS['border']};"
            f"  border-radius: 8px;"
            f"}}"
            "QLabel { border: none; background: transparent; }"
            "QRadioButton { border: none; background: transparent; }"
        )

        self._box_gemini.setStyleSheet(active_style if is_gemini else inactive_style)
        self._box_manual.setStyleSheet(inactive_style if is_gemini else active_style)

        if is_gemini:
            self._rb_gemini.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['accent']}; border: none; background: transparent;")
            self._rb_manual.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_secondary']}; border: none; background: transparent;")
        else:
            self._rb_gemini.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_secondary']}; border: none; background: transparent;")
            self._rb_manual.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['accent']}; border: none; background: transparent;")

    def _on_prev_step(self):
        curr = self._stack.currentIndex()
        if curr > 0:
            self._stack.setCurrentIndex(curr - 1)
            self._update_nav_state()

    def _on_next_step(self):
        curr = self._stack.currentIndex()
        if curr < self._stack.count() - 1:
            self._stack.setCurrentIndex(curr + 1)
            self._update_nav_state()
        else:
            self._finish_tutorial()

    def _update_nav_state(self):
        curr = self._stack.currentIndex()
        self._btn_prev.setEnabled(curr > 0)
        prev_icon_color = "#ffffff" if curr > 0 else "#6b7280"
        self._btn_prev.setIcon(get_icon("chevron-left", prev_icon_color, prev_icon_color, 14))

        if curr == 0:
            self._lbl_step_indicator.setText("Bước 1 / 3: Giới thiệu quy trình lồng tiếng")
            self._btn_next.setText("  Tiếp tục")
            self._btn_next.setIcon(get_icon("chevron-right", "#ffffff", "#ffffff", 14))
        elif curr == 1:
            self._lbl_step_indicator.setText("Bước 2 / 3: Lựa chọn mô hình nhận dạng giọng nói")
            self._btn_next.setText("  Tiếp tục")
            self._btn_next.setIcon(get_icon("chevron-right", "#ffffff", "#ffffff", 14))
        elif curr == 2:
            self._lbl_step_indicator.setText("Bước 3 / 3: Lựa chọn phương thức dịch thuật AI")
            self._btn_next.setText("  Hoàn tất && Bắt đầu")
            self._btn_next.setIcon(get_icon("check", "#ffffff", "#ffffff", 14))

    @property
    def _selected_whisper_model(self) -> str:
        if hasattr(self, "_rb_v3") and self._rb_v3.isChecked():
            return "large-v3"
        elif hasattr(self, "_rb_turbo") and self._rb_turbo.isChecked():
            return "sensevoice-small"
        return getattr(self, "_whisper_model_val", "large-v3")

    @_selected_whisper_model.setter
    def _selected_whisper_model(self, val: str):
        self._whisper_model_val = val
        if hasattr(self, "_rb_v3") and hasattr(self, "_rb_turbo"):
            if val == "sensevoice-small":
                self._rb_turbo.setChecked(True)
            else:
                self._rb_v3.setChecked(True)

    def _finish_tutorial(self):
        """Save selected configurations and mark first-run completed."""
        whisper_choice = self._selected_whisper_model
        provider_choice = "gemini_web" if self._rb_gemini.isChecked() else "manual"

        # Apply settings asynchronously or directly via API
        try:
            import requests
            payload = {
                "whisper_model": whisper_choice,
                "translation_provider": provider_choice,
            }
            requests.post("http://127.0.0.1:8765/api/settings", json=payload, timeout=5)
        except Exception:
            # Fallback to direct .env persistence
            try:
                from pathlib import Path
                env_p = Path(".env")
                content = env_p.read_text(encoding="utf-8") if env_p.exists() else ""
                lines = [l for l in content.splitlines() if not l.startswith("WHISPER_MODEL=") and not l.startswith("TRANSLATION_PROVIDER=")]
                lines.append(f"WHISPER_MODEL={whisper_choice}")
                lines.append(f"TRANSLATION_PROVIDER={provider_choice}")
                env_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except Exception:
                pass

        if self._chk_dont_show.isChecked():
            mark_first_run_done(True)

        self.accept()
