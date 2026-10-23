"""Component update notification dialog in Vietnamese."""
from __future__ import annotations
from typing import Any, Dict, Optional
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon
from ui.theme import COLORS


class ComponentUpdateDialog(QDialog):
    """Notification dialog presenting component updates clearly with consent for large downloads."""

    def __init__(self, update_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.update_info = update_info
        self.user_agreed = False
        self.remember_choice = False

        pkg = update_info.get("package", {})
        self.pkg_name = pkg.get("name", pkg.get("id", "Gói dữ liệu"))
        self.size_mb = update_info.get("size_mb", 0.0)
        self.changelog = update_info.get("changelog", "")
        self.is_large = bool(update_info.get("is_large", False))

        self.setWindowTitle("Cập nhật gói dữ liệu AI")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"background-color: {COLORS['surface']}; color: {COLORS['text']}; font-size: 13px;")

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)

        title = QLabel(f"Có phiên bản mới của gói <b>{self.pkg_name}</b> ({self.size_mb:.1f} MB)")
        title.setStyleSheet("font-size: 14.5px; font-weight: bold; color: #f8fafc;")
        title.setWordWrap(True)
        layout.addWidget(title)

        desc = QLabel(f"Nội dung thay đổi: {self.changelog or 'Cải tiến hiệu suất và chất lượng mô hình.'}")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; line-height: 1.4;")
        layout.addWidget(desc)

        if not self.is_large:
            self._chk_remember = QCheckBox("Ghi nhớ lựa chọn này cho các lần sau")
            layout.addWidget(self._chk_remember)
        else:
            self._chk_remember = None

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch(1)

        btn_later = QPushButton(" Để sau")
        btn_later.setFixedHeight(32)
        btn_later.clicked.connect(self._on_later)
        btn_box.addWidget(btn_later)

        btn_download = QPushButton(" Tải ngay")
        btn_download.setIcon(get_icon("check", "#ffffff", "#ffffff", 13))
        btn_download.setObjectName("primary")
        btn_download.setFixedHeight(32)
        btn_download.clicked.connect(self._on_download)
        btn_box.addWidget(btn_download)

        layout.addLayout(btn_box)

    def _on_download(self):
        self.user_agreed = True
        if self._chk_remember and self._chk_remember.isChecked():
            self.remember_choice = True
        self.accept()

    def _on_later(self):
        self.user_agreed = False
        if self._chk_remember and self._chk_remember.isChecked():
            self.remember_choice = True
        self.reject()
