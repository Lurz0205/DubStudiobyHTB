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
        self._btn_projects.setIcon(get_icon("folder", "#9ca3af", "#38bdf8", 17))
        self._btn_projects.setIconSize(QSize(17, 17))
        self._btn_projects.setProperty("class", "nav_item")
        self._btn_projects.setToolTip("Quản lý danh sách các dự án lồng tiếng")
        self._btn_projects.setCheckable(True)
        self._btn_projects.setChecked(True)
        self._btn_projects.setProperty("active", "true")
        self._btn_group.addButton(self._btn_projects, 0)
        side_layout.addWidget(self._btn_projects)

        self._btn_studio = QPushButton("  Lồng tiếng")
        self._btn_studio.setIcon(get_icon("mic", "#9ca3af", "#38bdf8", 17))
        self._btn_studio.setIconSize(QSize(17, 17))
        self._btn_studio.setProperty("class", "nav_item")
        self._btn_studio.setToolTip("Xem trước video, chỉnh sửa câu thoại, timeline và tạo lồng tiếng")
        self._btn_studio.setCheckable(True)
        self._btn_group.addButton(self._btn_studio, 1)
        side_layout.addWidget(self._btn_studio)

        self._btn_export = QPushButton("  Phụ đề")
        self._btn_export.setIcon(get_icon("subtitles", "#9ca3af", "#38bdf8", 17))
        self._btn_export.setIconSize(QSize(17, 17))
        self._btn_export.setProperty("class", "nav_item")
        self._btn_export.setToolTip("Tùy biến phong cách và cách khắc phụ đề vào video")
        self._btn_export.setCheckable(True)
        self._btn_group.addButton(self._btn_export, 2)
        side_layout.addWidget(self._btn_export)

        self._btn_merge = QPushButton("  Chỉnh sửa video")
        self._btn_merge.setIcon(get_icon("scissors", "#9ca3af", "#38bdf8", 17))
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
        self._btn_check_updates.setIcon(get_icon("download", "#9ca3af", "#38bdf8", 16))
        self._btn_check_updates.setIconSize(QSize(16, 16))
        self._btn_check_updates.setProperty("class", "nav_item")
        self._btn_check_updates.setToolTip("Kiểm tra bản cập nhật mới trên GitHub và các gói dữ liệu AI")
        self._btn_check_updates.clicked.connect(self._on_check_updates_clicked)
        side_layout.addWidget(self._btn_check_updates)

        self._btn_tutorial = QPushButton("  Hướng dẫn")
        self._btn_tutorial.setIcon(get_icon("info", "#9ca3af", "#38bdf8", 16))
        self._btn_tutorial.setIconSize(QSize(16, 16))
        self._btn_tutorial.setProperty("class", "nav_item")
        self._btn_tutorial.setToolTip("Xem lại bảng so sánh mô hình Whisper và hướng dẫn quy trình sử dụng")
        self._btn_tutorial.clicked.connect(self._on_tutorial_clicked)
        side_layout.addWidget(self._btn_tutorial)

        self._btn_settings = QPushButton("  Cài đặt")
        self._btn_settings.setIcon(get_icon("settings", "#9ca3af", "#38bdf8", 17))
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
            self._projects_page.refresh_projects()
        elif page_id == 2 and hasattr(self, "_export_page"):
            self._export_page.refresh_jobs()

    def _on_check_updates_clicked(self):
        """Check for both GitHub release updates and modular components updates."""
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        from dubstudio.updater import check_all_updates, CURRENT_VERSION

        self.status_bar.showMessage("Đang kiểm tra cập nhật từ GitHub và các gói dữ liệu...")
        res = check_all_updates()
        self.status_bar.showMessage("● Sẵn sàng làm việc.")

        has_app = res.get("has_app_update", False)
        comp_updates = res.get("component_updates", [])

        if has_app:
            latest = res.get("latest_version")
            from dubstudio.packaging import is_packaged, trigger_app_update, get_velopack_updater
            updater = get_velopack_updater()
            if is_packaged() and updater:
                msg = f"Đã có phiên bản mới v{latest}!\nBạn có muốn tự động tải và cập nhật ngay bây giờ không?"
                reply = QMessageBox.question(
                    self,
                    "Cập nhật ứng dụng",
                    msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    update_url = "https://github.com/Lurz0205/DubStudiobyHTB/releases"
                    self.status_bar.showMessage("Đang tải bản cập nhật ngầm qua Velopack...")
                    triggered = trigger_app_update(update_url)
                    if triggered:
                        QMessageBox.information(
                            self,
                            "Đang cập nhật",
                            "Bản cập nhật đang được tải ngầm.\nỨng dụng sẽ tự động áp dụng phiên bản mới khi bạn mở lại chương trình.",
                        )
                    else:
                        dl_url = res.get("download_url") or update_url
                        QDesktopServices.openUrl(QUrl(dl_url))
                return

            msg = f"Đã có phiên bản mới v{latest} trên GitHub!\n(Phiên bản hiện tại của bạn: v{CURRENT_VERSION})\n\nBạn có muốn mở trang tải bản cập nhật mới không?"
            reply = QMessageBox.question(
                self,
                "Bản cập nhật mới",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                dl_url = res.get("download_url") or "https://github.com/Lurz0205/DubStudiobyHTB/releases"
                QDesktopServices.openUrl(QUrl(dl_url))
            return

        if comp_updates:
            from ui.dialogs.component_update_dialog import ComponentUpdateDialog
            up_dlg = ComponentUpdateDialog(comp_updates[0], parent=self)
            up_dlg.exec()
            return

        QMessageBox.information(
            self,
            "Kiểm tra cập nhật",
            f"Bạn đang sử dụng phiên bản mới nhất (v{CURRENT_VERSION})!\nToàn bộ các gói thành phần AI đều sẵn sàng.",
        )

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
        os._exit(0)
