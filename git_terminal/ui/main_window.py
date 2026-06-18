from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PyQt6.QtCore import Qt, QThread, QPoint
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QTextCursor
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
    QSizePolicy,
    QSplitter,
    QStackedLayout,
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
from git_terminal.ui.workers import GitCommandWorker, ShellCommandWorker
from git_terminal.ui.theme import apply_theme
from git_terminal.ui.commit_graph import CommitGraphView, GraphCommit
from git_terminal.ui.vscode_shell import ActivityBar, BottomPanel, SidePanel, TopCommandBar


class CloneDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Clone Repository")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("git@github.com:org/repo.git 或 https://...")
        self.dest = QLineEdit()
        browse = QPushButton("选择目录")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.dest)
        row.addWidget(browse)
        form.addRow("远程 URL", self.url)
        form.addRow("目标目录", row)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择 clone 到的父目录")
        if directory:
            self.dest.setText(directory)


class RemoteDialog(QDialog):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.url = QLineEdit()
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
        self.resize(1180, 760)
        self.runner = GitRunner()
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

        self._build_actions()
        self._build_ui()
        self._wire_shortcuts()
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self, self.theme_mode, self.theme_accent)
        self.detect_environment()
        self.refresh_all()

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
        changes_menu.addAction("Stage All", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all()))
        changes_menu.addAction("Unstage All", lambda: self.run_git_command(["restore", "--staged", "."], callback=lambda _: self.refresh_all()))
        changes_menu.addAction("Commit...", self.commit_changes)
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

        self.left_sidebar = SidePanel("GIT TERMINAL", side="left", min_size=220)
        self.left_sidebar.set_collapse_callback(lambda: self.set_left_sidebar_visible(False))
        self.left_sidebar.add_header_action("+").clicked.connect(self.open_repository)
        self.left_sidebar.add_header_action("↻").clicked.connect(self.refresh_all)
        self.left_sidebar.add_header_action("⋯").clicked.connect(self.show_terminal_help)
        self.navigator = QTreeWidget()
        self.navigator.setHeaderHidden(True)
        self.navigator.setMinimumWidth(0)
        self.navigator.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._populate_navigator()
        self.navigator.itemClicked.connect(self._navigator_clicked)
        self.left_sidebar.body_layout.addWidget(self.navigator)

        self.center_splitter = QSplitter(Qt.Orientation.Vertical)
        self.center_splitter.setChildrenCollapsible(True)
        self.center_splitter.setHandleWidth(1)
        self.center_splitter.setMinimumWidth(120)
        self.center_splitter.splitterMoved.connect(self._on_center_splitter_moved)

        workspace = QWidget()
        self.workspace_container = workspace
        workspace.setMinimumHeight(0)
        self.workspace_stack = QStackedLayout(workspace)
        self.workspace_stack.setContentsMargins(0, 0, 0, 0)
        self.workspace_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self.workspace_content = QWidget()
        workspace_layout = QVBoxLayout(self.workspace_content)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        self.status_bar_label = QLabel("Repo: - | Branch: - | HEAD: - | Remote: - | Ahead: 0 | Behind: 0 | Dirty: 0 | Mode: -")
        self.status_bar_label.setObjectName("TopStatusLabel")
        self.status_bar_label.setMinimumHeight(30)
        workspace_layout.addWidget(self.status_bar_label)
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

        self.center_splitter.addWidget(workspace)
        self.center_splitter.addWidget(self.bottom_panel)
        self.center_splitter.setStretchFactor(0, 3)
        self.center_splitter.setStretchFactor(1, 1)
        self.center_splitter.setSizes([520, 180])

        self.right_sidebar = SidePanel("CONTEXT", side="right", min_size=220)
        self.right_sidebar.set_collapse_callback(lambda: self.set_right_sidebar_visible(False))
        self.context_panel = QWidget()
        self.context_panel.setMinimumWidth(0)
        context_layout = QVBoxLayout(self.context_panel)
        context_layout.setContentsMargins(8, 8, 8, 8)
        context_layout.setSpacing(8)
        self.context_buttons = []
        for text, handler in [
            ("git status -sb", lambda: self.run_git_command(["status", "-sb"], callback=lambda _: self.refresh_all())),
            ("Stage All", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all())),
            ("Unstage All", lambda: self.run_git_command(["restore", "--staged", "."], callback=lambda _: self.refresh_all())),
            ("Fetch --all --prune", lambda: self.run_git_command(["fetch", "--all", "--prune"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Pull --ff-only", lambda: self.run_git_command(["pull", "--ff-only"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Push", lambda: self.run_git_command(["push"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Reflog", lambda: self.run_git_command(["reflog", "--date=iso"], callback=self.show_result_in_log)),
            ("Rescue Branch from HEAD@{1}", self.create_rescue_branch),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            context_layout.addWidget(btn)
            self.context_buttons.append(btn)
        context_layout.addStretch(1)
        self.right_sidebar.body_layout.addWidget(self.context_panel)

        self.horizontal_splitter.addWidget(self.left_sidebar)
        self.horizontal_splitter.addWidget(self.center_splitter)
        self.horizontal_splitter.addWidget(self.right_sidebar)
        self.horizontal_splitter.setSizes([230, 720, 230])

        content_layout.addWidget(self.horizontal_splitter)
        root_layout.addWidget(content, 1)
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

        self._build_workspace_tab()
        self._build_history_tab()
        self._build_branch_tab()
        self._build_remote_tab()
        self._build_tag_stash_tab()
        self._build_conflict_tab()
        self._build_advanced_tab()
        self._build_all_commands_tab()
        self._build_platform_tab()
        self._compact_ui_controls()

    def _build_visible_top_menus(self) -> None:
        """Render full Git menus inside the template top bar.

        This is separate from the native QMenuBar, because users expect the
        template's top row itself to expose repository operations.
        """
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
            ("打开本地仓库...", self.open_repository),
            ("创建/初始化本地仓库...", self.init_repository),
            ("Clone 远程仓库...", self.clone_repository),
            ("创建 GitHub 远程仓库...", self.create_remote_repository),
            None,
            ("刷新全部", self.refresh_all),
        ])
        add_button("仓库", [
            ("Status -sb", lambda: self.run_git_command(["status", "-sb"], callback=lambda _: self.refresh_all())),
            ("查看配置", lambda: self.run_git_command(["config", "--list", "--show-origin"], callback=self.show_result_in_log)),
            ("设置 user.name...", self.set_git_user_name),
            ("设置 user.email...", self.set_git_user_email),
        ])
        add_button("更改", [
            ("Stage All", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all())),
            ("Unstage All", lambda: self.run_git_command(["restore", "--staged", "."], callback=lambda _: self.refresh_all())),
            ("Commit...", self.commit_changes),
            ("Diff", lambda: self.run_git_command(["diff"], callback=self.show_result_in_log)),
            ("Diff --staged", lambda: self.run_git_command(["diff", "--staged"], callback=self.show_result_in_log)),
        ])
        add_button("分支", [
            ("创建分支...", self.create_branch_from_menu),
            ("切换分支...", self.switch_branch_from_menu),
            ("Merge...", self.merge_branch_from_menu),
            ("Rebase...", self.rebase_branch_from_menu),
            ("打开分支页", lambda: self.tabs.setCurrentIndex(2) if hasattr(self, "tabs") else None),
            ("Reflog", lambda: self.run_git_command(["reflog", "--date=iso"], callback=self.show_result_in_log)),
        ])
        add_button("远程", [
            ("Remote -v", lambda: self.run_git_command(["remote", "-v"], callback=self.show_result_in_log)),
            ("添加 Remote...", self.add_remote),
            ("Fetch", lambda: self.run_git_command(["fetch"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Fetch --all --prune", lambda: self.run_git_command(["fetch", "--all", "--prune"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Pull", lambda: self.run_git_command(["pull"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Pull --ff-only", lambda: self.run_git_command(["pull", "--ff-only"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Pull --rebase", lambda: self.run_git_command(["pull", "--rebase"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Push", lambda: self.run_git_command(["push"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Push -u...", self.push_current_branch_upstream_from_menu),
            ("Push --tags", lambda: self.run_git_command(["push", "--tags"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("删除远程分支...", self.delete_remote_branch),
        ])
        add_button("标签", [
            ("创建标签...", self.create_tag_from_menu),
            ("Tag 列表", lambda: self.tabs.setCurrentIndex(4) if hasattr(self, "tabs") else None),
            ("Push --tags", lambda: self.run_git_command(["push", "--tags"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Stash Push -u", self.stash_push),
            ("Stash List", lambda: self.run_git_command(["stash", "list"], callback=self.show_result_in_log)),
            ("Stash Pop Selected", self.stash_pop),
        ])
        add_button("高级", [
            ("全部 Git 命令", lambda: self.tabs.setCurrentIndex(7) if hasattr(self, "tabs") else None),
            ("Object Inspector", lambda: self.tabs.setCurrentIndex(6) if hasattr(self, "tabs") else None),
            ("Cherry-pick...", self.cherry_pick_from_menu),
            ("Revert...", self.revert_from_menu),
            ("Reset --hard...", self.reset_hard_from_menu),
            None,
            ("Worktree List", lambda: self.run_git_command(["worktree", "list"], callback=self.show_result_in_log)),
            ("Worktree Add...", self.worktree_add_from_menu),
            ("Worktree Remove...", self.worktree_remove_from_menu),
            ("Submodule Status", lambda: self.run_git_command(["submodule", "status", "--recursive"], callback=self.show_result_in_log, timeout=300)),
            ("Submodule Add...", self.submodule_add_from_menu),
            ("Submodule Update --init --recursive", lambda: self.run_git_command(["submodule", "update", "--init", "--recursive"], callback=self.show_result_in_log, timeout=900)),
            ("LFS Status", lambda: self.run_git_command(["lfs", "status"], callback=self.show_result_in_log, timeout=300)),
            ("LFS Track...", self.lfs_track_from_menu),
            ("Bisect Start", lambda: self.run_git_command(["bisect", "start"], callback=self.show_result_in_log)),
            ("Bisect Good...", self.bisect_good_from_menu),
            ("Bisect Bad...", self.bisect_bad_from_menu),
            ("Bisect Reset", lambda: self.run_git_command(["bisect", "reset"], callback=self.show_result_in_log)),
            ("fsck --full", lambda: self.run_git_command(["fsck", "--full"], callback=self.show_result_in_log, timeout=300)),
            ("gc", lambda: self.run_git_command(["gc"], callback=self.show_result_in_log, timeout=300)),
            ("count-objects -vH", lambda: self.run_git_command(["count-objects", "-vH"], callback=self.show_result_in_log)),
        ])
        add_button("平台", [
            ("GitHub auth status", lambda: self.run_external_command(["gh", "auth", "status"])),
            ("GitHub repo list", lambda: self.run_external_command(["gh", "repo", "list", "--limit", "50"])),
            ("GitHub create repo...", self.create_remote_repository),
            ("GitLab auth status", lambda: self.run_external_command(["glab", "auth", "status"])),
            ("打开平台页", lambda: self.tabs.setCurrentIndex(8) if hasattr(self, "tabs") else None),
        ])
        add_button("视图", [
            ("显示/隐藏左侧栏", self.toggle_left_sidebar),
            ("显示/隐藏右侧栏", self.toggle_right_sidebar),
            ("显示/隐藏底部终端", self.toggle_bottom_panel),
            ("放大/缩小终端", self.toggle_bottom_maximized),
            None,
            ("工作区", lambda: self.tabs.setCurrentIndex(0) if hasattr(self, "tabs") else None),
            ("历史", lambda: self.tabs.setCurrentIndex(1) if hasattr(self, "tabs") else None),
            ("分支", lambda: self.tabs.setCurrentIndex(2) if hasattr(self, "tabs") else None),
            ("远程", lambda: self.tabs.setCurrentIndex(3) if hasattr(self, "tabs") else None),
        ])

    def activate_activity_tab(self, index: int, tab_index: int) -> None:
        self.set_left_sidebar_visible(True)
        if 0 <= tab_index < self.tabs.count():
            self.tabs.setCurrentIndex(tab_index)

    def set_left_sidebar_visible(self, visible: bool) -> None:
        self.left_sidebar.setVisible(visible)
        self.top_bar.left_sidebar_button.setChecked(visible)
        if visible:
            self.horizontal_splitter.setSizes([230, 720, 230 if self.right_sidebar.isVisible() else 0])

    def set_right_sidebar_visible(self, visible: bool) -> None:
        self.right_sidebar.setVisible(visible)
        self.top_bar.right_sidebar_button.setChecked(visible)
        if visible:
            self.horizontal_splitter.setSizes([230 if self.left_sidebar.isVisible() else 0, 720, 230])

    def set_bottom_panel_visible(self, visible: bool) -> None:
        if not visible and getattr(self, "_bottom_maximized", False):
            self.restore_bottom_panel()
        self.bottom_panel.setVisible(visible)
        self.top_bar.bottom_panel_button.setChecked(visible)
        if visible and not getattr(self, "_bottom_maximized", False):
            self.center_splitter.setSizes([520, 180])

    def toggle_left_sidebar(self) -> None:
        self.set_left_sidebar_visible(not self.left_sidebar.isVisible())

    def toggle_right_sidebar(self) -> None:
        self.set_right_sidebar_visible(not self.right_sidebar.isVisible())

    def toggle_bottom_panel(self) -> None:
        self.set_bottom_panel_visible(not self.bottom_panel.isVisible())

    def _on_horizontal_splitter_moved(self, _pos: int, _index: int) -> None:
        sizes = self.horizontal_splitter.sizes()
        if len(sizes) >= 3:
            if self.left_sidebar.isVisible() and sizes[0] <= 48:
                self.set_left_sidebar_visible(False)
            if self.right_sidebar.isVisible() and sizes[2] <= 48:
                self.set_right_sidebar_visible(False)

    def _on_center_splitter_moved(self, _pos: int, _index: int) -> None:
        if getattr(self, "_bottom_maximized", False):
            return
        sizes = self.center_splitter.sizes()
        if len(sizes) >= 2 and self.bottom_panel.isVisible():
            top, bottom = sizes[0], sizes[1]
            total = max(1, top + bottom)
            # Allow the terminal to grow naturally. Only collapse or maximize
            # when the user drags to an extreme edge.
            if bottom <= 36:
                self.set_bottom_panel_visible(False)
            elif top <= 12 and bottom / total >= 0.93:
                self.maximize_bottom_panel()

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
        if hasattr(self, "workspace_container"):
            self.workspace_container.setVisible(False)
        if hasattr(self, "terminal_max_btn"):
            self.terminal_max_btn.setText("▢")
            self.terminal_max_btn.setToolTip("恢复工作区 + 底部终端布局")

    def restore_bottom_panel(self) -> None:
        self._bottom_maximized = False
        if hasattr(self, "workspace_container"):
            self.workspace_container.setVisible(True)
        sizes = getattr(self, "_last_center_sizes", None) or [520, 180]
        if sum(sizes) <= 0:
            sizes = [520, 180]
        self.center_splitter.setSizes(sizes)
        if hasattr(self, "terminal_max_btn"):
            self.terminal_max_btn.setText("▣")
            self.terminal_max_btn.setToolTip("展开终端占领整个工作区域 / Restore")

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
        theme_menu = menu.addMenu("主题")
        dark = theme_menu.addAction("深色模式")
        light = theme_menu.addAction("浅色模式")
        dark.triggered.connect(lambda: self.change_theme_mode("dark"))
        light.triggered.connect(lambda: self.change_theme_mode("light"))
        accent_menu = menu.addMenu("配色")
        for key, label in [("blue", "蓝色"), ("purple", "紫色"), ("green", "绿色"), ("orange", "橙色")]:
            accent_menu.addAction(label, lambda _checked=False, k=key: self.change_theme_accent(k))
        menu.addSeparator()
        menu.addAction("显示左侧栏", lambda: self.set_left_sidebar_visible(True))
        menu.addAction("显示右侧栏", lambda: self.set_right_sidebar_visible(True))
        menu.addAction("显示底部栏", lambda: self.set_bottom_panel_visible(True))
        menu.addSeparator()
        menu.addAction("关于 Git Terminal", self.show_about)
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

    def request_workspace_form(
        self,
        title: str,
        message: str,
        fields: list[tuple[str, str, str, bool]],
        callback: Callable[[dict[str, str]], None],
    ) -> None:
        """Show a workspace-covering form with all required inputs at once."""
        if hasattr(self, "terminal_stack") and hasattr(self, "terminal_content"):
            self.terminal_stack.setCurrentWidget(self.terminal_content)
        self.workspace_prompt_callback = callback
        self.workspace_prompt_title.setText(title)
        self.workspace_prompt_message.setText(message)
        self._clear_workspace_prompt_form()
        self.workspace_prompt_fields = {}
        first_input = None
        for key, label, default, password in fields:
            edit = QLineEdit()
            edit.setObjectName("workspacePromptInput")
            edit.setText(default)
            edit.setEchoMode(QLineEdit.EchoMode.Password if password else QLineEdit.EchoMode.Normal)
            edit.returnPressed.connect(self._submit_workspace_prompt)
            self.workspace_prompt_form.addRow(label, edit)
            self.workspace_prompt_fields[key] = edit
            if first_input is None:
                first_input = edit
        self.workspace_overlay.setVisible(True)
        self.workspace_overlay.raise_()
        self.workspace_stack.setCurrentWidget(self.workspace_overlay)
        if first_input is not None:
            first_input.setFocus()
            first_input.selectAll()

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
        values = {key: edit.text() for key, edit in getattr(self, "workspace_prompt_fields", {}).items()}
        callback = getattr(self, "workspace_prompt_callback", None)
        self.workspace_overlay.setVisible(False)
        self.workspace_stack.setCurrentWidget(self.workspace_content)
        self._clear_workspace_prompt_form()
        self.workspace_prompt_fields = {}
        self.workspace_prompt_callback = None
        if callback:
            callback(values)

    def _cancel_workspace_prompt(self) -> None:
        if hasattr(self, "workspace_overlay"):
            self.workspace_overlay.setVisible(False)
            self.workspace_stack.setCurrentWidget(self.workspace_content)
        self._clear_workspace_prompt_form()
        self.workspace_prompt_fields = {}
        self.workspace_prompt_callback = None
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
            self.run_git_command(["worktree", "add", path] + ([ref] if ref else []), callback=lambda _: self.refresh_all(), timeout=300)
        self.request_workspace_form(
            "Worktree Add",
            "一次性输入 worktree 路径和可选 ref。",
            [("path", "worktree 路径", "", False), ("ref", "分支 / commit / ref", "", False)],
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
            self.run_git_command(["submodule", "add", url] + ([path] if path else []), callback=lambda _: self.refresh_all(), timeout=900)
        self.request_workspace_form(
            "Submodule Add",
            "一次性输入子模块 URL 和可选本地路径。",
            [("url", "子模块 URL", "", False), ("path", "本地路径", "", False)],
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

    def _build_workspace_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        lists = QSplitter(Qt.Orientation.Horizontal)
        self.changed_list = QListWidget()
        self.staged_list = QListWidget()
        self.untracked_list = QListWidget()
        for title, widget in [("Changed", self.changed_list), ("Staged", self.staged_list), ("Untracked", self.untracked_list)]:
            box = QGroupBox(title)
            box_layout = QVBoxLayout(box)
            box_layout.addWidget(widget)
            lists.addWidget(box)
        layout.addWidget(lists, 2)

        btns = QGridLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setHorizontalSpacing(6)
        btns.setVerticalSpacing(4)
        for index, (text, handler) in enumerate([
            ("Stage Selected", self.stage_selected),
            ("Unstage Selected", self.unstage_selected),
            ("Stage All", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all())),
            ("Unstage All", lambda: self.run_git_command(["restore", "--staged", "."], callback=lambda _: self.refresh_all())),
            ("Restore Selected", self.restore_selected),
            ("Clean Untracked", self.clean_selected_untracked),
            ("Diff", self.show_selected_diff),
            ("Refresh", self.refresh_all),
        ]):
            button = QPushButton(text)
            button.clicked.connect(handler)
            btns.addWidget(button, index // 4, index % 4)
        layout.addLayout(btns)

        self.diff_view = QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setPlaceholderText("选择文件后显示 git diff / git diff --staged")
        layout.addWidget(self.diff_view, 3)

        commit_actions = QGridLayout()
        commit_button = QPushButton("Commit...")
        commit_button.clicked.connect(self.commit_changes)
        amend_button = QPushButton("Amend --no-edit")
        amend_button.clicked.connect(lambda: self.run_git_command(["commit", "--amend", "--no-edit"], callback=lambda _: self.refresh_all()))
        commit_actions.addWidget(commit_button, 0, 0)
        commit_actions.addWidget(amend_button, 0, 1)
        layout.addLayout(commit_actions)

        for widget in (self.changed_list, self.staged_list, self.untracked_list):
            widget.currentItemChanged.connect(lambda *_: self.show_selected_diff())
            widget.itemDoubleClicked.connect(lambda *_: self.show_selected_diff())

        self.tabs.addTab(page, "工作区")

    def _build_history_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.history_tree = QTreeWidget()
        self.history_tree.setColumnCount(6)
        self.history_tree.setHeaderLabels(["Graph", "Hash", "Date", "Author", "Refs", "Message"])
        self.history_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_tree.customContextMenuRequested.connect(self._commit_context_menu)
        self.history_tree.itemClicked.connect(self.show_commit_details)
        layout.addWidget(self.history_tree, 3)
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
            buttons.addWidget(b, index // 4, index % 4)
        layout.addLayout(buttons)
        self.commit_detail = QPlainTextEdit()
        self.commit_detail.setReadOnly(True)
        layout.addWidget(self.commit_detail, 2)
        self.tabs.addTab(page, "提交历史")

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
            row.addWidget(b, 1 + index // 4, index % 4)
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
        self.branch_graph_view.commitSelected.connect(self.graph_commit_selected)
        self.branch_graph_view.commitHovered.connect(self.graph_commit_selected)
        self.branch_graph_view.commitActivated.connect(self.graph_checkout_commit)
        self.branch_graph_view.commitContextRequested.connect(self.graph_commit_context_menu)
        graph_splitter.addWidget(self.branch_graph_view)
        self.branch_graph_detail = QPlainTextEdit()
        self.branch_graph_detail.setReadOnly(True)
        self.branch_graph_detail.setPlaceholderText("鼠标悬浮或单击图节点后显示 commit 详情")
        graph_splitter.addWidget(self.branch_graph_detail)
        graph_splitter.setStretchFactor(0, 5)
        graph_splitter.setStretchFactor(1, 2)
        graph_splitter.setSizes([780, 300])
        graph_layout.addWidget(graph_splitter, 1)
        self.branch_view_tabs.addTab(graph_page, "有向图")

        self.tabs.addTab(page, "分支")

    def _build_remote_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.remote_tree = QTreeWidget()
        self.remote_tree.setColumnCount(3)
        self.remote_tree.setHeaderLabels(["Remote", "Type", "URL"])
        layout.addWidget(self.remote_tree, 1)
        row = QGridLayout()
        row.setHorizontalSpacing(6)
        row.setVerticalSpacing(4)
        for index, (text, handler) in enumerate([
            ("remote -v", self.refresh_remotes),
            ("Add", self.add_remote),
            ("Remove", self.remove_remote),
            ("Set URL", self.set_remote_url),
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
        layout.addWidget(self.remote_output, 1)
        self.tabs.addTab(page, "远程")

    def _build_tag_stash_tab(self) -> None:
        page = QWidget()
        layout = QHBoxLayout(page)

        tag_box = QGroupBox("Tags")
        tag_layout = QVBoxLayout(tag_box)
        self.tag_list = QListWidget()
        tag_layout.addWidget(self.tag_list)
        self.new_tag_name = QLineEdit()
        self.new_tag_name.setPlaceholderText("v1.0.0")
        tag_layout.addWidget(self.new_tag_name)
        tag_buttons = QGridLayout()
        tag_buttons.setHorizontalSpacing(6)
        tag_buttons.setVerticalSpacing(4)
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
        layout.addWidget(tag_box)

        stash_box = QGroupBox("Stash")
        stash_layout = QVBoxLayout(stash_box)
        self.stash_list = QListWidget()
        stash_layout.addWidget(self.stash_list)
        self.stash_message = QLineEdit()
        self.stash_message.setPlaceholderText("stash message")
        stash_layout.addWidget(self.stash_message)
        stash_buttons = QGridLayout()
        stash_buttons.setHorizontalSpacing(6)
        stash_buttons.setVerticalSpacing(4)
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
        layout.addWidget(stash_box)
        self.tabs.addTab(page, "标签 / Stash")

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
            row.addWidget(b, index // 5, index % 5)
        layout.addLayout(row)
        self.conflict_preview = QPlainTextEdit()
        self.conflict_preview.setReadOnly(True)
        layout.addWidget(self.conflict_preview, 1)
        self.conflict_list.currentItemChanged.connect(lambda *_: self.show_conflict_file())
        self.tabs.addTab(page, "冲突")

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
            maintenance_layout.addWidget(b, index // 4, index % 4)
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
        self.tabs.addTab(page, "专家模式")

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
            row.addWidget(b, index // 4, index % 4)
        layout.addLayout(row)

        self.all_commands_output = QPlainTextEdit()
        self.all_commands_output.setReadOnly(True)
        layout.addWidget(self.all_commands_output, 1)
        self.tabs.addTab(page, "全部命令")
        self._command_changed()

    def _build_platform_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(
            "平台能力是增强模块：本地 Git 功能无需登录；GitHub 可优先调用 gh CLI，GitLab 可调用 glab CLI，"
            "Gitee/Bitbucket 可通过 token 或自定义 API 扩展。这里保留命令透明输出，不保存明文 token。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        row = QGridLayout()
        row.setHorizontalSpacing(6)
        row.setVerticalSpacing(4)
        for index, (text, cmd) in enumerate([
            ("gh auth status", ["gh", "auth", "status"]),
            ("gh repo list", ["gh", "repo", "list", "--limit", "50"]),
            ("gh pr list", ["gh", "pr", "list"]),
            ("gh issue list", ["gh", "issue", "list"]),
            ("gh release list", ["gh", "release", "list"]),
            ("glab auth status", ["glab", "auth", "status"]),
            ("glab mr list", ["glab", "mr", "list"]),
            ("glab issue list", ["glab", "issue", "list"]),
        ]):
            b = QPushButton(text)
            b.clicked.connect(lambda _, c=cmd: self.run_external_command(c))
            row.addWidget(b, index // 4, index % 4)
        layout.addLayout(row)

        gitee_box = QGroupBox("Gitee / 自定义平台 API 扩展点")
        gitee_form = QFormLayout(gitee_box)
        self.gitee_token = QLineEdit()
        self.gitee_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.gitee_token.setPlaceholderText("不建议长期明文保存；生产版应接入系统 Keychain")
        self.gitee_user = QLineEdit()
        self.gitee_user.setPlaceholderText("用户名 / org")
        gitee_form.addRow("Gitee Token", self.gitee_token)
        gitee_form.addRow("用户/组织", self.gitee_user)
        gitee_btns = QHBoxLayout()
        check_btn = QPushButton("检查 token / user repos")
        check_btn.clicked.connect(self.gitee_list_repos)
        gitee_btns.addWidget(check_btn)
        gitee_form.addRow(gitee_btns)
        layout.addWidget(gitee_box)

        self.platform_output = QPlainTextEdit()
        self.platform_output.setReadOnly(True)
        layout.addWidget(self.platform_output, 1)
        self.tabs.addTab(page, "平台")

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

        self.command_log = QPlainTextEdit()
        self.command_log.setObjectName("terminalOutput")
        self.command_log.setReadOnly(True)
        self.command_log.setMaximumBlockCount(5000)
        self.command_log.setMinimumHeight(0)
        self.command_log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.command_log, 1)

        input_bar = QFrame()
        input_bar.setObjectName("terminalInputBar")
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(10, 6, 10, 8)
        input_layout.setSpacing(8)
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
        input_layout.addWidget(prompt)
        input_layout.addWidget(self.raw_command, 1)
        input_layout.addWidget(run_btn)
        input_layout.addWidget(self.terminal_max_btn)
        input_layout.addWidget(self.terminal_hide_btn)
        input_layout.addWidget(clear_btn)
        layout.addWidget(input_bar)

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
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            if button.text() and not button.toolTip():
                button.setToolTip(button.text())
        for line_edit in self.findChildren(QLineEdit):
            if line_edit.objectName() == "workspacePromptInput":
                line_edit.setMinimumWidth(260)
                line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                continue
            line_edit.setMinimumWidth(0)
            line_edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        for combo in self.findChildren(QComboBox):
            combo.setMinimumWidth(0)
            combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
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

    def change_theme_mode(self, mode: str) -> None:
        self.theme_mode = mode
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self, self.theme_mode, self.theme_accent)
        if hasattr(self, "branch_graph_view"):
            self.branch_graph_view.set_theme(self.theme_mode)
            self.refresh_branch_graph()

    def change_theme_accent(self, accent: str) -> None:
        self.theme_accent = accent
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self, self.theme_mode, self.theme_accent)
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
            self.append_log(f"✓ {git.output}")
        else:
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
        self.append_log(f"{status} {result.command_text}\n{result.output or '(no output)'}")
        if callback:
            callback(result)

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
            proc = subprocess.run(cmd, cwd=self.runner.cwd(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.platform_output.setPlainText(out.strip() or "(no output)")
            self.append_log(("✓" if proc.returncode == 0 else "✗") + " " + " ".join(cmd) + "\n" + (out.strip() or "(no output)"))
        except Exception as exc:
            self.platform_output.setPlainText(str(exc))
            self.append_log("✗ " + str(exc))

    def append_log(self, text: str) -> None:
        if not hasattr(self, "command_log"):
            return
        self.command_log.appendPlainText(text.rstrip() + "\n")
        self.command_log.moveCursor(QTextCursor.MoveOperation.End)

    def show_result_in_log(self, result: GitResult) -> None:
        if hasattr(self, "advanced_output"):
            self.advanced_output.setPlainText(result.output)
        if hasattr(self, "all_commands_output"):
            self.all_commands_output.setPlainText(result.output)

    # ------------------------------------------------------------------
    # Repository lifecycle
    # ------------------------------------------------------------------
    def open_repository(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "打开 Git 仓库")
        if not directory:
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
        self.refresh_all()

    def init_repository(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择要初始化的目录")
        if not directory:
            return
        self.runner.set_repo(directory)
        self.run_git_command(["init"], callback=lambda _: self.refresh_all())

    def clone_repository(self) -> None:
        def submitted(values: dict[str, str]) -> None:
            url = values.get("url", "").strip()
            dest = values.get("dest", "").strip()
            if not url or not dest:
                self.append_log("Clone 已取消：缺少远程 URL 或目标父目录。")
                return
            parent = Path(dest)
            self.runner.repo_path = parent
            self.run_git_command(["clone", url], callback=lambda r: self._after_clone(r, parent), timeout=900)
        self.request_workspace_form(
            "Clone 远程仓库",
            "一次性输入远程 URL 和目标父目录。",
            [("url", "远程 URL", "", False), ("dest", "目标父目录", str(Path.cwd()), False)],
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
        self.refresh_all()

    def refresh_all(self) -> None:
        self.update_top_status()
        self.refresh_worktree()
        self.refresh_history(all_branches=True)
        self.refresh_branches()
        self.refresh_branch_graph()
        self.refresh_remotes()
        self.refresh_tags_stash()
        self.refresh_conflicts()

    def update_top_status(self) -> None:
        summary = self.runner.summarize()
        remote = ",".join(summary.remotes) if summary.remotes else "-"
        self.status_bar_label.setText(
            f"Repo: {summary.name} | Branch: {summary.branch} | HEAD: {summary.head} | "
            f"Remote: {remote} | Upstream: {summary.upstream} | Ahead: {summary.ahead} | "
            f"Behind: {summary.behind} | Dirty: {summary.dirty} | Mode: {summary.mode}"
        )

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------
    def refresh_worktree(self) -> None:
        for widget in (self.changed_list, self.staged_list, self.untracked_list):
            widget.clear()
        if not self.runner.repo_path:
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
            return
        args = ["diff", "--staged", "--", path] if area == "staged" else ["diff", "--", path]
        result = self.runner.run(args)
        self.diff_view.setPlainText(result.output or "(no diff)")

    def commit_changes(self) -> None:
        self.request_terminal_text(
            "Commit",
            "请输入 commit message：",
            lambda msg: self.run_git_command(["commit", "-m", msg.strip()], callback=lambda _: self.refresh_all()) if msg.strip() else self.append_log("Commit 已取消：提交信息为空。"),
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
            "--date=short",
            "--pretty=format:%H%x09%P%x09%h%x09%ad%x09%an%x09%D%x09%s",
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
            self.branch_graph_detail.setPlainText(result.output if not result.ok else "没有提交历史。")

    def fit_branch_graph(self) -> None:
        if hasattr(self, "branch_graph_view") and self.branch_graph_view.scene() is not None:
            rect = self.branch_graph_view.scene().sceneRect()
            if rect.isValid() and not rect.isEmpty():
                self.branch_graph_view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def graph_commit_selected(self, commit_hash: str) -> None:
        result = self.runner.run(["show", "--stat", "--pretty=fuller", commit_hash])
        self.branch_graph_detail.setPlainText(result.output)

    def graph_checkout_commit(self, commit_hash: str) -> None:
        self.run_git_command(["checkout", commit_hash], callback=lambda _: self.refresh_all())

    def graph_create_branch_from_commit(self, commit_hash: str) -> None:
        self.request_terminal_text(
            "从图节点创建分支",
            "分支名：",
            lambda name: self.run_git_command(["switch", "-c", name.strip(), commit_hash], callback=lambda _: self.refresh_all()) if name.strip() else None,
        )

    def graph_commit_context_menu(self, commit_hash: str, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction("Checkout this commit", lambda: self.graph_checkout_commit(commit_hash))
        menu.addAction("Create branch here", lambda: self.graph_create_branch_from_commit(commit_hash))
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

    def _selected_remote(self) -> Optional[str]:
        item = self.remote_tree.currentItem()
        return item.text(0) if item else None

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
