from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QWidget


ACCENTS = {
    "blue": "#007acc",
    "purple": "#8b5cf6",
    "green": "#10b981",
    "orange": "#f97316",
}

PALETTES = {
    "dark": {
        "bg": "#1e1e1e",
        "panel": "#252526",
        "panel2": "#2d2d2d",
        "top": "#242424",
        "activity": "#333333",
        "input": "#1f1f1f",
        "terminal": "#181818",
        "text": "#d4d4d4",
        "muted": "#a8a8a8",
        "border": "#1c1c1c",
        "hover": "#3a3a3a",
        "selected": "#37373d",
    },
    "light": {
        "bg": "#ffffff",
        "panel": "#f3f3f3",
        "panel2": "#e8e8e8",
        "top": "#f3f3f3",
        "activity": "#e5e7eb",
        "input": "#ffffff",
        "terminal": "#ffffff",
        "text": "#1f2937",
        "muted": "#4b5563",
        "border": "#d1d5db",
        "hover": "#e5e7eb",
        "selected": "#dbeafe",
    },
}


def build_qss(mode: str = "dark", accent_name: str = "blue") -> str:
    p = PALETTES.get(mode, PALETTES["dark"])
    accent = ACCENTS.get(accent_name, ACCENTS["blue"])
    return f"""
* {{
    font-family: "Segoe UI", "Microsoft YaHei UI", Arial;
}}
QMainWindow {{
    background-color: {p['bg']};
    color: {p['text']};
}}
QMenuBar {{
    background-color: {p['panel2']};
    color: {p['text']};
    border-bottom: 1px solid {p['border']};
    height: 28px;
    font-size: 13px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
}}
QMenuBar::item:selected {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QMenu {{
    background-color: {p['panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    padding: 4px 0;
}}
QMenu::item {{
    padding: 7px 32px 7px 22px;
}}
QMenu::item:selected {{
    background-color: {accent};
    color: white;
}}
QToolBar {{
    background-color: {p['top']};
    color: {p['text']};
    border-bottom: 1px solid {p['border']};
    spacing: 6px;
    padding: 4px;
}}
QFrame#topCommandBar {{
    background-color: {p['top']};
    border-bottom: 1px solid {p['border']};
}}
QLabel#brand {{
    color: {p['text']};
    font-weight: 600;
    font-size: 13px;
}}

QWidget#topMenuHost {{
    background-color: transparent;
}}
QToolButton#topMenuButton {{
    background-color: transparent;
    color: {p['text']};
    border: none;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 13px;
}}
QToolButton#topMenuButton:hover {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QToolButton#topMenuButton::menu-indicator {{
    image: none;
    width: 0px;
}}
QLineEdit#commandCenter {{
    background-color: {p['input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 7px;
    padding: 6px 12px;
    selection-background-color: {accent};
}}
QLineEdit#commandCenter:focus {{
    border: 1px solid {accent};
}}
QFrame#activityBar {{
    background-color: {p['activity']};
    border-right: 1px solid {p['border']};
}}
QToolButton {{
    background-color: transparent;
    color: {p['muted']};
    border: none;
    font-size: 20px;
}}
QToolButton:hover {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QToolButton:checked {{
    background-color: {p['panel']};
    color: {p['text']};
    border-left: 2px solid {accent};
}}
QFrame#sidePanel, QFrame#rightPanel {{
    background-color: {p['panel']};
}}
QFrame#sidePanel {{
    border-right: 1px solid {p['border']};
}}
QFrame#rightPanel {{
    border-left: 1px solid {p['border']};
}}
QFrame#panelHeader {{
    background-color: {p['panel']};
    border-bottom: 1px solid {p['border']};
}}
QLabel#panelTitle {{
    color: {p['text']};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.6px;
}}
QPushButton#panelAction, QPushButton#collapseButton, QPushButton#layoutToggleButton, QPushButton#topIcon {{
    background-color: transparent;
    color: {p['muted']};
    border: none;
    border-radius: 4px;
}}
QPushButton#panelAction:hover, QPushButton#collapseButton:hover, QPushButton#layoutToggleButton:hover, QPushButton#topIcon:hover {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QPushButton#layoutToggleButton:checked {{
    background-color: {p['selected']};
    color: {p['text']};
}}
QPushButton {{
    background-color: {p['panel2']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 5px 9px;
}}
QPushButton:hover {{
    background-color: {p['hover']};
    border-color: {accent};
}}
QPushButton:pressed {{
    background-color: {accent};
    color: #ffffff;
}}
QPushButton#runButton {{
    background-color: {accent};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 3px 10px;
}}

QFrame#workspaceOverlay {{
    background-color: rgba(0, 0, 0, 150);
}}
QFrame#workspaceOverlayCard {{
    background-color: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    min-width: 520px;
}}
QLabel#workspacePromptTitle {{
    color: {p['text']};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#workspacePromptMessage {{
    color: {p['muted']};
    font-size: 13px;
}}

QLineEdit#workspacePromptInput {{
    background-color: {p['input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 5px;
    padding: 7px 9px;
    selection-background-color: {accent};
}}
QLineEdit#workspacePromptInput:focus {{
    border: 1px solid {accent};
}}
QPushButton#workspacePromptBackButton, QPushButton#workspacePromptCancelButton {{
    background-color: {p['panel2']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 5px;
    padding: 4px 10px;
}}
QPushButton#workspacePromptBackButton:hover, QPushButton#workspacePromptCancelButton:hover {{
    background-color: {p['hover']};
    border-color: {accent};
}}
QPushButton#workspacePromptOkButton {{
    background-color: {accent};
    color: white;
    border: none;
    border-radius: 5px;
    padding: 4px 12px;
}}
QPushButton#workspacePromptOkButton:hover {{
    background-color: {accent};
}}
QLabel#TopStatusLabel {{
    background-color: {p['bg']};
    color: {p['muted']};
    border-bottom: 1px solid {p['border']};
    padding: 5px 10px;
    font-size: 12px;
}}
QTreeWidget, QListWidget {{
    background-color: {p['panel']};
    color: {p['text']};
    border: none;
    outline: none;
    font-size: 13px;
}}
QTreeWidget::item, QListWidget::item {{
    min-height: 25px;
    padding-left: 4px;
}}
QTreeWidget::item:hover, QListWidget::item:hover {{
    background-color: {p['hover']};
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {p['selected']};
    color: {p['text']};
}}
QTabWidget {{
    background-color: {p['bg']};
    border: none;
}}
QTabWidget::pane {{
    border: none;
    background-color: {p['bg']};
}}
QTabBar {{
    background-color: {p['bg']};
    border: none;
}}
QTabBar::tab {{
    background-color: {p['panel2']};
    color: {p['muted']};
    padding: 8px 14px;
    border: none;
    border-right: 1px solid {p['border']};
    min-height: 18px;
}}
QTabBar::tab:selected {{
    background-color: {p['bg']};
    color: {p['text']};
    border-top: 1px solid {accent};
}}
QTabBar::tab:hover:!selected {{
    background-color: {p['selected']};
    color: {p['text']};
}}
QTabWidget#bottomTabs {{
    background-color: {p['terminal']};
}}
QTabWidget#bottomTabs::pane {{
    background-color: {p['terminal']};
    border-top: 1px solid {p['border']};
}}
QTabWidget#bottomTabs QTabBar {{
    background-color: {p['terminal']};
}}
QTabWidget#bottomTabs QTabBar::tab {{
    background-color: {p['terminal']};
    color: {p['muted']};
    padding: 7px 12px;
    border-right: none;
}}
QTabWidget#bottomTabs QTabBar::tab:selected {{
    color: {p['text']};
    background-color: {p['bg']};
    border-top: 1px solid {accent};
}}
QPlainTextEdit {{
    background-color: {p['bg']};
    color: {p['text']};
    border: none;
    selection-background-color: {accent};
    padding: 8px;
}}
QPlainTextEdit#terminalOutput {{
    background-color: {p['terminal']};
    color: {p['text']};
    border: none;
    padding: 10px;
}}
QFrame#terminalInputBar {{
    background-color: {p['terminal']};
    border-top: 1px solid {p['border']};
}}

QFrame#terminalPromptOverlay {{
    background-color: {p['terminal']};
    border-top: 1px solid {p['border']};
}}
QFrame#terminalPromptCard {{
    background-color: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    min-width: 360px;
}}
QLabel#terminalPromptTitle {{
    color: {p['text']};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#terminalPromptMessage {{
    color: {p['muted']};
    font-size: 13px;
}}

QPushButton#terminalPromptBackButton, QPushButton#terminalPromptCancelButton {{
    background-color: {p['panel2']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 5px;
    padding: 4px 10px;
}}
QPushButton#terminalPromptBackButton:hover, QPushButton#terminalPromptCancelButton:hover {{
    background-color: {p['hover']};
    border-color: {accent};
}}
QPushButton#terminalPromptOkButton {{
    background-color: {accent};
    color: white;
    border: none;
    border-radius: 5px;
    padding: 4px 12px;
}}
QPushButton#terminalPromptOkButton:hover {{
    background-color: {accent};
}}
QLabel#terminalPrompt {{
    color: {accent};
    font-family: Consolas;
    font-size: 12px;
}}
QLineEdit#terminalInput {{
    background-color: {p['input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 5px;
    padding: 6px 8px;
    font-family: Consolas;
    font-size: 12px;
    selection-background-color: {accent};
}}
QLineEdit#terminalInput:focus {{
    border: 1px solid {accent};
}}
QFrame#bottomPanel {{
    background-color: {p['terminal']};
    border-top: 1px solid {p['border']};
}}
QSplitter::handle {{
    background-color: {p['border']};
}}
QSplitter::handle:hover {{
    background-color: {accent};
}}
QScrollBar:vertical {{
    background: {p['bg']};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #424242;
    min-height: 24px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: #5a5a5a;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
}}
QStatusBar {{
    background-color: {accent};
    color: white;
    border: none;
    min-height: 23px;
    font-size: 12px;
}}
"""


def apply_theme(app: QApplication, root: QWidget, mode: str = "dark", accent: str = "blue") -> None:
    app.setStyleSheet(build_qss(mode, accent))
    ui_font = QFont("Segoe UI")
    ui_font.setPointSize(10)
    app.setFont(ui_font)
    mono = QFont("Consolas")
    mono.setStyleHint(QFont.StyleHint.Monospace)
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
        "output_panel",
    ]:
        widget = getattr(root, name, None)
        if widget is not None:
            widget.setFont(mono)
