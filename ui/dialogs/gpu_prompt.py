"""GPU Status and Driver guidance dialogs in clear Vietnamese."""
from __future__ import annotations
from typing import Optional
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dubstudio.gpu_check import GPUStatus, inspect_gpu_and_driver
from ui.icons import get_icon
from ui.theme import COLORS


class GPUDiagnosticDialog(QDialog):
    """Clean, user-friendly dialog for GPU / Driver status warnings."""

    def __init__(
        self,
        status: str,
        card_name: str = "",
        cur_driver: str = "",
        min_driver: str = "",
        vram_gb: float = 0.0,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.status = status
        self.card_name = card_name
        self.cur_driver = cur_driver
        self.min_driver = min_driver
        self.vram_gb = vram_gb
        self.chosen_action = "cpu"  # "cpu", "retry", "download_driver"

        self.setWindowTitle("Thông báo cấu hình phần cứng đồ họa (GPU)")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"background-color: {COLORS['surface']}; color: {COLORS['text']}; font-size: 13px;")

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel()
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(title)

        body = QLabel()
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {COLORS['text_secondary']}; line-height: 1.5;")
        layout.addWidget(body)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch(1)

        if self.status == GPUStatus.NO_NVIDIA:
            title.setText("Thông báo: Chạy bằng bộ xử lý trung tâm (CPU)")
            body.setText(
                "Máy của bạn không có card đồ họa NVIDIA (hoặc chỉ sử dụng chip đồ họa Intel / AMD).\n\n"
                "Ứng dụng vẫn hoạt động bình thường nhưng các tác vụ AI (tách nhạc nền, nhận diện giọng nói) "
                "sẽ được xử lý bằng CPU và sẽ chậm hơn so với máy có card đồ họa chuyên dụng."
            )
            btn_cpu = QPushButton(" Tiếp tục bằng CPU")
            btn_cpu.setIcon(get_icon("check", "#ffffff", "#ffffff", 14))
            btn_cpu.setObjectName("primary")
            btn_cpu.setFixedHeight(34)
            btn_cpu.clicked.connect(self._choose_cpu)
            btn_box.addWidget(btn_cpu)

        elif self.status == GPUStatus.DRIVER_OUTDATED_OR_MISSING:
            title.setText("Cần cập nhật Driver đồ họa NVIDIA")
            body.setText(
                f"Đã phát hiện card đồ họa: <b>{self.card_name}</b>\n\n"
                f"• Phiên bản Driver hiện tại: <b style='color:#f87171;'>{self.cur_driver or 'Chưa cài đặt'}</b>\n"
                f"• Phiên bản Driver tối thiểu cần thiết: <b style='color:#34d399;'>{self.min_driver}</b> trở lên.\n\n"
                "Để tận dụng tối đa tốc độ card NVIDIA, bạn vui lòng cài đặt hoặc nâng cấp Driver mới nhất từ trang web chính thức của NVIDIA."
            )
            btn_dl = QPushButton(" Mở trang tải Driver NVIDIA")
            btn_dl.setIcon(get_icon("link", "#38bdf8", "#38bdf8", 13))
            btn_dl.setObjectName("secondary")
            btn_dl.setFixedHeight(34)
            btn_dl.clicked.connect(self._open_driver_page)
            btn_box.addWidget(btn_dl)

            btn_retry = QPushButton(" Kiểm tra lại")
            btn_retry.setIcon(get_icon("refresh", "#9ca3af", "#f8fafc", 13))
            btn_retry.setFixedHeight(34)
            btn_retry.clicked.connect(self._choose_retry)
            btn_box.addWidget(btn_retry)

            btn_cpu = QPushButton(" Dùng CPU tạm thời")
            btn_cpu.setFixedHeight(34)
            btn_cpu.clicked.connect(self._choose_cpu)
            btn_box.addWidget(btn_cpu)

        elif self.status == GPUStatus.VRAM_LOW:
            title.setText("Cảnh báo: Bộ nhớ đồ họa (VRAM) dưới 4 GB")
            body.setText(
                f"Đã phát hiện card đồ họa: <b>{self.card_name}</b> ({self.vram_gb:.1f} GB VRAM).\n\n"
                "Bộ nhớ VRAM dưới 4 GB có thể khiến các mô hình AI lớn bị tràn bộ nhớ (Out of Memory). "
                "Ứng dụng khuyến nghị sử dụng cấu hình nhẹ hơn hoặc chuyển sang chạy bằng CPU để đảm bảo ổn định."
            )
            btn_cpu = QPushButton(" Chạy bằng CPU (Khuyến nghị)")
            btn_cpu.setObjectName("primary")
            btn_cpu.setFixedHeight(34)
            btn_cpu.clicked.connect(self._choose_cpu)
            btn_box.addWidget(btn_cpu)

            btn_continue = QPushButton(" Vẫn thử dùng GPU")
            btn_continue.setFixedHeight(34)
            btn_continue.clicked.connect(self._choose_continue_gpu)
            btn_box.addWidget(btn_continue)

        layout.addLayout(btn_box)

    def _choose_cpu(self):
        self.chosen_action = "cpu"
        self.accept()

    def _choose_continue_gpu(self):
        self.chosen_action = "gpu"
        self.accept()

    def _choose_retry(self):
        self.chosen_action = "retry"
        self.accept()

    def _open_driver_page(self):
        QDesktopServices.openUrl(QUrl("https://www.nvidia.com/Download/index.aspx"))


def check_and_prompt_gpu_if_packaged(parent: Optional[QWidget] = None) -> str:
    """
    Check GPU on startup when packaged.
    Returns chosen mode: 'cuda' or 'cpu'.
    """
    inspection = inspect_gpu_and_driver()
    status = inspection["status"]

    if status == GPUStatus.OK_CUDA:
        return "cuda"

    dlg = GPUDiagnosticDialog(
        status=status,
        card_name=inspection.get("card_name", ""),
        cur_driver=inspection.get("driver_version", ""),
        min_driver=inspection.get("min_driver_required", ""),
        vram_gb=inspection.get("vram_gb", 0.0),
        parent=parent,
    )
    dlg.exec()

    if dlg.chosen_action == "retry":
        return check_and_prompt_gpu_if_packaged(parent)

    return "cpu" if dlg.chosen_action == "cpu" else "cuda"
