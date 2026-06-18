from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class IconButton(QToolButton):
    def __init__(self, text: str = "", tooltip: str = "", icon_path: str | None = None) -> None:
        super().__init__()
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFixedSize(54, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon_path and Path(icon_path).exists():
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(24, 24))
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        else:
            self.setText(text)
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)


class ActivityBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("activityBar")
        self.setFixedWidth(54)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)
        assets = Path(__file__).resolve().parents[1] / "assets"
        # Activity bar is only for layout/navigation utilities, not duplicates of
        # central workbench tabs. Icons are app-owned SVGs.
        items = [
            ("", "工作区 / Workspace", assets / "activity_workspace.svg"),
            ("", "历史 / History", assets / "activity_history.svg"),
            ("", "分支 / Branches", assets / "activity_branches.svg"),
            ("", "远程 / Remotes", assets / "activity_remotes.svg"),
            ("", "标签与 Stash", assets / "activity_tags.svg"),
            ("", "高级 / Advanced", assets / "activity_advanced.svg"),
            ("", "平台 / Providers", assets / "activity_platform.svg"),
            ("", "Raw Git Terminal", assets / "activity_terminal.svg"),
            ("", "Help / Shortcuts", assets / "activity_help.svg"),
        ]
        self.buttons: list[IconButton] = []
        for index, (text, tooltip, icon_path) in enumerate(items):
            button = IconButton(text, tooltip, str(icon_path))
            if index == 0:
                button.setChecked(True)
            button.clicked.connect(lambda _checked, b=button: self.activate(b))
            self.buttons.append(button)
            layout.addWidget(button)
        layout.addStretch()
        self.account_button = IconButton("", "Accounts", str(assets / "activity_account.svg"))
        self.account_button.setCheckable(False)
        self.settings_button = IconButton("", "Manage / Theme", str(assets / "activity_settings.svg"))
        self.settings_button.setCheckable(False)
        layout.addWidget(self.account_button)
        layout.addWidget(self.settings_button)

    def activate(self, active_button: IconButton) -> None:
        for button in self.buttons:
            button.setChecked(button is active_button)


class TopCommandBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("topCommandBar")
        self.setFixedHeight(38)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        self.left_sidebar_button = QPushButton("◧")
        self.left_sidebar_button.setObjectName("layoutToggleButton")
        self.left_sidebar_button.setToolTip("Toggle Primary Side Bar")
        self.left_sidebar_button.setCheckable(True)
        self.left_sidebar_button.setChecked(True)
        self.left_sidebar_button.setFixedSize(30, 28)
        self.left_sidebar_button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.left_sidebar_button)

        brand = QLabel("Git Terminal")
        brand.setObjectName("brand")
        layout.addWidget(brand)

        # Visible in-template menu host. Native QMenuBar may be easy to miss on
        # some platforms/themes, so Git menus are also rendered directly inside
        # the uploaded template's top command bar.
        self.menu_host = QWidget()
        self.menu_host.setObjectName("topMenuHost")
        self.menu_layout = QHBoxLayout(self.menu_host)
        self.menu_layout.setContentsMargins(8, 0, 8, 0)
        self.menu_layout.setSpacing(2)
        layout.addWidget(self.menu_host)
        layout.addStretch(1)

        self.command_center = QLineEdit()
        self.command_center.setObjectName("commandCenter")
        self.command_center.setPlaceholderText("Search commands, branches, commits, remotes…")
        self.command_center.setFixedWidth(300)
        layout.addWidget(self.command_center)
        layout.addStretch(1)

        self.bottom_panel_button = QPushButton("▔")
        self.bottom_panel_button.setObjectName("layoutToggleButton")
        self.bottom_panel_button.setToolTip("Toggle Panel")
        self.bottom_panel_button.setCheckable(True)
        self.bottom_panel_button.setChecked(True)
        self.bottom_panel_button.setFixedSize(30, 28)
        self.bottom_panel_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.right_sidebar_button = QPushButton("◨")
        self.right_sidebar_button.setObjectName("layoutToggleButton")
        self.right_sidebar_button.setToolTip("Toggle Secondary Side Bar")
        self.right_sidebar_button.setCheckable(True)
        self.right_sidebar_button.setChecked(True)
        self.right_sidebar_button.setFixedSize(30, 28)
        self.right_sidebar_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setObjectName("topIcon")
        self.refresh_button.setFixedSize(30, 28)
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.more_button = QPushButton("⋯")
        self.more_button.setObjectName("topIcon")
        self.more_button.setFixedSize(30, 28)
        self.more_button.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self.bottom_panel_button)
        layout.addWidget(self.right_sidebar_button)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.more_button)


class SidePanel(QFrame):
    def __init__(self, title: str, side: str = "left", min_size: int = 220) -> None:
        super().__init__()
        self.side = side
        self.min_size = min_size
        self.collapse_callback = None
        self.setMinimumWidth(min_size)
        self.setObjectName("sidePanel" if side == "left" else "rightPanel")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.header = QFrame()
        self.header.setObjectName("panelHeader")
        self.header.setFixedHeight(36)
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(10, 0, 8, 0)
        self.header_layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("panelTitle")
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.collapse_button = QPushButton("‹" if side == "left" else "›")
        self.collapse_button.setObjectName("collapseButton")
        self.collapse_button.setToolTip("Hide Side Bar")
        self.collapse_button.setFixedSize(24, 24)
        self.collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_button.clicked.connect(self.request_collapse)
        self.header_layout.addWidget(self.collapse_button)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        main_layout.addWidget(self.header)
        main_layout.addWidget(self.body, 1)

    def set_collapse_callback(self, callback) -> None:
        self.collapse_callback = callback

    def request_collapse(self) -> None:
        if self.collapse_callback:
            self.collapse_callback()

    def add_header_action(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("panelAction")
        button.setFixedSize(24, 24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_layout.insertWidget(self.header_layout.count() - 1, button)
        return button


class BottomPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("bottomPanel")
        self.setMinimumHeight(72)
        self.hide_callback = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # No visible title/header: the whole bottom area is reserved for logs.
        # Collapse/maximize controls are placed in the terminal input bar.
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        layout.addWidget(self.body, 1)

    def set_hide_callback(self, callback) -> None:
        self.hide_callback = callback

    def request_hide(self) -> None:
        if self.hide_callback:
            self.hide_callback()

