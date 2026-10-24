# DubStudio v1.1.3 (Bản vá lỗi & Nâng cấp Hệ thống Cập nhật - Patch Release)

Bản cập nhật v1.1.3 mang đến kiến trúc cập nhật an toàn, cơ chế Hot-Patch siêu tốc, chu trình khởi động lại không xung đột Job Object và hoàn thiện vòng lặp khớp thời lượng thoại (Fit stage):

### 🚀 Các cải tiến & Tính năng mới nổi bật:

1. **Khắc phục triệt để lỗi cài đè & Tách biệt dữ liệu người dùng:**
   - Tách biệt hoàn toàn thư mục cài đặt ứng dụng của Velopack (`%LocalAppData%\DubStudio`) khỏi thư mục dữ liệu người dùng (`%LocalAppData%\DubStudioData`).
   - Tự động di chuyển an toàn toàn bộ mô hình AI (1.5GB+) và dữ liệu sang `DubStudioData`. Cài đè `DubStudio-win-Setup.exe` không bao giờ gặp lỗi `Directory already exists, and user cancelled overwrite`, và **không làm mất bất kỳ mô hình AI nào** đã tải.

2. **Cơ chế Hot-Patch siêu tốc (< 1MB) & Vượt PyiFrozenImporter:**
   - Tích hợp hệ thống Hot-Patch động tại `%LocalAppData%\DubStudioData\hotpatch\<VERSION>\`.
   - Sử dụng `HotpatchMetaPathFinder` ở `sys.meta_path[0]` để nạp trực tiếp các file sửa lỗi `.py`/`.pyc` vào RAM thay vì bản đóng băng trong file `.exe` của PyInstaller, không chạm vào `current/_internal/` để bảo toàn tính toàn vẹn của Velopack delta packages.
   - Tự động dọn dẹp các hot-patch cũ khi người dùng nâng cấp lên phiên bản `.exe` mới.

3. **Mở khóa Breakaway Job Object & Chu trình Safe Relaunch (Wait-for-PID):**
   - Cấu hình cờ `JOB_OBJECT_LIMIT_BREAKAWAY_OK` trong `dubstudio/win_job.py`, bổ sung hàm `launch_breakaway_process()`.
   - Chu trình khởi động lại sau cập nhật sẽ dừng toàn bộ workers, media player, chờ tiến trình có `PID` cũ thoát hoàn toàn khỏi bảng tiến trình Windows (tối đa 10s) rồi mới chạy `Setup.exe -s` và mở lại app, loại bỏ hoàn toàn lỗi khóa file `WinError 32` và không bị Windows Kernel đóng ngang.

4. **Xác thực toàn vẹn SHA-256 & Kích thước Byte:**
   - Kiểm tra mã băm SHA-256 và dung lượng thực tế trước khi áp dụng file vá hoặc bộ cài đặt. Nếu rớt mạng hoặc dữ liệu tải về bị thiếu, hệ thống tự động xóa file tạm và cảnh báo người dùng thay vì chạy file lỗi.

5. **Đồng bộ cảnh báo mô hình theo đúng lựa chọn người dùng:**
   - Hệ thống ghi nhớ chính xác mô hình nhận diện giọng nói (ASR) và tách nhạc nền (Separation) mà người dùng đã chọn trong **Hướng dẫn ban đầu (Tutorial)** hoặc **Cài đặt**.
   - Chỉ quét và cảnh báo đúng mô hình người dùng đã chọn, không bao giờ tự ý nhắc tải mô hình không sử dụng.
   - Khi người dùng chủ động đổi sang mô hình khác trong Cài đặt mà máy chưa có, ứng dụng sẽ lập tức hiển thị thông báo nhắc tải gói tương ứng.

6. **Tối ưu hóa Giai đoạn Fit (Khớp tiếng - hình 2 chiều & Batch TTS siêu tốc):**
   - **Cân bằng hai chiều (Two-way timing balance):** Tự động rút gọn câu bị đè âm thanh (`direction = 'shorter'`) và thoát ý câu dịch cộc lốc/quá ngắn so với khẩu hình nhân vật (`direction = 'longer'`).
   - **Gom 1 request LLM duy nhất:** Gửi toàn bộ các câu cần điều chỉnh trong cả video đến Gemini trong 1 lượt prompt duy nhất, rút ngắn thời gian xử lý từ vài phút xuống còn vài giây.
   - **Batch TTS Warm Worker:** Khởi động engine VieNeu một lần duy nhất, tổng hợp mỗi câu sửa lại chỉ tốn ~0.4s (thay vì khởi động lại Python 11s/câu).
   - **Chống va chạm dây chuyền:** Chỉ tổng hợp âm thanh cho những câu thực sự thay đổi lời thoại; tự động kết thúc vòng lặp ngay sau Lượt 1 nếu timeline đã an toàn.
   - **Khóa mốc phát âm (`orig_start`):** Giới hạn lùi tối đa 0.25s vào khoảng lặng trước để bám sát thời điểm người nói trên video gốc.

7. **Loại bỏ phụ thuộc cổng mạng TCP 8765:**
   - Chuyển toàn bộ giao tiếp UI sang In-Memory ASGI Bridge trong RAM, GUI khởi động tức thì và hoạt động mượt mà không lo Windows Firewall hay đụng độ cổng mạng.
