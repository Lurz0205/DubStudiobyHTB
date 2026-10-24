"""Main application window with sleek Antigravity-inspired navigation and design."""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon, get_pixmap
from ui.pages.merge_page import MergePage
from ui.pages.projects_page import ProjectsPage
from ui.pages.settings_page import SettingsPage
from ui.pages.studio_page import StudioPage
from ui.pages.subtitle_export_page import SubtitleExportPage
from ui.theme import COLORS, STYLESHEET


class MainWindow(QMainWindow):
    """Main window with Antigravity-style sidebar and stacked pages."""

    PAGE_NAMES = [
        "Dự án",
        "Lồng tiếng",
        "Phụ đề",
        "Xuất video",
        "Cài đặt hệ thống",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DubStudio — Trình lồng tiếng & Chỉnh sửa Video AI")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumSize(960, 600)

        # Set application icon
        from pathlib import Path
        from PyQt6.QtGui import QIcon
        from dubstudio.paths import get_app_dir
        for ico in [get_app_dir() / "dubstudio.ico", get_app_dir() / "app.ico", Path("dubstudio.ico")]:
            if ico.exists():
                self.setWindowIcon(QIcon(str(ico.resolve())))
                break

        self._setup_ui()

        # Ensure window fits safely inside the current screen bounds without overflowing
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = max(960, min(1200, int(avail.width() * 0.88)))
            h = max(600, min(720, int(avail.height() * 0.86)))
            self.resize(w, h)
            self.move(
                avail.x() + max(0, (avail.width() - w) // 2),
                avail.y() + max(0, (avail.height() - h) // 2),
            )
        else:
            self.resize(1180, 700)

    def _setup_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ─── Sidebar (Antigravity Style) ───
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 8, 0, 12)
        side_layout.setSpacing(4)

        # Brand header with custom vector logo
        brand_box = QWidget()
        brand_box.setObjectName("sidebar_brand")
        brand_layout = QVBoxLayout(brand_box)
        brand_layout.setContentsMargins(14, 8, 14, 8)
        brand_layout.setSpacing(3)

        brand_top = QHBoxLayout()
        brand_top.setSpacing(8)
        lbl_logo_ic = QLabel()
        lbl_logo_ic.setPixmap(get_pixmap("brand", "#38bdf8", 18))
        brand_top.addWidget(lbl_logo_ic)

        lbl_logo = QLabel("DubStudio")
        lbl_logo.setObjectName("sidebar_logo_text")
        brand_top.addWidget(lbl_logo)
        brand_top.addStretch(1)
        brand_layout.addLayout(brand_top)

        lbl_sub = QLabel("AI Video Dubbing Studio")
        lbl_sub.setObjectName("sidebar_sub_text")
        brand_layout.addWidget(lbl_sub)

        side_layout.addWidget(brand_box)


        # Section Label
        lbl_sec = QLabel("ĐIỀU HƯỚNG")
        lbl_sec.setObjectName("sidebar_section_title")
        side_layout.addWidget(lbl_sec)

        # Nav Buttons with custom vector icons
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        self._btn_projects = QPushButton("  Dự án")
        self._btn_projects.setIcon(get_icon("folder", "#9ca3af", "#818CF8", 17))
        self._btn_projects.setIconSize(QSize(17, 17))
        self._btn_projects.setProperty("class", "nav_item")
        self._btn_projects.setToolTip("Quản lý danh sách các dự án lồng tiếng")
        self._btn_projects.setCheckable(True)
        self._btn_projects.setChecked(True)
        self._btn_projects.setProperty("active", "true")
        self._btn_group.addButton(self._btn_projects, 0)
        side_layout.addWidget(self._btn_projects)

        self._btn_studio = QPushButton("  Lồng tiếng")
        self._btn_studio.setIcon(get_icon("mic", "#9ca3af", "#818CF8", 17))
        self._btn_studio.setIconSize(QSize(17, 17))
        self._btn_studio.setProperty("class", "nav_item")
        self._btn_studio.setToolTip("Xem trước video, chỉnh sửa câu thoại, timeline và tạo lồng tiếng")
        self._btn_studio.setCheckable(True)
        self._btn_group.addButton(self._btn_studio, 1)
        side_layout.addWidget(self._btn_studio)

        self._btn_export = QPushButton("  Phụ đề")
        self._btn_export.setIcon(get_icon("subtitles", "#9ca3af", "#818CF8", 17))
        self._btn_export.setIconSize(QSize(17, 17))
        self._btn_export.setProperty("class", "nav_item")
        self._btn_export.setToolTip("Tùy biến phong cách và cách khắc phụ đề vào video")
        self._btn_export.setCheckable(True)
        self._btn_group.addButton(self._btn_export, 2)
        side_layout.addWidget(self._btn_export)

        self._btn_merge = QPushButton("  Chỉnh sửa video")
        self._btn_merge.setIcon(get_icon("scissors", "#9ca3af", "#818CF8", 17))
        self._btn_merge.setIconSize(QSize(17, 17))
        self._btn_merge.setProperty("class", "nav_item")
        self._btn_merge.setToolTip("Cắt xén (Crop), đổi tỉ lệ 9:16 Shorts/TikTok, che logo, chèn watermark và xuất video")
        self._btn_merge.setCheckable(True)
        self._btn_group.addButton(self._btn_merge, 3)
        side_layout.addWidget(self._btn_merge)

        side_layout.addStretch(1)

        # Subtle divider before system section
        sys_sep = QFrame()
        sys_sep.setFrameShape(QFrame.Shape.HLine)
        sys_sep.setStyleSheet(f"background-color: {COLORS['border']}; max-height: 1px; margin: 4px 10px;")
        side_layout.addWidget(sys_sep)

        # Section Label Bottom
        lbl_sec_bottom = QLabel("HỆ THỐNG")
        lbl_sec_bottom.setObjectName("sidebar_section_title")
        side_layout.addWidget(lbl_sec_bottom)

        self._btn_check_updates = QPushButton("  Kiểm tra cập nhật")
        self._btn_check_updates.setIcon(get_icon("download", "#9ca3af", "#818CF8", 16))
        self._btn_check_updates.setIconSize(QSize(16, 16))
        self._btn_check_updates.setProperty("class", "nav_item")
        self._btn_check_updates.setToolTip("Kiểm tra bản cập nhật mới trên GitHub và các gói dữ liệu AI")
        self._btn_check_updates.clicked.connect(self._on_check_updates_clicked)
        side_layout.addWidget(self._btn_check_updates)

        self._btn_tutorial = QPushButton("  Hướng dẫn")
        self._btn_tutorial.setIcon(get_icon("info", "#9ca3af", "#818CF8", 16))
        self._btn_tutorial.setIconSize(QSize(16, 16))
        self._btn_tutorial.setProperty("class", "nav_item")
        self._btn_tutorial.setToolTip("Xem lại bảng so sánh mô hình Whisper và hướng dẫn quy trình sử dụng")
        self._btn_tutorial.clicked.connect(self._on_tutorial_clicked)
        side_layout.addWidget(self._btn_tutorial)

        self._btn_settings = QPushButton("  Cài đặt")
        self._btn_settings.setIcon(get_icon("settings", "#9ca3af", "#818CF8", 17))
        self._btn_settings.setIconSize(QSize(17, 17))
        self._btn_settings.setProperty("class", "nav_item")
        self._btn_settings.setToolTip("Cài đặt API key, giọng đọc mặc định")
        self._btn_settings.setCheckable(True)
        self._btn_group.addButton(self._btn_settings, 4)
        side_layout.addWidget(self._btn_settings)

        self._btn_group.idClicked.connect(self._on_nav_clicked)

        root_layout.addWidget(sidebar)

        # ─── Content Area (Stacked Pages) ───
        content_box = QWidget()
        content_layout = QVBoxLayout(content_box)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top Header Bar (Antigravity Clean Breadcrumb + Badges)
        header = QFrame()
        header.setObjectName("header")
        head_layout = QHBoxLayout(header)
        head_layout.setContentsMargins(18, 0, 18, 0)
        head_layout.setSpacing(12)

        self._lbl_breadcrumb = QLabel()
        self._lbl_breadcrumb.setText(
            f"<span style='color:{COLORS['text_muted']}; font-weight:500;'>DubStudio</span>  "
            f"<span style='color:{COLORS['border_light']};'>/</span>  "
            f"<span style='color:{COLORS['text']}; font-weight:600;'>Dự án</span>"
        )
        head_layout.addWidget(self._lbl_breadcrumb)

        head_layout.addStretch(1)


        content_layout.addWidget(header)

        # Stacked Pages
        self._pages = QStackedWidget()
        self._projects_page = ProjectsPage()
        self._studio_page = StudioPage()
        self._export_page = SubtitleExportPage()
        self._merge_page = MergePage()
        self._settings_page = SettingsPage()

        # Connect Navigation & Workflow Transitions
        self._projects_page.open_studio_requested.connect(self._open_studio_for_job)
        self._projects_page.job_delete_requested.connect(self._studio_page.unload_job)
        self._projects_page.job_delete_requested.connect(lambda _: self._export_page._video_player.unload())
        self._studio_page.goto_export_requested.connect(self._open_export_for_job)
        self._export_page.goto_merge_requested.connect(self._open_merge_for_video)

        self._pages.addWidget(self._projects_page)    # 0
        self._pages.addWidget(self._studio_page)      # 1
        self._pages.addWidget(self._export_page)      # 2
        self._pages.addWidget(self._merge_page)       # 3
        self._pages.addWidget(self._settings_page)    # 4

        content_layout.addWidget(self._pages, 1)
        root_layout.addWidget(content_box, 1)

        self.setCentralWidget(root)

        # Status Bar (Clean & Minimal)
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("● Sẵn sàng làm việc.")
        self.setStatusBar(self.status_bar)

        from dubstudio.version import APP_VERSION
        from dubstudio.packaging import is_packaged
        ver_text = f"v{APP_VERSION} (Đóng gói)" if is_packaged() else f"v{APP_VERSION} (Dev)"
        self._lbl_version = QLabel(f" {ver_text} ")
        self._lbl_version.setStyleSheet("color: #888888; font-weight: bold; font-size: 11px; padding-right: 8px;")
        self.status_bar.addPermanentWidget(self._lbl_version)

        # Pre-warm TTS worker in background so TTS generation and single-sentence preview is instant
        try:
            from ui.workers import WarmTTSWorker
            self._warm_tts_worker = WarmTTSWorker()
            self._warm_tts_worker.start()
        except Exception:
            pass

        # Auto-check updates and verify components on startup
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, self._start_startup_update_check)

        # Zero-Leftover Garbage Collector: clean update artifacts and temp files 3s after startup
        QTimer.singleShot(3000, self._run_background_cleanup)

    def _run_background_cleanup(self):
        """Asynchronously clean stale update artifacts and temp files without freezing GUI."""
        import threading
        try:
            from dubstudio.updater import cleanup_update_artifacts
            threading.Thread(target=cleanup_update_artifacts, daemon=True).start()
        except Exception:
            pass

    def _on_cta_create_project(self):
        """Action when clicking '+ Tạo dự án mới' on sidebar."""
        self._on_nav_clicked(0)
        self._btn_projects.setChecked(True)
        self._projects_page._create_project()

    def _open_studio_for_job(self, job_id: str):
        """Open Studio Page and load specific job."""
        self._studio_page.load_job_by_id(job_id)
        self._btn_studio.setChecked(True)
        self._on_nav_clicked(1)

    def _open_export_for_job(self, job_id: str):
        """Open Subtitle & Export Page and load specific job."""
        if hasattr(self, "_studio_page") and hasattr(self._studio_page, "_video_player"):
            try:
                self._studio_page._video_player.pause()
            except Exception:
                pass
        self._btn_export.setChecked(True)
        self._pages.setCurrentIndex(2)
        self._update_nav_ui(2)
        if hasattr(self, "_export_page"):
            self._export_page.set_active_job(job_id)

    def _open_merge_for_video(self, video_path: str, job_id: str = ""):
        """Open Final Video Export (Merge) page and load specific video and job."""
        if hasattr(self, "_export_page") and hasattr(self._export_page, "_video_player"):
            try:
                self._export_page._video_player.pause()
            except Exception:
                pass
        if hasattr(self, "_merge_page") and hasattr(self._merge_page, "_trim_player"):
            try:
                self._merge_page._trim_player.pause()
            except Exception:
                pass
        if hasattr(self, "_merge_page") and video_path:
            self._merge_page.load_video_path(video_path, job_id=job_id)
        self._btn_merge.setChecked(True)
        self._on_nav_clicked(3)

    def _update_nav_ui(self, page_id: int):
        if 0 <= page_id < len(self.PAGE_NAMES):
            page_name = self.PAGE_NAMES[page_id]
            self._lbl_breadcrumb.setText(
                f"<span style='color:{COLORS['text_muted']}; font-weight:500;'>DubStudio</span>  "
                f"<span style='color:{COLORS['border_light']};'>/</span>  "
                f"<span style='color:{COLORS['text']}; font-weight:600;'>{page_name}</span>"
            )
        nav_buttons = [
            self._btn_projects,
            self._btn_studio,
            self._btn_export,
            self._btn_merge,
            self._btn_settings,
        ]
        for btn in nav_buttons:
            is_active = (btn == nav_buttons[page_id])
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_nav_clicked(self, page_id: int):
        if self._pages.currentIndex() == page_id:
            return
        # Pause video players when switching away
        if hasattr(self, "_studio_page") and hasattr(self._studio_page, "_video_player"):
            try:
                self._studio_page._video_player.pause()
            except Exception:
                pass
        if hasattr(self, "_export_page") and hasattr(self._export_page, "_video_player"):
            try:
                self._export_page._video_player.pause()
            except Exception:
                pass
        if hasattr(self, "_merge_page") and hasattr(self._merge_page, "_trim_player"):
            try:
                self._merge_page._trim_player.pause()
            except Exception:
                pass

        self._pages.setCurrentIndex(page_id)
        self._update_nav_ui(page_id)

        if page_id == 0 and hasattr(self, "_projects_page"):
            if not getattr(self._projects_page, "_jobs", None):
                self._projects_page.refresh_projects()
        elif page_id == 2 and hasattr(self, "_export_page"):
            if not getattr(self._export_page, "_jobs", None):
                self._export_page.refresh_jobs()

    def _get_active_models_status(self):
        """
        Check readiness of the specific models currently selected in Settings.
        Returns: (all_ready: bool, active_info: dict, missing_list: list)
        """
        import os
        from dubstudio.components import is_component_ready
        from dubstudio.config import AppConfig

        # Determine currently selected models with strict precedence
        from dubstudio.config import AppConfig
        try:
            cfg = AppConfig.load()
        except Exception:
            cfg = None

        asr_val = (
            (self._settings_page._combo_asr_model.currentData() if hasattr(self, "_settings_page") and hasattr(self._settings_page, "_combo_asr_model") else None)
            or os.getenv("WHISPER_MODEL")
            or os.getenv("ASR_MODEL")
            or (cfg.asr.model_size if cfg else None)
            or "sensevoice-small"
        )
        sep_val = (
            (self._settings_page._combo_sep_model.currentData() if hasattr(self, "_settings_page") and hasattr(self._settings_page, "_combo_sep_model") else None)
            or os.getenv("SEPARATION_MODEL")
            or (getattr(getattr(cfg, "separation", None), "model_name", "Kim_Vocal_2.onnx") if cfg else "Kim_Vocal_2.onnx")
        )

        # Map ASR
        if "sensevoice" in str(asr_val).lower():
            asr_pkg = "sensevoice_small"
            asr_name = "SenseVoice-Small"
        else:
            asr_pkg = "whisper_large_v3"
            asr_name = "faster-whisper large-v3"

        # Map Separation
        if "roformer" in str(sep_val).lower():
            sep_pkg = "bs_roformer"
            sep_name = "BS-RoFormer EP 317"
        else:
            sep_pkg = "kim_vocal_2"
            sep_name = "Kim Vocal 2"

        asr_ready, _ = is_component_ready(asr_pkg)
        sep_ready, _ = is_component_ready(sep_pkg)
        tts_ready, _ = is_component_ready("vieneu_tts_voices")
        torch_ready, _ = is_component_ready("torch_core")
        ffmpeg_ready, _ = is_component_ready("ffmpeg_binaries")

        missing = []
        if not asr_ready:
            missing.append(f"Mô hình nhận diện giọng nói: {asr_name}")
        if not sep_ready:
            missing.append(f"Mô hình tách nhạc nền: {sep_name}")
        if not tts_ready:
            missing.append("Mô hình giọng đọc thuyết minh: VieNeu-TTS v3")
        if not torch_ready:
            missing.append("Môi trường AI: PyTorch & CUDA Runtime")
        if not ffmpeg_ready:
            missing.append("Công cụ đa phương tiện: FFmpeg")

        info = {
            "asr_name": asr_name,
            "asr_pkg": asr_pkg,
            "asr_ready": asr_ready,
            "sep_name": sep_name,
            "sep_pkg": sep_pkg,
            "sep_ready": sep_ready,
            "tts_ready": tts_ready,
            "torch_ready": torch_ready,
            "ffmpeg_ready": ffmpeg_ready,
        }
        return (len(missing) == 0, info, missing)

    def _on_check_updates_clicked(self):
        """Check for GitHub release updates and AI models asynchronously without freezing the UI."""
        self.status_bar.showMessage("Đang kiểm tra cập nhật từ GitHub và trạng thái mô hình...")
        if hasattr(self, "_btn_check_updates"):
            self._btn_check_updates.setEnabled(False)

        from ui.workers import CheckUpdatesWorker
        self._check_worker = CheckUpdatesWorker()
        self._check_worker.finished.connect(self._on_check_updates_finished)
        self._check_worker.start()

    def _on_check_updates_finished(self, res: dict):
        """Handle results of update check with clear user dialogs and one-click actions."""
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        from dubstudio.updater import CURRENT_VERSION
        from dubstudio.packaging import is_packaged

        if hasattr(self, "_btn_check_updates"):
            self._btn_check_updates.setEnabled(True)
        self.status_bar.showMessage("● Sẵn sàng làm việc.")

        # Always refresh settings components view so badges are 100% up-to-date
        if hasattr(self, "_settings_page") and hasattr(self._settings_page, "_render_components_ui"):
            try:
                self._settings_page._render_components_ui()
            except Exception:
                pass

        # 1. Handle network or API error
        if not res.get("success", False) and res.get("network_error"):
            err_msg = res.get("network_error")
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Lỗi kiểm tra cập nhật")
            msg_box.setText(
                f"Không thể kết nối đến máy chủ cập nhật GitHub:\n{err_msg}\n\n"
                "Bạn có muốn mở trang GitHub Releases trên trình duyệt để kiểm tra trực tiếp không?"
            )
            btn_web = msg_box.addButton("Mở trang GitHub", QMessageBox.ButtonRole.AcceptRole)
            msg_box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()
            if msg_box.clickedButton() == btn_web:
                QDesktopServices.openUrl(QUrl(res.get("download_url") or "https://github.com/Lurz0205/DubStudiobyHTB/releases"))
            return

        has_app = res.get("has_app_update", False)
        latest = res.get("latest_version", CURRENT_VERSION)
        notes = (res.get("release_notes") or "").strip()
        download_url = res.get("download_url", "")
        setup_url = res.get("setup_asset_url", "")
        setup_size = res.get("setup_asset_size", 0)
        comp_updates = res.get("component_updates", [])

        # 2. Check App version update on GitHub
        if has_app:
            if not is_packaged():
                # Dev mode (start.bat) -> Developer is already on working source code
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setWindowTitle("Môi trường phát triển (Dev Mode)")
                notes_preview = f"\n\nĐiểm mới trong bản v{latest}:\n{notes}" if notes else ""
                msg_box.setText(
                    f"Bạn đang chạy trực tiếp từ mã nguồn phát triển (start.bat — v{CURRENT_VERSION}).\n\n"
                    f"Mã nguồn trên máy bạn là phiên bản làm việc cục bộ mới nhất.\n"
                    f"(Bản release đóng gói trên GitHub hiện là: v{latest}){notes_preview}"
                )
                btn_test_dl = msg_box.addButton("Tải thử nghiệm bản cài", QMessageBox.ButtonRole.ActionRole)
                btn_gh = msg_box.addButton("Xem trên GitHub", QMessageBox.ButtonRole.ActionRole)
                msg_box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
                msg_box.exec()

                if msg_box.clickedButton() == btn_test_dl:
                    self._start_app_update_flow(latest, download_url, setup_url, setup_size)
                elif msg_box.clickedButton() == btn_gh:
                    QDesktopServices.openUrl(QUrl(download_url or "https://github.com/Lurz0205/DubStudiobyHTB/releases"))
                return

            # Packaged user mode -> Offer 1-click automatic update with live progress
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowTitle("Đã có bản cập nhật mới!")
            notes_text = f"\n\nNội dung bản vá:\n{notes}" if notes else "\n\nBản cập nhật bao gồm các bản sửa lỗi và cải tiến hiệu năng mới nhất."
            msg_box.setText(
                f"🎉 Đã có phiên bản mới: v{latest} trên GitHub!\n"
                f"(Phiên bản bạn đang dùng: v{CURRENT_VERSION}){notes_text}\n\n"
                "Bạn có muốn tự động tải và cập nhật ngay bây giờ không?"
            )
            btn_update = msg_box.addButton("Cập nhật ngay (Tự động)", QMessageBox.ButtonRole.AcceptRole)
            btn_gh = msg_box.addButton("Xem trên GitHub", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton("Để sau", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()

            if msg_box.clickedButton() == btn_update:
                self._start_app_update_flow(latest, download_url, setup_url, setup_size)
            elif msg_box.clickedButton() == btn_gh:
                QDesktopServices.openUrl(QUrl(download_url or "https://github.com/Lurz0205/DubStudiobyHTB/releases"))
            return

        # 3. Check modular component updates
        if comp_updates:
            from ui.dialogs.component_update_dialog import ComponentUpdateDialog
            up_dlg = ComponentUpdateDialog(comp_updates[0], parent=self)
            dlg_res = up_dlg.exec()
            if dlg_res == 1 or getattr(up_dlg, "user_agreed", False):
                self._btn_settings.setChecked(True)
                self._on_nav_clicked(4)
                pkg = comp_updates[0].get("package", {})
                pkg_id = pkg.get("id")
                if pkg_id and hasattr(self, "_settings_page"):
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(250, lambda pid=pkg_id: self._settings_page._trigger_download_by_pkg_id(pid))
            return

        # 4. Check readiness of active models selected in Settings
        all_ready, info, missing = self._get_active_models_status()
        if not all_ready:
            msg = (
                f"Hệ thống phát hiện mô hình bạn đang chọn để làm việc trong Cài đặt CHƯA ĐƯỢC TẢI:\n\n"
                + "\n".join(f"  • {m}" for m in missing)
                + "\n\nBạn có muốn chuyển sang mục 'Cài đặt' và tự động tải ngay bây giờ không?"
            )
            reply = QMessageBox.warning(
                self,
                "Chưa tải mô hình làm việc",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._btn_settings.setChecked(True)
                self._on_nav_clicked(4)
                target_pkg = info.get("asr_pkg") if not info.get("asr_ready") else info.get("sep_pkg")
                if target_pkg and hasattr(self, "_settings_page"):
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(250, lambda pid=target_pkg: self._settings_page._trigger_download_by_pkg_id(pid))
            return

        # 5. Everything is up to date and all selected models are ready
        asr_info = f"{info['asr_name']} (Đã sẵn sàng)"
        sep_info = f"{info['sep_name']} (Đã sẵn sàng)"
        tts_info = "VieNeu-TTS v3 (Đã sẵn sàng)"
        torch_info = "PyTorch & CUDA Runtime (Đã sẵn sàng)"
        ffmpeg_info = "FFmpeg NVENC/CPU (Đã sẵn sàng)"
        QMessageBox.information(
            self,
            "Kiểm tra cập nhật",
            f"✓ Bạn đang sử dụng phiên bản mới nhất (v{CURRENT_VERSION})!\n\n"
            f"Trạng thái mô hình & thư viện AI đang sử dụng:\n"
            f"  • Nhận diện giọng nói: {asr_info}\n"
            f"  • Tách nhạc nền & thoại: {sep_info}\n"
            f"  • Giọng đọc thuyết minh: {tts_info}\n"
            f"  • Nền tảng AI: {torch_info}\n"
            f"  • Công cụ kết xuất: {ffmpeg_info}\n\n"
            f"Toàn bộ tài nguyên đã sẵn sàng hoạt động.",
        )

    def _start_app_update_flow(
        self,
        latest: str,
        fallback_url: str,
        setup_url: str = "",
        setup_size: int = 0,
    ):
        """Show clear live progress and prompt for restart upon completion."""
        from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QApplication
        from PyQt6.QtCore import Qt
        from ui.workers import AppUpdateWorker
        import os
        import sys
        import subprocess

        progress_dlg = QProgressDialog("Đang chuẩn bị cập nhật...", "Hủy", 0, 100, self)
        progress_dlg.setWindowTitle(f"Cập nhật DubStudio v{latest}")
        progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(5)
        progress_dlg.setAutoClose(False)
        progress_dlg.setAutoReset(False)
        progress_dlg.show()

        worker = AppUpdateWorker(setup_url=setup_url, setup_size=setup_size)

        def _on_progress(pct: int, msg: str):
            progress_dlg.setValue(pct)
            progress_dlg.setLabelText(msg)

        def _on_finished(result):
            progress_dlg.close()
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowTitle("Cập nhật hoàn tất")
            msg_box.setText(
                f"🎉 Bản cập nhật DubStudio v{latest} đã được tải và cài đặt thành công!\n\n"
                "Bạn có muốn khởi động lại ứng dụng ngay bây giờ để áp dụng bản cập nhật không?"
            )
            btn_restart = msg_box.addButton("Khởi động lại ngay", QMessageBox.ButtonRole.AcceptRole)
            btn_later = msg_box.addButton("Để sau (áp dụng khi mở lại)", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()

            if msg_box.clickedButton() == btn_restart:
                installer = result.get("installer_path") if result else None
                mgr = result.get("mgr") if result else None
                info = result.get("info") if result else None

                # 1. Graceful shutdown: stop workers, media players, and release locks
                try:
                    from dubstudio.tts.worker_server import stop_worker_server
                    stop_worker_server()
                except Exception:
                    pass
                try:
                    if hasattr(self, "_studio_page") and hasattr(self._studio_page, "_video_player"):
                        self._studio_page._video_player.stop()
                except Exception:
                    pass
                try:
                    from dubstudio.paths import migrate_legacy_user_data
                    migrate_legacy_user_data()
                except Exception:
                    pass

                # 2. Breakaway relaunch with PID wait (no file lock collisions, survives Job Object exit)
                from dubstudio.win_job import launch_breakaway_process
                current_pid = os.getpid()
                target_exe = sys.executable

                mode = result.get("mode") if result else None
                if (mode == "velopack_delta" or (mgr and info)) and mgr and info:
                    # TẦNG 1: Gói cập nhật vi sai (Velopack Delta) — Áp dụng trực tiếp qua Velopack
                    # Tuyệt đối không gọi Setup.exe -s khi Tầng 1 đã tải thành công
                    try:
                        mgr.apply_updates_and_restart(info)
                    except Exception:
                        from dubstudio.paths import get_app_dir
                        from dubstudio.win_job import launch_breakaway_process
                        update_exe = get_app_dir().parent / "Update.exe"
                        if update_exe.exists():
                            cmd = [str(update_exe), "apply", "--waitPid", str(current_pid), "--restart"]
                            launch_breakaway_process(cmd)
                    app_inst = QApplication.instance()
                    if app_inst:
                        app_inst.quit()
                    os._exit(0)
                elif installer:
                    # TẦNG 2: Fallback Setup.exe -s (chỉ kích hoạt khi Tầng 1 không khả dụng hoặc lỗi)
                    ps_cmd = (
                        f"$pid_wait = {current_pid}; "
                        f"Wait-Process -Id $pid_wait -Timeout 10 -ErrorAction SilentlyContinue; "
                        f"Start-Process -FilePath '{installer}' -ArgumentList '-s' -Wait; "
                        f"Start-Process -FilePath '{target_exe}'"
                    )
                    cmd = ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd]
                    launch_breakaway_process(cmd)
                    app_inst = QApplication.instance()
                    if app_inst:
                        app_inst.quit()
                    os._exit(0)
                else:
                    # Fallback standard restart
                    ps_cmd = (
                        f"$pid_wait = {current_pid}; "
                        f"Wait-Process -Id $pid_wait -Timeout 10 -ErrorAction SilentlyContinue; "
                        f"Start-Process -FilePath '{target_exe}'"
                    )
                    cmd = ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd]
                    launch_breakaway_process(cmd)
                    app_inst = QApplication.instance()
                    if app_inst:
                        app_inst.quit()
                    os._exit(0)
            else:
                mgr = result.get("mgr") if result else None
                info = result.get("info") if result else None
                if mgr and info:
                    mgr.wait_exit_then_apply_updates(info)


        def _on_error(err: str):
            progress_dlg.close()
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Lỗi cập nhật tự động")
            msg_box.setText(
                f"Không thể tự động áp dụng bản cập nhật:\n{err}\n\n"
                "Bạn có muốn mở trang phát hành GitHub để tải bộ cài đặt mới nhất không?"
            )
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if msg_box.exec() == QMessageBox.StandardButton.Yes:
                from PyQt6.QtCore import QUrl
                from PyQt6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl(fallback_url or "https://github.com/Lurz0205/DubStudiobyHTB/releases"))

        progress_dlg.canceled.connect(worker.requestInterruption)
        worker.progress.connect(_on_progress)
        worker.finished.connect(_on_finished)
        worker.error.connect(_on_error)
        self._app_update_worker = worker
        worker.start()

    def _start_startup_update_check(self):
        """Run startup scan for updates and missing components in background."""
        try:
            from ui.workers import StartupCheckWorker
            self._startup_worker = StartupCheckWorker()
            self._startup_worker.finished.connect(self._on_startup_check_finished)
            self._startup_worker.start()
        except Exception:
            pass

    def _on_startup_check_finished(self, res: dict):
        """Handle startup check results cleanly without blocking the user."""
        if not res:
            return

        # Refresh settings page if present to reflect newly verified components
        if hasattr(self, "_settings_page") and hasattr(self._settings_page, "_render_components_ui"):
            try:
                self._settings_page._render_components_ui()
            except Exception:
                pass

        has_app = res.get("has_app_update", False)
        comp_updates = res.get("component_updates", [])
        missing = res.get("missing_components", [])

        if has_app:
            latest = res.get("latest_version")
            self.status_bar.showMessage(f"● Đã có phiên bản mới v{latest}. Mở Cài đặt để cập nhật.")
        elif comp_updates:
            self.status_bar.showMessage(f"● Có {len(comp_updates)} bản cập nhật mô hình AI. Mở Cài đặt để cập nhật.")
        elif missing:
            self.status_bar.showMessage(f"● Lưu ý: Có {len(missing)} mô hình chưa tải. Vào Cài đặt để tải gói cần dùng.")
        else:
            self.status_bar.showMessage("● Sẵn sàng làm việc (Toàn bộ mô hình đã cập nhật).")

    def _on_tutorial_clicked(self):
        """Display the Onboarding & Whisper Model Comparison Tutorial."""
        from ui.dialogs.welcome_tutorial_dialog import WelcomeTutorialDialog
        dlg = WelcomeTutorialDialog(self)
        if dlg.exec():
            if hasattr(self, "_settings_page"):
                self._settings_page.load_settings()

    def closeEvent(self, event):
        """Clean up active threads before exit to prevent QThread destroyed error."""
        # Clean projects page workers
        if hasattr(self, "_projects_page") and hasattr(self._projects_page, "_workers"):
            for w in self._projects_page._workers:
                if w.isRunning():
                    w.quit()
                    w.wait(500)
        # Clean studio page workers
        if hasattr(self, "_studio_page") and hasattr(self._studio_page, "_workers"):
            for w in self._studio_page._workers:
                if w.isRunning():
                    w.quit()
                    w.wait(500)
        # Clean export page workers
        if hasattr(self, "_export_page") and hasattr(self._export_page, "_workers"):
            for w in self._export_page._workers:
                if w.isRunning():
                    w.quit()
                    w.wait(500)
        # Clean settings page workers
        if hasattr(self, "_settings_page") and hasattr(self._settings_page, "_workers"):
            for w in self._settings_page._workers:
                if w.isRunning():
                    w.quit()
                    w.wait(500)
        # Clean merge page workers
        if hasattr(self, "_merge_page") and hasattr(self._merge_page, "_workers"):
            for w in self._merge_page._workers:
                if w.isRunning():
                    w.quit()
                    w.wait(500)
        event.accept()
        import os
        if "PYTEST_CURRENT_TEST" not in os.environ:
            os._exit(0)
