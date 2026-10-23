"""Settings Page: Manage translation providers, models, and default voices with smooth scrolling."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon
from ui.theme import COLORS
from ui.widgets.subtitle_editor import MALE_VOICES, FEMALE_VOICES
from ui.workers import LoadSettingsWorker, SaveSettingsWorker
from dubstudio.config import get_api_base_url


AVAILABLE_TRANSLATION_MODELS = [
    "gemini_web",
    "manual",
    "gemini-2.5-flash",
]


class SettingsPage(QWidget):
    """Settings page with smooth vertical scrolling for translation and audio configuration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[any] = []
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scroll Area for comfortable vertical scrolling
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(20)

        # Title
        title = QLabel("Cài đặt hệ thống")
        title.setObjectName("section_title")
        layout.addWidget(title)

        # 1. Translation Engine Box
        api_box = QGroupBox("Cấu hình Dịch thuật (Gemini Web hoặc Tự dịch thủ công)")
        api_form = QVBoxLayout(api_box)
        api_form.setSpacing(12)

        # Translation Provider selection
        lbl_provider = QLabel("Phương thức dịch thuật:")
        lbl_provider.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px;")
        api_form.addWidget(lbl_provider)

        self._combo_provider = QComboBox()
        self._combo_provider.addItems([
            "Gemini Web (Trình duyệt độc lập trong nền - Miễn phí không cần API Key)",
            "Tự dịch thủ công (Sao chép Prompt dán vào ChatGPT / Claude / Gemini ngoài)",
        ])
        self._combo_provider.setFixedHeight(30)
        self._combo_provider.currentIndexChanged.connect(self._on_provider_changed)
        api_form.addWidget(self._combo_provider)

        # ─── Manual Translation Guidance Container ───
        self._manual_container = QWidget()
        manual_layout = QVBoxLayout(self._manual_container)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(10)

        manual_box = QFrame()
        manual_box.setStyleSheet(
            f"background-color: {COLORS['surface_raised']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 14px;"
        )
        manual_box_layout = QVBoxLayout(manual_box)
        manual_box_layout.setSpacing(10)
        manual_box_layout.setContentsMargins(12, 12, 12, 12)

        lbl_manual_title = QLabel("Cơ chế Tự dịch thủ công qua AI ngoài (ChatGPT / Claude / Gemini):")
        lbl_manual_title.setStyleSheet(f"color: {COLORS['accent']}; font-weight: 600; font-size: 12px;")
        manual_box_layout.addWidget(lbl_manual_title)

        lbl_manual_desc = QLabel(
            "• Khi bạn bấm '1. Tạo phụ đề' ở Tab Studio, sau khi AI nhận dạng giọng nói tiếng Trung xong, "
            "hệ thống sẽ tự động bật cửa sổ 'Tự dịch thủ công'.\n"
            "• Cửa sổ này có nút 1-click 'Sao chép toàn bộ Prompt' và các nút mở nhanh ChatGPT / Claude / Gemini Web.\n"
            "• Bạn chỉ việc dán prompt vào AI để dịch, sau đó sao chép toàn bộ câu trả lời của AI dán lại vào ô kết quả và bấm 'Xác nhận'.\n"
            "• Phù hợp 100% cho mọi người dùng không muốn cài đặt API Key hoặc muốn tận dụng tài khoản ChatGPT Plus / Claude Pro cá nhân."
        )
        lbl_manual_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px; line-height: 1.5;")
        lbl_manual_desc.setWordWrap(True)
        manual_box_layout.addWidget(lbl_manual_desc)

        manual_layout.addWidget(manual_box)
        api_form.addWidget(self._manual_container)

        # ─── Gemini Web (CDP) Settings Container ───
        self._gemini_web_container = QWidget()
        cdp_layout = QVBoxLayout(self._gemini_web_container)
        cdp_layout.setContentsMargins(0, 0, 0, 0)
        cdp_layout.setSpacing(10)

        cdp_box = QFrame()
        cdp_box.setStyleSheet(
            f"background-color: {COLORS['surface_raised']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 14px;"
        )
        cdp_box_layout = QVBoxLayout(cdp_box)
        cdp_box_layout.setSpacing(10)
        cdp_box_layout.setContentsMargins(12, 12, 12, 12)

        lbl_cdp_title = QLabel("Mini Client Google Gemini (Cửa sổ ứng dụng độc lập):")
        lbl_cdp_title.setStyleSheet(f"color: {COLORS['accent']}; font-weight: 600; font-size: 12px;")
        cdp_box_layout.addWidget(lbl_cdp_title)

        lbl_cdp_desc = QLabel(
            "• Hoạt động như một ứng dụng độc lập, không thanh URL, không tab rườm rà và không ảnh hưởng đến trình duyệt duyệt web hàng ngày của bạn.\n"
            "• Hỗ trợ dịch miễn phí không giới hạn. Có thể dùng dạng khách (không cần tài khoản) hoặc đăng nhập Google một lần duy nhất để lưu lại.\n"
            "• Nhấn 'Mở Mini Client Gemini' bên dưới để khởi động cửa sổ."
        )
        lbl_cdp_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px; line-height: 1.5;")
        lbl_cdp_desc.setWordWrap(True)
        cdp_box_layout.addWidget(lbl_cdp_desc)

        cdp_btn_row = QHBoxLayout()
        btn_open_gemini = QPushButton(" Mở Mini Client Gemini")
        btn_open_gemini.setIcon(get_icon("link", "#38bdf8", "#38bdf8", 13))
        btn_open_gemini.setObjectName("secondary")
        btn_open_gemini.setFixedHeight(32)
        btn_open_gemini.clicked.connect(self._open_gemini_browser)
        cdp_btn_row.addWidget(btn_open_gemini)

        btn_check_gemini = QPushButton(" Kiểm tra kết nối")
        btn_check_gemini.setIcon(get_icon("check", "#38bdf8", "#38bdf8", 13))
        btn_check_gemini.setObjectName("compact")
        btn_check_gemini.setFixedHeight(32)
        btn_check_gemini.clicked.connect(self._check_gemini_browser)
        cdp_btn_row.addWidget(btn_check_gemini)
        cdp_btn_row.addStretch(1)

        cdp_box_layout.addLayout(cdp_btn_row)

        self._lbl_cdp_status = QLabel("Trạng thái: Đang kiểm tra Mini Client...")
        self._lbl_cdp_status.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        cdp_box_layout.addWidget(self._lbl_cdp_status)

        cdp_layout.addWidget(cdp_box)
        self._gemini_web_container.setVisible(False)
        api_form.addWidget(self._gemini_web_container)

        layout.addWidget(api_box)

        # 2. Voice Defaults Box (VieNeu-TTS Offline)
        voice_box = QGroupBox("Giọng đọc mặc định (VieNeu-TTS Offline)")
        v_form = QVBoxLayout(voice_box)
        v_form.setSpacing(12)

        # Male voice
        lbl_male = QLabel("Giọng Nam mặc định (Dùng cho nhân vật Nam / Thuyết minh nam):")
        lbl_male.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px;")
        v_form.addWidget(lbl_male)
        male_layout = QHBoxLayout()
        self._combo_male = QComboBox()
        self._combo_male.addItems(MALE_VOICES)
        self._combo_male.setFixedHeight(30)
        male_layout.addWidget(self._combo_male, 1)

        btn_listen_male = QPushButton(" Nghe thử")
        btn_listen_male.setIcon(get_icon("volume", "#38bdf8", "#38bdf8", 13))
        btn_listen_male.setObjectName("compact")
        btn_listen_male.setFixedHeight(30)
        btn_listen_male.clicked.connect(lambda: self._play_voice_preview(self._combo_male.currentText()))
        male_layout.addWidget(btn_listen_male)
        v_form.addLayout(male_layout)

        # Female voice
        lbl_female = QLabel("Giọng Nữ mặc định (Dùng cho nhân vật Nữ / Thuyết minh nữ):")
        lbl_female.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px;")
        v_form.addWidget(lbl_female)
        female_layout = QHBoxLayout()
        self._combo_female = QComboBox()
        self._combo_female.addItems(FEMALE_VOICES)
        self._combo_female.setFixedHeight(30)
        female_layout.addWidget(self._combo_female, 1)

        btn_listen_female = QPushButton(" Nghe thử")
        btn_listen_female.setIcon(get_icon("volume", "#38bdf8", "#38bdf8", 13))
        btn_listen_female.setObjectName("compact")
        btn_listen_female.setFixedHeight(30)
        btn_listen_female.clicked.connect(lambda: self._play_voice_preview(self._combo_female.currentText()))
        female_layout.addWidget(btn_listen_female)
        v_form.addLayout(female_layout)

        # Audio player for voice previews
        self._preview_player = QMediaPlayer(self)
        self._audio_out = QAudioOutput(self)
        self._preview_player.setAudioOutput(self._audio_out)
        self._audio_out.setVolume(1.0)

        layout.addWidget(voice_box)

        # 3. Speech Recognition Model Box (Whisper Offline)
        asr_box = QGroupBox("Mô hình Nhận dạng Giọng nói Tiếng Trung (ASR - faster-whisper)")
        asr_form = QVBoxLayout(asr_box)
        asr_form.setSpacing(10)

        lbl_asr_model = QLabel("Lựa chọn mô hình nhận dạng câu thoại tiếng Trung:")
        lbl_asr_model.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px;")
        asr_form.addWidget(lbl_asr_model)

        self._combo_asr_model = QComboBox()
        self._combo_asr_model.addItem("SenseVoice-Small (Tốc độ siêu nhanh — Khuyên dùng cho video dài)", "sensevoice-small")
        self._combo_asr_model.addItem("faster-whisper large-v3 (Độ chính xác cao — Phù hợp âm thanh nhiều tạp âm)", "large-v3")
        self._combo_asr_model.setFixedHeight(30)
        self._combo_asr_model.activated.connect(self._on_asr_model_user_selected)
        asr_form.addWidget(self._combo_asr_model)

        lbl_asr_hint = QLabel(
            "• SenseVoice-Small: Mô hình nhận diện giọng nói tiếng Trung với tốc độ siêu nhanh, khuyên dùng cho các video dài.\n"
            "• faster-whisper large-v3: Nhận dạng chuẩn xác tối đa, xử lý tốt âm thanh nhiều tạp âm hoặc phát âm khó, yêu cầu cấu hình máy tốt."
        )
        lbl_asr_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; line-height: 1.4;")
        lbl_asr_hint.setWordWrap(True)
        asr_form.addWidget(lbl_asr_hint)

        layout.addWidget(asr_box)

        # 3. Vocal Separation Model Box
        sep_box = QGroupBox("Tách nhạc nền & Lời thoại (Vocal Separation)")
        sep_form = QVBoxLayout(sep_box)
        sep_form.setSpacing(10)

        lbl_sep_model = QLabel("Lựa chọn mô hình tách nhạc nền:")
        lbl_sep_model.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px;")
        sep_form.addWidget(lbl_sep_model)

        self._combo_sep_model = QComboBox()
        self._combo_sep_model.addItem("Kim Vocal 2 (Tốc độ nhanh, nhẹ — Phù hợp đa số cấu hình)", "Kim_Vocal_2.onnx")
        self._combo_sep_model.addItem("BS-RoFormer EP 317 (Chất lượng cao — Tách âm sạch nhất, cần GPU rời)", "model_bs_roformer_ep_317_sdr_12.9755.ckpt")
        self._combo_sep_model.setFixedHeight(30)
        self._combo_sep_model.activated.connect(self._on_sep_model_user_selected)
        sep_form.addWidget(self._combo_sep_model)

        lbl_sep_hint = QLabel(
            "💡 Hướng dẫn chọn mô hình tách nhạc:\n"
            "• Kim Vocal 2: Tốc độ xử lý nhanh, tốn ít tài nguyên, phù hợp cho đa số cấu hình máy.\n"
            "• BS-RoFormer EP 317: Tách sạch và giữ trọn vẹn nhạc nền nhất, yêu cầu cấu hình máy có GPU rời."
        )
        lbl_sep_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; line-height: 1.4;")
        lbl_sep_hint.setWordWrap(True)
        sep_form.addWidget(lbl_sep_hint)

        layout.addWidget(sep_box)

        # 4. AI Models & Data Package Manager Box
        self._comp_box = QGroupBox("Quản lý Gói mô hình AI & Dữ liệu bổ trợ")
        self._comp_layout = QVBoxLayout(self._comp_box)
        self._comp_layout.setSpacing(12)

        comp_header_row = QHBoxLayout()
        lbl_comp_desc = QLabel(
            "Tất cả mô hình AI được tải về và thực thi hoàn toàn ngoại tuyến (offline) trên máy tính của bạn.\n"
            "Bạn có thể kiểm tra trạng thái và tải trực tiếp các gói còn thiếu dưới đây:"
        )
        lbl_comp_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px; line-height: 1.4;")
        lbl_comp_desc.setWordWrap(True)
        comp_header_row.addWidget(lbl_comp_desc, 1)

        btn_refresh_comp = QPushButton(" Làm mới trạng thái")
        btn_refresh_comp.setIcon(get_icon("refresh", "#38bdf8", "#38bdf8", 12))
        btn_refresh_comp.setFixedHeight(30)
        btn_refresh_comp.setObjectName("secondary")
        btn_refresh_comp.setStyleSheet("padding: 0 12px; font-size: 11.5px;")
        btn_refresh_comp.clicked.connect(self._refresh_components_ui)
        comp_header_row.addWidget(btn_refresh_comp, 0, Qt.AlignmentFlag.AlignTop)

        self._comp_layout.addLayout(comp_header_row)

        self._comp_rows_widget = QWidget()
        self._comp_rows_layout = QVBoxLayout(self._comp_rows_widget)
        self._comp_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._comp_rows_layout.setSpacing(8)
        self._comp_layout.addWidget(self._comp_rows_widget)

        layout.addWidget(self._comp_box)

        # 5. GPU Status & Data Packages Box
        from dubstudio.gpu_check import inspect_gpu_and_driver
        from dubstudio.version import get_version_info

        gpu_box = QGroupBox("Gói dữ liệu & Trạng thái đồ họa (GPU)")
        gpu_layout = QVBoxLayout(gpu_box)
        gpu_layout.setSpacing(10)

        self._lbl_gpu_info = QLabel("Đang kiểm tra thông số đồ họa...")
        self._lbl_gpu_info.setStyleSheet(
            f"background-color: {COLORS['surface_raised']}; color: {COLORS['text_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 12px; font-size: 11.5px; line-height: 1.6;"
        )
        self._lbl_gpu_info.setWordWrap(True)
        gpu_layout.addWidget(self._lbl_gpu_info)

        gpu_btn_layout = QHBoxLayout()
        btn_recheck_gpu = QPushButton(" Kiểm tra lại GPU & Mô hình")
        btn_recheck_gpu.setIcon(get_icon("refresh", "#38bdf8", "#38bdf8", 13))
        btn_recheck_gpu.setObjectName("secondary")
        btn_recheck_gpu.setFixedHeight(30)
        btn_recheck_gpu.clicked.connect(self._refresh_all_status)
        gpu_btn_layout.addWidget(btn_recheck_gpu)
        gpu_btn_layout.addStretch(1)
        gpu_layout.addLayout(gpu_btn_layout)

        layout.addWidget(gpu_box)

        # 4. About App Box
        about_box = QGroupBox("Về ứng dụng DubStudio")
        about_layout = QVBoxLayout(about_box)
        v_info = get_version_info()
        lbl_about = QLabel(
            f"<b>DubStudio</b> — Phiên bản: <span style='color:#38bdf8;'>v{v_info['version']}</span> | "
            f"Mã commit: <span style='color:#a78bfa;'>{v_info['commit']}</span> | "
            f"Schema Version: <span>v{v_info['schema_version']}</span>\n"
            f"Hệ thống lồng tiếng & dịch thuật video cục bộ, bảo vệ quyền riêng tư 100%."
        )
        lbl_about.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; line-height: 1.5;")
        about_layout.addWidget(lbl_about)
        # Troubleshooting & Repair Box
        trouble_box = QGroupBox("Khắc phục sự cố & Gỡ lỗi")
        trouble_layout = QVBoxLayout(trouble_box)
        trouble_layout.setSpacing(10)

        lbl_trouble_desc = QLabel(
            "Tự động dọn dẹp các tệp bộ nhớ đệm (cache), giải phóng dữ liệu tạm và khắc phục xung đột hệ thống.\n"
            "Toàn bộ các dự án, video và bản dịch của bạn được BẢO TOÀN NGUYÊN VẸN."
        )
        lbl_trouble_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px; line-height: 1.4;")
        lbl_trouble_desc.setWordWrap(True)
        trouble_layout.addWidget(lbl_trouble_desc)

        h_trouble = QHBoxLayout()
        btn_repair = QPushButton("  Gỡ lỗi & Dọn dẹp cache")
        btn_repair.setIcon(get_icon("refresh", "#f59e0b", "#f59e0b", 14))
        btn_repair.setFixedHeight(30)
        btn_repair.clicked.connect(self._on_repair_clicked)
        h_trouble.addWidget(btn_repair)

        btn_export_diag = QPushButton("  Xuất nhật ký chẩn đoán (.zip)")
        btn_export_diag.setIcon(get_icon("folder", "#a78bfa", "#a78bfa", 14))
        btn_export_diag.setFixedHeight(30)
        btn_export_diag.clicked.connect(self._on_export_diagnostics)
        h_trouble.addWidget(btn_export_diag)

        btn_clear_logs = QPushButton("  Xóa sạch nhật ký (Logs)")
        btn_clear_logs.setIcon(get_icon("trash", "#ef4444", "#ef4444", 14))
        btn_clear_logs.setFixedHeight(30)
        btn_clear_logs.clicked.connect(self._on_clear_logs)
        h_trouble.addWidget(btn_clear_logs)

        btn_reinstall = QPushButton("  Tải lại bản mới từ GitHub")
        btn_reinstall.setIcon(get_icon("download", "#38bdf8", "#38bdf8", 14))
        btn_reinstall.setFixedHeight(30)
        btn_reinstall.clicked.connect(self._on_reinstall_from_github)
        h_trouble.addWidget(btn_reinstall)
        h_trouble.addStretch(1)

        trouble_layout.addLayout(h_trouble)
        layout.addWidget(trouble_box)

        # Initial GPU & AI models status refresh
        self._refresh_all_status()

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_save = QPushButton(" Lưu cài đặt")
        btn_save.setIcon(get_icon("check", "#ffffff", "#ffffff", 14))
        btn_save.setObjectName("primary")
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(self._save_settings)
        btn_row.addWidget(btn_save)

        btn_tutorial = QPushButton(" Xem lại hướng dẫn ban đầu (Tutorial)")
        btn_tutorial.setIcon(get_icon("info", "#38bdf8", "#38bdf8", 14))
        btn_tutorial.setObjectName("secondary")
        btn_tutorial.setFixedHeight(34)
        btn_tutorial.clicked.connect(self._show_tutorial)
        btn_row.addWidget(btn_tutorial)
        btn_row.addStretch(1)

        layout.addLayout(btn_row)

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet(f"color: {COLORS['accent']}; font-size: 11.5px; margin-top: 4px;")
        layout.addWidget(self._lbl_status)

        layout.addStretch(1)

        scroll_area.setWidget(container)
        root_layout.addWidget(scroll_area)

    def _play_voice_preview(self, voice_name: str):
        """Play short voice preview sample with zero delay."""
        from pathlib import Path
        try:
            self._lbl_status.setText(f"Đang phát mẫu giọng: {voice_name}...")
            local_wav = Path("out/voice_previews") / f"{voice_name}.wav"
            if local_wav.exists():
                self._preview_player.setSource(QUrl.fromLocalFile(str(local_wav.resolve())))
                self._preview_player.play()
                self._lbl_status.setText(f"Đang nghe mẫu giọng: {voice_name}")
                return

            url = f"{get_api_base_url()}/api/voices/preview?voice={voice_name}"
            self._preview_player.setSource(QUrl(url))
            self._preview_player.play()
        except Exception as e:
            self._lbl_status.setText(f"Lỗi nghe thử: {e}")

    def _on_provider_changed(self, idx: int):
        # idx 0: Gemini Web, idx 1: Manual Translate
        is_cdp = (idx == 0)
        self._manual_container.setVisible(not is_cdp)
        self._gemini_web_container.setVisible(is_cdp)
        if is_cdp:
            self._update_cdp_status_async()

    def _update_cdp_status_async(self):
        # Prevent spawning duplicate check threads if one is already running
        if hasattr(self, "_cdp_check_worker") and self._cdp_check_worker and self._cdp_check_worker.isRunning():
            return
        from ui.workers import CheckCDPWorker
        self._lbl_cdp_status.setText("Trạng thái: Đang kiểm tra cổng 9222...")
        self._lbl_cdp_status.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        w = CheckCDPWorker()
        def _on_status(ready: bool):
            if ready:
                self._lbl_cdp_status.setText("Trạng thái: Đã kết nối sẵn sàng (Cổng 9222)")
                self._lbl_cdp_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px;")
            else:
                self._lbl_cdp_status.setText("Trạng thái: Chưa kết nối (Cổng 9222 đang đóng)")
                self._lbl_cdp_status.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        w.status_checked.connect(_on_status)
        self._cdp_check_worker = w
        self._workers.append(w)
        w.start()

    def _open_gemini_browser(self):
        if hasattr(self, "_launch_gemini_worker") and self._launch_gemini_worker and self._launch_gemini_worker.isRunning():
            return
        from ui.workers import LaunchBrowserCDPWorker
        self._lbl_cdp_status.setText("Đang khởi động cửa sổ Gemini...")
        self._lbl_cdp_status.setStyleSheet("color: #38bdf8; font-size: 11px;")
        w = LaunchBrowserCDPWorker()
        def _on_done(ok: bool):
            if ok:
                self._lbl_cdp_status.setText("Trạng thái: Đã kết nối sẵn sàng (Cửa sổ Gemini)")
                self._lbl_cdp_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px;")
                QMessageBox.information(
                    self,
                    "Thành công",
                    "Đã mở cửa sổ Gemini thành công!\n\n"
                    "👉 Cửa sổ trình duyệt đang hiển thị trang Gemini. "
                    "Bạn có thể đăng nhập tài khoản Google (chỉ cần đăng nhập 1 lần duy nhất) hoặc trò chuyện trực tiếp không cần đăng nhập!"
                )
            else:
                self._lbl_cdp_status.setText("Trạng thái: Chưa thể kích hoạt cửa sổ Gemini")
                self._lbl_cdp_status.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
                QMessageBox.warning(self, "Lỗi", "Trình duyệt chưa kịp kết nối hoặc bị đóng. Vui lòng thử lại.")
        def _on_err(err: str):
            self._lbl_cdp_status.setText(f"Lỗi: {err}")
            QMessageBox.critical(self, "Lỗi mở cửa sổ Gemini", err)
        w.finished.connect(_on_done)
        w.error.connect(_on_err)
        self._launch_gemini_worker = w
        self._workers.append(w)
        w.start()

    def _check_gemini_browser(self):
        if hasattr(self, "_check_worker") and self._check_worker and self._check_worker.isRunning():
            return
        from ui.workers import CheckCDPWorker
        self._lbl_cdp_status.setText("Đang kiểm tra kết nối...")
        self._lbl_cdp_status.setStyleSheet("color: #38bdf8; font-size: 11px;")
        w = CheckCDPWorker()
        def _on_res(ready: bool):
            if ready:
                self._lbl_cdp_status.setText("Trạng thái: Đã kết nối sẵn sàng (Cổng 9222)")
                self._lbl_cdp_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px;")
                QMessageBox.information(self, "Kết nối tốt", "Cửa sổ Gemini đang mở cổng 9222 và sẵn sàng dịch thuật!")
            else:
                self._lbl_cdp_status.setText("Trạng thái: Chưa kết nối (Cổng 9222 đang đóng)")
                self._lbl_cdp_status.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
                QMessageBox.warning(self, "Chưa kết nối", "Chưa phát hiện cửa sổ Gemini mở cổng 9222. Vui lòng nhấn nút 'Mở Mini Client Gemini' trước.")
        w.status_checked.connect(_on_res)
        self._check_worker = w
        self._workers.append(w)
        w.start()

    def load_settings(self):
        w = LoadSettingsWorker()

        def _on_done(data: dict):
            provider = data.get("translation_provider", "gemini_web")
            self._combo_provider.blockSignals(True)
            if provider == "manual":
                self._combo_provider.setCurrentIndex(1)
            else:
                self._combo_provider.setCurrentIndex(0)
            self._combo_provider.blockSignals(False)
            self._on_provider_changed(self._combo_provider.currentIndex())

            male = data.get("default_male_voice")
            if male and self._combo_male.findText(male) >= 0:
                self._combo_male.setCurrentText(male)

            female = data.get("default_female_voice")
            if female and self._combo_female.findText(female) >= 0:
                self._combo_female.setCurrentText(female)

            whisper_m = data.get("whisper_model", "large-v3")
            idx_m = self._combo_asr_model.findData(whisper_m)
            if idx_m >= 0:
                self._combo_asr_model.setCurrentIndex(idx_m)

            sep_m = data.get("separation_model", "Kim_Vocal_2.onnx")
            idx_sep = self._combo_sep_model.findData(sep_m)
            if idx_sep >= 0:
                self._combo_sep_model.setCurrentIndex(idx_sep)

        self._load_worker = w
        self._workers.append(w)
        w.finished.connect(_on_done)
        w.error.connect(lambda _: None)
        w.start()

    def _show_tutorial(self):
        from ui.dialogs.welcome_tutorial_dialog import WelcomeTutorialDialog
        dlg = WelcomeTutorialDialog(self)
        if dlg.exec():
            self.load_settings()

    def _save_settings(self):
        selected_provider = "gemini_web" if self._combo_provider.currentIndex() == 0 else "manual"
        selected_asr = self._combo_asr_model.currentData() or "large-v3"
        selected_sep = self._combo_sep_model.currentData() or "Kim_Vocal_2.onnx"
        payload: dict = {
            "translation_provider": selected_provider,
            "translation_model": "gemini_web" if selected_provider == "gemini_web" else "manual",
            "auto_fallback": False,
            "default_male_voice": self._combo_male.currentText(),
            "default_female_voice": self._combo_female.currentText(),
            "whisper_model": selected_asr,
            "separation_model": selected_sep,
        }

        w = SaveSettingsWorker(payload)

        def _on_saved(res):
            self._lbl_status.setText("Đã lưu cài đặt dịch thuật thành công!")
            QMessageBox.information(self, "Đã lưu", "Cài đặt dịch thuật đã được lưu thành công!")
            self.load_settings()

        def _on_err(err):
            QMessageBox.critical(self, "Lỗi lưu cài đặt", err)

        self._save_worker = w
        self._workers.append(w)
        w.finished.connect(_on_saved)
        w.error.connect(_on_err)
        w.start()

    def _refresh_gpu_status(self):
        """Inspect GPU / Driver status and update UI display."""
        from dubstudio.gpu_check import GPUStatus, inspect_gpu_and_driver
        info = inspect_gpu_and_driver()
        status = info["status"]
        card = info.get("card_name", "N/A")
        vram = info.get("vram_gb", 0.0)
        driver = info.get("driver_version", "N/A")
        rec_mode = info.get("recommended_mode", "cpu").upper()

        if status == GPUStatus.OK_CUDA:
            color = "#34d399"
            status_text = "Hoạt động tối ưu (Hỗ trợ tăng tốc GPU CUDA)"
        elif status == GPUStatus.VRAM_LOW:
            color = "#fbbf24"
            status_text = f"Cảnh báo: VRAM thấp ({vram:.1f} GB), khuyến nghị chạy CPU"
        elif status == GPUStatus.DRIVER_OUTDATED_OR_MISSING:
            color = "#f87171"
            status_text = f"Cần cập nhật Driver (hiện tại: {driver}, tối thiểu: {info.get('min_driver_required')})"
        else:
            color = "#9ca3af"
            status_text = "Không có card NVIDIA, chế độ CPU"

        html = (
            f"• <b>Card đồ họa:</b> {card}<br>"
            f"• <b>Dung lượng VRAM:</b> {vram:.1f} GB | <b>Phiên bản Driver:</b> {driver}<br>"
            f"• <b>Chế độ thực thi:</b> <span style='color:{color}; font-weight:600;'>{rec_mode}</span> ({status_text})"
        )
        self._lbl_gpu_info.setText(html)

    def _on_repair_clicked(self):
        """Clean all temporary caches, LLM hash caches, and rebuild runtime hooks safely."""
        reply = QMessageBox.question(
            self,
            "Xác nhận gỡ lỗi & Dọn dẹp cache",
            "Tiến trình này sẽ xóa toàn bộ bộ nhớ đệm tạm thời (cache LLM, cache Python, tệp rác hệ thống) để giải quyết các xung đột phát sinh.\n\n"
            "TOÀN BỘ DỰ ÁN VÀ VIDEO CỦA BẠN ĐƯỢC BẢO TOÀN NGUYÊN VẸN.\n\n"
            "Bạn có muốn tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from dubstudio.updater import repair_and_clean_cache
            res = repair_and_clean_cache()
            mb = res.get("freed_mb", 0.0)
            items = "\n• ".join(res.get("cleaned_items", []))
            QMessageBox.information(
                self,
                "Hoàn tất gỡ lỗi",
                f"Đã giải phóng thành công {mb:.2f} MB dữ liệu tạm thời!\n\nCác hạng mục đã làm sạch:\n• {items}\n\n"
                "Xung đột bộ nhớ đệm đã được giải quyết.",
            )

    def _on_reinstall_from_github(self):
        """Open latest GitHub release page for re-downloading Setup / updates."""
        from dubstudio.updater import GITHUB_REPO
        QDesktopServices.openUrl(QUrl(f"https://github.com/{GITHUB_REPO}/releases"))

    def _on_export_diagnostics(self):
        """Export all logs, environment stats and selftest report into a zip bundle."""
        from dubstudio.diagnostics import export_diagnostic_zip
        try:
            zip_file = export_diagnostic_zip()
            reply = QMessageBox.information(
                self,
                "Xuất nhật ký chẩn đoán thành công",
                f"Đã xuất tệp nén chẩn đoán hệ thống:\n\n{zip_file.resolve()}\n\n"
                "Tệp này chứa toàn bộ nhật ký lỗi (đã tự động che dấu thông tin nhạy cảm/API key) "
                "để bạn có thể gửi cho bộ phận hỗ trợ kỹ thuật hoặc kiểm tra lại.\n\n"
                "Bạn có muốn mở thư mục chứa tệp này ngay không?",
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Close,
            )
            if reply == QMessageBox.StandardButton.Open:
                try:
                    import os
                    os.startfile(str(zip_file.parent.resolve()))
                except Exception:
                    pass
        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất chẩn đoán", f"Không thể xuất tệp chẩn đoán: {e}")

    def _on_clear_logs(self):
        """Clear all application and stage logs immediately."""
        from dubstudio.logging_setup import clear_all_logs
        freed = clear_all_logs()
        mb = freed / (1024 * 1024)
        QMessageBox.information(
            self,
            "Đã dọn dẹp nhật ký",
            f"Đã xóa sạch toàn bộ các tệp nhật ký ghi đệm (Logs)!\nĐã giải phóng: {mb:.2f} MB dung lượng ổ đĩa.",
        )

    def _refresh_all_status(self):
        """Refresh both GPU status and all AI component package rows."""
        self._refresh_gpu_status()
        self._refresh_components_ui()

    def _refresh_components_ui(self):
        """Build or refresh UI cards for all AI models and packages from components.json."""
        import json
        from dubstudio.paths import get_resource_dir, get_app_dir
        from dubstudio.components import is_component_ready

        if not hasattr(self, "_active_downloading_pkgs"):
            self._active_downloading_pkgs = set()

        # If cards already exist, perform an in-place update to preserve C++ objects and active downloads!
        if hasattr(self, "_pkg_ui_map") and self._pkg_ui_map and self._comp_rows_layout.count() > 0:
            for pkg_id, entry in self._pkg_ui_map.items():
                if pkg_id in self._active_downloading_pkgs:
                    continue  # Keep downloading progress bar and cancel button untouched!
                ready, status_text = is_component_ready(pkg_id)
                try:
                    badge = entry.get("badge")
                    btn = entry.get("btn")
                    if badge:
                        if ready:
                            badge.setText("🟢 Đã sẵn sàng")
                            badge.setStyleSheet("color: #34d399; font-weight: 600; font-size: 11.5px;")
                        else:
                            badge.setText("🟡 Chưa tải")
                            badge.setStyleSheet("color: #fbbf24; font-weight: 600; font-size: 11.5px;")
                    if btn:
                        btn.setText(" Tải lại" if ready else " Tải gói này")
                        btn.setObjectName("secondary" if ready else "primary")
                        btn.style().unpolish(btn)
                        btn.style().polish(btn)
                except (RuntimeError, AttributeError):
                    pass
            return

        # Clear existing row widgets only when initial creation or empty
        while self._comp_rows_layout.count():
            item = self._comp_rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        from dubstudio.paths import get_resource_dir, get_app_dir
        candidates = [
            get_app_dir() / "config" / "components.json",
            get_resource_dir() / "config" / "components.json",
            Path("config/components.json"),
        ]
        manifest_file = next((c for c in candidates if c.exists()), None)

        packages = []
        if manifest_file:
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
                packages = data.get("packages", [])
            except Exception:
                pass

        if not hasattr(self, "_pkg_ui_map"):
            self._pkg_ui_map = {}
        self._pkg_ui_map.clear()

        if not packages:
            lbl_empty = QLabel("Không thể nạp danh mục gói thành phần.")
            lbl_empty.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
            self._comp_rows_layout.addWidget(lbl_empty)
            return

        for pkg in packages:
            pkg_id = pkg.get("id")
            name = pkg.get("name", pkg_id)
            size_disp = pkg.get("size_display", f"{round(pkg.get('size_bytes', 0) / (1024 * 1024), 1)} MB")
            desc = pkg.get("changelog_vi", "")
            ready, status_text = is_component_ready(pkg_id)

            card = QFrame()
            card.setStyleSheet(
                f"background-color: {COLORS['surface_raised']}; border: 1px solid {COLORS['border']}; "
                f"border-radius: 8px; padding: 10px;"
            )
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(12, 10, 12, 10)
            c_layout.setSpacing(6)

            top_row = QHBoxLayout()
            lbl_title = QLabel(f"<b>{name}</b>  <span style='color:{COLORS['text_muted']}; font-size:11px;'>({size_disp})</span>")
            lbl_title.setStyleSheet("font-size: 13px; color: #f8fafc;")
            top_row.addWidget(lbl_title, 1)

            status_badge = QLabel()
            if ready:
                status_badge.setText("🟢 Đã sẵn sàng")
                status_badge.setStyleSheet("color: #34d399; font-weight: 600; font-size: 11.5px;")
            else:
                status_badge.setText("🟡 Chưa tải")
                status_badge.setStyleSheet("color: #fbbf24; font-weight: 600; font-size: 11.5px;")
            top_row.addWidget(status_badge)

            btn_action = QPushButton(" Tải lại" if ready else " Tải gói này")
            btn_action.setIcon(get_icon("download", "#ffffff", "#ffffff", 12))
            btn_action.setFixedHeight(28)
            btn_action.setStyleSheet("padding: 0 12px; font-size: 11.5px;")
            if not ready:
                btn_action.setObjectName("primary")
            else:
                btn_action.setObjectName("secondary")

            btn_cancel = QPushButton(" Hủy")
            btn_cancel.setIcon(get_icon("x", "#f87171", "#f87171", 12))
            btn_cancel.setFixedHeight(28)
            btn_cancel.setStyleSheet("padding: 0 10px; font-size: 11.5px; background-color: #3b181e; color: #fca5a5; border: 1px solid #7f1d1d; border-radius: 6px;")
            btn_cancel.setVisible(False)

            top_row.addWidget(btn_action)
            top_row.addWidget(btn_cancel)
            c_layout.addLayout(top_row)

            if desc:
                lbl_desc = QLabel(desc)
                lbl_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
                lbl_desc.setWordWrap(True)
                c_layout.addWidget(lbl_desc)

            pbar = QProgressBar()
            pbar.setFixedHeight(8)
            pbar.setRange(0, 100)
            pbar.setValue(0)
            pbar.setTextVisible(False)
            pbar.setVisible(False)
            pbar.setStyleSheet(
                "QProgressBar { background-color: #1e293b; border-radius: 4px; border: 1px solid #334155; } "
                "QProgressBar::chunk { background-color: #38bdf8; border-radius: 3px; }"
            )
            c_layout.addWidget(pbar)

            self._pkg_ui_map[pkg_id] = {
                "pkg": pkg,
                "btn": btn_action,
                "btn_cancel": btn_cancel,
                "pbar": pbar,
                "badge": status_badge,
            }

            btn_action.clicked.connect(lambda _, p=pkg, b=btn_action, bc=btn_cancel, pb=pbar, sb=status_badge: self._download_component(p, b, bc, pb, sb))
            self._comp_rows_layout.addWidget(card)

    def _update_app_status(self, msg: str):
        """Forward real-time status message to the MainWindow bottom status bar."""
        try:
            win = self.window()
            if hasattr(win, "status_bar") and win.status_bar:
                win.status_bar.showMessage(msg)
        except Exception:
            pass

    def _trigger_download_by_pkg_id(self, pkg_id: str):
        """Programmatically trigger download for a component by pkg_id with full UI synchronization."""
        entry = getattr(self, "_pkg_ui_map", {}).get(pkg_id)
        if entry:
            self._download_component(
                entry["pkg"],
                entry["btn"],
                entry["btn_cancel"],
                entry["pbar"],
                entry["badge"]
            )

    def _on_asr_model_user_selected(self, idx: int):
        """Prompt and offer instant download when user interactively selects a model that is not yet ready."""
        val = self._combo_asr_model.currentData()
        pkg_id = "sensevoice_small" if "sensevoice" in str(val).lower() else "whisper_large_v3"
        pkg_name = "SenseVoice-Small" if pkg_id == "sensevoice_small" else "faster-whisper large-v3"
        from dubstudio.components import is_component_ready
        ready, _ = is_component_ready(pkg_id)
        if not ready:
            reply = QMessageBox.question(
                self,
                "Chưa tải mô hình",
                f"Mô hình nhận diện giọng nói '{pkg_name}' bạn vừa chọn chưa được tải về máy.\n\n"
                f"Bạn có muốn tải gói này ngay bây giờ không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._trigger_download_by_pkg_id(pkg_id)

    def _on_sep_model_user_selected(self, idx: int):
        """Prompt and offer instant download when user interactively selects a separation model that is not yet ready."""
        val = self._combo_sep_model.currentData()
        pkg_id = "bs_roformer" if "roformer" in str(val).lower() else "kim_vocal_2"
        pkg_name = "BS-RoFormer EP 317" if pkg_id == "bs_roformer" else "Kim Vocal 2"
        from dubstudio.components import is_component_ready
        ready, _ = is_component_ready(pkg_id)
        if not ready:
            reply = QMessageBox.question(
                self,
                "Chưa tải mô hình",
                f"Mô hình tách nhạc '{pkg_name}' bạn vừa chọn chưa được tải về máy.\n\n"
                f"Bạn có muốn tải gói này ngay bây giờ không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._trigger_download_by_pkg_id(pkg_id)

    def _download_component(self, pkg: dict, btn: QPushButton, btn_cancel: QPushButton, pbar: QProgressBar, status_badge: QLabel):
        """Launch background worker to download and install a component package with progress and cancel support."""
        from ui.workers import DownloadComponentWorker

        if not hasattr(self, "_active_downloading_pkgs"):
            self._active_downloading_pkgs = set()

        pkg_id = pkg.get("id")
        self._active_downloading_pkgs.add(pkg_id)

        try:
            btn.setVisible(False)
            btn_cancel.setVisible(True)
            btn_cancel.setEnabled(True)
            btn_cancel.setText(" Hủy")

            pbar.setVisible(True)
            pbar.setValue(0)
            status_badge.setText("⏳ Đang chuẩn bị tải...")
            status_badge.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 11.5px;")
        except (RuntimeError, AttributeError):
            pass
        self._update_app_status(f"⏳ Đang chuẩn bị tải gói '{pkg.get('name')}'...")

        w = DownloadComponentWorker(pkg)

        try:
            btn_cancel.clicked.disconnect()
        except Exception:
            pass

        def _on_cancel():
            self._active_downloading_pkgs.discard(pkg_id)
            try:
                btn_cancel.setEnabled(False)
                btn_cancel.setText(" Đang hủy...")
                status_badge.setText("⏳ Đang hủy & dọn dẹp file tạm...")
            except (RuntimeError, AttributeError):
                pass
            self._update_app_status(f"⏳ Đang hủy tải gói '{pkg.get('name')}' và dọn dẹp file tạm...")
            w.cancel()
        btn_cancel.clicked.connect(_on_cancel)

        def _on_prog(pid, pct, down, tot):
            entry = getattr(self, "_pkg_ui_map", {}).get(pid)
            cur_pbar = entry.get("pbar") if entry else pbar
            cur_badge = entry.get("badge") if entry else status_badge

            mb_down = max(0.0, float(down) / (1024 * 1024))
            mb_tot = max(0.0, float(tot) / (1024 * 1024)) if tot and tot > 0 else 0.0
            pct_val = max(0, min(100, int(pct)))
            try:
                if cur_pbar:
                    cur_pbar.setValue(pct_val)
                if cur_badge:
                    if mb_tot > 0:
                        cur_badge.setText(f"⏳ {pct_val}% ({mb_down:.1f}/{mb_tot:.1f} MB)")
                    else:
                        cur_badge.setText(f"⏳ {pct_val}% ({mb_down:.1f} MB)")
            except (RuntimeError, AttributeError):
                pass
            self._update_app_status(f"⏳ Đang tải {pkg.get('name')}: {pct_val}% ({mb_down:.1f}/{mb_tot:.1f} MB)...")

        def _on_done(pid, ok, msg):
            self._active_downloading_pkgs.discard(pkg_id)
            entry = getattr(self, "_pkg_ui_map", {}).get(pid)
            cur_pbar = entry.get("pbar") if entry else pbar
            cur_badge = entry.get("badge") if entry else status_badge
            cur_btn = entry.get("btn") if entry else btn
            cur_cancel = entry.get("btn_cancel") if entry else btn_cancel

            from dubstudio.components import is_component_ready
            ready, _ = is_component_ready(pid)
            try:
                if cur_pbar:
                    cur_pbar.setVisible(False)
                if cur_cancel:
                    cur_cancel.setVisible(False)
                if cur_btn:
                    cur_btn.setVisible(True)
                    cur_btn.setEnabled(True)
                    cur_btn.setText(" Tải lại" if (ok or ready) else " Tải gói này")
                    cur_btn.setObjectName("secondary" if (ok or ready) else "primary")
                    cur_btn.style().unpolish(cur_btn)
                    cur_btn.style().polish(cur_btn)
                if cur_badge:
                    if ok or ready:
                        cur_badge.setText("🟢 Đã sẵn sàng")
                        cur_badge.setStyleSheet("color: #34d399; font-weight: 600; font-size: 11.5px;")
                    else:
                        cur_badge.setText("🟡 Chưa tải")
                        cur_badge.setStyleSheet("color: #fbbf24; font-weight: 600; font-size: 11.5px;")
            except (RuntimeError, AttributeError):
                pass

            if ok:
                self._update_app_status(f"● Đã tải và cài đặt thành công: {pkg.get('name')}.")
                QMessageBox.information(self, "Tải thành công", msg)
            elif ready:
                self._update_app_status(f"● Gói '{pkg.get('name')}' đã sẵn sàng.")
            else:
                self._update_app_status(f"● Đã dừng/hủy tải gói '{pkg.get('name')}'.")

        def _on_err(pid, err_msg):
            self._active_downloading_pkgs.discard(pkg_id)
            entry = getattr(self, "_pkg_ui_map", {}).get(pid)
            cur_pbar = entry.get("pbar") if entry else pbar
            cur_badge = entry.get("badge") if entry else status_badge
            cur_btn = entry.get("btn") if entry else btn
            cur_cancel = entry.get("btn_cancel") if entry else btn_cancel

            from dubstudio.components import is_component_ready
            ready, _ = is_component_ready(pid)
            try:
                if cur_pbar:
                    cur_pbar.setVisible(False)
                if cur_cancel:
                    cur_cancel.setVisible(False)
                if cur_btn:
                    cur_btn.setVisible(True)
                    cur_btn.setEnabled(True)
                    cur_btn.setText(" Tải lại" if ready else " Thử lại")
                    cur_btn.setObjectName("secondary" if ready else "primary")
                    cur_btn.style().unpolish(cur_btn)
                    cur_btn.style().polish(cur_btn)
                if cur_badge:
                    if ready:
                        cur_badge.setText("🟢 Đã sẵn sàng")
                        cur_badge.setStyleSheet("color: #34d399; font-weight: 600; font-size: 11.5px;")
                    else:
                        cur_badge.setText("❌ Lỗi tải")
                        cur_badge.setStyleSheet("color: #ef4444; font-weight: 600; font-size: 11.5px;")
            except (RuntimeError, AttributeError):
                pass

            self._update_app_status(f"❌ Lỗi tải {pkg.get('name')}: {err_msg}")
            QMessageBox.critical(self, "Lỗi tải gói", f"Không thể tải gói '{pkg.get('name')}':\n\n{err_msg}")

        w.progress.connect(_on_prog)
        w.finished.connect(_on_done)
        w.error.connect(_on_err)
        self._workers.append(w)
        w.start()



