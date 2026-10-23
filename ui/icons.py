"""Custom vector icon generator for DubStudio using clean SVG paths.

Provides crisp, modern line icons (similar to Lucide / Feather icons)
without relying on system emojis or external icon fonts.
"""
from __future__ import annotations

from typing import Dict
from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

# SVG Icon templates (24x24 viewBox, stroke-width=2, stroke-linecap=round)
_SVG_PATHS: Dict[str, str] = {
    # Antigravity-style sparkle / brand logo
    "brand": (
        '<path d="M12 2L14.8 9.2L22 12L14.8 14.8L12 22L9.2 14.8L2 12L9.2 9.2Z" '
        'fill="{color}" stroke="{color}" stroke-width="1.5"/>'
    ),
    # Projects / folders
    "folder": (
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Microphone (Studio / Dubbing)
    "mic": (
        '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M19 10v2a7 7 0 0 1-14 0v-2" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="12" y1="19" x2="12" y2="23" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="8" y1="23" x2="16" y2="23" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    ),
    # Subtitles / Captions (Text overlay)
    "subtitles": (
        '<rect x="2" y="4" width="20" height="16" rx="2" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M7 15h4M15 15h2M7 11h2M13 11h4" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    ),
    # Download from web
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="7 10 12 15 17 10" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="12" y1="15" x2="12" y2="3" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    ),
    # Merge / Link video clips
    "link": (
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Sliders / Video Editor controls
    "sliders": (
        '<line x1="4" y1="21" x2="4" y2="14" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="4" y1="10" x2="4" y2="3" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="12" y1="21" x2="12" y2="12" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="12" y1="8" x2="12" y2="3" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="20" y1="21" x2="20" y2="16" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="20" y1="12" x2="20" y2="3" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="1" y1="14" x2="7" y2="14" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="9" y1="8" x2="15" y2="8" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="17" y1="16" x2="23" y2="16" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Settings / Gear
    "settings": (
        '<circle cx="12" cy="12" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Plus (+ create)
    "plus": (
        '<line x1="12" y1="5" x2="12" y2="19" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>'
        '<line x1="5" y1="12" x2="19" y2="12" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>'
    ),
    # Refresh / Reload
    "refresh": (
        '<polyline points="23 4 23 10 17 10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="1 20 1 14 7 14" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Trash / Delete
    "trash": (
        '<polyline points="3 6 5 6 21 6" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="10" y1="11" x2="10" y2="17" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="14" y1="11" x2="14" y2="17" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    ),
    # Film / Video Editor
    "film": (
        '<rect x="2" y="2" width="20" height="20" rx="2.2" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="7" y1="2" x2="7" y2="22" stroke="{color}" stroke-width="2"/>'
        '<line x1="17" y1="2" x2="17" y2="22" stroke="{color}" stroke-width="2"/>'
        '<line x1="2" y1="12" x2="22" y2="12" stroke="{color}" stroke-width="2"/>'
        '<line x1="2" y1="7" x2="7" y2="7" stroke="{color}" stroke-width="2"/>'
        '<line x1="2" y1="17" x2="7" y2="17" stroke="{color}" stroke-width="2"/>'
        '<line x1="17" y1="17" x2="22" y2="17" stroke="{color}" stroke-width="2"/>'
        '<line x1="17" y1="7" x2="22" y2="7" stroke="{color}" stroke-width="2"/>'
    ),
    # Play
    "play": (
        '<polygon points="6 4 20 12 6 20 6 4" fill="{color}" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>'
    ),
    # Pause
    "pause": (
        '<rect x="6" y="4" width="4" height="16" rx="1" fill="{color}"/>'
        '<rect x="14" y="4" width="4" height="16" rx="1" fill="{color}"/>'
    ),
    # Zap / AI Generation
    "zap": (
        '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" '
        'fill="{color}" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>'
    ),
    # Arrow Right (Transition)
    "arrow_right": (
        '<line x1="5" y1="12" x2="19" y2="12" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<polyline points="12 5 19 12 12 19" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Eye (Visibility toggle)
    "eye": (
        '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="12" cy="12" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
    ),
    # Speaker / Volume (Audio preview)
    "volume": (
        '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" '
        'fill="{color}" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>'
        '<path d="M15.54 8.46a5 5 0 0 1 0 7.07" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M19.07 4.93a10 10 0 0 1 0 14.14" '
        'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    ),
    # Check / Success
    "check": (
        '<polyline points="20 6 9 17 4 12" '
        'fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Scissors / Split segment
    "scissors": (
        '<circle cx="6" cy="6" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<circle cx="6" cy="18" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<line x1="20" y1="4" x2="8.12" y2="15.88" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="14.47" y1="14.48" x2="20" y2="20" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="8.12" y1="8.12" x2="12" y2="12" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    ),
    # Merge / Combine segments
    "combine": (
        '<circle cx="18" cy="18" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<circle cx="6" cy="6" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<circle cx="6" cy="18" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<path d="M6 9v6" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M9 6h4a5 5 0 0 1 5 5v4" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    ),
    # Search / Find
    "search": (
        '<circle cx="11" cy="11" r="8" fill="none" stroke="{color}" stroke-width="2"/>'
        '<line x1="21" y1="21" x2="16.65" y2="16.65" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    ),
    # Edit / Rename / Pen
    "edit": (
        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Close / Remove
    "close": (
        '<line x1="18" y1="6" x2="6" y2="18" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>'
        '<line x1="6" y1="6" x2="18" y2="18" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>'
    ),
    # Palette / Color picker
    "palette": (
        '<circle cx="13.5" cy="6.5" r="1" fill="{color}"/>'
        '<circle cx="17.5" cy="10.5" r="1" fill="{color}"/>'
        '<circle cx="8.5" cy="7.5" r="1" fill="{color}"/>'
        '<circle cx="6.5" cy="12.5" r="1" fill="{color}"/>'
        '<path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.563-2.512 5.563-5.563C22 6.5 17.5 2 12 2z" fill="none" stroke="{color}" stroke-width="1.8"/>'
    ),
    # Arrow Up
    "arrow_up": (
        '<line x1="12" y1="19" x2="12" y2="5" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>'
        '<polyline points="5 12 12 5 19 12" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Arrow Down
    "arrow_down": (
        '<line x1="12" y1="5" x2="12" y2="19" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>'
        '<polyline points="19 12 12 19 5 12" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Music / Audio track
    "music": (
        '<path d="M9 18V5l12-2v13" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="6" cy="18" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<circle cx="18" cy="16" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
    ),
    # Spinner / Loading
    "spinner": (
        '<path d="M21 12a9 9 0 1 1-6.219-8.56" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
    ),
    # Clock / Duration
    "clock": (
        '<circle cx="12" cy="12" r="10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="12 6 12 12 16 14" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Type / Font typography
    "type": (
        '<polyline points="4 7 4 4 20 4 20 7" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="12" y1="4" x2="12" y2="20" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Rotate-CCW / Reset
    "rotate-ccw": (
        '<path d="M1 4v6h6" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Layers / Overlays
    "layers": (
        '<polygon points="12 2 2 7 12 12 22 7 12 2" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="2 17 12 22 22 17" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="2 12 12 17 22 12" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Info / Guide
    "info": (
        '<circle cx="12" cy="12" r="10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="12" y1="16" x2="12" y2="12" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<circle cx="12" cy="8" r="1" fill="{color}"/>'
    ),
    # Chevrons for navigation
    "chevron-left": (
        '<polyline points="15 18 9 12 15 6" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "chevron_left": (
        '<polyline points="15 18 9 12 15 6" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "chevron-right": (
        '<polyline points="9 18 15 12 9 6" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "chevron_right": (
        '<polyline points="9 18 15 12 9 6" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Cut / Scissors alias
    "cut": (
        '<circle cx="6" cy="6" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<circle cx="6" cy="18" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<line x1="20" y1="4" x2="8.12" y2="15.88" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="14.47" y1="14.48" x2="20" y2="20" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="8.12" y1="8.12" x2="12" y2="12" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    ),
    # Copy to clipboard
    "copy": (
        '<rect x="9" y="9" width="13" height="13" rx="2" ry="2" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Globe / Web browser
    "globe": (
        '<circle cx="12" cy="12" r="10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="2" y1="12" x2="22" y2="12" stroke="{color}" stroke-width="2"/>'
        '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" fill="none" stroke="{color}" stroke-width="2"/>'
    ),
}


def _render_pixmap(name: str, color: str, size: int) -> QPixmap:
    """Render a single colored pixmap from the SVG template."""
    body = _SVG_PATHS.get(name)
    if not body:
        # Fallback empty transparent pixmap
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        return pm

    inner = body.format(color=color)
    svg_str = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24">{inner}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))

    # Render at 2x resolution for crisp high-DPI scaling
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()

    # Scale back smoothly
    return pm.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def get_icon(
    name: str,
    color: str = "#9ca3af",
    active_color: str = "#38bdf8",
    size: int = 18,
) -> QIcon:
    """
    Get a QIcon with custom colors for normal and active/selected states.
    
    Args:
        name: Icon name from _SVG_PATHS (e.g. 'folder', 'mic', 'settings', 'plus')
        color: Normal state color (hex)
        active_color: Active/Checked state color (hex)
        size: Icon bounding box size in pixels
    """
    icon = QIcon()

    # Normal state pixmap
    pm_normal = _render_pixmap(name, color, size)
    icon.addPixmap(pm_normal, QIcon.Mode.Normal, QIcon.State.Off)

    # Active/Checked state pixmap
    pm_active = _render_pixmap(name, active_color, size)
    icon.addPixmap(pm_active, QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(pm_active, QIcon.Mode.Selected, QIcon.State.On)

    return icon


def get_pixmap(name: str, color: str = "#9ca3af", size: int = 18) -> QPixmap:
    """Get a QPixmap directly (useful for QLabel or custom painting)."""
    return _render_pixmap(name, color, size)


def clean_icon_text(text: str) -> str:
    """
    Strip any Unicode emoji characters and duplicate spaces from string
    so button/label text stays purely text-based without double icons.
    """
    import re
    if not text:
        return ""
    cleaned = re.sub(
        r'[\U00010000-\U0010ffff]|[\u25a0-\u25ff]|[\u2600-\u26ff]|[\u2700-\u27bf]|[\u2300-\u23ff]|[\u2b00-\u2bff]|[\u2190-\u21ff]',
        '',
        text
    ).strip()
    return cleaned


def set_button_icon(
    btn,
    icon_name: str,
    text: str | None = None,
    color: str = "#9ca3af",
    active_color: str = "#38bdf8",
    size: int = 14,
) -> None:
    """
    Safely configure a QPushButton with a vector icon and clean text.
    Automatically strips any accidental Unicode emoji prefixes from text to guarantee
    no duplicate or inconsistent system emojis appear.
    """
    btn.setIcon(get_icon(icon_name, color, active_color, size))
    btn.setIconSize(QSize(size, size))
    if text is not None:
        cleaned = clean_icon_text(text)
        btn.setText(f" {cleaned}" if cleaned else "")

