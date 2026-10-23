# RESULTS.md — Kết quả Benchmark (Phase 2)

## 1. Video Render (h264_nvenc vs libx264)
| Tool | Clip | Wall time | Peak RAM | Peak VRAM | File Size | Ghi chú |
|---|---|---|---|---|---|---|
| `h264_nvenc` | `tiny.mp4` | FAILED | N/A | N/A | N/A | Cần Nvidia Driver >= 610.00 cho NVENC API 13.1 |
| `libx264` | `tiny.mp4` | 0.35s | 8335 MB | 132 MB | 148.6 KB | Nhanh, chất lượng cao, fallback tự động |

## 2. ASR Tiếng Trung (faster-whisper large-v3-turbo)
| Tool | Clip | Wall time | Peak RAM | Peak VRAM |
|---|---|---|---|---|
| faster-whisper (large-v3-turbo) | clip_1min.mp4 | 120.00s* | 11071.9 MB | 1434.5 MB |
| faster-whisper (large-v3-turbo) | clip_10min.mp4 | 30.05s | 11087.7 MB | 1442.5 MB |

*\*Lần đầu bao gồm thời gian tải weights mô hình từ HuggingFace vào cache.*

## 3. Tách giọng & nhạc nền (Demucs htdemucs)
| Tool | Clip | Wall time | Peak RAM | Peak VRAM |
|---|---|---|---|---|
| Demucs (htdemucs --two-stems vocals) | clip_1min.mp4 | 22.56s | 10028.9 MB | 996.5 MB |
| Demucs (htdemucs --two-stems vocals) | clip_10min.mp4 | 69.01s | 11514.3 MB | 996.5 MB |

## 4. TTS Tiếng Việt (VieNeu-TTS-v3-turbo)
| Giọng nói | Giới tính/Phong cách | Wall time (5 câu) | Tổng âm thanh | Tốc độ (chars/s) | Peak RAM | Peak VRAM |
|---|---|---|---|---|---|---|
| **Quỳnh Anh** | Nữ (chuẩn) | 4.16s | 21.92s | 16.97 chars/s | 9249.1 MB | 960.5 MB |
| **Mai Anh** | Nữ | 3.09s | 21.36s | 17.42 chars/s | 9275.5 MB | 960.5 MB |
| **Minh Đức** | Nam (trầm ấm) | 3.48s | 23.76s | 15.66 chars/s | 9130.8 MB | 960.5 MB |
| **Hải Đăng** | Nam (nhanh) | 2.70s | 18.24s | 20.39 chars/s | 9122.2 MB | 994.5 MB |
