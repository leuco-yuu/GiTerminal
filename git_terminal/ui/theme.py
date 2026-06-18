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
    status_bg = "#2d2d2d" if mode == "dark" else "#e5e5e5"
    status_text = p["text"]
    status_hover = "#3a3a3a" if mode == "dark" else "#d8d8d8"
    status_border = "#3f3f46" if mode == "dark" else "#cfcfcf"
    return f"""
* {{
    font-family: "Segoe UI", "Microsoft YaHei UI", Arial;
}}
QMainWindow {{
    background-color: {p['bg']};
    color: {p['text']};
}}
QWidget {{
    color: {p['text']};
}}
QLabel {{
    color: {p['text']};
    background-color: transparent;
}}
QFrame {{
    color: {p['text']};
}}
QGroupBox {{
    background-color: {p['bg']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    margin-top: 10px;
    padding: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    color: {p['text']};
    padding: 0 6px;
    left: 8px;
}}
QCheckBox {{
    color: {p['text']};
    spacing: 6px;
}}
QComboBox {{
    background-color: {p['input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 2px 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {p['panel']};
    color: {p['text']};
    selection-background-color: {p['selected']};
    selection-color: {p['text']};
}}
QLineEdit {{
    background-color: {p['input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 2px 6px;
    selection-background-color: {accent};
}}
QTextEdit {{
    background-color: {p['bg']};
    color: {p['text']};
    border: none;
    selection-background-color: {accent};
}}
QHeaderView::section {{
    background-color: {p['panel2']};
    color: {p['text']};
    border: 1px solid {p['border']};
    padding: 4px;
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
    background-color: {p['panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 3px 8px;
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

QPushButton#contextActionButton {{
    min-height: 24px;
    padding: 3px 6px;
}}
QPushButton#contextActionWideButton {{
    min-height: 24px;
    padding: 3px 8px;
}}
QGroupBox#contextActionGroup {{
    margin-top: 8px;
    padding: 6px;
}}

QFrame#workspaceOverlay {{
    background-color: rgba(0, 0, 0, 150);
}}
QFrame#workspaceOverlay QLabel {{
    color: {p['text']};
}}
QFrame#workspaceOverlayCard {{
    background-color: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    min-width: 480px;
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

QLineEdit#workspacePromptInput, QComboBox#workspacePromptInput {{
    background-color: {p['input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 1px 6px;
    min-height: 20px;
    max-height: 24px;
    selection-background-color: {accent};
}}
QPlainTextEdit#workspacePromptTextInput {{
    background-color: {p['input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: {accent};
}}
QLineEdit#workspacePromptInput:focus, QComboBox#workspacePromptInput:focus, QPlainTextEdit#workspacePromptTextInput:focus {{
    border: 1px solid {accent};
}}
QComboBox#workspacePromptInput QAbstractItemView {{
    background-color: {p['panel']};
    color: {p['text']};
    selection-background-color: {p['selected']};
}}
QPushButton#workspacePromptBackButton, QPushButton#workspacePromptCancelButton {{
    background-color: {p['panel2']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 4px;
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
    border-radius: 4px;
    padding: 4px 12px;
}}
QPushButton#workspacePromptOkButton:hover {{
    background-color: {accent};
}}
QLabel#TopStatusLabel {{
    background-color: {p['bg']};
    color: {p['muted']};
    border-bottom: 1px solid {p['border']};
    padding: 4px 10px;
    font-size: 12px;
}}
QLabel#RepoTargetLabel {{
    background-color: {p['panel2']};
    color: {p['text']};
    border-bottom: 1px solid {p['border']};
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
}}

QFrame#statusStrip {{
    background-color: {status_bg};
    border-top: 1px solid {status_border};
}}
QLabel#statusSegment, QLabel#statusPathSegment {{
    background-color: transparent;
    color: {status_text};
    border-right: 1px solid {status_border};
    padding: 0 8px;
    font-size: 12px;
}}
QLabel#statusSegment:hover, QLabel#statusPathSegment:hover {{
    background-color: {status_hover};
}}
QLabel#statusPathSegment {{
    font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei UI", monospace;
}}
QLabel#ProviderStatusLabel {{
    background-color: rgba(127, 127, 127, 28);
    color: {p['text']};
    border: 1px solid rgba(127, 127, 127, 56);
    border-radius: 6px;
    padding: 6px 8px;
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
    padding: 6px 12px;
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
QScrollArea#workspaceScroll, QScrollArea#workspacePageScroll, QScrollArea#contextScroll {{
    background-color: {p['bg']};
    border: none;
}}
QScrollArea#workspaceScroll > QWidget > QWidget, QScrollArea#workspacePageScroll > QWidget > QWidget, QScrollArea#contextScroll > QWidget > QWidget {{
    background-color: {p['bg']};
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
    border-bottom: 1px solid {p['border']};
}}
QFrame#terminalInputBar[state="running"] {{
    background-color: #1e3a8a;
    border-bottom: 1px solid #60a5fa;
}}
QFrame#terminalInputBar[state="success"] {{
    background-color: #14532d;
    border-bottom: 1px solid #22c55e;
}}
QFrame#terminalInputBar[state="error"] {{
    background-color: #7f1d1d;
    border-bottom: 1px solid #ef4444;
}}
QFrame#terminalInputBar[state="warning"] {{
    background-color: #713f12;
    border-bottom: 1px solid #f59e0b;
}}
QLabel#terminalStateLabel {{
    background-color: rgba(255, 255, 255, 32);
    color: #ffffff;
    border-radius: 4px;
    padding: 3px 7px;
    font-family: Consolas;
    font-size: 11px;
    font-weight: 700;
}}

QLabel#terminalEnvLabel {{
    color: {p['muted']};
    font-family: Consolas;
    font-size: 11px;
    padding: 0 4px;
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
    border-radius: 4px;
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
    border-radius: 4px;
    padding: 4px 12px;
}}
QPushButton#terminalPromptOkButton:hover {{
    background-color: {accent};
}}
QLabel#terminalPrompt {{
    color: #ffffff;
    font-family: Consolas;
    font-size: 12px;
}}
QLineEdit#terminalInput {{
    background-color: {p['input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 2px 6px;
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
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(127, 127, 127, 92);
    min-height: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(127, 127, 127, 150);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: rgba(127, 127, 127, 92);
    min-width: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(127, 127, 127, 150);
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal, QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
    width: 0;
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
