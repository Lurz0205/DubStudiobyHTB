"""Dark professional theme for DubStudio desktop app, inspired by Antigravity Soft Glass aesthetics."""

# Refined Cinema Dark Studio Color Palette (CapCut Pro / DaVinci / Linear Dark)
COLORS = {
    "bg_deep": "#0B0D13",         # Ultra-dark cinematic canvas
    "bg": "#0B0D13",              # Primary container background
    "surface": "#171B26",         # Standard Card / Frame / Control surface
    "surface_raised": "#1F2433",  # Elevated cards, row hover
    "surface_hover": "#282F42",   # Hover state
    "border": "#262C3A",          # Clean studio subtle border
    "border_light": "#323B4E",    # Elevated border
    "border_focus": "#6366F1",    # Indigo focus highlight
    "accent": "#6366F1",          # Primary Cinema Indigo Accent
    "accent_hover": "#4F46E5",    # Indigo hover state
    "accent_pressed": "#4338CA",  # Indigo deep pressed
    "accent_dim": "#1E2436",      # Active navigation & card selection tint
    "accent_border": "#3730A3",   # Accent container border
    "success": "#10B981",         # Emerald green
    "success_dim": "#064E3B",     # Success tint
    "warning": "#F59E0B",         # Amber warning
    "error": "#EF4444",           # Rose red error
    "error_dim": "#4C1D24",       # Error tint
    "text": "#F1F5F9",            # Crisp slate text
    "text_secondary": "#94A3B8",  # Refined secondary muted text
    "text_muted": "#64748B",      # Subtle hints and labels
    "text_disabled": "#475569",   # Disabled text
    "selection": "#312E81",       # Indigo text selection
    "timeline_bg": "#080A0F",     # Ultra-dark timeline canvas
    "track_bg": "#11141D",        # Timeline track background
    "track_sub": "#1E1B4B",       # Indigo Subtitle track
    "track_tts": "#064E3B",       # Emerald TTS audio track
    "handle": "#6366F1",          # Interactive handle
    "ruler": "#1A1F2C",           # Timeline ruler ticks
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
    font-family: "Segoe UI Variable Display", "Segoe UI", "Inter", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 10pt;
    border: none;
    outline: none;
}}

QMainWindow {{
    background-color: {COLORS['bg_deep']};
}}

/* ─── Sidebar (Cinema Dark Studio Vertical Navigation) ─── */
#sidebar {{
    background-color: #11141D;
    border-right: 1px solid {COLORS['border']};
    min-width: 195px;
    max-width: 195px;
}}

#sidebar_brand {{
    padding: 16px 14px 10px 14px;
}}

#sidebar_logo_text {{
    font-size: 15px;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: 0.4px;
}}

#sidebar_sub_text {{
    font-size: 10px;
    color: {COLORS['text_muted']};
}}

#sidebar_section_title {{
    font-size: 9.5px;
    font-weight: 700;
    color: {COLORS['text_muted']};
    text-transform: uppercase;
    letter-spacing: 1.2px;
    padding: 14px 14px 4px 14px;
}}

/* Sidebar Pill Action Button (+ Tạo dự án mới) */
QPushButton#sidebar_cta {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 10px;
    padding: 8px 14px;
    margin: 4px 10px 12px 10px;
    color: #FFFFFF;
    font-size: 11.5px;
    font-weight: 600;
    text-align: left;
}}

QPushButton#sidebar_cta:hover {{
    background-color: {COLORS['surface_raised']};
    border-color: {COLORS['accent']};
    color: #FFFFFF;
}}

QPushButton#sidebar_cta:pressed {{
    background-color: {COLORS['surface_hover']};
}}

/* Sidebar Standard Navigation Buttons */
#sidebar QPushButton.nav_item {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 8px 12px;
    margin: 2px 8px;
    color: {COLORS['text_secondary']};
    font-size: 11.5px;
    font-weight: 500;
    text-align: left;
    min-height: 20px;
}}

#sidebar QPushButton.nav_item:hover {{
    background-color: {COLORS['surface_raised']};
    color: #FFFFFF;
}}

#sidebar QPushButton.nav_item[active="true"] {{
    background-color: {COLORS['accent_dim']};
    border: 1px solid {COLORS['accent_border']};
    border-left: 3px solid {COLORS['accent']};
    color: #FFFFFF;
    font-weight: 600;
}}

/* ─── Header / Toolbar Bar ─── */
#header {{
    background-color: #11141D;
    border-bottom: 1px solid {COLORS['border']};
    padding: 0 18px;
    min-height: 46px;
    max-height: 46px;
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
    background-color: #6366F1;
    border: 1px solid #818CF8;
    color: #ffffff;
    font-weight: 600;
    border-radius: 8px;
}}

QPushButton#primary:hover {{
    background-color: #4F46E5;
    border-color: #A5B4FC;
}}

QPushButton#primary:pressed {{
    background-color: {COLORS['accent_pressed']};
}}

QPushButton#primary:disabled {{
    background-color: #1E1B4B;
    border-color: #312E81;
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

/* ─── Cinema Dark Studio Slider ─── */
QSlider::groove:horizontal {{
    height: 4px;
    background-color: {COLORS['border']};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {COLORS['accent']};
    border: 2px solid #FFFFFF;
    border-radius: 7px;
    width: 14px;
    height: 14px;
    margin: -5px 0;
}}

QSlider::handle:horizontal:hover {{
    background-color: {COLORS['accent_hover']};
    border-color: #FFFFFF;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::sub-page:horizontal {{
    background-color: {COLORS['accent']};
    border-radius: 2px;
}}

/* ─── Cinema Studio Tables ─── */
QTableWidget, QTableView {{
    background-color: #11141D;
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: #1E2436;
    selection-color: {COLORS['text']};
    alternate-background-color: #141724;
    outline: none;
}}

QHeaderView::section {{
    background-color: #171B26;
    color: {COLORS['text_secondary']};
    padding: 10px 12px;
    border: none;
    border-right: 1px solid {COLORS['border']};
    border-bottom: 1px solid {COLORS['border']};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QTableWidget::item, QTableView::item {{
    padding: 8px 12px;
    border-bottom: 1px solid #1E2330;
}}

QTableWidget::item:hover, QTableView::item:hover {{
    background-color: #1A1F2E;
}}

QTableWidget::item:selected, QTableView::item:selected {{
    background-color: #1E2436;
    color: #FFFFFF;
}}

/* ─── Sleek Studio ScrollBar ─── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 7px;
    margin: 0;
    border-radius: 3.5px;
}}

QScrollBar::handle:vertical {{
    background-color: #333B4D;
    border-radius: 3.5px;
    min-height: 36px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #4B5563;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 7px;
    margin: 0;
    border-radius: 3.5px;
}}

QScrollBar::handle:horizontal {{
    background-color: #333B4D;
    border-radius: 3.5px;
    min-width: 36px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #4B5563;
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
