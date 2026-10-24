"""Projects / Tasks Management Page for DubStudio.

HyperOS Bento Grid architecture: Metric summary tiles, clean project cards,
and direct studio transitions without legacy spreadsheet tables.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon
from ui.workers import CreateJobWorker, DeleteJobWorker, ListJobsWorker


def _fmt_dur(seconds: float) -> str:
    if not seconds or seconds <= 0:
        return "--:--"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


class BentoProjectCard(QFrame):
    """Modern Bento Card for a single project item."""

    clicked = pyqtSignal(str)

    def __init__(self, job: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("bento_project_item")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(66)

        self.jid = job.get("id") or ""
        self.name = job.get("video_name") or self.jid
        dur_sec = job.get("duration", 0.0)
        date_str = job.get("created_at") or "--"
        has_video = job.get("has_video", False)
        stages = job.get("stages", {})

        # Status determination
        if has_video or ("render" in stages and stages["render"].get("status") == "done"):
            status_text = "Đã xuất video"
            status_style = "background: #0f2e22; color: #10b981; border: 1px solid #14532d;"
        elif job.get("is_active"):
            status_text = "Đang xử lý"
            status_style = "background: #0c2a4d; color: #38bdf8; border: 1px solid #0284c7;"
        elif job.get("has_state"):
            status_text = "Đang biên tập"
            status_style = "background: #2a200d; color: #f59e0b; border: 1px solid #78350f;"
        else:
            status_text = "Mới tạo"
            status_style = "background: #171924; color: #9ca3af; border: 1px solid #23283a;"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(14)

        # Left: Rounded Video Icon Box
        icon_box = QFrame()
        icon_box.setFixedSize(38, 38)
        icon_box.setStyleSheet("background: #1a1e2d; border-radius: 10px; border: 1px solid #282f45;")
        ic_layout = QVBoxLayout(icon_box)
        ic_layout.setContentsMargins(0, 0, 0, 0)
        ic_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ic = QLabel()
        lbl_ic.setPixmap(get_icon("film", "#38bdf8", "#38bdf8", 16).pixmap(16, 16))
        ic_layout.addWidget(lbl_ic)
        layout.addWidget(icon_box)

        # Middle: Video Title & Meta
        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        info_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_name = QLabel(self.name)
        lbl_name.setStyleSheet("font-size: 13px; font-weight: 600; color: #f1f3f7;")
        info_box.addWidget(lbl_name)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)

        lbl_time_ic = QLabel()
        lbl_time_ic.setPixmap(get_icon("clock", "#9ca3af", "#9ca3af", 12).pixmap(12, 12))
        meta_row.addWidget(lbl_time_ic)

        lbl_dur = QLabel(_fmt_dur(dur_sec))
        lbl_dur.setStyleSheet("font-size: 11px; color: #9ca3af;")
        meta_row.addWidget(lbl_dur)

        lbl_dot = QLabel("•")
        lbl_dot.setStyleSheet("color: #4b5563; font-size: 10px;")
        meta_row.addWidget(lbl_dot)

        lbl_date = QLabel(date_str)
        lbl_date.setStyleSheet("font-size: 11px; color: #656d7d;")
        meta_row.addWidget(lbl_date)
        meta_row.addStretch(1)

        info_box.addLayout(meta_row)
        layout.addLayout(info_box, 1)

        # Right: Status Pill Badge
        lbl_status = QLabel(status_text)
        lbl_status.setFixedHeight(32)
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_status.setStyleSheet(
            f"{status_style} border-radius: 8px; padding: 0 10px; font-size: 11px; font-weight: 600;"
        )
        layout.addWidget(lbl_status, 0, Qt.AlignmentFlag.AlignVCenter)

        # Action Button: Mở
        self.btn_open = QPushButton(" Mở")
        self.btn_open.setIcon(get_icon("play", "#ffffff", "#ffffff", 12))
        self.btn_open.setObjectName("primary")
        self.btn_open.setFixedHeight(32)
        self.btn_open.setStyleSheet("padding: 0 14px; font-size: 11px; font-weight: 600; border-radius: 8px;")
        layout.addWidget(self.btn_open, 0, Qt.AlignmentFlag.AlignVCenter)

        # Delete Button
        self.btn_del = QPushButton()
        self.btn_del.setIcon(get_icon("trash", "#ef4444", "#fca5a5", 13))
        self.btn_del.setObjectName("danger")
        self.btn_del.setFixedSize(32, 32)
        self.btn_del.setStyleSheet("border-radius: 8px;")
        layout.addWidget(self.btn_del, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseDoubleClickEvent(self, event):
        self.clicked.emit(self.jid)
        super().mouseDoubleClickEvent(event)


class ProjectsPage(QWidget):
    """Page listing all projects in a clean Bento Grid layout."""

    open_studio_requested = pyqtSignal(str)  # job_id
    job_delete_requested = pyqtSignal(str)   # job_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: List[any] = []
        self._jobs: List[dict] = []
        self._setup_ui()
        self.refresh_projects()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title = QLabel("DỰ ÁN")
        title.setObjectName("section_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        btn_refresh = QPushButton(" Làm mới")
        btn_refresh.setIcon(get_icon("refresh", "#9ca3af", "#f0f2f5", 14))
        btn_refresh.setFixedHeight(34)
        btn_refresh.setStyleSheet("font-size: 12px; font-weight: 500; padding: 0 14px; border-radius: 8px;")
        btn_refresh.clicked.connect(self.refresh_projects)
        header_layout.addWidget(btn_refresh, 0, Qt.AlignmentFlag.AlignVCenter)

        btn_create = QPushButton(" Tạo dự án mới")
        btn_create.setIcon(get_icon("plus", "#ffffff", "#ffffff", 14))
        btn_create.setObjectName("primary")
        btn_create.setFixedHeight(34)
        btn_create.setStyleSheet("font-size: 12px; font-weight: 600; padding: 0 16px; border-radius: 8px;")
        btn_create.clicked.connect(self._create_project)
        header_layout.addWidget(btn_create, 0, Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(header_layout)

        # ─── Bento Grid Metric Tiles ───
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        # Metric 1: Total Projects
        m1 = QFrame()
        m1.setObjectName("bento_metric")
        m1.setFixedWidth(240)
        v1 = QVBoxLayout(m1)
        v1.setContentsMargins(0, 0, 0, 0)
        v1.setSpacing(4)
        h1 = QHBoxLayout()
        lbl_ic1 = QLabel()
        lbl_ic1.setPixmap(get_icon("folder", "#38bdf8", "#38bdf8", 16).pixmap(16, 16))
        h1.addWidget(lbl_ic1)
        lbl_t1 = QLabel("TỔNG DỰ ÁN")
        lbl_t1.setStyleSheet("color: #656d7d; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        h1.addWidget(lbl_t1)
        h1.addStretch(1)
        v1.addLayout(h1)
        self._lbl_metric_count = QLabel("0")
        self._lbl_metric_count.setStyleSheet("font-size: 22px; font-weight: 700; color: #f1f3f7;")
        v1.addWidget(self._lbl_metric_count)
        lbl_sub1 = QLabel("Dự án đang quản lý")
        lbl_sub1.setStyleSheet("color: #656d7d; font-size: 11px;")
        v1.addWidget(lbl_sub1)
        metrics_layout.addWidget(m1)
        metrics_layout.addStretch(1)

        main_layout.addLayout(metrics_layout)

        # Status info banner / empty hint
        self._lbl_hint = QLabel("")
        self._lbl_hint.setStyleSheet("color: #38bdf8; font-size: 12px; padding: 4px 8px; background-color: #0c1a29; border: 1px solid #163654; border-radius: 6px;")
        self._lbl_hint.setVisible(False)
        main_layout.addWidget(self._lbl_hint)

        # Projects Scroll Area Container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)

        scroll.setWidget(self._list_container)
        main_layout.addWidget(scroll, 1)

    def refresh_projects(self):
        w = ListJobsWorker()

        def _on_done(jobs: List[dict]):
            self._jobs = jobs
            self._render_cards(jobs)

        def _on_err(err: str):
            self._lbl_hint.setText(f"Lỗi tải danh sách: {err}")
            self._lbl_hint.setVisible(True)

        w.finished.connect(_on_done)
        w.error.connect(_on_err)
        self._workers.append(w)
        w.start()

    def _render_cards(self, jobs: List[dict]):
        if hasattr(self, "_lbl_metric_count"):
            self._lbl_metric_count.setText(str(len(jobs)))

        # Clear existing items
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not jobs:
            empty_box = QFrame()
            empty_box.setObjectName("bento_metric")
            v_empty = QVBoxLayout(empty_box)
            v_empty.setContentsMargins(30, 40, 30, 40)
            v_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v_empty.setSpacing(12)

            lbl_empty_t = QLabel("Chưa có dự án nào")
            lbl_empty_t.setStyleSheet("font-size: 15px; font-weight: 600; color: #f1f3f7;")
            v_empty.addWidget(lbl_empty_t, alignment=Qt.AlignmentFlag.AlignCenter)

            btn_empty_create = QPushButton("  Tạo dự án mới")
            btn_empty_create.setIcon(get_icon("plus", "#ffffff", "#ffffff", 14))
            btn_empty_create.setObjectName("primary")
            btn_empty_create.setFixedHeight(34)
            btn_empty_create.clicked.connect(self._create_project)
            v_empty.addWidget(btn_empty_create, alignment=Qt.AlignmentFlag.AlignCenter)

            self._list_layout.addWidget(empty_box)
            self._list_layout.addStretch(1)
            return

        for j in jobs:
            card = BentoProjectCard(j, self._list_container)
            jid = card.jid
            name = card.name
            card.clicked.connect(lambda id=jid: self.open_studio_requested.emit(id))
            card.btn_open.clicked.connect(lambda _, id=jid: self.open_studio_requested.emit(id))
            card.btn_del.clicked.connect(lambda _, id=jid, n=name: self._delete_project(id, n))
            self._list_layout.addWidget(card)

        self._list_layout.addStretch(1)

    def _create_project(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn video cần lồng tiếng",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.flv *.webm);;All Files (*.*)",
        )
        if not file_path:
            return

        import time
        from dubstudio.paths import get_workspace_dir
        base_date = time.strftime("%d%m%Y")
        ws_dir = get_workspace_dir()
        candidate = base_date
        idx = 1
        existing_names = set()
        if ws_dir.exists():
            for p in ws_dir.iterdir():
                if p.is_dir() and not p.name.startswith(".") and p.name != "components":
                    existing_names.add(p.name)
        for j in getattr(self, "_jobs", []):
            if j.get("id"):
                existing_names.add(j["id"])
            if j.get("video_name"):
                existing_names.add(j["video_name"])

        while candidate in existing_names:
            candidate = f"{base_date}_{idx}"
            idx += 1

        default_name = candidate
        proj_name, ok = QInputDialog.getText(
            self,
            "Đặt tên dự án",
            "Nhập tên dự án:",
            text=default_name,
        )
        if not ok:
            return
        proj_name = proj_name.strip() or default_name

        self._lbl_hint.setText("Đang tiếp nhận và khởi tạo dự án...")
        self._lbl_hint.setVisible(True)

        w = CreateJobWorker(file_path, proj_name)

        def _on_done(res: dict):
            jid = res.get("job_id")
            self._lbl_hint.setVisible(False)
            self.refresh_projects()
            if jid:
                self.open_studio_requested.emit(jid)

        def _on_err(err: str):
            self._lbl_hint.setVisible(False)
            QMessageBox.critical(self, "Lỗi tạo dự án", f"Không thể khởi tạo dự án: {err}")

        w.finished.connect(_on_done)
        w.error.connect(_on_err)
        self._workers.append(w)
        w.start()

    def _delete_project(self, job_id: str, video_name: str):
        confirm = QMessageBox.question(
            self,
            "Xác nhận xóa dự án",
            f"Bạn có chắc muốn xóa dự án '{video_name}' không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.job_delete_requested.emit(job_id)
        w = DeleteJobWorker(job_id)

        def _on_done(jid: str):
            self.refresh_projects()

        def _on_err(err: str):
            QMessageBox.critical(self, "Lỗi xóa dự án", f"Không thể xóa dự án: {err}")

        w.finished.connect(_on_done)
        w.error.connect(_on_err)
        self._workers.append(w)
        w.start()
