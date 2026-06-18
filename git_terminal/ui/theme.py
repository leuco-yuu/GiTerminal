from __future__ import annotations

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QWidget


ACCENTS = {
    "blue": {"accent": "#2563eb", "accent_hover": "#3b82f6", "accent_dark": "#1d4ed8", "soft": "#93c5fd"},
    "purple": {"accent": "#7c3aed", "accent_hover": "#8b5cf6", "accent_dark": "#6d28d9", "soft": "#c4b5fd"},
    "green": {"accent": "#059669", "accent_hover": "#10b981", "accent_dark": "#047857", "soft": "#86efac"},
    "orange": {"accent": "#ea580c", "accent_hover": "#f97316", "accent_dark": "#c2410c", "soft": "#fdba74"},
}

PALETTES = {
    "dark": {
        "bg": "#0f172a",
        "panel": "#111827",
        "panel2": "#1e293b",
        "input": "#020617",
        "text": "#e5e7eb",
        "muted": "#cbd5e1",
        "border": "#334155",
        "hover": "#1e293b",
        "header": "#172554",
        "selection": "#1d4ed8",
    },
    "light": {
        "bg": "#f8fafc",
        "panel": "#ffffff",
        "panel2": "#e2e8f0",
        "input": "#ffffff",
        "text": "#0f172a",
        "muted": "#334155",
        "border": "#cbd5e1",
        "hover": "#e0f2fe",
        "header": "#dbeafe",
        "selection": "#bfdbfe",
    },
}


def build_qss(mode: str = "dark", accent_name: str = "blue") -> str:
    palette = PALETTES.get(mode, PALETTES["dark"])
    accent = ACCENTS.get(accent_name, ACCENTS["blue"])
    return f"""
QMainWindow, QWidget {{
    background: {palette['bg']};
    color: {palette['text']};
    font-size: 13px;
}}
QMenuBar, QMenu, QToolBar {{
    background: {palette['panel']};
    color: {palette['text']};
    border: none;
}}
QMenuBar::item {{
    padding: 5px 9px;
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background: {accent['accent']};
    color: #ffffff;
}}
QToolBar {{
    spacing: 8px;
    padding: 6px;
    border-bottom: 1px solid {palette['border']};
}}
QLabel {{
    color: {palette['text']};
}}
QLabel#TopStatusLabel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {palette['panel2']}, stop:1 {palette['header']});
    color: {palette['text']};
    border: 1px solid {palette['border']};
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 600;
}}
QLabel#PaneTitle {{
    color: {accent['soft']};
    font-weight: 700;
}}
QFrame#PaneHeader {{
    background: {palette['panel']};
    border: 1px solid {palette['border']};
    border-radius: 10px;
}}
QGroupBox {{
    border: 1px solid {palette['border']};
    border-radius: 12px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    background: {palette['panel']};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {accent['soft']};
}}
QPushButton {{
    background: {accent['accent']};
    color: #ffffff;
    border: 1px solid {accent['accent_hover']};
    border-radius: 8px;
    padding: 7px 10px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {accent['accent_hover']};
    border-color: {accent['soft']};
}}
QPushButton:pressed {{
    background: {accent['accent_dark']};
}}
QPushButton:disabled {{
    background: {palette['panel2']};
    color: {palette['muted']};
    border-color: {palette['border']};
}}
QPushButton#CollapseButton {{
    min-width: 26px;
    max-width: 32px;
    padding: 5px;
    border-radius: 7px;
}}
QLineEdit, QComboBox {{
    background: {palette['input']};
    color: {palette['text']};
    border: 1px solid {palette['border']};
    border-radius: 8px;
    padding: 7px 9px;
    selection-background-color: {accent['accent']};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {accent['accent_hover']};
}}
QPlainTextEdit, QTextEdit {{
    background: {palette['input']};
    color: {palette['muted']};
    border: 1px solid {palette['border']};
    border-radius: 10px;
    padding: 8px;
    selection-background-color: {accent['accent']};
}}
QListWidget, QTreeWidget {{
    background: {palette['input']};
    color: {palette['text']};
    border: 1px solid {palette['border']};
    border-radius: 10px;
    padding: 4px;
    alternate-background-color: {palette['panel']};
    selection-background-color: {accent['accent']};
    selection-color: #ffffff;
}}
QTreeWidget::item, QListWidget::item {{
    min-height: 24px;
    padding: 3px 6px;
    border-radius: 6px;
}}
QTreeWidget::item:hover, QListWidget::item:hover {{
    background: {palette['hover']};
}}
QHeaderView::section {{
    background: {palette['panel2']};
    color: {accent['soft']};
    border: none;
    border-right: 1px solid {palette['border']};
    padding: 6px;
    font-weight: 600;
}}
QTabWidget::pane {{
    border: 1px solid {palette['border']};
    border-radius: 12px;
    top: -1px;
    background: {palette['bg']};
}}
QTabBar::tab {{
    background: {palette['panel']};
    color: {palette['muted']};
    padding: 9px 14px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 3px;
    border: 1px solid {palette['border']};
}}
QTabBar::tab:selected {{
    background: {accent['accent']};
    color: #ffffff;
    border-color: {accent['accent_hover']};
}}
QSplitter::handle {{
    background: {palette['panel2']};
}}
QSplitter::handle:hover {{
    background: {accent['accent']};
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: {palette['bg']};
    border: none;
    margin: 0;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {palette['border']};
    border-radius: 5px;
    min-height: 22px;
    min-width: 22px;
}}
QStatusBar {{
    background: {palette['panel']};
    color: {palette['muted']};
}}
"""


def apply_theme(app: QApplication, root: QWidget, mode: str = "dark", accent: str = "blue") -> None:
    app.setStyleSheet(build_qss(mode, accent))
    ui_font = QFont("Segoe UI", 10)
    app.setFont(ui_font)
    mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    mono.setPointSize(10)
    for name in [
        "diff_view",
        "commit_detail",
        "branch_graph_detail",
        "remote_output",
        "conflict_preview",
        "advanced_output",
        "all_commands_output",
        "platform_output",
        "command_log",
    ]:
        widget = getattr(root, name, None)
        if widget is not None:
            widget.setFont(mono)
