from __future__ import annotations

import json
import html
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PyQt6.QtCore import Qt, QThread, QPoint
from PyQt6.QtGui import QAction, QActionGroup, QBrush, QColor, QIcon, QKeySequence, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedLayout,
    QStyle,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from git_terminal.core.commands import GitCommandSpec, build_command_catalog
from git_terminal.core.models import GitResult, GitStatusItem, RiskLevel
from git_terminal.core.runner import GitRunner
from git_terminal.core.safety import classify_git_command
from git_terminal.core.encoding import completed_process_text, decode_command_output, utf8_subprocess_env
from git_terminal.ui.workers import GitCommandWorker, ShellCommandWorker
from git_terminal.ui.theme import ACCENTS, apply_theme
from git_terminal.i18n import LANGUAGE_MODES, LanguageService, make_key
from git_terminal.ui.commit_graph import CommitGraphView, GraphCommit
from git_terminal.ui.vscode_shell import ActivityBar, BottomPanel, SidePanel, TopCommandBar


class CloneDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Clone Repository")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(7)
        self.url = QLineEdit()
        self.url.setPlaceholderText("git@github.com:org/repo.git 或 https://...")
        self.dest = QLineEdit()
        folder_action = self.dest.addAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        folder_action.setToolTip("从资源管理器选择文件夹；路径不存在时会自动创建")
        folder_action.triggered.connect(self._browse)
        field_width = 450
        for edit in (self.url, self.dest):
            edit.setMinimumHeight(22)
            edit.setMaximumHeight(24)
            edit.setFixedWidth(field_width)
            edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        form.addRow("远程 URL", self.url)
        form.addRow("目标目录", self.dest)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        current = self.dest.text().strip()
        base = Path(current).expanduser() if current else Path.cwd()
        if not base.exists():
            base = base.parent if base.suffix else base
        directory = QFileDialog.getExistingDirectory(self, "选择 clone 到的父目录", str(base if base.exists() else Path.cwd()))
        if directory:
            path = Path(directory).expanduser()
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                QMessageBox.warning(self, "目录创建失败", f"无法创建目录：{path}\n{exc}")
                return
            self.dest.setText(str(path))


class RemoteDialog(QDialog):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(7)
        self.name = QLineEdit()
        self.url = QLineEdit()
        for edit in (self.name, self.url):
            edit.setMinimumHeight(22)
            edit.setMaximumHeight(24)
            edit.setFixedWidth(420)
            edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        form.addRow("remote 名称", self.name)
        form.addRow("URL", self.url)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Git Terminal")
        icon_path = Path(__file__).resolve().parents[1] / "assets" / "git_terminal_icon.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1040, 620)
        self.runner = GitRunner()
        self.git_version_text = ""
        self.config_path = self._default_config_path()
        base_config = self._load_config()
        self.language_mode = str(base_config.get("language_mode", "default"))
        self.language = LanguageService(self.language_mode)
        self.recent_repositories = self._load_recent_repositories()
        self.custom_buttons = self._load_custom_buttons()
        self.command_catalog = build_command_catalog()
        self._threads: List[Tuple[QThread, GitCommandWorker]] = []
        self._option_checks: List[QCheckBox] = []
        self._suppress_preview = False
        self.theme_mode = "dark"
        self.theme_accent = "blue"
        self._left_collapsed = False
        self._right_collapsed = False
        self._bottom_collapsed = False
        self._last_left_width = 220
        self._last_right_width = 260
        self._last_bottom_height = 190
        self._initial_center_sizes = [430, 130]
        self._initial_horizontal_sizes = [220, 580, 220]
        self._git_config_tree_updating = False
        self._cli_install_scripts: list[Path] = []

        self._build_actions()
        self._build_ui()
        self._wire_shortcuts()
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self, self.theme_mode, self.theme_accent)
        self._apply_activity_icon_theme()
        self.apply_language()
        self.detect_environment()
        self.refresh_all()

    # ------------------------------------------------------------------
    # Local configuration
    # ------------------------------------------------------------------
    def _default_config_path(self) -> Path:
        return Path.home() / ".git_terminal" / "config.json"

    def _load_config(self) -> dict:
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save_config(self, config: dict) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            if hasattr(self, "command_log"):
                self.append_log(f"保存配置失败：{exc}")

    def _load_recent_repositories(self) -> list[str]:
        config = self._load_config()
        values = config.get("recent_repositories", [])
        if not isinstance(values, list):
            return []
        result: list[str] = []
        for value in values:
            if isinstance(value, str) and value and value not in result:
                result.append(value)
        return result[:20]

    def _save_recent_repositories(self) -> None:
        config = self._load_config()
        config["recent_repositories"] = self.recent_repositories[:20]
        self._save_config(config)

    def _load_custom_buttons(self) -> list[dict[str, str]]:
        config = self._load_config()
        raw = config.get("custom_buttons", [])
        if not isinstance(raw, list):
            return []
        buttons: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            commands = str(item.get("commands", "")).strip()
            if name and commands and not any(existing["name"] == name for existing in buttons):
                buttons.append({"name": name, "commands": commands})
        return buttons[:40]

    def _save_custom_buttons(self) -> None:
        config = self._load_config()
        config["custom_buttons"] = self.custom_buttons[:40]
        self._save_config(config)

    def register_custom_button(self, name: str, commands: str, persist: bool = True) -> bool:
        """Public extension hook for user scripts/plugins.

        Example:
            window.register_custom_button("Sync", "git fetch --all --prune\ngit status -sb")
        """
        name = str(name).strip()
        commands = str(commands).strip()
        if not name or not commands:
            return False
        if any(item.get("name") == name for item in self.custom_buttons):
            return False
        self.custom_buttons.append({"name": name, "commands": commands})
        if persist:
            self._save_custom_buttons()
        if hasattr(self, "context_scroll"):
            self._rebuild_context_actions()
        return True

    def _remember_repository(self, path: str | Path) -> None:
        repo = str(Path(path).expanduser().resolve())
        self.recent_repositories = [repo] + [p for p in self.recent_repositories if p != repo]
        self.recent_repositories = self.recent_repositories[:20]
        self._save_recent_repositories()
        if hasattr(self, "navigator"):
            self._populate_navigator()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_actions(self) -> None:
        self.open_repo_action = QAction("打开本地仓库...", self)
        self.open_repo_action.triggered.connect(self.open_repository)
        self.init_repo_action = QAction("创建/初始化本地仓库...", self)
        self.init_repo_action.triggered.connect(self.init_repository)
        self.clone_repo_action = QAction("Clone 远程仓库...", self)
        self.clone_repo_action.triggered.connect(self.clone_repository)
        self.refresh_action = QAction("刷新全部", self)
        self.refresh_action.triggered.connect(self.refresh_all)
        self.copy_command_action = QAction("复制最后命令", self)
        self.copy_command_action.triggered.connect(self.copy_last_command)

        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction(self.open_repo_action)
        file_menu.addAction(self.init_repo_action)
        file_menu.addAction(self.clone_repo_action)
        file_menu.addAction("打开仓库文件夹", self.open_repo_folder)
        file_menu.addAction("创建 GitHub 远程仓库...", self.create_remote_repository)
        file_menu.addSeparator()
        file_menu.addAction(self.refresh_action)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close)

        repo_menu = self.menuBar().addMenu("仓库")
        repo_menu.addAction("Status -sb", lambda: self.run_git_command(["status", "-sb"], callback=lambda _: self.refresh_all()))
        repo_menu.addAction("打开 Raw Git 终端", lambda: self.set_bottom_panel_visible(True))
        repo_menu.addAction("查看配置", lambda: self.run_git_command(["config", "--list", "--show-origin"], callback=self.show_result_in_log))
        repo_menu.addAction("设置 user.name...", self.set_git_user_name)
        repo_menu.addAction("设置 user.email...", self.set_git_user_email)
        repo_menu.addAction("刷新仓库状态", self.refresh_all)

        changes_menu = self.menuBar().addMenu("更改")
        changes_menu.addAction("git add -A / 添加全部", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all()))
        changes_menu.addAction("Unstage All", lambda: self.run_git_command(["restore", "--staged", "."], callback=lambda _: self.refresh_all()))
        changes_menu.addAction("Add All + Commit...", self.commit_changes)
        changes_menu.addAction("Commit Only...", self.commit_staged_only)
        changes_menu.addAction("Amend --no-edit", lambda: self.run_git_command(["commit", "--amend", "--no-edit"], callback=lambda _: self.refresh_all()))
        changes_menu.addAction("Diff", lambda: self.run_git_command(["diff"], callback=self.show_result_in_log))
        changes_menu.addAction("Diff --staged", lambda: self.run_git_command(["diff", "--staged"], callback=self.show_result_in_log))
        changes_menu.addAction("Clean -fd", lambda: self.run_git_command(["clean", "-fd"], callback=lambda _: self.refresh_all()))

        branch_menu = self.menuBar().addMenu("分支")
        branch_menu.addAction("创建分支...", self.create_branch_from_menu)
        branch_menu.addAction("切换分支...", self.switch_branch_from_menu)
        branch_menu.addAction("分支列表", lambda: self.tabs.setCurrentIndex(2) if hasattr(self, "tabs") else None)
        branch_menu.addAction("Fetch 后刷新图", lambda: self.run_git_command(["fetch", "--all", "--prune"], callback=lambda _: self.refresh_all(), timeout=300))
        branch_menu.addAction("Merge...", self.merge_branch_from_menu)
        branch_menu.addAction("Rebase...", self.rebase_branch_from_menu)
        branch_menu.addAction("Reflog", lambda: self.run_git_command(["reflog", "--date=iso"], callback=self.show_result_in_log))

        remote_menu = self.menuBar().addMenu("远程")
        remote_menu.addAction("Remote -v", lambda: self.run_git_command(["remote", "-v"], callback=self.show_result_in_log))
        remote_menu.addAction("添加 Remote...", self.add_remote)
        remote_menu.addAction("设置 Remote URL...", self.set_remote_url)
        remote_menu.addSeparator()
        remote_menu.addAction("Fetch", lambda: self.run_git_command(["fetch"], callback=lambda _: self.refresh_all(), timeout=300))
        remote_menu.addAction("Fetch --all --prune", lambda: self.run_git_command(["fetch", "--all", "--prune"], callback=lambda _: self.refresh_all(), timeout=300))
        remote_menu.addAction("Pull", lambda: self.run_git_command(["pull"], callback=lambda _: self.refresh_all(), timeout=300))
        remote_menu.addAction("Pull --ff-only", lambda: self.run_git_command(["pull", "--ff-only"], callback=lambda _: self.refresh_all(), timeout=300))
        remote_menu.addAction("Pull --rebase", lambda: self.run_git_command(["pull", "--rebase"], callback=lambda _: self.refresh_all(), timeout=300))
        remote_menu.addAction("Push", lambda: self.run_git_command(["push"], callback=lambda _: self.refresh_all(), timeout=300))
        remote_menu.addAction("Push -u...", self.push_current_branch_upstream_from_menu)
        remote_menu.addAction("Push --tags", lambda: self.run_git_command(["push", "--tags"], callback=lambda _: self.refresh_all(), timeout=300))
        remote_menu.addAction("删除远程分支...", self.delete_remote_branch)

        tag_stash_menu = self.menuBar().addMenu("标签/Stash")
        tag_stash_menu.addAction("创建标签...", self.create_tag_from_menu)
        tag_stash_menu.addAction("Push --tags", lambda: self.run_git_command(["push", "--tags"], callback=lambda _: self.refresh_all(), timeout=300))
        tag_stash_menu.addAction("Stash Push -u", self.stash_push)
        tag_stash_menu.addAction("Stash List", lambda: self.run_git_command(["stash", "list"], callback=self.show_result_in_log))
        tag_stash_menu.addAction("Stash Pop Selected", self.stash_pop)

        advanced_menu = self.menuBar().addMenu("高级")
        advanced_menu.addAction("全部 Git 命令", lambda: self.tabs.setCurrentIndex(7) if hasattr(self, "tabs") else None)
        advanced_menu.addAction("Object Inspector", lambda: self.tabs.setCurrentIndex(6) if hasattr(self, "tabs") else None)
        advanced_menu.addAction("fsck --full", lambda: self.run_git_command(["fsck", "--full"], callback=self.show_result_in_log, timeout=300))
        advanced_menu.addAction("gc", lambda: self.run_git_command(["gc"], callback=self.show_result_in_log, timeout=300))
        advanced_menu.addAction("count-objects -vH", lambda: self.run_git_command(["count-objects", "-vH"], callback=self.show_result_in_log))
        advanced_menu.addSeparator()
        advanced_menu.addAction("Worktree Add...", self.worktree_add_from_menu)
        advanced_menu.addAction("Worktree Remove...", self.worktree_remove_from_menu)
        advanced_menu.addAction("Submodule Add...", self.submodule_add_from_menu)
        advanced_menu.addAction("Submodule Update --init --recursive", lambda: self.run_git_command(["submodule", "update", "--init", "--recursive"], callback=self.show_result_in_log, timeout=900))
        advanced_menu.addAction("LFS Track...", self.lfs_track_from_menu)
        advanced_menu.addAction("Bisect Start", lambda: self.run_git_command(["bisect", "start"], callback=self.show_result_in_log))
        advanced_menu.addAction("Bisect Good...", self.bisect_good_from_menu)
        advanced_menu.addAction("Bisect Bad...", self.bisect_bad_from_menu)
        advanced_menu.addAction("Bisect Reset", lambda: self.run_git_command(["bisect", "reset"], callback=self.show_result_in_log))
        advanced_menu.addSeparator()
        advanced_menu.addAction("复制最后命令", self.copy_last_command)

        view_menu = self.menuBar().addMenu("视图")
        view_menu.addAction("显示/隐藏左侧栏", self.toggle_left_sidebar)
        view_menu.addAction("显示/隐藏右侧栏", self.toggle_right_sidebar)
        view_menu.addAction("显示/隐藏底部栏", self.toggle_bottom_panel)
        view_menu.addAction("放大/缩小终端", self.toggle_bottom_maximized)
        view_menu.addSeparator()
        view_menu.addAction("工作区", lambda: self.tabs.setCurrentIndex(0) if hasattr(self, "tabs") else None)
        view_menu.addAction("历史", lambda: self.tabs.setCurrentIndex(1) if hasattr(self, "tabs") else None)
        view_menu.addAction("分支", lambda: self.tabs.setCurrentIndex(2) if hasattr(self, "tabs") else None)
        view_menu.addAction("远程", lambda: self.tabs.setCurrentIndex(3) if hasattr(self, "tabs") else None)

        appearance_menu = self.menuBar().addMenu("外观")
        self._build_theme_menu(appearance_menu)

        platform_menu = self.menuBar().addMenu("平台")
        platform_menu.addAction("GitHub auth status", lambda: self.run_external_command(["gh", "auth", "status"]))
        platform_menu.addAction("GitHub repo list", lambda: self.run_external_command(["gh", "repo", "list", "--limit", "50"]))
        platform_menu.addAction("GitHub create repo...", self.create_remote_repository)
        platform_menu.addAction("GitLab auth status", lambda: self.run_external_command(["glab", "auth", "status"]))

        help_menu = self.menuBar().addMenu("帮助")
        help_menu.addAction("快捷键", self.show_shortcuts)
        help_menu.addAction("原生命令示例", self.show_terminal_help)
        help_menu.addAction("关于 Git Terminal", self.show_about)

        # The uploaded template uses its own top command bar as the visible menu.
        # Hide the native menu bar so no blank row remains above the template.
        native_menu = self.menuBar()
        native_menu.clear()
        native_menu.setNativeMenuBar(False)
        native_menu.setMinimumHeight(0)
        native_menu.setMaximumHeight(0)
        native_menu.setFixedHeight(0)
        native_menu.hide()
        zero_menu = QWidget(self)
        zero_menu.setObjectName("nativeMenuSpacer")
        zero_menu.setFixedHeight(0)
        zero_menu.setMinimumHeight(0)
        zero_menu.setMaximumHeight(0)
        self.setMenuWidget(zero_menu)

    def _build_theme_menu(self, appearance_menu) -> None:
        mode_group = QActionGroup(self)
        mode_group.setExclusive(True)
        self.dark_theme_action = QAction("深色模式", self)
        self.dark_theme_action.setCheckable(True)
        self.light_theme_action = QAction("浅色模式", self)
        self.light_theme_action.setCheckable(True)
        self.dark_theme_action.setChecked(self.theme_mode == "dark")
        self.light_theme_action.setChecked(self.theme_mode == "light")
        mode_group.addAction(self.dark_theme_action)
        mode_group.addAction(self.light_theme_action)
        self.dark_theme_action.triggered.connect(lambda: self.change_theme_mode("dark"))
        self.light_theme_action.triggered.connect(lambda: self.change_theme_mode("light"))
        appearance_menu.addAction(self.dark_theme_action)
        appearance_menu.addAction(self.light_theme_action)
        accent_menu = appearance_menu.addMenu("配色")
        accent_group = QActionGroup(self)
        accent_group.setExclusive(True)
        self.accent_actions = getattr(self, "accent_actions", {})
        for accent_key, label in [("blue", "蓝色"), ("purple", "紫色"), ("green", "绿色"), ("orange", "橙色")]:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(self.theme_accent == accent_key)
            action.triggered.connect(lambda _=False, key=accent_key: self.change_theme_accent(key))
            accent_group.addAction(action)
            accent_menu.addAction(action)
            self.accent_actions[accent_key] = action

    def _build_ui(self) -> None:
        # Use the uploaded VS Code-style template layout without changing its
        # core logic: top command bar + activity bar + left side bar + center
        # workspace + right side bar + bottom panel with terminal input.
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.top_bar = TopCommandBar()
        self._build_visible_top_menus()
        root_layout.addWidget(self.top_bar)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.activity_bar = ActivityBar()
        content_layout.addWidget(self.activity_bar)

        self.horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.horizontal_splitter.setChildrenCollapsible(True)
        self.horizontal_splitter.setHandleWidth(1)
        self.horizontal_splitter.splitterMoved.connect(self._on_horizontal_splitter_moved)

        self.left_sidebar = SidePanel("GIT TERMINAL", side="left", min_size=0)
        self.left_sidebar.set_collapse_callback(lambda: self.set_left_sidebar_visible(False))
        self.left_sidebar.add_header_action("+").clicked.connect(self.open_repository)
        self.left_sidebar.add_header_action("↻").clicked.connect(self.refresh_all)
        self.left_sidebar.add_header_action("⋯").clicked.connect(self.show_terminal_help)
        self.navigator = QTreeWidget()
        self.navigator.setHeaderHidden(True)
        self.navigator.setMinimumWidth(0)
        self.navigator.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.navigator.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.navigator.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._populate_navigator()
        self.navigator.itemClicked.connect(self._navigator_clicked)
        self.left_sidebar.body_layout.addWidget(self.navigator)

        self.center_splitter = QSplitter(Qt.Orientation.Vertical)
        self.center_splitter.setChildrenCollapsible(False)
        self.center_splitter.setHandleWidth(1)
        self.center_splitter.setMinimumWidth(120)
        self.center_splitter.splitterMoved.connect(self._on_center_splitter_moved)

        workspace = QWidget()
        self.workspace_container = workspace
        workspace.setMinimumHeight(150)
        self.workspace_stack = QStackedLayout(workspace)
        self.workspace_stack.setContentsMargins(0, 0, 0, 0)
        self.workspace_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self.workspace_content = QWidget()
        workspace_layout = QVBoxLayout(self.workspace_content)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("editorTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(False)
        self.tabs.setMovable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().hide()
        self.tabs.setMinimumWidth(80)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        workspace_layout.addWidget(self.tabs, 1)
        self.workspace_stack.addWidget(self.workspace_content)

        self.workspace_overlay = QFrame()
        self.workspace_overlay.setObjectName("workspaceOverlay")
        self.workspace_overlay.setVisible(False)
        overlay_outer = QVBoxLayout(self.workspace_overlay)
        overlay_outer.setContentsMargins(18, 18, 18, 18)
        overlay_outer.setSpacing(10)

        overlay_top = QHBoxLayout()
        self.workspace_prompt_back = QPushButton("← 返回")
        self.workspace_prompt_back.setObjectName("workspacePromptBackButton")
        self.workspace_prompt_back.setMinimumWidth(86)
        self.workspace_prompt_back.setFixedHeight(30)
        self.workspace_prompt_back.clicked.connect(self._cancel_workspace_prompt)
        overlay_top.addWidget(self.workspace_prompt_back, 0, Qt.AlignmentFlag.AlignLeft)
        overlay_top.addStretch(1)
        overlay_outer.addLayout(overlay_top)
        overlay_outer.addStretch(1)

        overlay_card = QFrame()
        overlay_card.setObjectName("workspaceOverlayCard")
        card = QVBoxLayout(overlay_card)
        card.setContentsMargins(20, 18, 20, 18)
        card.setSpacing(10)
        self.workspace_prompt_title = QLabel("")
        self.workspace_prompt_title.setObjectName("workspacePromptTitle")
        self.workspace_prompt_message = QLabel("")
        self.workspace_prompt_message.setObjectName("workspacePromptMessage")
        self.workspace_prompt_message.setWordWrap(True)
        self.workspace_prompt_form_widget = QWidget()
        self.workspace_prompt_form = QFormLayout(self.workspace_prompt_form_widget)
        self.workspace_prompt_form.setContentsMargins(0, 0, 0, 0)
        self.workspace_prompt_form.setSpacing(8)
        self.workspace_prompt_fields = {}
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.workspace_prompt_cancel = QPushButton("取消")
        self.workspace_prompt_cancel.setObjectName("workspacePromptCancelButton")
        self.workspace_prompt_cancel.setMinimumWidth(86)
        self.workspace_prompt_cancel.setFixedHeight(30)
        self.workspace_prompt_cancel.clicked.connect(self._cancel_workspace_prompt)
        self.workspace_prompt_ok = QPushButton("确定")
        self.workspace_prompt_ok.setObjectName("workspacePromptOkButton")
        self.workspace_prompt_ok.setMinimumWidth(86)
        self.workspace_prompt_ok.setFixedHeight(30)
        self.workspace_prompt_ok.clicked.connect(self._submit_workspace_prompt)
        button_row.addWidget(self.workspace_prompt_cancel)
        button_row.addWidget(self.workspace_prompt_ok)
        card.addWidget(self.workspace_prompt_title)
        card.addWidget(self.workspace_prompt_message)
        card.addWidget(self.workspace_prompt_form_widget)
        card.addLayout(button_row)
        overlay_outer.addWidget(overlay_card, 0, Qt.AlignmentFlag.AlignHCenter)
        overlay_outer.addStretch(2)
        self.workspace_stack.addWidget(self.workspace_overlay)

        self.bottom_panel = BottomPanel()
        self.bottom_panel.set_hide_callback(lambda: self.set_bottom_panel_visible(False))
        self._build_log_bar()
        # Bottom panel follows the uploaded template area but is now terminal-only:
        # no useless bottom tab strip, no hidden placeholder panels.
        self.bottom_panel.body_layout.addWidget(self.log_bar)

        self.workspace_scroll = QScrollArea()
        self.workspace_scroll.setObjectName("workspaceScroll")
        self.workspace_scroll.setWidgetResizable(True)
        self.workspace_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.workspace_scroll.setMinimumHeight(80)
        self.workspace_scroll.setWidget(workspace)
        self.center_splitter.addWidget(self.workspace_scroll)
        self.center_splitter.addWidget(self.bottom_panel)
        self.center_splitter.setStretchFactor(0, 3)
        self.center_splitter.setStretchFactor(1, 1)
        self.center_splitter.setSizes(self._initial_center_sizes)

        self.right_sidebar = SidePanel("ACTIONS", side="right", min_size=0)
        self.right_sidebar.set_collapse_callback(lambda: self.set_right_sidebar_visible(False))
        self._build_context_actions()
        self.right_sidebar.body_layout.addWidget(self.context_scroll)

        self.horizontal_splitter.addWidget(self.left_sidebar)
        self.horizontal_splitter.addWidget(self.center_splitter)
        self.horizontal_splitter.addWidget(self.right_sidebar)
        self.horizontal_splitter.setSizes(self._initial_horizontal_sizes)

        content_layout.addWidget(self.horizontal_splitter)
        root_layout.addWidget(content, 1)
        self._build_bottom_status_strip()
        root_layout.addWidget(self.bottom_status_strip)
        self.setCentralWidget(root)

        self.top_bar.left_sidebar_button.clicked.connect(self.toggle_left_sidebar)
        self.top_bar.right_sidebar_button.clicked.connect(self.toggle_right_sidebar)
        self.top_bar.bottom_panel_button.clicked.connect(self.toggle_bottom_panel)
        self.top_bar.refresh_button.clicked.connect(self.refresh_all)
        self.top_bar.command_center.returnPressed.connect(self.run_command_center)

        activity_handlers = [
            lambda _checked=False: (self.tabs.setCurrentIndex(0), self.refresh_worktree()),
            lambda _checked=False: (self.tabs.setCurrentIndex(1), self.refresh_history(all_branches=True)),
            lambda _checked=False: (self.tabs.setCurrentIndex(2), self.refresh_branch_graph()),
            lambda _checked=False: (self.tabs.setCurrentIndex(3), self.refresh_remotes()),
            lambda _checked=False: (self.tabs.setCurrentIndex(4), self.refresh_tags_stash()),
            lambda _checked=False: self.tabs.setCurrentIndex(6),
            lambda _checked=False: self.tabs.setCurrentIndex(8),
            lambda _checked=False: (self.set_bottom_panel_visible(True), self.raw_command.setFocus()),
            lambda _checked=False: self.show_shortcuts(),
        ]
        for index, button in enumerate(self.activity_bar.buttons):
            button.clicked.connect(activity_handlers[index])
        self.activity_bar.settings_button.clicked.connect(self.show_settings_menu)
        self.activity_bar.account_button.clicked.connect(self.show_user_accounts)

        self._build_workspace_tab()
        self._build_history_tab()
        self._build_branch_tab()
        self._build_remote_tab()
        self._build_tag_stash_tab()
        self._build_conflict_tab()
        self._build_advanced_tab()
        self._build_all_commands_tab()
        self._build_platform_tab()
        self._strip_workspace_buttons()
        self._compact_ui_controls()

    def _build_bottom_status_strip(self) -> None:
        """Build a VS Code-style one-line status strip at the bottom of the window."""
        self.bottom_status_strip = QFrame()
        self.bottom_status_strip.setObjectName("statusStrip")
        self.bottom_status_strip.setFixedHeight(25)
        layout = QHBoxLayout(self.bottom_status_strip)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.status_segments: dict[str, QLabel] = {}

        def add_segment(key: str, text: str, max_width: int | None = None, stretch: int = 0) -> QLabel:
            label = QLabel(text)
            label.setObjectName("statusPathSegment" if key in {"push", "local"} else "statusSegment")
            label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            label.setFixedHeight(25)
            label.setMinimumWidth(0)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setSizePolicy(QSizePolicy.Policy.Ignored if stretch else QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            if max_width is not None:
                label.setMaximumWidth(max_width)
            self.status_segments[key] = label
            layout.addWidget(label, stretch)
            return label

        add_segment("repo", "仓库: 未打开")
        add_segment("branch", "分支: -")
        add_segment("head", "HEAD: -")
        add_segment("upstream", "Upstream: -", max_width=230)
        add_segment("sync", "↑0 ↓0")
        add_segment("dirty", "变更: 0")
        add_segment("breakdown", "暂存 0 | 修改 0 | 未跟踪 0 | 冲突 0", max_width=260)
        add_segment("mode", "Mode: -")
        add_segment("remotes", "远程: -", max_width=220)
        add_segment("push", "Push: -", max_width=320)
        add_segment("local", "Local: -", max_width=360, stretch=1)
        add_segment("git", "Git: -")

    def _set_status_segment(self, key: str, text: str, tooltip: str | None = None) -> None:
        label = getattr(self, "status_segments", {}).get(key)
        if label is None:
            return
        label.setText(text)
        label.setToolTip(tooltip if tooltip is not None else text)

    def _short_middle(self, value: str, limit: int = 56) -> str:
        value = value or "-"
        if len(value) <= limit:
            return value
        left = max(12, limit // 2 - 3)
        right = max(12, limit - left - 1)
        return value[:left] + "…" + value[-right:]

    def _sanitize_url_for_status(self, url: str) -> str:
        # Avoid leaking HTTPS credentials in the always-visible status strip.
        return re.sub(r"(https?://)([^/@:\\s]+):([^/@\\s]+)@", r"\1\2:***@", url.strip()) if url else "-"

    def _build_context_actions(self) -> None:
        """Build the right ACTIONS sidebar with collapsible groups."""
        self.context_scroll = QScrollArea()
        self.context_scroll.setObjectName("contextScroll")
        self.context_scroll.setWidgetResizable(True)
        self.context_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.context_panel = QWidget()
        self.context_panel.setMinimumWidth(0)
        self.context_panel_layout = QVBoxLayout(self.context_panel)
        self.context_panel_layout.setContentsMargins(4, 0, 4, 4)
        self.context_panel_layout.setSpacing(4)
        self.context_buttons = []
        self._populate_context_action_groups()
        self.context_scroll.setWidget(self.context_panel)

    def _rebuild_context_actions(self) -> None:
        if not hasattr(self, "context_panel_layout"):
            return
        layout = self.context_panel_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.context_buttons = []
        self._populate_context_action_groups()
        self._compact_ui_controls()

    def _populate_context_action_groups(self) -> None:
        layout = self.context_panel_layout

        def add_group(title: str, entries: list[tuple[str, Callable[[], None], bool]]) -> QGroupBox:
            box = QGroupBox(title)
            box.setObjectName("contextActionGroup")
            box.setCheckable(True)
            box.setChecked(True)
            grid = QGridLayout(box)
            grid.setContentsMargins(6, 8, 6, 6)
            grid.setHorizontalSpacing(6)
            grid.setVerticalSpacing(6)
            row = 0
            col = 0
            group_widgets: list[QPushButton] = []
            for text, handler, wide in entries:
                button = QPushButton(text)
                button.setObjectName("contextActionWideButton" if wide else "contextActionButton")
                button.setToolTip(text)
                button.clicked.connect(handler)
                self.context_buttons.append(button)
                group_widgets.append(button)
                if wide:
                    if col:
                        row += 1
                        col = 0
                    grid.addWidget(button, row, 0, 1, 2)
                    row += 1
                    col = 0
                else:
                    grid.addWidget(button, row, col)
                    col += 1
                    if col >= 2:
                        row += 1
                        col = 0
            box.toggled.connect(lambda checked, widgets=group_widgets: [w.setVisible(checked) for w in widgets])
            layout.addWidget(box)
            return box

        add_group("Repository", [
            ("Open", self.open_repository, False),
            ("Clone", self.clone_repository, False),
            ("Init", self.init_repository, False),
            ("Folder", self.open_repo_folder, False),
            ("Refresh", self.refresh_all, False),
            ("Status", lambda: self.run_git_command(["status", "-sb"], callback=lambda _: self.refresh_all()), False),
        ])
        add_group("Changes", [
            ("Add All", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all()), False),
            ("Unstage", lambda: self.run_git_command(["restore", "--staged", "."], callback=lambda _: self.refresh_all()), False),
            ("Commit", self.commit_staged_only, False),
            ("Add+Commit", self.commit_changes, False),
            ("Diff", self.show_selected_diff, False),
            ("Clean", self.clean_selected_untracked, False),
        ])
        add_group("History", [
            ("Log", lambda: self.refresh_history(all_branches=True), False),
            ("Graph", self.refresh_branch_graph, False),
            ("Show", self.show_commit_details, False),
            ("Checkout", self.checkout_selected_commit, False),
        ])
        add_group("Branch", [
            ("New", self.create_branch_from_menu, False),
            ("Switch", self.switch_branch, False),
            ("Merge", self.merge_branch_from_menu, False),
            ("Rebase", self.rebase_branch_from_menu, False),
            ("Merge To", self.merge_to_target_from_menu, False),
            ("Rebase To", self.rebase_to_target_from_menu, False),
            ("Push -u", self.push_current_branch_upstream_from_menu, True),
        ])
        add_group("Remote", [
            ("Fetch", lambda: self.run_git_command(["fetch", "--all", "--prune"], callback=lambda _: self.refresh_all(), timeout=300), False),
            ("Pull", lambda: self.run_git_command(["pull", "--ff-only"], callback=lambda _: self.refresh_all(), timeout=300), False),
            ("Push", lambda: self.run_git_command(["push"], callback=lambda _: self.refresh_all(), timeout=300), False),
            ("Remote -v", lambda: self.run_git_command(["remote", "-v"], callback=self.show_result_in_log), False),
            ("Track Existing", self.track_existing_remote_branch_from_panel, True),
            ("Push -u", self.publish_local_branch_and_track_from_panel, True),
            ("Add Remote", self.add_remote, True),
            ("SSH Auth", self.configure_provider_ssh_from_menu, True),
            ("HTTPS Auth", self.configure_provider_https_from_menu, True),
        ])
        add_group("Tags / Stash", [
            ("New Tag", self.create_tag_from_menu, False),
            ("Push Tags", lambda: self.run_git_command(["push", "--tags"], callback=lambda _: self.refresh_all(), timeout=300), False),
            ("Stash", self.stash_push, False),
            ("Stash Pop", self.stash_pop, False),
        ])
        add_group("Advanced", [
            ("All Commands", lambda: self.tabs.setCurrentIndex(7) if hasattr(self, "tabs") else None, True),
            ("Object Inspector", lambda: self.tabs.setCurrentIndex(6) if hasattr(self, "tabs") else None, True),
            ("Maintenance", lambda: self.run_git_command(["count-objects", "-vH"], callback=self.show_result_in_log), True),
        ])
        add_group("Platform", [
            ("Accounts", self.show_user_accounts, False),
            ("SSH Setup", self.configure_provider_ssh_from_menu, False),
            ("HTTPS Setup", self.configure_provider_https_from_menu, False),
            ("Test Auth", self.test_provider_auth_from_menu, False),
            ("Install gh", self.install_gh_cli, False),
            ("Install glab", self.install_glab_cli, False),
            ("GitHub", self.show_github_cli_page, False),
            ("GitLab", self.show_gitlab_cli_page, False),
        ])

        custom_entries: list[tuple[str, Callable[[], None], bool]] = [
            ("Add Custom", self.add_custom_button, False),
            ("Delete", self.delete_custom_button, False),
        ]
        for item in getattr(self, "custom_buttons", []):
            name = item.get("name", "")
            commands = item.get("commands", "")
            if name and commands:
                custom_entries.append((name, lambda _checked=False, cmds=commands: self.run_custom_button_commands(cmds), True))
        custom_box = add_group("Custom", custom_entries)
        custom_box.setToolTip(
            "用户自定义按钮。暴露接口：window.register_custom_button('Name', 'git status\\ngit fetch --all --prune')"
        )
        layout.addStretch(1)

    def _strip_workspace_buttons(self) -> None:
        """Keep the central workspace read-only/inspection oriented.

        Action buttons live in the right sidebar. Prompt overlay buttons are not
        inside self.tabs and are therefore kept visible.
        """
        if not hasattr(self, "tabs"):
            return
        for button in self.tabs.findChildren(QPushButton):
            if hasattr(self, "platform_tabs") and self.platform_tabs.isAncestorOf(button):
                button.show()
                button.setEnabled(True)
                continue
            button.hide()
            button.setEnabled(False)

    def _build_visible_top_menus(self) -> None:
        """Render a compact menu set inside the template top bar."""
        def add_button(title: str, entries: list[tuple[str, object] | None]) -> None:
            button = QToolButton()
            button.setObjectName("topMenuButton")
            button.setText(title)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            menu = QMenu(button)
            for entry in entries:
                if entry is None:
                    menu.addSeparator()
                    continue
                label, callback = entry
                menu.addAction(label, callback)
            button.setMenu(menu)
            self.top_bar.menu_layout.addWidget(button)

        add_button("文件", [
            ("打开仓库...", self.open_repository),
            ("Clone...", self.clone_repository),
            ("初始化...", self.init_repository),
            ("打开仓库文件夹", self.open_repo_folder),
            ("刷新", self.refresh_all),
        ])
        add_button("更改", [
            ("git add -A", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all())),
            ("Commit Only...", self.commit_staged_only),
            ("Add + Commit...", self.commit_changes),
            ("Diff", lambda: self.run_git_command(["diff"], callback=self.show_result_in_log)),
            ("Diff --staged", lambda: self.run_git_command(["diff", "--staged"], callback=self.show_result_in_log)),
        ])
        add_button("分支", [
            ("新建分支...", self.create_branch_from_menu),
            ("切换分支...", self.switch_branch_from_menu),
            ("Merge...", self.merge_branch_from_menu),
            ("Rebase...", self.rebase_branch_from_menu),
            ("分支图", lambda: self.tabs.setCurrentIndex(2) if hasattr(self, "tabs") else None),
        ])
        add_button("远程", [
            ("Fetch --all --prune", lambda: self.run_git_command(["fetch", "--all", "--prune"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Pull --ff-only", lambda: self.run_git_command(["pull", "--ff-only"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Push", lambda: self.run_git_command(["push"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Remote -v", lambda: self.run_git_command(["remote", "-v"], callback=self.show_result_in_log)),
            ("远程配置", self.show_ssh_remote_info),
        ])
        add_button("工具", [
            ("全部 Git 命令", lambda: self.tabs.setCurrentIndex(7) if hasattr(self, "tabs") else None),
            ("Object Inspector", lambda: self.tabs.setCurrentIndex(6) if hasattr(self, "tabs") else None),
            ("平台账户", self.show_user_accounts),
            ("Raw Terminal", lambda: (self.set_bottom_panel_visible(True), self.raw_command.setFocus()) if hasattr(self, "raw_command") else None),
        ])
        add_button("视图", [
            ("显示/隐藏左侧栏", self.toggle_left_sidebar),
            ("显示/隐藏右侧栏", self.toggle_right_sidebar),
            ("显示/隐藏底部终端", self.toggle_bottom_panel),
            ("放大/缩小终端", self.toggle_bottom_maximized),
        ])

    def activate_activity_tab(self, index: int, tab_index: int) -> None:
        self.set_left_sidebar_visible(True)
        if 0 <= tab_index < self.tabs.count():
            self.tabs.setCurrentIndex(tab_index)

    def set_left_sidebar_visible(self, visible: bool) -> None:
        self.left_sidebar.setVisible(visible)
        self.top_bar.left_sidebar_button.setChecked(visible)
        if visible:
            self.horizontal_splitter.setSizes([self._initial_horizontal_sizes[0], self._initial_horizontal_sizes[1], self._initial_horizontal_sizes[2] if self.right_sidebar.isVisible() else 0])

    def set_right_sidebar_visible(self, visible: bool) -> None:
        self.right_sidebar.setVisible(visible)
        self.top_bar.right_sidebar_button.setChecked(visible)
        if visible:
            self.horizontal_splitter.setSizes([self._initial_horizontal_sizes[0] if self.left_sidebar.isVisible() else 0, self._initial_horizontal_sizes[1], self._initial_horizontal_sizes[2]])

    def set_bottom_panel_visible(self, visible: bool) -> None:
        if not visible and getattr(self, "_bottom_maximized", False):
            self.restore_bottom_panel()
        self.bottom_panel.setVisible(visible)
        self.top_bar.bottom_panel_button.setChecked(visible)
        if visible and not getattr(self, "_bottom_maximized", False):
            self.center_splitter.setSizes(self._initial_center_sizes)

    def toggle_left_sidebar(self) -> None:
        self.set_left_sidebar_visible(not self.left_sidebar.isVisible())

    def toggle_right_sidebar(self) -> None:
        self.set_right_sidebar_visible(not self.right_sidebar.isVisible())

    def toggle_bottom_panel(self) -> None:
        self.set_bottom_panel_visible(not self.bottom_panel.isVisible())

    def _on_horizontal_splitter_moved(self, _pos: int, _index: int) -> None:
        sizes = self.horizontal_splitter.sizes()
        if len(sizes) >= 3:
            if self.left_sidebar.isVisible() and sizes[0] <= 8:
                self.set_left_sidebar_visible(False)
            if self.right_sidebar.isVisible() and sizes[2] <= 8:
                self.set_right_sidebar_visible(False)

    def _on_center_splitter_moved(self, _pos: int, _index: int) -> None:
        if getattr(self, "_bottom_maximized", False):
            return
        sizes = self.center_splitter.sizes()
        if len(sizes) >= 2 and self.bottom_panel.isVisible():
            _top, bottom = sizes[0], sizes[1]
            # Dragging up should only enlarge the terminal. Global terminal is
            # entered by the explicit view/menu button, not by a small drag.
            if bottom <= 32:
                self.set_bottom_panel_visible(False)

    def toggle_bottom_maximized(self) -> None:
        if getattr(self, "_bottom_maximized", False):
            self.restore_bottom_panel()
        else:
            self.maximize_bottom_panel()

    def maximize_bottom_panel(self) -> None:
        self._bottom_maximized = True
        self._last_center_sizes = self.center_splitter.sizes()
        self.bottom_panel.setVisible(True)
        self.top_bar.bottom_panel_button.setChecked(True)
        if hasattr(self, "workspace_scroll"):
            self.workspace_scroll.setVisible(False)
        elif hasattr(self, "workspace_container"):
            self.workspace_container.setVisible(False)
        if hasattr(self, "terminal_max_btn"):
            self.terminal_max_btn.setText("▢")
            self.terminal_max_btn.setToolTip("恢复工作区 + 底部终端布局")

    def restore_bottom_panel(self) -> None:
        self._bottom_maximized = False
        self.bottom_panel.setVisible(True)
        self.top_bar.bottom_panel_button.setChecked(True)
        if hasattr(self, "workspace_scroll"):
            self.workspace_scroll.setVisible(True)
        elif hasattr(self, "workspace_container"):
            self.workspace_container.setVisible(True)
        # 缩小终端必须回到初始布局，而不是回到拖拽前的任意尺寸。
        self.center_splitter.setSizes(self._initial_center_sizes)
        if hasattr(self, "terminal_max_btn"):
            self.terminal_max_btn.setText("▣")
            self.terminal_max_btn.setToolTip("放大终端；再次点击恢复初始底部高度")

    def run_command_center(self) -> None:
        text = self.top_bar.command_center.text().strip()
        self.top_bar.command_center.clear()
        if not text:
            return
        lower = text.lower()
        if lower in {"status", "git status"}:
            self.tabs.setCurrentIndex(0)
            self.run_git_command(["status", "-sb"], callback=lambda _: self.refresh_all())
        elif lower in {"branches", "branch"}:
            self.tabs.setCurrentIndex(2)
        elif lower in {"remotes", "remote"}:
            self.tabs.setCurrentIndex(3)
        elif lower.startswith("git "):
            self.raw_command.setText(text)
            self.run_raw_command()
        else:
            self.raw_command.setText(text)
            self.run_raw_command()

    def show_settings_menu(self) -> None:
        menu = QMenu(self)
        theme_menu = menu.addMenu(self.t("settings.theme", "主题"))
        dark = theme_menu.addAction(self.t("settings.theme.dark", "深色模式"))
        light = theme_menu.addAction(self.t("settings.theme.light", "浅色模式"))
        dark.triggered.connect(lambda: self.change_theme_mode("dark"))
        light.triggered.connect(lambda: self.change_theme_mode("light"))
        accent_menu = menu.addMenu(self.t("settings.accent", "配色"))
        for key, label in [("blue", "蓝色"), ("purple", "紫色"), ("green", "绿色"), ("orange", "橙色")]:
            accent_menu.addAction(self.t(f"settings.accent.{key}", label), lambda _checked=False, k=key: self.change_theme_accent(k))
        language_menu = menu.addMenu(self.t("settings.language", "语言"))
        language_group = QActionGroup(self)
        language_group.setExclusive(True)
        for key, label in [("zh", "中文"), ("en", "English"), ("default", "默认 / Default"), ("all", "中文 + English")]:
            action = QAction(self.t(f"settings.language.{key}", label), self)
            action.setCheckable(True)
            action.setChecked(self.language_mode == key)
            action.triggered.connect(lambda _checked=False, k=key: self.change_language_mode(k))
            language_group.addAction(action)
            language_menu.addAction(action)
        menu.addSeparator()
        menu.addAction(self.t("settings.show_left", "显示左侧栏"), lambda: self.set_left_sidebar_visible(True))
        menu.addAction(self.t("settings.show_right", "显示右侧栏"), lambda: self.set_right_sidebar_visible(True))
        menu.addAction(self.t("settings.show_bottom", "显示底部栏"), lambda: self.set_bottom_panel_visible(True))
        menu.addSeparator()
        menu.addAction(self.t("settings.about", "关于 Git Terminal"), self.show_about)
        button = getattr(self.activity_bar, "settings_button", None)
        if button is not None:
            menu_size = menu.sizeHint()
            app_bottom = self.mapToGlobal(self.rect().bottomLeft()).y()
            anchor = button.mapToGlobal(button.rect().topRight())
            x = anchor.x()
            y = max(self.mapToGlobal(self.rect().topLeft()).y(), app_bottom - menu_size.height())
            menu.exec(QPoint(x, y))
        else:
            menu.exec(self.mapToGlobal(self.rect().center()))

    # ------------------------------------------------------------------
    # Language / internationalization
    # ------------------------------------------------------------------
    def t(self, key: str, default_text: str = "") -> str:
        return self.language.text(key, default_text) if hasattr(self, "language") else default_text

    def _is_translatable_text(self, text: str) -> bool:
        if not text:
            return False
        stripped = text.strip()
        if not stripped:
            return False
        if stripped in {"▣", "▢", "⌄", "▔", "◧", "◨", "⟳", "⋯", "$ >", "‹", "›"}:
            return False
        # Do not translate pure hashes / object names / CSS-ish tokens.
        if stripped.startswith("#") or stripped.startswith("_"):
            return False
        return True

    def _language_key(self, default_text: str, prefix: str = "ui") -> str:
        return make_key(default_text, prefix)

    def _apply_text_property(self, obj, getter, setter, prop_name: str, prefix: str) -> None:
        try:
            current = getter()
        except Exception:
            return
        if not self._is_translatable_text(current):
            return
        default = obj.property(prop_name)
        if not default:
            default = current
            obj.setProperty(prop_name, default)
        key_prop = prop_name + "_key"
        key = obj.property(key_prop)
        if not key:
            key = self._language_key(str(default), prefix)
            obj.setProperty(key_prop, key)
        try:
            setter(self.t(str(key), str(default)))
        except Exception:
            return

    def apply_language(self) -> None:
        """Apply configured UI language to registered static text.

        Widgets keep their original text in dynamic properties, so switching
        zh/en/default/all does not lose the default mixed-language text.
        New or third-party text without an entry is automatically appended to
        ~/.git_terminal/language_config.json with zh/en/default/all values.
        """
        if not hasattr(self, "language"):
            return
        self.language.set_mode(getattr(self, "language_mode", "default"))
        # Window title.
        self._apply_text_property(self, self.windowTitle, self.setWindowTitle, "i18n_window_title", "window")
        # Actions, including menu actions.
        for action in self.findChildren(QAction):
            self._apply_text_property(action, action.text, action.setText, "i18n_action_text", "action")
            self._apply_text_property(action, action.toolTip, action.setToolTip, "i18n_action_tooltip", "tooltip")
        # Widgets.
        for widget in self.findChildren(QWidget):
            # QLineEdit.text() is user data, not static UI text. Only its placeholder is localized.
            if not isinstance(widget, QLineEdit) and hasattr(widget, "text") and hasattr(widget, "setText"):
                self._apply_text_property(widget, widget.text, widget.setText, "i18n_widget_text", "widget")
            if hasattr(widget, "title") and hasattr(widget, "setTitle"):
                self._apply_text_property(widget, widget.title, widget.setTitle, "i18n_widget_title", "title")
            if hasattr(widget, "placeholderText") and hasattr(widget, "setPlaceholderText"):
                self._apply_text_property(widget, widget.placeholderText, widget.setPlaceholderText, "i18n_placeholder", "placeholder")
            if hasattr(widget, "toolTip") and hasattr(widget, "setToolTip"):
                self._apply_text_property(widget, widget.toolTip, widget.setToolTip, "i18n_widget_tooltip", "tooltip")
            if isinstance(widget, QTabWidget):
                defaults = widget.property("i18n_tab_defaults")
                if not isinstance(defaults, list) or len(defaults) != widget.count():
                    defaults = [widget.tabText(i) for i in range(widget.count())]
                    widget.setProperty("i18n_tab_defaults", defaults)
                keys = widget.property("i18n_tab_keys")
                if not isinstance(keys, list) or len(keys) != widget.count():
                    keys = [self._language_key(str(defaults[i]), "tab") for i in range(widget.count())]
                    widget.setProperty("i18n_tab_keys", keys)
                for i in range(widget.count()):
                    default = str(defaults[i])
                    if self._is_translatable_text(default):
                        widget.setTabText(i, self.t(str(keys[i]), default))
        # Update checked language actions if a settings menu/action is currently alive.
        self.language.flush()

    def change_language_mode(self, mode: str) -> None:
        if mode not in LANGUAGE_MODES:
            mode = "default"
        self.language_mode = mode
        self.language.set_mode(mode)
        config = self._load_config()
        config["language_mode"] = mode
        self._save_config(config)
        self.apply_language()
        self.append_log(f"语言已切换：{LANGUAGE_MODES.get(mode, mode)}")

    def _field_suggestions(self, key: str, label: str) -> list[str]:
        text = f"{key} {label}".lower()
        if not self.runner.repo_path:
            return []
        # URL 字段必须保持自由输入；不能因为标签里有“远程”就塞入 remote 名称。
        if "url" in text or "地址" in text:
            return []
        try:
            if any(word in text for word in ["branch", "分支", "target", "onto"]):
                result = self.runner.run(["for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes"])
                if result.ok:
                    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if any(word in text for word in ["tag", "version", "版本"]):
                result = self.runner.run(["tag", "--list"])
                if result.ok:
                    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if "remote" in text or "远程" in text:
                result = self.runner.run(["remote"])
                if result.ok:
                    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except Exception:
            return []
        return []

    def _compact_field_width(self, *texts: object, folder: bool = False) -> int:
        samples = [str(text).strip() for text in texts if str(text).strip()]
        sample = max(samples, key=len) if samples else "输入"
        metrics = self.fontMetrics()
        width = metrics.horizontalAdvance(sample) + (44 if folder else 24)
        return max(132, min(width, 460))

    def _set_compact_field_size(self, widget: QWidget, width: int) -> None:
        widget.setMinimumHeight(22)
        widget.setMaximumHeight(24)
        widget.setFixedWidth(width)
        widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if isinstance(widget, QComboBox) and widget.lineEdit() is not None:
            widget.lineEdit().setMinimumHeight(20)
            widget.lineEdit().setMaximumHeight(22)

    def _prompt_label_width(self, labels: list[str]) -> int:
        metrics = self.fontMetrics()
        if not labels:
            return 96
        width = max(metrics.horizontalAdvance(label) for label in labels) + 10
        return max(92, min(width, 150))

    def _make_prompt_label(self, text: str, width: int, height: int = 22) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setFixedWidth(width)
        label.setFixedHeight(height)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return label

    def _attach_folder_picker_action(self, edit, label: str = "") -> None:
        target = edit.lineEdit() if isinstance(edit, QComboBox) and edit.lineEdit() is not None else edit
        if not isinstance(target, QLineEdit):
            return
        action = target.addAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        action.setToolTip("从资源管理器选择文件夹；路径不存在时会自动创建")
        action.triggered.connect(lambda _=False, e=edit, l=label: self._browse_folder_into(e, l))


    def request_workspace_form(
        self,
        title: str,
        message: str,
        fields: list[tuple],
        callback: Callable[[dict[str, str]], None],
    ) -> None:
        """Show a workspace-covering form with all required inputs at once.

        Field tuple format remains backward-compatible:
            (key, label, default, password)
        Optional fifth item can be "folder" to force a folder picker button.
        """
        if hasattr(self, "terminal_stack") and hasattr(self, "terminal_content"):
            self.terminal_stack.setCurrentWidget(self.terminal_content)
        self.workspace_prompt_callback = callback
        self.workspace_prompt_title.setText(self.t(self._language_key(title, "prompt.title"), title))
        self.workspace_prompt_message.setText(self.t(self._language_key(message, "prompt.message"), message))
        self._clear_workspace_prompt_form()
        self.workspace_prompt_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.workspace_prompt_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.workspace_prompt_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.workspace_prompt_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.workspace_prompt_form.setHorizontalSpacing(10)
        self.workspace_prompt_form.setVerticalSpacing(7)
        normalized_fields = []
        translated_labels: list[str] = []
        field_widths: list[int] = []
        for raw_field in fields:
            key, label, default, password = raw_field[:4]
            kind = raw_field[4] if len(raw_field) >= 5 else "auto"
            translated_label = self.t(self._language_key(str(label), "prompt.label"), str(label))
            needs_folder = self._is_folder_field(str(key), str(label), kind)
            normalized_fields.append((key, label, default, password, kind, translated_label, needs_folder))
            translated_labels.append(translated_label)
            field_widths.append(self._compact_field_width(str(default), str(label), str(key), folder=needs_folder))
        label_width = self._prompt_label_width(translated_labels)
        field_width = max(field_widths) if field_widths else 132
        self.workspace_prompt_fields = {}
        first_input = None
        for key, label, default, password, kind, translated_label, needs_folder in normalized_fields:
            is_multiline = str(kind).lower() in {"multiline", "textarea", "plain_text"} or str(key) in {"commands", "script"}
            suggestions = [] if password or is_multiline else self._field_suggestions(str(key), str(label))
            if is_multiline:
                edit = QPlainTextEdit()
                edit.setObjectName("workspacePromptTextInput")
                edit.setPlainText(str(default))
                edit.setFixedWidth(max(field_width, 300))
                edit.setFixedHeight(74)
                edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            elif suggestions:
                edit = QComboBox()
                edit.setObjectName("workspacePromptInput")
                edit.setEditable(True)
                edit.addItems(suggestions)
                if default:
                    edit.setCurrentText(str(default))
                edit.lineEdit().returnPressed.connect(self._submit_workspace_prompt)
                self._set_compact_field_size(edit, field_width)
            else:
                edit = QLineEdit()
                edit.setObjectName("workspacePromptInput")
                edit.setText(str(default))
                edit.setEchoMode(QLineEdit.EchoMode.Password if password else QLineEdit.EchoMode.Normal)
                edit.returnPressed.connect(self._submit_workspace_prompt)
                self._set_compact_field_size(edit, field_width)
            if needs_folder:
                self._attach_folder_picker_action(edit, str(label))
            label_height = 74 if is_multiline else 22
            self.workspace_prompt_form.addRow(self._make_prompt_label(translated_label, label_width, label_height), edit)
            self.workspace_prompt_fields[str(key)] = edit
            if first_input is None:
                first_input = edit
        self.workspace_overlay.setVisible(True)
        self.workspace_overlay.raise_()
        self.workspace_stack.setCurrentWidget(self.workspace_overlay)
        if first_input is not None:
            first_input.setFocus()
            if hasattr(first_input, "selectAll"):
                first_input.selectAll()
            elif hasattr(first_input, "lineEdit") and first_input.lineEdit() is not None:
                first_input.lineEdit().selectAll()

    def _is_folder_field(self, key: str, label: str, kind: object = "auto") -> bool:
        if str(kind).lower() in {"folder", "directory", "dir"}:
            return True
        text = f"{key} {label}".lower()
        return any(token in text for token in ["目录", "folder", "directory", "dir", "父目录", "worktree 路径"])

    def _browse_folder_into(self, edit, label: str = "") -> None:
        current = ""
        if hasattr(edit, "currentText"):
            current = edit.currentText()
        elif hasattr(edit, "text"):
            current = edit.text()
        base = Path(current).expanduser() if current else Path.cwd()
        if not base.exists():
            base = base.parent if base.suffix else base
        directory = QFileDialog.getExistingDirectory(self, f"选择{label or '文件夹'}", str(base if base.exists() else Path.cwd()))
        if not directory:
            return
        path = Path(directory).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "目录创建失败", f"无法创建目录：{path}\n{exc}")
            return
        if hasattr(edit, "setCurrentText"):
            edit.setCurrentText(str(path))
        elif hasattr(edit, "setText"):
            edit.setText(str(path))

    def _clear_workspace_prompt_form(self) -> None:
        if not hasattr(self, "workspace_prompt_form"):
            return
        while self.workspace_prompt_form.rowCount():
            self.workspace_prompt_form.removeRow(0)

    def request_terminal_text(
        self,
        title: str,
        message: str,
        callback: Callable[[str], None],
        default: str = "",
        password: bool = False,
    ) -> None:
        self.request_workspace_form(
            title,
            message,
            [("value", message, default, password)],
            lambda values: callback(values.get("value", "")),
        )

    def _submit_terminal_prompt(self) -> None:
        # Compatibility: old terminal prompt submit now delegates to workspace form.
        self._submit_workspace_prompt()

    def _cancel_terminal_prompt(self) -> None:
        # Compatibility: old terminal prompt cancel now delegates to workspace form.
        self._cancel_workspace_prompt()

    def _submit_workspace_prompt(self) -> None:
        values = {}
        for key, edit in getattr(self, "workspace_prompt_fields", {}).items():
            if hasattr(edit, "toPlainText"):
                values[key] = edit.toPlainText()
            elif hasattr(edit, "currentText"):
                values[key] = edit.currentText()
            else:
                values[key] = edit.text()
        callback = getattr(self, "workspace_prompt_callback", None)
        self.workspace_overlay.setVisible(False)
        self.workspace_stack.setCurrentWidget(self.workspace_content)
        self._clear_workspace_prompt_form()
        self.workspace_prompt_fields = {}
        self.workspace_prompt_callback = None
        if callback:
            try:
                callback(values)
            except Exception as exc:
                self.append_log(f"输入提交后的处理失败：{exc}")

    def _cancel_workspace_prompt(self) -> None:
        if hasattr(self, "workspace_overlay"):
            self.workspace_overlay.setVisible(False)
            self.workspace_stack.setCurrentWidget(self.workspace_content)
        self._clear_workspace_prompt_form()
        self.workspace_prompt_fields = {}
        self.workspace_prompt_callback = None
        self.set_terminal_state("warning", "CANCEL")
        self.append_log("已返回，输入已取消。")

    def create_remote_repository(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            name = values.get("name", "").strip()
            visibility = values.get("visibility", "private").strip().lower() or "private"
            if not name:
                self.append_log("创建远程仓库已取消：仓库名为空。")
                return
            if visibility not in {"private", "public"}:
                self.append_log("仓库可见性只能输入 private 或 public。")
                return
            self.run_external_command(["gh", "repo", "create", name, f"--{visibility}", "--source", ".", "--remote", "origin"])
        self.request_workspace_form(
            "创建 GitHub 远程仓库",
            "需要已安装并登录 gh CLI。所有参数一次性输入。",
            [("name", "仓库名", "", False), ("visibility", "Visibility", "private", False)],
            submitted,
        )

    def set_git_user_name(self) -> None:
        self.request_terminal_text(
            "Git user.name",
            "user.name：",
            lambda name: self.run_git_command(["config", "--global", "user.name", name.strip()], callback=lambda _: self.refresh_all()) if name.strip() else None,
        )

    def set_git_user_email(self) -> None:
        self.request_terminal_text(
            "Git user.email",
            "user.email：",
            lambda email: self.run_git_command(["config", "--global", "user.email", email.strip()], callback=lambda _: self.refresh_all()) if email.strip() else None,
        )

    def create_branch_from_menu(self) -> None:
        self.request_terminal_text(
            "创建分支",
            "分支名：",
            lambda name: self.run_git_command(["branch", name.strip()], callback=lambda _: self.refresh_all()) if name.strip() else None,
        )

    def switch_branch_from_menu(self) -> None:
        self.request_terminal_text(
            "切换分支",
            "分支名：",
            lambda name: self.run_git_command(["switch", name.strip()], callback=lambda _: self.refresh_all()) if name.strip() else None,
        )

    def merge_branch_from_menu(self) -> None:
        self.request_terminal_text(
            "Merge",
            "要合并到当前分支的分支名：",
            lambda name: self.run_git_command(["merge", name.strip()], callback=lambda _: self.refresh_all()) if name.strip() else None,
        )

    def rebase_branch_from_menu(self) -> None:
        self.request_terminal_text(
            "Rebase",
            "当前分支 rebase 到：",
            lambda name: self.run_git_command(["rebase", name.strip()], callback=lambda _: self.refresh_all()) if name.strip() else None,
        )

    def merge_to_target_from_menu(self) -> None:
        self.request_workspace_form(
            "Merge To",
            "选择要合并进当前分支的目标分支 / commit。输入框支持下拉选择已有本地/远程分支。",
            [("branch", "目标分支 / commit", "", False)],
            lambda values: self.run_git_command(["merge", values.get("branch", "").strip()], callback=lambda _: self.refresh_all()) if values.get("branch", "").strip() else None,
        )

    def rebase_to_target_from_menu(self) -> None:
        self.request_workspace_form(
            "Rebase To",
            "选择当前分支要 rebase 到的目标分支 / commit。输入框支持下拉选择已有本地/远程分支。",
            [("branch", "目标分支 / commit", "", False)],
            lambda values: self.run_git_command(["rebase", values.get("branch", "").strip()], callback=lambda _: self.refresh_all()) if values.get("branch", "").strip() else None,
        )

    def cherry_pick_from_menu(self) -> None:
        self.request_terminal_text(
            "Cherry-pick",
            "commit hash / ref：",
            lambda commit: self.run_git_command(["cherry-pick", commit.strip()], callback=lambda _: self.refresh_all()) if commit.strip() else None,
        )

    def revert_from_menu(self) -> None:
        self.request_terminal_text(
            "Revert",
            "commit hash / ref：",
            lambda commit: self.run_git_command(["revert", commit.strip()], callback=lambda _: self.refresh_all()) if commit.strip() else None,
        )

    def reset_hard_from_menu(self) -> None:
        self.request_terminal_text(
            "Reset --hard",
            "目标 commit / ref：",
            lambda target: self.run_git_command(["reset", "--hard", target.strip()], callback=lambda _: self.refresh_all()) if target.strip() else None,
        )

    def push_current_branch_upstream_from_menu(self) -> None:
        current = self.runner.run(["branch", "--show-current"]).stdout.strip()
        def submitted(values: dict[str, str]) -> None:
            remote = values.get("remote", "origin").strip() or "origin"
            branch = values.get("branch", current).strip()
            if not branch:
                self.append_log("Push -u 已取消：缺少分支名。")
                return
            self.run_git_command(["push", "-u", remote, branch], callback=lambda _: self.refresh_all(), timeout=300)
        self.request_workspace_form(
            "Push -u",
            "一次性输入 remote 和 branch。",
            [("remote", "remote", "origin", False), ("branch", "branch", current, False)],
            submitted,
        )

    def create_tag_from_menu(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            tag = values.get("tag", "").strip()
            message = values.get("message", "").strip() or tag
            if tag:
                self.run_git_command(["tag", "-a", tag, "-m", message], callback=lambda _: self.refresh_all())
        self.request_workspace_form(
            "创建标签",
            "一次性输入标签名和标签信息。",
            [("tag", "标签名", "", False), ("message", "标签信息", "", False)],
            submitted,
        )

    def worktree_add_from_menu(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            path = values.get("path", "").strip()
            ref = values.get("ref", "").strip()
            if not path:
                self.append_log("Worktree Add 已取消：缺少路径。")
                return
            target = Path(path).expanduser()
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                self.append_log(f"Worktree Add 已取消：父目录无法创建：{target.parent}\n{exc}")
                return
            self.run_git_command(["worktree", "add", str(target)] + ([ref] if ref else []), callback=lambda _: self.refresh_all(), timeout=300)
        self.request_workspace_form(
            "Worktree Add",
            "一次性输入 worktree 路径和可选 ref。",
            [("path", "worktree 路径", "", False, "folder"), ("ref", "分支 / commit / ref", "", False)],
            submitted,
        )

    def worktree_remove_from_menu(self) -> None:
        self.request_terminal_text(
            "Worktree Remove",
            "要移除的 worktree 路径：",
            lambda path: self.run_git_command(["worktree", "remove", path.strip()], callback=lambda _: self.refresh_all(), timeout=300) if path.strip() else None,
        )

    def submodule_add_from_menu(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            url = values.get("url", "").strip()
            path = values.get("path", "").strip()
            if not url:
                self.append_log("Submodule Add 已取消：缺少 URL。")
                return
            if path:
                target = Path(path).expanduser()
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                except Exception as exc:
                    self.append_log(f"Submodule Add 已取消：父目录无法创建：{target.parent}\n{exc}")
                    return
                path = str(target)
            self.run_git_command(["submodule", "add", url] + ([path] if path else []), callback=lambda _: self.refresh_all(), timeout=900)
        self.request_workspace_form(
            "Submodule Add",
            "一次性输入子模块 URL 和可选本地路径。",
            [("url", "子模块 URL", "", False), ("path", "本地路径", "", False, "folder")],
            submitted,
        )

    def lfs_track_from_menu(self) -> None:
        self.request_terminal_text(
            "Git LFS Track",
            "匹配模式，例如 *.psd / assets/**：",
            lambda pattern: self.run_git_command(["lfs", "track", pattern.strip()], callback=lambda _: self.refresh_all(), timeout=300) if pattern.strip() else None,
        )

    def bisect_good_from_menu(self) -> None:
        self.request_terminal_text(
            "Bisect Good",
            "good commit / ref（可空）：",
            lambda ref: self.run_git_command(["bisect", "good"] + ([ref.strip()] if ref.strip() else []), callback=self.show_result_in_log),
        )

    def bisect_bad_from_menu(self) -> None:
        self.request_terminal_text(
            "Bisect Bad",
            "bad commit / ref（可空）：",
            lambda ref: self.run_git_command(["bisect", "bad"] + ([ref.strip()] if ref.strip() else []), callback=self.show_result_in_log),
        )

    def _populate_navigator(self) -> None:
        self.navigator.clear()
        recent_root = QTreeWidgetItem(["Recent Repositories"])
        recent_root.setData(0, Qt.ItemDataRole.UserRole, {"kind": "recent-root"})
        self.navigator.addTopLevelItem(recent_root)
        if self.recent_repositories:
            for repo in self.recent_repositories[:10]:
                item = QTreeWidgetItem([Path(repo).name or repo])
                item.setToolTip(0, repo)
                item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "recent-repo", "path": repo})
                recent_root.addChild(item)
        else:
            empty = QTreeWidgetItem(["No recent repositories"])
            empty.setData(0, Qt.ItemDataRole.UserRole, {"kind": "recent-empty"})
            recent_root.addChild(empty)
        recent_root.setExpanded(True)

        groups = {
            "Workspace": ["Changed files", "Staged files", "Untracked files", "Ignored files"],
            "History": ["Current branch", "All branches", "Reflog", "Bisect"],
            "Refs": ["Local branches", "Remote branches", "Tags", "Worktrees"],
            "Remotes": ["origin", "upstream", "custom"],
            "Collaboration": ["GitHub", "Gitee", "GitLab", "Bitbucket", "Pull Requests", "Issues", "Releases", "CI"],
            "Advanced": ["Stash", "Submodules", "LFS", "Hooks", "Config", "Objects", "Maintenance", "Raw Commands"],
        }
        for group, children in groups.items():
            root = QTreeWidgetItem([group])
            self.navigator.addTopLevelItem(root)
            for child in children:
                root.addChild(QTreeWidgetItem([child]))
            root.setExpanded(True)

    def _add_scrollable_tab(self, page: QWidget, title: str) -> None:
        """Add a workspace page inside a scroll area so terminal resizing never compresses page controls."""
        scroll = QScrollArea()
        scroll.setObjectName("workspacePageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        page.setMinimumSize(0, 0)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, title)

    def _build_workspace_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        workspace_tabs = QTabWidget()
        workspace_tabs.setDocumentMode(True)
        workspace_tabs.setTabsClosable(False)

        status_page = QWidget()
        status_layout = QVBoxLayout(status_page)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(0)
        lists = QSplitter(Qt.Orientation.Horizontal)
        lists.setChildrenCollapsible(True)
        lists.setHandleWidth(1)
        self.changed_list = QListWidget()
        self.staged_list = QListWidget()
        self.untracked_list = QListWidget()
        for title, widget in [("Changed", self.changed_list), ("Staged", self.staged_list), ("Untracked", self.untracked_list)]:
            box = QGroupBox(title)
            box.setMinimumWidth(0)
            box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(6, 8, 6, 6)
            box_layout.addWidget(widget)
            lists.addWidget(box)
        lists.setSizes([1, 1, 1])
        status_layout.addWidget(lists, 1)
        workspace_tabs.addTab(status_page, "Status")

        diff_page = QWidget()
        diff_layout = QVBoxLayout(diff_page)
        diff_layout.setContentsMargins(0, 0, 0, 0)
        diff_hint = QLabel("Diff 以折叠树展示：文件 -> file/header -> hunk -> 具体变更行。新增/删除/元信息会高亮。")
        diff_hint.setWordWrap(True)
        diff_layout.addWidget(diff_hint)
        self.diff_tree = QTreeWidget()
        self.diff_tree.setColumnCount(3)
        self.diff_tree.setHeaderLabels(["范围", "路径 / Hunk", "内容"])
        self.diff_tree.setAlternatingRowColors(True)
        self.diff_tree.setUniformRowHeights(False)
        self.diff_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.diff_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        diff_layout.addWidget(self.diff_tree, 1)
        workspace_tabs.addTab(diff_page, "Diff")

        # Hidden compatibility buttons. Actions are exposed in the right ACTIONS bar.
        hidden_actions = QWidget()
        hidden_layout = QGridLayout(hidden_actions)
        for index, (text, handler) in enumerate([
            ("git add selected", self.stage_selected),
            ("Unstage Selected", self.unstage_selected),
            ("git add -A / 全部", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all())),
            ("Unstage All", lambda: self.run_git_command(["restore", "--staged", "."], callback=lambda _: self.refresh_all())),
            ("Restore Selected", self.restore_selected),
            ("Clean Untracked", self.clean_selected_untracked),
            ("Diff", self.show_selected_diff),
            ("Open Folder", self.open_repo_folder),
            ("Refresh", self.refresh_all),
            ("Add All + Commit...", self.commit_changes),
            ("Commit Only...", self.commit_staged_only),
        ]):
            button = QPushButton(text)
            button.clicked.connect(handler)
            hidden_layout.addWidget(button, index // 3, index % 3)
        hidden_actions.hide()
        layout.addWidget(workspace_tabs, 1)
        layout.addWidget(hidden_actions)

        for widget in (self.changed_list, self.staged_list, self.untracked_list):
            widget.currentItemChanged.connect(lambda *_: self.show_selected_diff())
            widget.itemDoubleClicked.connect(lambda *_: self.show_selected_diff())

        self._add_scrollable_tab(page, "工作区")

    def _build_history_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        self.history_tree = QTreeWidget()
        self.history_tree.setColumnCount(6)
        self.history_tree.setHeaderLabels(["Graph", "Hash", "Date", "Author", "Refs", "Message"])
        self.history_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_tree.customContextMenuRequested.connect(self._commit_context_menu)
        self.history_tree.itemClicked.connect(self.show_commit_details)
        layout.addWidget(self.history_tree, 8)
        buttons = QGridLayout()
        buttons.setHorizontalSpacing(6)
        buttons.setVerticalSpacing(4)
        for index, (text, handler) in enumerate([
            ("Log Current", lambda: self.refresh_history(all_branches=False)),
            ("Log --all", lambda: self.refresh_history(all_branches=True)),
            ("Show Commit", self.show_commit_details),
            ("Checkout Commit", self.checkout_selected_commit),
            ("Create Branch Here", self.branch_from_selected_commit),
            ("Cherry-pick", self.cherry_pick_selected_commit),
            ("Revert", self.revert_selected_commit),
            ("Reset --hard Here", self.reset_hard_selected_commit),
        ]):
            b = QPushButton(text)
            b.clicked.connect(handler)
            buttons.addWidget(b, index // 3, index % 3)
        layout.addLayout(buttons)
        self.commit_detail = QPlainTextEdit()
        self.commit_detail.setReadOnly(True)
        layout.addWidget(self.commit_detail, 2)
        self._add_scrollable_tab(page, "提交历史")

    def _build_branch_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.branch_view_tabs = QTabWidget()
        self.branch_view_tabs.setUsesScrollButtons(True)
        self.branch_view_tabs.tabBar().setExpanding(False)
        layout.addWidget(self.branch_view_tabs, 1)

        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        self.branch_list = QListWidget()
        self.branch_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.branch_list.customContextMenuRequested.connect(self._branch_context_menu)
        list_layout.addWidget(self.branch_list, 1)
        row = QGridLayout()
        row.setHorizontalSpacing(6)
        row.setVerticalSpacing(4)
        self.new_branch_name = QLineEdit()
        self.new_branch_name.setPlaceholderText("新分支名")
        row.addWidget(self.new_branch_name, 0, 0, 1, 2)
        for index, (text, handler) in enumerate([
            ("Create", self.create_branch),
            ("Switch", self.switch_branch),
            ("Delete", self.delete_branch),
            ("Merge", self.merge_branch),
            ("Rebase", self.rebase_onto_branch),
            ("Push -u", self.push_branch_upstream),
            ("Pull", lambda: self.run_git_command(["pull"], callback=lambda _: self.refresh_all(), timeout=300)),
        ]):
            b = QPushButton(text)
            b.clicked.connect(handler)
            row.addWidget(b, 1 + index // 3, index % 3)
        list_layout.addLayout(row)
        self.branch_view_tabs.addTab(list_page, "列表")

        graph_page = QWidget()
        graph_layout = QVBoxLayout(graph_page)
        graph_toolbar = QHBoxLayout()
        refresh_graph_btn = QPushButton("刷新图")
        refresh_graph_btn.clicked.connect(self.refresh_branch_graph)
        fit_graph_btn = QPushButton("适应视图")
        fit_graph_btn.clicked.connect(self.fit_branch_graph)
        graph_help = QLabel("提示：悬浮节点看信息，单击看详情，双击 checkout，右键更多操作；Ctrl+滚轮缩放。")
        graph_help.setWordWrap(True)
        graph_toolbar.addWidget(refresh_graph_btn)
        graph_toolbar.addWidget(fit_graph_btn)
        graph_toolbar.addWidget(graph_help, 1)
        graph_layout.addLayout(graph_toolbar)
        graph_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.branch_graph_view = CommitGraphView()
        self.branch_graph_view.set_theme(self.theme_mode)
        self.branch_graph_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.branch_graph_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.branch_graph_view.commitSelected.connect(self.graph_commit_selected)
        self.branch_graph_view.commitHovered.connect(self.graph_commit_selected)
        self.branch_graph_view.commitActivated.connect(self.graph_checkout_commit)
        self.branch_graph_view.commitContextRequested.connect(self.graph_commit_context_menu)
        graph_splitter.addWidget(self.branch_graph_view)
        self.branch_graph_detail = QTreeWidget()
        self.branch_graph_detail.setHeaderHidden(True)
        self.branch_graph_detail.setMinimumWidth(260)
        self.branch_graph_detail.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.branch_graph_detail.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.branch_graph_detail.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._set_branch_graph_detail_message("鼠标悬浮或单击图节点后显示 commit 详情")
        graph_splitter.addWidget(self.branch_graph_detail)
        graph_splitter.setChildrenCollapsible(False)
        graph_splitter.setStretchFactor(0, 4)
        graph_splitter.setStretchFactor(1, 2)
        graph_splitter.setSizes([620, 280])
        graph_layout.addWidget(graph_splitter, 1)
        self.branch_view_tabs.addTab(graph_page, "有向图")

        self.tabs.addTab(page, "分支")

    def _build_remote_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 0, 6, 6)
        layout.setSpacing(6)

        tracking_box = QGroupBox("Tracking / Upstream")
        tracking_layout = QGridLayout(tracking_box)
        tracking_layout.setContentsMargins(8, 8, 8, 8)
        tracking_layout.setHorizontalSpacing(8)
        tracking_layout.setVerticalSpacing(6)
        self.remote_tracking_local = QLineEdit()
        self.remote_tracking_local.setPlaceholderText("本地分支，例如 newbee2")
        self.remote_tracking_remote = QLineEdit("origin")
        self.remote_tracking_remote.setPlaceholderText("remote，例如 origin")
        self.remote_tracking_branch = QLineEdit()
        self.remote_tracking_branch.setPlaceholderText("远程分支名，默认等于本地分支")
        for edit in (self.remote_tracking_local, self.remote_tracking_remote, self.remote_tracking_branch):
            edit.setMinimumHeight(22)
            edit.setMaximumHeight(24)
            edit.setFixedWidth(180)
            edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        tracking_layout.addWidget(QLabel("本地分支"), 0, 0, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tracking_layout.addWidget(self.remote_tracking_local, 0, 1)
        tracking_layout.addWidget(QLabel("remote"), 0, 2, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tracking_layout.addWidget(self.remote_tracking_remote, 0, 3)
        tracking_layout.addWidget(QLabel("远程分支"), 0, 4, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tracking_layout.addWidget(self.remote_tracking_branch, 0, 5)
        tracking_layout.setColumnStretch(6, 1)

        fetch_tracking = QPushButton("Fetch remote branches")
        fetch_tracking.clicked.connect(self.fetch_remote_branches_from_tracking_panel)
        track_existing = QPushButton("Track existing remote branch")
        track_existing.setToolTip("绑定已存在的远程分支：git branch --set-upstream-to origin/name local")
        track_existing.clicked.connect(self.track_existing_remote_branch_from_panel)
        publish_track = QPushButton("Publish local branch + track (Push -u)")
        publish_track.setToolTip("发布新的本地分支到远程，并同时设置 tracking：git push -u origin local")
        publish_track.clicked.connect(self.publish_local_branch_and_track_from_panel)
        show_upstream = QPushButton("Show upstream")
        show_upstream.clicked.connect(self.show_current_upstream_from_panel)
        for index, button in enumerate([fetch_tracking, track_existing, publish_track, show_upstream]):
            tracking_layout.addWidget(button, 1, index)
        tracking_note = QLabel("提示：远程分支还不存在时，不要用 Track existing；应使用 Push -u，它会创建远程分支并设置 upstream。")
        tracking_note.setWordWrap(True)
        tracking_layout.addWidget(tracking_note, 2, 0, 1, 7)
        layout.addWidget(tracking_box, 0)

        self.remote_tree = QTreeWidget()
        self.remote_tree.setColumnCount(3)
        self.remote_tree.setHeaderLabels(["Remote", "Type", "URL"])
        self.remote_tree.currentItemChanged.connect(lambda *_: self._sync_remote_tracking_fields(force=True))
        layout.addWidget(self.remote_tree, 6)
        row = QGridLayout()
        row.setHorizontalSpacing(6)
        row.setVerticalSpacing(4)
        for index, (text, handler) in enumerate([
            ("remote -v", self.refresh_remotes),
            ("Add", self.add_remote),
            ("Remove", self.remove_remote),
            ("Set URL", self.set_remote_url),
            ("Track Existing", self.track_existing_remote_branch_from_panel),
            ("Push -u", self.publish_local_branch_and_track_from_panel),
            ("Create SSH Key", self.create_provider_ssh_key_from_page),
            ("SSH Auth", self.configure_provider_ssh_from_menu),
            ("HTTPS Auth", self.configure_provider_https_from_menu),
            ("Test Auth", self.test_provider_auth_from_menu),
            ("Fetch", self.fetch_remote),
            ("Fetch --prune", lambda: self.run_git_command(["fetch", "--all", "--prune"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Push", lambda: self.run_git_command(["push"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Delete Remote Branch", self.delete_remote_branch),
        ]):
            b = QPushButton(text)
            b.clicked.connect(handler)
            row.addWidget(b, index // 4, index % 4)
        layout.addLayout(row)
        self.remote_output = QPlainTextEdit()
        self.remote_output.setReadOnly(True)
        layout.addWidget(self.remote_output, 2)
        self._add_scrollable_tab(page, "远程")

    def _build_tag_stash_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setTabsClosable(False)

        tag_page = QWidget()
        tag_layout = QVBoxLayout(tag_page)
        tag_layout.setContentsMargins(6, 6, 6, 6)
        tag_layout.setSpacing(6)
        tag_tip = QLabel("Tags：用于版本发布或重要节点标记。操作按钮已移动到右侧 ACTIONS > Tags / Stash。")
        tag_tip.setWordWrap(True)
        tag_layout.addWidget(tag_tip)
        self.tag_list = QListWidget()
        tag_layout.addWidget(self.tag_list, 1)
        self.new_tag_name = QLineEdit()
        self.new_tag_name.setPlaceholderText("v1.0.0")
        tag_layout.addWidget(self.new_tag_name)
        # Hidden central buttons keep old signal wiring available but actions live in right sidebar.
        tag_buttons = QGridLayout()
        for index, (text, handler) in enumerate([
            ("Create", self.create_tag),
            ("Delete", self.delete_tag),
            ("Push", self.push_tag),
            ("Push --tags", lambda: self.run_git_command(["push", "--tags"], callback=lambda _: self.refresh_all(), timeout=300)),
        ]):
            b = QPushButton(text)
            b.clicked.connect(handler)
            tag_buttons.addWidget(b, index // 2, index % 2)
        tag_layout.addLayout(tag_buttons)
        tabs.addTab(tag_page, "Tags")

        stash_page = QWidget()
        stash_layout = QVBoxLayout(stash_page)
        stash_layout.setContentsMargins(6, 6, 6, 6)
        stash_layout.setSpacing(6)
        stash_tip = QLabel("Stash：临时保存工作区改动。操作按钮已移动到右侧 ACTIONS > Tags / Stash。")
        stash_tip.setWordWrap(True)
        stash_layout.addWidget(stash_tip)
        self.stash_list = QListWidget()
        stash_layout.addWidget(self.stash_list, 1)
        self.stash_message = QLineEdit()
        self.stash_message.setPlaceholderText("stash message")
        stash_layout.addWidget(self.stash_message)
        stash_buttons = QGridLayout()
        for index, (text, handler) in enumerate([
            ("Push -u", self.stash_push),
            ("Apply", self.stash_apply),
            ("Pop", self.stash_pop),
            ("Drop", self.stash_drop),
            ("Clear", lambda: self.run_git_command(["stash", "clear"], callback=lambda _: self.refresh_all())),
        ]):
            b = QPushButton(text)
            b.clicked.connect(handler)
            stash_buttons.addWidget(b, index // 3, index % 3)
        stash_layout.addLayout(stash_buttons)
        tabs.addTab(stash_page, "Stash")

        layout.addWidget(tabs, 1)
        self._add_scrollable_tab(page, "标签 / Stash")

    def _build_conflict_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.conflict_list = QListWidget()
        layout.addWidget(self.conflict_list)
        row = QGridLayout()
        row.setHorizontalSpacing(6)
        row.setVerticalSpacing(4)
        for index, (text, handler) in enumerate([
            ("Use ours", lambda: self.checkout_conflict_side("--ours")),
            ("Use theirs", lambda: self.checkout_conflict_side("--theirs")),
            ("Mark resolved", self.mark_conflict_resolved),
            ("Merge Continue", lambda: self.run_git_command(["merge", "--continue"], callback=lambda _: self.refresh_all())),
            ("Merge Abort", lambda: self.run_git_command(["merge", "--abort"], callback=lambda _: self.refresh_all())),
            ("Rebase Continue", lambda: self.run_git_command(["rebase", "--continue"], callback=lambda _: self.refresh_all())),
            ("Rebase Skip", lambda: self.run_git_command(["rebase", "--skip"], callback=lambda _: self.refresh_all())),
            ("Rebase Abort", lambda: self.run_git_command(["rebase", "--abort"], callback=lambda _: self.refresh_all())),
            ("Cherry-pick Continue", lambda: self.run_git_command(["cherry-pick", "--continue"], callback=lambda _: self.refresh_all())),
            ("Cherry-pick Abort", lambda: self.run_git_command(["cherry-pick", "--abort"], callback=lambda _: self.refresh_all())),
        ]):
            b = QPushButton(text)
            b.clicked.connect(handler)
            row.addWidget(b, index // 3, index % 3)
        layout.addLayout(row)
        self.conflict_preview = QPlainTextEdit()
        self.conflict_preview.setReadOnly(True)
        layout.addWidget(self.conflict_preview, 1)
        self.conflict_list.currentItemChanged.connect(lambda *_: self.show_conflict_file())
        self._add_scrollable_tab(page, "冲突")

    def _build_advanced_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        object_box = QGroupBox("Object Inspector")
        form = QFormLayout(object_box)
        self.object_command = QComboBox()
        self.object_command.addItems(["cat-file -p", "cat-file -t", "cat-file -s", "ls-tree -r", "ls-files -s", "rev-parse --short", "show-ref", "for-each-ref", "hash-object", "commit-tree", "write-tree"])
        self.object_target = QLineEdit()
        self.object_target.setPlaceholderText("HEAD / HEAD^{tree} / path / hash")
        form.addRow("命令", self.object_command)
        form.addRow("对象或参数", self.object_target)
        run_obj = QPushButton("Run Object Command")
        run_obj.clicked.connect(self.run_object_command)
        form.addRow(run_obj)
        layout.addWidget(object_box)

        maintenance_box = QGroupBox("Repository Maintenance")
        maintenance_layout = QGridLayout(maintenance_box)
        maintenance_layout.setHorizontalSpacing(6)
        maintenance_layout.setVerticalSpacing(4)
        for index, (text, args) in enumerate([
            ("count-objects -vH", ["count-objects", "-vH"]),
            ("fsck --full", ["fsck", "--full"]),
            ("gc", ["gc"]),
            ("reflog", ["reflog", "--date=iso"]),
            ("archive HEAD", ["archive", "--format=zip", "HEAD", "-o", "git-terminal-archive.zip"]),
            ("bundle --all", ["bundle", "create", "git-terminal.bundle", "--all"]),
            ("maintenance run", ["maintenance", "run"]),
        ]):
            b = QPushButton(text)
            b.clicked.connect(lambda _, a=args: self.run_git_command(a, callback=self.show_result_in_log, timeout=300))
            maintenance_layout.addWidget(b, index // 3, index % 3)
        layout.addWidget(maintenance_box)

        config_box = QGroupBox("Config / Hooks / LFS / Submodule 快捷入口")
        config_layout = QGridLayout(config_box)
        config_layout.setHorizontalSpacing(6)
        config_layout.setVerticalSpacing(4)
        for index, (text, args) in enumerate([
            ("config --list --show-origin", ["config", "--list", "--show-origin"]),
            ("submodule status", ["submodule", "status", "--recursive"]),
            ("submodule update", ["submodule", "update", "--init", "--recursive"]),
            ("lfs status", ["lfs", "status"]),
            ("worktree list", ["worktree", "list"]),
            ("bisect log", ["bisect", "log"]),
            ("hooks path", ["config", "--get", "core.hooksPath"]),
            ("ignored files", ["status", "--ignored", "-s"]),
        ]):
            b = QPushButton(text)
            b.clicked.connect(lambda _, a=args: self.run_git_command(a, callback=self.show_result_in_log, timeout=300))
            config_layout.addWidget(b, index // 3, index % 3)
        layout.addWidget(config_box)

        self.advanced_output = QPlainTextEdit()
        self.advanced_output.setReadOnly(True)
        layout.addWidget(self.advanced_output, 1)
        self._add_scrollable_tab(page, "专家模式")

    def _build_all_commands_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("完整 Git 命令入口：从本机 git help -a 动态发现命令，并叠加内置常用选项。任何 Git 子命令都可以在这里带参数执行。")
        header.setWordWrap(True)
        layout.addWidget(header)

        form_box = QGroupBox("高级参数面板")
        form = QFormLayout(form_box)
        self.command_combo = QComboBox()
        for name, spec in self.command_catalog.items():
            self.command_combo.addItem(f"{name}  [{spec.category}]", name)
        self.command_combo.currentIndexChanged.connect(self._command_changed)
        self.command_args = QLineEdit()
        self.command_args.setPlaceholderText("参数，例如 --all --prune 或 origin main")
        self.command_args.textChanged.connect(self.update_command_preview)
        self.options_box = QGroupBox("常用选项")
        self.options_layout = QHBoxLayout(self.options_box)
        self.options_layout.addStretch(1)
        self.command_preview = QLineEdit()
        self.command_preview.setReadOnly(True)
        self.command_desc = QLabel()
        self.command_desc.setWordWrap(True)
        form.addRow("Git 命令", self.command_combo)
        form.addRow("参数", self.command_args)
        form.addRow(self.options_box)
        form.addRow("预览", self.command_preview)
        form.addRow("说明", self.command_desc)
        layout.addWidget(form_box)

        examples_box = QGroupBox("示例")
        examples_layout = QVBoxLayout(examples_box)
        self.command_examples = QListWidget()
        self.command_examples.itemDoubleClicked.connect(self.use_command_example)
        examples_layout.addWidget(self.command_examples)
        layout.addWidget(examples_box)

        row = QGridLayout()
        row.setHorizontalSpacing(6)
        row.setVerticalSpacing(4)
        for index, (text, handler) in enumerate([
            ("Run", self.run_advanced_command),
            ("Copy", lambda: QApplication.clipboard().setText(self.command_preview.text())),
            ("Open Help", self.open_selected_command_help),
            ("Refresh git help -a", self.reload_command_catalog),
        ]):
            b = QPushButton(text)
            b.clicked.connect(handler)
            row.addWidget(b, index // 3, index % 3)
        layout.addLayout(row)

        self.all_commands_output = QPlainTextEdit()
        self.all_commands_output.setReadOnly(True)
        layout.addWidget(self.all_commands_output, 1)
        self._add_scrollable_tab(page, "全部命令")
        self._command_changed()

    def _build_platform_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(
            "平台与 Git 配置集中在这里：本地 Git 功能不依赖平台登录；SSH / HTTPS / CLI / Git config 都可以独立配置和测试。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self.platform_tabs = QTabWidget()
        platform_tabs = self.platform_tabs
        platform_tabs.setObjectName("platformTabs")
        platform_tabs.setDocumentMode(True)
        platform_tabs.setTabsClosable(False)

        def add_command_grid(parent_layout: QVBoxLayout, title: str, entries: list[tuple[str, list[str] | Callable[[], None]]], columns: int = 3) -> None:
            box = QGroupBox(title)
            grid = QGridLayout(box)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(6)
            for index, (text, command) in enumerate(entries):
                button = QPushButton(text)
                button.setToolTip(text)
                if callable(command):
                    button.clicked.connect(command)
                else:
                    button.clicked.connect(lambda _=False, c=command: self.run_external_command(c))
                grid.addWidget(button, index // columns, index % columns)
            parent_layout.addWidget(box)

        # Git config page -------------------------------------------------
        git_config = QWidget()
        git_config_layout = QVBoxLayout(git_config)
        git_config_layout.setSpacing(8)
        git_config_tip = QLabel(
            "Git 配置页：上方直接列出 global/local/system 配置，包括代理、端口、credential、SSH 命令等；下方保留单项编辑。"
        )
        git_config_tip.setWordWrap(True)
        git_config_layout.addWidget(git_config_tip)
        self.git_config_status = QLabel("Git 配置：刷新后直接列出所有配置项；可直接双击 Key/Value 编辑，保存后会执行 git config。")
        self.git_config_status.setObjectName("ProviderStatusLabel")
        self.git_config_status.setWordWrap(True)
        git_config_layout.addWidget(self.git_config_status)

        config_list_box = QGroupBox("Git config 列表")
        config_list_layout = QVBoxLayout(config_list_box)
        self.git_config_tree = QTreeWidget()
        self.git_config_tree.setColumnCount(4)
        self.git_config_tree.setHeaderLabels(["作用域", "来源", "Key", "Value"])
        self.git_config_tree.setRootIsDecorated(False)
        self.git_config_tree.setAlternatingRowColors(True)
        self.git_config_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.git_config_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.git_config_tree.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.git_config_tree.itemSelectionChanged.connect(self._copy_selected_git_config_to_editor)
        self.git_config_tree.itemChanged.connect(self._git_config_tree_item_changed)
        config_list_layout.addWidget(self.git_config_tree, 1)
        config_list_buttons = QHBoxLayout()
        for text, handler in [
            ("刷新全部", self.refresh_git_config_list_all),
            ("只看 global", lambda: self.refresh_git_config_list_scope("global")),
            ("只看 local", lambda: self.refresh_git_config_list_scope("local")),
            ("只看 system", lambda: self.refresh_git_config_list_scope("system")),
            ("设置代理...", self.configure_proxy_from_page),
            ("刷新 SSH config", self.show_ssh_config_file),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            config_list_buttons.addWidget(button)
        config_list_buttons.addStretch(1)
        config_list_layout.addLayout(config_list_buttons)
        git_config_layout.addWidget(config_list_box, 2)

        config_box = QGroupBox("Git config 单项编辑")
        config_form = QFormLayout(config_box)
        config_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        config_form.setHorizontalSpacing(12)
        config_form.setVerticalSpacing(7)
        self.git_config_scope = QComboBox()
        self.git_config_scope.addItems(["global", "local", "system"])
        self.git_config_key = QComboBox()
        self.git_config_key.setEditable(True)
        self.git_config_key.addItems([
            "user.name", "user.email", "core.editor", "core.autocrlf", "core.safecrlf",
            "core.filemode", "core.longpaths", "init.defaultBranch", "pull.rebase", "pull.ff",
            "fetch.prune", "push.default", "credential.helper", "http.proxy", "https.proxy",
            "http.sslVerify", "http.postBuffer", "http.version", "http.proxyAuthMethod",
            "http.noProxy", "url.<base>.insteadOf", "ssh.variant", "core.sshCommand",
        ])
        self.git_config_value = QLineEdit()
        self.git_config_value.setPlaceholderText("要写入的值；读取/删除时可留空")
        for widget in (self.git_config_scope, self.git_config_key, self.git_config_value):
            self._set_compact_field_size(widget, 360 if widget is self.git_config_value else 220)
        config_form.addRow("作用域", self.git_config_scope)
        config_form.addRow("key", self.git_config_key)
        config_form.addRow("value", self.git_config_value)
        config_buttons = QHBoxLayout()
        for text, handler in [
            ("读取", self.read_git_config_key),
            ("设置", self.set_git_config_key),
            ("删除", self.unset_git_config_key),
            ("列出作用域", self.list_git_config_scope),
            ("刷新列表", self.refresh_git_config_list_all),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            config_buttons.addWidget(button)
        config_buttons.addStretch(1)
        config_form.addRow(config_buttons)
        git_config_layout.addWidget(config_box)

        ssh_box = QGroupBox("SSH / HTTPS 认证与密钥")
        ssh_layout = QVBoxLayout(ssh_box)
        ssh_tip = QLabel("SSH 推荐每个平台、每个账号使用独立私钥；HTTPS 使用 token / credential helper，不生成公私钥。SSH 端口写入 ~/.ssh/config 的 Host 块。")
        ssh_tip.setWordWrap(True)
        ssh_layout.addWidget(ssh_tip)
        ssh_buttons = QGridLayout()
        for index, (text, handler) in enumerate([
            ("创建平台独立 SSH 私钥...", self.create_provider_ssh_key_from_page),
            ("多用户 SSH 一键配置...", self.configure_provider_ssh_from_menu),
            ("列出本机 SSH Key", self.list_local_ssh_keys),
            ("配置 SSH Host 端口...", self.configure_ssh_host_port_from_page),
            ("设置 core.sshCommand...", self.configure_core_ssh_command_from_page),
            ("查看 ~/.ssh/config", self.show_ssh_config_file),
            ("HTTPS / Credential Helper...", self.configure_credential_helper_from_page),
            ("测试认证...", self.test_provider_auth_from_menu),
        ]):
            button = QPushButton(text)
            button.clicked.connect(handler)
            ssh_buttons.addWidget(button, index // 3, index % 3)
        ssh_layout.addLayout(ssh_buttons)
        git_config_layout.addWidget(ssh_box)
        platform_tabs.addTab(git_config, "Git 配置")

        # User page -------------------------------------------------------
        user_page = QWidget()
        user_layout = QVBoxLayout(user_page)
        user_tip = QLabel("用户与账号配置：这里集中展示 Git identity、credential helper，以及 GitHub/GitLab/Gitee 配置入口。")
        user_tip.setWordWrap(True)
        user_layout.addWidget(user_tip)
        self.git_identity_status = QLabel("Git identity: 点击 Refresh Status 或仓库刷新后检测。")
        self.git_identity_status.setObjectName("ProviderStatusLabel")
        self.git_identity_status.setWordWrap(True)
        user_layout.addWidget(self.git_identity_status)
        identity_box = QGroupBox("Git Identity")
        identity_form = QFormLayout(identity_box)
        identity_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.git_user_name_input = QLineEdit()
        self.git_user_email_input = QLineEdit()
        for edit in (self.git_user_name_input, self.git_user_email_input):
            self._set_compact_field_size(edit, 280)
        identity_form.addRow("user.name", self.git_user_name_input)
        identity_form.addRow("user.email", self.git_user_email_input)
        identity_buttons = QHBoxLayout()
        for text, handler in [
            ("保存为 global", self.save_git_identity_from_page),
            ("刷新", self.refresh_platform_statuses),
            ("打开 Git 配置页", self.show_git_config_page),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            identity_buttons.addWidget(button)
        identity_buttons.addStretch(1)
        identity_form.addRow(identity_buttons)
        user_layout.addWidget(identity_box)
        user_layout.addStretch(1)
        platform_tabs.addTab(user_page, "User")

        # GitHub page; CLI functions merged here -------------------------
        github = QWidget()
        github_layout = QVBoxLayout(github)
        github_layout.setSpacing(8)
        github_tip = QLabel("GitHub：认证配置和 gh CLI 常用功能合并在同一页；没有 gh 也可以先配置 SSH / HTTPS remote。")
        github_tip.setWordWrap(True)
        github_layout.addWidget(github_tip)
        self.github_status_label = QLabel("GitHub: 正在检测 gh 登录状态...")
        self.github_status_label.setObjectName("ProviderStatusLabel")
        self.github_status_label.setWordWrap(True)
        github_layout.addWidget(self.github_status_label)
        add_command_grid(github_layout, "GitHub 初始化 / 账号 / 认证", [
            ("一键安装 gh", self.install_gh_cli),
            ("检查 gh", ["gh", "--version"]),
            ("gh auth login", ["gh", "auth", "login"]),
            ("gh auth status", ["gh", "auth", "status"]),
            ("gh auth setup-git", ["gh", "auth", "setup-git"]),
            ("创建 SSH 私钥", self.create_provider_ssh_key_from_page),
            ("SSH 多用户配置", self.configure_provider_ssh_from_menu),
            ("HTTPS 配置", self.configure_provider_https_from_menu),
            ("认证测试", self.test_provider_auth_from_menu),
        ])
        add_command_grid(github_layout, "Repo / PR / Issue / Release / Actions", [
            ("repo clone...", self.gh_repo_clone_interactive),
            ("repo create...", self.gh_repo_create_interactive),
            ("repo list", ["gh", "repo", "list", "--limit", "50"]),
            ("repo view", ["gh", "repo", "view"]),
            ("PR create...", self.gh_pr_create_interactive),
            ("PR checkout...", self.gh_pr_checkout_interactive),
            ("PR list", ["gh", "pr", "list"]),
            ("PR status", ["gh", "pr", "status"]),
            ("Issue create...", self.gh_issue_create_interactive),
            ("Issue list", ["gh", "issue", "list"]),
            ("Release list", ["gh", "release", "list"]),
            ("Actions runs", ["gh", "run", "list"]),
        ])
        github_layout.addStretch(1)
        platform_tabs.addTab(github, "GitHub")

        # GitLab page; CLI functions merged here -------------------------
        gitlab = QWidget()
        gitlab_layout = QVBoxLayout(gitlab)
        gitlab_layout.setSpacing(8)
        gitlab_tip = QLabel("GitLab：认证配置和 glab CLI 常用功能合并在同一页；没有 glab 也可以先配置 SSH / HTTPS remote。")
        gitlab_tip.setWordWrap(True)
        gitlab_layout.addWidget(gitlab_tip)
        self.gitlab_status_label = QLabel("GitLab: 正在检测 glab 登录状态...")
        self.gitlab_status_label.setObjectName("ProviderStatusLabel")
        self.gitlab_status_label.setWordWrap(True)
        gitlab_layout.addWidget(self.gitlab_status_label)
        add_command_grid(gitlab_layout, "GitLab 初始化 / 账号 / 认证", [
            ("一键安装 glab", self.install_glab_cli),
            ("检查 glab", ["glab", "--version"]),
            ("glab auth login", ["glab", "auth", "login"]),
            ("glab auth status", ["glab", "auth", "status"]),
            ("glab config list", ["glab", "config", "list"]),
            ("创建 SSH 私钥", self.create_provider_ssh_key_from_page),
            ("SSH 多用户配置", self.configure_provider_ssh_from_menu),
            ("HTTPS 配置", self.configure_provider_https_from_menu),
            ("认证测试", self.test_provider_auth_from_menu),
        ])
        add_command_grid(gitlab_layout, "Repo / MR / Issue / Pipeline / Release", [
            ("repo clone...", self.glab_repo_clone_interactive),
            ("repo create...", self.glab_repo_create_interactive),
            ("repo list", ["glab", "repo", "list"]),
            ("repo view", ["glab", "repo", "view"]),
            ("MR create...", self.glab_mr_create_interactive),
            ("MR checkout...", self.glab_mr_checkout_interactive),
            ("MR list", ["glab", "mr", "list"]),
            ("MR status", ["glab", "mr", "status"]),
            ("Issue create...", self.glab_issue_create_interactive),
            ("Issue list", ["glab", "issue", "list"]),
            ("Pipeline list", ["glab", "pipeline", "list"]),
            ("Release list", ["glab", "release", "list"]),
        ])
        gitlab_layout.addStretch(1)
        platform_tabs.addTab(gitlab, "GitLab")

        # Gitee page ------------------------------------------------------
        gitee = QWidget()
        gitee_layout = QVBoxLayout(gitee)
        gitee_layout.setSpacing(8)
        gitee_tip = QLabel("Gitee：可配置 Token，也可直接配置 SSH / HTTPS remote；不要求先登录 GitHub/GitLab。")
        gitee_tip.setWordWrap(True)
        gitee_layout.addWidget(gitee_tip)
        self.gitee_status_label = QLabel("Gitee: 未配置 Token。请填写 Token 和用户/组织后点击检查。")
        self.gitee_status_label.setObjectName("ProviderStatusLabel")
        self.gitee_status_label.setWordWrap(True)
        gitee_layout.addWidget(self.gitee_status_label)
        gitee_box = QGroupBox("Gitee 初始化配置")
        gitee_form = QFormLayout(gitee_box)
        gitee_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.gitee_token = QLineEdit()
        self.gitee_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.gitee_token.setPlaceholderText("Personal Access Token")
        self.gitee_user = QLineEdit()
        self.gitee_user.setPlaceholderText("用户名 / 组织名")
        for edit in (self.gitee_token, self.gitee_user):
            self._set_compact_field_size(edit, 300)
        gitee_form.addRow("Gitee Token", self.gitee_token)
        gitee_form.addRow("用户/组织", self.gitee_user)
        gitee_buttons = QHBoxLayout()
        for text, handler in [
            ("检查 token / repos", self.gitee_list_repos),
            ("创建 SSH 私钥", self.create_provider_ssh_key_from_page),
            ("SSH 多用户配置", self.configure_provider_ssh_from_menu),
            ("HTTPS 配置", self.configure_provider_https_from_menu),
            ("认证测试", self.test_provider_auth_from_menu),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            gitee_buttons.addWidget(button)
        gitee_buttons.addStretch(1)
        gitee_form.addRow(gitee_buttons)
        gitee_layout.addWidget(gitee_box)
        add_command_grid(gitee_layout, "Gitee / 自定义 Git 远程", [
            ("remote -v", lambda: self.run_git_command(["remote", "-v"], callback=self.show_result_in_log)),
            ("添加 Remote...", self.add_remote),
            ("设置 Remote URL...", self.set_remote_url),
            ("设置跟踪分支...", self.set_tracking_branch_from_remote_page),
            ("测试 ls-remote", lambda: self.run_git_command(["ls-remote"], callback=self.show_result_in_log, timeout=300)),
        ])
        gitee_layout.addStretch(1)
        platform_tabs.addTab(gitee, "Gitee")

        # Advanced page ---------------------------------------------------
        advanced = QWidget()
        advanced_layout = QVBoxLayout(advanced)
        advanced_tip = QLabel("高级平台配置：SSH、credential helper、remote 权限、保护分支和 CI 状态通常由平台 API 或 CLI 执行。")
        advanced_tip.setWordWrap(True)
        advanced_layout.addWidget(advanced_tip)
        add_command_grid(advanced_layout, "通用认证 / Remote 检查", [
            ("ssh -V", ["ssh", "-V"]),
            ("ssh-add -l", ["ssh-add", "-l"]),
            ("git credential helper", lambda: self.run_git_command(["config", "--global", "credential.helper"], callback=self.show_result_in_log)),
            ("remote show origin", lambda: self.run_git_command(["remote", "show", "origin"], callback=self.show_result_in_log, timeout=300)),
            ("branch -vv", lambda: self.run_git_command(["branch", "-vv"], callback=self.show_result_in_log)),
            ("ls-remote origin", lambda: self.run_git_command(["ls-remote", "origin"], callback=self.show_result_in_log, timeout=300)),
        ])
        advanced_layout.addStretch(1)
        platform_tabs.addTab(advanced, "高级")

        layout.addWidget(platform_tabs, 2)
        self.platform_output = QPlainTextEdit()
        self.platform_output.setReadOnly(True)
        layout.addWidget(self.platform_output, 1)
        self._add_scrollable_tab(page, "平台")
        self.refresh_platform_statuses()
        self.refresh_git_config_list_all()

    # ------------------------------------------------------------------
    # Git config page helpers
    # ------------------------------------------------------------------

    def _parse_git_config_lines(self, scope: str, text: str) -> list[tuple[str, str, str, str]]:
        rows: list[tuple[str, str, str, str]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            origin = ""
            pair = line
            if "\t" in line:
                origin, pair = line.split("\t", 1)
            elif " " in line and line.startswith(("file:", "command line:")):
                origin, pair = line.split(None, 1)
            if "=" in pair:
                key, value = pair.split("=", 1)
            else:
                key, value = pair, ""
            rows.append((scope, origin, key.strip(), value.strip()))
        return rows

    def _set_git_config_tree_rows(self, rows: list[tuple[str, str, str, str]], warnings: list[str] | None = None) -> None:
        tree = getattr(self, "git_config_tree", None)
        if tree is None:
            return
        self._git_config_tree_updating = True
        try:
            tree.clear()
            for scope, origin, key, value in rows:
                item = QTreeWidgetItem([scope, origin, key, value])
                # Scope/origin are informational; Key and Value are directly editable.
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                item.setData(0, Qt.ItemDataRole.UserRole, (scope, origin, key, value))
                item.setToolTip(0, "只读：配置作用域")
                item.setToolTip(1, origin or "只读：来源文件")
                item.setToolTip(2, "双击可改 key；改名会先 unset 原 key，再 set 新 key")
                item.setToolTip(3, value or "双击可直接改 value")
                tree.addTopLevelItem(item)
            for col, width in enumerate([74, 300, 210, 420]):
                tree.setColumnWidth(col, width)
        finally:
            self._git_config_tree_updating = False
        summary = f"已列出 {len(rows)} 条 Git config。可双击 Key/Value 直接编辑。"
        if warnings:
            summary += " " + "；".join(warnings)
        if hasattr(self, "git_config_status"):
            self.git_config_status.setText("✓ " + summary if rows else "⚠ " + summary)
        if hasattr(self, "platform_output"):
            lines = ["Scope\tOrigin\tKey\tValue"] + ["\t".join(r) for r in rows]
            if warnings:
                lines += ["", "Warnings:", *warnings]
            self.platform_output.setPlainText("\n".join(lines) if rows or warnings else "(no git config entries)")

    def _git_config_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if getattr(self, "_git_config_tree_updating", False):
            return
        if column not in {2, 3}:
            self._git_config_tree_updating = True
            try:
                original = item.data(0, Qt.ItemDataRole.UserRole) or tuple(item.text(i) for i in range(4))
                item.setText(column, str(original[column]))
            finally:
                self._git_config_tree_updating = False
            self.append_log("Git config 列表中只有 Key 和 Value 支持直接编辑。")
            return
        original = item.data(0, Qt.ItemDataRole.UserRole) or tuple(item.text(i) for i in range(4))
        old_scope, _old_origin, old_key, old_value = [str(x) for x in original]
        new_key = item.text(2).strip()
        new_value = item.text(3).strip()
        if not new_key:
            self._git_config_tree_updating = True
            try:
                item.setText(2, old_key)
                item.setText(3, old_value)
            finally:
                self._git_config_tree_updating = False
            self.append_log("Git config 更新已取消：key 不能为空。")
            return
        if old_scope == "local" and not self.runner.repo_path:
            self.append_log("Git config 更新已取消：local 作用域需要先打开仓库。")
            return
        commands: list[str] = []
        if new_key != old_key:
            commands.append(f"git config --{old_scope} --unset-all {self._shell_quote(old_key)}")
        commands.append(f"git config --{old_scope} {self._shell_quote(new_key)} {self._shell_quote(new_value)}")
        command = "\n".join(commands)

        def after(result: GitResult) -> None:
            if result.ok:
                self.append_log(f"✓ 已更新 Git config：{old_scope} {new_key}")
                self.refresh_git_config_list_scope(old_scope)
            else:
                self._git_config_tree_updating = True
                try:
                    item.setText(2, old_key)
                    item.setText(3, old_value)
                    item.setData(0, Qt.ItemDataRole.UserRole, original)
                finally:
                    self._git_config_tree_updating = False
                self.append_log(f"✗ Git config 更新失败，已回滚界面：{result.output.strip() or result.stderr.strip()}")
        self.run_shell_command(command, callback=after, timeout=120)

    def refresh_git_config_list_scope(self, scope: str | None = None) -> None:
        scope = (scope or (self.git_config_scope.currentText().strip() if hasattr(self, "git_config_scope") else "global")).lower()
        if scope not in {"global", "local", "system"}:
            scope = "global"
        if scope == "local" and not self.runner.repo_path:
            self._set_git_config_tree_rows([], ["local 作用域需要先打开仓库"])
            return
        result = self.runner.run(["config", f"--{scope}", "--list", "--show-origin"], cwd=None if scope != "local" else self.runner.repo_path)
        rows = self._parse_git_config_lines(scope, result.output)
        warnings = [] if result.ok else [result.stderr.strip() or result.stdout.strip() or f"{scope} 读取失败"]
        self._set_git_config_tree_rows(rows, warnings)

    def refresh_git_config_list_all(self) -> None:
        rows: list[tuple[str, str, str, str]] = []
        warnings: list[str] = []
        for scope in ["global", "local", "system"]:
            if scope == "local" and not self.runner.repo_path:
                warnings.append("local 跳过：未打开仓库")
                continue
            result = self.runner.run(["config", f"--{scope}", "--list", "--show-origin"], cwd=None if scope != "local" else self.runner.repo_path)
            if result.ok or result.output.strip():
                rows.extend(self._parse_git_config_lines(scope, result.output))
            elif result.returncode not in {0, 1}:
                warnings.append(f"{scope} 读取失败：{(result.stderr or result.stdout).strip()}")
        self._set_git_config_tree_rows(rows, warnings)

    def _copy_selected_git_config_to_editor(self) -> None:
        tree = getattr(self, "git_config_tree", None)
        if tree is None:
            return
        items = tree.selectedItems()
        if not items:
            return
        item = items[0]
        scope, _origin, key, value = [item.text(i) for i in range(4)]
        if hasattr(self, "git_config_scope"):
            index = self.git_config_scope.findText(scope)
            if index >= 0:
                self.git_config_scope.setCurrentIndex(index)
        if hasattr(self, "git_config_key"):
            index = self.git_config_key.findText(key)
            if index < 0:
                self.git_config_key.addItem(key)
                index = self.git_config_key.findText(key)
            self.git_config_key.setCurrentIndex(index)
            self.git_config_key.setEditText(key)
        if hasattr(self, "git_config_value"):
            self.git_config_value.setText(value)

    def _git_config_cwd_for_scope(self, scope: str) -> str | None:
        return self.runner.cwd() if scope == "local" else None

    def _git_config_key_exists(self, scope: str, key: str) -> bool:
        result = self.runner.run(["config", f"--{scope}", "--get-all", key], cwd=self._git_config_cwd_for_scope(scope), timeout=30)
        return result.ok and bool(result.output.strip())

    def _format_git_config_scope_list(self, scope: str) -> str:
        result = self.runner.run(["config", f"--{scope}", "--list", "--show-origin"], cwd=self._git_config_cwd_for_scope(scope), timeout=30)
        text = result.output.strip()
        if result.ok:
            return text or f"({scope} 没有任何 Git config 项)"
        return f"读取 {scope} config 失败：{(result.stderr or result.stdout).strip() or 'unknown error'}"

    def apply_proxy_settings(self, scope: str, entries: list[tuple[str, str]]) -> None:
        """Set or clear proxy config without treating missing keys as failures."""
        if scope == "local" and not self.runner.repo_path:
            self.append_log("代理设置已取消：local 作用域需要先打开仓库。")
            return
        messages: list[str] = [f"Git 代理配置作用域：{scope}"]
        failures: list[str] = []
        for key, value in entries:
            value = value.strip()
            if value:
                result = self.runner.run(["config", f"--{scope}", key, value], cwd=self._git_config_cwd_for_scope(scope), timeout=30)
                if result.ok:
                    messages.append(f"✓ 已设置 {key} = {value}")
                else:
                    error = (result.stderr or result.stdout).strip() or "unknown error"
                    messages.append(f"✗ 设置失败 {key}: {error}")
                    failures.append(key)
                continue

            if not self._git_config_key_exists(scope, key):
                messages.append(f"- {key} 未配置，无需删除。")
                continue

            result = self.runner.run(["config", f"--{scope}", "--unset-all", key], cwd=self._git_config_cwd_for_scope(scope), timeout=30)
            if result.ok:
                messages.append(f"✓ 已删除 {key}")
            else:
                error = (result.stderr or result.stdout).strip() or "unknown error"
                messages.append(f"✗ 删除失败 {key}: {error}")
                failures.append(key)

        messages.append("")
        messages.append(f"当前 {scope} config：")
        messages.append(self._format_git_config_scope_list(scope))
        output = "\n".join(messages)
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(output)
        self.append_log(("✗" if failures else "✓") + " Git 代理配置完成\n" + output)
        self.refresh_git_config_list_scope(scope)

    def configure_proxy_from_page(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            scope = values.get("scope", "global").strip().lower() or "global"
            if scope not in {"global", "local", "system"}:
                scope = "global"
            self.apply_proxy_settings(scope, [
                ("http.proxy", values.get("http_proxy", "")),
                ("https.proxy", values.get("https_proxy", "")),
                ("http.noProxy", values.get("no_proxy", "")),
            ])
        self.request_workspace_form(
            "设置 Git HTTP/HTTPS 代理",
            "直接设置或清空代理配置。例：http://127.0.0.1:7890；留空会删除对应 key。不存在的 key 不会被当成错误。",
            [
                ("scope", "作用域 global/local/system", "global", False),
                ("http_proxy", "http.proxy", "http://127.0.0.1:7890", False),
                ("https_proxy", "https.proxy", "http://127.0.0.1:7890", False),
                ("no_proxy", "http.noProxy", "localhost,127.0.0.1", False),
            ],
            submitted,
        )

    def list_local_ssh_keys(self) -> None:
        ssh_dir = Path.home() / ".ssh"
        rows: list[str] = [f"SSH directory: {ssh_dir}"]
        if not ssh_dir.exists():
            rows.append("目录不存在。")
        else:
            private_candidates = []
            for path in sorted(ssh_dir.iterdir()):
                if path.is_file() and not path.name.endswith(".pub") and path.name not in {"config", "known_hosts", "authorized_keys"}:
                    private_candidates.append(path)
            if private_candidates:
                rows.append("\nPrivate keys:")
                for path in private_candidates:
                    pub = Path(str(path) + ".pub")
                    rows.append(f"- {path}  {'✓ has .pub' if pub.exists() else '⚠ missing .pub'}")
            else:
                rows.append("未发现常见私钥文件。")
            rows.append("\nPublic keys:")
            pubs = sorted(ssh_dir.glob("*.pub"))
            rows.extend([f"- {p}" for p in pubs] or ["未发现 .pub 公钥文件。"])
            config = ssh_dir / "config"
            rows.append("\nSSH config:")
            rows.append(config.read_text(encoding="utf-8", errors="replace") if config.exists() else "~/.ssh/config 不存在。")
        text = "\n".join(rows)
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(text)
        self.append_log("✓ 已列出本机 SSH Key。")

    def create_provider_ssh_key_from_page(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            provider = values.get("provider", "github").strip().lower() or "github"
            account = values.get("account", "default").strip() or "default"
            email = values.get("email", "").strip() or f"{account}@git-terminal"
            path_text = values.get("key_path", "").strip() or self._default_ssh_key_path(provider, account)
            overwrite = values.get("overwrite", "no").strip().lower() in {"y", "yes", "1", "true", "是"}
            key_path = Path(path_text).expanduser()
            key_path.parent.mkdir(parents=True, exist_ok=True)
            if key_path.exists() and not overwrite:
                self.append_log(f"SSH 私钥已存在，未覆盖：{key_path}")
                pub = Path(str(key_path) + ".pub")
                if hasattr(self, "platform_output"):
                    self.platform_output.setPlainText(pub.read_text(encoding="utf-8", errors="replace") if pub.exists() else f"{pub} 不存在。")
                return
            cmd = ["ssh-keygen", "-t", "ed25519", "-C", email, "-f", str(key_path), "-N", ""]
            def after(result: GitResult) -> None:
                pub = Path(str(key_path) + ".pub")
                text = result.output
                if pub.exists():
                    text += "\n\nPublic key; copy this to the platform SSH Keys page:\n" + pub.read_text(encoding="utf-8", errors="replace").strip()
                if hasattr(self, "platform_output"):
                    self.platform_output.setPlainText(text.strip() or "(no output)")
                self.append_log(("✓" if result.ok else "✗") + f" 平台独立 SSH 私钥创建完成：{provider}/{account} -> {key_path}")
            self.run_external_command_with_callback(cmd, after)
        self.request_workspace_form(
            "创建平台独立 SSH 私钥",
            "建议每个平台、每个账号使用独立 key。默认路径会按 provider/account 生成，例如 id_ed25519_github_work。",
            [
                ("provider", "平台 github/gitlab/gitee", "github", False),
                ("account", "账号标识", "default", False),
                ("email", "Key 注释邮箱", "", False),
                ("key_path", "SSH 私钥路径", self._default_ssh_key_path("github", "default"), False),
                ("overwrite", "覆盖已有 key? yes/no", "no", False),
            ],
            submitted,
        )

    def _git_config_scope_arg(self) -> str:
        widget = getattr(self, "git_config_scope", None)
        scope = widget.currentText().strip() if widget is not None else "global"
        return "--" + (scope if scope in {"global", "local", "system"} else "global")

    def _git_config_key_text(self) -> str:
        widget = getattr(self, "git_config_key", None)
        return widget.currentText().strip() if widget is not None else ""

    def _git_config_value_text(self) -> str:
        widget = getattr(self, "git_config_value", None)
        return widget.text().strip() if widget is not None else ""

    def _git_config_cwd_ok(self) -> bool:
        scope = self._git_config_scope_arg()
        if scope == "--local" and not self.runner.repo_path:
            self.append_log("Git config local 操作已取消：需要先打开一个本地仓库。")
            return False
        return True

    def read_git_config_key(self) -> None:
        if not self._git_config_cwd_ok():
            return
        key = self._git_config_key_text()
        if not key:
            self.append_log("读取 Git config 已取消：key 为空。")
            return
        self.run_git_command(["config", self._git_config_scope_arg(), "--get", key], callback=self._show_git_config_result)

    def set_git_config_key(self) -> None:
        if not self._git_config_cwd_ok():
            return
        key = self._git_config_key_text()
        value = self._git_config_value_text()
        if not key:
            self.append_log("设置 Git config 已取消：key 为空。")
            return
        self.run_git_command(["config", self._git_config_scope_arg(), key, value], callback=self._show_git_config_result)

    def unset_git_config_key(self) -> None:
        if not self._git_config_cwd_ok():
            return
        key = self._git_config_key_text()
        if not key:
            self.append_log("删除 Git config 已取消：key 为空。")
            return
        self.run_git_command(["config", self._git_config_scope_arg(), "--unset-all", key], callback=self._show_git_config_result)

    def list_git_config_scope(self) -> None:
        if not self._git_config_cwd_ok():
            return
        self.run_git_command(["config", self._git_config_scope_arg(), "--list", "--show-origin"], callback=self._show_git_config_result)

    def _show_git_config_result(self, result: GitResult) -> None:
        text = result.output.strip() or "(no output)"
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(text)
        if hasattr(self, "git_config_status"):
            self.git_config_status.setText(("✓ " if result.ok else "⚠ ") + "Git config 命令已执行，详情见输出区。")
        self.append_log(("✓" if result.ok else "⚠") + " Git config 命令完成。")
        self.refresh_platform_statuses()

    def configure_credential_helper_from_page(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            helper = values.get("helper", "manager-core").strip()
            scope = values.get("scope", "global").strip().lower() or "global"
            if scope not in {"global", "local", "system"}:
                scope = "global"
            if scope == "local" and not self.runner.repo_path:
                self.append_log("Credential Helper 设置已取消：local 作用域需要先打开仓库。")
                return
            if not helper:
                self.append_log("Credential Helper 设置已取消：helper 为空。")
                return
            self.run_git_command(["config", f"--{scope}", "credential.helper", helper], callback=self._show_git_config_result)
        self.request_workspace_form(
            "设置 Credential Helper",
            "设置 Git credential.helper。Windows 通常使用 manager-core；也可输入 store/cache/osxkeychain/libsecret。",
            [("scope", "作用域 global/local/system", "global", False), ("helper", "credential.helper", "manager-core", False)],
            submitted,
        )

    def configure_core_ssh_command_from_page(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            scope = values.get("scope", "global").strip().lower() or "global"
            command = values.get("command", "").strip()
            if scope not in {"global", "local", "system"}:
                scope = "global"
            if scope == "local" and not self.runner.repo_path:
                self.append_log("core.sshCommand 设置已取消：local 作用域需要先打开仓库。")
                return
            if not command:
                self.append_log("core.sshCommand 设置已取消：命令为空。")
                return
            self.run_git_command(["config", f"--{scope}", "core.sshCommand", command], callback=self._show_git_config_result)
        self.request_workspace_form(
            "设置 core.sshCommand",
            "用于覆盖 Git 调用 ssh 的方式；例如：ssh -p 2222 -i ~/.ssh/id_ed25519。更推荐稳定地写入 ~/.ssh/config。",
            [("scope", "作用域 global/local/system", "local", False), ("command", "core.sshCommand", "ssh -p 22", False)],
            submitted,
        )

    def configure_ssh_host_port_from_page(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            host = values.get("host", "github.com-work").strip()
            hostname = values.get("hostname", "github.com").strip()
            user = values.get("user", "git").strip() or "git"
            port = values.get("port", "22").strip() or "22"
            identity = values.get("identity", "").strip()
            if not host or not hostname:
                self.append_log("SSH Host 端口配置已取消：Host 或 HostName 为空。")
                return
            ssh_dir = Path.home() / ".ssh"
            ssh_dir.mkdir(parents=True, exist_ok=True)
            config_path = ssh_dir / "config"
            lines = [
                f"Host {host}",
                f"  HostName {hostname}",
                f"  User {user}",
                f"  Port {port}",
                "  IdentitiesOnly yes",
            ]
            if identity:
                lines.append(f"  IdentityFile {Path(identity).expanduser()}")
            block = "\n".join(lines) + "\n"
            existing = config_path.read_text(encoding="utf-8", errors="replace") if config_path.exists() else ""
            if f"Host {host}" in existing:
                self.append_log(f"SSH Host 已存在，未覆盖：{host}。请在 ~/.ssh/config 中手动调整，或换一个 Host alias。")
                if hasattr(self, "platform_output"):
                    self.platform_output.setPlainText(existing)
                return
            with config_path.open("a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write(block)
            self.append_log(f"✓ 已写入 SSH Host：{host} -> {hostname}:{port}")
            if hasattr(self, "platform_output"):
                self.platform_output.setPlainText(f"已追加到 {config_path}:\n\n{block}")
        self.request_workspace_form(
            "配置 SSH Host / 端口",
            "写入 ~/.ssh/config。remote 可使用 git@HostAlias:owner/repo.git，从而绑定 HostName、Port、IdentityFile。",
            [
                ("host", "Host alias", "github.com-work", False),
                ("hostname", "HostName", "github.com", False),
                ("port", "Port", "22", False),
                ("user", "User", "git", False),
                ("identity", "IdentityFile", str(Path.home() / ".ssh" / "id_ed25519"), False),
            ],
            submitted,
        )

    def show_ssh_config_file(self) -> None:
        config_path = Path.home() / ".ssh" / "config"
        if config_path.exists():
            text = config_path.read_text(encoding="utf-8", errors="replace")
        else:
            text = f"{config_path} 不存在。"
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(text)
        self.append_log(f"已读取 SSH config：{config_path}")

    def save_git_identity_from_page(self) -> None:
        name = self.git_user_name_input.text().strip() if hasattr(self, "git_user_name_input") else ""
        email = self.git_user_email_input.text().strip() if hasattr(self, "git_user_email_input") else ""
        if not name or not email:
            self.append_log("保存 Git identity 已取消：user.name 或 user.email 为空。")
            return
        command = "\n".join([
            f"git config --global user.name {self._shell_quote(name)}",
            f"git config --global user.email {self._shell_quote(email)}",
            "git config --global --get-regexp '^user\\.(name|email)$'",
        ])
        self.run_shell_command(command, callback=self._show_git_config_result)

    def show_git_config_page(self) -> None:
        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(8)
        self._set_platform_tab_by_text("Git 配置")

    def refresh_platform_statuses(self) -> None:
        def set_label(name: str, text: str, ok: bool | None = None) -> None:
            label = getattr(self, name, None)
            if label is not None:
                prefix = "✓ " if ok is True else ("⚠ " if ok is False else "ℹ ")
                label.setText(prefix + text)

        if shutil.which("gh"):
            try:
                result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=False, timeout=8, env=utf8_subprocess_env())
                stdout, stderr = completed_process_text(result)
                if result.returncode == 0:
                    detail = (stdout or stderr).strip().splitlines()[0:3]
                    set_label("github_status_label", "GitHub 已登录：" + " | ".join(detail), True)
                else:
                    set_label("github_status_label", "GitHub 未登录。点击右侧 gh auth 或在终端执行：gh auth login，然后执行 gh auth setup-git。", False)
            except Exception as exc:
                set_label("github_status_label", f"GitHub 状态检测失败：{exc}", False)
        else:
            set_label("github_status_label", "未检测到 gh CLI。请安装 GitHub CLI 后执行：gh auth login。", False)

        if shutil.which("glab"):
            try:
                result = subprocess.run(["glab", "auth", "status"], capture_output=True, text=False, timeout=8, env=utf8_subprocess_env())
                stdout, stderr = completed_process_text(result)
                if result.returncode == 0:
                    detail = (stdout or stderr).strip().splitlines()[0:3]
                    set_label("gitlab_status_label", "GitLab 已登录：" + " | ".join(detail), True)
                else:
                    set_label("gitlab_status_label", "GitLab 未登录。点击右侧 glab auth 或在终端执行：glab auth login。", False)
            except Exception as exc:
                set_label("gitlab_status_label", f"GitLab 状态检测失败：{exc}", False)
        else:
            set_label("gitlab_status_label", "未检测到 glab CLI。请安装 GitLab CLI 后执行：glab auth login。", False)

        name_result = self.runner.run(["config", "--global", "user.name"], cwd=None)
        email_result = self.runner.run(["config", "--global", "user.email"], cwd=None)
        name = name_result.stdout.strip() if name_result.ok else ""
        email = email_result.stdout.strip() if email_result.ok else ""
        if hasattr(self, "git_user_name_input"):
            self.git_user_name_input.setText(name)
        if hasattr(self, "git_user_email_input"):
            self.git_user_email_input.setText(email)
        if name and email:
            set_label("git_identity_status", f"Git identity 已配置：{name} <{email}>", True)
        else:
            set_label("git_identity_status", "Git identity 未完整配置。请设置 user.name 和 user.email。", False)

        helper_result = self.runner.run(["config", "--global", "credential.helper"], cwd=None)
        helper = helper_result.stdout.strip() if helper_result.ok else ""
        set_label("git_config_status", f"global credential.helper={helper or '(未设置)'}；Git config 页面可设置 http.proxy / https.proxy / core.sshCommand / pull 等。", True if helper else None)

        token = getattr(self, "gitee_token", None).text().strip() if hasattr(self, "gitee_token") else ""
        user = getattr(self, "gitee_user", None).text().strip() if hasattr(self, "gitee_user") else ""
        if token and user:
            set_label("gitee_status_label", f"Gitee 已填写 Token 和用户/组织：{user}。点击 Gitee repos 检查仓库访问。", True)
        else:
            set_label("gitee_status_label", "Gitee 未配置。请填写 Personal Access Token 和用户/组织；Token 应优先保存到系统凭据管理器。", False)

    def _terminal_environment_text(self) -> str:
        if sys.platform.startswith("win"):
            return "Shell: cmd.exe /d /s /c | UTF-8: chcp 65001 | decode fallback: UTF-8/GB18030/GBK/CP936"
        return "Shell: /bin/sh -lc | UTF-8 env | decode fallback: UTF-8/locale"

    def _build_log_bar(self) -> None:
        self.log_bar = QWidget()
        self.log_bar.setObjectName("terminalPage")
        self.log_bar.setMinimumHeight(0)
        self.log_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.terminal_stack = QStackedLayout(self.log_bar)
        self.terminal_stack.setContentsMargins(0, 0, 0, 0)
        self.terminal_stack.setSpacing(0)

        self.terminal_content = QWidget()
        layout = QVBoxLayout(self.terminal_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.terminal_input_bar = QFrame()
        self.terminal_input_bar.setObjectName("terminalInputBar")
        self.terminal_input_bar.setProperty("state", "neutral")
        input_layout = QHBoxLayout(self.terminal_input_bar)
        input_layout.setContentsMargins(10, 5, 10, 5)
        input_layout.setSpacing(8)
        self.terminal_state_label = QLabel("READY")
        self.terminal_state_label.setObjectName("terminalStateLabel")
        self.terminal_env_label = QLabel(self._terminal_environment_text())
        self.terminal_env_label.setObjectName("terminalEnvLabel")
        self.terminal_env_label.setToolTip(self._terminal_environment_text())
        prompt = QLabel("$ >")
        prompt.setObjectName("terminalPrompt")
        self.raw_command = QLineEdit()
        self.raw_command.setObjectName("terminalInput")
        self.raw_command.setPlaceholderText("输入任意命令，例如：git status -sb / python --version / dir / ls")
        self.raw_command.returnPressed.connect(self.run_raw_command)
        run_btn = QPushButton("Run")
        run_btn.setObjectName("runButton")
        run_btn.clicked.connect(self.run_raw_command)
        self.terminal_max_btn = QPushButton("▣")
        self.terminal_max_btn.setObjectName("panelAction")
        self.terminal_max_btn.setToolTip("放大/缩小终端")
        self.terminal_max_btn.clicked.connect(self.toggle_bottom_maximized)
        self.terminal_hide_btn = QPushButton("⌄")
        self.terminal_hide_btn.setObjectName("panelAction")
        self.terminal_hide_btn.setToolTip("收起底部终端")
        self.terminal_hide_btn.clicked.connect(lambda: self.set_bottom_panel_visible(False))
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("panelAction")
        clear_btn.clicked.connect(lambda: self.command_log.clear())
        input_layout.addWidget(self.terminal_state_label)
        input_layout.addWidget(self.terminal_env_label)
        input_layout.addWidget(prompt)
        input_layout.addWidget(self.raw_command, 1)
        input_layout.addWidget(run_btn)
        input_layout.addWidget(self.terminal_max_btn)
        input_layout.addWidget(self.terminal_hide_btn)
        input_layout.addWidget(clear_btn)
        layout.addWidget(self.terminal_input_bar)

        self.command_log = QTextEdit()
        self.command_log.setObjectName("terminalOutput")
        self.command_log.setReadOnly(True)
        self.command_log.setAcceptRichText(True)
        self.command_log.setMinimumHeight(0)
        self.command_log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.command_log, 1)

        self.terminal_prompt_overlay = QFrame()
        self.terminal_prompt_overlay.setObjectName("terminalPromptOverlay")
        overlay = QVBoxLayout(self.terminal_prompt_overlay)
        overlay.setContentsMargins(10, 10, 10, 10)
        overlay.setSpacing(8)

        top_row = QHBoxLayout()
        self.terminal_prompt_back = QPushButton("← 返回")
        self.terminal_prompt_back.setObjectName("terminalPromptBackButton")
        self.terminal_prompt_back.setToolTip("关闭输入提示并恢复终端")
        self.terminal_prompt_back.setMinimumWidth(82)
        self.terminal_prompt_back.setFixedHeight(30)
        self.terminal_prompt_back.clicked.connect(self._cancel_terminal_prompt)
        top_row.addWidget(self.terminal_prompt_back, 0, Qt.AlignmentFlag.AlignLeft)
        top_row.addStretch(1)
        overlay.addLayout(top_row)

        card = QFrame()
        card.setObjectName("terminalPromptCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)
        self.terminal_prompt_title = QLabel("")
        self.terminal_prompt_title.setObjectName("terminalPromptTitle")
        self.terminal_prompt_message = QLabel("")
        self.terminal_prompt_message.setObjectName("terminalPromptMessage")
        self.terminal_prompt_message.setWordWrap(True)
        self.terminal_prompt_input = QLineEdit()
        self.terminal_prompt_input.setObjectName("terminalInput")
        self.terminal_prompt_input.returnPressed.connect(self._submit_terminal_prompt)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.terminal_prompt_cancel = QPushButton("取消")
        self.terminal_prompt_cancel.setObjectName("terminalPromptCancelButton")
        self.terminal_prompt_cancel.setMinimumWidth(82)
        self.terminal_prompt_cancel.setFixedHeight(30)
        self.terminal_prompt_cancel.clicked.connect(self._cancel_terminal_prompt)
        self.terminal_prompt_ok = QPushButton("确定")
        self.terminal_prompt_ok.setObjectName("terminalPromptOkButton")
        self.terminal_prompt_ok.setMinimumWidth(82)
        self.terminal_prompt_ok.setFixedHeight(30)
        self.terminal_prompt_ok.clicked.connect(self._submit_terminal_prompt)
        button_row.addWidget(self.terminal_prompt_cancel)
        button_row.addWidget(self.terminal_prompt_ok)
        card_layout.addWidget(self.terminal_prompt_title)
        card_layout.addWidget(self.terminal_prompt_message)
        card_layout.addWidget(self.terminal_prompt_input)
        card_layout.addLayout(button_row)
        overlay.addWidget(card)
        overlay.addStretch(1)

        self.terminal_stack.addWidget(self.terminal_content)
        self.terminal_stack.addWidget(self.terminal_prompt_overlay)
        self.terminal_stack.setCurrentWidget(self.terminal_content)

    def _compact_ui_controls(self) -> None:
        """Let the VS Code-like splitters win over verbose control rows.

        Many tabs contain long button captions. If Qt uses their sizeHint as a
        hard layout minimum, the center pane becomes too wide and sidebars cannot
        expand. Mark these controls as horizontally shrinkable; text can clip at
        very small widths, but the user can freely resize panes.
        """
        for button in self.findChildren(QPushButton):
            if button.objectName() in {"CollapseButton", "terminalPromptBackButton", "terminalPromptCancelButton", "terminalPromptOkButton", "workspacePromptBackButton", "workspacePromptCancelButton", "workspacePromptOkButton"}:
                continue
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if button.objectName() in {"layoutToggleButton", "topIcon", "panelAction", "collapseButton"}:
                button.setMinimumWidth(0)
                button.setMaximumWidth(34)
                button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            elif button.objectName() == "contextActionWideButton":
                button.setMinimumWidth(0)
                button.setMaximumWidth(16777215)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            elif button.objectName() == "contextActionButton":
                button.setMinimumWidth(0)
                button.setMaximumWidth(112)
                button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            else:
                button.setMinimumWidth(54)
                button.setMaximumWidth(150)
                button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            button.setMinimumHeight(24)
            if button.text() and not button.toolTip():
                button.setToolTip(button.text())
        for form in self.findChildren(QFormLayout):
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
            form.setHorizontalSpacing(10)
            form.setVerticalSpacing(7)
        for line_edit in self.findChildren(QLineEdit):
            name = line_edit.objectName()
            line_edit.setMinimumHeight(22)
            line_edit.setMaximumHeight(24)
            if name in {"commandCenter", "rawCommandInput", "terminalInput"}:
                line_edit.setMinimumWidth(160)
                line_edit.setMaximumWidth(520)
                line_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            elif name == "workspacePromptInput":
                if line_edit.maximumWidth() > 360:
                    line_edit.setMaximumWidth(360)
                line_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            else:
                line_edit.setMinimumWidth(96)
                line_edit.setMaximumWidth(260)
                line_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        for combo in self.findChildren(QComboBox):
            combo.setMinimumHeight(22)
            combo.setMaximumHeight(24)
            combo.setMinimumWidth(96)
            combo.setMaximumWidth(320)
            combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        for tree in self.findChildren(QTreeWidget):
            tree.setMinimumWidth(0)
            tree.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        for list_widget in self.findChildren(QListWidget):
            list_widget.setMinimumWidth(0)
            list_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.tabs.setMinimumWidth(80)

    def toggle_bottom_bar(self) -> None:
        if hasattr(self, "bottom_panel"):
            self.set_bottom_panel_visible(False)

    def _apply_activity_icon_theme(self) -> None:
        if hasattr(self, "activity_bar"):
            self.activity_bar.apply_icon_theme(self.theme_mode, ACCENTS.get(self.theme_accent, ACCENTS["blue"]))

    def change_theme_mode(self, mode: str) -> None:
        self.theme_mode = mode
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self, self.theme_mode, self.theme_accent)
        self._apply_activity_icon_theme()
        if hasattr(self, "branch_graph_view"):
            self.branch_graph_view.set_theme(self.theme_mode)
            self.refresh_branch_graph()

    def change_theme_accent(self, accent: str) -> None:
        self.theme_accent = accent
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self, self.theme_mode, self.theme_accent)
        self._apply_activity_icon_theme()
        if hasattr(self, "branch_graph_view"):
            self.branch_graph_view.set_theme(self.theme_mode)
            self.refresh_branch_graph()

    def _wire_shortcuts(self) -> None:
        self.open_repo_action.setShortcut(QKeySequence("Ctrl+O"))
        self.refresh_action.setShortcut(QKeySequence("F5"))
        self.stage_all_action = QAction("Stage All", self)
        self.stage_all_action.setShortcut(QKeySequence("A"))
        self.stage_all_action.triggered.connect(lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all()))
        self.addAction(self.stage_all_action)

    # ------------------------------------------------------------------
    # General command execution
    # ------------------------------------------------------------------
    def detect_environment(self) -> None:
        git = self.runner.detect_git()
        self.append_log("Environment check")
        if git.ok:
            self.git_version_text = git.output.strip().splitlines()[0] if git.output.strip() else ""
            self.append_log(f"✓ {git.output}")
        else:
            self.git_version_text = ""
            self.append_log("✗ Git not found. 请先安装 Git 后重新检测。")
        for args in (["config", "--global", "user.name"], ["config", "--global", "user.email"], ["config", "--global", "init.defaultBranch"], ["config", "--global", "credential.helper"]):
            result = self.runner.run(args, cwd=None)
            self.append_log(f"$ git {' '.join(args)}\n{result.output or '(empty)'}")
        if shutil.which("ssh"):
            self.append_log("✓ ssh found")
        else:
            self.append_log("⚠ ssh not found")
        if shutil.which("gh"):
            self.append_log("✓ GitHub CLI gh found")
        else:
            self.append_log("ℹ GitHub CLI gh not found；平台功能仍可通过 Git remote 使用。")

    def confirm_risk(self, args: List[str]) -> bool:
        # Kept for API compatibility. High-risk confirmation is now handled by
        # run_git_command through the inline terminal prompt panel.
        return classify_git_command(args).level != RiskLevel.HIGH

    def set_terminal_state(self, state: str = "neutral", label: str | None = None) -> None:
        if not hasattr(self, "terminal_input_bar"):
            return
        normalized = state if state in {"neutral", "running", "success", "error", "warning"} else "neutral"
        self.terminal_input_bar.setProperty("state", normalized)
        self.terminal_input_bar.style().unpolish(self.terminal_input_bar)
        self.terminal_input_bar.style().polish(self.terminal_input_bar)
        self.terminal_input_bar.update()
        if hasattr(self, "terminal_state_label"):
            default_label = {
                "neutral": "READY",
                "running": "RUN",
                "success": "OK",
                "error": "ERR",
                "warning": "WARN",
            }.get(normalized, "READY")
            self.terminal_state_label.setText(label or default_label)

    def run_git_command(
        self,
        args: List[str],
        callback: Optional[Callable[[GitResult], None]] = None,
        timeout: int = 120,
        risk_check: bool = True,
    ) -> None:
        if not args:
            return
        if args[0] == "git":
            args = args[1:]
        if risk_check:
            assessment = classify_git_command(args)
            if assessment.level == RiskLevel.HIGH:
                command_text = "git " + " ".join(shlex.quote(a) for a in args)
                message = (
                    f"{assessment.title}\n\n"
                    f"原因：{assessment.reason}\n\n"
                    f"Will run:\n{command_text}\n\n"
                    f"请输入 {assessment.confirmation_word} 继续。"
                )
                def confirmed(value: str) -> None:
                    if value.strip() == assessment.confirmation_word:
                        self._execute_git_command(args, callback, timeout)
                    else:
                        self.set_terminal_state("warning", "CANCEL")
                        self.append_log(f"已取消高风险命令：{command_text}")
                self.request_terminal_text("危险操作确认", message, confirmed)
                return
        self._execute_git_command(args, callback, timeout)

    def _execute_git_command(
        self,
        args: List[str],
        callback: Optional[Callable[[GitResult], None]] = None,
        timeout: int = 120,
    ) -> None:
        command_text = "git " + " ".join(shlex.quote(a) for a in args)
        self.set_terminal_state("running", "RUN")
        self.append_log(f"Will run:\n{command_text}")
        thread = QThread(self)
        worker = GitCommandWorker(self.runner, args, callback, timeout)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._command_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._threads.append((thread, worker))
        thread.finished.connect(lambda t=thread, w=worker: self._cleanup_thread(t, w))
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _command_finished(self, result: GitResult, callback: Optional[Callable[[GitResult], None]]) -> None:
        status = "✓" if result.ok else "✗"
        if result.ok:
            self.set_terminal_state("success", "OK")
        elif result.returncode == 124:
            self.set_terminal_state("warning", "TIMEOUT")
        else:
            self.set_terminal_state("error", "ERR")
        self.append_log(f"{status} {result.command_text}\n{result.output or '(no output)'}")
        if callback:
            try:
                callback(result)
            except Exception as exc:
                self.append_log(f"命令回调执行失败：{exc}")

    def _cleanup_thread(self, thread: QThread, worker: GitCommandWorker) -> None:
        # Do not call thread.isRunning() here: on Windows/PyQt the wrapped C++
        # QThread may already be scheduled for deletion, which caused
        # RuntimeError: wrapped C/C++ object of type QThread has been deleted.
        self._threads = [(t, w) for (t, w) in self._threads if t is not thread and w is not worker]

    def run_raw_command(self) -> None:
        raw = self.raw_command.text().strip()
        self.raw_command.clear()
        if not raw:
            return
        if raw.startswith(":"):
            raw = raw[1:].strip()
        # Bottom terminal is now a real command terminal: run exactly what the
        # user typed. Git commands still refresh repository state afterwards.
        if raw.startswith("git "):
            parts = shlex.split(raw)
            self.run_git_command(parts[1:], callback=lambda _: self.refresh_all(), timeout=300)
        else:
            self.run_shell_command(raw, callback=lambda _: self.refresh_all(), timeout=300)

    def run_shell_command(
        self,
        command: str,
        callback: Optional[Callable[[GitResult], None]] = None,
        timeout: int = 300,
    ) -> None:
        self.set_terminal_state("running", "RUN")
        self.append_log(f"Will run shell:\n{command}")
        thread = QThread(self)
        worker = ShellCommandWorker(command, self.runner.cwd(), callback, timeout)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._command_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._threads.append((thread, worker))
        thread.finished.connect(lambda t=thread, w=worker: self._cleanup_thread(t, w))
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def run_external_command(self, cmd: List[str]) -> None:
        self.append_log("Will run external:\n" + " ".join(shlex.quote(x) for x in cmd))
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.runner.cwd(),
                capture_output=True,
                text=False,
                timeout=120,
                env=utf8_subprocess_env(),
            )
            stdout, stderr = completed_process_text(proc)
            out = stdout + stderr
            self.platform_output.setPlainText(out.strip() or "(no output)")
            self.append_log(("✓" if proc.returncode == 0 else "✗") + " " + " ".join(cmd) + "\n" + (out.strip() or "(no output)"))
        except Exception as exc:
            self.platform_output.setPlainText(str(exc))
            self.append_log("✗ " + str(exc))

    def run_external_command_with_callback(self, cmd: List[str], callback: Optional[Callable[[GitResult], None]] = None, timeout: int = 120) -> None:
        self.append_log("Will run external:\n" + " ".join(shlex.quote(x) for x in cmd))
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.runner.cwd(),
                capture_output=True,
                text=False,
                timeout=timeout,
                env=utf8_subprocess_env(),
            )
            stdout, stderr = completed_process_text(proc)
            result = GitResult(cmd, self.runner.cwd(), proc.returncode, stdout, stderr)
            if hasattr(self, "platform_output"):
                self.platform_output.setPlainText(result.output.strip() or "(no output)")
            self.append_log(("✓" if result.ok else "✗") + " " + " ".join(cmd) + "\n" + (result.output.strip() or "(no output)"))
        except Exception as exc:
            result = GitResult(cmd, self.runner.cwd(), 1, "", str(exc))
            if hasattr(self, "platform_output"):
                self.platform_output.setPlainText(str(exc))
            self.append_log("✗ " + str(exc))
        if callback:
            try:
                callback(result)
            except Exception as exc:
                self.append_log(f"命令回调执行失败：{exc}")

    def append_log(self, text: str) -> None:
        if not hasattr(self, "command_log"):
            return
        raw = text.rstrip()
        escaped = html.escape(raw).replace("\n", "<br>")
        color = "#d4d4d4"
        bg = "transparent"
        weight = "400"
        if raw.startswith("Will run") or raw.startswith("Will run shell") or raw.startswith("Will run external") or raw.startswith("$ "):
            color = "#93c5fd"
            bg = "rgba(59, 130, 246, 0.14)"
            weight = "700"
        elif raw.startswith("✓"):
            color = "#86efac"
            bg = "rgba(34, 197, 94, 0.14)"
            weight = "700"
        elif raw.startswith("✗"):
            color = "#fca5a5"
            bg = "rgba(239, 68, 68, 0.16)"
            weight = "700"
        elif raw.startswith("⚠") or "取消" in raw or "失败" in raw:
            color = "#fde68a"
            bg = "rgba(245, 158, 11, 0.14)"
        self.command_log.append(
            f"<div style='white-space:pre-wrap; color:{color}; background:{bg}; "
            f"font-family:Consolas, monospace; font-weight:{weight}; "
            f"padding:4px 6px; border-radius:4px; margin:2px 0;'>{escaped}</div>"
        )
        self.command_log.moveCursor(QTextCursor.MoveOperation.End)

    def show_result_in_log(self, result: GitResult) -> None:
        if hasattr(self, "advanced_output"):
            self.advanced_output.setPlainText(result.output)
        if hasattr(self, "all_commands_output"):
            self.all_commands_output.setPlainText(result.output)

    # ------------------------------------------------------------------
    # Remote credential helpers
    # ------------------------------------------------------------------
    def show_ssh_remote_info(self) -> None:
        text = (
            "Remote push 认证配置入口：\n"
            "1. GitHub / GitLab / Gitee 支持多账号 SSH：每个账号生成独立 key，并写入 ~/.ssh/config Host alias。\n"
            "2. SSH 一键配置会自动执行 ssh-keygen、ssh-add、ssh -T 测试；输出中会展示需要复制到平台的公钥。\n"
            "3. HTTPS 一键配置会设置 credential.helper，更新当前仓库 remote URL，并执行 git ls-remote 测试。\n"
            "4. GitHub / GitLab 支持一键安装 gh / glab；安装结束后会跳转到新的 GitHub CLI / GitLab CLI 页面。\n"
            "5. 右侧 ACTIONS > Platform 提供 SSH Setup / HTTPS Setup / Test Auth / Install gh / Install glab。"
        )
        if hasattr(self, "remote_output"):
            self.remote_output.setPlainText(text)
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(text)
        self.append_log(text)

    def generate_ssh_key_from_menu(self) -> None:
        self.request_workspace_form(
            "Generate SSH Key",
            "生成 ed25519 SSH key。邮箱用于 key 注释，输出路径默认 ~/.ssh/id_ed25519。",
            [("email", "Email / Comment", "", False), ("path", "Key path", str(Path.home() / ".ssh" / "id_ed25519"), False)],
            lambda values: self.run_external_command(["ssh-keygen", "-t", "ed25519", "-C", values.get("email", "").strip() or "git-terminal", "-f", values.get("path", "").strip() or str(Path.home() / ".ssh" / "id_ed25519")]),
        )

    def ssh_add_key_from_menu(self) -> None:
        self.request_workspace_form(
            "ssh-add Key",
            "把私钥加入 ssh-agent。Windows 下需要 OpenSSH Authentication Agent 已启动。",
            [("path", "Private key path", str(Path.home() / ".ssh" / "id_ed25519"), False)],
            lambda values: self.run_external_command(["ssh-add", values.get("path", "").strip() or str(Path.home() / ".ssh" / "id_ed25519")]),
        )

    def configure_credential_helper(self) -> None:
        self.request_workspace_form(
            "Credential Helper",
            "配置 Git HTTPS 凭据助手。Windows 常用 manager-core / manager，macOS 常用 osxkeychain，Linux 常用 libsecret/cache。",
            [("helper", "credential.helper", "manager-core", False)],
            lambda values: self.run_git_command(["config", "--global", "credential.helper", values.get("helper", "").strip()], callback=self.show_result_in_log) if values.get("helper", "").strip() else None,
        )

    # ------------------------------------------------------------------
    # Repository lifecycle
    # ------------------------------------------------------------------
    def open_repo_folder(self) -> None:
        path = self.runner.repo_path
        if not path:
            self.set_terminal_state("warning", "WARN")
            self.append_log("尚未打开仓库，无法打开仓库文件夹。")
            return
        path = Path(path)
        if not path.exists() or not path.is_dir():
            self.set_terminal_state("error", "ERR")
            self.append_log(f"仓库路径无效：{path}")
            return
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            self.set_terminal_state("success", "OK")
            self.append_log(f"已打开仓库文件夹：{path}")
        except Exception as exc:
            self.set_terminal_state("error", "ERR")
            self.append_log(f"打开仓库文件夹失败：{exc}")

    def open_repository(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "打开 Git 仓库")
        if not directory:
            return
        try:
            Path(directory).expanduser().mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "目录创建失败", f"无法创建目录：{directory}\n{exc}")
            return
        self.runner.set_repo(directory)
        check = self.runner.run(["rev-parse", "--is-inside-work-tree"])
        if not check.ok:
            answer = QMessageBox.question(self, "不是 Git 仓库", "该目录不是 Git 仓库。是否执行 git init？")
            if answer == QMessageBox.StandardButton.Yes:
                self.run_git_command(["init"], callback=lambda _: self.refresh_all())
            else:
                self.runner.repo_path = None
                return
        self._remember_repository(directory)
        self.refresh_all()

    def init_repository(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择要初始化的目录")
        if not directory:
            return
        try:
            Path(directory).expanduser().mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "目录创建失败", f"无法创建目录：{directory}\n{exc}")
            return
        self.runner.set_repo(directory)
        self.run_git_command(["init"], callback=lambda _: (self._remember_repository(directory), self.refresh_all()))

    def clone_repository(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            url = values.get("url", "").strip()
            dest = values.get("dest", "").strip()
            if not url or not dest:
                self.append_log("Clone 已取消：缺少远程 URL 或目标父目录。")
                return
            parent = Path(dest).expanduser().resolve()
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                self.append_log(f"Clone 已取消：目标父目录无法创建：{parent}\n{exc}")
                return
            if not parent.is_dir():
                self.append_log(f"Clone 已取消：目标父目录不是有效目录：{parent}")
                return
            self.runner.repo_path = parent
            self.run_git_command(["clone", url], callback=lambda r: self._after_clone(r, parent), timeout=900)
        self.request_workspace_form(
            "Clone 远程仓库",
            "一次性输入远程 URL 和目标父目录。",
            [("url", "远程 URL", "", False), ("dest", "目标父目录", str(Path.cwd()), False, "folder")],
            submitted,
        )

    def _after_clone(self, result: GitResult, parent: Path) -> None:
        if result.ok:
            # Infer repository directory from clone URL.
            name = result.command[-1].rstrip("/").split("/")[-1]
            if name.endswith(".git"):
                name = name[:-4]
            candidate = parent / name
            if candidate.exists():
                self.runner.set_repo(candidate)
                self._remember_repository(candidate)
        self.refresh_all()

    def refresh_all(self) -> None:
        horizontal_sizes = self.horizontal_splitter.sizes() if hasattr(self, "horizontal_splitter") else []
        center_sizes = self.center_splitter.sizes() if hasattr(self, "center_splitter") else []
        self.update_top_status()
        self.refresh_worktree()
        self.refresh_history(all_branches=True)
        self.refresh_branches()
        self.refresh_branch_graph()
        self.refresh_remotes()
        self.refresh_tags_stash()
        self.refresh_conflicts()
        self._strip_workspace_buttons()
        if horizontal_sizes and sum(horizontal_sizes) > 0 and hasattr(self, "horizontal_splitter"):
            self.horizontal_splitter.setSizes(horizontal_sizes)
        if center_sizes and sum(center_sizes) > 0 and hasattr(self, "center_splitter") and not getattr(self, "_bottom_maximized", False):
            self.center_splitter.setSizes(center_sizes)

    def update_top_status(self) -> None:
        """Update the bottom status strip. Name kept for existing call sites."""
        summary = self.runner.summarize()
        remotes = ", ".join(summary.remotes) if summary.remotes else "-"
        items = self.runner.parse_status() if self.runner.repo_path else []
        staged_count = sum(1 for item in items if item.staged)
        changed_count = sum(1 for item in items if item.changed)
        untracked_count = sum(1 for item in items if item.untracked)
        conflict_count = sum(1 for item in items if self._is_conflict_status(item.index_status, item.worktree_status))
        push_target, push_url, local_path = self._repo_target_details(summary)
        push_url_safe = self._sanitize_url_for_status(push_url)
        repo_tooltip = str(summary.path) if summary.path else "未打开仓库"
        branch_tooltip = f"当前分支: {summary.branch}\nHEAD: {summary.head}\nUpstream: {summary.upstream}"
        sync_tooltip = f"Ahead: {summary.ahead}\nBehind: {summary.behind}\nUpstream: {summary.upstream}"
        dirty_tooltip = (
            f"Dirty: {summary.dirty}\nStaged: {staged_count}\nChanged: {changed_count}\n"
            f"Untracked: {untracked_count}\nConflicts: {conflict_count}"
        )
        target_tooltip = (
            f"提交/推送目标: {push_target}\nPush URL: {push_url_safe}\n"
            f"当前提交: {summary.head}\nLocal: {local_path}"
        )
        self._set_status_segment("repo", f"仓库: {self._short_middle(summary.name, 32)}", repo_tooltip)
        self._set_status_segment("branch", f"分支: {self._short_middle(summary.branch, 28)}", branch_tooltip)
        self._set_status_segment("head", f"HEAD: {summary.head or '-'}", branch_tooltip)
        self._set_status_segment("upstream", f"Upstream: {self._short_middle(summary.upstream, 34)}", sync_tooltip)
        self._set_status_segment("sync", f"↑{summary.ahead} ↓{summary.behind}", sync_tooltip)
        self._set_status_segment("dirty", f"变更: {summary.dirty}", dirty_tooltip)
        self._set_status_segment("breakdown", f"暂存 {staged_count} | 修改 {changed_count} | 未跟踪 {untracked_count} | 冲突 {conflict_count}", dirty_tooltip)
        self._set_status_segment("mode", f"Mode: {summary.mode}", f"Repository state: {summary.mode}")
        self._set_status_segment("remotes", f"远程: {self._short_middle(remotes, 34)}", f"Remotes: {remotes}")
        self._set_status_segment("push", f"Push: {self._short_middle(push_target, 34)}", target_tooltip)
        self._set_status_segment("local", f"Local: {self._short_middle(local_path, 58)}", target_tooltip)
        git_text = self.git_version_text.replace("git version ", "") if self.git_version_text else "-"
        self._set_status_segment("git", f"Git: {git_text}", self.git_version_text or "Git 未检测")

    def _is_conflict_status(self, index_status: str, worktree_status: str) -> bool:
        return (
            "U" in (index_status, worktree_status)
            or (index_status, worktree_status) in {("A", "A"), ("D", "D"), ("A", "U"), ("U", "A"), ("D", "U"), ("U", "D")}
        )

    def _repo_target_details(self, summary) -> tuple[str, str, str]:
        if not self.runner.repo_path:
            return "未打开仓库", "-", "-"
        upstream = summary.upstream or ""
        push_target = "未设置 upstream"
        push_url = "-"
        remote_name = ""
        if upstream and upstream != "-" and "/" in upstream:
            remote_name = upstream.split("/", 1)[0]
            push_target = upstream
        elif summary.remotes:
            remote_name = "origin" if "origin" in summary.remotes else summary.remotes[0]
            push_target = f"{remote_name}/(未设置跟踪分支)"
        if remote_name:
            url_result = self.runner.run(["remote", "get-url", "--push", remote_name])
            if url_result.ok and url_result.stdout.strip():
                push_url = url_result.stdout.strip().splitlines()[0]
        return push_target, push_url, str(self.runner.repo_path)

    def _build_repo_target_text(self, summary) -> str:
        push_target, push_url, local = self._repo_target_details(summary)
        push_url = self._sanitize_url_for_status(push_url)
        return f"提交目标: {push_target} | Push URL: {push_url} | 当前提交: {summary.head} | Local: {local}"

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------
    def refresh_worktree(self) -> None:
        for widget in (self.changed_list, self.staged_list, self.untracked_list):
            widget.clear()
        if not self.runner.repo_path:
            if hasattr(self, "diff_tree"):
                self.diff_tree.clear()
            return
        for item in self.runner.parse_status():
            list_item = QListWidgetItem(item.display)
            list_item.setData(Qt.ItemDataRole.UserRole, item.path)
            if item.untracked:
                self.untracked_list.addItem(list_item)
            else:
                if item.staged:
                    staged_item = QListWidgetItem(item.display)
                    staged_item.setData(Qt.ItemDataRole.UserRole, item.path)
                    self.staged_list.addItem(staged_item)
                if item.changed:
                    self.changed_list.addItem(list_item)
        self.refresh_diff_tree()

    def _selected_status_item(self) -> Tuple[Optional[str], str]:
        for name, widget in [("staged", self.staged_list), ("changed", self.changed_list), ("untracked", self.untracked_list)]:
            item = widget.currentItem()
            if item and widget.hasFocus():
                return item.data(Qt.ItemDataRole.UserRole), name
        # Fallback: any current item.
        for name, widget in [("staged", self.staged_list), ("changed", self.changed_list), ("untracked", self.untracked_list)]:
            item = widget.currentItem()
            if item:
                return item.data(Qt.ItemDataRole.UserRole), name
        return None, ""

    def stage_selected(self) -> None:
        path, _ = self._selected_status_item()
        if path:
            self.run_git_command(["add", "--", path], callback=lambda _: self.refresh_all())

    def unstage_selected(self) -> None:
        path, _ = self._selected_status_item()
        if path:
            self.run_git_command(["restore", "--staged", "--", path], callback=lambda _: self.refresh_all())

    def restore_selected(self) -> None:
        path, area = self._selected_status_item()
        if not path:
            return
        if area == "staged":
            self.run_git_command(["restore", "--staged", "--", path], callback=lambda _: self.refresh_all())
        else:
            self.run_git_command(["restore", "--", path], callback=lambda _: self.refresh_all())

    def clean_selected_untracked(self) -> None:
        path, area = self._selected_status_item()
        if path and area == "untracked":
            self.run_git_command(["clean", "-f", "--", path], callback=lambda _: self.refresh_all())

    def show_selected_diff(self) -> None:
        path, area = self._selected_status_item()
        if not path:
            self.refresh_diff_tree()
            return
        args = ["diff", "--staged", "--", path] if area == "staged" else ["diff", "--", path]
        result = self.runner.run(args)
        self.diff_tree.clear()
        title = "Staged" if area == "staged" else ("Untracked" if area == "untracked" else "Working tree")
        if area == "untracked":
            root = QTreeWidgetItem([title, path, "未跟踪文件没有 git diff；使用 git add 后可查看 staged diff。"])
            self.diff_tree.addTopLevelItem(root)
        else:
            self._append_diff_to_tree(title, result.output)
        self._resize_diff_tree_columns()

    def refresh_diff_tree(self) -> None:
        if not hasattr(self, "diff_tree"):
            return
        self.diff_tree.clear()
        if not self.runner.repo_path:
            return
        staged = self.runner.run(["diff", "--staged", "--patch", "--find-renames", "--find-copies"])
        working = self.runner.run(["diff", "--patch", "--find-renames", "--find-copies"])
        any_diff = False
        if staged.output.strip():
            self._append_diff_to_tree("Staged", staged.output)
            any_diff = True
        if working.output.strip():
            self._append_diff_to_tree("Working tree", working.output)
            any_diff = True
        if not any_diff:
            root = QTreeWidgetItem(["Diff", "-", "没有已跟踪文件变更。未跟踪文件需 git add 后才会出现完整 diff。"])
            self.diff_tree.addTopLevelItem(root)
        self._resize_diff_tree_columns()

    def _append_diff_to_tree(self, scope: str, diff: str) -> None:
        current_file: QTreeWidgetItem | None = None
        file_node: QTreeWidgetItem | None = None
        current_hunk: QTreeWidgetItem | None = None
        file_path = ""
        additions = QBrush(QColor("#22c55e"))
        deletions = QBrush(QColor("#ef4444"))
        meta = QBrush(QColor("#f59e0b"))
        hunk_brush = QBrush(QColor("#60a5fa"))

        def ensure_file(path: str) -> QTreeWidgetItem:
            nonlocal current_file, file_node, current_hunk, file_path
            if current_file is None or path != file_path:
                file_path = path or "(unknown)"
                current_file = QTreeWidgetItem([scope, file_path, ""])
                current_file.setExpanded(False)
                self.diff_tree.addTopLevelItem(current_file)
                file_node = QTreeWidgetItem(["file", file_path, "header / metadata"])
                current_file.addChild(file_node)
                current_hunk = None
            return current_file

        for raw in diff.splitlines():
            line = raw.rstrip("\n")
            if line.startswith("diff --git "):
                parts = line.split()
                path = parts[-1][2:] if len(parts) >= 4 and parts[-1].startswith("b/") else line
                root = ensure_file(path)
                header = QTreeWidgetItem(["file", path, line])
                header.setForeground(2, meta)
                root.addChild(header)
                file_node = header
                current_hunk = None
                continue
            if current_file is None:
                ensure_file("(raw diff)")
            if line.startswith("@@"):
                current_hunk = QTreeWidgetItem(["hunk", file_path, line])
                current_hunk.setForeground(2, hunk_brush)
                current_file.addChild(current_hunk)
                continue
            if line.startswith("+++") or line.startswith("---") or line.startswith("index ") or line.startswith("new file") or line.startswith("deleted file") or line.startswith("similarity ") or line.startswith("rename "):
                target = file_node or current_file
                item = QTreeWidgetItem(["file", file_path, line])
                item.setForeground(2, meta)
                target.addChild(item)
                continue
            parent = current_hunk or file_node or current_file
            kind = "context"
            brush = None
            if line.startswith("+"):
                kind = "add"
                brush = additions
            elif line.startswith("-"):
                kind = "del"
                brush = deletions
            item = QTreeWidgetItem([kind, file_path, line])
            if brush is not None:
                item.setForeground(2, brush)
            parent.addChild(item)

    def _resize_diff_tree_columns(self) -> None:
        if not hasattr(self, "diff_tree"):
            return
        for i in range(3):
            self.diff_tree.resizeColumnToContents(i)

    def _format_diff_output(self, diff: str) -> str:
        sections: list[str] = []
        for line in diff.splitlines():
            if line.startswith("diff --git "):
                sections.append("\n" + "=" * 72)
                sections.append("File")
                sections.append(f"  {line}")
            elif line.startswith("@@"):
                sections.append("\nHunk")
                sections.append(f"  {line}")
            elif line.startswith("+++") or line.startswith("---"):
                sections.append(f"  {line}")
            elif line.startswith("+"):
                sections.append(f"  ADD    {line}")
            elif line.startswith("-"):
                sections.append(f"  DEL    {line}")
            elif line.startswith("index ") or line.startswith("new file") or line.startswith("deleted file"):
                sections.append(f"  META   {line}")
            else:
                sections.append(f"         {line}")
        return "\n".join(sections).lstrip()

    def commit_changes(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            message = values.get("message", "").strip()
            stage_answer = values.get("stage_all", "yes").strip().lower()
            if not message:
                self.set_terminal_state("warning", "CANCEL")
                self.append_log("Commit 已取消：提交信息为空。")
                return
            should_stage_all = stage_answer in {"", "y", "yes", "1", "true", "是", "全部"}
            if should_stage_all:
                self.run_git_command(["add", "-A"], callback=lambda result: self._commit_after_stage(result, message), timeout=300)
            else:
                self.run_git_command(["commit", "-m", message], callback=lambda _: self.refresh_all())
        self.request_workspace_form(
            "Add All + Commit",
            "默认先执行 git add -A，把新增/修改/删除文件全部加入暂存区，然后提交。输入 no 可只提交已暂存内容。",
            [("message", "Commit message", "", False), ("stage_all", "提交前执行 git add -A?", "yes", False)],
            submitted,
        )

    def _commit_after_stage(self, result: GitResult, message: str) -> None:
        if not result.ok:
            self.set_terminal_state("error", "ERR")
            self.append_log("git add -A 失败，已停止 commit。")
            self.refresh_all()
            return
        self.run_git_command(["commit", "-m", message], callback=lambda _: self.refresh_all())

    def commit_staged_only(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            message = values.get("message", "").strip()
            if not message:
                self.set_terminal_state("warning", "CANCEL")
                self.append_log("Commit 已取消：提交信息为空。")
                return
            self.run_git_command(["commit", "-m", message], callback=lambda _: self.refresh_all())
        self.request_workspace_form(
            "Commit Only",
            "只提交已经暂存的内容，不自动执行 git add。未暂存的新文件不会进入本次提交。",
            [("message", "Commit message", "", False)],
            submitted,
        )

    # ------------------------------------------------------------------
    # History and commit graph
    # ------------------------------------------------------------------
    def refresh_history(self, all_branches: bool = True) -> None:
        self.history_tree.clear()
        if not self.runner.repo_path:
            return
        args = [
            "log",
            "--graph",
            "--date=short",
            "--pretty=format:%h%x09%H%x09%ad%x09%an%x09%D%x09%s",
            "-n",
            "300",
        ]
        if all_branches:
            args.insert(-2, "--all")
        result = self.runner.run(args)
        if not result.ok:
            self.commit_detail.setPlainText(result.output)
            return
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 6:
                self.history_tree.addTopLevelItem(QTreeWidgetItem([line, "", "", "", "", ""]))
                continue
            graph_hash, full_hash, date, author, refs, message = parts[:6]
            # graph_hash can contain graph characters before the abbreviated hash.
            item = QTreeWidgetItem([graph_hash, graph_hash.split()[-1] if graph_hash.split() else "", date, author, refs, message])
            item.setData(0, Qt.ItemDataRole.UserRole, full_hash)
            self.history_tree.addTopLevelItem(item)
        for i in range(6):
            self.history_tree.resizeColumnToContents(i)

    def _selected_commit_hash(self) -> Optional[str]:
        item = self.history_tree.currentItem()
        if not item:
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    def show_commit_details(self, *_args) -> None:
        commit = self._selected_commit_hash()
        if not commit:
            return
        result = self.runner.run(["show", "--stat", "--patch", "--pretty=fuller", commit])
        self.commit_detail.setPlainText(result.output)

    def checkout_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if commit:
            self.run_git_command(["checkout", commit], callback=lambda _: self.refresh_all())

    def branch_from_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if not commit:
            return
        self.request_terminal_text(
            "创建分支",
            "分支名：",
            lambda name: self.run_git_command(["switch", "-c", name.strip(), commit], callback=lambda _: self.refresh_all()) if name.strip() else None,
        )

    def cherry_pick_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if commit:
            self.run_git_command(["cherry-pick", commit], callback=lambda _: self.refresh_all())

    def revert_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if commit:
            self.run_git_command(["revert", commit], callback=lambda _: self.refresh_all())

    def reset_hard_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if commit:
            self.run_git_command(["reset", "--hard", commit], callback=lambda _: self.refresh_all())

    def _commit_context_menu(self, pos: QPoint) -> None:
        commit = self._selected_commit_hash()
        if not commit:
            return
        menu = QMenu(self)
        menu.addAction("Checkout this commit", self.checkout_selected_commit)
        menu.addAction("Create branch here", self.branch_from_selected_commit)
        menu.addAction("Cherry-pick into current branch", self.cherry_pick_selected_commit)
        menu.addAction("Revert this commit", self.revert_selected_commit)
        menu.addAction("Reset current branch --hard here", self.reset_hard_selected_commit)
        menu.addAction("Compare with HEAD", lambda: self.run_git_command(["diff", "HEAD", commit], callback=self.show_result_in_log))
        menu.addAction("Copy commit hash", lambda: QApplication.clipboard().setText(commit))
        menu.addAction("Show raw object", lambda: self.run_git_command(["cat-file", "-p", commit], callback=self.show_result_in_log))
        menu.exec(self.history_tree.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Branches
    # ------------------------------------------------------------------
    def refresh_branches(self) -> None:
        self.branch_list.clear()
        if not self.runner.repo_path:
            return
        result = self.runner.run(["branch", "-a", "-vv", "--no-color"])
        if result.ok:
            for line in result.stdout.splitlines():
                self.branch_list.addItem(line)

    def refresh_branch_graph(self) -> None:
        if not hasattr(self, "branch_graph_view"):
            return
        if not self.runner.repo_path:
            self.branch_graph_view.set_commits([])
            return
        result = self.runner.run([
            "log",
            "--topo-order",
            "--all",
            "--parents",
            "--date=format:%Y-%m-%d %H:%M",
            "--pretty=format:%H%x09%P%x09%h%x09%cd%x09%an%x09%D%x09%s",
            "-n",
            "260",
        ])
        commits: List[GraphCommit] = []
        if result.ok:
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                full_hash, parent_text, short_hash, date, author, refs, message = parts[:7]
                parents = [p for p in parent_text.split() if p]
                commits.append(GraphCommit(full_hash, parents, short_hash, date, author, refs, message))
        self.branch_graph_view.set_commits(commits)
        if not commits:
            self._set_branch_graph_detail_message(result.output if not result.ok else "没有提交历史。")

    def fit_branch_graph(self) -> None:
        if hasattr(self, "branch_graph_view") and self.branch_graph_view.scene() is not None:
            rect = self.branch_graph_view.scene().sceneRect()
            if rect.isValid() and not rect.isEmpty():
                self.branch_graph_view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _set_branch_graph_detail_message(self, message: str) -> None:
        if not hasattr(self, "branch_graph_detail"):
            return
        self.branch_graph_detail.clear()
        item = QTreeWidgetItem([message])
        self.branch_graph_detail.addTopLevelItem(item)
        item.setExpanded(True)

    def graph_commit_selected(self, commit_hash: str) -> None:
        meta = self.runner.run([
            "show",
            "-s",
            "--date=format:%Y-%m-%d %H:%M:%S %z",
            "--pretty=format:%H%x1f%h%x1f%D%x1f%an%x1f%ae%x1f%ad%x1f%cn%x1f%ce%x1f%cd%x1f%P%x1f%s",
            commit_hash,
        ])
        stat = self.runner.run(["show", "--stat", "--format=", commit_hash])
        if not meta.ok:
            self._set_branch_graph_detail_message(meta.output)
            return
        parts = meta.stdout.split("\x1f")
        while len(parts) < 11:
            parts.append("")
        full_hash, short_hash, refs, author, author_email, author_date, committer, committer_email, commit_date, parents, subject = parts[:11]
        self.branch_graph_detail.clear()

        def section(title: str, rows: list[tuple[str, str]] | list[str], expanded: bool = True) -> QTreeWidgetItem:
            root = QTreeWidgetItem([title])
            self.branch_graph_detail.addTopLevelItem(root)
            for row in rows:
                if isinstance(row, tuple):
                    key, value = row
                    root.addChild(QTreeWidgetItem([f"{key}: {value or '-'}"]))
                else:
                    root.addChild(QTreeWidgetItem([row]))
            root.setExpanded(expanded)
            return root

        section("Commit", [
            ("Hash", full_hash),
            ("Short", short_hash),
            ("Refs", refs or "-"),
        ])
        section("Message", [subject or "-"])
        section("Author", [
            ("Name", author),
            ("Email", author_email),
            ("Date", author_date),
        ], expanded=False)
        section("Committer", [
            ("Name", committer),
            ("Email", committer_email),
            ("Date", commit_date),
        ])
        parent_rows = [p for p in parents.split()] or ["<root>"]
        section("Parents", parent_rows, expanded=False)
        stat_lines = [line for line in stat.stdout.splitlines() if line.strip()] if stat.ok else [stat.output]
        section("Changed files", stat_lines or ["(no stat)"], expanded=True)

    def graph_checkout_commit(self, commit_hash: str) -> None:
        self.run_git_command(["checkout", commit_hash], callback=lambda _: self.refresh_all())

    def graph_create_branch_from_commit(self, commit_hash: str) -> None:
        self.request_terminal_text(
            "从图节点创建分支",
            "分支名：",
            lambda name: self.run_git_command(["switch", "-c", name.strip(), commit_hash], callback=lambda _: self.refresh_all()) if name.strip() else None,
        )

    def graph_create_tag_from_commit(self, commit_hash: str) -> None:
        def submitted(name: str) -> None:
            tag = name.strip()
            if not tag:
                return
            existing = self.runner.run(["tag", "--list", tag])
            if existing.ok and any(line.strip() == tag for line in existing.stdout.splitlines()):
                QMessageBox.warning(self, "标签已存在", f"不能创建已有标签：{tag}")
                return
            self.run_git_command(["tag", "-a", tag, commit_hash, "-m", tag], callback=lambda _: self.refresh_all())
        self.request_terminal_text("在图节点打标签", "新标签名：", submitted)

    def graph_commit_context_menu(self, commit_hash: str, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction("Checkout this commit", lambda: self.graph_checkout_commit(commit_hash))
        menu.addAction("Create branch here", lambda: self.graph_create_branch_from_commit(commit_hash))
        menu.addAction("Create tag here", lambda: self.graph_create_tag_from_commit(commit_hash))
        menu.addAction("Cherry-pick into current branch", lambda: self.run_git_command(["cherry-pick", commit_hash], callback=lambda _: self.refresh_all()))
        menu.addAction("Revert this commit", lambda: self.run_git_command(["revert", commit_hash], callback=lambda _: self.refresh_all()))
        menu.addAction("Reset current branch --hard here", lambda: self.run_git_command(["reset", "--hard", commit_hash], callback=lambda _: self.refresh_all()))
        menu.addAction("Compare with HEAD", lambda: self.run_git_command(["diff", "HEAD", commit_hash], callback=self.show_result_in_log))
        menu.addAction("Copy commit hash", lambda: QApplication.clipboard().setText(commit_hash))
        menu.addAction("Show raw object", lambda: self.run_git_command(["cat-file", "-p", commit_hash], callback=self.show_result_in_log))
        menu.exec(pos)

    def _selected_branch_name(self) -> Optional[str]:
        item = self.branch_list.currentItem()
        if not item:
            return None
        text = item.text().strip()
        if text.startswith("*"):
            text = text[1:].strip()
        # Remove metadata after whitespace / [upstream]
        if " " in text:
            text = text.split()[0]
        return text

    def create_branch(self) -> None:
        name = self.new_branch_name.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少分支名", "请输入分支名。")
            return
        self.run_git_command(["branch", name], callback=lambda _: self.refresh_all())

    def switch_branch(self) -> None:
        name = self._selected_branch_name()
        if not name:
            return
        if name.startswith("remotes/"):
            local = name.split("/", 2)[-1]
            self.run_git_command(["switch", "--track", name], callback=lambda _: self.refresh_all())
        else:
            self.run_git_command(["switch", name], callback=lambda _: self.refresh_all())

    def delete_branch(self) -> None:
        name = self._selected_branch_name()
        if not name:
            return
        if name.startswith("remotes/"):
            QMessageBox.information(self, "远程分支", "请在远程页使用 Delete Remote Branch。")
            return
        self.run_git_command(["branch", "-D", name], callback=lambda _: self.refresh_all())

    def merge_branch(self) -> None:
        name = self._selected_branch_name()
        if name:
            self.run_git_command(["merge", name], callback=lambda _: self.refresh_all())

    def rebase_onto_branch(self) -> None:
        name = self._selected_branch_name()
        if name:
            self.run_git_command(["rebase", name], callback=lambda _: self.refresh_all())

    def push_branch_upstream(self) -> None:
        name = self._selected_branch_name()
        if name and not name.startswith("remotes/"):
            self.request_terminal_text(
                "Push upstream",
                "remote：",
                lambda remote: self.run_git_command(["push", "-u", (remote.strip() or "origin"), name], callback=lambda _: self.refresh_all(), timeout=300),
                "origin",
            )

    def _branch_context_menu(self, pos: QPoint) -> None:
        name = self._selected_branch_name()
        if not name:
            return
        menu = QMenu(self)
        menu.addAction("Switch to branch", self.switch_branch)
        menu.addAction("Merge into current branch", self.merge_branch)
        menu.addAction("Rebase current branch onto this branch", self.rebase_onto_branch)
        menu.addAction("Push branch", self.push_branch_upstream)
        menu.addAction("Delete branch", self.delete_branch)
        menu.addAction("Compare with current branch", lambda: self.run_git_command(["diff", "HEAD", name], callback=self.show_result_in_log))
        menu.addAction("Copy branch name", lambda: QApplication.clipboard().setText(name))
        menu.exec(self.branch_list.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Remotes
    # ------------------------------------------------------------------
    def refresh_remotes(self) -> None:
        self.remote_tree.clear()
        if not self.runner.repo_path:
            return
        result = self.runner.run(["remote", "-v"])
        self.remote_output.setPlainText(result.output)
        if result.ok:
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    remote, url, typ = parts[0], parts[1], parts[2].strip("()")
                    self.remote_tree.addTopLevelItem(QTreeWidgetItem([remote, typ, url]))
            for i in range(3):
                self.remote_tree.resizeColumnToContents(i)
        self._sync_remote_tracking_fields(force=False)

    def _selected_remote(self) -> Optional[str]:
        item = self.remote_tree.currentItem()
        return item.text(0) if item else None

    def _current_branch_name(self) -> str:
        if not self.runner.repo_path:
            return ""
        result = self.runner.run(["branch", "--show-current"])
        return result.stdout.strip() if result.ok else ""

    def _sync_remote_tracking_fields(self, force: bool = False) -> None:
        if not hasattr(self, "remote_tracking_local"):
            return
        current = self._current_branch_name()
        selected_remote = self._selected_remote() or "origin"
        if force or not self.remote_tracking_local.text().strip():
            self.remote_tracking_local.setText(current)
        if force or not self.remote_tracking_remote.text().strip():
            self.remote_tracking_remote.setText(selected_remote)
        if force or not self.remote_tracking_branch.text().strip():
            self.remote_tracking_branch.setText(self.remote_tracking_local.text().strip() or current)

    def _remote_tracking_values(self) -> tuple[str, str, str]:
        self._sync_remote_tracking_fields(force=False)
        local_branch = self.remote_tracking_local.text().strip() if hasattr(self, "remote_tracking_local") else self._current_branch_name()
        remote = self.remote_tracking_remote.text().strip() if hasattr(self, "remote_tracking_remote") else (self._selected_remote() or "origin")
        remote_branch = self.remote_tracking_branch.text().strip() if hasattr(self, "remote_tracking_branch") else local_branch
        if not remote_branch:
            remote_branch = local_branch
        return local_branch, remote or "origin", remote_branch

    def fetch_remote_branches_from_tracking_panel(self) -> None:
        _, remote, _ = self._remote_tracking_values()
        self.run_git_command(["fetch", remote, "--prune"], callback=lambda _: self.refresh_all(), timeout=300)

    def show_current_upstream_from_panel(self) -> None:
        local_branch, _, _ = self._remote_tracking_values()
        branch = local_branch or "HEAD"
        self.run_git_command(["rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"], callback=self.show_result_in_log)

    def track_existing_remote_branch_from_panel(self) -> None:
        local_branch, remote, remote_branch = self._remote_tracking_values()
        if not local_branch or not remote or not remote_branch:
            self.append_log("Track Existing 已取消：本地分支 / remote / 远程分支不能为空。")
            return

        def after_check(result: GitResult) -> None:
            if result.ok and result.stdout.strip():
                self.run_git_command(["branch", "--set-upstream-to", f"{remote}/{remote_branch}", local_branch], callback=lambda _: self.refresh_all())
                return
            message = (
                f"远程跟踪分支 {remote}/{remote_branch} 不存在。\n\n"
                "Track Existing 只适用于远程分支已经存在的场景。\n"
                "如果这是新建的本地分支，应使用 Push -u，它会创建远程分支并设置 tracking。\n\n"
                f"是否现在执行：git push -u {remote} {local_branch} ?"
            )
            if QMessageBox.question(self, "远程分支不存在", message) == QMessageBox.StandardButton.Yes:
                self.run_git_command(["push", "-u", remote, local_branch], callback=lambda _: self.refresh_all(), timeout=300)
            else:
                self.append_log(f"未设置 tracking：{remote}/{remote_branch} 不存在。可先 Fetch，或使用 Push -u 发布本地分支。")

        self.run_git_command(["ls-remote", "--heads", remote, remote_branch], callback=after_check, timeout=300, risk_check=False)

    def publish_local_branch_and_track_from_panel(self) -> None:
        local_branch, remote, _ = self._remote_tracking_values()
        if not local_branch or not remote:
            self.append_log("Push -u 已取消：本地分支 / remote 不能为空。")
            return
        self.run_git_command(["push", "-u", remote, local_branch], callback=lambda _: self.refresh_all(), timeout=300)

    def add_remote(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            name = values.get("name", "origin").strip() or "origin"
            url = values.get("url", "").strip()
            if not url:
                self.append_log("Add Remote 已取消：URL 为空。")
                return
            self.run_git_command(["remote", "add", name, url], callback=lambda _: self.refresh_all())
        self.request_workspace_form(
            "Add Remote",
            "一次性输入 remote 名称和 URL。",
            [("name", "remote 名称", "origin", False), ("url", "URL", "", False)],
            submitted,
        )

    def remove_remote(self) -> None:
        remote = self._selected_remote()
        if remote:
            self.run_git_command(["remote", "remove", remote], callback=lambda _: self.refresh_all())

    def set_remote_url(self) -> None:
        selected = self._selected_remote() or "origin"
        def submitted(values: dict[str, str]) -> None:
            remote = values.get("remote", selected).strip() or selected
            url = values.get("url", "").strip()
            if not url:
                self.append_log("Set Remote URL 已取消：URL 为空。")
                return
            self.run_git_command(["remote", "set-url", remote, url], callback=lambda _: self.refresh_all())
        self.request_workspace_form(
            "Set Remote URL",
            "一次性输入 remote 名称和新的 URL。",
            [("remote", "remote 名称", selected, False), ("url", "URL", "", False)],
            submitted,
        )

    def fetch_remote(self) -> None:
        remote = self._selected_remote() or "--all"
        self.run_git_command(["fetch", remote], callback=lambda _: self.refresh_all(), timeout=300)

    def set_tracking_branch_from_remote_page(self) -> None:
        current = self.runner.run(["branch", "--show-current"]).stdout.strip() if self.runner.repo_path else ""
        selected_remote = self._selected_remote() or "origin"
        def submitted(values: dict[str, str]) -> None:
            local_branch = values.get("local", current).strip() or current
            remote = values.get("remote", selected_remote).strip() or selected_remote
            upstream = values.get("upstream", local_branch).strip() or local_branch
            mode = values.get("mode", "set-upstream").strip().lower() or "set-upstream"
            if not local_branch or not remote or not upstream:
                self.append_log("设置跟踪分支已取消：local / remote / upstream 不能为空。")
                return
            if mode in {"push-u", "push", "push -u"}:
                self.run_git_command(["push", "-u", remote, local_branch], callback=lambda _: self.refresh_all(), timeout=300)
            else:
                self.run_git_command(["branch", "--set-upstream-to", f"{remote}/{upstream}", local_branch], callback=lambda _: self.refresh_all())
        self.request_workspace_form(
            "设置跟踪分支",
            "为本地分支设置 upstream。默认执行 git branch --set-upstream-to remote/upstream local；mode 输入 push-u 时改为 git push -u remote local。",
            [
                ("local", "本地分支", current, False),
                ("remote", "remote", selected_remote, False),
                ("upstream", "远程分支", current, False),
                ("mode", "模式 set-upstream/push-u", "set-upstream", False),
            ],
            submitted,
        )

    def delete_remote_branch(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            remote = values.get("remote", "origin").strip() or "origin"
            branch = values.get("branch", "").strip()
            if not branch:
                self.append_log("Delete Remote Branch 已取消：缺少远程分支名。")
                return
            self.run_git_command(["push", remote, "--delete", branch], callback=lambda _: self.refresh_all(), timeout=300)
        self.request_workspace_form(
            "Delete Remote Branch",
            "一次性输入 remote 和远程分支名。",
            [("remote", "remote", "origin", False), ("branch", "远程分支名", "", False)],
            submitted,
        )

    # ------------------------------------------------------------------
    # Tags and Stash
    # ------------------------------------------------------------------
    def refresh_tags_stash(self) -> None:
        self.tag_list.clear()
        self.stash_list.clear()
        if not self.runner.repo_path:
            return
        tags = self.runner.run(["tag", "--list", "--sort=-creatordate"])
        if tags.ok:
            self.tag_list.addItems([x for x in tags.stdout.splitlines() if x.strip()])
        stash = self.runner.run(["stash", "list"])
        if stash.ok:
            self.stash_list.addItems([x for x in stash.stdout.splitlines() if x.strip()])

    def _selected_tag(self) -> Optional[str]:
        item = self.tag_list.currentItem()
        return item.text() if item else None

    def create_tag(self) -> None:
        tag = self.new_tag_name.text().strip()
        if tag:
            self.run_git_command(["tag", "-a", tag, "-m", tag], callback=lambda _: self.refresh_all())

    def delete_tag(self) -> None:
        tag = self._selected_tag()
        if tag:
            self.run_git_command(["tag", "-d", tag], callback=lambda _: self.refresh_all())

    def push_tag(self) -> None:
        tag = self._selected_tag()
        if tag:
            self.request_terminal_text(
                "Push Tag",
                "remote：",
                lambda remote: self.run_git_command(["push", (remote.strip() or "origin"), tag], callback=lambda _: self.refresh_all(), timeout=300),
                "origin",
            )

    def stash_push(self) -> None:
        msg = self.stash_message.text().strip() or "Git Terminal stash"
        self.run_git_command(["stash", "push", "-u", "-m", msg], callback=lambda _: self.refresh_all())

    def _selected_stash_ref(self) -> Optional[str]:
        item = self.stash_list.currentItem()
        if not item:
            return None
        return item.text().split(":", 1)[0]

    def stash_apply(self) -> None:
        ref = self._selected_stash_ref()
        if ref:
            self.run_git_command(["stash", "apply", ref], callback=lambda _: self.refresh_all())

    def stash_pop(self) -> None:
        ref = self._selected_stash_ref()
        if ref:
            self.run_git_command(["stash", "pop", ref], callback=lambda _: self.refresh_all())

    def stash_drop(self) -> None:
        ref = self._selected_stash_ref()
        if ref:
            self.run_git_command(["stash", "drop", ref], callback=lambda _: self.refresh_all())

    # ------------------------------------------------------------------
    # Conflicts
    # ------------------------------------------------------------------
    def refresh_conflicts(self) -> None:
        self.conflict_list.clear()
        if not self.runner.repo_path:
            return
        result = self.runner.run(["status", "--porcelain=v1"])
        if not result.ok:
            return
        conflict_codes = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
        for line in result.stdout.splitlines():
            if len(line) >= 4 and line[:2] in conflict_codes:
                item = QListWidgetItem(line)
                item.setData(Qt.ItemDataRole.UserRole, line[3:])
                self.conflict_list.addItem(item)

    def _selected_conflict_path(self) -> Optional[str]:
        item = self.conflict_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def show_conflict_file(self) -> None:
        path = self._selected_conflict_path()
        if not path:
            return
        full = Path(self.runner.cwd() or ".") / path
        try:
            self.conflict_preview.setPlainText(full.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            self.conflict_preview.setPlainText(str(exc))

    def checkout_conflict_side(self, side: str) -> None:
        path = self._selected_conflict_path()
        if path:
            self.run_git_command(["checkout", side, "--", path], callback=lambda _: self.refresh_all())

    def mark_conflict_resolved(self) -> None:
        path = self._selected_conflict_path()
        if path:
            self.run_git_command(["add", "--", path], callback=lambda _: self.refresh_all())

    # ------------------------------------------------------------------
    # Advanced / all commands
    # ------------------------------------------------------------------
    def run_object_command(self) -> None:
        cmd = self.object_command.currentText().split()
        target = shlex.split(self.object_target.text().strip()) if self.object_target.text().strip() else []
        self.run_git_command(cmd + target, callback=lambda r: self.advanced_output.setPlainText(r.output))

    def _command_changed(self) -> None:
        name = self.command_combo.currentData()
        spec: GitCommandSpec = self.command_catalog.get(name, GitCommandSpec(name=name or "", category=""))
        self.command_desc.setText(f"类别：{spec.category}\n说明：{spec.description or '本机 Git 动态命令；可在参数框中输入任意参数。'}")
        self.command_examples.clear()
        for example in spec.examples:
            self.command_examples.addItem(example)
        self._clear_option_checks()
        for opt in spec.common_options[:12]:
            cb = QCheckBox(opt)
            cb.stateChanged.connect(self.update_command_preview)
            self.options_layout.insertWidget(max(0, self.options_layout.count() - 1), cb)
            self._option_checks.append(cb)
        self.update_command_preview()

    def _clear_option_checks(self) -> None:
        for cb in self._option_checks:
            self.options_layout.removeWidget(cb)
            cb.deleteLater()
        self._option_checks.clear()

    def selected_advanced_args(self) -> List[str]:
        name = self.command_combo.currentData()
        args = [name]
        for cb in self._option_checks:
            if cb.isChecked():
                args.extend(shlex.split(cb.text()))
        text = self.command_args.text().strip()
        if text:
            args.extend(shlex.split(text))
        return args

    def update_command_preview(self) -> None:
        if self._suppress_preview:
            return
        try:
            args = self.selected_advanced_args()
            self.command_preview.setText("git " + " ".join(shlex.quote(a) for a in args))
        except ValueError as exc:
            self.command_preview.setText(f"参数解析错误：{exc}")

    def run_advanced_command(self) -> None:
        try:
            args = self.selected_advanced_args()
        except ValueError as exc:
            QMessageBox.warning(self, "参数解析错误", str(exc))
            return
        self.run_git_command(args, callback=lambda r: self.all_commands_output.setPlainText(r.output), timeout=600)

    def use_command_example(self, item: QListWidgetItem) -> None:
        text = item.text().strip()
        parts = shlex.split(text)
        if parts and parts[0] == "git":
            parts = parts[1:]
        if not parts:
            return
        name = parts[0]
        index = self.command_combo.findData(name)
        if index >= 0:
            self.command_combo.setCurrentIndex(index)
        self.command_args.setText(" ".join(shlex.quote(x) for x in parts[1:]))

    def open_selected_command_help(self) -> None:
        name = self.command_combo.currentData()
        if name:
            self.run_git_command(["help", name], callback=lambda r: self.all_commands_output.setPlainText(r.output), timeout=120, risk_check=False)

    def reload_command_catalog(self) -> None:
        self.command_catalog = build_command_catalog()
        current = self.command_combo.currentData()
        self.command_combo.clear()
        for name, spec in self.command_catalog.items():
            self.command_combo.addItem(f"{name}  [{spec.category}]", name)
        if current:
            idx = self.command_combo.findData(current)
            if idx >= 0:
                self.command_combo.setCurrentIndex(idx)
        self._command_changed()

    # ------------------------------------------------------------------
    # Platform helpers
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Custom ACTIONS buttons
    # ------------------------------------------------------------------
    def add_custom_button(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            name = values.get("name", "").strip()
            commands = values.get("commands", "").strip()
            if not name or not commands:
                self.append_log("Custom 按钮未创建：名称或指令为空。")
                return
            if not self.register_custom_button(name, commands):
                self.append_log("Custom 按钮未创建：名称重复或参数无效。")
                return
            self.append_log(f"已新增 Custom 按钮：{name}")
        self.request_workspace_form(
            "新增 Custom 按钮",
            "自定义按钮会存放在右侧 ACTIONS 最后的 Custom 分组。commands 可输入一行或多行 shell/git 指令。",
            [("name", "按钮名称", "", False), ("commands", "一行或多行指令", "git status -sb", False, "multiline")],
            submitted,
        )

    def delete_custom_button(self) -> None:
        names = [item.get("name", "") for item in getattr(self, "custom_buttons", []) if item.get("name")]
        if not names:
            self.append_log("没有可删除的 Custom 按钮。")
            return
        def submitted(values: dict[str, str]) -> None:
            name = values.get("name", "").strip()
            before = len(self.custom_buttons)
            self.custom_buttons = [item for item in self.custom_buttons if item.get("name") != name]
            if len(self.custom_buttons) == before:
                self.append_log(f"未找到 Custom 按钮：{name}")
                return
            self._save_custom_buttons()
            self._rebuild_context_actions()
            self.append_log(f"已删除 Custom 按钮：{name}")
        self.request_workspace_form(
            "删除 Custom 按钮",
            "输入要删除的按钮名称。当前可选：" + ", ".join(names),
            [("name", "按钮名称", names[0], False)],
            submitted,
        )

    def run_custom_button_commands(self, commands: str) -> None:
        commands = commands.strip()
        if not commands:
            return
        self.run_shell_command(commands, callback=lambda _: self.refresh_all(), timeout=900)

    # ------------------------------------------------------------------
    # Platform CLI / SSH / HTTPS helpers
    # ------------------------------------------------------------------
    def _provider_host(self, provider: str) -> str:
        provider = provider.strip().lower()
        mapping = {
            "github": "github.com",
            "gitlab": "gitlab.com",
            "gitee": "gitee.com",
        }
        return mapping.get(provider, provider or "github.com")

    def _provider_name_from_host(self, host: str) -> str:
        host = host.lower()
        if "gitlab" in host:
            return "gitlab"
        if "gitee" in host:
            return "gitee"
        return "github"

    def _safe_account_token(self, text: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text.strip())
        return cleaned.strip("-") or "default"

    def _default_ssh_key_path(self, provider: str, account: str) -> str:
        name = f"id_ed25519_{self._provider_name_from_host(self._provider_host(provider))}_{self._safe_account_token(account)}"
        return str(Path.home() / ".ssh" / name)

    def _shell_quote(self, value: str) -> str:
        if os.name == "nt":
            return subprocess.list2cmdline([value])
        return shlex.quote(value)

    def _write_temp_python_script(self, name: str, body: str) -> Path:
        script_dir = self.config_path.parent / "scripts"
        script_dir.mkdir(parents=True, exist_ok=True)
        path = script_dir / name
        path.write_text(body, encoding="utf-8")
        return path

    def _run_python_script_async(self, script_name: str, script_body: str, callback: Optional[Callable[[GitResult], None]] = None, timeout: int = 300) -> None:
        script = self._write_temp_python_script(script_name, script_body)
        command = f"{self._shell_quote(sys.executable)} {self._shell_quote(str(script))}"
        self.run_shell_command(command, callback=callback, timeout=timeout)

    def configure_provider_ssh_from_menu(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            provider = values.get("provider", "github").strip().lower() or "github"
            account = values.get("account", "default").strip() or "default"
            email = values.get("email", "").strip() or f"{account}@git-terminal"
            key_path = values.get("key_path", "").strip() or self._default_ssh_key_path(provider, account)
            remote_name = values.get("remote", "origin").strip() or "origin"
            owner_repo = values.get("owner_repo", "").strip().strip("/")
            apply_remote = values.get("apply_remote", "yes").strip().lower() in {"", "y", "yes", "1", "true", "是"}
            host = self._provider_host(provider)
            alias = f"{host}-{self._safe_account_token(account)}"
            script = self._build_ssh_setup_python_script(host, alias, key_path, email)
            def after(result: GitResult) -> None:
                self._after_provider_ssh_setup(result, provider, alias, key_path, remote_name, owner_repo, apply_remote)
            self._run_python_script_async("setup_provider_ssh.py", script, callback=after, timeout=300)
        self.request_workspace_form(
            "多用户 SSH 一键配置",
            "为 GitHub / GitLab / Gitee 生成或复用独立 ed25519 key，写入 ~/.ssh/config 的 Host alias，自动 ssh 测试；可选同步修改当前仓库 remote URL。",
            [
                ("provider", "平台 github/gitlab/gitee", "github", False),
                ("account", "账号标识", "default", False),
                ("email", "Key 注释邮箱", "", False),
                ("key_path", "SSH 私钥路径", self._default_ssh_key_path("github", "default"), False),
                ("remote", "remote 名称", "origin", False),
                ("owner_repo", "owner/repo", "", False),
                ("apply_remote", "设置当前仓库 remote?", "yes", False),
            ],
            submitted,
        )

    def _build_ssh_setup_python_script(self, host: str, alias: str, key_path: str, email: str) -> str:
        payload = {
            "host": host,
            "alias": alias,
            "key_path": str(Path(key_path).expanduser()),
            "email": email,
        }
        payload_text = json.dumps(json.dumps(payload))
        return """from __future__ import annotations
import json
import os
import locale
import subprocess
from pathlib import Path

def decode_output(data):
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    encodings = ["utf-8", "utf-8-sig", locale.getpreferredencoding(False), "gb18030", "gbk", "cp936"]
    used = set()
    for enc in encodings:
        if not enc or enc.lower() in used:
            continue
        used.add(enc.lower())
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")

cfg = json.loads(PAYLOAD)
ssh_dir = Path.home() / ".ssh"
ssh_dir.mkdir(parents=True, exist_ok=True)
key_path = Path(cfg["key_path"]).expanduser()
key_path.parent.mkdir(parents=True, exist_ok=True)
if not key_path.exists():
    print("Generating SSH key:", key_path)
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-C", cfg["email"], "-f", str(key_path), "-N", ""], check=True)
else:
    print("SSH key already exists:", key_path)
try:
    os.chmod(key_path, 0o600)
except Exception as exc:
    print("chmod warning:", exc)
config_path = ssh_dir / "config"
block = "\nHost {alias}\n  HostName {host}\n  User git\n  IdentityFile {key}\n  IdentitiesOnly yes\n".format(alias=cfg["alias"], host=cfg["host"], key=key_path)
existing = config_path.read_text(encoding="utf-8", errors="replace") if config_path.exists() else ""
if "Host " + cfg["alias"] not in existing:
    with config_path.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(block.lstrip("\n"))
    print("Appended SSH config Host:", cfg["alias"])
else:
    print("SSH config Host already exists:", cfg["alias"])
print("Trying ssh-add; it is OK if no agent is running.")
subprocess.run(["ssh-add", str(key_path)], check=False)
print("Public key; copy this to the platform SSH Keys page if it has not been added:")
pub = Path(str(key_path) + ".pub")
if pub.exists():
    print(pub.read_text(encoding="utf-8", errors="replace").strip())
print("Testing SSH alias:", cfg["alias"])
proc = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-T", cfg["alias"]], text=False, capture_output=True, timeout=30)
print(decode_output(proc.stdout).strip())
print(decode_output(proc.stderr).strip())
print("SSH_TEST_RETURN_CODE=", proc.returncode)
""".replace("PAYLOAD", payload_text)

    def _after_provider_ssh_setup(self, result: GitResult, provider: str, alias: str, key_path: str, remote_name: str, owner_repo: str, apply_remote: bool) -> None:
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(result.output)
        okish = result.ok or "successfully authenticated" in result.output.lower() or "welcome" in result.output.lower()
        if owner_repo and apply_remote and self.runner.repo_path:
            ssh_url = f"git@{alias}:{owner_repo}.git"
            self.run_git_command(["remote", "set-url", remote_name, ssh_url], callback=lambda _: self._test_remote_after_config(remote_name), timeout=300)
            self.append_log(f"SSH 配置已写入，已设置 {remote_name} -> {ssh_url}，正在测试 remote。")
        else:
            self.append_log(("✓" if okish else "⚠") + f" SSH 配置完成。Host alias: {alias}；私钥: {key_path}。请确认公钥已添加到平台账号。")
        self.refresh_platform_statuses()

    def configure_provider_https_from_menu(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            provider = values.get("provider", "github").strip().lower() or "github"
            host = self._provider_host(provider)
            owner_repo = values.get("owner_repo", "").strip().strip("/")
            remote_name = values.get("remote", "origin").strip() or "origin"
            helper = values.get("helper", "manager-core").strip() or "manager-core"
            if not owner_repo:
                self.append_log("HTTPS 配置已取消：缺少 owner/repo。")
                return
            if not self.runner.repo_path:
                self.append_log("HTTPS 配置已取消：需要先打开一个本地仓库。")
                return
            url = f"https://{host}/{owner_repo}.git"
            command = "\n".join([
                f"git config --global credential.helper {self._shell_quote(helper)}",
                f"git remote set-url {self._shell_quote(remote_name)} {self._shell_quote(url)}",
                f"git ls-remote {self._shell_quote(remote_name)}",
            ])
            self.run_shell_command(command, callback=lambda r: self._after_https_setup(r, remote_name, url), timeout=300)
        self.request_workspace_form(
            "HTTPS 一键配置",
            "设置 credential.helper，修改当前仓库 remote 为 HTTPS，并自动执行 ls-remote 测试。",
            [
                ("provider", "平台 github/gitlab/gitee", "github", False),
                ("owner_repo", "owner/repo", "", False),
                ("remote", "remote 名称", "origin", False),
                ("helper", "credential.helper", "manager-core", False),
            ],
            submitted,
        )

    def _after_https_setup(self, result: GitResult, remote_name: str, url: str) -> None:
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(result.output)
        self.append_log(("✓" if result.ok else "⚠") + f" HTTPS remote 配置完成：{remote_name} -> {url}。ls-remote 已执行，详情见平台输出。")
        self.refresh_all()

    def _test_remote_after_config(self, remote_name: str) -> None:
        self.run_git_command(["ls-remote", remote_name], callback=lambda r: self._after_remote_test(r, remote_name), timeout=300)

    def _after_remote_test(self, result: GitResult, remote_name: str) -> None:
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(result.output)
        self.append_log(("✓" if result.ok else "⚠") + f" remote 测试完成：{remote_name}。")
        self.refresh_all()

    def test_provider_auth_from_menu(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            provider = values.get("provider", "github").strip().lower() or "github"
            account = values.get("account", "").strip()
            remote_name = values.get("remote", "origin").strip() or "origin"
            host = self._provider_host(provider)
            ssh_target = f"{host}-{self._safe_account_token(account)}" if account else host
            lines = [f"ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -T {self._shell_quote(ssh_target)}"]
            if self.runner.repo_path:
                lines.append(f"git ls-remote {self._shell_quote(remote_name)}")
            self.run_shell_command("\n".join(lines), callback=lambda r: self._after_auth_test(r, ssh_target, remote_name), timeout=120)
        self.request_workspace_form(
            "测试平台认证",
            "测试 SSH Host 或多用户 Host alias；若当前已打开仓库，会同时测试 git ls-remote。",
            [("provider", "平台 github/gitlab/gitee", "github", False), ("account", "账号标识，可空", "", False), ("remote", "remote 名称", "origin", False)],
            submitted,
        )

    def _after_auth_test(self, result: GitResult, ssh_target: str, remote_name: str) -> None:
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(result.output)
        self.append_log(("✓" if result.ok else "⚠") + f" 认证测试完成：SSH={ssh_target}, remote={remote_name}。")

    def _powershell_script_file_command(self, script: str, tool: str) -> str:
        # Avoid Windows cmd.exe command-line length limits: write the installer
        # script to a .ps1 file instead of passing a huge -EncodedCommand string.
        scripts_dir = Path(tempfile.gettempdir()) / "git-terminal-installers"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = scripts_dir / f"install-{tool}-{os.getpid()}.ps1"
        script_path.write_text(script, encoding="utf-8-sig")
        self._cli_install_scripts.append(script_path)
        return f"powershell.exe -NoProfile -ExecutionPolicy Bypass -File {self._shell_quote(str(script_path))}"

    def _windows_portable_cli_install_script(self, tool: str) -> str:
        exe = "gh.exe" if tool == "gh" else "glab.exe"
        api_url = "https://api.github.com/repos/cli/cli/releases/latest" if tool == "gh" else "https://gitlab.com/api/v4/projects/gitlab-org%2Fcli/releases/permalink/latest"
        asset_selector = r"windows_amd64\.zip$" if tool == "gh" else r"windows_amd64\.zip$|windows_x86_64\.zip$"
        source_name = "GitHub official release zip" if tool == "gh" else "GitLab official release zip"
        return f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$Tool = '{tool}'
$Exe = '{exe}'
$ApiUrl = '{api_url}'
$AssetSelector = '{asset_selector}'
$SourceName = '{source_name}'

function Write-Step([string]$Text) {{ Write-Host "[git-terminal] $Text" }}
function Add-UserPath([string]$Dir) {{
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ([string]::IsNullOrWhiteSpace($current)) {{
        [Environment]::SetEnvironmentVariable('Path', $Dir, 'User')
    }} elseif ((";$current;" -notlike "*;$Dir;*")) {{
        [Environment]::SetEnvironmentVariable('Path', "$current;$Dir", 'User')
    }}
    if ((";$env:Path;" -notlike "*;$Dir;*")) {{ $env:Path = "$Dir;$env:Path" }}
}}
function First-NonEmptyUrl($Item) {{
    if ($Item.browser_download_url) {{ return [string]$Item.browser_download_url }}
    if ($Item.direct_asset_url) {{ return [string]$Item.direct_asset_url }}
    if ($Item.url) {{ return [string]$Item.url }}
    return ''
}}
function Find-AssetUrl($Release) {{
    $items = @()
    if ($Release.assets) {{
        if ($Release.assets.links) {{ $items += $Release.assets.links }}
        if ($Release.assets -is [System.Array]) {{ $items += $Release.assets }}
    }}
    foreach ($item in $items) {{
        $name = [string]$item.name
        $url = First-NonEmptyUrl $item
        if (($name -match $AssetSelector) -or ($url -match $AssetSelector)) {{ return $url }}
    }}
    throw "未在最新 release 中找到 $Tool 的 Windows amd64/x86_64 zip 资产。"
}}

$existing = Get-Command $Tool -ErrorAction SilentlyContinue
if ($existing) {{
    Write-Step "已检测到 $Tool：$($existing.Source)；只做版本检查。"
    & $Tool --version
    exit $LASTEXITCODE
}}

$binDir = Join-Path $env:LOCALAPPDATA 'GitTerminal\bin'
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$target = Join-Path $binDir $Exe

if (Test-Path $target) {{
    Write-Step "已检测到便携安装文件：$target；只做版本检查。"
    Add-UserPath $binDir
    & $target --version
    exit $LASTEXITCODE
}}

Write-Step "未检测到 $Tool，且没有可用包管理器；改用 $SourceName 安装到当前用户目录。"
$headers = @{{ 'User-Agent' = 'git-terminal' }}
$release = Invoke-RestMethod -Uri $ApiUrl -Headers $headers
$url = Find-AssetUrl $release
$name = Split-Path ([System.Uri]$url).AbsolutePath -Leaf
$archive = Join-Path $env:TEMP $name
$extract = Join-Path $env:TEMP ("git-terminal-$Tool-" + [Guid]::NewGuid().ToString('N'))

Write-Step "下载：$url"
Invoke-WebRequest -Uri $url -OutFile $archive -UseBasicParsing -Headers $headers
New-Item -ItemType Directory -Force -Path $extract | Out-Null
Expand-Archive -Path $archive -DestinationPath $extract -Force
$found = Get-ChildItem -Path $extract -Filter $Exe -Recurse -File | Select-Object -First 1
if (-not $found) {{ throw "压缩包中未找到 $Exe。" }}
Copy-Item -Path $found.FullName -Destination $target -Force
Add-UserPath $binDir
Write-Step "已安装到：$target"
Write-Step "已把 $binDir 写入当前用户 PATH；新开的终端会自动继承。"
& $target --version
exit $LASTEXITCODE
"""

    def _cli_install_command(self, tool: str) -> tuple[Optional[str], str]:
        tool = "gh" if tool == "gh" else "glab"
        if shutil.which(tool):
            return f"{self._shell_quote(tool)} --version", f"已检测到 {tool}，只执行版本检查，不重复安装。"

        if os.name == "nt":
            candidates: list[tuple[str, str]] = []
            winget_id = "GitHub.cli" if tool == "gh" else "GLab.GLab"
            if shutil.which("winget"):
                candidates.append(("winget", f"winget install --id {winget_id} -e --accept-package-agreements --accept-source-agreements"))
            if shutil.which("choco"):
                candidates.append(("choco", f"choco install {tool} -y"))
            if shutil.which("scoop"):
                candidates.append(("scoop", f"scoop install {tool}"))
            if candidates:
                manager, install = candidates[0]
                return f"{install} && {tool} --version", f"未检测到 {tool}；检测到 {manager}，将只使用该安装器安装。"
            script = self._windows_portable_cli_install_script(tool)
            return self._powershell_script_file_command(script, tool), f"未检测到 {tool}，且没有 winget / choco / scoop；将从官方 release 下载 Windows zip 并安装到当前用户目录。PowerShell 脚本已写入临时 .ps1，避免 cmd 命令行过长。"

        if sys.platform == "darwin":
            if not shutil.which("brew"):
                return None, f"未检测到 {tool}，且当前 macOS 环境没有 Homebrew。已停止。"
            return f"brew install {tool} && {tool} --version", f"未检测到 {tool}；检测到 Homebrew，将使用 brew 安装。"

        linux_candidates = [
            ("brew", f"brew install {tool}"),
            ("apt-get", f"sudo apt-get update && sudo apt-get install -y {tool}"),
            ("dnf", f"sudo dnf install -y {tool}"),
            ("yum", f"sudo yum install -y {tool}"),
            ("pacman", f"sudo pacman -Sy --noconfirm {tool}"),
            ("snap", f"sudo snap install {tool}"),
        ]
        for manager, install in linux_candidates:
            if shutil.which(manager):
                return f"set -e\n{install}\n{tool} --version", f"未检测到 {tool}；检测到 {manager}，将只使用该安装器安装。"
        return None, f"未检测到 {tool}，且当前系统没有可用安装器：brew / apt-get / dnf / yum / pacman / snap。已停止。"

    def _install_cli_tool(self, tool: str) -> None:
        command, message = self._cli_install_command(tool)
        self.append_log(message)
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(message)
        if not command:
            self.set_terminal_state("warning", "SKIP")
            return
        self.run_shell_command(command, callback=lambda r: self._after_cli_install(r, tool), timeout=1200)

    def install_gh_cli(self) -> None:
        self._install_cli_tool("gh")

    def install_glab_cli(self) -> None:
        self._install_cli_tool("glab")

    def _after_cli_install(self, result: GitResult, tool: str) -> None:
        if hasattr(self, "platform_output"):
            self.platform_output.setPlainText(result.output)
        self.refresh_platform_statuses()
        if result.ok:
            self.append_log(f"✓ {tool} 已可用。")
            if tool == "gh":
                self.show_github_cli_page()
            else:
                self.show_gitlab_cli_page()
        else:
            self.append_log(f"✗ {tool} 安装失败或版本检查失败；未跳转 CLI 页面。请查看平台输出。")

    def _set_platform_tab_by_text(self, tab_text: str) -> None:
        if not hasattr(self, "platform_tabs"):
            return
        for index in range(self.platform_tabs.count()):
            if self.platform_tabs.tabText(index) == tab_text:
                self.platform_tabs.setCurrentIndex(index)
                return

    def show_github_cli_page(self) -> None:
        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(8)
        self._set_platform_tab_by_text("GitHub")

    def show_gitlab_cli_page(self) -> None:
        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(8)
        self._set_platform_tab_by_text("GitLab")

    def gh_repo_clone_interactive(self) -> None:
        self._cli_clone_interactive("gh")

    def glab_repo_clone_interactive(self) -> None:
        self._cli_clone_interactive("glab")

    def _cli_clone_interactive(self, tool: str) -> None:
        def submitted(values: dict[str, str]) -> None:
            repo = values.get("repo", "").strip()
            parent = values.get("parent", str(Path.cwd())).strip() or str(Path.cwd())
            if not repo:
                self.append_log(f"{tool} clone 已取消：缺少仓库。")
                return
            parent_path = Path(parent).expanduser().resolve()
            try:
                parent_path.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                self.append_log(f"{tool} clone 已取消：父目录无法创建：{parent_path}\n{exc}")
                return
            command = f"cd {self._shell_quote(str(parent_path))}\n{tool} repo clone {self._shell_quote(repo)}"
            self.run_shell_command(command, callback=lambda _: self.refresh_all(), timeout=900)
        self.request_workspace_form(
            f"{tool} repo clone",
            "输入 owner/repo 或完整 URL，并选择 clone 父目录；目录不存在会自动创建。",
            [("repo", "owner/repo 或 URL", "", False), ("parent", "clone 父目录", str(Path.cwd()), False, "folder")],
            submitted,
        )

    def gh_repo_create_interactive(self) -> None:
        self._repo_create_interactive("gh")

    def glab_repo_create_interactive(self) -> None:
        self._repo_create_interactive("glab")

    def _repo_create_interactive(self, tool: str) -> None:
        def submitted(values: dict[str, str]) -> None:
            name = values.get("name", "").strip()
            visibility = values.get("visibility", "private").strip().lower() or "private"
            if not name:
                self.append_log(f"{tool} repo create 已取消：仓库名为空。")
                return
            vis_arg = "--public" if visibility == "public" else "--private"
            source = " --source . --remote origin" if values.get("source", "yes").strip().lower() in {"", "yes", "y", "1", "true", "是"} else ""
            command = f"{tool} repo create {self._shell_quote(name)} {vis_arg}{source}"
            self.run_shell_command(command, callback=lambda _: self.refresh_all(), timeout=300)
        self.request_workspace_form(
            f"{tool} repo create",
            "交互式创建远程仓库；source=yes 时尝试把当前目录作为源并设置 origin。",
            [("name", "仓库名", "", False), ("visibility", "public/private", "private", False), ("source", "使用当前仓库作为 source?", "yes", False)],
            submitted,
        )

    def gh_pr_create_interactive(self) -> None:
        self._pr_mr_create_interactive("gh", "pr")

    def glab_mr_create_interactive(self) -> None:
        self._pr_mr_create_interactive("glab", "mr")

    def _pr_mr_create_interactive(self, tool: str, kind: str) -> None:
        def submitted(values: dict[str, str]) -> None:
            title = values.get("title", "").strip()
            body = values.get("body", "").strip()
            base = values.get("base", "").strip()
            head = values.get("head", "").strip()
            if not title:
                self.append_log(f"{tool} {kind} create 已取消：标题为空。")
                return
            args = [tool, kind, "create", "--title", title]
            if body:
                args += ["--body", body]
            if base:
                args += ["--base", base]
            if head:
                args += ["--head", head]
            self.run_shell_command(" ".join(self._shell_quote(x) for x in args), callback=lambda _: self.refresh_all(), timeout=300)
        self.request_workspace_form(
            f"{tool} {kind} create",
            "交互式创建 PR/MR。base/head 可留空，由 CLI 使用默认值。",
            [("title", "标题", "", False), ("body", "描述", "", False), ("base", "base", "", False), ("head", "head", "", False)],
            submitted,
        )

    def gh_pr_checkout_interactive(self) -> None:
        self._pr_mr_checkout_interactive("gh", "pr")

    def glab_mr_checkout_interactive(self) -> None:
        self._pr_mr_checkout_interactive("glab", "mr")

    def _pr_mr_checkout_interactive(self, tool: str, kind: str) -> None:
        self.request_terminal_text(
            f"{tool} {kind} checkout",
            "编号 / URL / 分支：",
            lambda value: self.run_shell_command(f"{tool} {kind} checkout {self._shell_quote(value.strip())}", callback=lambda _: self.refresh_all(), timeout=300) if value.strip() else None,
        )

    def gh_issue_create_interactive(self) -> None:
        self._issue_create_interactive("gh")

    def glab_issue_create_interactive(self) -> None:
        self._issue_create_interactive("glab")

    def _issue_create_interactive(self, tool: str) -> None:
        def submitted(values: dict[str, str]) -> None:
            title = values.get("title", "").strip()
            body = values.get("body", "").strip()
            if not title:
                self.append_log(f"{tool} issue create 已取消：标题为空。")
                return
            args = [tool, "issue", "create", "--title", title]
            if body:
                args += ["--body", body]
            self.run_shell_command(" ".join(self._shell_quote(x) for x in args), callback=lambda _: self.refresh_all(), timeout=300)
        self.request_workspace_form(
            f"{tool} issue create",
            "交互式创建 issue。",
            [("title", "标题", "", False), ("body", "描述", "", False)],
            submitted,
        )

    def gitee_list_repos(self) -> None:
        token = self.gitee_token.text().strip()
        user = self.gitee_user.text().strip()
        if not token or not user:
            QMessageBox.warning(self, "缺少参数", "请输入 Gitee token 和用户名/组织。")
            return
        try:
            import requests

            url = f"https://gitee.com/api/v5/users/{user}/repos"
            resp = requests.get(url, params={"access_token": token, "per_page": 50}, timeout=20)
            data = resp.json()
            self.platform_output.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as exc:
            self.platform_output.setPlainText(str(exc))

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def create_rescue_branch(self) -> None:
        self.request_terminal_text(
            "Rescue Branch",
            "救援分支名：",
            lambda name: self.run_git_command(["switch", "-c", name.strip(), "HEAD@{1}"], callback=lambda _: self.refresh_all()) if name.strip() else None,
            "rescue/head-1",
        )

    def copy_last_command(self) -> None:
        text = self.command_log.toPlainText().splitlines()
        for line in reversed(text):
            if line.startswith("git ") or line.startswith("✓ git ") or line.startswith("✗ git "):
                QApplication.clipboard().setText(line.replace("✓ ", "").replace("✗ ", ""))
                return

    def _navigator_clicked(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, dict) and data.get("kind") == "recent-repo":
            path = data.get("path")
            if isinstance(path, str):
                self.open_recent_repository(path)
            return
        text = item.text(0)
        mapping = {
            "Workspace": 0,
            "Changed files": 0,
            "Staged files": 0,
            "Untracked files": 0,
            "History": 1,
            "Current branch": 1,
            "All branches": 1,
            "Reflog": 6,
            "Bisect": 7,
            "Refs": 2,
            "Local branches": 2,
            "Remote branches": 2,
            "Tags": 4,
            "Worktrees": 6,
            "Remotes": 3,
            "origin": 3,
            "upstream": 3,
            "Collaboration": 8,
            "GitHub": 8,
            "Gitee": 8,
            "GitLab": 8,
            "Bitbucket": 8,
            "Pull Requests": 8,
            "Issues": 8,
            "Releases": 8,
            "CI": 8,
            "Advanced": 6,
            "Stash": 4,
            "Submodules": 6,
            "LFS": 6,
            "Hooks": 6,
            "Config": 6,
            "Objects": 6,
            "Maintenance": 6,
            "Raw Commands": 7,
        }
        if text in mapping:
            self.tabs.setCurrentIndex(mapping[text])
            if mapping[text] == 0:
                self.refresh_worktree()

    def open_recent_repository(self, path: str) -> None:
        repo = Path(path)
        if not repo.exists() or not repo.is_dir():
            self.set_terminal_state("warning", "WARN")
            self.append_log(f"最近仓库路径无效：{path}")
            self.recent_repositories = [p for p in self.recent_repositories if p != path]
            self._save_recent_repositories()
            self._populate_navigator()
            return
        self.runner.set_repo(repo)
        check = self.runner.run(["rev-parse", "--is-inside-work-tree"])
        if not check.ok:
            self.set_terminal_state("warning", "WARN")
            self.append_log(f"该路径不是 Git 仓库：{path}")
            return
        self._remember_repository(repo)
        self.refresh_all()

    def show_user_accounts(self) -> None:
        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(8)
        if hasattr(self, "platform_tabs"):
            self.platform_tabs.setCurrentIndex(0)
        self.refresh_platform_statuses()

    def show_terminal_help(self) -> None:
        QMessageBox.information(
            self,
            "原生命令入口",
            "底部命令栏支持输入：\n"
            ":git status -sb\n"
            ":git cat-file -p HEAD\n"
            ":git update-ref refs/heads/test <hash>\n\n"
            "高风险命令会要求输入确认词。",
        )

    def show_shortcuts(self) -> None:
        QMessageBox.information(
            self,
            "快捷键",
            "F5 刷新\nCtrl+O 打开仓库\nEnter 在底部命令栏执行 Raw Git 命令\n"
            "常用 Git 快捷键可在各面板按钮和右键菜单中使用。",
        )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 Git Terminal",
            "Git Terminal\n\n"
            "一个基于本机 git CLI 的 PyQt Git 管理终端。\n"
            "高频功能图形化，全部 Git 命令通过高级参数面板和 Raw Git Terminal 兜底。",
        )
