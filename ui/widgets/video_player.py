"""Video preview widget using QtMultimedia for synchronized video and audio playback."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QSizeF, QThread, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon


class DraggableSubtitleOverlay(QWidget):
    """
    Interactive subtitle overlay that sits directly on top of the video canvas.
    Uses custom QPainter paintEvent to guarantee 100% visibility on all backgrounds,
    with clear dashed borders, visible resize grips (||), word-wrapping, and true text outline.
    """
    dragged = pyqtSignal(dict)  # {"action": str, ...}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("draggable_subtitle_box")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._draggable = True
        self._mode: Optional[str] = None  # "move", "resize_left", "resize_right"
        self._drag_start_pos: Optional[QPoint] = None
        self._orig_pos: Optional[QPoint] = None
        self._orig_width = 100
        self._style = {}
        self._text = ""
        self._scaled_font_size = 22
        self._hovered = False

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Kéo ở giữa để di chuyển, kéo 2 mép để co giãn khung chữ")

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def set_draggable(self, enabled: bool):
        self._draggable = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_text_and_style(self, text: str, style: dict, scaled_font_size: int = 22, scale_ratio: float = 1.0):
        self._text = text or ""
        self._style = dict(style or {})
        self._scaled_font_size = max(10, scaled_font_size)
        self._scale_ratio = max(0.05, float(scale_ratio))
        self.update()

    def set_style_data(self, style: dict):
        self._style = dict(style or {})
        self.update()

    def mousePressEvent(self, event):
        if self._draggable and event.button() == Qt.MouseButton.LeftButton:
            x_pos = event.position().x()
            w = self.width()
            edge_margin = 18

            if x_pos >= w - edge_margin:
                self._mode = "resize_right"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif x_pos <= edge_margin:
                self._mode = "resize_left"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self._mode = "move"
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

            self._drag_start_pos = event.globalPosition().toPoint()
            proxy = self.graphicsProxyWidget()
            if proxy:
                self._orig_proxy_pos = proxy.pos().toPoint()
            else:
                self._orig_proxy_pos = self.pos()
            self._orig_width = self.width()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._mode:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            if self._mode == "resize_right":
                new_w = max(80, self._orig_width + delta.x() * 2)
                self.dragged.emit({"action": "resize", "width": new_w})
            elif self._mode == "resize_left":
                new_w = max(80, self._orig_width - delta.x() * 2)
                self.dragged.emit({"action": "resize", "width": new_w})
            elif self._mode == "move":
                proxy = self.graphicsProxyWidget()
                if proxy:
                    new_scene_x = proxy.pos().x()
                    new_scene_y = self._orig_proxy_pos.y() + delta.y()
                    proxy.setPos(new_scene_x, new_scene_y)
                    self.dragged.emit({"action": "move", "scene_y": new_scene_y, "box_h": self.height()})
                else:
                    new_y = self._orig_proxy_pos.y() + delta.y()
                    self.dragged.emit({"action": "move", "scene_y": new_y, "box_h": self.height()})
            event.accept()
        else:
            x_pos = event.position().x()
            w = self.width()
            if x_pos >= w - 18 or x_pos <= 18:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._mode:
            self._mode = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = self.rect()

        has_box = bool(self._style.get("has_box", True))
        box_color_str = self._style.get("box_color", "#000000")
        box_opacity = float(self._style.get("box_opacity", 0.6))
        scale_r = getattr(self, "_scale_ratio", 1.0)
        box_radius = max(0, int(round(int(self._style.get("box_radius", 6)) * scale_r)))
        box_mode = self._style.get("box_mode", "full_width")  # "full_width" or "wrap_text"

        font_name = self._style.get("font_name", "Arial")
        font_px = max(10, int(getattr(self, "_scaled_font_size", 22)))
        font = QFont(font_name)
        font.setPixelSize(font_px)
        font.setBold(True)
        painter.setFont(font)
        fm = QFontMetrics(font)

        text_align = self._style.get("text_align", "center")
        align_flag = Qt.AlignmentFlag.AlignCenter
        if text_align == "left":
            align_flag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        elif text_align == "right":
            align_flag = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        else:
            align_flag = Qt.AlignmentFlag.AlignCenter

        flags = align_flag | Qt.TextFlag.TextWordWrap
        pad_x_val = float((self._style or {}).get("box_padding_x", 14) or 14)
        pad_y_val = float((self._style or {}).get("box_padding_y", 8) or 8)
        pad_x = max(2, int(round(pad_x_val * scale_r)))
        pad_y = max(1, int(round(pad_y_val * scale_r)))
        text_rect = rect.adjusted(pad_x, pad_y, -pad_x, -pad_y)

        # 1. Determine Box Geometry based on box_mode
        if box_mode == "wrap_text" and self._text:
            text_bound = fm.boundingRect(text_rect, flags, self._text)
            box_rect = QRect(
                max(0, text_bound.left() - pad_x),
                max(0, text_bound.top() - pad_y),
                min(rect.width(), text_bound.width() + pad_x * 2),
                min(rect.height(), text_bound.height() + pad_y * 2),
            )
        else:
            # Full rectangular box spanning the whole container
            box_rect = rect.adjusted(1, 1, -1, -1)

        # 1. Fill Background Box with true opacity and corner radius
        if has_box:
            c = QColor(box_color_str)
            if not c.isValid():
                c = QColor(0, 0, 0)
            c.setAlphaF(max(0.0, min(1.0, box_opacity)))
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(box_rect, box_radius, box_radius)

        # 2. Draw Bounding Rectangle Outline & grips only when hovered or dragged
        if getattr(self, "_hovered", False) or self._mode:
            target_outline = box_rect if box_mode == "wrap_text" else rect.adjusted(1, 1, -1, -1)
            pen_shadow = QPen(QColor(0, 0, 0, 180), 2.5)
            painter.setPen(pen_shadow)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(target_outline, max(2, box_radius), max(2, box_radius))

            pen_border = QPen(QColor(255, 255, 255, 220), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen_border)
            painter.drawRoundedRect(target_outline, max(2, box_radius), max(2, box_radius))

            # 3. Draw visible resize handle grips (||) on left and right edges
            grip_w = 4
            grip_h = max(14, min(rect.height() - 8, 22))
            grip_y = int((rect.height() - grip_h) / 2)

            # Left grip (white with shadow)
            painter.fillRect(3, grip_y + 1, grip_w, grip_h, QColor(0, 0, 0, 160))
            painter.fillRect(2, grip_y, grip_w, grip_h, QColor(255, 255, 255, 240))

            # Right grip (white with shadow)
            rx = rect.width() - grip_w - 3
            painter.fillRect(rx + 1, grip_y + 1, grip_w, grip_h, QColor(0, 0, 0, 160))
            painter.fillRect(rx, grip_y, grip_w, grip_h, QColor(255, 255, 255, 240))

        # 4. Draw Crisp Wrapped Text with True Outline
        if not self._text:
            return

        primary_color = QColor(self._style.get("primary_color", "#FFFFFF"))
        outline_color = QColor(self._style.get("outline_color", "#000000"))
        outline_width = int(self._style.get("outline_width", 2))
        scaled_outline = max(1, int(round(outline_width * scale_r)))

        # Draw outline (stroke) around text
        if outline_width > 0:
            painter.setPen(outline_color)
            r_ow = max(1, min(scaled_outline, 5))
            for dx in range(-r_ow, r_ow + 1):
                for dy in range(-r_ow, r_ow + 1):
                    if dx != 0 or dy != 0:
                        painter.drawText(text_rect.adjusted(dx, dy, dx, dy), flags, self._text)

        # Draw main text
        painter.setPen(primary_color)
        painter.drawText(text_rect, flags, self._text)


class VideoContainerFilter(QObject):
    """Filters resize events of video view to update video and overlay synchronously."""
    def __init__(self, player_widget: VideoPlayerWidget):
        super().__init__()
        self._player = player_widget

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self._player._on_container_resized()
        return super().eventFilter(watched, event)


class AudioPrepWorker(QThread):
    finished = pyqtSignal(int, dict)  # gen_id, results dict

    def __init__(
        self,
        generation_id: int,
        workspace_dir: Optional[Path],
        custom_bgm_path: Optional[str] = None,
        vi_voice_vol: float = 1.0,
        is_rendered_video: bool = False,
    ):
        super().__init__()
        self.gen_id = generation_id
        self.ws = Path(workspace_dir) if workspace_dir else None
        self.custom_bgm_path = custom_bgm_path
        self.vi_voice_vol = vi_voice_vol
        self.is_rendered = is_rendered_video

    def run(self):
        if not self.ws or not self.ws.exists() or self.is_rendered:
            self.finished.emit(self.gen_id, {})
            return

        res = {}
        try:
            # 1. Voice Raw
            vi_wav = VideoPlayerWidget._ensure_voice_raw(self.ws)
            if not vi_wav or not vi_wav.exists():
                vi_wav = (self.ws / "voice_raw.wav") if (self.ws / "voice_raw.wav").exists() else None
            if not vi_wav or not vi_wav.exists():
                vi_wav = (self.ws / "voice_track.wav") if (self.ws / "voice_track.wav").exists() else None

            # 2. Effective BGM
            bgm_wav = VideoPlayerWidget._ensure_effective_bgm(self.ws)
            if not bgm_wav or not bgm_wav.exists():
                bgm_wav = (self.ws / "audio" / "bgm.wav") if (self.ws / "audio" / "bgm.wav").exists() else None

            # 3. Vocals
            vocals_wav = self.ws / "audio" / "vocals.wav"
            if not vocals_wav.exists():
                vocals_wav = self.ws / "audio" / "orig.wav"

            if vi_wav and vi_wav.exists():
                res["vi_raw"] = str(vi_wav.resolve())
                VideoPlayerWidget._ensure_boosted_track(vi_wav)
                if self.vi_voice_vol > 1.0:
                    boosted = vi_wav.parent / "voice_boosted_200.wav"
                    res["vi_voice"] = str(boosted.resolve()) if boosted.exists() else str(vi_wav.resolve())
                else:
                    res["vi_voice"] = str(vi_wav.resolve())

            if bgm_wav and bgm_wav.exists():
                res["bgm"] = str(bgm_wav.resolve())

            if vocals_wav and vocals_wav.exists():
                res["vocals"] = str(vocals_wav.resolve())

            if self.custom_bgm_path and Path(self.custom_bgm_path).exists():
                res["custom_bgm"] = self.custom_bgm_path

        except Exception:
            pass

        self.finished.emit(self.gen_id, res)


class VideoPlayerWidget(QWidget):
    """
    Video player widget with synchronized video and audio using QMediaPlayer.
    Supports seek, play/pause, time display, and emits timing signals.
    """
    position_changed = pyqtSignal(float)   # position in seconds
    duration_known = pyqtSignal(float)     # total duration in seconds
    subtitle_dragged = pyqtSignal(dict)    # {"position": str, "margin_v": int, "box_width_pct": float}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._video_path: Optional[str] = None
        self._duration: float = 0.0
        self._is_seeking = False
        self._show_overlay = True
        self._multi_track_active = False
        self._video_native_w: int = 1280
        self._video_native_h: int = 720
        self._audio_prep_worker: Optional[AudioPrepWorker] = None
        self._current_gen_id: int = 0

        self._setup_player()
        self._setup_ui()

    def _setup_player(self):
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)

        self._player.positionChanged.connect(self._on_player_pos_changed)
        self._player.durationChanged.connect(self._on_player_duration_changed)
        self._player.playbackStateChanged.connect(self._on_player_playback_state_changed)
        self._player.mediaStatusChanged.connect(self._on_player_media_status_changed)

        # 4 Audio Channels for Synchronized Multi-Track Preview
        # Track 1: Vietnamese Dubbing Voice
        self._vi_voice_player = QMediaPlayer(self)
        self._vi_voice_audio = QAudioOutput(self)
        self._vi_voice_player.setAudioOutput(self._vi_voice_audio)
        self._vi_voice_path: Optional[str] = None
        self._vi_voice_raw_path: Optional[str] = None
        self._vi_voice_vol: float = 1.0
        self._vi_voice_audio.setVolume(1.0)

        # Track 2: Original Separated BGM
        self._orig_bgm_player = QMediaPlayer(self)
        self._orig_bgm_audio = QAudioOutput(self)
        self._orig_bgm_player.setAudioOutput(self._orig_bgm_audio)
        self._orig_bgm_path: Optional[str] = None
        self._orig_bgm_vol: float = 0.8
        self._orig_bgm_audio.setVolume(0.8)

        # Track 3: Custom External BGM (loops)
        self._custom_bgm_player = QMediaPlayer(self)
        self._custom_bgm_player.setLoops(QMediaPlayer.Loops.Infinite)
        self._custom_bgm_audio = QAudioOutput(self)
        self._custom_bgm_player.setAudioOutput(self._custom_bgm_audio)
        self._custom_bgm_path: Optional[str] = None
        self._custom_bgm_vol: float = 0.5
        self._custom_bgm_audio.setVolume(0.5)

        # Track 4: Original Voice (Vocals)
        self._orig_voice_player = QMediaPlayer(self)
        self._orig_voice_audio = QAudioOutput(self)
        self._orig_voice_player.setAudioOutput(self._orig_voice_audio)
        self._orig_voice_path: Optional[str] = None
        self._orig_voice_vol: float = 0.0
        self._include_orig_voice: bool = False
        self._orig_voice_audio.setVolume(0.0)

        # Backward-compatible aliases
        self._bgm_player = self._custom_bgm_player
        self._bgm_audio = self._custom_bgm_audio
        self._bgm_path = self._custom_bgm_path
        self._bgm_volume = self._custom_bgm_vol

        # Aspect Ratio Canvas preview state
        self._canvas_aspect_enabled: bool = False
        self._canvas_aspect_ratio_str: str = "original"
        self._canvas_color: str = "#000000"
        self._canvas_bg_item = None

        # Dynamic Audio Device Routing (Bluetooth / Headphones / Speaker auto-sync)
        self._media_devices = QMediaDevices(self)
        self._media_devices.audioOutputsChanged.connect(self._sync_audio_device)
        self._sync_audio_device()

    def _sync_audio_device(self):
        """Ensure all audio outputs follow the current system default audio device (e.g. Bluetooth)."""
        def_dev = QMediaDevices.defaultAudioOutput()
        if def_dev.isNull():
            return
        for ao in (
            getattr(self, "_audio_output", None),
            getattr(self, "_vi_voice_audio", None),
            getattr(self, "_orig_bgm_audio", None),
            getattr(self, "_custom_bgm_audio", None),
            getattr(self, "_orig_voice_audio", None),
        ):
            if ao is not None:
                ao.setDevice(def_dev)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Video canvas viewport container using QGraphicsView for 100% reliable hardware compositing
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene, self)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self._view.setStyleSheet("background-color: #0c0d10; border-radius: 8px; border: 1px solid #21242c;")
        layout.addWidget(self._view, 1)

        # Canvas background item for aspect-ratio padding preview (9:16, 1:1, etc.)
        self._canvas_bg_item = self._scene.addRect(0, 0, 10, 10)
        self._canvas_bg_item.setZValue(-1)
        self._canvas_bg_item.hide()

        # Video Item inside Graphics Scene
        self._video_item = QGraphicsVideoItem()
        self._scene.addItem(self._video_item)
        self._player.setVideoOutput(self._video_item)

        # Real-time draggable & stretchable subtitle overlay placed as QGraphicsProxyWidget on top of video item
        self._sub_overlay = DraggableSubtitleOverlay()
        self._sub_overlay.dragged.connect(self._on_overlay_dragged)
        self._proxy = self._scene.addWidget(self._sub_overlay)
        self._proxy.setZValue(100)
        self._proxy.hide()
        self._overlay_style = {
            "font_name": "Arial",
            "font_size": 22,
            "primary_color": "#FFFFFF",
            "outline_color": "#000000",
            "outline_width": 2,
            "has_box": True,
            "box_color": "#000000",
            "box_opacity": 0.6,
            "position": "bottom",
            "margin_v": 35,
            "box_width_pct": 85,
            "text_align": "center",
        }
        self._overlay_text = "Xin chào! Đây là phụ đề mẫu tiếng Việt."

        # Set minimum size for video player so preview is clear and never collapsed
        self.setMinimumSize(420, 260)

        # Install resize listener on viewport
        self._container_filter = VideoContainerFilter(self)
        self._view.viewport().installEventFilter(self._container_filter)

        # Controls bar
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(4, 0, 4, 4)
        ctrl.setSpacing(6)

        self._play_btn = QPushButton()
        self._play_btn.setIcon(get_icon("play", "#9ca3af", "#38bdf8", 14))
        self._play_btn.setObjectName("icon_btn")
        self._play_btn.setFixedSize(32, 28)
        self._play_btn.clicked.connect(self.toggle_play)
        ctrl.addWidget(self._play_btn)

        self._time_label = QLabel("0:00.0 / 0:00.0")
        self._time_label.setObjectName("status_label")
        self._time_label.setFixedWidth(130)
        ctrl.addWidget(self._time_label)

        self._seek_bar = QSlider(Qt.Orientation.Horizontal)
        self._seek_bar.setRange(0, 1000)
        self._seek_bar.setValue(0)
        self._seek_bar.sliderMoved.connect(self._on_seek_drag)
        self._seek_bar.sliderReleased.connect(self._on_seek_released)
        ctrl.addWidget(self._seek_bar, 1)

        # Audio volume toggle
        self._vol_btn = QPushButton()
        self._vol_btn.setIcon(get_icon("zap", "#38bdf8", "#38bdf8", 14))
        self._vol_btn.setObjectName("icon_btn")
        self._vol_btn.setFixedSize(28, 28)
        self._vol_btn.setToolTip("Âm thanh: 100% (bấm để tắt/bật tiếng)")
        self._vol_btn.clicked.connect(self._toggle_mute)
        ctrl.addWidget(self._vol_btn)

        layout.addLayout(ctrl)

    def _toggle_mute(self):
        is_muted = self._vi_voice_audio.isMuted() if self._multi_track_active else self._audio_output.isMuted()
        new_state = not is_muted
        if not self._multi_track_active:
            self._audio_output.setMuted(new_state)
        else:
            self._audio_output.setMuted(True)
            self._vi_voice_audio.setMuted(new_state)
            self._orig_bgm_audio.setMuted(new_state)
            self._custom_bgm_audio.setMuted(new_state)
            self._orig_voice_audio.setMuted(new_state)
        if new_state:
            self._vol_btn.setIcon(get_icon("zap", "#ef4444", "#ef4444", 14))
            self._vol_btn.setToolTip("Đã tắt tiếng (bấm để bật)")
        else:
            self._vol_btn.setIcon(get_icon("zap", "#38bdf8", "#38bdf8", 14))
            self._vol_btn.setToolTip("Âm thanh: 100% (bấm để tắt tiếng)")

    def _on_container_resized(self):
        """Called whenever _view geometry changes."""
        cw = max(self._view.viewport().width(), 100)
        ch = max(self._view.viewport().height(), 100)
        self._scene.setSceneRect(0, 0, cw, ch)
        disp_x, disp_y, disp_w, disp_h, scale = self._get_active_video_rect()
        self._video_item.setPos(disp_x, disp_y)
        self._video_item.setSize(QSizeF(disp_w, disp_h))
        self._reposition_overlay()

    def load_video(self, path: str, target_pos: float = 0.0):
        self._video_path = path

        # Fast metadata resolution from probe.json without executing ffprobe
        p_json = Path(path).parent / "probe.json"
        if p_json.exists():
            try:
                import json
                pdata = json.loads(p_json.read_text(encoding="utf-8"))
                v_info = pdata.get("video", {})
                self._video_native_w = int(v_info.get("width") or 1280)
                self._video_native_h = int(v_info.get("height") or 720)
            except Exception:
                self._video_native_w = 1280
                self._video_native_h = 720
        else:
            # Probe native video resolution in background thread so Main GUI thread never blocks
            def _bg_probe():
                try:
                    from dubstudio.ffmpeg_utils import probe_file
                    info = probe_file(Path(path))
                    for s in info.get("streams", []):
                        if s.get("codec_type") == "video":
                            self._video_native_w = int(s.get("width") or 1280)
                            self._video_native_h = int(s.get("height") or 720)
                            break
                except Exception:
                    pass
            import threading
            threading.Thread(target=_bg_probe, daemon=True).start()

        # Always ensure audio is unmuted and at 100% volume for newly loaded video
        self._audio_output.setMuted(False)
        self._audio_output.setVolume(1.0)
        self._multi_track_active = False
        self._stop_all_audio_tracks()

        if target_pos > 0.0:
            target_ms = int(target_pos * 1000)
            def _restore_pos(status: QMediaPlayer.MediaStatus):
                if status == QMediaPlayer.MediaStatus.LoadedMedia:
                    try:
                        self._player.mediaStatusChanged.disconnect(_restore_pos)
                    except Exception:
                        pass
                    self._player.setPosition(target_ms)
            self._player.mediaStatusChanged.connect(_restore_pos)

        url = QUrl.fromLocalFile(str(Path(path).resolve()))
        self._player.setSource(url)
        self._play_btn.setIcon(get_icon("play", "#9ca3af", "#38bdf8", 14))
        self._play_btn.setText("")
        self._seek_bar.setValue(int(target_pos * 1000) if target_pos > 0 else 0)
        self._on_container_resized()


    @staticmethod
    def _ensure_voice_raw(ws: Optional[Path]) -> Optional[Path]:
        """Ensure raw isolated Vietnamese voice track exists without pre-baked background music."""
        if not ws or not ws.exists():
            return None
        raw_wav = ws / "voice_raw.wav"
        if raw_wav.exists() and raw_wav.stat().st_size > 44:
            try:
                import soundfile as sf
                raw_info = sf.info(str(raw_wav.resolve()))
                fit_plan_file = ws / "fit_plan.json"
                if fit_plan_file.exists():
                    import json
                    fp_data = json.loads(fit_plan_file.read_text(encoding="utf-8"))
                    max_plan_en = max([float(it.get("end", 0.0)) for it in fp_data], default=0.0)
                    if max_plan_en > 10.0 and raw_info.duration < (max_plan_en * 0.5):
                        # File voice_raw bị cụt (do lỗi tính duration cũ) -> buộc lắp ráp lại từ fit_plan
                        raw_wav = None
                    else:
                        return raw_wav
                else:
                    return raw_wav
            except Exception:
                return raw_wav

        # 1. Collect audio placement items from fit_plan.json or segments.json
        plan_items = []
        fit_plan = ws / "fit_plan.json"
        if fit_plan.exists():
            try:
                import json
                with open(fit_plan, "r", encoding="utf-8") as f:
                    plan = json.load(f)
                if isinstance(plan, list):
                    for item in plan:
                        w_rel = item.get("wav", "")
                        st = float(item.get("start", 0.0))
                        en = float(item.get("end", st + 1.0))
                        if w_rel and (ws / w_rel).exists():
                            plan_items.append({"start": st, "end": en, "wav": w_rel})
            except Exception:
                pass

        # 2. Fallback: Assemble directly from segments.json and tts/*.wav
        if not plan_items:
            seg_file = ws / "segments.json"
            if seg_file.exists():
                try:
                    import json
                    with open(seg_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    segs = data.get("segments", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    for s in segs:
                        st = float(s.get("voice_start") if s.get("voice_start") is not None else s.get("start", 0.0))
                        dur = float(s.get("tts_dur") or s.get("dur", 1.0))
                        en = st + dur
                        wav_rel = s.get("tts_file") or f"tts/{s.get('id', 0):04d}.wav"
                        if (ws / wav_rel).exists():
                            plan_items.append({"start": st, "end": en, "wav": wav_rel})
                except Exception:
                    pass

        # 3. Check for voice_track.wav as direct fallback
        if not plan_items:
            v_track = ws / "voice_track.wav"
            return v_track if v_track.exists() else None

        try:
            import numpy as np
            import soundfile as sf
            max_end = max(item.get("end", 0.0) for item in plan_items)
            sr = 48000
            total_samples = int(max_end * sr) + sr * 2
            track = np.zeros(total_samples, dtype=np.float32)
            has_any = False
            for i, item in enumerate(plan_items):
                wav_file = ws / item.get("wav", "")
                if not wav_file.exists():
                    continue
                data, file_sr = sf.read(str(wav_file.resolve()))
                if data.ndim > 1:
                    data = data.mean(axis=1)
                if file_sr != sr:
                    target_len = int(len(data) * sr / file_sr)
                    data = np.interp(
                        np.linspace(0, len(data), target_len, endpoint=False),
                        np.arange(len(data)),
                        data,
                    )
                # Anti-overlap enforcement ("chống đè giọng")
                st_sec = float(item.get("start", 0.0))
                if i + 1 < len(plan_items):
                    next_st_sec = float(plan_items[i + 1].get("start", st_sec + 1.0))
                    max_allowed_dur = max(0.1, next_st_sec - st_sec + 0.08)
                    curr_dur = len(data) / sr
                    if curr_dur > max_allowed_dur:
                        max_samples = int(max_allowed_dur * sr)
                        data = data[:max_samples]
                        fade_samples = min(int(0.05 * sr), len(data))
                        if fade_samples > 0:
                            data[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
                st_idx = int(st_sec * sr)
                en_idx = min(st_idx + len(data), total_samples)
                ch_len = en_idx - st_idx
                if ch_len > 0:
                    track[st_idx:en_idx] += data[:ch_len]
                    has_any = True

            if not has_any:
                v_track = ws / "voice_track.wav"
                return v_track if v_track.exists() else None

            max_val = np.max(np.abs(track))
            if max_val > 0.95:
                track = (track / max_val) * 0.95
            sf.write(str(raw_wav.resolve()), track, sr)
            return raw_wav
        except Exception:
            v_track = ws / "voice_track.wav"
            return v_track if v_track.exists() else None

    @staticmethod
    def _ensure_effective_bgm(ws: Optional[Path]) -> Optional[Path]:
        """Ensure effective BGM track exists by combining separated BGM with original audio passthrough."""
        if not ws or not ws.exists():
            return None
        orig_bgm = ws / "audio" / "bgm.wav"
        if not orig_bgm.exists():
            return None
        orig_ranges_file = ws / "orig_audio_ranges.json"
        ranges = []
        if orig_ranges_file.exists():
            try:
                import json
                r_data = json.loads(orig_ranges_file.read_text(encoding="utf-8"))
                for r in r_data:
                    if isinstance(r, dict):
                        st = float(r.get("start", 0.0))
                        en = float(r.get("end", 0.0))
                        if en > st:
                            ranges.append((st, en))
            except Exception:
                ranges = []

        if not ranges:
            return orig_bgm

        orig_wav = ws / "audio" / "orig.wav"
        if not orig_wav.exists():
            return orig_bgm

        effective_wav = ws / "bgm_effective.wav"
        if effective_wav.exists() and effective_wav.stat().st_size > 44:
            if effective_wav.stat().st_mtime >= orig_ranges_file.stat().st_mtime:
                return effective_wav

        try:
            import math
            import numpy as np
            import soundfile as sf
            from scipy.signal import resample_poly

            bgm_data, sr = sf.read(str(orig_bgm.resolve()))
            if bgm_data.ndim == 1:
                bgm_data = np.column_stack([bgm_data, bgm_data])
            total_samples = len(bgm_data)

            orig_data, o_sr = sf.read(str(orig_wav.resolve()))
            if o_sr != sr:
                g = math.gcd(int(sr), int(o_sr))
                up = int(sr) // g
                down = int(o_sr) // g
                orig_data = resample_poly(orig_data, up, down).astype(np.float32)
            if orig_data.ndim == 1:
                orig_data = np.column_stack([orig_data, orig_data])

            sorted_ranges = sorted(ranges, key=lambda x: x[0])
            merged = []
            for st, en in sorted_ranges:
                if not merged:
                    merged.append([st, en])
                else:
                    if st <= merged[-1][1]:
                        merged[-1][1] = max(merged[-1][1], en)
                    else:
                        merged.append([st, en])

            fade_len = int(0.15 * sr)
            orig_mask = np.zeros(total_samples, dtype=np.float32)
            for st, en in merged:
                i0 = int(st * sr)
                i1 = min(total_samples, int(en * sr))
                if i1 <= i0:
                    continue
                orig_mask[i0:i1] = 1.0
                fl = min(fade_len, (i1 - i0) // 2)
                if fl > 0:
                    x = np.linspace(0.0, 1.0, fl, dtype=np.float32)
                    curve_in = (0.5 * (1.0 - np.cos(np.pi * x))).astype(np.float32)
                    curve_out = (0.5 * (1.0 + np.cos(np.pi * x))).astype(np.float32)
                    orig_mask[i0:i0 + fl] = curve_in
                    orig_mask[i1 - fl:i1] = curve_out

            ducked_bgm = np.zeros((total_samples, 2), dtype=np.float32)
            p_len_b = min(len(bgm_data), total_samples)
            ducked_bgm[:p_len_b] = bgm_data[:p_len_b]
            ducked_bgm[:, 0] *= (1.0 - orig_mask)
            ducked_bgm[:, 1] *= (1.0 - orig_mask)

            passthrough = np.zeros((total_samples, 2), dtype=np.float32)
            p_len_o = min(len(orig_data), total_samples)
            passthrough[:p_len_o] = orig_data[:p_len_o]
            passthrough[:, 0] *= orig_mask
            passthrough[:, 1] *= orig_mask

            combined = ducked_bgm + passthrough
            sf.write(str(effective_wav.resolve()), combined, sr)
            return effective_wav
        except Exception:
            return orig_bgm

    def reload_bgm_track(self, workspace_dir: Optional[Path]):
        """Reload BGM track in-place when original audio ranges are modified."""
        ws = Path(workspace_dir) if workspace_dir else None
        bgm_wav = self._ensure_effective_bgm(ws) if ws else None
        if not bgm_wav or not bgm_wav.exists():
            bgm_wav = (ws / "audio" / "bgm.wav") if ws else None
        if bgm_wav and bgm_wav.exists():
            curr_pos = self._player.position()
            self._orig_bgm_path = str(bgm_wav.resolve())
            self._orig_bgm_player.setSource(QUrl.fromLocalFile(self._orig_bgm_path))
            self._orig_bgm_player.setPosition(curr_pos)
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._orig_bgm_player.play()

    def setup_job_audio(
        self,
        workspace_dir: Optional[Path],
        orig_bgm_vol: float = 0.8,
        custom_bgm_path: Optional[str] = None,
        custom_bgm_vol: float = 0.5,
        include_orig_voice: bool = False,
        orig_voice_vol: float = 0.0,
        vi_voice_vol: float = 1.0,
        is_rendered_video: bool = False,
    ):
        """Configure audio stems for synchronized multi-track playback asynchronously."""
        ws = Path(workspace_dir) if workspace_dir else None
        if not ws or not ws.exists() or is_rendered_video:
            self._multi_track_active = False
            self._audio_output.setMuted(False)
            self._audio_output.setVolume(1.0)
            self._stop_all_audio_tracks()
            return

        self._multi_track_active = True
        self._audio_output.setMuted(True)
        self._audio_output.setVolume(0.0)

        # Store volumes immediately
        self.set_vi_voice_volume(vi_voice_vol)
        self.set_orig_bgm_volume(orig_bgm_vol)
        self.set_custom_bgm(custom_bgm_path, custom_bgm_vol)
        self.set_orig_voice_volume(orig_voice_vol, include_orig_voice)

        # Fast path: Bind already existing cached files immediately in 0 ms
        fast_vi = (ws / "voice_raw.wav") if (ws / "voice_raw.wav").exists() else ((ws / "voice_track.wav") if (ws / "voice_track.wav").exists() else None)
        fast_bgm = (ws / "bgm_effective.wav") if (ws / "bgm_effective.wav").exists() else ((ws / "audio" / "bgm.wav") if (ws / "audio" / "bgm.wav").exists() else None)
        fast_voc = (ws / "audio" / "vocals.wav") if (ws / "audio" / "vocals.wav").exists() else ((ws / "audio" / "orig.wav") if (ws / "audio" / "orig.wav").exists() else None)

        if fast_vi:
            self._vi_voice_path = str(fast_vi.resolve())
            self._vi_voice_player.setSource(QUrl.fromLocalFile(self._vi_voice_path))
        if fast_bgm:
            self._orig_bgm_path = str(fast_bgm.resolve())
            self._orig_bgm_player.setSource(QUrl.fromLocalFile(self._orig_bgm_path))
        if fast_voc:
            self._orig_voice_path = str(fast_voc.resolve())
            self._orig_voice_player.setSource(QUrl.fromLocalFile(self._orig_voice_path))

        # Launch background prep worker with generation ID to assemble/boost tracks asynchronously
        self._current_gen_id += 1
        gen_id = self._current_gen_id

        if self._audio_prep_worker and self._audio_prep_worker.isRunning():
            try:
                self._audio_prep_worker.finished.disconnect()
            except Exception:
                pass

        worker = AudioPrepWorker(
            generation_id=gen_id,
            workspace_dir=ws,
            custom_bgm_path=custom_bgm_path,
            vi_voice_vol=vi_voice_vol,
            is_rendered_video=is_rendered_video,
        )
        worker.finished.connect(self._on_audio_prep_finished)
        self._audio_prep_worker = worker
        worker.start()

    def _on_audio_prep_finished(self, gen_id: int, res: dict):
        if gen_id != self._current_gen_id:
            # Stale generation from previous job, discard
            return

        if not res or not self._multi_track_active:
            return

        pos = self._player.position()
        is_playing = (self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)

        if "vi_voice" in res:
            target_vi = res["vi_voice"]
            if getattr(self, "_vi_voice_path", None) != target_vi:
                self._vi_voice_path = target_vi
                self._vi_voice_player.setSource(QUrl.fromLocalFile(target_vi))
                self._vi_voice_player.setPosition(pos)
                if is_playing:
                    self._vi_voice_player.play()

        if "bgm" in res:
            target_bgm = res["bgm"]
            if getattr(self, "_orig_bgm_path", None) != target_bgm:
                self._orig_bgm_path = target_bgm
                self._orig_bgm_player.setSource(QUrl.fromLocalFile(target_bgm))
                self._orig_bgm_player.setPosition(pos)
                if is_playing:
                    self._orig_bgm_player.play()

        if "vocals" in res:
            target_voc = res["vocals"]
            if getattr(self, "_orig_voice_path", None) != target_voc:
                self._orig_voice_path = target_voc
                self._orig_voice_player.setSource(QUrl.fromLocalFile(target_voc))
                self._orig_voice_player.setPosition(pos)
                if is_playing:
                    self._orig_voice_player.play()

    def load_audio_tracks(
        self,
        vi_voice_path: Optional[str | Path] = None,
        bgm_path: Optional[str | Path] = None,
        orig_voice_path: Optional[str | Path] = None,
    ):
        """Update live preview audio tracks without interrupting current video position."""
        curr_pos = self._player.position()
        if vi_voice_path and Path(vi_voice_path).exists():
            self._vi_voice_raw_path = str(Path(vi_voice_path).resolve())
            self._vi_voice_path = str(Path(vi_voice_path).resolve())
            self._vi_voice_player.setSource(QUrl.fromLocalFile(self._vi_voice_path))
            self._vi_voice_player.setPosition(curr_pos)
            self._multi_track_active = True
            self._audio_output.setMuted(True)
            self._audio_output.setVolume(0.0)
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._vi_voice_player.play()
        if bgm_path and Path(bgm_path).exists():
            self._orig_bgm_path = str(Path(bgm_path).resolve())
            self._orig_bgm_player.setSource(QUrl.fromLocalFile(self._orig_bgm_path))
            self._orig_bgm_player.setPosition(curr_pos)
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._orig_bgm_player.play()
        if orig_voice_path and Path(orig_voice_path).exists():
            self._orig_voice_path = str(Path(orig_voice_path).resolve())
            self._orig_voice_player.setSource(QUrl.fromLocalFile(self._orig_voice_path))
            self._orig_voice_player.setPosition(curr_pos)
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._orig_voice_player.play()
        self._apply_stem_volumes()

    @staticmethod
    def _ensure_boosted_track(raw_path: Optional[Path]) -> Optional[Path]:
        """Pre-generate or cache 200% (+10.5 dB RMS broadcast companded) audio track."""
        if not raw_path or not Path(raw_path).exists():
            return None
        raw_p = Path(raw_path).resolve()
        boosted = raw_p.parent / "voice_boosted_200.wav"
        if boosted.exists() and boosted.stat().st_mtime >= raw_p.stat().st_mtime and boosted.stat().st_size > 44:
            return boosted
        try:
            import subprocess
            from dubstudio.paths import resolve_tool
            from dubstudio.packaging import get_subprocess_kwargs, get_subprocess_env
            ffmpeg_exe = resolve_tool("ffmpeg")
            cmd = [
                ffmpeg_exe, "-y",
                "-i", str(raw_p),
                "-filter:a", "compand=attacks=0.01:decays=0.1:points=-90/-90|-40/-25|-20/-6|0/0:gain=10,alimiter=limit=0.98:attack=5:release=50",
                str(boosted.resolve()),
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=get_subprocess_env(),
                **get_subprocess_kwargs(),
            )
            if res.returncode == 0 and boosted.exists():
                return boosted
        except Exception:
            pass
        return raw_p

    def _switch_vi_voice_source(self, target_path: str):
        """Seamlessly switch vi_voice_player source without dropping position or playback."""
        if getattr(self, "_vi_voice_path", None) == target_path:
            return
        pos = self._player.position()
        was_playing = (self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        self._vi_voice_path = target_path

        def _on_loaded(status: QMediaPlayer.MediaStatus):
            if status == QMediaPlayer.MediaStatus.LoadedMedia:
                try:
                    self._vi_voice_player.mediaStatusChanged.disconnect(_on_loaded)
                except Exception:
                    pass
                self._vi_voice_player.setPosition(pos)
                if was_playing:
                    self._vi_voice_player.play()

        self._vi_voice_player.mediaStatusChanged.connect(_on_loaded)
        self._vi_voice_player.setSource(QUrl.fromLocalFile(target_path))

    def _apply_stem_volumes(self):
        """
        Apply stem volumes across all 4 independent audio tracks.
        For vi_voice:
        - <= 100%: uses raw audio with linear scaling [0.0, 1.0].
        - > 100%: uses broadcast companded audio (+10.5 dB boost) with progressive volume curve.
        """
        vi_vol = getattr(self, "_vi_voice_vol", 1.0)
        bgm_vol = getattr(self, "_orig_bgm_vol", 0.8)
        custom_vol = getattr(self, "_custom_bgm_vol", 0.5)
        include_orig = getattr(self, "_include_orig_voice", False)
        orig_voice_vol = getattr(self, "_orig_voice_vol", 0.0) if include_orig else 0.0

        if vi_vol > 1.0:
            eff_vi = max(0.0, min(1.0, 0.35 + 0.65 * (vi_vol - 1.0)))
        else:
            eff_vi = max(0.0, min(1.0, vi_vol))

        eff_bgm = max(0.0, min(1.0, bgm_vol))
        eff_custom = max(0.0, min(1.0, custom_vol))
        eff_orig_voice = max(0.0, min(1.0, orig_voice_vol))

        self._vi_voice_audio.setVolume(eff_vi)
        self._vi_voice_audio.setMuted(eff_vi <= 0.001)

        self._orig_bgm_audio.setVolume(eff_bgm)
        self._orig_bgm_audio.setMuted(eff_bgm <= 0.001)

        self._custom_bgm_audio.setVolume(eff_custom)
        self._custom_bgm_audio.setMuted(eff_custom <= 0.001 or not self._custom_bgm_path)

        self._orig_voice_audio.setVolume(eff_orig_voice)
        self._orig_voice_audio.setMuted(eff_orig_voice <= 0.001 or not include_orig)

    def set_vi_voice_volume(self, volume: float):
        """Live adjust Vietnamese voice dubbing volume (supports 0.0 to 2.0 / up to 200%)."""
        self._vi_voice_vol = max(0.0, min(2.0, float(volume)))
        raw_path = getattr(self, "_vi_voice_raw_path", None)

        if raw_path and Path(raw_path).exists():
            if self._vi_voice_vol > 1.0:
                boosted = self._ensure_boosted_track(Path(raw_path))
                if boosted and boosted.exists():
                    self._switch_vi_voice_source(str(boosted.resolve()))
            else:
                self._switch_vi_voice_source(str(Path(raw_path).resolve()))

        self._apply_stem_volumes()

    def set_orig_bgm_volume(self, volume: float):
        """Live adjust original video background music volume."""
        self._orig_bgm_vol = max(0.0, min(1.0, float(volume)))
        self._apply_stem_volumes()

    def set_custom_bgm(self, audio_path: Optional[str], volume: float = 0.5):
        """Set custom background music file and update live preview volume immediately."""
        self._custom_bgm_vol = max(0.0, min(1.0, float(volume)))
        self._bgm_volume = self._custom_bgm_vol
        if audio_path and Path(audio_path).exists():
            self._custom_bgm_path = str(Path(audio_path).resolve())
            self._bgm_path = self._custom_bgm_path
            self._custom_bgm_player.setSource(QUrl.fromLocalFile(self._custom_bgm_path))
            self._multi_track_active = True
            self._audio_output.setMuted(True)
            self._audio_output.setVolume(0.0)
            curr_pos = self._player.position()
            self._custom_bgm_player.setPosition(curr_pos)
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._custom_bgm_player.play()
            else:
                self._custom_bgm_player.pause()
        else:
            self._custom_bgm_path = None
            self._bgm_path = None
            self._custom_bgm_player.stop()
            self._custom_bgm_player.setSource(QUrl())
        self._apply_stem_volumes()

    def set_custom_bgm_volume(self, volume: float):
        """Live adjust custom BGM preview volume without restarting playback."""
        self._custom_bgm_vol = max(0.0, min(1.0, float(volume)))
        self._bgm_volume = self._custom_bgm_vol
        self._apply_stem_volumes()

    def set_bgm_volume(self, volume: float):
        """Alias for set_orig_bgm_volume or set_custom_bgm_volume."""
        if self._custom_bgm_path:
            self.set_custom_bgm_volume(volume)
        else:
            self.set_orig_bgm_volume(volume)

    def set_orig_voice_volume(self, volume: float, include: bool = True):
        """Live adjust original voice volume and inclusion toggle."""
        self._include_orig_voice = include
        self._orig_voice_vol = max(0.0, min(1.0, float(volume)))
        self._apply_stem_volumes()

    def _stop_all_audio_tracks(self):
        for p in (self._vi_voice_player, self._orig_bgm_player, self._custom_bgm_player, self._orig_voice_player):
            p.stop()
            p.setSource(QUrl())
        self._vi_voice_path = None
        self._vi_voice_raw_path = None
        self._orig_bgm_path = None
        self._custom_bgm_path = None
        self._orig_voice_path = None

    def set_overlay_preview_visible(self, visible: bool):
        """Toggle showing the sample subtitle preview overlay box."""
        self._show_overlay = bool(visible)
        if not self._show_overlay:
            self._sub_overlay.hide()
            if hasattr(self, "_proxy") and self._proxy:
                self._proxy.hide()
        else:
            self._sub_overlay.show()
            if hasattr(self, "_proxy") and self._proxy:
                self._proxy.show()
            self._reposition_overlay()

    def unload(self):
        """Stop player and release file source to unlock file on Windows."""
        self.pause()
        self._player.setSource(QUrl())
        self._stop_all_audio_tracks()
        self._video_path = None
        self._duration = 0.0
        self._time_label.setText("0:00.0 / 0:00.0")
        self._seek_bar.setValue(0)

    def get_position(self) -> float:
        """Return current playback position in seconds."""
        if hasattr(self, "_player") and self._player:
            return round(self._player.position() / 1000.0, 3)
        return 0.0

    def seek(self, t: float):
        if self._player.duration() > 0:
            ms = int(max(0.0, t) * 1000)
            self._player.setPosition(ms)
            if self._vi_voice_path: self._vi_voice_player.setPosition(ms)
            if self._orig_bgm_path: self._orig_bgm_player.setPosition(ms)
            if self._custom_bgm_path: self._custom_bgm_player.setPosition(ms)
            if self._orig_voice_path: self._orig_voice_player.setPosition(ms)

    def toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def play(self):
        if self._video_path:
            pos = self._player.position()
            if not self._multi_track_active:
                self._audio_output.setMuted(False)
                if self._audio_output.volume() < 0.05:
                    self._audio_output.setVolume(1.0)
            else:
                self._audio_output.setMuted(True)
                self._audio_output.setVolume(0.0)
                self._apply_stem_volumes()
            self._player.play()
            self._play_btn.setIcon(get_icon("pause", "#38bdf8", "#38bdf8", 14))
            if self._multi_track_active:
                for p, p_path in [
                    (self._vi_voice_player, self._vi_voice_path),
                    (self._orig_bgm_player, self._orig_bgm_path),
                    (self._custom_bgm_player, self._custom_bgm_path),
                    (self._orig_voice_player, self._orig_voice_path),
                ]:
                    if p_path:
                        p.setPosition(pos)
                        p.play()

    def pause(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play_btn.setIcon(get_icon("play", "#9ca3af", "#38bdf8", 14))
        for p in (self._vi_voice_player, self._orig_bgm_player, self._custom_bgm_player, self._orig_voice_player):
            if p.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                p.pause()

    def _on_player_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        """Keep all audio stems in sync with main player state transitions."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setIcon(get_icon("pause", "#38bdf8", "#38bdf8", 14))
            pos = self._player.position()
            if self._multi_track_active:
                for p, p_path in [
                    (self._vi_voice_player, self._vi_voice_path),
                    (self._orig_bgm_player, self._orig_bgm_path),
                    (self._custom_bgm_player, self._custom_bgm_path),
                    (self._orig_voice_player, self._orig_voice_path),
                ]:
                    if p_path:
                        if abs(p.position() - pos) > 200:
                            p.setPosition(pos)
                        if p.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                            p.play()
        else:
            self._play_btn.setIcon(get_icon("play", "#9ca3af", "#38bdf8", 14))
            for p in (self._vi_voice_player, self._orig_bgm_player, self._custom_bgm_player, self._orig_voice_player):
                if p.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    p.pause()

    def _on_player_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        """Automatically pause and rewind all audio tracks when video reaches end."""
        if status in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.NoMedia):
            for p in (self._vi_voice_player, self._orig_bgm_player, self._custom_bgm_player, self._orig_voice_player):
                p.pause()
                p.setPosition(0)

    def _on_player_pos_changed(self, pos_ms: int):
        sec = pos_ms / 1000.0
        if not self._is_seeking and self._duration > 0:
            val = int((sec / self._duration) * 1000)
            self._seek_bar.blockSignals(True)
            self._seek_bar.setValue(val)
            self._seek_bar.blockSignals(False)
        self._time_label.setText(f"{_fmt(sec)} / {_fmt(self._duration)}")
        self.position_changed.emit(sec)

        # Re-synchronize audio channels if drifting > 300ms
        if self._multi_track_active and self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            for p, p_path in [
                (self._vi_voice_player, self._vi_voice_path),
                (self._orig_bgm_player, self._orig_bgm_path),
                (self._custom_bgm_player, self._custom_bgm_path),
                (self._orig_voice_player, self._orig_voice_path),
            ]:
                if p_path and abs(p.position() - pos_ms) > 300:
                    p.setPosition(pos_ms)

    def _on_player_duration_changed(self, dur_ms: int):
        self._duration = dur_ms / 1000.0
        self._time_label.setText(f"{_fmt(0)} / {_fmt(self._duration)}")
        self.duration_known.emit(self._duration)

    def _on_seek_drag(self, val: int):
        self._is_seeking = True
        if self._duration > 0:
            sec = (val / 1000.0) * self._duration
            self._time_label.setText(f"{_fmt(sec)} / {_fmt(self._duration)}")

    def _on_seek_released(self):
        if self._duration > 0:
            val = self._seek_bar.value()
            sec = (val / 1000.0) * self._duration
            self.seek(sec)
        self._is_seeking = False

    def set_overlay_draggable(self, draggable: bool):
        """Enable or disable dragging the subtitle overlay with mouse."""
        self._sub_overlay.set_draggable(draggable)

    def set_canvas_aspect_ratio(self, ratio_str: str, canvas_color: str = "#000000", enabled: bool = True):
        """Set live aspect ratio padding preview (e.g. '9:16', '1:1', '16:9')."""
        self._canvas_aspect_enabled = bool(enabled and ratio_str != "original")
        self._canvas_aspect_ratio_str = ratio_str or "original"
        self._canvas_color = canvas_color or "#000000"
        self._on_container_resized()

    def _get_active_video_rect(self) -> tuple[float, float, float, float, float]:
        """Compute the exact visible display rectangle of the video inside the view."""
        cw = max(self._view.viewport().width(), 100)
        ch = max(self._view.viewport().height(), 100)
        vw = getattr(self, "_video_native_w", 1280) or 1280
        vh = getattr(self, "_video_native_h", 720) or 720

        aspect_c = cw / ch
        aspect_v = vw / vh

        if getattr(self, "_canvas_aspect_enabled", False) and self._canvas_aspect_ratio_str != "original":
            r_str = self._canvas_aspect_ratio_str
            target_ratio = 1.0
            if ":" in r_str:
                parts = r_str.split(":")
                try:
                    target_ratio = float(parts[0]) / float(parts[1])
                except Exception:
                    target_ratio = 1.0
            elif "/" in r_str:
                parts = r_str.split("/")
                try:
                    target_ratio = float(parts[0]) / float(parts[1])
                except Exception:
                    target_ratio = 1.0

            if aspect_v > target_ratio:
                # Video is wider than canvas -> pad top and bottom
                canvas_vw = float(vw)
                canvas_vh = float(vw) / target_ratio
            else:
                # Video is taller than canvas -> pad left and right
                canvas_vh = float(vh)
                canvas_vw = float(vh) * target_ratio

            # Fit canvas inside container (cw, ch)
            if aspect_c > target_ratio:
                # Container is wider than canvas (pillarbox)
                canvas_disp_h = float(ch)
                canvas_disp_w = ch * target_ratio
                canvas_disp_x = (cw - canvas_disp_w) / 2.0
                canvas_disp_y = 0.0
                scale = canvas_disp_h / canvas_vh
            else:
                # Container is taller than canvas (letterbox)
                canvas_disp_w = float(cw)
                canvas_disp_h = cw / target_ratio
                canvas_disp_x = 0.0
                canvas_disp_y = (ch - canvas_disp_h) / 2.0
                scale = canvas_disp_w / canvas_vw

            disp_w = vw * scale
            disp_h = vh * scale
            disp_x = canvas_disp_x + (canvas_disp_w - disp_w) / 2.0
            disp_y = canvas_disp_y + (canvas_disp_h - disp_h) / 2.0

            if hasattr(self, "_canvas_bg_item") and self._canvas_bg_item:
                self._canvas_bg_item.setRect(canvas_disp_x, canvas_disp_y, canvas_disp_w, canvas_disp_h)
                c = QColor(getattr(self, "_canvas_color", "#000000"))
                if not c.isValid():
                    c = QColor(0, 0, 0)
                self._canvas_bg_item.setBrush(QBrush(c))
                self._canvas_bg_item.setPen(QPen(QColor("#38bdf8"), 1.5, Qt.PenStyle.DashLine))
                self._canvas_bg_item.show()

            return disp_x, disp_y, disp_w, disp_h, max(scale, 0.01)

        # Normal standard video rect
        if hasattr(self, "_canvas_bg_item") and self._canvas_bg_item:
            self._canvas_bg_item.hide()

        if aspect_c > aspect_v:
            # Pillarboxed (black bars left and right, e.g. vertical 9:16 video on wide container)
            disp_h = float(ch)
            disp_w = ch * aspect_v
            disp_x = (cw - disp_w) / 2.0
            disp_y = 0.0
            scale = disp_h / float(vh)
        else:
            # Letterboxed (black bars top and bottom)
            disp_w = float(cw)
            disp_h = cw / aspect_v
            disp_x = 0.0
            disp_y = (ch - disp_h) / 2.0
            scale = disp_w / float(vw)

        return disp_x, disp_y, disp_w, disp_h, max(scale, 0.01)

    def _on_overlay_dragged(self, data: dict):
        """Handle both moving and resizing of the subtitle bounding box."""
        disp_x, disp_y, disp_w, disp_h, scale = self._get_active_video_rect()
        native_h = getattr(self, "_video_native_h", 720) or 720
        total_scale = disp_h / 720.0
        action = data.get("action", "move")

        if action == "resize":
            w_screen = float(data.get("width", 100))
            box_width_pct = max(30.0, min(95.0, round((w_screen / disp_w) * 100.0, 1)))
            if self._overlay_style is not None:
                self._overlay_style["box_width_pct"] = box_width_pct
            self._reposition_overlay()
            self.subtitle_dragged.emit({
                "position": (self._overlay_style or {}).get("position", "bottom"),
                "margin_v": (self._overlay_style or {}).get("margin_v", 35),
                "box_width_pct": box_width_pct,
            })
            return

        # Action: Move
        fallback_y = self._proxy.pos().y() if hasattr(self, "_proxy") and self._proxy else self._sub_overlay.y()
        cur_y = float(data.get("scene_y", fallback_y))
        box_h = float(data.get("box_h", self._sub_overlay.height()))

        # Calculate continuous position percentage relative to video frame
        pos_y_pct = max(0.0, min(100.0, round(((cur_y - disp_y) / float(disp_h)) * 100.0, 2)))
        self._pinned_pos_ratio = max(0.0, min(1.0, (cur_y - disp_y) / float(disp_h)))

        if self._overlay_style is not None:
            self._overlay_style["pos_y_pct"] = pos_y_pct

        self.subtitle_dragged.emit({
            "pos_y_pct": pos_y_pct,
            "box_width_pct": (self._overlay_style or {}).get("box_width_pct", 85),
        })

    def update_subtitle_overlay(self, text: str, style: dict, visible: bool = True):
        """Update live subtitle preview directly on top of the video canvas with 1:1 WYSIWYG matching."""
        self._overlay_text = text or "Xin chào! Đây là phụ đề mẫu tiếng Việt."
        self._overlay_style = dict(style or {})

        if not getattr(self, "_show_overlay", True) or not visible:
            self._sub_overlay.hide()
            if hasattr(self, "_proxy") and self._proxy:
                self._proxy.hide()
            return

        self._sub_overlay.show()
        if hasattr(self, "_proxy") and self._proxy:
            self._proxy.show()
        self._reposition_overlay()

    def _reposition_overlay(self):
        """Position and stretch overlay strictly within the visible video rectangle, scaled 1:1 with exported video."""
        if not hasattr(self, "_sub_overlay") or not self._sub_overlay.isVisible():
            return

        disp_x, disp_y, disp_w, disp_h, scale = self._get_active_video_rect()
        native_w = getattr(self, "_video_native_w", 1280) or 1280
        native_h = getattr(self, "_video_native_h", 720) or 720

        # Video resolution scale relative to reference 720p height (identical to ass.py)
        ref_h = 720.0
        video_scale = max(native_h, 360) / ref_h

        # Scale factor from native video coordinate to screen display coordinate
        disp_scale = disp_h / float(native_h)
        total_scale = video_scale * disp_scale

        # Font pixel size strictly 1:1 with exported video (ass_font_size * disp_scale)
        font_size_setting = float((self._overlay_style or {}).get("font_size", 24) or 24)
        native_font_size = max(12, int(round(font_size_setting * video_scale)))
        scaled_font_px = max(10, int(round(native_font_size * disp_scale)))

        font_name = (self._overlay_style or {}).get("font_name", "Arial")
        font = QFont(font_name)
        font.setPixelSize(scaled_font_px)
        font.setBold(True)
        fm = QFontMetrics(font)

        # Bounding box width constrained by box_width_pct (default 85%)
        box_width_pct = float((self._overlay_style or {}).get("box_width_pct", 85) or 85)
        native_box_w = max(80, min(int(round(native_w * (box_width_pct / 100.0))), native_w))
        w = max(40, int(round(native_box_w * disp_scale)))

        text_align = (self._overlay_style or {}).get("text_align", "center")
        align_flag = Qt.AlignmentFlag.AlignCenter
        if text_align == "left":
            align_flag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        elif text_align == "right":
            align_flag = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        flags = align_flag | Qt.TextFlag.TextWordWrap

        # Compute needed height based on word-wrapped text and adjustable padding
        pad_x_setting = float((self._overlay_style or {}).get("box_padding_x", 14) or 14)
        pad_y_setting = float((self._overlay_style or {}).get("box_padding_y", 8) or 8)
        native_pad_x = max(4, int(round(pad_x_setting * video_scale)))
        native_pad_y = max(2, int(round(pad_y_setting * video_scale)))
        pad_x = max(2, int(round(native_pad_x * disp_scale)))
        pad_y = max(1, int(round(native_pad_y * disp_scale)))

        text_rect_needed = fm.boundingRect(QRect(0, 0, max(40, w - pad_x * 2), 2000), flags, self._overlay_text)
        h = max(int(round(20 * total_scale)), text_rect_needed.height() + pad_y * 2)

        # Align horizontally within active video frame
        if text_align == "left":
            x = int(disp_x + 10 * total_scale)
        elif text_align == "right":
            x = int(disp_x + disp_w - w - 10 * total_scale)
        else:
            x = int(disp_x + (disp_w - w) / 2.0)

        # Vertical position relative to active video frame
        if (self._overlay_style or {}).get("pos_y_pct") is not None:
            pct = float(self._overlay_style["pos_y_pct"])
            y = int(round(disp_y + (pct / 100.0) * disp_h))
            y = max(int(disp_y), min(int(disp_y + disp_h - h), y))
        elif getattr(self, "_pinned_pos_ratio", None) is not None:
            y = int(round(disp_y + self._pinned_pos_ratio * disp_h))
            y = max(int(disp_y), min(int(disp_y + disp_h - h), y))
        else:
            pos = (self._overlay_style or {}).get("position", "bottom")
            margin_v_setting = float((self._overlay_style or {}).get("margin_v", 35) or 35)
            scaled_margin_v = max(2, int(round(margin_v_setting * total_scale)))
            if pos == "top":
                y = int(disp_y + scaled_margin_v)
            elif pos == "center":
                y = int(disp_y + (disp_h - h) / 2.0)
            else:  # bottom
                y = int(disp_y + disp_h - h - scaled_margin_v)

        # Update overlay styling & dimensions
        if self._sub_overlay.width() != w or self._sub_overlay.height() != h:
            self._sub_overlay.setFixedSize(w, h)
        self._sub_overlay.set_text_and_style(self._overlay_text, self._overlay_style, scaled_font_px, total_scale)

        if hasattr(self, "_proxy") and self._proxy:
            cur_pos = self._proxy.pos()
            # Only update proxy coordinates if actually shifted to avoid unnecessary UI jitter
            if abs(cur_pos.x() - x) >= 1.0 or abs(cur_pos.y() - y) >= 1.0:
                self._proxy.setPos(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._on_container_resized()


def _fmt(t: float) -> str:
    mins = int(t) // 60
    secs = t - mins * 60
    return f"{mins}:{secs:04.1f}"
