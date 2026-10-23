"""Dark professional theme for DubStudio desktop app, inspired by Antigravity Soft Glass aesthetics."""

# Refined Antigravity Soft Glass Color Palette
COLORS = {
    "bg_deep": "#080910",         # Ultra-dark matte canvas
    "bg": "#0d0f16",              # Primary container background
    "surface": "#12141d",         # Card / Input surface with soft glass depth
    "surface_raised": "#181b27",  # Elevated cards, row hover
    "surface_hover": "#1f2335",   # Hover state
    "border": "#1c2030",          # Ultra-subtle border
    "border_light": "#262c3e",    # Slightly elevated border
    "border_focus": "#38bdf8",    # Focus highlight
    "accent": "#38bdf8",          # Signature sky-blue / cyan
    "accent_hover": "#60c8ff",    # Lighter accent
    "accent_pressed": "#0284c7",  # Deep accent
    "accent_dim": "#0c2236",      # Selected / active background
    "accent_border": "#194b71",   # Subtle accent border
    "success": "#10b981",         # Emerald green
    "success_dim": "#0a2618",     # Success tint
    "warning": "#f59e0b",         # Warm amber
    "error": "#ef4444",           # Rose red
    "error_dim": "#2a0e10",       # Error tint
    "text": "#eef0f6",            # Crisp high-contrast text
    "text_secondary": "#8e96aa",  # Refined muted text
    "text_muted": "#575f72",      # Subtle hints and labels
    "text_disabled": "#3e4454",   # Disabled text
    "selection": "#113550",       # Text selection
    "timeline_bg": "#07080b",     # Ultra-dark timeline canvas
    "track_bg": "#101219",        # Timeline track background
    "track_sub": "#0d2d4a",       # Subtitle track
    "track_tts": "#0a3820",       # TTS audio track
    "handle": "#38bdf8",          # Interactive handle
    "ruler": "#161824",           # Timeline ruler ticks
}

from pathlib import Path

# Setup resources for stepper arrows
_RES_DIR = Path(__file__).parent / "resources"
_RES_DIR.mkdir(parents=True, exist_ok=True)
_ARROW_UP_FILE = _RES_DIR / "arrow_up.svg"
_ARROW_DOWN_FILE = _RES_DIR / "arrow_down.svg"

if not _ARROW_UP_FILE.exists():
    _ARROW_UP_FILE.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" '
        'fill="none" stroke="#38bdf8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="18 15 12 9 6 15"/></svg>',
        encoding="utf-8"
    )

if not _ARROW_DOWN_FILE.exists():
    _ARROW_DOWN_FILE.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" '
        'fill="none" stroke="#38bdf8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="6 9 12 15 18 9"/></svg>',
        encoding="utf-8"
    )

ARROW_UP_PATH = _ARROW_UP_FILE.as_posix()
ARROW_DOWN_PATH = _ARROW_DOWN_FILE.as_posix()

STYLESHEET = f"""
/* ─── Global Reset & Typography ─── */
QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 10pt;
    border: none;
    outline: none;
}}

QMainWindow {{
    background-color: {COLORS['bg_deep']};
}}

/* ─── Sidebar (Antigravity Clean Vertical Navigation) ─── */
#sidebar {{
    background-color: {COLORS['bg_deep']};
    border-right: 1px solid {COLORS['border']};
    min-width: 190px;
    max-width: 190px;
}}

#sidebar_brand {{
    padding: 14px 12px 10px 12px;
}}

#sidebar_logo_text {{
    font-size: 14px;
    font-weight: 700;
    color: {COLORS['text']};
    letter-spacing: 0.4px;
}}

#sidebar_sub_text {{
    font-size: 10px;
    color: {COLORS['text_muted']};
}}

#sidebar_section_title {{
    font-size: 9px;
    font-weight: 700;
    color: {COLORS['text_muted']};
    text-transform: uppercase;
    letter-spacing: 1.2px;
    padding: 12px 12px 3px 12px;
}}

/* Sidebar Pill Action Button (+ Tạo dự án mới) */
QPushButton#sidebar_cta {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 14px;
    padding: 7px 12px;
    margin: 4px 10px 10px 10px;
    color: {COLORS['text']};
    font-size: 11px;
    font-weight: 600;
    text-align: left;
}}

QPushButton#sidebar_cta:hover {{
    background-color: {COLORS['surface_raised']};
    border-color: {COLORS['accent']};
    color: {COLORS['accent']};
}}

QPushButton#sidebar_cta:pressed {{
    background-color: {COLORS['surface_hover']};
}}

/* Sidebar Standard Navigation Buttons */
#sidebar QPushButton.nav_item {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 8px 10px;
    margin: 1px 8px;
    color: {COLORS['text_secondary']};
    font-size: 11.5px;
    font-weight: 500;
    text-align: left;
    min-height: 18px;
}}

#sidebar QPushButton.nav_item:hover {{
    background-color: {COLORS['surface_raised']};
    color: {COLORS['text']};
}}

#sidebar QPushButton.nav_item[active="true"] {{
    background-color: {COLORS['accent_dim']};
    border: 1px solid {COLORS['accent_border']};
    color: {COLORS['accent']};
    font-weight: 600;
}}

/* ─── Header / Toolbar Bar ─── */
#header {{
    background-color: {COLORS['bg_deep']};
    border-bottom: 1px solid {COLORS['border']};
    padding: 0 16px;
    min-height: 44px;
    max-height: 44px;
}}

#app_title {{
    font-size: 12px;
    font-weight: 500;
    color: {COLORS['text_muted']};
}}

#header_crumb {{
    font-size: 13px;
    color: {COLORS['text']};
    font-weight: 600;
}}

#header_gpu_badge {{
    background-color: {COLORS['surface_raised']};
    border: 1px solid {COLORS['border_light']};
    color: {COLORS['text_secondary']};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: 500;
}}

/* ─── Buttons (HyperOS Capsule Bento Style) ─── */
QPushButton {{
    background-color: {COLORS['surface_raised']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    padding: 5px 14px;
    color: {COLORS['text']};
    font-size: 11.5px;
    font-weight: 500;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {COLORS['surface_hover']};
    border-color: #333a52;
    color: #ffffff;
}}

QPushButton:pressed {{
    background-color: {COLORS['surface']};
}}

QPushButton:disabled {{
    color: {COLORS['text_disabled']};
    border-color: {COLORS['border']};
    background-color: {COLORS['surface']};
}}

/* Compact toolbar-sized button */
QPushButton#compact {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 7px;
    padding: 4px 10px;
    font-size: 11px;
    min-height: 26px;
}}

QPushButton#compact:hover {{
    background-color: {COLORS['surface_hover']};
    border-color: #2f3850;
}}

/* Primary Accent Button */
QPushButton#primary {{
    background-color: #0b78b8;
    border: 1px solid #38bdf8;
    color: #ffffff;
    font-weight: 600;
    border-radius: 8px;
}}

QPushButton#primary:hover {{
    background-color: #0e93d8;
    border-color: #6dd2fc;
}}

QPushButton#primary:pressed {{
    background-color: {COLORS['accent_pressed']};
}}

QPushButton#primary:disabled {{
    background-color: #0a2d43;
    border-color: #163a52;
    color: {COLORS['text_disabled']};
}}

/* Success Button */
QPushButton#success {{
    background-color: #047857;
    border: 1px solid #10b981;
    color: #ffffff;
    font-weight: 600;
    border-radius: 8px;
}}

QPushButton#success:hover {{
    background-color: #10b981;
    border-color: #34d399;
}}

QPushButton#success:pressed {{
    background-color: #036349;
}}

QPushButton#success:disabled {{
    background-color: #0a2416;
    border-color: #0d3320;
    color: {COLORS['text_disabled']};
}}

/* Danger Button */
QPushButton#danger {{
    background-color: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.30);
    color: #ef4444;
    border-radius: 8px;
}}

QPushButton#danger:hover {{
    background-color: rgba(239, 68, 68, 0.18);
    border-color: #ef4444;
    color: #fca5a5;
}}

QPushButton#icon_btn {{
    background-color: transparent;
    border: 1px solid transparent;
    padding: 4px;
    border-radius: 7px;
    font-size: 14px;
    min-height: 24px;
}}

QPushButton#icon_btn:hover {{
    background-color: {COLORS['surface_raised']};
    border-color: {COLORS['border_light']};
}}

/* ─── Toolbar Card Frame ─── */
QFrame#toolbar_card {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 6px 10px;
}}

/* ─── Text Inputs & Editors (Bento Inset Style) ─── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: #0a0c13;
    border: 1px solid #1e2232;
    border-radius: 9px;
    padding: 6px 11px;
    color: {COLORS['text']};
    font-size: 11.5px;
    selection-background-color: {COLORS['selection']};
}}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border-color: #2c3348;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {COLORS['accent']};
    background-color: #070910;
}}

/* ─── ComboBox (Bento Dropdown Style) ─── */
QComboBox {{
    background-color: #0a0c13;
    border: 1px solid #1e2232;
    border-radius: 8px;
    padding: 5px 10px;
    color: {COLORS['text']};
    font-size: 11.5px;
    min-height: 26px;
}}

QComboBox:hover {{
    border-color: #2c3348;
    background-color: #0e1120;
}}

QComboBox:focus {{
    border-color: {COLORS['accent']};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 0px;
    border: none;
}}

QComboBox::down-arrow {{
    image: none;
    border: none;
    width: 0px;
    height: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: #0e1120;
    border: 1px solid #1e2334;
    border-radius: 9px;
    padding: 4px;
    selection-background-color: {COLORS['accent_dim']};
    selection-color: {COLORS['accent']};
    outline: none;
}}

/* ─── SpinBox & DoubleSpinBox ─── */
QSpinBox, QDoubleSpinBox {{
    background-color: #0a0c13;
    border: 1px solid #1e2232;
    border-radius: 8px;
    padding: 4px 22px 4px 8px;
    color: {COLORS['text']};
    font-size: 11.5px;
    min-height: 26px;
}}

QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: #2c3348;
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLORS['accent']};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    background-color: {COLORS['surface_raised']};
    border-top-right-radius: 7px;
    border-left: 1px solid {COLORS['border_light']};
    border-bottom: 1px solid {COLORS['border']};
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    background-color: {COLORS['surface_raised']};
    border-bottom-right-radius: 7px;
    border-left: 1px solid {COLORS['border_light']};
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {COLORS['surface_hover']};
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({ARROW_UP_PATH});
    width: 10px;
    height: 10px;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({ARROW_DOWN_PATH});
    width: 10px;
    height: 10px;
}}

/* SpinBox accent variant (words-per-line) */
QSpinBox#accent_spin {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['accent']};
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
    border-radius: 8px;
    min-height: 28px;
    padding-left: 8px;
    padding-right: 24px;
}}

QSpinBox#accent_spin:focus {{
    border-color: #38bdf8;
}}

QSpinBox#accent_spin::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    background-color: {COLORS['accent_dim']};
    border-top-right-radius: 7px;
    border-left: 1px solid {COLORS['accent_border']};
    border-bottom: 1px solid {COLORS['accent_border']};
}}

QSpinBox#accent_spin::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    background-color: {COLORS['accent_dim']};
    border-bottom-right-radius: 7px;
    border-left: 1px solid {COLORS['accent_border']};
}}

QSpinBox#accent_spin::up-button:hover, QSpinBox#accent_spin::down-button:hover {{
    background-color: {COLORS['accent_border']};
}}

QSpinBox#accent_spin::up-arrow {{
    image: url({ARROW_UP_PATH});
    width: 10px;
    height: 10px;
}}

QSpinBox#accent_spin::down-arrow {{
    image: url({ARROW_DOWN_PATH});
    width: 10px;
    height: 10px;
}}

/* ─── Minimal Slider ─── */
QSlider::groove:horizontal {{
    height: 4px;
    background-color: {COLORS['border_light']};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {COLORS['accent']};
    border-radius: 6px;
    width: 12px;
    height: 12px;
    margin: -4px 0;
}}

QSlider::handle:horizontal:hover {{
    background-color: {COLORS['accent_hover']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::sub-page:horizontal {{
    background-color: {COLORS['accent']};
    border-radius: 2px;
}}

/* ─── Tables (Bento Card Style) ─── */
QTableWidget {{
    background-color: #0f1119;
    border: 1px solid #191d2c;
    border-radius: 12px;
    gridline-color: transparent;
    selection-background-color: #0c2840;
    selection-color: {COLORS['text']};
    alternate-background-color: #131725;
    outline: none;
}}

QHeaderView::section {{
    background-color: #14172a;
    color: {COLORS['text_muted']};
    padding: 9px 12px;
    border: none;
    border-right: 1px solid #191d2c;
    border-bottom: 1px solid #1e2334;
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QTableWidget::item {{
    padding: 7px 12px;
    border-bottom: 1px solid #181c28;
}}

QTableWidget::item:hover {{
    background-color: #171b2b;
}}

QTableWidget::item:selected {{
    background-color: #0c2840;
    color: #38bdf8;
}}

/* ─── Sleek ScrollBar ─── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 5px;
    margin: 0;
    border-radius: 3px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border_light']};
    border-radius: 3px;
    min-height: 36px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['text_muted']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 5px;
    margin: 0;
    border-radius: 3px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS['border_light']};
    border-radius: 3px;
    min-width: 36px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS['text_muted']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ─── Splitter ─── */
QSplitter::handle {{
    background-color: {COLORS['border']};
}}

QSplitter::handle:horizontal {{
    width: 6px;
    background-color: {COLORS['surface_raised']};
    border-left: 1px solid {COLORS['border']};
    border-right: 1px solid {COLORS['border']};
}}

QSplitter::handle:vertical {{
    height: 6px;
    background-color: {COLORS['surface_raised']};
    border-top: 1px solid {COLORS['border']};
    border-bottom: 1px solid {COLORS['border']};
}}

QSplitter::handle:hover {{
    background-color: {COLORS['accent_border']};
}}

/* ─── Labels ─── */
QLabel {{
    background-color: transparent;
    color: {COLORS['text']};
}}

QLabel#section_title {{
    font-size: 11px;
    font-weight: 700;
    color: {COLORS['text']};
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 2px 0;
}}

QLabel#status_label {{
    color: {COLORS['text_secondary']};
    font-size: 11px;
}}

QLabel#toolbar_label {{
    color: {COLORS['text_muted']};
    font-size: 10.5px;
    font-weight: 500;
}}

/* ─── Progress Bar ─── */
QProgressBar {{
    background-color: {COLORS['surface_raised']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 9px;
    height: 18px;
    min-height: 18px;
    max-height: 20px;
    text-align: center;
    color: #ffffff;
    font-size: 11px;
    font-weight: 600;
}}

QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 8px;
}}

/* ─── Tab Bar ─── */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    background-color: {COLORS['surface']};
}}

QTabBar::tab {{
    background-color: transparent;
    color: {COLORS['text_secondary']};
    padding: 7px 14px;
    border-bottom: 2px solid transparent;
    margin-right: 4px;
    font-weight: 500;
    font-size: 11px;
}}

QTabBar::tab:selected {{
    color: {COLORS['accent']};
    border-bottom-color: {COLORS['accent']};
    font-weight: 600;
}}

QTabBar::tab:hover {{
    color: {COLORS['text']};
}}

/* ─── GroupBox (HyperOS Bento Card) ─── */
QGroupBox {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-size: 11.5px;
    font-weight: 600;
    color: {COLORS['text']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 0 7px;
    background-color: {COLORS['bg']};
    color: {COLORS['accent']};
    font-weight: 600;
}}

/* ─── Checkbox (Modern Clean Switch / Indicator) ─── */
QCheckBox {{
    background-color: transparent;
    color: {COLORS['text']};
    spacing: 7px;
    font-size: 11.5px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {COLORS['border_light']};
    border-radius: 5px;
    background-color: {COLORS['surface_raised']};
}}

QCheckBox::indicator:hover {{
    border-color: {COLORS['accent']};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

/* ─── Radio Button (Modern Accent Dot Indicator) ─── */
QRadioButton {{
    background-color: transparent;
    color: {COLORS['text_secondary']};
    spacing: 7px;
    font-size: 11.5px;
    font-weight: 500;
}}

QRadioButton:hover {{
    color: {COLORS['text']};
}}

QRadioButton:checked {{
    color: {COLORS['accent']};
    font-weight: 600;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {COLORS['border_light']};
    border-radius: 8px;
    background-color: {COLORS['surface_raised']};
}}

QRadioButton::indicator:hover {{
    border-color: {COLORS['accent']};
}}

QRadioButton::indicator:checked {{
    border: 4px solid #111422;
    background-color: {COLORS['accent']};
    border-radius: 8px;
}}

/* ─── ToolTip ─── */
QToolTip {{
    background-color: {COLORS['surface_raised']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    padding: 5px 9px;
    border-radius: 6px;
    font-size: 10.5px;
}}

/* ─── Dialogs ─── */
QMessageBox {{
    background-color: {COLORS['bg']};
}}

/* ─── Card & Panel Frames (HyperOS Bento Card Depth) ─── */
QFrame#card {{
    background-color: #101220;
    border: 1px solid #1a1e30;
    border-radius: 14px;
    padding: 12px;
}}

QFrame#bento_metric {{
    background-color: #101220;
    border: 1px solid #1a1e30;
    border-radius: 14px;
    padding: 12px 16px;
}}

QFrame#bento_metric:hover {{
    border-color: #29304a;
    background-color: #141728;
}}

QFrame#bento_project_item {{
    background-color: #101220;
    border: 1px solid #1a1e30;
    border-radius: 12px;
}}

QFrame#bento_project_item:hover {{
    background-color: #141728;
    border-color: #29304a;
}}

QFrame#panel {{
    background-color: {COLORS['bg_deep']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
}}

/* ─── Subtle Status Bar ─── */
QStatusBar {{
    background-color: {COLORS['bg_deep']};
    border-top: 1px solid {COLORS['border']};
    color: {COLORS['text_secondary']};
    font-size: 10.5px;
    font-weight: 500;
    padding: 3px 12px;
}}
"""
