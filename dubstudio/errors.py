"""Custom errors with Vietnamese messages and actionable hints."""
from typing import Any, Dict, Optional


class DubError(Exception):
    """Base exception for all predictable failures in dubstudio."""

    def __init__(
        self,
        code: str = "DUB_ERROR",
        user_message_vi: Optional[str] = None,
        hint_vi: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if user_message_vi is None:
            # Flexible 1-argument usage: DubError("Some error message")
            msg = code
            c = "DUB_ERROR"
            hint = "Vui lòng kiểm tra lại thao tác hoặc cấu hình."
        else:
            c = code
            msg = user_message_vi
            hint = hint_vi or ""
        super().__init__(f"[{c}] {msg} - Gợi ý: {hint}")
        self.code = c
        self.user_message_vi = msg
        self.hint_vi = hint
        self.details = details or {}

    def __str__(self) -> str:
        return self.user_message_vi

    def format_user(self) -> str:
        """Format an error string intended for display to the user."""
        msg = f"❌ Lỗi [{self.code}]: {self.user_message_vi}\n💡 Khắc phục: {self.hint_vi}"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            msg += f"\nChi tiết: {details_str}"
        return msg

    @classmethod
    def cuda_oom(cls, stage_name: str, details: Optional[Dict[str, Any]] = None) -> "DubError":
        return cls(
            code="CUDA_OOM",
            user_message_vi=f"Tràn bộ nhớ GPU (VRAM) trong giai đoạn '{stage_name}'.",
            hint_vi="Hệ thống sẽ tự động hạ tải xuống CPU hoặc giảm kích thước chunk xử lý. Đóng bớt các ứng dụng đang dùng GPU và thử lại.",
            details=details,
        )

    @classmethod
    def cudnn_missing(cls, details: Optional[Dict[str, Any]] = None) -> "DubError":
        return cls(
            code="CUDNN_MISSING",
            user_message_vi="Thiếu thư viện cuDNN/cuBLAS trên hệ thống Windows.",
            hint_vi="Cài đặt các gói hỗ trợ bằng lệnh: .venv\\Scripts\\pip install nvidia-cublas-cu12 nvidia-cudnn-cu12.",
            details=details,
        )

    @classmethod
    def api_rate_limited(cls, retry_after: int = 60, details: Optional[Dict[str, Any]] = None) -> "DubError":
        return cls(
            code="API_RATE_LIMIT",
            user_message_vi="Đạt giới hạn lượt gọi miễn phí Google Gemini API (Mã 429).",
            hint_vi=f"Vui lòng đợi khoảng {retry_after} giây trước khi gửi tiếp, hoặc đổi API key khác trong tab Cài đặt.",
            details=details,
        )

    @classmethod
    def disk_full(cls, path: str, required_mb: int = 500, details: Optional[Dict[str, Any]] = None) -> "DubError":
        return cls(
            code="DISK_FULL",
            user_message_vi=f"Dung lượng ổ đĩa tại '{path}' không đủ (cần tối thiểu {required_mb} MB).",
            hint_vi="Dọn dẹp bớt các file thừa trong thư mục workspace/out hoặc giải phóng dung lượng ổ cứng của bạn.",
            details=details,
        )

    @classmethod
    def corrupted_video(cls, video_path: str, details: Optional[Dict[str, Any]] = None) -> "DubError":
        return cls(
            code="CORRUPTED_VIDEO",
            user_message_vi=f"File video '{video_path}' bị lỗi hoặc định dạng không được hỗ trợ.",
            hint_vi="Thử mở video bằng VLC để kiểm tra, hoặc dùng phần mềm HandBrake/FFmpeg chuyển đổi lại sang định dạng chuẩn MP4 (H.264).",
            details=details,
        )

    @classmethod
    def invalid_path(cls, path_str: str, details: Optional[Dict[str, Any]] = None) -> "DubError":
        return cls(
            code="INVALID_PATH",
            user_message_vi=f"Đường dẫn file '{path_str}' chứa ký tự đặc biệt hoặc không truy cập được.",
            hint_vi="Đổi tên file và thư mục chứa sang tiếng Việt không dấu hoặc tiếng Anh, tránh các ký tự đặc biệt như ?, *, <, >.",
            details=details,
        )
